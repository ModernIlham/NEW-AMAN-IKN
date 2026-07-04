"""Inventory activity CRUD routes."""
import io
import uuid
import base64
import logging
import asyncio
import time
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from PIL import Image as PILImage
from bson import ObjectId  # noqa: F401  (kept for downstream import use)

from db import db
from auth_utils import require_user
from routes.media import auto_compress_image
from routes.pdf_compress import compress_pdf_iloveapi, compress_pdf_whipdoc
from shared_utils import (
    decode_data_url,
    store_document_to_gridfs,
    get_document_from_gridfs,
    delete_document_from_gridfs,
)
from routes.pengesahan import next_ticket_number, ensure_ticket_number

logger = logging.getLogger(__name__)
activities_router = APIRouter()

# Per-activity upload limits (matches UI hint "X/10 Foto" and "Y/5 Dokumen")
MAX_ACTIVITY_PHOTOS = 10
MAX_ACTIVITY_DOCUMENTS = 5


def generate_thumbnail(image_data_b64: str, max_size: int = 200) -> str:
    """Generate a small thumbnail from a base64 image."""
    image_bytes = decode_data_url(image_data_b64)
    if not image_bytes:
        return image_data_b64  # Return original if decode failed
    try:
        img = PILImage.open(io.BytesIO(image_bytes))
        # Convert to RGB
        if img.mode in ('RGBA', 'LA', 'P'):
            bg = PILImage.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'RGBA':
                bg.paste(img, mask=img.split()[-1])
            else:
                bg.paste(img)
            img = bg
        # Resize to thumbnail
        img.thumbnail((max_size, max_size), PILImage.LANCZOS)
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=70, optimize=True)
        thumb_b64 = base64.b64encode(output.getvalue()).decode('utf-8')
        return f"data:image/jpeg;base64,{thumb_b64}"
    except Exception as e:
        logger.error(f"Thumbnail generation failed: {e}")
        return image_data_b64  # Return original if fails


async def process_activity_photos(photos: List[str]) -> tuple:
    """Compress photos and generate thumbnails in parallel.

    Returns (compressed_photos, thumbnails). On per-photo failure we keep
    the original bytes so the user never loses uploaded data.
    """
    if not photos:
        return [], []

    async def _process_one(photo: str):
        if not photo:
            return None, None
        try:
            compressed, method, orig_size, comp_size = await auto_compress_image(photo)
            thumb = generate_thumbnail(compressed, max_size=200)
            if method != "none":
                logger.info(f"Activity photo compressed: {orig_size//1024}KB -> {comp_size//1024}KB ({method})")
            return compressed, thumb
        except Exception as e:
            logger.error(f"Photo processing failed: {e}")
            return photo, generate_thumbnail(photo, max_size=200)

    # Run all per-photo work concurrently — Tinify/Pillow are async-friendly.
    # 10 photos × 2s sequential → ~2s parallel.
    results = await asyncio.gather(*(_process_one(p) for p in photos))
    compressed_photos = [r[0] for r in results if r[0] is not None]
    thumbnails = [r[1] for r in results if r[1] is not None]
    return compressed_photos, thumbnails


async def _decode_doc_data_url(data_url: str) -> tuple:
    """Backwards-compatible wrapper around `shared_utils.decode_data_url`.

    Kept to not break call-sites that expect the (bytes, str) tuple shape.
    New code should prefer `decode_data_url` directly.
    """
    raw = decode_data_url(data_url)
    encoded = ""
    if data_url and isinstance(data_url, str):
        encoded = data_url.split("base64,", 1)[1] if "base64," in data_url else data_url
    return raw, encoded


