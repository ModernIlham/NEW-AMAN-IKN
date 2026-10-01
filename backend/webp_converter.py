"""Kompresi foto bertahap di latar belakang — adaptif-idle & aman.

Foto aset/pegawai di GridFS serta foto inline lama/checklist/kegiatan mendapat
giliran bergantian. Setiap hasil hemat >=1% kembali diantrekan; <1% berhenti.
Tidak memperkecil resolusi dan tidak menyentuh dokumen/TTD. Prinsip:

  • Idle-aware   — hanya bekerja saat aplikasi benar-benar sepi (tak ada
                   request selama ``IDLE_DETIK``); begitu ada aktivitas,
                   berhenti (lihat activity_tracker.py, lintas-worker).
  • Satu worker  — lease atomik MongoDB agar 2–4 worker uvicorn tak dobel
                   memproses / dobel membakar kuota.
  • Hemat kuota  — berhenti bila SISA kuota Tinify ≤ ``KUOTA_SISA_MIN`` (50).
  • Aman         — verifikasi berlapis SEBELUM menghapus blob lama: (1) sumber
                   raster statis valid, (2) WebP utuh + dimensi/alfa identik
                   dan penjaga kualitas, (3) blob baru terbaca ulang. Swap ber-OCC (bump
                   version) → race dengan edit user tertutup. Blob lama dihapus
                   HANYA setelah semua verifikasi lolos.
  • Otomatis     — satu foto per siklus, berjeda; berhenti saat semua selesai;
                   bangun lagi berkala untuk foto baru.

Fase A — foto aset, pegawai, inline/checklist/kegiatan via Tinify (kuota atomik).
Fase B — THUMBNAIL inline base64 (thumbnail/gallery_thumbnail/photo_thumbnails)
         di dokumen aset: re-encode JPEG→WebP secara LOKAL (PIL), TANPA Tinify
         (tak menyentuh kuota), sapuan berputar berbasis kursor `id`, OCC,
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
from foto_kompresi import AMBANG_HEMAT_PERSEN, sumber_foto_valid, verifikasi_foto
import activity_tracker

logger = logging.getLogger(__name__)

# ── Konfigurasi (override via env) ──
AKTIF = os.environ.get("WEBP_KONVERSI_AKTIF", "1") != "0"
IDLE_DETIK = float(os.environ.get("WEBP_IDLE_DETIK", "90"))
JEDA_ANTAR_FOTO = float(os.environ.get("WEBP_JEDA_FOTO", "8"))
JEDA_CEK = float(os.environ.get("WEBP_JEDA_CEK", "30"))
JEDA_SELESAI = float(os.environ.get("WEBP_JEDA_SELESAI", "600"))
KUOTA_SISA_MIN = int(os.environ.get("WEBP_KUOTA_SISA_MIN", "50"))
LEASE_TTL = 120

# ── Fase migrasi THUMBNAIL inline (lokal PIL, TANPA Tinify) ──
# Thumbnail (thumbnail/gallery_thumbnail/photo_thumbnails) tersimpan base64 JPEG
# di dalam dokumen aset. Re-encode ke WebP dilakukan LOKAL (PIL) sehingga TIDAK
# menyentuh kuota Tinify — jadi jalan walau kuota foto asli habis. Sapuan
# berbasis kursor `id` (indeks unik) — satu batch kecil per giliran.
# max(1, ...): cegah footgun `.limit(0)` Mongo (= tanpa batas → muat seluruh koleksi).
THUMB_BATCH = max(1, int(os.environ.get("WEBP_THUMB_BATCH", "25")))
THUMB_WEBP_Q = int(os.environ.get("WEBP_THUMB_QUALITY", "80"))
_THUMB_CURSOR_ID = "webp_thumb_cursor"

_task = None
_worker_id = f"{os.getpid()}-{uuid.uuid4().hex[:6]}"


# ── Pemakaian kuota bulanan (permintaan pemilik) ──
# Kuota Tinify hangus tiap pergantian bulan. Sepanjang bulan konversi dicicil
# di jam sepi dengan menyisakan bantalan `KUOTA_SISA_MIN` (agar unggahan user
# yang butuh Tinify tak kehabisan). Pada HARI TERAKHIR bulan, bantalan itu
# dilepas: sisa kuota lebih baik dipakai daripada hangus.
AMBANG_HEMAT_ULANG = AMBANG_HEMAT_PERSEN
WIB = timezone(timedelta(hours=7))
VERSI_PROGRES = 2
_sumber_berikut = 0


# ───────────────────────── helper murni (mudah diuji) ─────────────────────────

def hari_terakhir_bulan(sekarang) -> bool:
    """True bila `sekarang` jatuh pada HARI TERAKHIR bulan (zona waktunya
    sendiri). MURNI.

    Dipakai untuk memutuskan kapan bantalan kuota dilepas. Memakai "besok
    bulannya berbeda" alih-alih tabel jumlah hari — otomatis benar untuk
    Februari maupun tahun kabisat.
    """
    if sekarang is None:
        return False
    return (sekarang + timedelta(days=1)).month != sekarang.month


def ambang_kuota_sisa(sekarang, ambang_normal=None) -> int:
    """Berapa sisa kuota yang HARUS dijaga. MURNI.

    Hari terakhir bulan → 0 (habiskan; besok hangus). Selain itu → bantalan
    normal, supaya konversi tercicil dan tak memakan jatah unggahan user.
    """
    normal = KUOTA_SISA_MIN if ambang_normal is None else int(ambang_normal)
    return 0 if hari_terakhir_bulan(sekarang) else normal


def hemat_persen(ukuran_lama, ukuran_baru) -> float:
    """Persen penghematan ukuran; negatif bila hasilnya justru membesar.
    MURNI. Sumber 0/negatif → 0.0 (tak ada yang bisa dihemat)."""
    try:
        lama, baru = float(ukuran_lama or 0), float(ukuran_baru or 0)
    except (TypeError, ValueError):
        return 0.0
    if lama <= 0:
        return 0.0
    return (lama - baru) / lama * 100.0


def layak_ganti(ukuran_lama, ukuran_baru, ambang_persen=0.0) -> bool:
    """Apakah blob baru LAYAK menggantikan yang lama. MURNI.

    `ambang_persen=0` (konversi pertama JPEG→WebP): cukup lebih kecil. Ini
    penjaga disk — tanpanya sebuah JPEG bisa digantikan WebP yang JUSTRU lebih
    besar, dan penyimpanan membengkak alih-alih menyusut.

    `ambang_persen=1` (konversi ULANG WebP→WebP): hemat harus berarti.
    Menukar blob demi 0,3% hanya membakar kuota dan menulis ulang disk tanpa
    manfaat — pemilik meminta berhenti di bawah 1%.
    """
    if not ukuran_baru or int(ukuran_baru) <= 0:
        return False
    hemat = hemat_persen(ukuran_lama, ukuran_baru)
    # `hemat > 0` WAJIB, bukan hanya `>= ambang`: dengan ambang 0, ukuran yang
    # SAMA PERSIS akan lolos (0 >= 0) dan blob ditukar tanpa manfaat apa pun —
    # membakar kuota sekaligus menulis ulang disk untuk hasil identik.
    return hemat > 0 and hemat >= float(ambang_persen)

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
        # Foto lama dapat ditambahkan/berubah setelah kursor lewat. Sapuan
        # berikutnya harus mengunjungi ulang, termasuk konflik OCC sebelumnya.
        await db.app_runtime.update_one(
            {"_id": _THUMB_CURSOR_ID}, {"$set": {"last_id": ""}}, upsert=True)
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

async def konversi_ke_webp(image_bytes, cadangan=0):
    """Satu gerbang kuota bersama unggahan; galat dibedakan dari plateau."""
    from tinify_service import optimalkan
    return await optimalkan(image_bytes, webp=True, cadangan=cadangan)


async def sisa_kuota_tinify() -> int:
    """Sisa kuota Tinify bulan ini (limit - used) dari penghitung Mongo bersama
    (murah, tanpa panggilan jaringan di loop panas)."""
    try:
        from tinify_service import status_kuota
        q = await status_kuota()
        return max(0, int(q.get("remaining", 0))) if q.get("tersedia") else 0
    except Exception:
        return 0


# ───────────────────────── GridFS util ─────────────────────────

async def _simpan_webp(webp_bytes: bytes, meta_tambahan=None) -> str:
    """Simpan blob WebP baru ke GridFS; kembalikan id (str). ``meta_tambahan``
    (mis. jenis/pegawai_id) DIPERTAHANKAN agar serve content-type-aware & query
    kandidat sumber tetap benar."""
    fid = ObjectId()
    meta = {}
    if meta_tambahan:
        meta.update({k: v for k, v in meta_tambahan.items() if v is not None})
    meta.update({"content_type": "image/webp", "size": len(webp_bytes), "webp": True})
    prefix = (meta_tambahan or {}).get("jenis") or "photo"
    grid_in = fs_bucket.open_upload_stream_with_id(
        fid, filename=f"{prefix}_{uuid.uuid4()}.webp", metadata=meta)
    try:
        await grid_in.write(webp_bytes)
        await grid_in.close()
    except BaseException:
        await grid_in.abort()
        raise
    return str(fid)


async def _tandai_blob(old_id, **fields):
    """Catat progres; galat DB diteruskan agar scheduler menahan percobaan."""
    await db["fs.files"].update_one(
        {"_id": old_id if isinstance(old_id, ObjectId) else ObjectId(old_id)},
        {"$set": {f"metadata.{k}": v for k, v in fields.items()}})


# ───────────────────────── sumber foto (registry) ─────────────────────────
# Tiap sumber punya: query kandidat fs.files, resolver pemilik (cek referensi +
# data untuk swap), dan swap referensi atomik. Scheduler memberi giliran
# round-robin agar backlog satu sumber tidak membuat sumber lain kelaparan.

async def _aset_pemilik(old_id_str, meta):
    return await db.assets.find_one({"photo_gridfs_ids": old_id_str}, {"id": 1, "version": 1})


async def _aset_swap(owner, old_id_str, new_id_str) -> bool:
    # OCC: cocokkan version yg dibaca + id lama masih ada; bump version agar
    # PATCH foto user konkuren gagal OCC & retry (tak menimpa dgn id yg dihapus).
    res = await db.assets.update_one(
        {"id": owner["id"], "version": owner["version"] if "version" in owner else {"$exists": False},
         "photo_gridfs_ids": old_id_str},
        {"$set": {"photo_gridfs_ids.$": new_id_str,
                  "updated_at": datetime.now(timezone.utc).isoformat()}, "$inc": {"version": 1}})
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


def _meta_foto(meta):
    """Pertahankan asal/ukuran awal; jangan bawa penanda gagal warisan."""
    return {k: v for k, v in meta.items()
            if k not in {"webp_skip", "webp_gagal", "webp_ulang_selesai", "webp_progres"}}


SUMBER = [
    {   # Fase 1 — foto asli aset (prioritas)
        "nama": "aset",
        "query": {"metadata.content_type": {"$in": ["image/jpeg", "image/png"]},
                  "filename": {"$regex": "^photo_"},
                  "metadata.jenis": {"$exists": False}, "metadata.kind": {"$exists": False}},
        "pemilik": _aset_pemilik, "swap": _aset_swap, "meta": _meta_foto},
    {   # Fase 2 — foto pegawai (tampil)
        "nama": "pegawai",
        "query": {"metadata.jenis": "foto_pegawai",
                  "metadata.content_type": {"$in": ["image/jpeg", "image/png"]}},
        "pemilik": _pegawai_pemilik("foto_file_id"), "swap": _pegawai_swap("foto_file_id"),
        "meta": _meta_foto},
    {   # Fase 2 — foto asli pegawai (sumber krop)
        "nama": "pegawai_asli",
        "query": {"metadata.jenis": "foto_pegawai_asli",
                  "metadata.content_type": {"$in": ["image/jpeg", "image/png"]}},
        "pemilik": _pegawai_pemilik("foto_asli_file_id"), "swap": _pegawai_swap("foto_asli_file_id"),
        "meta": _meta_foto},
    # ── Fase 3 — KONVERSI ULANG WebP yang sudah ada (permintaan pemilik) ──
    # Foto WebP juga mendapat giliran; plateau lama tetap dihormati.
    # Penanda skip/gagal lama tidak disaring karena dulunya mencampur galat
    # jaringan dengan foto rusak. Progres v2 mencatat alasan dan retry terpisah.
    {
        "nama": "aset_ulang",
        "query": {"metadata.content_type": "image/webp",
                  "filename": {"$regex": "^photo_"},
                  "metadata.jenis": {"$exists": False}, "metadata.kind": {"$exists": False},
                  "metadata.webp_ulang_selesai": {"$ne": True}},
        "pemilik": _aset_pemilik, "swap": _aset_swap, "meta": _meta_foto,
        "ambang_hemat": AMBANG_HEMAT_ULANG, "tanda_selesai": "webp_ulang_selesai"},
    {
        "nama": "pegawai_ulang",
        "query": {"metadata.jenis": "foto_pegawai",
                  "metadata.content_type": "image/webp",
                  "metadata.webp_ulang_selesai": {"$ne": True}},
        "pemilik": _pegawai_pemilik("foto_file_id"), "swap": _pegawai_swap("foto_file_id"),
        "meta": _meta_foto,
        "ambang_hemat": AMBANG_HEMAT_ULANG, "tanda_selesai": "webp_ulang_selesai"},
    {
        "nama": "pegawai_asli_ulang",
        "query": {"metadata.jenis": "foto_pegawai_asli",
                  "metadata.content_type": "image/webp",
                  "metadata.webp_ulang_selesai": {"$ne": True}},
        "pemilik": _pegawai_pemilik("foto_asli_file_id"), "swap": _pegawai_swap("foto_asli_file_id"),
        "meta": _meta_foto,
        "ambang_hemat": AMBANG_HEMAT_ULANG, "tanda_selesai": "webp_ulang_selesai"},
]


# ───────────────────────── inti: konversi satu foto ─────────────────────────

async def _catat_progres(old_id, meta, status, **tambahan):
    progres = dict(meta.get("webp_progres") or {})
    progres.update(v=VERSI_PROGRES, status=status, diperiksa=datetime.now(timezone.utc))
    progres.update(tambahan)
    await _tandai_blob(old_id, webp_progres=progres)


async def _masih_dirujuk(fid):
    """Backup/impor lama bisa berbagi blob. Jangan putus referensi lainnya."""
    if await db.assets.find_one({"photo_gridfs_ids": fid}, {"_id": 1}):
        return True
    return bool(await db.pegawai.find_one(
        {"$or": [{"foto_file_id": fid}, {"foto_asli_file_id": fid}]}, {"_id": 1}))


async def _proses_satu(sumber, cadangan=0) -> str:
    """Konversi SATU foto; None bila tidak ada kandidat yang boleh dicoba kini.
    Galat sementara tetap diantrekan; kualitas meragukan ditahan untuk review."""
    now = datetime.now(timezone.utc)
    query = {"$and": [sumber["query"], {
        "metadata.webp_progres.status": {"$nin": ["plateau", "perlu_periksa", "yatim"]},
        "$or": [{"metadata.webp_progres.retry_at": {"$exists": False}},
                # Arsip GridFS lama menulis datetime sebagai string JSON.
                # Re-evaluasi sekali setelah restore, jangan kunci selamanya.
                {"metadata.webp_progres.retry_at": {"$not": {"$type": "date"}}},
                {"metadata.webp_progres.retry_at": {"$lte": now}}],
    }]}
    # Yang belum pernah dicoba lebih dulu, kemudian hasil putaran terdahulu.
    f = await db["fs.files"].find_one(query, {"_id": 1, "metadata": 1},
                                    sort=[("metadata.webp_progres.diperiksa", 1), ("_id", 1)])
    if not f:
        return None
    old_id = f["_id"]
    old_id_str = str(old_id)
    meta = f.get("metadata") or {}

    # Hanya blob yang MASIH direferensikan pemilik yang dikonversi (hindari bakar
    # kuota utk yatim).
    owner = await sumber["pemilik"](old_id_str, meta)
    if not owner:
        await _catat_progres(old_id, meta, "yatim")
        return "yatim"

    old_bytes = await get_photo_from_gridfs(old_id_str)
    if not old_bytes:
        # GridFS gagal dibaca bisa sementara; bukan bukti bahwa foto rusak.
        await _catat_progres(old_id, meta, "menunggu", retry_at=now + timedelta(minutes=15))
        return "konversi_gagal"
    if not await asyncio.to_thread(sumber_foto_valid, old_bytes):
        await _catat_progres(old_id, meta, "perlu_periksa", alasan="sumber_tidak_layak")
        return "sumber_rusak"

    if not await _lease_masih_milik():
        return "berubah"
    hasil = await konversi_ke_webp(old_bytes, cadangan=cadangan)
    webp = hasil.data
    if hasil.status != "ok" or not webp:
        if hasil.status == "input_rusak":
            await _catat_progres(old_id, meta, "perlu_periksa", alasan="input_ditolak")
        else:
            n = int((meta.get("webp_progres") or {}).get("percobaan_gagal", 0)) + 1
            retry = hasil.retry_at or now + timedelta(seconds=min(3600, 60 * 2 ** min(n, 6)))
            await _catat_progres(old_id, meta, "menunggu", retry_at=retry,
                                 percobaan_gagal=n, alasan=hasil.status)
        return hasil.status

    # Gerbang keamanan 1: hasil WebP utuh & dimensi identik dgn sumber.
    if not await asyncio.to_thread(verifikasi_foto, old_bytes, webp):
        await _catat_progres(old_id, meta, "perlu_periksa", alasan="hasil_tidak_aman")
        return "verifikasi_gagal"

    # Gerbang DISK: blob baru harus benar-benar lebih hemat. Tanpa ini sebuah
    # foto bisa digantikan hasil yang JUSTRU lebih besar — penyimpanan
    # membengkak padahal tujuannya menyusutkan. Untuk konversi ULANG, ambangnya
    # 1%: menukar blob demi hemat sepersekian persen hanya membakar kuota.
    ambang = AMBANG_HEMAT_PERSEN
    if not layak_ganti(len(old_bytes), len(webp), ambang):
        # Ditandai PERMANEN supaya tak dicoba lagi tiap putaran — inilah yang
        # membuat konverter berhenti sendiri saat semua sudah mentok.
        await _catat_progres(old_id, meta, "plateau", retry_at=now,
                             hemat_terakhir=hemat_persen(len(old_bytes), len(webp)),
                             ukuran_sekarang=len(old_bytes))
        return "hemat_tipis"

    # Simpan blob baru (metadata sumber dipertahankan), lalu gerbang keamanan 2:
    # baca ULANG blob baru.
    baru_meta = sumber["meta"](meta)
    lama_progres = meta.get("webp_progres") or {}
    baru_meta["webp_progres"] = {
        "v": VERSI_PROGRES, "status": "menunggu", "diperiksa": now,
        "putaran": int(lama_progres.get("putaran", 0)) + 1,
        "ukuran_awal_teramati": lama_progres.get("ukuran_awal_teramati", len(old_bytes)),
        "ukuran_sekarang": len(webp), "hemat_terakhir": hemat_persen(len(old_bytes), len(webp)),
    }
    new_id_str = await _simpan_webp(webp, baru_meta)
    cek = await get_photo_from_gridfs(new_id_str)
    if not cek or cek != webp:
        await delete_photo_from_gridfs(new_id_str)
        return "simpan_gagal"

    # Swap referensi atomik (OCC utk aset; id-match utk pegawai).
    if not await _lease_masih_milik() or not await sumber["swap"](owner, old_id_str, new_id_str):
        # Pemilik berubah selagi konversi → batalkan; buang blob baru (yatim).
        await delete_photo_from_gridfs(new_id_str)
        await _catat_progres(old_id, meta, "menunggu", retry_at=now + timedelta(minutes=5))
        return "berubah"

    # Referensi sudah pindah & terverifikasi → aman menghapus blob lama.
    try:
        if not await _masih_dirujuk(old_id_str):
            await delete_photo_from_gridfs(old_id_str)
    except Exception:
        pass
    return "sukses"


async def konversi_satu(cadangan=0) -> str:
    """Round-robin antarsumber: backlog aset tak mengunci foto pegawai/inline."""
    global _sumber_berikut
    from foto_inline_optimizer import proses_satu as proses_inline
    jumlah = len(SUMBER) + 1
    for _ in range(jumlah):
        idx = _sumber_berikut % jumlah
        _sumber_berikut = (idx + 1) % jumlah
        if idx == len(SUMBER):
            hasil = await proses_inline(cadangan=cadangan, masih_berwenang=_lease_masih_milik)
        else:
            hasil = await _proses_satu(SUMBER[idx], cadangan=cadangan)
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


async def _lease_masih_milik() -> bool:
    # Pause juga saat restore: dokumen induk/GridFS sedang diganti sebagai
    # satu himpunan, sehingga hasil lama tak boleh diterapkan di tengahnya.
    from pemeliharaan import pemeliharaan_aktif
    if await pemeliharaan_aktif():
        return False
    return bool(await db.app_runtime.find_one({
        "_id": "webp_lease", "pemegang": _worker_id,
        "kadaluarsa": {"$gt": datetime.now(timezone.utc)},
    }, {"_id": 1}))


async def _perpanjang_lease() -> bool:
    now = datetime.now(timezone.utc)
    res = await db.app_runtime.update_one(
        {"_id": "webp_lease", "pemegang": _worker_id, "kadaluarsa": {"$gt": now}},
        {"$set": {"kadaluarsa": now + timedelta(seconds=LEASE_TTL)}})
    return res.matched_count > 0


async def _kerja_dengan_lease(cadangan):
    """Perbarui lease selama I/O; kehilangan lease membatalkan HTTP async.

    Tidak menghidupkan lease yang sudah kedaluwarsa. Pemeriksaan sebelum
    API/swap membatasi hasil tertunda agar tak mengambil alih worker baru.
    """
    async def heartbeat():
        while True:
            await asyncio.sleep(LEASE_TTL / 4)
            if not await _perpanjang_lease():
                raise RuntimeError("lease_kompresi_hilang")

    proses = asyncio.create_task(konversi_satu(cadangan=cadangan))
    penjaga = asyncio.create_task(heartbeat())
    try:
        done, _ = await asyncio.wait({proses, penjaga}, return_when=asyncio.FIRST_COMPLETED)
        if penjaga in done:
            await penjaga
        return await proses
    finally:
        for task in (proses, penjaga):
            if not task.done():
                task.cancel()
        await asyncio.gather(proses, penjaga, return_exceptions=True)


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

            # Fase A: foto GridFS via Tinify — dibatasi kuota bulanan, KECUALI
            # pada hari terakhir bulan: bantalan dilepas agar sisa kuota
            # terpakai habis alih-alih hangus saat bulan berganti.
            # Periode UTC konsisten dengan penghitung kuota, bukan WIB lokal.
            ambang = ambang_kuota_sisa(datetime.now(timezone.utc))
            if await sisa_kuota_tinify() > ambang:
                status = await _kerja_dengan_lease(ambang)
                if status == "sukses":
                    kerja = True
                    logger.info("WebP: 1 foto dikonversi (bantalan kuota %s)", ambang)
                elif status == "hemat_tipis":
                    kerja = True
                    logger.info("WebP: hemat < ambang — blob ditandai selesai, lanjut kandidat lain")
                elif status not in ("kosong", "kuota", "sementara", "tidak_tersedia"):
                    kerja = True                                # kandidat bermasalah → lanjut cepat

            # Fase B: migrasi thumbnail inline JPEG→WebP — LOKAL (tanpa Tinify),
            # tetap jalan walau kuota foto asli habis.
            if await _lease_masih_milik() and (await _thumb_batch()) in ("sukses", "lewat"):
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


async def stop_webp_converter() -> None:
    """Hentikan loop konverter (dipanggil saat shutdown — temuan U22)."""
    global _task
    t, _task = _task, None
    if t is None:
        return
    t.cancel()
    try:
        await t
    except (asyncio.CancelledError, Exception):    # noqa: BLE001
        pass


async def ringkasan_progres() -> dict:
    """Diagnostik admin, bukan klaim semua foto selesai berdasarkan ledger.

    GridFS mencakup blob sumber dalam registry (termasuk yatim). Ledger inline
    menghitung hash yang pernah diamati, bukan banyaknya foto hidup. Foto baru
    atau belum disapu tidak boleh diam-diam dihitung plateau.
    """
    query = {"$or": [{k: v for k, v in s["query"].items()
                      if k != "metadata.webp_ulang_selesai"} for s in SUMBER]}
    pipeline = [{"$match": query}, {"$group": {
        "_id": {"$ifNull": ["$metadata.webp_progres.status", {
            "$cond": [{"$eq": ["$metadata.webp_ulang_selesai", True]},
                      "plateau_lama", "belum_diperiksa"]}]},
        "jumlah_blob": {"$sum": 1}, "bita": {"$sum": "$length"},
    }}]
    gridfs = await db["fs.files"].aggregate(pipeline, maxTimeMS=5000).to_list(20)
    inline = await db.foto_kompresi_status.aggregate([
        {"$group": {"_id": "$status", "jumlah_hash": {"$sum": 1}}}
    ], maxTimeMS=5000).to_list(20)
    cursor = await db.app_runtime.find_one({"_id": "foto_inline_cursor_v1"}) or {}
    return {
        "aktif": AKTIF, "ambang_persen": AMBANG_HEMAT_PERSEN,
        "gridfs": [{"status": g.pop("_id"), **g} for g in gridfs],
        "inline_teramati": [{"status": g.pop("_id"), **g} for g in inline],
        "sapuan_inline_terakhir": cursor.get("updated_at"),
        "semua_selesai": None,
        "catatan": "Statistik blob/hash teramati, bukan bukti seluruh foto hidup sudah selesai. "
                   "Perlu periksa bukan plateau; foto baru masuk sapuan berikutnya.",
    }
