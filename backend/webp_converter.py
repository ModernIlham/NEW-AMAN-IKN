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

async def _simpan_webp(webp_bytes: bytes, meta_tambahan=None) -> str:
    """Simpan blob WebP baru ke GridFS; kembalikan id (str). ``meta_tambahan``
    (mis. jenis/pegawai_id) DIPERTAHANKAN agar serve content-type-aware & query
    kandidat sumber tetap benar."""
    fid = ObjectId()
    meta = {"content_type": "image/webp", "size": len(webp_bytes), "webp": True}
    if meta_tambahan:
        meta.update({k: v for k, v in meta_tambahan.items() if v is not None})
    prefix = (meta_tambahan or {}).get("jenis") or "photo"
    grid_in = fs_bucket.open_upload_stream_with_id(
        fid, filename=f"{prefix}_{uuid.uuid4()}.webp", metadata=meta)
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


# ───────────────────────── sumber foto (registry) ─────────────────────────
# Tiap sumber punya: query kandidat fs.files, resolver pemilik (cek referensi +
# data untuk swap), dan swap referensi atomik. Ditambah sesuai PRIORITAS: foto
# ASLI aset lebih dulu, lalu foto pegawai. Menambah sumber = tambah satu entri.

async def _aset_pemilik(old_id_str, meta):
    return await db.assets.find_one({"photo_gridfs_ids": old_id_str}, {"id": 1, "version": 1})


async def _aset_swap(owner, old_id_str, new_id_str) -> bool:
    # OCC: cocokkan version yg dibaca + id lama masih ada; bump version agar
    # PATCH foto user konkuren gagal OCC & retry (tak menimpa dgn id yg dihapus).
    res = await db.assets.update_one(
        {"id": owner["id"], "version": owner.get("version", 0), "photo_gridfs_ids": old_id_str},
        {"$set": {"photo_gridfs_ids.$": new_id_str}, "$inc": {"version": 1}})
    return res.matched_count > 0


def _pegawai_pemilik(field):
    async def _p(old_id_str, meta):
        pid = meta.get("pegawai_id")
        if not pid:
            return None
        return await db.pegawai.find_one({"id": pid, field: old_id_str}, {"id": 1})
    return _p


def _pegawai_swap(field):
    # Swap optimistis berbasis id: cocok HANYA bila field masih menunjuk id
    # lama (mis. foto tak diganti user). Serve pegawai sudah content-type-aware.
    async def _s(owner, old_id_str, new_id_str) -> bool:
        res = await db.pegawai.update_one({"id": owner["id"], field: old_id_str},
                                          {"$set": {field: new_id_str}})
        return res.matched_count > 0
    return _s


SUMBER = [
    {   # Fase 1 — foto asli aset (prioritas)
        "nama": "aset",
        "query": {"metadata.content_type": "image/jpeg",
                  "filename": {"$regex": "^photo_"},
                  "metadata.jenis": {"$exists": False},
                  "metadata.webp_skip": {"$ne": True}},
        "pemilik": _aset_pemilik, "swap": _aset_swap, "meta": lambda m: {}},
    {   # Fase 2 — foto pegawai (tampil)
        "nama": "pegawai",
        "query": {"metadata.jenis": "foto_pegawai",
                  "metadata.content_type": {"$in": ["image/jpeg", "image/png"]},
                  "metadata.webp_skip": {"$ne": True}},
        "pemilik": _pegawai_pemilik("foto_file_id"), "swap": _pegawai_swap("foto_file_id"),
        "meta": lambda m: {"jenis": "foto_pegawai", "pegawai_id": m.get("pegawai_id")}},
    {   # Fase 2 — foto asli pegawai (sumber krop)
        "nama": "pegawai_asli",
        "query": {"metadata.jenis": "foto_pegawai_asli",
                  "metadata.content_type": {"$in": ["image/jpeg", "image/png"]},
                  "metadata.webp_skip": {"$ne": True}},
        "pemilik": _pegawai_pemilik("foto_asli_file_id"), "swap": _pegawai_swap("foto_asli_file_id"),
        "meta": lambda m: {"jenis": "foto_pegawai_asli", "pegawai_id": m.get("pegawai_id")}},
]


# ───────────────────────── inti: konversi satu foto ─────────────────────────

async def _proses_satu(sumber) -> str:
    """Konversi SATU foto dari satu sumber. None bila sumber tak punya kandidat;
    selain itu: yatim|sumber_rusak|konversi_gagal|verifikasi_gagal|simpan_gagal|
    berubah|sukses."""
    f = await db["fs.files"].find_one(sumber["query"], {"_id": 1, "metadata": 1})
    if not f:
        return None
    old_id = f["_id"]
    old_id_str = str(old_id)
    meta = f.get("metadata") or {}

    # Hanya blob yang MASIH direferensikan pemilik yang dikonversi (hindari bakar
    # kuota utk yatim).
    owner = await sumber["pemilik"](old_id_str, meta)
    if not owner:
        await _tandai_blob(old_id, webp_skip=True)
        return "yatim"

    old_bytes = await get_photo_from_gridfs(old_id_str)
    dims = _dimensi(old_bytes)
    if not old_bytes or not dims:
        await _tandai_blob(old_id, webp_skip=True)
        return "sumber_rusak"

    webp = await konversi_ke_webp(old_bytes)
    if not webp:
        n = int(meta.get("webp_gagal", 0)) + 1
        await _tandai_blob(old_id, **({"webp_skip": True} if n >= MAKS_GAGAL else {"webp_gagal": n}))
        return "konversi_gagal"

    # Gerbang keamanan 1: hasil WebP utuh & dimensi identik dgn sumber.
    if not verifikasi_webp(webp, dims[0], dims[1]):
        await _tandai_blob(old_id, webp_skip=True)
        return "verifikasi_gagal"

    # Simpan blob baru (metadata sumber dipertahankan), lalu gerbang keamanan 2:
    # baca ULANG blob baru.
    new_id_str = await _simpan_webp(webp, sumber["meta"](meta))
    cek = await get_photo_from_gridfs(new_id_str)
    if not cek or not verifikasi_webp(cek, dims[0], dims[1]):
        await delete_photo_from_gridfs(new_id_str)
        return "simpan_gagal"

    # Swap referensi atomik (OCC utk aset; id-match utk pegawai).
    if not await sumber["swap"](owner, old_id_str, new_id_str):
        # Pemilik berubah selagi konversi → batalkan; buang blob baru (yatim).
        await delete_photo_from_gridfs(new_id_str)
        return "berubah"

    # Referensi sudah pindah & terverifikasi → aman menghapus blob lama.
    try:
        await delete_photo_from_gridfs(old_id_str)
    except Exception:
        pass
    return "sukses"


async def konversi_satu() -> str:
    """Coba tiap sumber sesuai PRIORITAS (foto asli aset → foto pegawai).
    'kosong' HANYA bila semua sumber tak punya kandidat lagi."""
    for sumber in SUMBER:
        hasil = await _proses_satu(sumber)
        if hasil is not None:
            return hasil
    return "kosong"


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