async def process_activity_documents(documents: List[dict], existing_docs: Optional[List[dict]] = None) -> List[dict]:
    """Compress + persist activity PDFs to GridFS (concurrently).

    Input shape (from frontend):
        [{"name": "kontrak.pdf", "data": "data:application/pdf;base64,..."}]
    OR migrated docs that already contain a `gridfs_id`:
        [{"name": "kontrak.pdf", "gridfs_id": "<oid>", "size": 12345}]

    Output shape (stored in DB):
        [{"name": "kontrak.pdf", "gridfs_id": "<oid>", "size": <bytes>,
          "compression_method": "iloveapi|whipdoc|none"}]

    The fat `data` base64 is NEVER persisted in the parent activity document —
    only a GridFS reference. This avoids 16MB BSON limit issues when 5 PDFs
    of 5-10MB each are attached.

    Each PDF is compressed + uploaded concurrently via asyncio.gather so 5
    documents take O(slowest) time instead of O(sum). Without this, the
    HTTP request would commonly time out at the proxy layer.

    `existing_docs` lets us avoid re-compressing documents that were already
    migrated to GridFS in a previous save; we only process inputs that contain
    raw `data` (i.e. newly uploaded by the user).
    """
    if not documents:
        return []

    existing_by_id = {}
    if existing_docs:
        for d in existing_docs:
            gid = d.get("gridfs_id") if isinstance(d, dict) else None
            if gid:
                existing_by_id[gid] = d

    async def _process_one(d: dict) -> Optional[dict]:
        if not isinstance(d, dict):
            return None
        name = d.get("name") or f"document_{uuid.uuid4()}.pdf"

        # Case 1: client sent a kept document (already in GridFS) — pass through
        gid = d.get("gridfs_id")
        if gid and gid in existing_by_id:
            return existing_by_id[gid]

        # Case 2: client sent a new upload with raw `data`
        raw = d.get("data")
        if not raw:
            return None

        pdf_bytes, _ = await _decode_doc_data_url(raw)
        if not pdf_bytes:
            return None

        original_size = len(pdf_bytes)
        compressed, method = None, None

        # Try iLoveAPI → WhipDoc fallback. Both helpers respect quota.
        try:
            compressed, method = await compress_pdf_iloveapi(pdf_bytes, name)
        except Exception as e:
            logger.warning(f"iLoveAPI compress threw for '{name}': {e}")
        if not compressed:
            try:
                compressed, method = await compress_pdf_whipdoc(pdf_bytes, name)
            except Exception as e:
                logger.warning(f"WhipDoc compress threw for '{name}': {e}")

        if compressed and len(compressed) < original_size:
            final_bytes, final_method = compressed, (method or "none")
            logger.info(
                f"Activity PDF '{name}' compressed: "
                f"{original_size//1024}KB → {len(final_bytes)//1024}KB ({final_method})"
            )
        else:
            final_bytes, final_method = pdf_bytes, "none"

        b64 = base64.b64encode(final_bytes).decode("utf-8")
        new_gid = await store_document_to_gridfs(b64, filename=name)
        if not new_gid:
            logger.error(f"Failed to store document '{name}' in GridFS — dropping")
            return None

        return {
            "name": name,
            "gridfs_id": new_gid,
            "size": len(final_bytes),
            "compression_method": final_method,
        }

    results = await asyncio.gather(*(_process_one(d) for d in documents))
    return [r for r in results if r is not None]

# ============================================================================
# INVENTORY ACTIVITY MANAGEMENT
# ============================================================================

class InventoryActivityCreate(BaseModel):
    nomor_surat: str
    nama_kegiatan: str
    deskripsi: Optional[str] = ""
    tanggal_mulai: Optional[str] = ""
    tanggal_selesai: Optional[str] = ""
    penanggung_jawab: Optional[str] = ""
    penanggung_jawab_jabatan: Optional[str] = ""
    penanggung_jawab_nip: Optional[str] = ""
    # photos / documents use None as the "field not provided" sentinel so the
    # PUT handler can tell apart "user wants to wipe all photos/docs" ([]) from
    # "user saved the form without touching photos/docs" (None → keep existing).
    # This is critical after we made the list endpoint strip heavy fields — if
    # the frontend didn't explicitly reload them into the form, saving would
    # otherwise erase them from the DB.
    photos: Optional[List[str]] = None
    documents: Optional[List[dict]] = None
    asset_ids: Optional[List[str]] = []
    # === Satuan Kerja ===
    kode_satker: str = ""
    nama_satker: str = ""
    eselon1: Optional[List[dict]] = []  # [{nama: str, eselon2: [str]}]
    # === Tim Inventarisasi (Internal) ===
    tim_inti: Optional[List[dict]] = []  # [{nama, jabatan, nip, unit, is_ketua: bool}]
    tim_pembantu: Optional[List[dict]] = []  # [{nama, jabatan, nip, unit, is_ketua: bool}]
    # === Tim Eksternal ===
    tim_peneliti: Optional[List[dict]] = []  # [{nama, jabatan, nip}]
    tim_pendukung: Optional[List[dict]] = []  # [{nama, jabatan, nip, dari_pihak}]
    kasatker_nama: Optional[str] = ""
    kasatker_nip: Optional[str] = ""
    kasatker_jabatan: Optional[str] = ""
    alamat_satker: Optional[str] = ""
    nomor_berita_acara: Optional[str] = ""
    tanggal_berita_acara: Optional[str] = ""
    kesimpulan: Optional[str] = ""

