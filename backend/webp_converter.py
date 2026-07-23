"""Konverter foto GridFS → WebP di latar belakang — adaptif-idle & aman.

Tujuan: mengonversi foto ASLI aset (``assets.photo_gridfs_ids``, JPEG di
GridFS) menjadi WebP sedikit demi sedikit menggunakan Tinify, TANPA mengganggu
performa aplikasi. Prinsip:

  • Idle-aware   — hanya bekerja saat aplikasi benar-benar sepi (tak ada
                   request selama ``IDLE_DETIK``); begitu ada aktivitas,
                   berhenti (lihat activity_tracker.py, lintas-worker).
  • Satu worker  — lease atomik MongoDB agar 2–4 worker uvicorn tak dobel
                   memproses / dobel membakar kuota.
  • Hemat kuota  — berhenti bila SISA kuota Tinify ≤ ``KUOTA_SISA_MIN`` (50).
  • Aman         — verifikasi berlapis SEBELUM menghapus blob lama: (1) sumber
                   JPEG valid, (2) hasil WebP terdekode + dimensi sama persis,
                   (3) blob baru terbaca ulang. Swap referensi ber-OCC (bump
                   version) → race dengan edit user tertutup. Blob lama dihapus
                   HANYA setelah semua verifikasi lolos.
  • Otomatis     — satu foto per siklus, berjeda; berhenti saat semua selesai;
                   bangun lagi berkala untuk foto baru.

Fase 1 (modul ini): foto asli aset. Thumbnail inline (kecil) & lampiran modul
menyusul di fase berikutnya (prioritas = foto asli, sesuai permintaan).

Kill-switch: env ``WEBP_KONVERSI_AKTIF=0`` menonaktifkan tanpa deploy ulang.
"""
import asyncio
import io
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from pymongo import ReturnDocument

from db import db, fs_bucket
from shared_utils import delete_photo_from_gridfs, get_photo_from_gridfs
import activity_tracker

logger = logging.getLogger(__name__)

# ── Konfigurasi (override via env) ──
AKTIF = os.environ.get("WEBP_KONVERSI_AKTIF", "1") != "0"
IDLE_DETIK = float(os.environ.get("WEBP_IDLE_DETIK", "90"))
JEDA_ANTAR_FOTO = float(os.environ.get("WEBP_JEDA_FOTO", "8"))
JEDA_CEK = float(os.environ.get("WEBP_JEDA_CEK", "30"))
JEDA_SELESAI = float(os.environ.get("WEBP_JEDA_SELESAI", "600"))
KUOTA_SISA_MIN = int(os.environ.get("WEBP_KUOTA_SISA_MIN", "50"))
MAKS_GAGAL = 3
LEASE_TTL = 120

_task = None
_worker_id = f"{os.getpid()}-{uuid.uuid4().hex[:6]}"


# ───────────────────────── helper murni (mudah diuji) ─────────────────────────

def _dimensi(image_bytes):
    """(lebar, tinggi) gambar, atau None bila tak terdekode."""
    if not image_bytes:
        return None
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes))
        img.load()
        return img.size
    except Exception:
        return None


def verifikasi_webp(webp_bytes, lebar, tinggi) -> bool:
    """True HANYA bila bytes adalah WebP valid, terdekode penuh, & dimensinya
    sama persis dengan (lebar, tinggi). Gerbang keamanan sebelum hapus lama."""
    if not webp_bytes or len(webp_bytes) < 32:
        return False
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(webp_bytes))
        img.load()
        if (img.format or "").upper() != "WEBP":
            return False
        return img.size == (lebar, tinggi)
    except Exception:
        return False


# ───────────────────────── Tinify & kuota ─────────────────────────

