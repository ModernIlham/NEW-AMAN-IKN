"""
Shared utilities used across route modules.
Cache, audit logging, thumbnail generation, OTP, constants, limiter.
"""
import os
import io
import uuid
import base64
import logging
import secrets
import string
import asyncio
from datetime import datetime, timezone
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from typing import Optional, List
from pathlib import Path

from cachetools import TTLCache
from fastapi import HTTPException
from PIL import Image as PILImage
# Pertahanan decompression-bomb (global proses, semua titik dekode PIL): batasi
# total piksel yang boleh didekode ke ~50MP (default Pillow ~89MP). Pillow
# melempar DecompressionBombError pada >2× nilai ini → cegah alokasi RAM
# raksasa dari berkas kecil-terkompres (mis. unggah foto TTD tamu e-sign).
PILImage.MAX_IMAGE_PIXELS = 50_000_000
from slowapi import Limiter
from slowapi.util import get_remote_address
import tinify
import resend

from asset_fields import SCALAR_FIELD_NAMES
from db import db, fs_bucket
from gridfs_id_utils import coerce_gridfs_id

logger = logging.getLogger(__name__)


# --- Pengesahan lock guard ---
# Backend adalah sumber kebenaran: SEMUA jalur mutasi aset (create/PUT/PATCH/
# DELETE/batch/bulk-delete/import) wajib memanggil ini. Satu lookup kegiatan
# ber-indeks (inventory_activities.id) — murah dan konsisten.
SEALED_DETAIL = "Kegiatan sudah disahkan dan terkunci"


async def ensure_activity_not_sealed(activity_id):
    """Raise HTTP 423 (Locked) bila kegiatan sudah disahkan (status_pengesahan)."""
    if not activity_id:
        return
    sealed = await db.inventory_activities.find_one(
        {"id": activity_id, "status_pengesahan": "disahkan"}, {"_id": 0, "id": 1}
    )
    if sealed:
        raise HTTPException(status_code=423, detail=SEALED_DETAIL)


# --- Shared base64 / data-URL helpers ---
# Centralized here so all 6+ places that decode "data:image/...;base64,..."
# strings use identical logic (DRY). Previously each route had its own
# slightly-different implementation, leading to subtle bugs (e.g. one used
# `,` split, another `base64,`, another no header tolerance at all).

def decode_data_url(data_url: Optional[str]) -> bytes:
    """Decode a `data:<mime>;base64,...` string OR a raw base64 string into bytes.

    Returns b'' on any failure (never raises) so callers can use truthy checks
    without try/except boilerplate.
    """
    if not data_url or not isinstance(data_url, str):
        return b""
    try:
        if "base64," in data_url:
            _, encoded = data_url.split("base64,", 1)
        elif data_url.startswith("data:"):
            # data: prefix without 'base64,' marker — unsupported, treat as raw
            encoded = data_url
        else:
            encoded = data_url
        return base64.b64decode(encoded)
    except Exception as e:
        logger.debug(f"decode_data_url failed: {e}")
        return b""


# --- GridFS Photo Helpers ---
async def store_photo_to_gridfs(photo_base64: str) -> str:
    """Store a base64 photo in GridFS and return the GridFS ID as string.

    RAISES bila gagal (decode/tulis). Dulu fungsi ini mengembalikan "" secara
    diam-diam — pasca migrasi GridFS-only itu berarti byte foto HILANG PERMANEN
    sementara API melapor sukses (dan blob lama ikut terhapus). Semua pemanggil
    punya jalur rollback/penanganan error; kegagalan harus terdengar."""
    photo_bytes = decode_data_url(photo_base64)
    if not photo_bytes:
        raise ValueError("Foto tidak valid (bukan base64 gambar)")
    from bson import ObjectId
    file_id = ObjectId()
    grid_in = fs_bucket.open_upload_stream_with_id(
        file_id, filename=f"photo_{uuid.uuid4()}.jpg",
        metadata={"content_type": "image/jpeg", "size": len(photo_bytes)}
    )
    await grid_in.write(photo_bytes)
    await grid_in.close()
    return str(file_id)


async def get_photo_from_gridfs(gridfs_id: str) -> Optional[bytes]:
    """Retrieve a photo from GridFS by its ID string. Memakai `coerce_gridfs_id`
    (toleran) — selaras jalur unduh lain (regen cover thumbnail_index, migrasi,
    impor backup)."""
    try:
        grid_out = await fs_bucket.open_download_stream(coerce_gridfs_id(gridfs_id))
        return await grid_out.read()
    except Exception as e:
        logger.error(f"GridFS read error for {gridfs_id}: {e}")
        return None


async def delete_photo_from_gridfs(gridfs_id: str):
    """Delete a photo from GridFS."""
    try:
        from bson import ObjectId
        await fs_bucket.delete(ObjectId(gridfs_id))
    except Exception as e:
        logger.error(f"GridFS delete error for {gridfs_id}: {e}")


def generate_photo_thumbnail(photo_base64: str, size: int = 100, quality: int = 70) -> Optional[str]:
    """Generate a small thumbnail from a base64 photo."""
    return create_thumbnail(photo_base64, size=size, quality=quality)