class InventoryActivityResponse(BaseModel):
    id: str
    nomor_surat: str
    nama_kegiatan: str
    deskripsi: Optional[str] = ""
    tanggal_mulai: Optional[str] = ""
    tanggal_selesai: Optional[str] = ""
    penanggung_jawab: Optional[str] = ""
    penanggung_jawab_jabatan: Optional[str] = ""
    penanggung_jawab_nip: Optional[str] = ""
    photos: Optional[List[str]] = []
    photo_thumbnails: Optional[List[str]] = []
    documents: Optional[List[dict]] = []
    asset_ids: Optional[List[str]] = []
    total_assets: int = 0
    total_value: float = 0
    summary: Optional[dict] = {}
    # === Satuan Kerja ===
    kode_satker: Optional[str] = ""
    nama_satker: Optional[str] = ""
    eselon1: Optional[List[dict]] = []  # [{nama: str, eselon2: [str]}]
    # === Tim Inventarisasi (Internal) ===
    tim_inti: Optional[List[dict]] = []
    tim_pembantu: Optional[List[dict]] = []
    # === Tim Eksternal ===
    tim_peneliti: Optional[List[dict]] = []
    tim_pendukung: Optional[List[dict]] = []
    kasatker_nama: Optional[str] = ""
    kasatker_nip: Optional[str] = ""
    kasatker_jabatan: Optional[str] = ""
    alamat_satker: Optional[str] = ""
    nomor_berita_acara: Optional[str] = ""
    tanggal_berita_acara: Optional[str] = ""
    kesimpulan: Optional[str] = ""
    created_at: str

@activities_router.get("/inventory-activities")
async def get_inventory_activities():
    """Get all inventory activities with dynamic asset counts
    
    OPTIMIZED: Uses single aggregation query instead of N+1 queries.
    Photos/documents themselves are stripped from the list (heavy base64);
    only their counts are exposed so the UI can show "X/10 Foto" buttons
    without downloading the actual bytes until the user opens the detail.
    """
    start = time.time()

    # Use an aggregation so we can compute $size of photos/documents server-side
    # without materializing them into the response.
    activities = await db.inventory_activities.aggregate([
        {"$sort": {"created_at": -1}},
        {"$limit": 100},
        {"$addFields": {
            "photos_count": {"$size": {"$ifNull": ["$photos", []]}},
            "documents_count": {"$size": {"$ifNull": ["$documents", []]}},
        }},
        {"$project": {
            "_id": 0,
            # Heavy base64 fields stripped
            "photos": 0, "photo_thumbnails": 0, "documents": 0,
        }},
    ]).to_list(100)
    step1_time = time.time() - start

    if not activities:
        return []

    # Backfill malas nomor tiket: hanya menyentuh DB untuk kegiatan lama yang
    # belum punya ticket_number (startup backfill sudah menangani mayoritas).
    for act in activities:
        if not act.get("ticket_number"):
            await ensure_ticket_number(act)

    activity_ids = [act.get("id") for act in activities if act.get("id")]
    
    stats_pipeline = [
        {"$match": {"activity_id": {"$in": activity_ids}}},
        {"$group": {
            "_id": "$activity_id",
            "count": {"$sum": 1},
            "total_value": {"$sum": {"$convert": {
                "input": "$purchase_price", 
                "to": "double", 
                "onError": 0, 
                "onNull": 0
            }}}
        }}
    ]
    all_stats = await db.assets.aggregate(stats_pipeline).to_list(None)
    step2_time = time.time() - start - step1_time
    
    stats_map = {s["_id"]: s for s in all_stats}
    
    for act in activities:
        act_stats = stats_map.get(act.get("id"), {})
        act["total_assets"] = act_stats.get("count", 0)
        act["total_value"] = act_stats.get("total_value", 0)
    
    total_time = time.time() - start
    logger.info(f"get_inventory_activities: fetch={step1_time:.3f}s, aggregate={step2_time:.3f}s, total={total_time:.3f}s")
    
    return activities

