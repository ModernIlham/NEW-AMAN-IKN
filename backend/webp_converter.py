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

Fase A — foto ASLI aset & pegawai (GridFS via Tinify, dibatasi kuota).
Fase B — THUMBNAIL inline base64 (thumbnail/gallery_thumbnail/photo_thumbnails)
         di dokumen aset: re-encode JPEG→WebP secara LOKAL (PIL), TANPA Tinify
         (tak menyentuh kuota), sapuan sekali-jalan berbasis kursor `id`, OCC,
         dan HANYA disimpan bila hasil WebP lebih kecil (tak pernah memperburuk).
Keduanya idle & lease-gated; Fase B tetap jalan walau kuota foto asli habis.

Thumbnail BARU sudah langsung WebP di titik pembuatan (shared_utils.create_thumbnail);
Fase B menambal thumbnail LAMA (pra-deploy) yang masih JPEG.

Kill-switch: env ``WEBP_KONVERSI_AKTIF=0`` menonaktifkan tanpa deploy ulang.
"""
import asyncio
import base64
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

# ── Fase migrasi THUMBNAIL inline (lokal PIL, TANPA Tinify) ──
# Thumbnail (thumbnail/gallery_thumbnail/photo_thumbnails) tersimpan base64 JPEG
# di dalam dokumen aset. Re-encode ke WebP dilakukan LOKAL (PIL) sehingga TIDAK
# menyentuh kuota Tinify — jadi jalan walau kuota foto asli habis. Sapuan sekali-
# jalan berbasis kursor `id` (indeks unik) — hemat & tak scan berulang.
# max(1, ...): cegah footgun `.limit(0)` Mongo (= tanpa batas → muat seluruh koleksi).
THUMB_BATCH = max(1, int(os.environ.get("WEBP_THUMB_BATCH", "25")))
THUMB_WEBP_Q = int(os.environ.get("WEBP_THUMB_QUALITY", "80"))
_THUMB_CURSOR_ID = "webp_thumb_cursor"

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


# ───────────────── re-encode thumbnail inline JPEG → WebP (lokal) ─────────────

def _reencode_thumb_uri(uri):
    """Data-URI thumbnail JPEG → data-URI WebP, HANYA bila hasilnya lebih kecil.

    Mengembalikan None bila: bukan string / bukan JPEG data-URI / gagal decode /
    WebP tak lebih kecil (biar tak pernah memperburuk). Re-encode dari JPEG yang
    sudah lossy → pakai kualitas agak tinggi (THUMB_WEBP_Q) untuk menekan
    kehilangan; tetap sering lebih kecil karena WebP lebih efisien. Dimensi
    dipertahankan (tak resize)."""
    if not isinstance(uri, str) or not uri.startswith("data:image/jpeg"):
        return None
    try:
        from PIL import Image
        b = base64.b64decode(uri.split(",", 1)[1])
        img = Image.open(io.BytesIO(b))
        img.load()
        buf = io.BytesIO()
        img.save(buf, format="WEBP", quality=THUMB_WEBP_Q, method=6)
        wb = buf.getvalue()
        if not wb or len(wb) >= len(b):
            return None  # tak lebih kecil → biarkan JPEG apa adanya
        return "data:image/webp;base64," + base64.b64encode(wb).decode("ascii")
    except Exception:
        return None


def _reencode_thumbs(a):
    """Bangun dict field thumbnail yang perlu di-set (JPEG→WebP) untuk satu aset.
    Kosong bila tak ada yang berubah. Murni (tanpa I/O) → mudah diuji."""
    updates = {}
    for field in ("thumbnail", "gallery_thumbnail"):
        r = _reencode_thumb_uri(a.get(field))
        if r:
            updates[field] = r
    pts = a.get("photo_thumbnails")
    if isinstance(pts, list) and pts:
        baru = list(pts)
        berubah = False
        for i, t in enumerate(pts):
            r = _reencode_thumb_uri(t)
            if r:
                baru[i] = r
                berubah = True
        if berubah:
            updates["photo_thumbnails"] = baru
    return updates


async def _thumb_batch() -> str:
    """Sapuan SATU batch aset (kursor `id` menaik) → re-encode thumbnail inline
    JPEG ke WebP secara LOKAL (tanpa Tinify). OCC (version) menutup race dgn edit
    user. `updated_at` SENGAJA tak diubah agar tak memicu re-sync offline massal
    (pola sama dgn swap foto GridFS). Kembalian:
      kosong  — kursor sudah di ujung (sapuan selesai),
      sukses  — ada aset yang thumbnailnya dikonversi,
      lewat   — batch ada tapi tak ada yang perlu/lebih kecil (kursor tetap maju)."""
    cur = await db.app_runtime.find_one({"_id": _THUMB_CURSOR_ID})
    last_id = (cur or {}).get("last_id", "")
    proj = {"_id": 0, "id": 1, "version": 1,
            "thumbnail": 1, "gallery_thumbnail": 1, "photo_thumbnails": 1}
    batch = await (db.assets.find({"id": {"$gt": last_id}}, proj)
                   .sort("id", 1).limit(THUMB_BATCH).to_list(THUMB_BATCH))
    if not batch:
        return "kosong"
    diproses = 0
    for a in batch:
        updates = await asyncio.to_thread(_reencode_thumbs, a)
        if updates:
            res = await db.assets.update_one(
                {"id": a["id"], "version": a.get("version", 0)},
                {"$set": updates, "$inc": {"version": 1}})
            if res.matched_count:
                diproses += 1
        last_id = a["id"]
    await db.app_runtime.update_one(
        {"_id": _THUMB_CURSOR_ID}, {"$set": {"last_id": last_id}}, upsert=True)
    return "sukses" if diproses else "lewat"


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
            if not await activity_tracker.aplikasi_idle(IDLE_DETIK):
                await asyncio.sleep(JEDA_CEK); continue        # ada aktivitas → tahan

            kerja = False

            # Fase A: foto ASLI GridFS via Tinify — DIBATASI kuota bulanan.
            if await sisa_kuota_tinify() > KUOTA_SISA_MIN:
                status = await konversi_satu()
                if status == "sukses":
                    kerja = True
                    logger.info("WebP: 1 foto asli dikonversi (sisa kuota dijaga > %s)", KUOTA_SISA_MIN)
                elif status != "kosong":
                    kerja = True                                # kandidat bermasalah → lanjut cepat

            # Fase B: migrasi thumbnail inline JPEG→WebP — LOKAL (tanpa Tinify),
            # tetap jalan walau kuota foto asli habis.
            if (await _thumb_batch()) in ("sukses", "lewat"):
                kerja = True

            await asyncio.sleep(JEDA_ANTAR_FOTO if kerja else JEDA_SELESAI)
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