# --- GridFS Document Helpers (for PDFs) ---
async def store_document_to_gridfs(doc_base64: str, filename: str = "document.pdf") -> str:
    """Store a base64 document (PDF) in GridFS and return the GridFS ID as string.

    Used by `inventory_activities` to keep the parent doc tiny — large PDFs
    inline easily blow past the 16MB BSON limit when 3-5 are attached.
    """
    doc_bytes = decode_data_url(doc_base64)
    if not doc_bytes:
        return ""
    try:
        from bson import ObjectId
        file_id = ObjectId()
        grid_in = fs_bucket.open_upload_stream_with_id(
            file_id, filename=filename or f"document_{uuid.uuid4()}.pdf",
            metadata={"content_type": "application/pdf", "size": len(doc_bytes)},
        )
        await grid_in.write(doc_bytes)
        await grid_in.close()
        return str(file_id)
    except Exception as e:
        logger.error(f"GridFS document store error: {e}")
        return ""


async def get_document_from_gridfs(gridfs_id: str) -> Optional[bytes]:
    """Retrieve a document from GridFS by its ID string."""
    try:
        from bson import ObjectId
        grid_out = await fs_bucket.open_download_stream(ObjectId(gridfs_id))
        return await grid_out.read()
    except Exception as e:
        logger.error(f"GridFS document read error for {gridfs_id}: {e}")
        return None


async def delete_document_from_gridfs(gridfs_id: str):
    """Delete a document from GridFS."""
    try:
        from bson import ObjectId
        await fs_bucket.delete(ObjectId(gridfs_id))
    except Exception as e:
        logger.error(f"GridFS document delete error for {gridfs_id}: {e}")


# --- Rate Limiter ---
limiter = Limiter(key_func=get_remote_address)

# --- In-Memory Cache ---
_cache_categories = TTLCache(maxsize=1, ttl=300)
_cache_filter_opts = TTLCache(maxsize=50, ttl=180)
_cache_stats = TTLCache(maxsize=100, ttl=60)
_cache_analytics = TTLCache(maxsize=50, ttl=120)

def invalidate_category_cache():
    _cache_categories.clear()

def invalidate_asset_cache():
    _cache_filter_opts.clear()
    _cache_stats.clear()
    _cache_analytics.clear()

# --- Tinify Config ---
TINIFY_API_KEY = os.environ.get("TINIFY_API_KEY", "")
TINIFY_AVAILABLE = False
if TINIFY_API_KEY:
    tinify.key = TINIFY_API_KEY
    TINIFY_AVAILABLE = True

# --- Resend Config ---
def _bersihkan_env(nilai) -> str:
    """Buang spasi/CR-LF & tanda kutip yang kerap ikut tersalin ke .env —
    kunci yang "terlihat benar" dengan \r di ujung (file diedit di Windows)
    atau terbungkus kutip ditolak Resend sebagai 401 invalid API key."""
    return str(nilai or "").strip().strip('"').strip("'").strip()


RESEND_API_KEY = _bersihkan_env(os.environ.get("RESEND_API_KEY", ""))
SENDER_EMAIL = _bersihkan_env(os.environ.get("SENDER_EMAIL", "")) or "onboarding@resend.dev"
if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY
    # Jejak diagnosa di log server (kunci di-masker): admin bisa memastikan
    # kunci yang TERBACA aplikasi sama dengan yang dimaksud.
    logger.info(
        f"Resend siap: kunci {RESEND_API_KEY[:5]}… (panjang {len(RESEND_API_KEY)}), "
        f"pengirim {SENDER_EMAIL}")

# --- OTP Store (MongoDB-backed for multi-replica support) ---

def generate_otp(length=6):
    # secrets (CSPRNG), bukan random — OTP dipakai utk verifikasi/reset akun.
    return ''.join(secrets.choice(string.digits) for _ in range(length))

async def store_otp(email, otp, user_data):
    """Store OTP in MongoDB with TTL expiry"""
    await db.otp_store.update_one(
        {"email": email},
        {"$set": {
            "email": email,
            "otp": otp,
            "user_data": user_data,
            "attempts": 0,  # OTP baru → reset penghitung gagal (anti brute-force)
            "expires_at": datetime.now(timezone.utc).timestamp() + 600,
            "created_at": datetime.now(timezone.utc)
        }},
        upsert=True
    )

async def get_otp(email):
    """Retrieve OTP from MongoDB"""
    doc = await db.otp_store.find_one({"email": email}, {"_id": 0})
    if not doc:
        return None
    if datetime.now(timezone.utc).timestamp() > doc.get("expires_at", 0):
        await db.otp_store.delete_one({"email": email})
        return None
    return doc

async def delete_otp(email):
    """Remove OTP from MongoDB"""
    await db.otp_store.delete_one({"email": email})


async def catat_gagal_otp(email, maks_percobaan=5) -> bool:
    """Catat 1 percobaan OTP GAGAL (atomik `$inc`). Bila mencapai batas, OTP
    DIHAPUS (invalidasi) supaya brute-force terkunci — penyerang harus meminta
    OTP baru, sehingga ruang tebak tetap kecil meski rate-limit hanya per-IP.
    Kembalikan True bila OTP baru saja dinonaktifkan (terkunci)."""
    doc = await db.otp_store.find_one_and_update(
        {"email": email},
        {"$inc": {"attempts": 1}},
        projection={"_id": 0, "attempts": 1},
        return_document=ReturnDocument.AFTER,
    )
    if doc and int(doc.get("attempts") or 0) >= maks_percobaan:
        await db.otp_store.delete_one({"email": email})
        return True
    return False