@activities_router.get("/satker-list")
async def get_satker_list():
    """Get unique satker pairs (kode_satker + nama_satker) for filter tabs"""
    pipeline = [
        {"$match": {"kode_satker": {"$exists": True, "$ne": ""}}},
        {"$group": {
            "_id": "$kode_satker",
            "nama_satker": {"$first": "$nama_satker"},
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}},
        {"$project": {"_id": 0, "kode_satker": "$_id", "nama_satker": 1, "count": 1}}
    ]
    result = await db.inventory_activities.aggregate(pipeline).to_list(100)
    return result

@activities_router.get("/satker-lookup")
async def satker_lookup(kode: str = "", nama: str = ""):
    """Lookup satker by kode or nama for auto-fill consistency (includes eselon1)"""
    if kode:
        doc = await db.inventory_activities.find_one(
            {"kode_satker": kode}, {"_id": 0, "kode_satker": 1, "nama_satker": 1, "eselon1": 1}
        )
        if doc:
            return {"kode_satker": doc.get("kode_satker", ""), "nama_satker": doc.get("nama_satker", ""), "eselon1": doc.get("eselon1", [])}
    if nama:
        doc = await db.inventory_activities.find_one(
            {"nama_satker": {"$regex": f"^{nama}$", "$options": "i"}},
            {"_id": 0, "kode_satker": 1, "nama_satker": 1, "eselon1": 1}
        )
        if doc:
            return {"kode_satker": doc.get("kode_satker", ""), "nama_satker": doc.get("nama_satker", ""), "eselon1": doc.get("eselon1", [])}
    return None

