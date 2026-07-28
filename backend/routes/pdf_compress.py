"""Kompresi PDF — rantai: iLovePDF → pypdf lokal.

RIWAYAT YANG PENTING DIKETAHUI. Versi sebelumnya memanggil dua host yang
**tidak ada**: `api.iloveapi.com` dan `api.whipdoc.com`.

Cara temuan itu diperoleh, supaya bisa diperiksa ulang alih-alih dipercaya:
resolusi DNS dijalankan atas enam host sekaligus (`getent hosts` dan
`socket.gethostbyname`). Empat berhasil — termasuk domain telanjang
`iloveapi.com` dan `whipdoc.com`, jadi mereknya memang ada — sementara
persis kedua subdomain `api.*` di atas gagal. Host API v1 yang benar,
`api.ilovepdf.com`, teresolusi normal. Perhatikan bahwa panggilan HTTP tak
bisa dipakai sebagai bukti di sini: kebijakan jaringan CI menolak CONNECT ke
SEMUA host penyedia dengan 403, sehingga kegagalan HTTP tidak membedakan
apa pun. Yang membedakan hanyalah DNS.

Akibatnya seluruh rantai mati, tetapi endpoint tetap menjawab
200 dengan PDF ASLI dan header `X-Compression-Method: none` — kegagalan yang
tak pernah terlihat siapa pun kecuali di log server. Tiga pelajaran dipasang
permanen di berkas ini:

1.  **Host yang benar adalah `api.ilovepdf.com`.**
2.  **Alasan kegagalan ikut dikirim ke klien** (`X-Compression-Note`), supaya
    "tidak terkompresi" tak pernah lagi menyamar sebagai keberhasilan.
3.  **Selalu ada jaring pengaman lokal.** Jalur gambar sudah punya Pillow
    sejak awal; jalur PDF tidak — dan justru itu yang membuat matinya tak
    terdeteksi. Kini `pypdf` memegang peran itu.

Kontrak iLovePDF v1 (5 langkah, bukan 4):
    auth/self-sign → GET /v1/start/compress → POST {server}/v1/upload
    → POST {server}/v1/process → GET {server}/v1/download/{task}
Seluruh langkah 2-5 memakai `Authorization: Bearer <token>`.
"""
import io
import logging
import os
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

import pdf_compress_utils as pcu
from auth_utils import require_user, require_writer
from db import db
from shared_utils import limiter

logger = logging.getLogger(__name__)
pdf_compress_router = APIRouter()

ILOVEPDF_PUBLIC_KEY = os.environ.get("ILOVEAPI_PUBLIC_KEY", "")
ILOVEPDF_SECRET_KEY = os.environ.get("ILOVEAPI_SECRET_KEY", "")

# Host yang BENAR. `api.iloveapi.com` — yang dipakai versi lama — tidak pernah
# ada; jangan dikembalikan tanpa membuktikannya lewat DNS lebih dulu.
ILOVEPDF_API = "https://api.ilovepdf.com"

PDF_SERVICE_LIMITS = {"ilovepdf": 250}      # paket gratis

# Batas waktu per langkah. Unggah/proses PDF 25 MB bisa lama, tetapi tanpa
# plafon satu permintaan yang menggantung akan menahan worker tanpa batas.
TIMEOUT_DETIK = 90.0


# ── Kuota ──────────────────────────────────────────────────────────────────

def _bulan_ini() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


async def get_pdf_quota(service: str) -> dict:
    bulan = _bulan_ini()
    q = await db.pdf_compression_quotas.find_one(
        {"service": service, "month": bulan}, {"_id": 0})
    if not q:
        return {"service": service, "month": bulan, "used": 0,
                "limit": PDF_SERVICE_LIMITS.get(service, 100),
                "sisa_penyedia": None, "galat_terakhir": "", "terakhir_sukses": ""}
    return q


async def increment_pdf_quota(service: str, sisa_penyedia=None):
    """Tambah hitungan lokal, dan bila penyedia memberi tahu sisanya, simpan.

    `remaining_files` dari `/v1/start` adalah sumber kebenaran yang sebenarnya:
    hitungan lokal kita bisa meleset karena kredit yang sama dipakai aplikasi
    lain, karena restart, atau karena bulan berjalan berbeda dengan siklus
    tagihan iLovePDF.
    """
    ubah = {"$inc": {"used": 1},
            "$setOnInsert": {"limit": PDF_SERVICE_LIMITS.get(service, 100)},
            "$set": {"terakhir_sukses": datetime.now(timezone.utc).isoformat(),
                     "galat_terakhir": ""}}
    if sisa_penyedia is not None:
        ubah["$set"]["sisa_penyedia"] = int(sisa_penyedia)
    await db.pdf_compression_quotas.update_one(
        {"service": service, "month": _bulan_ini()}, ubah, upsert=True)


