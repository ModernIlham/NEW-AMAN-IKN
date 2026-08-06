"""
Image compression routes with multi-service fallback chain.
Chain: Tinify → Compresto → Uploadcare → Local (Pillow)
Quota tracking stored in MongoDB.

Provides: POST /compress-image, GET /compression-stats, GET /compression-quotas
Dependencies: tinify (optional), Pillow, httpx
"""
import io
import os
import base64
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from PIL import Image as PILImage, ImageOps
import httpx

from db import db
from auth_utils import require_user
from shared_utils import TINIFY_API_KEY, TINIFY_AVAILABLE

logger = logging.getLogger(__name__)
media_router = APIRouter()

# API Keys from environment
from kompresi_diagnostik import catat_percobaan, ringkas_layanan
from kompresi_rantai import URUTAN, layanan_aktif

COMPRESTO_API_KEY = os.environ.get("COMPRESTO_API_KEY", "")
UPLOADCARE_PUBLIC_KEY = os.environ.get("UPLOADCARE_PUBLIC_KEY", "")

# Service limits
SERVICE_LIMITS = {
    "tinify": 500,
    "compresto": 500,
    "uploadcare": 1000,  # Free tier ~1000/month
}


# ============================================================================
# QUOTA TRACKING
# ============================================================================
async def get_current_month():
    return datetime.now(timezone.utc).strftime("%Y-%m")


async def get_quota(service: str) -> dict:
    """Get quota usage for a service in current month."""
    month = await get_current_month()
    quota = await db.compression_quotas.find_one(
        {"service": service, "month": month}, {"_id": 0}
    )
    if not quota:
        return {"service": service, "month": month, "used": 0, "limit": SERVICE_LIMITS.get(service, 500)}
    return quota


async def increment_quota(service: str):
    """Increment usage count for a service."""
    month = await get_current_month()
    await db.compression_quotas.update_one(
        {"service": service, "month": month},
        {
            "$inc": {"used": 1},
            "$setOnInsert": {"limit": SERVICE_LIMITS.get(service, 500)},
        },
        upsert=True,
    )


async def is_quota_available(service: str) -> bool:
    """Check if quota is still available for a service."""
    quota = await get_quota(service)
    return quota["used"] < quota.get("limit", SERVICE_LIMITS.get(service, 500))


# ============================================================================
# Plafon piksel: 50 MP didekode Pillow ~150 MB RGB. Tanpa plafon, satu
# unggahan bisa menahan ratusan MB per permintaan.
MAKS_PIKSEL = 40_000_000