@activities_router.post("/inventory-activities")
async def create_inventory_activity(activity: InventoryActivityCreate):
    """Create a new inventory activity"""
    # Validate required satker fields
    if not activity.kode_satker.strip():
        raise HTTPException(status_code=400, detail="Kode Satker wajib diisi")
    if not activity.nama_satker.strip():
        raise HTTPException(status_code=400, detail="Nama Satker wajib diisi")

    # Enforce max file counts
    if activity.photos is not None and len(activity.photos) > MAX_ACTIVITY_PHOTOS:
        raise HTTPException(status_code=400, detail=f"Maksimal {MAX_ACTIVITY_PHOTOS} foto kegiatan")
    if activity.documents is not None and len(activity.documents) > MAX_ACTIVITY_DOCUMENTS:
        raise HTTPException(status_code=400, detail=f"Maksimal {MAX_ACTIVITY_DOCUMENTS} dokumen kegiatan")
    
    # Enforce satker consistency: if kode_satker exists, nama_satker must match
    existing_satker = await db.inventory_activities.find_one(
        {"kode_satker": activity.kode_satker.strip()},
        {"_id": 0, "nama_satker": 1}
    )
    if existing_satker and existing_satker.get("nama_satker", "") != activity.nama_satker.strip():
        raise HTTPException(
            status_code=400,
            detail=f"Kode Satker '{activity.kode_satker}' sudah terdaftar dengan nama '{existing_satker['nama_satker']}'. Nama Satker harus sama."
        )
    # Also check reverse: if nama_satker exists, kode_satker must match
    existing_nama = await db.inventory_activities.find_one(
        {"nama_satker": activity.nama_satker.strip(), "kode_satker": {"$ne": activity.kode_satker.strip()}},
        {"_id": 0, "kode_satker": 1}
    )
    if existing_nama:
        raise HTTPException(
            status_code=400,
            detail=f"Nama Satker '{activity.nama_satker}' sudah terdaftar dengan kode '{existing_nama['kode_satker']}'. Kode Satker harus sama."
        )

    # Validate unique nomor_surat
    existing = await db.inventory_activities.find_one({"nomor_surat": activity.nomor_surat})
    if existing:
        raise HTTPException(status_code=400, detail=f"Nomor surat '{activity.nomor_surat}' sudah digunakan sebelumnya")
    
    activity_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    # Calculate summary from linked assets
    total_value = 0
    condition_summary = {}
    status_summary = {}
    category_summary = {}
    
    if activity.asset_ids:
        assets = await db.assets.find(
            {"id": {"$in": activity.asset_ids}}, 
            {"_id": 0, "purchase_price": 1, "condition": 1, "status": 1, "category": 1}
        ).to_list(None)
        
        for a in assets:
            try:
                total_value += float(a.get('purchase_price', 0) or 0)
            except (ValueError, TypeError):
                pass
            cond = a.get('condition', 'Tidak Diketahui')
            stat = a.get('status', 'Tidak Diketahui')
            cat = a.get('category', 'Lainnya')
            condition_summary[cond] = condition_summary.get(cond, 0) + 1
            status_summary[stat] = status_summary.get(stat, 0) + 1
            category_summary[cat] = category_summary.get(cat, 0) + 1
    
    summary = {
        "condition": condition_summary,
        "status": status_summary,
        "category": category_summary
    }
    
    # Process photos: compress + generate thumbnails
    photos_to_store = activity.photos or []
    photo_thumbnails = []
    if photos_to_store:
        logger.info(f"Processing {len(photos_to_store)} activity photos...")
        photos_to_store, photo_thumbnails = await process_activity_photos(photos_to_store)

    # Process documents: compress PDFs (iLoveAPI → WhipDoc) and store in GridFS
    documents_to_store = []
    if activity.documents:
        logger.info(f"Processing {len(activity.documents)} activity documents...")
        documents_to_store = await process_activity_documents(activity.documents)

    payload = activity.model_dump()
    # Replace user-supplied raw payload with our processed/persisted versions
    payload["photos"] = photos_to_store
    payload["documents"] = documents_to_store

    doc = {
        "id": activity_id,
        **payload,
        "photo_thumbnails": photo_thumbnails,
        "total_assets": len(activity.asset_ids or []),
        "total_value": total_value,
        "summary": summary,
        # Nomor tiket: berurutan per tahun, atomik via counters (pengesahan.py)
        "ticket_number": await next_ticket_number(),
        "status_pengesahan": "draft",
        "created_at": now
    }
    
    await db.inventory_activities.insert_one(doc)
    logger.info(f"Inventory activity created: {activity.nomor_surat}")
    
    # Return the created document without MongoDB ObjectId
    created_doc = await db.inventory_activities.find_one({"id": activity_id}, {"_id": 0})
    # Replace heavy GridFS-stored documents with metadata-only entries for response
    return _strip_doc_payload(created_doc)


def _strip_doc_payload(activity: Optional[dict]) -> Optional[dict]:
    """Strip raw `data` base64 from any documents (including legacy inline ones)
    so the response stays small. The frontend reads `gridfs_id` (or for legacy
    inline docs, calls `/inventory-activities/{id}/documents/{idx}`) to fetch
    the bytes on demand.

    Idempotent + safe: tolerates malformed list entries by skipping them
    with a warning log.
    """
    if not activity:
        return activity
    docs = activity.get("documents") or []
    cleaned = []
    for i, d in enumerate(docs):
        if not isinstance(d, dict):
            logger.warning(f"Activity {activity.get('id')} doc[{i}] is not a dict — skipping")
            continue
        if d.get("gridfs_id"):
            cleaned.append({
                "name": d.get("name", ""),
                "gridfs_id": d["gridfs_id"],
                "size": d.get("size", 0),
                "compression_method": d.get("compression_method", "none"),
            })
        elif d.get("data"):
            # Legacy inline document — return a *metadata stub* (no raw base64)
            # so the UI shows a "Lihat" button which fetches via the streaming
            # endpoint. Never leak base64 in list/get responses.
            cleaned.append({
                "name": d.get("name", "document.pdf"),
                "size": 0,
                "compression_method": "legacy-inline",
            })
    activity["documents"] = cleaned
    return activity

@activities_router.get("/inventory-activities/{activity_id}")
async def get_inventory_activity(activity_id: str):
    """Get a single inventory activity (documents stripped of raw bytes)."""
    activity = await db.inventory_activities.find_one({"id": activity_id}, {"_id": 0})
    if not activity:
        raise HTTPException(status_code=404, detail="Kegiatan tidak ditemukan")
    activity = await ensure_ticket_number(activity)
    return _strip_doc_payload(activity)