async def _catat_galat(service: str, alasan: str):
    """Rekam kegagalan terakhir supaya layar bisa menyatakannya.

    Tanpa ini, satu-satunya jejak kegagalan adalah baris log yang tak pernah
    dibaca — persis bagaimana host mati bisa bertahan berbulan-bulan.
    """
    await db.pdf_compression_quotas.update_one(
        {"service": service, "month": _bulan_ini()},
        {"$set": {"galat_terakhir": str(alasan)[:300],
                  "galat_pada": datetime.now(timezone.utc).isoformat()},
         "$setOnInsert": {"used": 0,
                          "limit": PDF_SERVICE_LIMITS.get(service, 100)}},
        upsert=True)


async def is_pdf_quota_available(service: str) -> bool:
    q = await get_pdf_quota(service)
    sisa = q.get("sisa_penyedia")
    if sisa is not None and int(sisa) <= 0:
        return False
    return q.get("used", 0) < q.get("limit", PDF_SERVICE_LIMITS.get(service, 100))


# ── iLovePDF ───────────────────────────────────────────────────────────────

def _token() -> str:
    """Token Bearer iLovePDF.

    Diutamakan JWT self-signed: secret key dipakai menandatangani secara LOKAL
    dan tak pernah dikirim ke jaringan. Bila hanya public key yang tersedia,
    pemanggil akan menempuh `/v1/auth`.
    """
    if ILOVEPDF_PUBLIC_KEY and ILOVEPDF_SECRET_KEY:
        return pcu.token_ilovepdf(ILOVEPDF_PUBLIC_KEY, ILOVEPDF_SECRET_KEY)
    return ""


async def _token_via_auth(client: httpx.AsyncClient) -> str:
    r = await client.post(f"{ILOVEPDF_API}/v1/auth",
                          json={"public_key": ILOVEPDF_PUBLIC_KEY})
    if r.status_code != 200:
        raise RuntimeError(f"auth ditolak ({r.status_code})")
    tok = (r.json() or {}).get("token") or ""
    if not tok:
        raise RuntimeError("auth tidak mengembalikan token")
    return tok


async def compress_pdf_ilovepdf(pdf_bytes: bytes, filename: str,
                                tingkat: str = pcu.TINGKAT_KOMPRESI_BAWAAN,
                                transport=None) -> tuple:
    """Kompres lewat iLovePDF. Kembalikan (bytes|None, metode|None, alasan).

    `alasan` selalu terisi saat gagal — itu yang dikirim ke klien, bukan
    ditelan diam-diam.
    """
    if not ILOVEPDF_PUBLIC_KEY:
        return None, None, "kunci iLovePDF belum dipasang"
    if not await is_pdf_quota_available("ilovepdf"):
        return None, None, "kuota iLovePDF habis bulan ini"

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_DETIK,
                                     transport=transport) as client:
            token = _token() or await _token_via_auth(client)
            h = {"Authorization": f"Bearer {token}"}

            # 1) start — nama alat ada di PATH, dan ini GET (bukan POST+body).
            r = await client.get(f"{ILOVEPDF_API}/v1/start/compress", headers=h)
            if r.status_code != 200:
                return None, None, f"start gagal ({r.status_code})"
            d = r.json() or {}
            server, task = d.get("server"), d.get("task")
            sisa = d.get("remaining_files")
            if not server or not task:
                return None, None, "start tak memberi server/task"

            # 2) upload
            r = await client.post(
                f"https://{server}/v1/upload", headers=h,
                data={"task": task},
                files={"file": (filename, pdf_bytes, "application/pdf")})
            if r.status_code != 200:
                return None, None, f"unggah gagal ({r.status_code})"
            server_filename = (r.json() or {}).get("server_filename")
            if not server_filename:
                return None, None, "unggah tak memberi server_filename"

            # 3) process — kuota terpakai DI SINI.
            r = await client.post(
                f"https://{server}/v1/process", headers=h,
                json={"task": task, "tool": "compress",
                      "files": [{"server_filename": server_filename,
                                 "filename": filename}],
                      "compression_level": pcu.tingkat_kompresi_sah(tingkat)})
            if r.status_code != 200:
                return None, None, f"proses gagal ({r.status_code})"
            ok, sebab = pcu.proses_berhasil(r.json() or {})
            if not ok:
                # HTTP 200 TAPI gagal — inilah kasus yang dulu tak terlihat.
                return None, None, f"proses ditolak: {sebab}"

            # 4) download
            r = await client.get(f"https://{server}/v1/download/{task}",
                                 headers=h)
            if r.status_code != 200:
                return None, None, f"unduh gagal ({r.status_code})"
            if not pcu.layak_dipakai(pdf_bytes, r.content):
                return None, None, "hasil iLovePDF tak lebih kecil / bukan PDF"

            await increment_pdf_quota("ilovepdf", sisa)
            return r.content, "ilovepdf", ""
    except Exception as e:
        # Nama galat saja, TANPA pesan: pesan httpx bisa memuat URL berisi
        # token. Rinciannya tetap masuk log server.
        logger.warning("iLovePDF gagal", exc_info=True)
        return None, None, f"iLovePDF tak terjangkau ({type(e).__name__})"