# ============================================================================
# COMPRESSION METHODS
# ============================================================================
def compress_with_pillow(image_bytes: bytes, max_size_kb: int = 500) -> bytes:
    """Kompresi lokal dengan Pillow (selalu tersedia).

    Tiga cacat yang dulu merusak foto bukti inventarisasi, kini ditutup:

    1.  **Orientasi EXIF dibuang.** Kamera HP menyimpan foto dalam orientasi
        sensor lalu menandai putarannya di tag EXIF `Orientation`. Karena
        blok EXIF tak ikut disimpan, foto tersimpan MIRING permanen — dan
        tanpa tag itu tak ada lagi informasi untuk membetulkannya otomatis.
        `exif_transpose` memutar pikselnya lebih dulu, sehingga hasilnya
        benar tanpa bergantung pada tag apa pun.
    2.  **PNG transparan dipaksa JPEG.** Pindaian dokumen, tangkapan layar
        SIMAN, dan spesimen tanda tangan potong kehilangan transparansi dan
        mendapat artefak JPEG pada garis tipis serta huruf kecil. Kini PNG
        tetap PNG.
    3.  **Tanpa plafon piksel.** Berkas 50 megapiksel didekode utuh ke RAM
        (~150 MB RGB) sebelum apa pun diperiksa.
    """
    try:
        img = PILImage.open(io.BytesIO(image_bytes))
        # Plafon piksel SEBELUM dekode penuh — pertahanan terhadap
        # "decompression bomb" sekaligus penjaga memori.
        if (img.width * img.height) > MAKS_PIKSEL:
            raise ValueError(f"Gambar {img.width}x{img.height} melebihi plafon piksel")
        # Putar dulu menurut EXIF, SEBELUM konversi mode apa pun.
        try:
            img = ImageOps.exif_transpose(img) or img
        except Exception:
            pass

        # PNG/GIF ber-transparansi tetap PNG. Meratakannya ke putih adalah
        # kerusakan yang tak bisa dibatalkan pada dokumen pindaian.
        punya_alfa = img.mode in ("RGBA", "LA") or (
            img.mode == "P" and "transparency" in img.info)
        if punya_alfa:
            keluar_png = io.BytesIO()
            img.save(keluar_png, format="PNG", optimize=True)
            hasil_png = keluar_png.getvalue()
            # Hanya dipakai bila memang lebih kecil; kalau tidak, kembalikan
            # yang asli daripada membengkakkannya.
            return hasil_png if len(hasil_png) < len(image_bytes) else image_bytes

        if img.mode != "RGB":
            img = img.convert("RGB")

        current_size = len(image_bytes) / 1024
        if current_size > max_size_kb:
            ratio = (max_size_kb / current_size) ** 0.5
            new_width = int(img.width * ratio)
            new_height = int(img.height * ratio)
            img = img.resize((new_width, new_height), PILImage.LANCZOS)

        output = io.BytesIO()
        quality = 85
        img.save(output, format='JPEG', quality=quality, optimize=True)
        while output.tell() / 1024 > max_size_kb and quality > 30:
            output = io.BytesIO()
            quality -= 10
            img.save(output, format='JPEG', quality=quality, optimize=True)
        return output.getvalue()
    except Exception as e:
        logger.error(f"Pillow compression error: {e}")
        raise


async def compress_with_tinify(image_bytes: bytes) -> Optional[bytes]:
    """Compress using Tinify API."""
    if not TINIFY_AVAILABLE:
        return None
    if not await is_quota_available("tinify"):
        logger.info("Tinify quota exhausted")
        return None
    try:
        import tinify

        def _kirim():
            # SELURUH panggilan dijalankan di thread — termasuk `from_buffer`.
            # Sebelumnya hanya `.to_buffer` yang dilempar ke thread, padahal
            # `tinify.from_buffer(...)` ITU SENDIRI melakukan POST /shrink
            # secara sinkron. Akibatnya event loop terhenti selama tiap
            # unggahan foto: simpan aset, sinkronisasi luring, dan permintaan
            # pengguna lain ikut membeku — gejalanya tampak seperti "server
            # lambat", bukan seperti kompresi yang memblokir.
            return tinify.from_buffer(image_bytes).to_buffer()

        compressed = await asyncio.to_thread(_kirim)
        await increment_quota("tinify")
        return compressed
    except Exception as e:
        logger.warning(f"Tinify error: {e}")
        return None