@activities_router.get("/inventory-activities/{activity_id}/documents/{idx}")
async def get_inventory_activity_document(
    activity_id: str,
    idx: int,
    _user: dict = Depends(require_user),
):
    """Stream a single document by index from GridFS (or inline-base64 legacy).

    Frontend calls this to view/download a PDF on demand instead of inlining
    the bytes inside the activity JSON.

    SECURITY: Requires authenticated user. Previously this endpoint was public
    and could be enumerated to leak BAST/contract PDFs (with PII like nomor
    perkara and pihak bersengketa).
    """
    activity = await db.inventory_activities.find_one(
        {"id": activity_id}, {"_id": 0, "documents": 1}
    )
    if not activity:
        raise HTTPException(status_code=404, detail="Kegiatan tidak ditemukan")
    docs = activity.get("documents") or []
    if idx < 0 or idx >= len(docs):
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")

    doc = docs[idx]
    name = (doc.get("name") if isinstance(doc, dict) else None) or "document.pdf"

    # Prefer GridFS
    gid = doc.get("gridfs_id") if isinstance(doc, dict) else None
    if gid:
        pdf_bytes = await get_document_from_gridfs(gid)
        if not pdf_bytes:
            raise HTTPException(status_code=404, detail="File dokumen tidak tersedia")
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{name}"'},
        )

    # Legacy inline base64 fallback
    raw = doc.get("data") if isinstance(doc, dict) else None
    if raw:
        pdf_bytes, _ = await _decode_doc_data_url(raw)
        if pdf_bytes:
            return StreamingResponse(
                io.BytesIO(pdf_bytes),
                media_type="application/pdf",
                headers={"Content-Disposition": f'inline; filename="{name}"'},
            )

    raise HTTPException(status_code=404, detail="Konten dokumen tidak ditemukan")