# ── Endpoint ───────────────────────────────────────────────────────────────

@pdf_compress_router.post("/compress-pdf")
@limiter.limit("12/minute")
async def compress_pdf(request: Request, file: UploadFile = File(...),
                       _user: dict = Depends(require_writer)):
    """Kompres PDF: iLovePDF → pypdf lokal → asli.

    `require_writer` (bukan `require_user`) dan ber-rate-limit: tiap panggilan
    membakar satu kredit iLovePDF berbayar. Tanpa keduanya, pengguna
    read-only pun bisa menguras kuota satker hanya dengan mengulang unggahan.
    """
    import asyncio

    pdf_bytes = await file.read()
    sah, galat = pcu.pdf_valid(pdf_bytes)
    if not sah:
        raise HTTPException(status_code=400, detail=galat)
    ukuran_asli = len(pdf_bytes)
    nama = pcu.nama_berkas_aman(file.filename)

    hasil, metode, alasan = await compress_pdf_ilovepdf(pdf_bytes, nama)
    if not hasil:
        if alasan:
            await _catat_galat("ilovepdf", alasan)
        # Jaring pengaman lokal — shapely-nya PDF: CPU-berat, jadi ke thread.
        lokal = await asyncio.to_thread(pcu.kompres_pdf_lokal, pdf_bytes)
        if lokal:
            hasil, metode = lokal, "pypdf-lokal"
            alasan = f"{alasan}; dipakai kompresi lokal" if alasan else ""

    if hasil and pcu.layak_dipakai(pdf_bytes, hasil):
        hemat = pcu.persen_hemat(ukuran_asli, len(hasil))
        logger.info("PDF %dKB → %dKB (%d%% via %s)",
                    ukuran_asli // 1024, len(hasil) // 1024, hemat, metode)
        isi, ukuran, cara, nama_out = hasil, len(hasil), metode, f"compressed_{nama}"
    else:
        isi, ukuran, cara, nama_out = pdf_bytes, ukuran_asli, "none", nama
        hemat = 0

    return StreamingResponse(io.BytesIO(isi), media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{nama_out}"',
        "X-Original-Size": str(ukuran_asli),
        "X-Compressed-Size": str(ukuran),
        "X-Compression-Method": cara,
        "X-Savings-Percent": str(hemat),
        # Alasan kegagalan IKUT TERKIRIM. Inilah bedanya dengan versi lama,
        # yang membiarkan "tak terkompresi" tampak seperti keberhasilan.
        "X-Compression-Note": pcu.nama_berkas_aman(alasan, "") or "",
        "Access-Control-Expose-Headers":
            "X-Original-Size,X-Compressed-Size,X-Compression-Method,"
            "X-Savings-Percent,X-Compression-Note",
    })


@pdf_compress_router.get("/pdf-compression-quotas")
async def get_pdf_compression_quotas(_user: dict = Depends(require_user)):
    """Status kuota. `tersedia` mencerminkan KEADAAN NYATA, bukan env var.

    Versi lama menghitung `available = bool(API_KEY)` — layanan yang host-nya
    tidak ada pun tampil hijau selamanya. Kini kunci yang terpasang hanya
    membuatnya "terkonfigurasi"; hijau menuntut bukti panggilan yang berhasil.
    """
    q = await get_pdf_quota("ilovepdf")
    terkonfigurasi = bool(ILOVEPDF_PUBLIC_KEY)
    return {"quotas": [{
        "service": "ilovepdf",
        "name": "iLovePDF",
        "used": q.get("used", 0),
        "limit": PDF_SERVICE_LIMITS["ilovepdf"],
        "remaining": max(0, PDF_SERVICE_LIMITS["ilovepdf"] - q.get("used", 0)),
        "sisa_penyedia": q.get("sisa_penyedia"),
        "terkonfigurasi": terkonfigurasi,
        "terakhir_sukses": q.get("terakhir_sukses", ""),
        "galat_terakhir": q.get("galat_terakhir", ""),
        # Hijau HANYA bila terkonfigurasi DAN pernah berhasil DAN tak sedang
        # galat. Kunci terpasang saja tidak membuktikan apa pun.
        "available": bool(terkonfigurasi and q.get("terakhir_sukses")
                          and not q.get("galat_terakhir")),
        "month": q.get("month", _bulan_ini()),
    }, {
        "service": "pypdf",
        "name": "Kompresi lokal (pypdf)",
        "used": 0, "limit": 0, "remaining": 0, "sisa_penyedia": None,
        "terkonfigurasi": True, "terakhir_sukses": "", "galat_terakhir": "",
        # Selalu tersedia: tak butuh kunci maupun jaringan. Inilah alasan ia ada.
        "available": True,
        "month": _bulan_ini(),
    }], "month": _bulan_ini()}