def _sekarang() -> str:
    """Cap waktu UTC ISO untuk catatan diagnostik."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _alasan_http(response) -> str:
    """Terjemahkan status HTTP jadi kalimat yang berguna bagi operator.

    Badan respons ikut dilampirkan (dipangkas) karena justru di situlah layanan
    biasanya menjelaskan penolakannya — dan tanpa itu, "gagal" tetap buntu.
    """
    kode = getattr(response, "status_code", None)
    try:
        cuplikan = (response.text or "")[:160].replace("\n", " ").strip()
    except Exception:
        cuplikan = ""
    dasar = {
        400: "Permintaan ditolak — format atau parameter tak sesuai kontrak layanan",
        401: "Kunci API ditolak (tidak sah)",
        402: "Layanan menolak: langganan/kuota berbayar bermasalah",
        403: "Kunci API tidak berhak atas operasi ini",
        404: "Alamat endpoint tidak ditemukan — kontrak API mungkin sudah berubah",
        413: "Berkas terlalu besar untuk layanan ini",
        429: "Batas laju layanan tercapai",
    }.get(kode)
    if dasar is None:
        dasar = ("Layanan sedang bermasalah" if (kode or 0) >= 500
                 else f"Layanan menjawab {kode}")
    return f"{dasar}{(' — ' + cuplikan) if cuplikan else ''}"


async def compress_with_compresto(image_bytes: bytes) -> Optional[bytes]:
    """Compress using Compresto API."""
    if not COMPRESTO_API_KEY:
        return None
    if not await is_quota_available("compresto"):
        logger.info("Compresto quota exhausted")
        catat_percobaan("compresto", False, waktu=_sekarang(),
                        alasan="Kuota bulanan sudah habis")
        return None
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.compresto.app/v1/compress",
                headers={"X-API-Key": COMPRESTO_API_KEY},
                files={"image": ("photo.jpg", image_bytes, "image/jpeg")},
                data={"quality": "80", "format": "jpeg"},
            )
            if response.status_code == 200:
                await increment_quota("compresto")
                catat_percobaan("compresto", True, waktu=_sekarang())
                return response.content
            elif response.status_code == 429:
                logger.warning("Compresto rate limit reached")
                catat_percobaan("compresto", False, kode_http=429, waktu=_sekarang(),
                                alasan="Batas laju layanan tercapai — tunggu lalu coba lagi")
                return None
            else:
                logger.warning(f"Compresto error {response.status_code}: {response.text[:200]}")
                catat_percobaan("compresto", False, kode_http=response.status_code,
                                waktu=_sekarang(), alasan=_alasan_http(response))
                return None
    except Exception as e:
        logger.warning(f"Compresto error: {e}")
        catat_percobaan("compresto", False, waktu=_sekarang(),
                        alasan=f"Tidak dapat menghubungi layanan: {type(e).__name__}: {e}")
        return None


async def compress_with_uploadcare(image_bytes: bytes) -> Optional[bytes]:
    """Compress using Uploadcare Upload API + CDN transformations."""
    if not UPLOADCARE_PUBLIC_KEY:
        return None
    if not await is_quota_available("uploadcare"):
        logger.info("Uploadcare quota exhausted")
        catat_percobaan("uploadcare", False, waktu=_sekarang(),
                        alasan="Kuota bulanan sudah habis")
        return None
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Upload to Uploadcare
            response = await client.post(
                "https://upload.uploadcare.com/base/",
                data={
                    "UPLOADCARE_PUB_KEY": UPLOADCARE_PUBLIC_KEY,
                    "UPLOADCARE_STORE": "0",  # Don't store permanently
                },
                files={"file": ("photo.jpg", image_bytes, "image/jpeg")},
            )
            if response.status_code != 200:
                logger.warning(f"Uploadcare upload error: {response.status_code}")
                catat_percobaan("uploadcare", False, kode_http=response.status_code,
                                waktu=_sekarang(), alasan=_alasan_http(response))
                return None

            file_id = response.json().get("file")
            if not file_id:
                catat_percobaan("uploadcare", False, kode_http=200, waktu=_sekarang(),
                                alasan="Respons unggah tak memuat id berkas — kontrak API berubah?")
                return None

            # Download compressed version via CDN with quality reduction
            cdn_url = f"https://ucarecdn.com/{file_id}/-/quality/smart/-/format/jpeg/"
            dl_response = await client.get(cdn_url)
            if dl_response.status_code == 200:
                await increment_quota("uploadcare")
                catat_percobaan("uploadcare", True, waktu=_sekarang())
                return dl_response.content
            else:
                logger.warning(f"Uploadcare CDN error: {dl_response.status_code}")
                catat_percobaan("uploadcare", False, kode_http=dl_response.status_code,
                                waktu=_sekarang(), alasan=f"CDN menolak: {_alasan_http(dl_response)}")
                return None
    except Exception as e:
        logger.warning(f"Uploadcare error: {e}")
        catat_percobaan("uploadcare", False, waktu=_sekarang(),
                        alasan=f"Tidak dapat menghubungi layanan: {type(e).__name__}: {e}")
        return None


# ============================================================================
# MAIN COMPRESSION FUNCTION (Fallback Chain)
# ============================================================================
# Fungsi kompresi per layanan JARINGAN. `pillow` sengaja TIDAK di sini: ia
# jaring terakhir yang tak pernah mengembalikan None dan tak berkuota, jadi
# perlakuannya berbeda (dipanggil setelah seluruh rantai gagal).
_FUNGSI_KOMPRESI = {
    "tinify": compress_with_tinify,
    "compresto": compress_with_compresto,
    "uploadcare": compress_with_uploadcare,
}


async def auto_compress_image(image_data_b64: str) -> tuple:
    """
    Auto-compress image using fallback chain:
    Tinify → Compresto → Uploadcare → Pillow (local)
    Returns: (compressed_b64, method, original_size, compressed_size)
    """
    try:
        if ',' in image_data_b64:
            _, encoded = image_data_b64.split(',', 1)
        else:
            encoded = image_data_b64

        image_bytes = base64.b64decode(encoded)
        original_size = len(image_bytes)

        # CHAIN: Tinify → Compresto → Uploadcare → Pillow
        #
        # Urutannya diambil dari `kompresi_rantai.URUTAN` — SATU sumber
        # kebenaran yang dipakai bersama indikator kuota di layar. Dulu daftar
        # ini ditulis ulang di sini; rantai dan indikatornya lalu bisa berbeda
        # tanpa ada yang menyadarinya. Uji anti-drift menagih keduanya sejalan.
        for method_name in URUTAN:
            compress_fn = _FUNGSI_KOMPRESI.get(method_name)
            if compress_fn is None:
                continue    # "pillow" bukan layanan jaringan — ditangani di bawah
            compressed = await compress_fn(image_bytes)
            if compressed and len(compressed) < original_size:
                compressed_b64 = base64.b64encode(compressed).decode('utf-8')
                return f"data:image/jpeg;base64,{compressed_b64}", method_name, original_size, len(compressed)

        # Final fallback: Pillow (always works)
        compressed = compress_with_pillow(image_bytes)
        compressed_b64 = base64.b64encode(compressed).decode('utf-8')
        return f"data:image/jpeg;base64,{compressed_b64}", "pillow", original_size, len(compressed)

    except Exception as e:
        logger.error(f"Auto-compress failed: {e}, using original")
        return image_data_b64, "none", 0, 0


# ============================================================================
# API ENDPOINTS
# ============================================================================
class CompressRequest(BaseModel):
    image_data: str

class CompressResponse(BaseModel):
    success: bool
    compressed_data: Optional[str] = None
    original_size: int = 0
    compressed_size: int = 0
    method: str = "none"
    error: Optional[str] = None


@media_router.post("/compress-image", response_model=CompressResponse)
async def compress_image(request: CompressRequest, _user: dict = Depends(require_user)):
    """Compress image using fallback chain: Tinify → Compresto → Uploadcare → Pillow"""
    try:
        compressed_b64, method, original_size, compressed_size = await auto_compress_image(request.image_data)
        return CompressResponse(
            success=True,
            compressed_data=compressed_b64,
            original_size=original_size,
            compressed_size=compressed_size,
            method=method,
        )
    except Exception:
        # Never leak internal exception detail to the client; log it server-side.
        logger.exception("Compression error")
        return CompressResponse(success=False, error="Gagal mengompres gambar")


@media_router.get("/compression-stats")
async def get_compression_stats(_user: dict = Depends(require_user)):
    """Get current Tinify compression usage stats (backward compatible)."""
    stats = {
        "tinify_available": TINIFY_AVAILABLE,
        "tinify_api_key_set": bool(TINIFY_API_KEY),
        "monthly_limit": 500,
        "compressions_this_month": 0,
        "remaining": 500,
    }
    if TINIFY_AVAILABLE:
        try:
            import tinify
            tinify.validate()
            stats["compressions_this_month"] = getattr(tinify, 'compression_count', 0) or 0
            stats["remaining"] = 500 - stats["compressions_this_month"]
        except Exception:
            # Jangan bocorkan pesan galat internal SDK ke klien.
            logger.warning("Gagal validasi Tinify saat ambil stats", exc_info=True)
            stats["error"] = "Gagal memuat kuota kompresi"
    return stats


@media_router.get("/compression-quotas")
async def get_all_compression_quotas(_user: dict = Depends(require_user)):
    """Get quota status for ALL compression services."""
    month = await get_current_month()
    quotas = []

    # Tinify
    tinify_quota = await get_quota("tinify")
    tinify_used = tinify_quota["used"]
    # Also check Tinify's own counter
    if TINIFY_AVAILABLE:
        try:
            import tinify
            tinify.validate()
            tinify_api_count = getattr(tinify, 'compression_count', 0) or 0
            if tinify_api_count > tinify_used:
                tinify_used = tinify_api_count
        except Exception:
            pass
    quotas.append({
        "service": "tinify",
        "name": "Tinify (TinyPNG)",
        "used": tinify_used,
        "limit": SERVICE_LIMITS["tinify"],
        "remaining": max(0, SERVICE_LIMITS["tinify"] - tinify_used),
        "available": bool(TINIFY_API_KEY),
        # `terpasang` = syarat masuk rantai, PERSIS seperti yang diperiksa
        # `compress_with_tinify`: pustaka ada DAN kunci ada. Kunci terisi
        # tanpa pustaka terpasang berarti layanannya tak pernah dipanggil.
        "terpasang": bool(TINIFY_API_KEY) and bool(TINIFY_AVAILABLE),
        "month": month,
    })

    # Compresto
    # `available` DULU berarti "env var terisi" — kebohongan yang membuat layar
    # tampak sehat sementara kompresinya tak pernah jalan. Kini ia berarti
    # "percobaan terakhir memang berhasil", dan sebab kegagalan ikut dibawa
    # sampai ke layar (lihat kompresi_diagnostik.py).
    compresto_quota = await get_quota("compresto")
    r = ringkas_layanan("compresto", bool(COMPRESTO_API_KEY),
                        compresto_quota["used"], SERVICE_LIMITS["compresto"])
    r.update({"name": "Compresto", "available": r["tersedia"],
              "terpasang": bool(COMPRESTO_API_KEY), "month": month})
    quotas.append(r)

    # Uploadcare
    uploadcare_quota = await get_quota("uploadcare")
    r = ringkas_layanan("uploadcare", bool(UPLOADCARE_PUBLIC_KEY),
                        uploadcare_quota["used"], SERVICE_LIMITS["uploadcare"])
    r.update({"name": "Uploadcare", "available": r["tersedia"],
              "terpasang": bool(UPLOADCARE_PUBLIC_KEY), "month": month})
    quotas.append(r)

    # Pillow (always available, unlimited)
    quotas.append({
        "service": "pillow",
        "name": "Lokal (Pillow)",
        "used": 0,
        "limit": -1,  # Unlimited
        "remaining": -1,
        "available": True,
        "terpasang": True,   # jaring terakhir — selalu ada, tanpa kuota
        "month": month,
    })

    # Layanan yang AKAN melayani permintaan berikutnya.
    #
    # Dihitung di server, bukan di layar, karena hanya di sinilah syarat
    # sesungguhnya diketahui — dan supaya jawabannya tak bisa berbeda antara
    # rantai dan indikatornya. Ini BUKAN `available`: `available` menjawab
    # "sudah terbukti berhasil sejak proses ini hidup" (catatan diagnostik di
    # memori, hangus tiap restart). Indikator kuota yang memakainya menampilkan
    # 0/500 milik Tinify padahal Compresto masih menyisakan ratusan — laporan
    # lapangan yang memunculkan perubahan ini.
    return {"quotas": quotas, "month": month,
            "aktif": layanan_aktif(quotas), "urutan": list(URUTAN)}