@activities_router.put("/inventory-activities/{activity_id}")
async def update_inventory_activity(activity_id: str, activity: InventoryActivityCreate):
    """Update an existing inventory activity"""
    existing = await db.inventory_activities.find_one({"id": activity_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Kegiatan tidak ditemukan")
    
    # Validate required satker fields
    if not activity.kode_satker.strip():
        raise HTTPException(status_code=400, detail="Kode Satker wajib diisi")
    if not activity.nama_satker.strip():
        raise HTTPException(status_code=400, detail="Nama Satker wajib diisi")

    # Enforce max file counts (only when the fields are actually being updated)
    if activity.photos is not None and len(activity.photos) > MAX_ACTIVITY_PHOTOS:
        raise HTTPException(status_code=400, detail=f"Maksimal {MAX_ACTIVITY_PHOTOS} foto kegiatan")
    if activity.documents is not None and len(activity.documents) > MAX_ACTIVITY_DOCUMENTS:
        raise HTTPException(status_code=400, detail=f"Maksimal {MAX_ACTIVITY_DOCUMENTS} dokumen kegiatan")

    # Enforce satker consistency (exclude self)
    existing_satker = await db.inventory_activities.find_one(
        {"kode_satker": activity.kode_satker.strip(), "id": {"$ne": activity_id}},
        {"_id": 0, "nama_satker": 1}
    )
    if existing_satker and existing_satker.get("nama_satker", "") != activity.nama_satker.strip():
        raise HTTPException(
            status_code=400,
            detail=f"Kode Satker '{activity.kode_satker}' sudah terdaftar dengan nama '{existing_satker['nama_satker']}'. Nama Satker harus sama."
        )
    existing_nama = await db.inventory_activities.find_one(
        {"nama_satker": activity.nama_satker.strip(), "kode_satker": {"$ne": activity.kode_satker.strip()}, "id": {"$ne": activity_id}},
        {"_id": 0, "kode_satker": 1}
    )
    if existing_nama:
        raise HTTPException(
            status_code=400,
            detail=f"Nama Satker '{activity.nama_satker}' sudah terdaftar dengan kode '{existing_nama['kode_satker']}'. Kode Satker harus sama."
        )
    
    # Check unique nomor_surat (exclude self)
    if activity.nomor_surat != existing.get("nomor_surat"):
        dup = await db.inventory_activities.find_one({
            "nomor_surat": activity.nomor_surat,
            "id": {"$ne": activity_id}
        })
        if dup:
            raise HTTPException(status_code=400, detail=f"Nomor surat '{activity.nomor_surat}' sudah digunakan sebelumnya")
    
    update_data = activity.model_dump()
    update_data["created_at"] = existing.get("created_at")

    # ── Lazy-load friendly semantics ───────────────────────────────────────
    # When the frontend opens the edit form, it no longer eagerly loads photos
    # & documents (they can each be multi-MB base64). If the user saves the
    # form WITHOUT clicking the "Lihat & Kelola" button to fetch them, the
    # request omits those fields → Pydantic gives us None. In that case we
    # MUST NOT touch the existing DB values. An explicit `[]` still means
    # "wipe all" so the user can still clear everything intentionally.
    if activity.photos is None:
        # Keep existing photos + thumbnails untouched
        update_data.pop("photos", None)
        update_data.pop("photo_thumbnails", None)
    else:
        # Process photos: compress new ones, keep already-compressed
        new_photos = activity.photos
        old_photos = existing.get("photos", [])
        old_thumbnails = existing.get("photo_thumbnails", [])

        photos_to_process = []
        kept_photos = []
        kept_thumbnails = []

        for photo in new_photos:
            if photo in old_photos:
                idx = old_photos.index(photo)
                kept_photos.append(photo)
                if idx < len(old_thumbnails):
                    kept_thumbnails.append(old_thumbnails[idx])
                else:
                    kept_thumbnails.append(generate_thumbnail(photo, max_size=200))
            else:
                photos_to_process.append(photo)

        if photos_to_process:
            logger.info(f"Processing {len(photos_to_process)} new activity photos...")
            compressed_new, thumbs_new = await process_activity_photos(photos_to_process)
            kept_photos.extend(compressed_new)
            kept_thumbnails.extend(thumbs_new)

        update_data["photos"] = kept_photos
        update_data["photo_thumbnails"] = kept_thumbnails

    if activity.documents is None:
        # Keep existing documents (already in GridFS) untouched
        update_data.pop("documents", None)
        deferred_doc_deletes = []
    else:
        # User explicitly sent the documents array. Diff against existing docs:
        #   - kept docs (with `gridfs_id` matching an existing one) → reuse as-is
        #   - new docs (with `data` base64) → compress + push to GridFS
        #   - removed docs → marked for deletion AFTER successful DB write
        #     (deleting before DB commit risks orphan reference if commit fails)
        old_docs = existing.get("documents") or []
        old_by_id = {d["gridfs_id"]: d for d in old_docs if isinstance(d, dict) and d.get("gridfs_id")}

        processed = await process_activity_documents(activity.documents, existing_docs=old_docs)

        # Identify GridFS IDs no longer referenced — defer actual deletion
        kept_ids = {d["gridfs_id"] for d in processed if isinstance(d, dict) and d.get("gridfs_id")}
        deferred_doc_deletes = [orphan_id for orphan_id in old_by_id if orphan_id not in kept_ids]

        update_data["documents"] = processed

    await db.inventory_activities.update_one(
        {"id": activity_id},
        {"$set": update_data}
    )

    # Safe to delete orphan GridFS blobs only AFTER the DB write succeeded.
    # Failures here are non-fatal (we just have a temporary orphan blob, can
    # be cleaned up by a periodic GC job).
    for orphan_id in deferred_doc_deletes:
        await delete_document_from_gridfs(orphan_id)
        logger.info(f"Deleted orphan document GridFS blob: {orphan_id}")

    logger.info(f"Inventory activity updated: {activity.nomor_surat}")
    updated = await db.inventory_activities.find_one({"id": activity_id}, {"_id": 0})
    return _strip_doc_payload(updated)

@activities_router.delete("/inventory-activities/{activity_id}")
async def delete_inventory_activity(activity_id: str):
    """Delete an inventory activity and all its assets"""
    # Kegiatan yang sudah disahkan terkunci — hapus kegiatan mengkaskade ke
    # semua asetnya, jadi wajib ditolak juga (konsisten dengan bulk-delete).
    sealed = await db.inventory_activities.find_one(
        {"id": activity_id, "status_pengesahan": "disahkan"}, {"_id": 0, "id": 1}
    )
    if sealed:
        raise HTTPException(status_code=423, detail="Kegiatan sudah disahkan dan terkunci")

    # First load existing to clean up GridFS document blobs
    existing = await db.inventory_activities.find_one({"id": activity_id}, {"_id": 0, "documents": 1})
    if existing:
        for d in (existing.get("documents") or []):
            gid = d.get("gridfs_id") if isinstance(d, dict) else None
            if gid:
                await delete_document_from_gridfs(gid)

    result = await db.inventory_activities.delete_one({"id": activity_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Kegiatan tidak ditemukan")
    # Delete all assets linked to this activity
    asset_result = await db.assets.delete_many({"activity_id": activity_id})
    logger.info(f"Deleted activity {activity_id} and {asset_result.deleted_count} associated assets")
    return {"message": f"Kegiatan berhasil dihapus beserta {asset_result.deleted_count} data aset"}


@activities_router.get("/inventory-activities/{activity_id}/completion-status")
async def get_completion_status(activity_id: str):
    """Validate whether an activity qualifies as 'Selesai'.

    Called ON-DEMAND when the user clicks the status ribbon on the activity
    card — NOT on every list render — because scanning every asset is
    relatively expensive compared to a lightweight date comparison.

    A kegiatan is `selesai` only if ALL of:
      1. tanggal_selesai has passed (date-based precondition);
      2. every linked asset has inventory_status != "Belum Diinventarisasi";
      3. every linked asset has at least one photo (inline or GridFS).

    Returns detail counts so the UI can surface WHY an activity is not yet
    complete (e.g. "2 aset belum diinventarisasi, 5 aset belum berfoto").
    """
    activity = await db.inventory_activities.find_one(
        {"id": activity_id},
        {"_id": 0, "tanggal_mulai": 1, "tanggal_selesai": 1}
    )
    if not activity:
        raise HTTPException(status_code=404, detail="Kegiatan tidak ditemukan")

    # Assets with inventory pending
    pending_filter = {
        "activity_id": activity_id,
        "$or": [
            {"inventory_status": {"$in": ["", "Belum Diinventarisasi", None]}},
            {"inventory_status": {"$exists": False}},
        ],
    }
    pending_count = await db.assets.count_documents(pending_filter)

    # Assets without any photo — check both legacy `photos` array and
    # GridFS-referenced `photo_gridfs_ids` so newer and older data both work.
    no_photo_filter = {
        "activity_id": activity_id,
        "$and": [
            {"$or": [{"photos": {"$exists": False}}, {"photos": {"$size": 0}}]},
            {"$or": [{"photo_gridfs_ids": {"$exists": False}}, {"photo_gridfs_ids": {"$size": 0}}]},
        ],
    }
    no_photo_count = await db.assets.count_documents(no_photo_filter)

    total_assets = await db.assets.count_documents({"activity_id": activity_id})

    from datetime import date
    today = date.today().isoformat()
    date_mulai = (activity.get("tanggal_mulai") or "").strip()
    date_selesai = (activity.get("tanggal_selesai") or "").strip()

    if not date_mulai:
        date_phase = "belum_dimulai"
    elif today < date_mulai:
        date_phase = "belum_dimulai"
    elif date_selesai and today > date_selesai:
        date_phase = "selesai_tanggal"
    else:
        date_phase = "berlangsung"

    all_inventoried = pending_count == 0 and total_assets > 0
    all_have_photos = no_photo_count == 0 and total_assets > 0

    if date_phase == "belum_dimulai":
        computed = "belum_dimulai"
    elif date_phase == "selesai_tanggal" and all_inventoried and all_have_photos:
        computed = "selesai"
    elif date_phase == "selesai_tanggal":
        computed = "belum_lengkap"
    else:
        computed = "berlangsung"

    return {
        "activity_id": activity_id,
        "date_phase": date_phase,
        "computed_status": computed,
        "total_assets": total_assets,
        "pending_inventory_count": pending_count,
        "no_photo_count": no_photo_count,
        "all_inventoried": all_inventoried,
        "all_have_photos": all_have_photos,
    }


