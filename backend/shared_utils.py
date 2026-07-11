"""
Shared utilities used across route modules.
Cache, audit logging, thumbnail generation, OTP, constants, limiter.
"""
import os
import io
import uuid
import base64
import logging
import random
import string
import asyncio
from datetime import datetime, timezone
from pymongo.errors import DuplicateKeyError
from typing import Optional, List
from pathlib import Path

from cachetools import TTLCache
from fastapi import HTTPException
from PIL import Image as PILImage
from slowapi import Limiter
from slowapi.util import get_remote_address
import tinify
import resend

from db import db, fs_bucket

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
    """Store a base64 photo in GridFS and return the GridFS ID as string."""
    photo_bytes = decode_data_url(photo_base64)
    if not photo_bytes:
        return ""
    try:
        from bson import ObjectId
        file_id = ObjectId()
        grid_in = fs_bucket.open_upload_stream_with_id(
            file_id, filename=f"photo_{uuid.uuid4()}.jpg",
            metadata={"content_type": "image/jpeg", "size": len(photo_bytes)}
        )
        await grid_in.write(photo_bytes)
        await grid_in.close()
        return str(file_id)
    except Exception as e:
        logger.error(f"GridFS store error: {e}")
        return ""


async def get_photo_from_gridfs(gridfs_id: str) -> Optional[bytes]:
    """Retrieve a photo from GridFS by its ID string."""
    try:
        from bson import ObjectId
        grid_out = await fs_bucket.open_download_stream(ObjectId(gridfs_id))
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
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY

# --- OTP Store (MongoDB-backed for multi-replica support) ---

def generate_otp(length=6):
    return ''.join(random.choices(string.digits, k=length))

async def store_otp(email, otp, user_data):
    """Store OTP in MongoDB with TTL expiry"""
    await db.otp_store.update_one(
        {"email": email},
        {"$set": {
            "email": email,
            "otp": otp,
            "user_data": user_data,
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
    if not RESEND_API_KEY:
        logger.warning("Resend API key not configured, OTP email not sent")
        return False
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
    params = {"from": SENDER_EMAIL, "to": [email], "subject": f"Kode Verifikasi OTP: {otp}", "html": html_content}
    try:
        result = await asyncio.to_thread(resend.Emails.send, params)
        logger.info(f"OTP email sent to {email}: {result.get('id', 'unknown')}")
        return True
    except Exception as e:
        logger.error(f"Failed to send OTP email to {email}: {str(e)}")
        return False

# --- Audit Logging ---
TRACKED_FIELDS = [
    "asset_name", "category", "brand", "model", "kode_register", "serial_number",
    "purchase_date", "purchase_price", "location", "user",
    "pengguna_melekat_ke", "pengguna_jabatan", "operasional_jenis", "nomor_bast",
    "condition", "status", "NUP", "notes", "stiker_status", "stiker_ukuran", "stiker_photo_index",
    "nomor_spm", "perolehan_dari_nama", "nomor_kontrak", "nomor_bukti_perolehan", "supplier",
    "inventory_status", "klasifikasi_tidak_ditemukan", "sub_klasifikasi", "uraian_tidak_ditemukan", "tindak_lanjut",
    "koordinat_latitude", "koordinat_longitude", "kronologis",
    "keterangan_berlebih", "asal_usul_berlebih", "nomor_perkara", "pihak_bersengketa", "keterangan_sengketa"
]
TRACKED_COUNT_FIELDS = ["photos", "document_checklist"]

async def log_audit(action: str, activity_id: str, asset_id: str = "", asset_code: str = "", asset_name: str = "", username: str = "system", changes: list = None, detail: str = "", nup: str = ""):
    entry = {
        "id": str(uuid.uuid4()), "action": action, "activity_id": activity_id,
        "asset_id": asset_id, "asset_code": asset_code, "nup": nup,
        "asset_name": asset_name, "username": username,
        "changes": changes or [], "detail": detail,
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