# --- Row Lock Store (Persistent via MongoDB, 5min TTL with heartbeat) ---
# Replaced in-memory TTLCache with MongoDB collection `row_locks`
# MongoDB TTL index auto-expires documents after `expires_at` passes

# --- Idempotency Key Store (MongoDB-backed, 24h TTL) ---
# Used to prevent duplicate writes when clients retry after network failures.
# TTL index on `created_at` (expireAfterSeconds=86400) is created in indexes.py.

async def get_idempotent_response(key: str) -> Optional[dict]:
    """Return cached response for a given idempotency key, or None."""
    if not key:
        return None
    try:
        doc = await db.idempotency_keys.find_one({"key": key}, {"_id": 0, "response": 1, "status_code": 1})
        return doc
    except Exception:
        return None

async def store_idempotent_response(key: str, response: dict, status_code: int = 200):
    """Cache a successful response keyed by the client-provided idempotency key."""
    if not key:
        return
    try:
        await db.idempotency_keys.update_one(
            {"key": key},
            {"$set": {
                "key": key,
                "response": response,
                "status_code": status_code,
                "created_at": datetime.now(timezone.utc),
            }},
            upsert=True,
        )
    except Exception as e:
        logger.warning(f"Failed to cache idempotent response: {e}")


async def reserve_idempotency_key(key: str, stale_seconds: int = 30) -> str:
    """Atomically claim an idempotency key BEFORE doing the work, so two
    concurrent requests with the same key can't both execute.

    Returns "new" (proceed), "done" (a completed response is cached -> replay),
    or "pending" (another request is in flight -> the caller should 409).
    Fail-open: any infra error returns "new" so idempotency never blocks a
    legitimate request.
    """
    if not key:
        return "new"
    now = datetime.now(timezone.utc)
    try:
        await db.idempotency_keys.insert_one({"key": key, "created_at": now})
        return "new"
    except DuplicateKeyError:
        doc = await db.idempotency_keys.find_one({"key": key}, {"_id": 0, "response": 1, "created_at": 1})
        if doc and doc.get("response") is not None:
            return "done"
        ca = doc.get("created_at") if doc else None
        if ca is not None:
            if ca.tzinfo is None:
                ca = ca.replace(tzinfo=timezone.utc)
            if (now - ca).total_seconds() > stale_seconds:
                # Previous holder likely failed/abandoned -> take the slot over.
                await db.idempotency_keys.update_one({"key": key}, {"$set": {"created_at": now}})
                return "new"
        return "pending"
    except Exception as e:
        logger.warning(f"reserve_idempotency_key failed open: {e}")
        return "new"



async def send_otp_email(email: str, otp: str, name: str = ""):
    """Kirim OTP via Resend. Kembalikan (ok, alasan) — alasan berbahasa
    Indonesia yang ACTIONABLE bila gagal (kunci API kosong / domain pengirim
    belum terverifikasi / galat lain), bukan False bisu: pendaftar berulang
    kali "coba ulang" tanpa tahu emailnya memang mustahil terkirim.
    Galat sementara (jaringan/5xx) dicoba ulang otomatis SEKALI."""
    if not RESEND_API_KEY:
        logger.warning("Resend API key not configured, OTP email not sent")
        return False, ("Layanan email belum dikonfigurasi di server "
                       "(RESEND_API_KEY kosong) — hubungi administrator")
    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #1e40af; margin-bottom: 20px;">Verifikasi Email Anda</h2>
        <p style="color: #374151; font-size: 16px;">Halo{' ' + name if name else ''},</p>
        <p style="color: #374151; font-size: 16px;">Gunakan kode OTP berikut untuk menyelesaikan registrasi akun Anda:</p>
        <div style="background: #f3f4f6; padding: 20px; text-align: center; border-radius: 8px; margin: 20px 0;">
            <span style="font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #1e40af;">{otp}</span>
        </div>
        <p style="color: #6b7280; font-size: 14px;">Kode ini berlaku selama 10 menit.</p>
        <p style="color: #6b7280; font-size: 14px;">Jika Anda tidak meminta kode ini, abaikan email ini.</p>
        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;">
        <p style="color: #9ca3af; font-size: 12px;">Sistem Inventaris Aset</p>
    </div>
    """
    # Subjek generik — JANGAN taruh OTP di subjek (tampil di pratinjau notifikasi
    # HP/lockscreen). OTP hanya di badan email.
    params = {"from": SENDER_EMAIL, "to": [email], "subject": "Kode Verifikasi OTP — Sistem Inventaris Aset", "html": html_content}
    galat = ""
    for percobaan in (1, 2):
        try:
            result = await asyncio.to_thread(resend.Emails.send, params)
            logger.info(f"OTP email sent to {email}: {result.get('id', 'unknown')}")
            return True, ""
        except Exception as e:
            galat = str(e)
            logger.error(f"Failed to send OTP email to {email} (percobaan {percobaan}): {galat}")
            g = galat.lower()
            # Galat konfigurasi PASTI — jangan buang waktu coba ulang.
            if ("testing email" in g or "verify a domain" in g
                    or "not verified" in g or "own email address" in g):
                return False, (
                    "Domain PENGIRIM email belum terverifikasi — SENDER_EMAIL "
                    f"saat ini '{SENDER_EMAIL}' (alamat uji Resend hanya bisa "
                    "mengirim ke email pemilik akun Resend). Administrator perlu "
                    "menyetel domain terverifikasi di pengaturan server")
            if "api key" in g or "unauthorized" in g or "401" in g:
                return False, ("Kunci API layanan email tidak valid — "
                               "administrator perlu memeriksa RESEND_API_KEY di server")
            await asyncio.sleep(1.5)
    return False, (f"Gagal mengirim email ({galat[:120]}) — coba beberapa saat "
                   "lagi atau hubungi administrator")

async def send_esign_email(email: str, nama: str, judul: str, link: str) -> bool:
    """Kirim link tanda tangan elektronik ke penanda tangan (best-effort —
    gagal kirim TIDAK menggagalkan pembuatan permintaan; link tetap bisa
    dibagikan manual/WA)."""
    if not RESEND_API_KEY or not str(email or "").strip():
        return False
    from xml.sax.saxutils import escape as _e
    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 520px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #1e40af; margin-bottom: 16px;">Permintaan Tanda Tangan Elektronik</h2>
        <p style="color: #374151; font-size: 15px;">Yth. <b>{_e(str(nama or ''))}</b>,</p>
        <p style="color: #374151; font-size: 15px;">Mohon berkenan menandatangani secara elektronik dokumen:</p>
        <div style="background: #f3f4f6; padding: 14px 18px; border-radius: 8px; margin: 14px 0;">
            <b style="color: #111827; font-size: 15px;">{_e(str(judul or ''))}</b>
        </div>
        <p style="margin: 22px 0; text-align: center;">
            <a href="{_e(str(link))}" style="background: #1d4ed8; color: #ffffff; text-decoration: none;
               padding: 12px 26px; border-radius: 8px; font-size: 15px; font-weight: bold;">
               Tanda Tangani Sekarang</a>
        </p>
        <p style="color: #6b7280; font-size: 13px;">Tautan bersifat pribadi &amp; sekali pakai, berlaku 14 hari.
        Bila tombol tidak berfungsi, salin tautan berikut ke peramban:<br/>
        <span style="word-break: break-all; color: #1d4ed8;">{_e(str(link))}</span></p>
        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 18px 0;">
        <p style="color: #9ca3af; font-size: 12px;">AMAN — Aplikasi Manajemen Aset &amp; BMN</p>
    </div>
    """
    params = {"from": SENDER_EMAIL, "to": [str(email).strip()],
              "subject": f"Permintaan Tanda Tangan Elektronik — {str(judul or '')[:80]}",
              "html": html_content}
    try:
        result = await asyncio.to_thread(resend.Emails.send, params)
        logger.info(f"E-sign email sent to {email}: {result.get('id', 'unknown')}")
        return True
    except Exception as e:
        logger.error(f"Failed to send e-sign email to {email}: {e}")
        return False