async def konversi_ke_webp(image_bytes):
    """Konversi bytes gambar → WebP via Tinify Convert API. None bila gagal /
    Tinify tak tersedia. Menaikkan penghitung kuota bersama saat sukses."""
    from shared_utils import TINIFY_AVAILABLE
    if not TINIFY_AVAILABLE:
        return None
    try:
        import tinify

        def _do():
            return tinify.from_buffer(image_bytes).convert(type="image/webp").to_buffer()

        buf = await asyncio.to_thread(_do)
        if buf:
            try:
                from routes.media import increment_quota
                await increment_quota("tinify")
            except Exception:
                pass
        return buf
    except Exception as e:
        logger.warning("WebP: konversi Tinify gagal: %s", e)
        return None


async def sisa_kuota_tinify() -> int:
    """Sisa kuota Tinify bulan ini (limit - used) dari penghitung Mongo bersama
    (murah, tanpa panggilan jaringan di loop panas)."""
    try:
        from routes.media import get_quota, SERVICE_LIMITS
        q = await get_quota("tinify")
        return int(q.get("limit", SERVICE_LIMITS.get("tinify", 500))) - int(q.get("used", 0))
    except Exception:
        return 0


# ───────────────────────── GridFS util ─────────────────────────

async def _simpan_webp(webp_bytes: bytes) -> str:
    """Simpan blob WebP baru ke GridFS; kembalikan id (str)."""
    fid = ObjectId()
    grid_in = fs_bucket.open_upload_stream_with_id(
        fid, filename=f"photo_{uuid.uuid4()}.webp",
        metadata={"content_type": "image/webp", "size": len(webp_bytes), "webp": True})
    await grid_in.write(webp_bytes)
    await grid_in.close()
    return str(fid)


async def _tandai_blob(old_id, **fields):
    """Set metadata pada fs.files (mis. webp_skip / webp_gagal) — best-effort."""
    try:
        await db["fs.files"].update_one(
            {"_id": old_id if isinstance(old_id, ObjectId) else ObjectId(old_id)},
            {"$set": {f"metadata.{k}": v for k, v in fields.items()}})
    except Exception:
        pass


async def _cari_kandidat():
    """Satu blob foto aset JPEG yang belum WebP & belum di-skip."""
    return await db["fs.files"].find_one({
        "metadata.content_type": "image/jpeg",
        "filename": {"$regex": "^photo_"},
        "metadata.webp_skip": {"$ne": True},
    }, {"_id": 1, "metadata.webp_gagal": 1})


# ───────────────────────── inti: konversi satu foto ─────────────────────────

async def konversi_satu() -> str:
    """Konversi SATU foto aset. Mengembalikan status:
    kosong | yatim | sumber_rusak | konversi_gagal | verifikasi_gagal |
    simpan_gagal | berubah | sukses."""
    f = await _cari_kandidat()
    if not f:
        return "kosong"
    old_id = f["_id"]
    old_id_str = str(old_id)

    # Aset pemilik (untuk swap referensi + OCC version). Hanya foto yang MASIH
    # direferensikan aset yang dikonversi — hindari bakar kuota utk yatim.
    asset = await db.assets.find_one({"photo_gridfs_ids": old_id_str},
                                     {"id": 1, "version": 1})
    if not asset:
        await _tandai_blob(old_id, webp_skip=True)
        return "yatim"

    old_bytes = await get_photo_from_gridfs(old_id_str)
    dims = _dimensi(old_bytes)
    if not old_bytes or not dims:
        await _tandai_blob(old_id, webp_skip=True)
        return "sumber_rusak"

    webp = await konversi_ke_webp(old_bytes)
    if not webp:
        n = int(((f.get("metadata") or {}).get("webp_gagal", 0))) + 1
        if n >= MAKS_GAGAL:
            await _tandai_blob(old_id, webp_skip=True)
        else:
            await _tandai_blob(old_id, webp_gagal=n)
        return "konversi_gagal"

    # Gerbang keamanan 1: hasil WebP utuh & dimensi identik dgn sumber.
    if not verifikasi_webp(webp, dims[0], dims[1]):
        await _tandai_blob(old_id, webp_skip=True)
        return "verifikasi_gagal"

    # Simpan blob baru, lalu gerbang keamanan 2: baca ULANG blob baru.
    new_id_str = await _simpan_webp(webp)
    cek = await get_photo_from_gridfs(new_id_str)
    if not cek or not verifikasi_webp(cek, dims[0], dims[1]):
        await delete_photo_from_gridfs(new_id_str)
        return "simpan_gagal"

    # Swap referensi ber-OCC: cocokkan version yg dibaca + id lama masih ada;
    # bump version agar PATCH foto user konkuren gagal OCC & retry (tak menimpa
    # dgn id lama yang akan dihapus). Operator posisi `$` mengganti elemen tepat.
    res = await db.assets.update_one(
        {"id": asset["id"], "version": asset.get("version", 0), "photo_gridfs_ids": old_id_str},
        {"$set": {"photo_gridfs_ids.$": new_id_str}, "$inc": {"version": 1}})
    if res.matched_count == 0:
        # Aset berubah selagi konversi → batalkan; buang blob baru (yatim).
        await delete_photo_from_gridfs(new_id_str)
        return "berubah"

    # Referensi sudah pindah & terverifikasi → aman menghapus blob lama.
    try:
        await delete_photo_from_gridfs(old_id_str)
    except Exception:
        pass
    return "sukses"


# ───────────────────────── lease worker tunggal ─────────────────────────

async def _pegang_lease() -> bool:
    """Klaim/renew lease worker tunggal. True bila worker INI pemegangnya."""
    now = datetime.now(timezone.utc)
    kadaluarsa = now + timedelta(seconds=LEASE_TTL)
    try:
        res = await db.app_runtime.find_one_and_update(
            {"_id": "webp_lease", "$or": [
                {"pemegang": _worker_id},
                {"kadaluarsa": {"$lt": now}},
                {"kadaluarsa": {"$exists": False}},
            ]},
            {"$set": {"pemegang": _worker_id, "kadaluarsa": kadaluarsa}},
            upsert=True, return_document=ReturnDocument.AFTER)
        return bool(res) and res.get("pemegang") == _worker_id
    except Exception:
        # Duplicate-key saat upsert = worker lain sudah pegang lease.
        return False


# ───────────────────────── loop utama ─────────────────────────

async def _loop():
    await asyncio.sleep(30)  # beri startup lain kesempatan selesai
    while True:
        try:
            if not AKTIF:
                await asyncio.sleep(300); continue
            if not await _pegang_lease():
                await asyncio.sleep(JEDA_CEK); continue
            if await sisa_kuota_tinify() <= KUOTA_SISA_MIN:
                await asyncio.sleep(1800); continue          # kuota reset bulanan
            if not await activity_tracker.aplikasi_idle(IDLE_DETIK):
                await asyncio.sleep(JEDA_CEK); continue        # ada aktivitas → tahan
            status = await konversi_satu()
            if status == "kosong":
                await asyncio.sleep(JEDA_SELESAI)              # semua selesai; cek berkala
            elif status == "sukses":
                logger.info("WebP: 1 foto asli dikonversi (sisa kuota dijaga > %s)", KUOTA_SISA_MIN)
                await asyncio.sleep(JEDA_ANTAR_FOTO)
            else:
                await asyncio.sleep(2)                          # lewati kandidat bermasalah
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("WebP konverter (non-fatal): %s", e)
            await asyncio.sleep(JEDA_CEK)


def start_webp_converter() -> None:
    """Start loop konverter WebP (idempoten, sekali per proses)."""
    global _task
    if _task is not None:
        return
    _task = asyncio.create_task(_loop())
    logger.info("Konverter WebP latar aktif=%s (idle=%ss, jeda=%ss, stop sisa kuota<=%s)",
                AKTIF, IDLE_DETIK, JEDA_ANTAR_FOTO, KUOTA_SISA_MIN)