# --- Audit Logging ---
# Semua field skalar registry (kini termasuk asset_code & eselon1/eselon2 yang
# dulu terlewat dari audit) + stiker_photo_index yang dilacak sebagai nilai.
TRACKED_FIELDS = [*SCALAR_FIELD_NAMES, "stiker_photo_index"]
TRACKED_COUNT_FIELDS = ["photos", "document_checklist"]

async def log_audit(action: str, activity_id: str, asset_id: str = "", asset_code: str = "", asset_name: str = "", username: str = "system", changes: list = None, detail: str = "", nup: str = "", kode_satker: str = ""):
    # kode_satker (opsional): log SISTEM tanpa activity_id (mis. kejadian
    # kartu pegawai) tetap bisa dibatasi & dilihat per satker di halaman
    # audit — tanpa ini log ber-activity_id "" tak terlihat siapa pun.
    entry = {
        "id": str(uuid.uuid4()), "action": action, "activity_id": activity_id,
        "asset_id": asset_id, "asset_code": asset_code, "nup": nup,
        "asset_name": asset_name, "username": username,
        "changes": changes or [], "detail": detail, "kode_satker": kode_satker,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    try:
        await db.audit_logs.insert_one(entry)
    except Exception as e:
        logger.error(f"Failed to write audit log: {e}")

def compute_changes(old_doc: dict, new_data: dict) -> list:
    changes = []
    for field in TRACKED_FIELDS:
        old_val = str(old_doc.get(field, "") or "")
        new_val = str(new_data.get(field, "") or "")
        if old_val != new_val:
            changes.append({"field": field, "from": old_val, "to": new_val})
    for field in TRACKED_COUNT_FIELDS:
        old_list = old_doc.get(field, []) or []
        new_list = new_data.get(field, []) or []
        old_count = len(old_list) if isinstance(old_list, list) else 0
        new_count = len(new_list) if isinstance(new_list, list) else 0
        if field == "photos":
            # GridFS-first: dokumen bersih menyimpan photos=[] — jumlah nyata
            # ada di photo_gridfs_ids (payload klien tetap kirim array foto).
            old_g = old_doc.get("photo_gridfs_ids") or []
            new_g = new_data.get("photo_gridfs_ids") or []
            old_count = len([x for x in old_g if x]) or old_count
            new_count = len([x for x in new_g if x]) or new_count
            if old_count != new_count:
                changes.append({"field": "photos", "from": f"{old_count} foto", "to": f"{new_count} foto"})
        elif field == "document_checklist":
            # Track completion changes (checking/unchecking a document) even when
            # the number of checklist items is unchanged.
            old_checked = sum(1 for d in old_list if isinstance(d, dict) and d.get("checked", False))
            new_checked = sum(1 for d in new_list if isinstance(d, dict) and d.get("checked", False))
            if old_checked != new_checked:
                changes.append({"field": "document_checklist", "from": f"{old_checked} dok selesai", "to": f"{new_checked} dok selesai"})
    return changes

# --- Thumbnail Generation ---
def _prepare_image(image_data: Optional[str]):
    """Decode base64 image data and return PIL Image in RGB mode."""
    image_bytes = decode_data_url(image_data)
    if not image_bytes:
        return None
    img = PILImage.open(io.BytesIO(image_bytes))
    if img.mode in ('RGBA', 'P', 'LA'):
        background = PILImage.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
        img = background
    elif img.mode != 'RGB':
        img = img.convert('RGB')
    return img

def create_thumbnail(image_data: Optional[str], size: int = 100, quality: int = 70) -> Optional[str]:
    try:
        img = _prepare_image(image_data)
        if not img:
            return None
        img.thumbnail((size, size))
        buffer = io.BytesIO()
        # optimize: tabel Huffman optimal (hemat 2-10% byte tanpa penurunan
        # kualitas); progressive: tampil bertahap di koneksi lambat.
        img.save(buffer, format="JPEG", quality=quality, optimize=True, progressive=True)
        buffer.seek(0)
        thumb_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return f"data:image/jpeg;base64,{thumb_base64}"
    except Exception as e:
        logger.error(f"Thumbnail generation error: {e}")
        return None

def create_gallery_thumbnail(image_data: Optional[str]) -> Optional[str]:
    """Generate a 256x256 thumbnail for gallery view."""
    return create_thumbnail(image_data, size=256, quality=65)

# --- Inventory Constants ---
VALID_INVENTORY_STATUSES = ["Belum Diinventarisasi", "Ditemukan", "Tidak Ditemukan", "Berlebih", "Sengketa"]
VALID_CONDITIONS = ["Baik", "Rusak Ringan", "Rusak Berat"]
VALID_STATUSES = ["Aktif", "Idle", "Maintenance", "Nonaktif"]
VALID_STIKER_STATUSES = ["Belum Terpasang", "Sudah Terpasang"]
VALID_STIKER_SIZES = ["Kecil", "Sedang", "Besar"]
VALID_KLASIFIKASI = ["Kesalahan Pencatatan", "Tidak Ditemukan Lainnya"]
VALID_SUB_KLASIFIKASI_PENCATATAN = [
    "Salah Kode Barang/NUP",
    "Salah Pembukuan (SIMAK-BMN Error)",
    "Perubahan Kondisi Belum Dicatat",
    "Aset Sudah Dihibahkan/Dipindahtangankan",
    "Aset Sudah Dihapuskan",
    "Pencatatan Ganda (Double Counting)",
    "Pemecahan/Penggabungan Belum Dicatat",
    "Transfer Masuk/Keluar Belum Diproses"
]
VALID_SUB_KLASIFIKASI_LAINNYA = [
    "Hilang / Dicuri",
    "Rusak Total / Hancur",
    "Bencana Alam",
    "Lainnya"
]
VALID_SUB_KLASIFIKASI_ALL = VALID_SUB_KLASIFIKASI_PENCATATAN + VALID_SUB_KLASIFIKASI_LAINNYA


# ── Penanda tangan dokumen resmi (temuan review #26 — satu resolver lintas modul) ──

async def status_kepegawaian_by_nip(nip) -> str:
    """Kode status kepegawaian ("pns"/"non_asn"/...) seseorang per NIP —
    registry pejabat dulu, lalu Master Pegawai; "" bila tak ditemukan.
    Dipakai aturan privasi blok TTD: Non-ASN tidak dicetak NIP/NIK-nya."""
    n = str(nip or "").strip()
    if not n or set(n) <= set(".-_ "):
        return ""
    for koleksi in (db.pejabat, db.pegawai):
        doc = await koleksi.find_one(
            {"nip": n}, {"_id": 0, "status_kepegawaian": 1})
        if doc and str(doc.get("status_kepegawaian") or "").strip():
            return str(doc["status_kepegawaian"]).strip()
    return ""


def _q_pejabat_satker(kode_satker: str = "") -> dict:
    """Query registry `pejabat` ter-scope satker untuk resolver penanda tangan.

    Isolasi M-SCOPE lanjutan (langkah 2 setelah pejabat membawa kode_satker):
    dokumen resmi satker ini hanya boleh ditandatangani pejabat satker ini
    (atau pejabat era-lama tanpa kode). `kode_satker` kosong → query kosong =
    SEMUA pejabat (perilaku lama, aman-mundur untuk super-admin/lintas-satker
    & deployment satker-tunggal). MURNI."""
    kode = str(kode_satker or "").strip()
    return {"kode_satker": {"$in": [kode, "", None]}} if kode else {}


async def resolve_penandatangan_kpb(settings, per_iso=None, kode_satker=""):
    """Penanda tangan **Kuasa Pengguna Barang** untuk dokumen resmi.

    SATU resolver untuk semua modul (dulu 5 modul membaca setelan kasatker
    langsung sehingga KPB dari registry pejabat tidak muncul): KPB aktif dari
    registry `pejabat` pada tanggal dokumen (`per_iso`), fallback setelan
    laporan (kasatker). Kembalikan {nama, nip, jabatan, status_kepegawaian,
    sumber}.

    `kode_satker` (opsional) membatasi kandidat KPB ke satker penerbit dokumen
    (+ pejabat era-lama tanpa kode) agar KPB satker lain tak ikut terpilih di
    DB multi-satker; kosong = semua pejabat (perilaku lama).
    """
    from pejabat_utils import penandatangan_kpb
    # Default tanggal = hari ini (temuan #41: tanpa tanggal, rentang berlaku
    # SK pejabat tidak dicek sehingga pejabat kedaluwarsa bisa terpilih).
    per_iso = per_iso or datetime.now(timezone.utc).date().isoformat()
    pejabat_list = await db.pejabat.find(
        _q_pejabat_satker(kode_satker), {"_id": 0}).to_list(2000)
    kpb = penandatangan_kpb(settings or {}, pejabat_list, per_iso)
    # Fallback setelan tidak membawa status — lengkapi via lookup NIP agar
    # aturan Non-ASN tetap berlaku bila orangnya terdaftar di master.
    if not kpb.get("status_kepegawaian"):
        kpb["status_kepegawaian"] = await status_kepegawaian_by_nip(kpb.get("nip"))
    return kpb


async def resolve_pejabat_peran(peran, per_iso=None, kode_satker=""):
    """Pejabat aktif pemegang `peran` (mis. 'pengurus_barang') pada tanggal
    `per_iso` (default hari ini) dari registry pejabat — None bila belum ada.

    `kode_satker` (opsional) membatasi kandidat ke satker penerbit dokumen
    (+ era-lama tanpa kode); kosong = semua pejabat (perilaku lama)."""
    from pejabat_utils import pejabat_aktif_untuk_peran
    per_iso = per_iso or datetime.now(timezone.utc).date().isoformat()
    pejabat_list = await db.pejabat.find(
        _q_pejabat_satker(kode_satker), {"_id": 0}).to_list(2000)
    return pejabat_aktif_untuk_peran(pejabat_list, peran, per_iso)


# ============================================================================
# ISOLASI DATA PER-SATKER (M-SCOPE, multi-satker DB bersama)
# ============================================================================

def kode_satker_user(user) -> str:
    """Kode satker yang mengikat user; '' = lintas-satker (super-admin/pusat)."""
    return str((user or {}).get("kode_satker") or "").strip()


async def id_kegiatan_satker(kode: str) -> list:
    """Seluruh id kegiatan milik satu satker — dipakai memfilter koleksi
    turunan yang berelasi lewat activity_id (aset dkk.)."""
    return [a["id"] async for a in db.inventory_activities.find(
        {"kode_satker": kode}, {"_id": 0, "id": 1})]


async def scope_query_kegiatan(user, query=None) -> dict:
    """Sisipkan filter kode_satker ke query kegiatan bila user terikat satker."""
    q = dict(query or {})
    kode = kode_satker_user(user)
    if kode:
        q["kode_satker"] = kode
    return q


async def scope_query_aset(user, query=None) -> dict:
    """Sisipkan filter activity_id ∈ kegiatan-satker ke query aset bila user
    terikat satker. Bila query sudah menunjuk activity_id tertentu, cukup
    biarkan — pemeriksaan kepemilikan kegiatan dilakukan guard terpisah."""
    q = dict(query or {})
    kode = kode_satker_user(user)
    if not kode or "activity_id" in q:
        return q
    q["activity_id"] = {"$in": await id_kegiatan_satker(kode)}
    return q


async def pastikan_akses_kegiatan(user, activity) -> None:
    """403 bila user terikat satker lain dari kegiatan ini. Kegiatan tanpa
    kode_satker (data era lama) dianggap terbuka."""
    from fastapi import HTTPException
    kode = kode_satker_user(user)
    milik = str((activity or {}).get("kode_satker") or "").strip()
    if kode and milik and milik != kode:
        raise HTTPException(
            status_code=403,
            detail=f"Data milik satker {milik} — akun Anda terikat satker {kode}")


async def pastikan_akses_kegiatan_id(user, activity_id: str) -> None:
    """Varian by-id: no-op untuk user lintas-satker / id kosong."""
    if not kode_satker_user(user) or not str(activity_id or "").strip():
        return
    act = await db.inventory_activities.find_one(
        {"id": activity_id}, {"_id": 0, "kode_satker": 1})
    if act:
        await pastikan_akses_kegiatan(user, act)


async def pastikan_akses_aset(user, asset) -> None:
    """Guard aset lewat kegiatan induknya (asset.activity_id)."""
    if not kode_satker_user(user):
        return
    await pastikan_akses_kegiatan_id(user, (asset or {}).get("activity_id"))


def scope_query_field_satker(user, query=None, field="kode_satker") -> dict:
    """Filter koleksi yang MEMBAWA kode_satker langsung di dokumennya
    (persediaan, PSP, idle, …): user terikat melihat dokumen satkernya +
    dokumen ERA LAMA tanpa kode (kosong/None/tak ada — $in dengan None juga
    cocok untuk field yang hilang); user lintas-satker melihat semua."""
    q = dict(query or {})
    kode = kode_satker_user(user)
    if kode:
        q[field] = {"$in": [kode, "", None]}
    return q


async def pastikan_akses_dok_satker(user, doc, field="kode_satker") -> None:
    """403 bila dokumen terikat satker LAIN (field terisi & berbeda).
    Dokumen era lama tanpa kode tetap terbuka — konsisten dengan kegiatan."""
    from fastapi import HTTPException
    kode = kode_satker_user(user)
    milik = str((doc or {}).get(field) or "").strip()
    if kode and milik and milik != kode:
        raise HTTPException(
            status_code=403,
            detail=f"Data milik satker {milik} — akun Anda terikat satker {kode}")


async def pengaturan_kop(activity=None, kode_satker=""):
    """Setelan kop EFEKTIF untuk laporan sebuah kegiatan: report_settings
    global di-overlay kop MASTER SATKER (field non-kosong menimpa) berdasar
    `kode_satker` kegiatan. Tanpa kode satker → setelan global apa adanya."""
    from satker_utils import gabung_kop
    settings = await db.report_settings.find_one({"type": "global"}, {"_id": 0}) or {}
    kode = str(kode_satker or (activity or {}).get("kode_satker") or "").strip()
    if not kode:
        return settings
    satker = await db.satker.find_one({"kode_satker": kode}, {"_id": 0})
    return gabung_kop(settings, satker) if satker else settings


async def ambang_kapitalisasi() -> dict:
    """Ambang kapitalisasi PMK 181 EFEKTIF: default digabung override setelan
    admin (dokumen `report_settings {type: "kapitalisasi"}`, field `ambang`).
    Dipakai seluruh laporan pembukuan (DBKP/LBKP/Posisi) agar satker dengan
    kebijakan ambang berbeda tak perlu ubah kode."""
    from pembukuan_utils import gabung_ambang
    doc = await db.report_settings.find_one(
        {"type": "kapitalisasi"}, {"_id": 0, "ambang": 1}) or {}
    return gabung_ambang(doc.get("ambang"))


async def ambil_ttd_img(file_id):
    """Bytes gambar TTD digital (PNG transparan) dari GridFS — None bila
    kosong/gagal. Dipakai menyematkan tanda tangan ke blok TTD PDF."""
    fid = str(file_id or "").strip()
    if not fid:
        return None
    try:
        return await get_document_from_gridfs(fid)
    except Exception:
        return None


async def blok_ttd_kpb(settings, per_iso=None, kode_satker=""):
    """Entri `_signature_block` "Kuasa Pengguna Barang" (dengan baris tempat/
    tanggal titik-titik) — nama/NIP dari registry pejabat, fallback setelan.
    Penandatangan Non-ASN: baris NIP/NIK TIDAK dicetak (privasi).
    `kode_satker` membatasi KPB ke satker penerbit (kosong = semua, lama)."""
    from pegawai_utils import baris_identitas_ttd
    kpb = await resolve_penandatangan_kpb(settings, per_iso, kode_satker)
    return {'pre': ['.................., .......................'],
            'header': 'Kuasa Pengguna Barang,',
            'nama': kpb["nama"],
            'ttd_img': await ambil_ttd_img(kpb.get("ttd_file_id")),
            'after': baris_identitas_ttd(
                kpb["nip"], "NIP. ....................",
                kpb.get("status_kepegawaian"))}


def nama_file_disposition(filename, fallback="dokumen"):
    """Nama file AMAN untuk header Content-Disposition (cegah header/response
    splitting): buang CR/LF/kutip/`;`/pemisah path, batasi panjang. MURNI."""
    import re as _re
    nama = _re.sub(r'[\r\n"\\/;]+', "_", str(filename or "").strip())
    nama = nama[:120].strip() or fallback
    return nama


# Magic byte per ekstensi gambar (deteksi spoofing tipe upload).
_MAGIC_GAMBAR = {
    ".jpg": (b"\xff\xd8\xff",), ".jpeg": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".webp": (b"RIFF",),   # + "WEBP" di offset 8 (dicek terpisah)
    ".gif": (b"GIF87a", b"GIF89a"),
}


def cek_magic_gambar(data: bytes, ext: str) -> bool:
    """True bila `data` cocok magic byte untuk ekstensi gambar `ext`
    (atau ext bukan gambar yang dikenal → dianggap lolos, dicek terpisah).
    MURNI."""
    sigs = _MAGIC_GAMBAR.get(str(ext or "").lower())
    if not sigs:
        return True
    ok = any(data[:len(s)] == s for s in sigs)
    if ext.lower() == ".webp":
        return ok and data[8:12] == b"WEBP"
    return ok


async def catat_mutasi_bmn(entri: dict):
    """Tulis satu entri jurnal `mutasi_bmn` (Buku Barang, G7) — BEST-EFFORT:
    entri tak valid / gagal tulis hanya di-log, TIDAK menggagalkan transaksi
    modul pemanggil (jurnal = pencatatan turunan, bukan gerbang)."""
    import uuid as _uuid
    from datetime import datetime as _dt, timezone as _tz
    try:
        from mutasi_bmn_utils import validate_entri_mutasi
        errs = validate_entri_mutasi(entri)
        if errs:
            logger.warning("catat_mutasi_bmn dilewati: %s", "; ".join(errs))
            return False
        await db.mutasi_bmn.insert_one({
            **entri, "id": str(_uuid.uuid4()),
            "created_at": _dt.now(_tz.utc).isoformat()})
        return True
    except Exception as e:  # jangan pernah mematahkan alur pemanggil
        logger.warning("catat_mutasi_bmn gagal: %s", e)
        return False


async def proses_keluar_aktif(asset_ids):
    """Peta asset_id → daftar proses KELUAR aktif lintas register (audit G5
    #11 — penanda in-flight): usulan penghapusan (diusulkan/diproses), usulan
    pemindahtanganan (belum selesai/ditolak), dan BA pemusnahan. Dipakai cek
    silang non-blocking saat membuat usulan baru agar satu aset tidak duduk
    di dua jalur keluar sekaligus tanpa disadari."""
    ids = [str(a) for a in (asset_ids or []) if str(a or "").strip()]
    if not ids:
        return {}
    peta = {}

    def _tambah(aid, label):
        peta.setdefault(aid, [])
        if label not in peta[aid]:
            peta[aid].append(label)

    async for u in db.usulan_penghapusan.find(
            {"asset_id": {"$in": ids}, "status": {"$in": ["diusulkan", "diproses"]}},
            {"_id": 0, "asset_id": 1}):
        _tambah(u["asset_id"], "usulan penghapusan")
    async for r in db.pemindahtanganan.find(
            {"aset.asset_id": {"$in": ids},
             "status": {"$nin": ["selesai", "ditolak", "batal"]}},
            {"_id": 0, "aset.asset_id": 1}):
        for a in r.get("aset") or []:
            if a.get("asset_id") in ids:
                _tambah(a["asset_id"], "usulan pemindahtanganan")
    async for r in db.pemusnahan.find(
            {"aset.asset_id": {"$in": ids}}, {"_id": 0, "aset.asset_id": 1}):
        for a in r.get("aset") or []:
            if a.get("asset_id") in ids:
                _tambah(a["asset_id"], "BA pemusnahan")
    return peta


async def blok_ttd_kpb_titik(settings, per_iso=None, kode_satker=""):
    """Entri `_signature_block` "Mengetahui / Kuasa Pengguna Barang" dengan
    fallback garis-titik (pola BA/daftar) — nama/NIP dari registry pejabat.
    Penandatangan Non-ASN: baris NIP/NIK TIDAK dicetak (privasi).
    `kode_satker` membatasi KPB ke satker penerbit (kosong = semua, lama)."""
    from pegawai_utils import baris_identitas_ttd
    kpb = await resolve_penandatangan_kpb(settings, per_iso, kode_satker)
    return {'pre': [''], 'header': 'Mengetahui,', 'role': 'Kuasa Pengguna Barang,',
            'nama': kpb["nama"] if kpb["nama"] != "-" else '...........................',
            'ttd_img': await ambil_ttd_img(kpb.get("ttd_file_id")),
            'after': baris_identitas_ttd(
                kpb["nip"], "NIP. ....................",
                kpb.get("status_kepegawaian"))}


async def enforce_pegawai_terdaftar(pengguna_nip):
    """Evaluasi #4 / temuan #29 (OPT-IN, satu penegakan lintas jalur tulis):
    bila setelan `wajib_pegawai_terdaftar` ON dan NIP pengguna diisi tapi
    TIDAK terdaftar di Master Pegawai → HTTPException 400. Default OFF
    (perilaku lama; entri lapangan/offline & data lama tetap jalan)."""
    nip = str(pengguna_nip or "").strip()
    if not nip:
        return
    settings = await db.report_settings.find_one(
        {"type": "global"}, {"_id": 0, "wajib_pegawai_terdaftar": 1}) or {}
    if not settings.get("wajib_pegawai_terdaftar"):
        return
    if not await db.pegawai.find_one({"nip": nip}, {"_id": 1}):
        raise HTTPException(
            status_code=400,
            detail=f"NIP/NIK pengguna '{nip}' belum terdaftar di Master Pegawai. "
                   f"Daftarkan pegawai tersebut, atau nonaktifkan setelan "
                   f"'Wajib Pegawai Terdaftar'.")


async def filter_aset_perhitungan(query=None) -> dict:
    """Gerbang W9 untuk endpoint PERHITUNGAN lintas modul: batasi aset pada
    kegiatan inventarisasi yang LAYAK HITUNG (disahkan / tanggal selesai
    sudah lewat — fase selesai atau belum lengkap) dan singkirkan aset
    berkategori dummy. Kegiatan belum dimulai / berlangsung / menunggu
    validasi = lingkup modul Inventarisasi saja.

    Dipanggil SETELAH scoping satker: bila query sudah membawa
    `activity_id` ($in satker atau satu id), hasilnya di-IRIS dengan
    daftar kegiatan layak. Tampilan di dalam modul Inventarisasi TIDAK
    memakai filter ini."""
    from datetime import date as _date

    from report_filters import layak_hitung_kegiatan, tanpa_dummy_filter
    today = _date.today().isoformat()
    layak = set()
    async for a in db.inventory_activities.find(
            {}, {"_id": 0, "id": 1, "status_pengesahan": 1,
                 "tanggal_selesai": 1}):
        if layak_hitung_kegiatan(a, today):
            layak.add(a["id"])
    q = tanpa_dummy_filter(query)
    ada = q.get("activity_id")
    if isinstance(ada, dict) and "$in" in ada:
        q["activity_id"] = {"$in": [i for i in ada["$in"] if i in layak]}
    elif isinstance(ada, str):
        if ada not in layak:
            q["activity_id"] = {"$in": []}
    else:
        q["activity_id"] = {"$in": sorted(layak)}
    return q
