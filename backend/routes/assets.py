"""Asset CRUD, filter options, stats, analytics."""
import re
import uuid
import base64
import logging
import asyncio
from collections import deque
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, Depends, UploadFile, File
from fastapi.responses import Response

from db import db, fs_bucket
from models import AssetCreate, AssetResponse
from auth_utils import require_user, require_admin, require_user_or_query_token
from shared_utils import (
    invalidate_asset_cache, _cache_filter_opts, _cache_stats, _cache_analytics,
    log_audit, compute_changes, create_thumbnail, create_gallery_thumbnail,
    store_photo_to_gridfs, get_photo_from_gridfs, delete_photo_from_gridfs,
    generate_photo_thumbnail,
    get_idempotent_response, store_idempotent_response, reserve_idempotency_key,
    ensure_activity_not_sealed,
    get_document_from_gridfs, delete_document_from_gridfs,
)
from routes.websocket import notify_asset_change

logger = logging.getLogger(__name__)
assets_router = APIRouter()

# ============================================================================
# ASSET ROUTES
# ============================================================================


def _rx(term: str) -> dict:
    """Case-insensitive substring match treating user input as a LITERAL
    (re.escape). Prevents ReDoS + invalid-regex 500s from crafted input like
    "(a+)+$" or "[" while preserving plain substring search semantics."""
    return {"$regex": re.escape(term), "$options": "i"}


async def _collect_asset_blob_ids(asset: dict) -> dict:
    """Gather GridFS blob ids referenced by an asset so they can be deleted
    alongside the doc (prevents orphaned blobs on delete). In this schema only
    full-size photos (photo_gridfs_ids) and the BAST file live in GridFS;
    checklist photos/PDFs are stored inline and vanish with the doc. Any
    checklist doc `gridfs_id` is collected defensively for forward-compat."""
    photo_ids = [g for g in (asset.get("photo_gridfs_ids") or []) if g]
    doc_ids = []
    bast_id = asset.get("bast_file_id") or ""
    if bast_id:
        doc_ids.append(bast_id)
    for item in (asset.get("document_checklist") or []):
        if not isinstance(item, dict):
            continue
        for d in (item.get("documents") or []):
            gid = d.get("gridfs_id") if isinstance(d, dict) else None
            if gid:
                doc_ids.append(gid)
    return {"photos": photo_ids, "documents": doc_ids}


# NOTE: Row locking & batch operations moved to routes/batch.py


def _build_cas_filter(asset_id: str, current_version: int) -> dict:
    """Build a resilient CAS (Compare-And-Swap) filter for the assets collection.

    Legacy assets (created before OCC was introduced, or restored from older
    backups) may be missing the `version` field entirely. In that case
    `existing.get("version", 1)` returns 1 (our default), but a plain query
    `{"version": 1}` will NOT match a document without the field.

    When current_version == 1 we therefore additionally accept docs where
    version is missing — this lets the very first write after an upgrade
    succeed and backfill the version field via `$inc`.
    """
    if current_version == 1:
        return {
            "id": asset_id,
            "$or": [
                {"version": 1},
                {"version": {"$exists": False}},
            ],
        }
    return {"id": asset_id, "version": current_version}


# OPTIMIZED: Lightweight list projection - excludes photos and document_checklist.
# Photos and document_checklist are fetched separately when editing an asset;
# this reduces response size by ~95% for assets with images. Shared by
# GET /assets and GET /assets/offline-snapshot so the offline cache stores
# EXACTLY the same (media-free) shape as the live list.
LIST_PROJECTION = {
    "_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
    "category": 1, "brand": 1, "model": 1, "kode_register": 1,
    "serial_number": 1, "purchase_date": 1, "purchase_price": 1,
    "location": 1, "eselon1": 1, "eselon2": 1, "user": 1, "condition": 1,
    "pengguna_melekat_ke": 1, "pengguna_jabatan": 1, "operasional_jenis": 1,
    "nomor_bast": 1,
    "bast_file_id": 1, "bast_filename": 1,
    "status": 1, "nomor_spm": 1, "perolehan_dari_nama": 1,
    "nomor_kontrak": 1, "nomor_bukti_perolehan": 1, "supplier": 1,
    "notes": 1, "thumbnail": 1, "thumbnail_index": 1,
    "gallery_thumbnail": 1,
    "created_at": 1, "updated_at": 1, "activity_id": 1,
    "version": 1,  # OCC: client needs this to send If-Match on subsequent writes
    "stiker_status": 1, "stiker_ukuran": 1, "stiker_photo_index": 1,
    "inventory_status": 1, "klasifikasi_tidak_ditemukan": 1, "sub_klasifikasi": 1,
    "uraian_tidak_ditemukan": 1, "tindak_lanjut": 1,
    "koordinat_latitude": 1, "koordinat_longitude": 1, "kronologis": 1,
    "photo_count": {"$size": {"$ifNull": ["$photos", []]}},
    # Computed doc checklist summary (avoids sending full checklist data)
    "doc_total": {"$size": {"$ifNull": ["$document_checklist", []]}},
    "doc_checked": {"$size": {"$filter": {
        "input": {"$ifNull": ["$document_checklist", []]},
        "cond": {"$eq": ["$$this.checked", True]}
    }}},
    "doc_summary": {"$map": {
        "input": {"$ifNull": ["$document_checklist", []]},
        "as": "doc",
        "in": {
            "name": "$$doc.name",
            "checked": "$$doc.checked",
            "has_photos": {"$gt": [{"$size": {"$ifNull": ["$$doc.photos", []]}}, 0]},
            "has_documents": {"$gt": [{"$size": {"$ifNull": ["$$doc.documents", []]}}, 0]},
            "photo_count": {"$size": {"$ifNull": ["$$doc.photos", []]}},
            "doc_count": {"$size": {"$ifNull": ["$$doc.documents", []]}}
        }
    }}
    # EXCLUDED: "photos", "document_checklist" - fetched via GET /assets/{id}
}


@assets_router.get("/assets")
async def get_assets(
    search: str = "",
    category: str = "",
    sort_by: str = "newest",
    page: int = 1,
    page_size: int = 50,
    activity_id: str = "",
    # Advanced filters
    condition: str = "",
    status: str = "",
    location: str = "",
    eselon1_filter: str = "",
    eselon2_filter: str = "",
    stiker_status: str = "",
    inventory_status: str = "",
    price_min: float = None,
    price_max: float = None,
    nomor_spm: str = "",
    perolehan_dari: str = "",
    _user: dict = Depends(require_user),
):
    """Get paginated assets with advanced filters - optimized for millions of records"""
    query = {}
    
    # Filter by activity_id if provided
    if activity_id:
        query["activity_id"] = activity_id
    
    # Multi-field search with regex - EXTENDED to cover all important fields
    if search:
        # Try to detect if search is a number (for price search)
        search_as_number = None
        search_as_string = None
        try:
            # Remove dots and commas for Indonesian number format
            clean_search = search.replace(".", "").replace(",", "")
            search_as_number = float(clean_search)
            search_as_string = clean_search  # Also search as string since prices might be stored as strings
        except ValueError:
            pass
        
        rx = _rx(search)
        search_conditions = [
            {"asset_code": rx},
            {"asset_name": rx},
            {"serial_number": rx},
            {"location": rx},
            {"brand": rx},
            {"model": rx},
            {"category": rx},
            {"eselon1": rx},
            {"eselon2": rx},
            {"user": rx},
            {"supplier": rx},
            {"condition": rx},
            {"status": rx},
            {"nomor_spm": rx},
            {"kode_register": rx},
            {"notes": rx},
        ]

        # Add numeric search for purchase_price if search looks like a number
        if search_as_number is not None:
            search_conditions.append({"purchase_price": search_as_number})
            # Also search as string (prices might be stored as strings)
            search_conditions.append({"purchase_price": search_as_string})
            search_conditions.append({"purchase_price": {"$regex": f"^{re.escape(search_as_string)}", "$options": "i"}})
        
        query["$or"] = search_conditions
    
    # Basic category filter
    if category:
        query["category"] = category
    
    # Advanced filters
    if condition:
        query["condition"] = condition
    
    if status:
        query["status"] = status
    
    if location:
        query["location"] = _rx(location)

    if eselon1_filter:
        query["eselon1"] = _rx(eselon1_filter)

    if eselon2_filter:
        query["eselon2"] = _rx(eselon2_filter)

    if stiker_status:
        query["stiker_status"] = stiker_status

    if inventory_status:
        query["inventory_status"] = inventory_status

    if nomor_spm:
        query["nomor_spm"] = _rx(nomor_spm)

    if perolehan_dari:
        query["supplier"] = _rx(perolehan_dari)
    
    # Price range filter
    if price_min is not None or price_max is not None:
        price_query = {}
        if price_min is not None:
            price_query["$gte"] = price_min
        if price_max is not None:
            price_query["$lte"] = price_max
        if price_query:
            # Handle both numeric and string prices (including empty strings)
            # Use $convert with onError to handle empty strings and invalid values
            price_convert = {
                "$convert": {
                    "input": "$purchase_price",
                    "to": "double",
                    "onError": 0,
                    "onNull": 0
                }
            }
            query["$expr"] = {
                "$and": [
                    {"$gte": [price_convert, price_min or 0]},
                    {"$lte": [price_convert, price_max or 999999999999]}
                ]
            }
    
    # Extended sort options
    sort_options = {
        "newest": [("created_at", -1)],
        "oldest": [("created_at", 1)],
        "name_asc": [("asset_name", 1)],
        "name_desc": [("asset_name", -1)],
        "price_asc": [("purchase_price", 1)],
        "price_desc": [("purchase_price", -1)],
        "category_asc": [("category", 1)],
        "category_desc": [("category", -1)],
        "location_asc": [("location", 1)],
        "eselon1_asc": [("eselon1", 1)],
        "condition_asc": [("condition", 1)],
        "status_asc": [("status", 1)]
    }
    sort = sort_options.get(sort_by, [("created_at", -1)])
    
    # Lightweight shared list projection (see LIST_PROJECTION above)
    projection = LIST_PROJECTION

    # Clamp page_size - allow up to 500 for power users
    page_size = min(max(page_size, 10), 500)
    skip = (max(page, 1) - 1) * page_size
    
    # Run count and fetch in parallel using aggregation for computed fields
    pipeline = [
        {"$match": query},
        {"$sort": dict(sort)},
        {"$skip": skip},
        {"$limit": page_size},
        {"$project": projection}
    ]
    total, assets = await asyncio.gather(
        db.assets.count_documents(query),
        db.assets.aggregate(pipeline).to_list(page_size)
    )
    
    total_pages = max(1, (total + page_size - 1) // page_size)
    
    return {
        "items": assets,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


@assets_router.get("/assets/offline-snapshot")
async def get_assets_offline_snapshot(
    activity_id: str,
    since: str = "",
    skip: int = 0,
    limit: int = 1000,
    _user: dict = Depends(require_user),
):
    """Delta feed for the client-side offline read cache (inventory mode).

    Returns list-projection assets (LIST_PROJECTION — NO photos / full
    document_checklist) for ONE activity, paged with skip/limit so 10k assets
    stream in chunks of <= 1000. With `since` (ISO timestamp from a previous
    response's `server_time`) only assets changed after that moment are
    returned — creates/PUT/PATCH/batch all stamp `updated_at`.

    Tombstones: there is no dedicated deletions log, but every single-asset
    DELETE writes an audit entry (action='delete' with asset_id), so those are
    returned as `deleted_ids`. Bulk deletes (action='bulk_delete') carry no
    per-asset ids — when one happened after `since` we set
    `requires_full_refresh` and the client re-syncs from scratch (a full
    refresh reconciles deletes by definition).

    Auth: gated by require_user like other protected endpoints, and strictly
    scoped by activity_id (400 without it) so a snapshot can never leak
    assets from another activity.
    """
    if not activity_id:
        raise HTTPException(status_code=400, detail="activity_id wajib diisi")

    limit = min(max(limit, 1), 1000)
    skip = max(skip, 0)

    # Capture server_time BEFORE querying: anything written while we stream
    # pages is (re-)fetched by the next delta — upserts are idempotent.
    server_time = datetime.now(timezone.utc).isoformat()

    query = {"activity_id": activity_id}
    if since:
        # Legacy docs created before updated_at stamping existed only have
        # created_at — cover both so a fresh row is never missed.
        query["$or"] = [
            {"updated_at": {"$gt": since}},
            {"updated_at": {"$exists": False}, "created_at": {"$gt": since}},
        ]

    # Deterministic total order (created_at can tie on imports; id breaks the
    # tie) so skip/limit pages never overlap or skip rows.
    pipeline = [
        {"$match": query},
        {"$sort": {"created_at": -1, "id": 1}},
        {"$skip": skip},
        {"$limit": limit},
        {"$project": LIST_PROJECTION},
    ]
    total, assets = await asyncio.gather(
        db.assets.count_documents(query),
        db.assets.aggregate(pipeline).to_list(limit),
    )

    # Tombstones only make sense for a delta, and only need to be sent once
    # per sync run (first page).
    deleted_ids = []
    requires_full_refresh = False
    if since and skip == 0:
        tomb_query = {"action": "delete", "activity_id": activity_id, "timestamp": {"$gt": since}}
        tombstones = await db.audit_logs.find(tomb_query, {"_id": 0, "asset_id": 1}).to_list(10000)
        deleted_ids = [t["asset_id"] for t in tombstones if t.get("asset_id")]
        bulk = await db.audit_logs.count_documents(
            {"action": "bulk_delete", "activity_id": activity_id, "timestamp": {"$gt": since}}
        )
        requires_full_refresh = bulk > 0

    return {
        "items": assets,
        "total": total,
        "skip": skip,
        "limit": limit,
        "server_time": server_time,
        "deleted_ids": deleted_ids,
        "requires_full_refresh": requires_full_refresh,
    }


@assets_router.get("/assets/filter-options")
async def get_filter_options(activity_id: str = "", _user: dict = Depends(require_user)):
    """Get distinct values for filter dropdowns (cached 3 min per activity)"""
    cache_key = activity_id or "__all__"
    if cache_key in _cache_filter_opts:
        return _cache_filter_opts[cache_key]
    
    query = {}
    if activity_id:
        query["activity_id"] = activity_id
    
    # Get distinct values for each filterable field
    locations, eselon1s, eselon2s, conditions, statuses, stiker_statuses, inventory_statuses = await asyncio.gather(
        db.assets.distinct("location", query),
        db.assets.distinct("eselon1", query),
        db.assets.distinct("eselon2", query),
        db.assets.distinct("condition", query),
        db.assets.distinct("status", query),
        db.assets.distinct("stiker_status", query),
        db.assets.distinct("inventory_status", query)
    )
    
    # Filter out None/empty values and sort
    clean_sort = lambda lst: sorted([x for x in lst if x and str(x).strip()])
    
    result = {
        "locations": clean_sort(locations),
        "eselon1s": clean_sort(eselon1s),
        "eselon2s": clean_sort(eselon2s),
        "conditions": clean_sort(conditions),
        "statuses": clean_sort(statuses),
        "stiker_statuses": clean_sort(stiker_statuses),
        "inventory_statuses": clean_sort(inventory_statuses)
    }
    _cache_filter_opts[cache_key] = result
    return result

@assets_router.get("/assets/stats")
async def get_assets_stats(search: str = "", category: str = "", activity_id: str = "",
                           _user: dict = Depends(require_user)):
    """Get aggregate stats (cached 1 min per unique query)"""
    cache_key = f"{activity_id}|{search}|{category}"
    if cache_key in _cache_stats:
        return _cache_stats[cache_key]

    query = {}
    if activity_id:
        query["activity_id"] = activity_id
    if search:
        rx = _rx(search)
        query["$or"] = [
            {"asset_code": rx},
            {"asset_name": rx},
            {"serial_number": rx},
            {"location": rx},
            {"brand": rx},
        ]
    if category:
        query["category"] = category
    
    pipeline = [
        {"$match": query},
        {"$group": {
            "_id": None,
            "total_assets": {"$sum": 1},
            "total_value": {"$sum": {
                "$convert": {
                    "input": "$purchase_price",
                    "to": "double",
                    "onError": 0,
                    "onNull": 0
                }
            }},
            "active_count": {"$sum": {"$cond": [{"$eq": ["$status", "Aktif"]}, 1, 0]}},
            "maintenance_count": {"$sum": {"$cond": [{"$eq": ["$status", "Maintenance"]}, 1, 0]}}
        }}
    ]
    
    result = await db.assets.aggregate(pipeline).to_list(1)
    if result:
        r = result[0]
        stats = {
            "total_assets": r["total_assets"],
            "total_value": r["total_value"],
            "active_count": r["active_count"],
            "maintenance_count": r["maintenance_count"]
        }
    else:
        stats = {"total_assets": 0, "total_value": 0, "active_count": 0, "maintenance_count": 0}
    _cache_stats[cache_key] = stats
    return stats

@assets_router.get("/assets/analytics")
async def get_assets_analytics(activity_id: str = "", _user: dict = Depends(require_user)):
    """Get analytics data for charts (cached 2 min per activity)"""
    cache_key = activity_id or "_all"
    if cache_key in _cache_analytics:
        return _cache_analytics[cache_key]
    
    query = {}
    if activity_id:
        query["activity_id"] = activity_id

    price_convert = {"$convert": {"input": "$purchase_price", "to": "double", "onError": 0, "onNull": 0}}

    # Run all aggregations in parallel
    by_category = db.assets.aggregate([
        {"$match": query},
        {"$group": {"_id": "$category", "count": {"$sum": 1}, "value": {"$sum": price_convert}}},
        {"$sort": {"count": -1}},
        {"$limit": 15}
    ]).to_list(15)

    by_condition = db.assets.aggregate([
        {"$match": query},
        {"$group": {"_id": {"$ifNull": ["$condition", "Tidak Diketahui"]}, "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]).to_list(20)

    by_status = db.assets.aggregate([
        {"$match": query},
        {"$group": {"_id": {"$ifNull": ["$status", "Tidak Diketahui"]}, "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]).to_list(20)

    by_location = db.assets.aggregate([
        {"$match": query},
        {"$group": {"_id": {"$ifNull": ["$location", "Tidak Diketahui"]}, "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]).to_list(10)

    by_eselon = db.assets.aggregate([
        {"$match": query},
        {"$group": {"_id": {"$ifNull": ["$eselon1", "Tidak Diketahui"]}, "count": {"$sum": 1}, "value": {"$sum": price_convert}}},
        {"$sort": {"value": -1}},
        {"$limit": 10}
    ]).to_list(10)

    import asyncio
    cat_res, cond_res, stat_res, loc_res, eselon_res = await asyncio.gather(
        by_category, by_condition, by_status, by_location, by_eselon
    )

    result = {
        "by_category": [{"name": r["_id"] or "Lainnya", "count": r["count"], "value": r["value"]} for r in cat_res],
        "by_condition": [{"name": r["_id"] or "Lainnya", "count": r["count"]} for r in cond_res],
        "by_status": [{"name": r["_id"] or "Lainnya", "count": r["count"]} for r in stat_res],
        "by_location": [{"name": r["_id"] or "Lainnya", "count": r["count"]} for r in loc_res],
        "by_eselon": [{"name": r["_id"] or "Lainnya", "count": r["count"], "value": r["value"]} for r in eselon_res],
    }
    _cache_analytics[cache_key] = result
    return result


# Must be declared BEFORE /assets/{asset_id} or "next-nup" would be captured
# as an asset id by that route.
@assets_router.get("/assets/next-nup")
async def get_next_nup(activity_id: str = "", asset_code: str = "", category: str = "",
                       _user: dict = Depends(require_user)):
    """Next available numeric NUP for a category/asset_code within an activity.

    Uniqueness in this app is (asset_code, NUP) per activity_id, so the next
    number is computed over the same scope. NUP is stored as a string; values
    that aren't parseable as integers are ignored via $convert onError.
    """
    query = {}
    if activity_id:
        query["activity_id"] = activity_id
    if asset_code:
        query["asset_code"] = asset_code
    elif category:
        query["category"] = category
    else:
        raise HTTPException(status_code=400, detail="asset_code atau category wajib diisi")

    res = await db.assets.aggregate([
        {"$match": query},
        {"$group": {"_id": None, "max_nup": {"$max": {"$convert": {
            "input": "$NUP", "to": "int", "onError": None, "onNull": None
        }}}}}
    ]).to_list(1)

    max_nup = (res[0].get("max_nup") if res else None) or 0
    return {"next_nup": str(max_nup + 1), "max_nup": str(max_nup)}


# NOTE: Audit logs moved to routes/audit.py
# NOTE: Image compression moved to routes/media.py

async def process_photos_for_storage(photos: list) -> dict:
    """Store photos in GridFS and generate thumbnails. Atomic: rolls back on failure.
    Returns {gridfs_ids, thumbnails}."""
    gridfs_ids = []
    thumbnails = []
    try:
        for photo in photos:
            gid = await store_photo_to_gridfs(photo)
            gridfs_ids.append(gid)
            thumb = generate_photo_thumbnail(photo, size=100, quality=70)
            thumbnails.append(thumb or "")
    except Exception as e:
        # Rollback: clean up any already-stored GridFS blobs to prevent orphans
        logger.warning(f"Photo processing failed, rolling back {len(gridfs_ids)} blobs: {e}")
        for gid in gridfs_ids:
            try:
                await delete_photo_from_gridfs(gid)
            except Exception:
                pass
        raise
    return {"gridfs_ids": gridfs_ids, "thumbnails": thumbnails}


@assets_router.post("/assets", response_model=AssetResponse)
async def create_asset(asset: AssetCreate, request: Request, _user: dict = Depends(require_user)):
    """Create a new asset. Supports Idempotency-Key header to safely retry on network errors."""
    # Idempotency check: if same key was seen within the TTL window (24h), return cached response
    idem_key = request.headers.get("Idempotency-Key", "")
    if idem_key:
        cached = await get_idempotent_response(idem_key)
        if cached and cached.get("response"):
            logger.info(f"Idempotent replay for key {idem_key[:8]}...")
            return AssetResponse(**cached["response"])
        # Atomically claim the key so concurrent duplicates can't both run.
        _idem = await reserve_idempotency_key(idem_key)
        if _idem == "done":
            cached = await get_idempotent_response(idem_key)
            if cached and cached.get("response"):
                return AssetResponse(**cached["response"])
        elif _idem == "pending":
            raise HTTPException(status_code=409, detail="Permintaan dengan kunci idempotensi ini sedang diproses, coba lagi sebentar")

    # Kegiatan yang sudah disahkan terkunci — tolak penambahan aset (423)
    await ensure_activity_not_sealed(asset.activity_id)

    # Check uniqueness: asset_code + NUP within same activity
    existing_query = {
        "asset_code": asset.asset_code,
        "NUP": asset.NUP or "",
        "activity_id": asset.activity_id
    }
    existing = await db.assets.find_one(existing_query)
    if existing:
        raise HTTPException(status_code=400, detail=f"Kombinasi Kode Barang '{asset.asset_code}' dan NUP '{asset.NUP}' sudah digunakan dalam kegiatan ini")
    
    # Check kode_register uniqueness within same activity (if provided)
    if asset.kode_register and asset.activity_id:
        kr_existing = await db.assets.find_one({
            "kode_register": asset.kode_register,
            "activity_id": asset.activity_id
        })
        if kr_existing:
            raise HTTPException(status_code=400, detail=f"Kode Register '{asset.kode_register}' sudah digunakan dalam kegiatan ini")
    
    asset_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    # Process photos: store in GridFS + generate thumbnails (atomic with rollback)
    photos = asset.photos or []
    if asset.photo and not photos:
        photos = [asset.photo]
    
    photo_gridfs_ids = []
    photo_thumbnails = []
    thumbnail = None
    gallery_thumbnail = None
    
    if photos:
        result = await process_photos_for_storage(photos)
        photo_gridfs_ids = result["gridfs_ids"]
        photo_thumbnails = result["thumbnails"]
        cover_idx = min(asset.thumbnail_index or 0, len(photos) - 1)
        thumbnail = create_thumbnail(photos[cover_idx])
        gallery_thumbnail = create_gallery_thumbnail(photos[cover_idx])

    asset_doc = {
        "id": asset_id,
        **asset.model_dump(),
        "photos": photos,
        "photo_gridfs_ids": photo_gridfs_ids,
        "photo_thumbnails": photo_thumbnails,
        "photo": photos[cover_idx] if photos else None,
        "thumbnail": thumbnail,
        "gallery_thumbnail": gallery_thumbnail,
        "thumbnail_index": asset.thumbnail_index or 0,
        "document_checklist": [item.model_dump() for item in (asset.document_checklist or [])],
        "created_at": now,
        "updated_at": now,  # delta cursor for /assets/offline-snapshot
        "version": 1,  # OCC: initial version
    }
    
    try:
        await db.assets.insert_one(asset_doc)
    except Exception as e:
        # Rollback GridFS photos on DB insert failure
        for gid in photo_gridfs_ids:
            try:
                await delete_photo_from_gridfs(gid)
            except Exception:
                pass
        error_msg = str(e)
        if "document too large" in error_msg.lower():
            raise HTTPException(
                status_code=413,
                detail="Ukuran data terlalu besar (melebihi 16MB). Kurangi jumlah atau ukuran foto."
            )
        raise HTTPException(status_code=500, detail=f"Gagal menyimpan: {error_msg}")
    
    logger.info(f"Asset created: {asset.asset_code}")
    invalidate_asset_cache()
    # Audit actor comes from the authenticated JWT identity (can't be spoofed);
    # the X-Audit-User header is only a fallback hint.
    audit_user = _user.get("name") or _user.get("username") or request.headers.get("X-Audit-User", "unknown")
    audit_user_id = _user.get("id") or request.headers.get("X-Audit-User-Id", "")
    await log_audit("create", asset.activity_id, asset_id, asset.asset_code, asset.asset_name, audit_user, detail="Aset baru ditambahkan", nup=asset.NUP or "")
    await notify_asset_change(asset.activity_id, "asset_created", {"id": asset_id, "asset_code": asset.asset_code, "asset_name": asset.asset_name}, audit_user, user_id=audit_user_id)

    # Respons TANPA media (lihat _strip_media): klien sudah punya fotonya —
    # jangan kirim balik base64 besar. Salinan dangkal agar asset_doc asli utuh.
    response = AssetResponse(**_strip_media({**asset_doc}))
    # Cache the response for idempotent retries
    if idem_key:
        await store_idempotent_response(idem_key, response.model_dump(mode="json"), 200)
    return response

def _strip_media(asset: dict) -> dict:
    """Ganti media base64 (foto + berkas checklist) dengan array kosong sambil
    menyisipkan photo_count/document_count. Dipakai GET ?exclude_media=true dan
    respons tulis (POST/PUT/PATCH) — klien sudah memegang medianya sendiri,
    mengirim balik ratusan KB base64 hanya membuang kuota & waktu."""
    real_photos = asset.get("photos", []) or []
    asset["photo_count"] = len(asset.get("photo_gridfs_ids") or []) or len(real_photos)
    asset["photos"] = []
    asset.pop("photo", None)
    if asset.get("document_checklist"):
        asset["document_checklist"] = [
            {**item, "photos": [], "documents": [], "photo_count": len(item.get("photos", []) or []), "document_count": len(item.get("documents", []) or [])}
            for item in asset["document_checklist"]
        ]
    return asset


@assets_router.get("/assets/{asset_id}", response_model=AssetResponse)
async def get_asset(asset_id: str, exclude_media: bool = False, _user: dict = Depends(require_user)):
    """Get a single asset by ID. Use ?exclude_media=true for a lightweight response without base64 photos/documents."""
    asset = await db.assets.find_one({"id": asset_id}, {"_id": 0})
    if not asset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    if exclude_media:
        asset = _strip_media(asset)
    return AssetResponse(**asset)


@assets_router.get("/assets/{asset_id}/media")
async def get_asset_media(asset_id: str, _user: dict = Depends(require_user)):
    """Return photo thumbnails + document_checklist media for the form.
    Full-size photos are in GridFS and accessed via /assets/{id}/photos/{index}."""
    asset = await db.assets.find_one({"id": asset_id}, {
        "_id": 0, "id": 1, "photos": 1, "photo_thumbnails": 1,
        "photo_gridfs_ids": 1, "document_checklist": 1
    })
    if not asset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    
    # Return thumbnails for display; if no thumbnails yet (legacy), generate on the fly
    photo_thumbnails = asset.get("photo_thumbnails", []) or []
    photo_gridfs_ids = asset.get("photo_gridfs_ids", []) or []
    photos = asset.get("photos", []) or []
    
    # Fallback for legacy assets without thumbnails: generate from full photos
    if photos and not photo_thumbnails:
        photo_thumbnails = [generate_photo_thumbnail(p) or "" for p in photos]
    
    checklist = asset.get("document_checklist", []) or []
    # For document checklist, also return thumbnails for photos
    checklist_media = []
    for item in checklist:
        item_photos = item.get("photos", []) or []
        item_photo_thumbs = item.get("photo_thumbnails", []) or []
        if item_photos and not item_photo_thumbs:
            item_photo_thumbs = [generate_photo_thumbnail(p) or "" for p in item_photos]
        checklist_media.append({
            "name": item.get("name", ""),
            "photo_thumbnails": item_photo_thumbs,
            "photo_count": len(item_photos),
            "documents": [{"name": d.get("name", "document.pdf")} for d in (item.get("documents", []) or [])],
            "document_count": len(item.get("documents", []) or [])
        })
    
    return {
        "photo_thumbnails": photo_thumbnails,
        "photo_gridfs_ids": photo_gridfs_ids,
        "photo_count": len(photos) if not photo_gridfs_ids else len(photo_gridfs_ids),
        "document_checklist_media": checklist_media
    }


@assets_router.get("/assets/{asset_id}/checklist-full")
async def get_asset_checklist_full(asset_id: str, _user: dict = Depends(require_user)):
    """Return checklist metadata + thumbnails ONLY. Photo full bytes and PDF
    bytes are streamed via dedicated endpoints (see below) — embedding them
    inline produced multi-MB JSON responses that timed out at the proxy / hung
    the browser when an asset had several large PDFs.

    Per item we return:
      - name / checked / notes
      - photo_thumbnails: array of small base64 thumbs (already cheap)
      - photo_count: total # of photos (for `photos.length` parity in the form
        state — the actual photo bytes are loaded by the <img> tag on demand)
      - documents: array of {name, idx} (NO data field)
    """
    asset = await db.assets.find_one({"id": asset_id}, {"_id": 0, "document_checklist": 1})
    if not asset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    checklist = asset.get("document_checklist", []) or []
    normalized = []
    for item in checklist:
        item_photos = item.get("photos", []) or []
        item_thumbs = item.get("photo_thumbnails", []) or []
        # Generate thumbs on the fly for legacy items
        if item_photos and not item_thumbs:
            item_thumbs = [generate_photo_thumbnail(p) or "" for p in item_photos]
        # Trim to actual count — never return more thumbs than photos
        if len(item_thumbs) > len(item_photos):
            item_thumbs = item_thumbs[: len(item_photos)]
        normalized.append({
            "name": item.get("name", ""),
            "checked": bool(item.get("checked", False)),
            "notes": item.get("notes", ""),
            "photo_thumbnails": item_thumbs,
            "photo_count": len(item_photos),
            "documents": [
                {"name": d.get("name", "document.pdf"), "idx": idx}
                for idx, d in enumerate(item.get("documents", []) or [])
            ],
            "document_count": len(item.get("documents", []) or []),
        })
    return {"document_checklist": normalized}


# ============================================================================
# MEDIA STREAMING (photos / checklist photos / checklist PDFs)
#
# Auth posture: these are consumed by plain <img src="..."> tags and
# window.open(), neither of which can attach Authorization headers, so they
# accept EITHER the header OR a ?token=<jwt> query param via
# require_user_or_query_token. This closes the previous fully-anonymous read
# hole while keeping <img>/window.open working (see auth_utils for the URL-in-
# log tradeoff note). The frontend appends the token via lib/mediaUrl.js.
#
# Caching: responses are browser-cacheable. The frontend appends a
# ?v={asset.version} cache-buster to every media URL, so any edit (which
# bumps `version` via OCC) yields a brand-new URL and busts the cache. The
# version-based ETag additionally lets the browser revalidate cheaply (304)
# once max-age expires. X-Content-Type-Options: nosniff stops MIME sniffing.
# ============================================================================
MEDIA_CACHE_CONTROL = "private, max-age=86400"


# --- Varian PREVIEW foto (lebar dibatasi) untuk lightbox/galeri -------------
# Full-res (≤1920px, ~900KB) terlalu berat untuk dilihat cepat di jaringan
# lapangan. ?w=<lebar> menghasilkan JPEG yang diperkecil (~100-250KB) —
# di-resize SEKALI lalu di-cache di koleksi media_previews (ber-TTL), sehingga
# permintaan berikutnya (siapa pun penggunanya) langsung dari cache.
_PREVIEW_WIDTHS = {640, 1280}
_PREVIEW_TTL_DAYS = 30
_preview_index_ready = False


async def _ensure_preview_index():
    global _preview_index_ready
    if _preview_index_ready:
        return
    _preview_index_ready = True
    try:
        await db.media_previews.create_index("created_at", expireAfterSeconds=_PREVIEW_TTL_DAYS * 86400)
    except Exception:  # index sudah ada / tak bisa dibuat — cache tetap berfungsi
        pass


def _resize_jpeg(photo_bytes: bytes, max_w: int, quality: int = 80) -> bytes:
    """Perkecil JPEG ke lebar maks `max_w` (rasio dipertahankan). Sinkron &
    cepat (puluhan ms untuk sumber ≤1920px); hasil di-cache oleh pemanggil."""
    import io
    from PIL import Image as PILImage
    img = PILImage.open(io.BytesIO(photo_bytes))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    w, h = img.size
    if w > max_w:
        img = img.resize((max_w, max(1, round(h * max_w / w))), PILImage.LANCZOS)
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=quality, optimize=True, progressive=True)
    return out.getvalue()


def _media_headers(etag: str, extra: dict = None) -> dict:
    headers = {"Cache-Control": MEDIA_CACHE_CONTROL, "ETag": etag,
               "X-Content-Type-Options": "nosniff"}
    if extra:
        headers.update(extra)
    return headers


def _not_modified(request: Request, etag: str):
    """Return a 304 Response when the client already holds this exact version."""
    if request.headers.get("if-none-match", "").strip() == etag:
        return Response(status_code=304, headers=_media_headers(etag))
    return None


@assets_router.get("/assets/{asset_id}/checklist/{item_idx}/photos/{photo_idx}")
async def get_asset_checklist_photo(asset_id: str, item_idx: int, photo_idx: int, request: Request,
                                    _user: dict = Depends(require_user_or_query_token)):
    """Stream a single inline checklist photo by item & photo index."""
    asset = await db.assets.find_one({"id": asset_id}, {"_id": 0, "document_checklist": 1, "version": 1})
    if not asset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    checklist = asset.get("document_checklist", []) or []
    if item_idx < 0 or item_idx >= len(checklist):
        raise HTTPException(status_code=404, detail="Item tidak ditemukan")
    photos = (checklist[item_idx] or {}).get("photos", []) or []
    if photo_idx < 0 or photo_idx >= len(photos):
        raise HTTPException(status_code=404, detail="Foto tidak ditemukan")
    etag = f'"cl-{asset_id}-{item_idx}-p{photo_idx}-v{int(asset.get("version", 1) or 1)}"'
    not_modified = _not_modified(request, etag)
    if not_modified:
        return not_modified
    photo_b64 = photos[photo_idx]
    if not isinstance(photo_b64, str):
        raise HTTPException(status_code=500, detail="Format foto tidak valid")
    if photo_b64.startswith("data:"):
        try:
            _, data = photo_b64.split(",", 1)
        except ValueError:
            raise HTTPException(status_code=500, detail="Format foto tidak valid")
    else:
        data = photo_b64
    try:
        raw = base64.b64decode(data)
    except Exception:
        raise HTTPException(status_code=500, detail="Foto rusak")
    return Response(content=raw, media_type="image/jpeg", headers=_media_headers(etag))


@assets_router.get("/assets/{asset_id}/checklist/{item_idx}/documents/{doc_idx}")
async def get_asset_checklist_document(asset_id: str, item_idx: int, doc_idx: int, request: Request,
                                       _user: dict = Depends(require_user_or_query_token)):
    """Stream a single inline checklist PDF by item & document index."""
    asset = await db.assets.find_one({"id": asset_id}, {"_id": 0, "document_checklist": 1, "version": 1})
    if not asset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    checklist = asset.get("document_checklist", []) or []
    if item_idx < 0 or item_idx >= len(checklist):
        raise HTTPException(status_code=404, detail="Item tidak ditemukan")
    docs = (checklist[item_idx] or {}).get("documents", []) or []
    if doc_idx < 0 or doc_idx >= len(docs):
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")
    etag = f'"cl-{asset_id}-{item_idx}-d{doc_idx}-v{int(asset.get("version", 1) or 1)}"'
    not_modified = _not_modified(request, etag)
    if not_modified:
        return not_modified
    doc = docs[doc_idx] or {}
    data_url = doc.get("data", "") or ""
    if not data_url:
        raise HTTPException(status_code=404, detail="Data dokumen kosong")
    if data_url.startswith("data:"):
        try:
            _, data = data_url.split(",", 1)
        except ValueError:
            raise HTTPException(status_code=500, detail="Format dokumen tidak valid")
    else:
        data = data_url
    try:
        raw = base64.b64decode(data)
    except Exception:
        raise HTTPException(status_code=500, detail="Dokumen rusak")
    name = doc.get("name", "document.pdf") or "document.pdf"
    return Response(
        content=raw,
        media_type="application/pdf",
        headers=_media_headers(etag, {"Content-Disposition": f'inline; filename="{name}"'}),
    )


@assets_router.get("/assets/{asset_id}/photos/{photo_index}")
async def get_asset_photo_full(asset_id: str, photo_index: int, request: Request, thumb: int = 0,
                               w: int = 0,
                               _user: dict = Depends(require_user_or_query_token)):
    """Stream a full-resolution photo from GridFS or fallback to inline base64.

    ?thumb=1 returns the small per-photo thumbnail instead: the one stored in
    `photo_thumbnails` at upload time, or (legacy assets without stored
    thumbnails) one generated on the fly — same fallback /media uses, cheap
    enough per request. The form's photo strip uses this so each thumbnail
    loads progressively via <img src> and gets cached by the browser.

    ?w=640|1280 returns a width-capped PREVIEW JPEG (progressive, q80) —
    resized once then cached in media_previews, so the lightbox loads a
    ~100-250KB image instead of the full ~900KB original.
    """
    asset = await db.assets.find_one({"id": asset_id}, {
        "_id": 0, "photo_gridfs_ids": 1, "photos": 1, "photo_thumbnails": 1, "version": 1
    })
    if not asset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")

    preview_w = w if (w in _PREVIEW_WIDTHS and not thumb) else 0
    etag = (f'"{asset_id}-p{photo_index}{"-t" if thumb else ""}'
            f'{f"-w{preview_w}" if preview_w else ""}-v{int(asset.get("version", 1) or 1)}"')
    not_modified = _not_modified(request, etag)
    if not_modified:
        return not_modified

    # Preview: sajikan dari cache bila sudah pernah di-resize (kunci = etag,
    # otomatis basi saat versi aset berubah; koleksi ber-TTL).
    if preview_w:
        await _ensure_preview_index()
        cached = await db.media_previews.find_one({"_id": etag})
        if cached and cached.get("data"):
            return Response(content=bytes(cached["data"]), media_type="image/jpeg",
                            headers=_media_headers(etag))

    gridfs_ids = asset.get("photo_gridfs_ids", []) or []
    photos = asset.get("photos", []) or []

    if thumb:
        thumbnails = asset.get("photo_thumbnails", []) or []
        thumb_b64 = thumbnails[photo_index] if 0 <= photo_index < len(thumbnails) else ""
        if not thumb_b64:
            # Legacy asset without stored per-photo thumbnails: generate on the fly
            if photo_index < len(photos) and photos[photo_index]:
                thumb_b64 = generate_photo_thumbnail(photos[photo_index]) or ""
            elif photo_index < len(gridfs_ids) and gridfs_ids[photo_index]:
                photo_bytes = await get_photo_from_gridfs(gridfs_ids[photo_index])
                if photo_bytes:
                    thumb_b64 = generate_photo_thumbnail(base64.b64encode(photo_bytes).decode("utf-8")) or ""
        if thumb_b64:
            data = thumb_b64.split(",", 1)[1] if thumb_b64.startswith("data:") else thumb_b64
            try:
                return Response(content=base64.b64decode(data), media_type="image/jpeg",
                                headers=_media_headers(etag))
            except Exception:
                pass  # corrupt stored thumbnail — fall through to the full photo

    # Ambil byte foto penuh: GridFS dulu, lalu fallback inline base64
    photo_bytes = None
    if photo_index < len(gridfs_ids) and gridfs_ids[photo_index]:
        photo_bytes = await get_photo_from_gridfs(gridfs_ids[photo_index])
    if photo_bytes is None and photo_index < len(photos):
        photo_b64 = photos[photo_index]
        if photo_b64.startswith('data:'):
            _, data = photo_b64.split(',', 1)
        else:
            data = photo_b64
        try:
            photo_bytes = base64.b64decode(data)
        except Exception:
            photo_bytes = None
    if photo_bytes is None:
        raise HTTPException(status_code=404, detail="Foto tidak ditemukan")

    # Preview: resize sekali → cache → sajikan. Gagal resize → foto asli.
    if preview_w:
        try:
            preview = _resize_jpeg(photo_bytes, preview_w)
            if len(preview) < len(photo_bytes):
                try:
                    await db.media_previews.update_one(
                        {"_id": etag},
                        {"$set": {"data": preview, "created_at": datetime.now(timezone.utc)}},
                        upsert=True,
                    )
                except Exception:
                    pass  # cache best-effort — respons tetap dilayani
                return Response(content=preview, media_type="image/jpeg",
                                headers=_media_headers(etag))
        except Exception:
            pass  # bukan JPEG valid / Pillow gagal — sajikan asli

    return Response(content=photo_bytes, media_type="image/jpeg",
                    headers=_media_headers(etag))


# ============================================================================
# DOKUMEN BAST (Berita Acara Serah Terima) — satu file per aset di GridFS.
# Posture sama dengan pengesahan-dokumen (routes/pengesahan.py): upload
# ter-gate auth (admin/user), GET publik + Cache-Control agar bisa dibuka
# via window.open() yang tidak dapat membawa Authorization header.
# ============================================================================
MAX_BAST_BYTES = 10 * 1024 * 1024  # 10MB
_BAST_MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".png": "image/png", ".webp": "image/webp",
}


def _bast_ext(filename: str) -> str:
    name = (filename or "").lower()
    for ext in _BAST_MEDIA_TYPES:
        if name.endswith(ext):
            return ext
    return ""


@assets_router.post("/assets/{asset_id}/bast")
async def upload_asset_bast(
    asset_id: str,
    request: Request,
    file: UploadFile = File(...),
    user: dict = Depends(require_user),
):
    """Unggah dokumen BAST (PDF/gambar, maks 10MB) — menggantikan yang lama."""
    existing = await db.assets.find_one(
        {"id": asset_id},
        {"_id": 0, "id": 1, "activity_id": 1, "asset_code": 1, "asset_name": 1,
         "NUP": 1, "bast_file_id": 1},
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    # Kegiatan yang sudah disahkan terkunci — sama seperti mutasi aset lain
    await ensure_activity_not_sealed(existing.get("activity_id"))

    filename = (file.filename or "bast.pdf").strip() or "bast.pdf"
    ext = _bast_ext(filename)
    if not ext:
        raise HTTPException(status_code=400, detail="Dokumen BAST harus PDF atau gambar (JPG/PNG/WEBP)")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="File kosong")
    if len(file_bytes) > MAX_BAST_BYTES:
        raise HTTPException(status_code=400, detail="Ukuran dokumen BAST maksimal 10MB")
    if ext == ".pdf" and not file_bytes[:5].startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="File bukan PDF yang valid")

    # Simpan ke GridFS (pola sama dengan pengesahan-dokumen)
    from bson import ObjectId
    file_id = ObjectId()
    try:
        grid_in = fs_bucket.open_upload_stream_with_id(
            file_id,
            filename=filename,
            metadata={"content_type": _BAST_MEDIA_TYPES[ext], "size": len(file_bytes),
                      "kind": "bast", "asset_id": asset_id},
        )
        await grid_in.write(file_bytes)
        await grid_in.close()
    except Exception as e:
        logger.error(f"GridFS store BAST gagal: {e}")
        raise HTTPException(status_code=500, detail="Gagal menyimpan dokumen BAST")

    old_file_id = existing.get("bast_file_id") or ""
    # Sengaja TIDAK menaikkan `version` (OCC): unggah BAST terjadi saat form
    # edit masih terbuka — bump version akan membuat PATCH berikutnya 409.
    # Cache-busting GET memakai bast_file_id yang selalu baru per unggahan.
    result = await db.assets.update_one(
        {"id": asset_id},
        {"$set": {
            "bast_file_id": str(file_id),
            "bast_filename": filename,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    if result.matched_count == 0:
        await delete_document_from_gridfs(str(file_id))
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    if old_file_id:
        await delete_document_from_gridfs(old_file_id)

    invalidate_asset_cache()
    # Prefer the authenticated JWT identity over the spoofable header hint.
    audit_user = user.get("name") or user.get("username") or request.headers.get("X-Audit-User", "unknown")
    await log_audit(
        "update", existing.get("activity_id", ""), asset_id,
        existing.get("asset_code", ""), existing.get("asset_name", ""),
        audit_user, detail=f"Dokumen BAST diunggah: {filename}", nup=existing.get("NUP", "") or "",
    )
    logger.info(f"BAST diunggah untuk aset {asset_id}: {filename}")
    return {
        "message": "Dokumen BAST berhasil diunggah",
        "bast_file_id": str(file_id),
        "bast_filename": filename,
    }


@assets_router.get("/assets/{asset_id}/bast")
async def get_asset_bast(asset_id: str, request: Request,
                         _user: dict = Depends(require_user_or_query_token)):
    """Stream dokumen BAST aset. Dikonsumsi window.open() (tidak bisa membawa
    Authorization header) → menerima header ATAU ?token=<jwt>. ETag berbasis
    bast_file_id (unik per unggahan) → cacheable."""
    asset = await db.assets.find_one(
        {"id": asset_id}, {"_id": 0, "bast_file_id": 1, "bast_filename": 1}
    )
    if not asset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    file_id = asset.get("bast_file_id") or ""
    if not file_id:
        raise HTTPException(status_code=404, detail="Aset belum memiliki dokumen BAST")

    etag = f'"bast-{file_id}"'
    not_modified = _not_modified(request, etag)
    if not_modified:
        return not_modified

    file_bytes = await get_document_from_gridfs(file_id)
    if not file_bytes:
        raise HTTPException(status_code=404, detail="File BAST tidak tersedia")
    name = asset.get("bast_filename", "bast.pdf") or "bast.pdf"
    media_type = _BAST_MEDIA_TYPES.get(_bast_ext(name), "application/octet-stream")
    return Response(
        content=file_bytes,
        media_type=media_type,
        headers=_media_headers(etag, {"Content-Disposition": f'inline; filename="{name}"'}),
    )


@assets_router.put("/assets/{asset_id}", response_model=AssetResponse)
async def update_asset(asset_id: str, asset: AssetCreate, request: Request,
                       _user: dict = Depends(require_user)):
    """Update an existing asset. Supports OCC via If-Match header (expected version).
    Returns 409 Conflict if another user modified the asset in the meantime."""
    existing = await db.assets.find_one({"id": asset_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")

    # Kegiatan yang sudah disahkan terkunci — cek activity asal DAN tujuan
    # (bila aset dipindah antar kegiatan lewat PUT).
    await ensure_activity_not_sealed(existing.get("activity_id"))
    if asset.activity_id and asset.activity_id != existing.get("activity_id"):
        await ensure_activity_not_sealed(asset.activity_id)

    # --- Optimistic Concurrency Control (OCC) ---
    # Client sends If-Match header with the version they loaded. If server has a
    # newer version, reject with 409 so client can show conflict-resolution UI.
    if_match = request.headers.get("If-Match", "").strip().strip('"')
    current_version = int(existing.get("version", 1))
    if if_match:
        try:
            expected = int(if_match)
        except ValueError:
            expected = current_version
        if expected != current_version:
            # Return minimal current state so client can show diff / refresh
            current_clean = {k: v for k, v in existing.items() if k != "_id"}
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Aset telah diubah oleh pengguna lain. Muat ulang dan coba lagi.",
                    "current_version": current_version,
                    "your_version": expected,
                    "current": {
                        "id": current_clean.get("id"),
                        "version": current_version,
                        "asset_code": current_clean.get("asset_code"),
                        "asset_name": current_clean.get("asset_name"),
                    },
                },
            )
    
    # Check uniqueness: asset_code + NUP within same activity (exclude self)
    if (asset.asset_code != existing.get("asset_code") or 
        (asset.NUP or "") != existing.get("NUP", "")):
        dup_query = {
            "asset_code": asset.asset_code,
            "NUP": asset.NUP or "",
            "activity_id": asset.activity_id,
            "id": {"$ne": asset_id}
        }
        dup = await db.assets.find_one(dup_query)
        if dup:
            raise HTTPException(status_code=400, detail=f"Kombinasi Kode Barang '{asset.asset_code}' dan NUP '{asset.NUP}' sudah digunakan dalam kegiatan ini")
    
    # Check kode_register uniqueness within same activity (exclude self)
    if asset.kode_register and asset.activity_id:
        kr_existing = await db.assets.find_one({
            "kode_register": asset.kode_register,
            "activity_id": asset.activity_id,
            "id": {"$ne": asset_id}
        })
        if kr_existing:
            raise HTTPException(status_code=400, detail=f"Kode Register '{asset.kode_register}' sudah digunakan dalam kegiatan ini")
    
    photos = asset.photos or []
    if asset.photo and not photos:
        photos = [asset.photo]
    
    # Generate thumbnail from selected cover photo + GridFS storage
    thumbnail = existing.get("thumbnail")
    gallery_thumbnail = existing.get("gallery_thumbnail")
    old_photos = existing.get("photos", [])
    cover_idx = min(asset.thumbnail_index or 0, len(photos) - 1) if photos else 0
    
    photo_gridfs_ids = existing.get("photo_gridfs_ids", [])
    photo_thumbnails = existing.get("photo_thumbnails", [])
    old_gridfs_for_rollback = list(photo_gridfs_ids)  # pre-existing IDs (keep if new upload fails)

    if photos and (photos != old_photos or cover_idx != existing.get("thumbnail_index", 0)):
        thumbnail = create_thumbnail(photos[cover_idx])
        gallery_thumbnail = create_gallery_thumbnail(photos[cover_idx])
        # Store new photos in GridFS + generate per-photo thumbnails (atomic rollback on error)
        result = await process_photos_for_storage(photos)
        photo_gridfs_ids = result["gridfs_ids"]
        photo_thumbnails = result["thumbnails"]
    elif not photos:
        thumbnail = None
        gallery_thumbnail = None
        photo_gridfs_ids = []
        photo_thumbnails = []

    update_data = {
        **asset.model_dump(),
        "photos": photos,
        "photo_gridfs_ids": photo_gridfs_ids,
        "photo_thumbnails": photo_thumbnails,
        "photo": photos[cover_idx] if photos else None,
        "thumbnail": thumbnail,
        "gallery_thumbnail": gallery_thumbnail,
        "thumbnail_index": cover_idx,
        "document_checklist": [item.model_dump() for item in (asset.document_checklist or [])],
        "created_at": existing["created_at"],
        # Stamped on every write so the offline snapshot delta sync
        # (GET /assets/offline-snapshot?since=...) picks this change up.
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    try:
        # Atomic CAS update: only succeeds if version still matches.
        # Support legacy docs without version field: when current_version==1,
        # also match docs where version is missing ($exists=False).
        cas_filter = _build_cas_filter(asset_id, current_version)
        result = await db.assets.update_one(
            cas_filter,
            {"$set": update_data, "$inc": {"version": 1}}
        )
        if result.matched_count == 0:
            # Someone else bumped version between our read and write — 409
            fresh = await db.assets.find_one({"id": asset_id}, {"_id": 0, "version": 1, "asset_code": 1, "asset_name": 1})
            # Rollback GridFS uploads that were freshly created for this request
            if photo_gridfs_ids != old_gridfs_for_rollback:
                for gid in photo_gridfs_ids:
                    if gid and gid not in old_gridfs_for_rollback:
                        try:
                            await delete_photo_from_gridfs(gid)
                        except Exception:
                            pass
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Aset telah diubah oleh pengguna lain (race condition). Muat ulang dan coba lagi.",
                    "current_version": (fresh or {}).get("version", current_version + 1),
                    "your_version": current_version,
                    "current": fresh or {},
                },
            )
    except HTTPException:
        raise
    except Exception as e:
        # Rollback new GridFS uploads on write error
        if photo_gridfs_ids != old_gridfs_for_rollback:
            for gid in photo_gridfs_ids:
                if gid and gid not in old_gridfs_for_rollback:
                    try:
                        await delete_photo_from_gridfs(gid)
                    except Exception:
                        pass
        error_msg = str(e)
        if "document too large" in error_msg.lower():
            raise HTTPException(
                status_code=413,
                detail="Ukuran data terlalu besar (melebihi 16MB). Kurangi jumlah atau ukuran foto."
            )
        raise HTTPException(status_code=500, detail=f"Gagal menyimpan: {error_msg}")

    # After successful update: delete GridFS IDs that were replaced (old no-longer-referenced)
    if photo_gridfs_ids != old_gridfs_for_rollback:
        new_set = set(x for x in photo_gridfs_ids if x)
        for old_gid in old_gridfs_for_rollback:
            if old_gid and old_gid not in new_set:
                try:
                    await delete_photo_from_gridfs(old_gid)
                except Exception:
                    pass

    logger.info(f"Asset updated: {asset.asset_code}")
    invalidate_asset_cache()
    audit_user = _user.get("name") or _user.get("username") or request.headers.get("X-Audit-User", "unknown")
    audit_user_id = _user.get("id") or request.headers.get("X-Audit-User-Id", "")
    changes = compute_changes(existing, asset.model_dump())
    if changes:
        await log_audit("update", asset.activity_id, asset_id, asset.asset_code, asset.asset_name, audit_user, changes=changes, nup=asset.NUP or "")
    # Respons TANPA media: klien sudah memegang foto/dokumennya sendiri —
    # mengirim balik base64 (bisa >1MB) di tiap simpan memboroskan kuota HP.
    updated_asset = _strip_media(await db.assets.find_one({"id": asset_id}, {"_id": 0}))
    # Real-time notification
    await notify_asset_change(asset.activity_id, "asset_updated", {"id": asset_id, "asset_code": asset.asset_code, "asset_name": asset.asset_name}, audit_user, user_id=audit_user_id)
    return AssetResponse(**updated_asset)


# Fields that can be patched individually
PATCHABLE_FIELDS = {
    "asset_code", "NUP", "asset_name", "category", "brand", "model",
    "kode_register", "serial_number", "purchase_date", "purchase_price",
    "location", "eselon1", "eselon2", "user", "condition", "status",
    "pengguna_melekat_ke", "pengguna_jabatan", "operasional_jenis", "nomor_bast",
    "nomor_spm", "perolehan_dari_nama", "nomor_kontrak",
    "nomor_bukti_perolehan", "supplier", "notes",
    "photos", "photo", "thumbnail_index", "document_checklist",
    "stiker_status", "stiker_ukuran", "stiker_photo_index",
    "inventory_status", "klasifikasi_tidak_ditemukan", "sub_klasifikasi",
    "uraian_tidak_ditemukan", "tindak_lanjut",
    "koordinat_latitude", "koordinat_longitude", "kronologis",
    "keterangan_berlebih", "asal_usul_berlebih",
    "nomor_perkara", "pihak_bersengketa", "keterangan_sengketa",
    "activity_id",
}

@assets_router.patch("/assets/{asset_id}")
async def patch_asset(asset_id: str, request: Request, _user: dict = Depends(require_user)):
    """Partial update — only update the fields provided in the body.
    Supports OCC via If-Match header (expected version) and Idempotency-Key header."""
    # --- Idempotency: replay cached response if same key seen recently ---
    idem_key = request.headers.get("Idempotency-Key", "")
    if idem_key:
        cached = await get_idempotent_response(idem_key)
        if cached and cached.get("response"):
            logger.info(f"Idempotent PATCH replay for key {idem_key[:8]}...")
            return AssetResponse(**cached["response"])
        _idem = await reserve_idempotency_key(idem_key)
        if _idem == "done":
            cached = await get_idempotent_response(idem_key)
            if cached and cached.get("response"):
                return AssetResponse(**cached["response"])
        elif _idem == "pending":
            raise HTTPException(status_code=409, detail="Permintaan dengan kunci idempotensi ini sedang diproses, coba lagi sebentar")

    body = await request.json()
    existing = await db.assets.find_one({"id": asset_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")

    # Kegiatan yang sudah disahkan terkunci — cek activity asal DAN tujuan
    await ensure_activity_not_sealed(existing.get("activity_id"))
    body_activity_id = body.get("activity_id")
    if body_activity_id and body_activity_id != existing.get("activity_id"):
        await ensure_activity_not_sealed(body_activity_id)

    # --- Optimistic Concurrency Control ---
    if_match = request.headers.get("If-Match", "").strip().strip('"')
    current_version = int(existing.get("version", 1))
    if if_match:
        try:
            expected = int(if_match)
        except ValueError:
            expected = current_version
        if expected != current_version:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Aset telah diubah oleh pengguna lain. Muat ulang dan coba lagi.",
                    "current_version": current_version,
                    "your_version": expected,
                    "current": {
                        "id": existing.get("id"),
                        "version": current_version,
                        "asset_code": existing.get("asset_code"),
                        "asset_name": existing.get("asset_name"),
                    },
                },
            )

    # Filter to patchable fields only
    update_data = {k: v for k, v in body.items() if k in PATCHABLE_FIELDS}
    has_photo_ops = "photo_ops" in body

    if not update_data and not has_photo_ops:
        raise HTTPException(status_code=400, detail="Tidak ada field yang diubah")

    # Validate uniqueness: asset_code + NUP (only if either changed)
    new_code = update_data.get("asset_code", existing["asset_code"])
    new_nup = update_data.get("NUP", existing.get("NUP", ""))
    if new_code != existing.get("asset_code") or new_nup != existing.get("NUP", ""):
        activity_id = update_data.get("activity_id", existing.get("activity_id"))
        dup = await db.assets.find_one({
            "asset_code": new_code, "NUP": new_nup,
            "activity_id": activity_id, "id": {"$ne": asset_id}
        })
        if dup:
            raise HTTPException(status_code=400, detail=f"Kombinasi Kode Barang '{new_code}' dan NUP '{new_nup}' sudah digunakan dalam kegiatan ini")

    # Validate kode_register uniqueness (only if changed)
    if "kode_register" in update_data and update_data["kode_register"]:
        activity_id = update_data.get("activity_id", existing.get("activity_id"))
        kr_dup = await db.assets.find_one({
            "kode_register": update_data["kode_register"],
            "activity_id": activity_id, "id": {"$ne": asset_id}
        })
        if kr_dup:
            raise HTTPException(status_code=400, detail=f"Kode Register '{update_data['kode_register']}' sudah digunakan dalam kegiatan ini")

    # Track GridFS IDs that we create in this request for rollback on failure
    newly_uploaded_gridfs = []

    # Handle photo_ops: server-side photo manipulation without frontend needing full photos
    if has_photo_ops:
        ops = body["photo_ops"]
        keep_indices = ops.get("keep", [])
        new_photos_b64 = ops.get("add", [])
        new_thumb_idx = ops.get("thumbnail_index", 0)

        old_photos = existing.get("photos", []) or []
        old_gridfs_ids = existing.get("photo_gridfs_ids", []) or []
        old_thumbnails = existing.get("photo_thumbnails", []) or []

        # Build new arrays from kept photos + new photos
        final_photos = []
        final_gridfs_ids = []
        final_thumbnails = []

        for idx in keep_indices:
            if 0 <= idx < len(old_photos):
                final_photos.append(old_photos[idx])
            if 0 <= idx < len(old_gridfs_ids):
                final_gridfs_ids.append(old_gridfs_ids[idx])
            elif 0 <= idx < len(old_photos):
                final_gridfs_ids.append("")
            if 0 <= idx < len(old_thumbnails):
                final_thumbnails.append(old_thumbnails[idx])
            elif 0 <= idx < len(old_photos):
                final_thumbnails.append(generate_photo_thumbnail(old_photos[idx]) or "")

        # Process new photos: store in GridFS + generate thumbnails (atomic rollback if one fails)
        try:
            for photo_b64 in new_photos_b64:
                final_photos.append(photo_b64)
                gid = await store_photo_to_gridfs(photo_b64)
                newly_uploaded_gridfs.append(gid)
                final_gridfs_ids.append(gid)
                thumb = generate_photo_thumbnail(photo_b64)
                final_thumbnails.append(thumb or "")
        except Exception as e:
            # Rollback newly uploaded blobs
            for gid in newly_uploaded_gridfs:
                try:
                    await delete_photo_from_gridfs(gid)
                except Exception:
                    pass
            raise HTTPException(status_code=500, detail=f"Gagal menyimpan foto: {e}")

        # Delete removed photos from GridFS (only AFTER successful uploads, to allow rollback)
        removed_indices = set(range(len(old_gridfs_ids))) - set(keep_indices)

        cover_idx = min(new_thumb_idx, len(final_photos) - 1) if final_photos else 0
        update_data["photos"] = final_photos
        update_data["photo_gridfs_ids"] = final_gridfs_ids
        update_data["photo_thumbnails"] = final_thumbnails
        update_data["photo"] = final_photos[cover_idx] if final_photos else None
        update_data["thumbnail_index"] = cover_idx
        if final_photos:
            update_data["thumbnail"] = create_thumbnail(final_photos[cover_idx])
            update_data["gallery_thumbnail"] = create_gallery_thumbnail(final_photos[cover_idx])
        else:
            update_data["thumbnail"] = None
            update_data["gallery_thumbnail"] = None
        # Defer deletion of removed indices till after DB update succeeds
        update_data["__rollback_old_removed_gids__"] = [
            old_gridfs_ids[i] for i in removed_indices if 0 <= i < len(old_gridfs_ids) and old_gridfs_ids[i]
        ]

    # Handle legacy photos field (backward compat for full-photo PATCH)
    elif "photos" in update_data:
        photos = update_data["photos"] or []
        cover_idx = min(update_data.get("thumbnail_index", existing.get("thumbnail_index", 0)), len(photos) - 1) if photos else 0
        old_photos = existing.get("photos", [])
        if photos and (photos != old_photos or cover_idx != existing.get("thumbnail_index", 0)):
            update_data["thumbnail"] = create_thumbnail(photos[cover_idx])
            update_data["gallery_thumbnail"] = create_gallery_thumbnail(photos[cover_idx])
            # Atomic rollback inside process_photos_for_storage
            result = await process_photos_for_storage(photos)
            newly_uploaded_gridfs.extend(result["gridfs_ids"])
            update_data["photo_gridfs_ids"] = result["gridfs_ids"]
            update_data["photo_thumbnails"] = result["thumbnails"]
        elif not photos:
            update_data["thumbnail"] = None
            update_data["gallery_thumbnail"] = None
            update_data["photo_gridfs_ids"] = []
            update_data["photo_thumbnails"] = []
        update_data["photo"] = photos[cover_idx] if photos else None
        update_data["thumbnail_index"] = cover_idx

    # Handle cover-only change: user just picked a different thumbnail without
    # adding/removing any photo. Previously the backend stored the new index
    # but never regenerated `thumbnail` / `gallery_thumbnail` / `photo`, so
    # the list/gallery cover never updated — matching the user-reported bug
    # "thumbnails tidak berganti sesuai dengan cover yang dipilih".
    elif "thumbnail_index" in update_data:
        existing_photos = existing.get("photos", []) or []
        existing_gridfs = existing.get("photo_gridfs_ids", []) or []
        n_photos = max(len(existing_photos), len(existing_gridfs))
        if n_photos == 0:
            # No photos → thumbnail_index is meaningless, just clear
            update_data["thumbnail_index"] = 0
        else:
            new_idx = int(update_data.get("thumbnail_index", 0) or 0)
            new_idx = max(0, min(new_idx, n_photos - 1))
            update_data["thumbnail_index"] = new_idx
            # Prefer a full-res photo source if we still have one (legacy docs),
            # otherwise fall back to streaming the chosen GridFS blob and
            # re-rendering the composite thumbnails from its bytes.
            cover_b64 = None
            if new_idx < len(existing_photos) and existing_photos[new_idx]:
                cover_b64 = existing_photos[new_idx]
            elif new_idx < len(existing_gridfs) and existing_gridfs[new_idx]:
                try:
                    import base64
                    from bson import ObjectId
                    gid = existing_gridfs[new_idx]
                    stream = await fs_bucket.open_download_stream(ObjectId(gid) if ObjectId.is_valid(str(gid)) else gid)
                    raw = await stream.read()
                    cover_b64 = "data:image/jpeg;base64," + base64.b64encode(raw).decode("ascii")
                except Exception as e:
                    logger.warning(f"thumbnail_index cover regen: GridFS read failed for asset {asset_id} idx {new_idx}: {e}")
            if cover_b64:
                update_data["thumbnail"] = create_thumbnail(cover_b64)
                update_data["gallery_thumbnail"] = create_gallery_thumbnail(cover_b64)
                update_data["photo"] = cover_b64

    # Handle document_checklist → normalize dicts. Frontend uses sentinels to
    # signal "preserve existing item at this index" without re-shipping the
    # base64 bytes; we resolve those sentinels against the existing doc here.
    if "document_checklist" in update_data:
        existing_checklist = existing.get("document_checklist", []) or []
        # Consume each existing item at most once, in order, so duplicate or
        # empty checklist-item names can't cross-wire / lose photos on edit.
        existing_by_name = {}
        for _it in existing_checklist:
            existing_by_name.setdefault((_it.get("name") or ""), deque()).append(_it)
        new_checklist = []
        for item in (update_data["document_checklist"] or []):
            name = item.get("name", "") or ""
            _q = existing_by_name.get(name)
            orig_item = _q.popleft() if _q else {}
            orig_photos = orig_item.get("photos", []) or []
            orig_docs = orig_item.get("documents", []) or []
            orig_thumbs = orig_item.get("photo_thumbnails", []) or []

            # Resolve photo sentinels: "__existing__:<idx>" → orig_photos[idx]
            resolved_photos = []
            resolved_thumbs = []
            for p in (item.get("photos", []) or []):
                if isinstance(p, str) and p.startswith("__existing__:"):
                    try:
                        idx = int(p.split(":", 1)[1])
                    except (ValueError, IndexError):
                        continue
                    if 0 <= idx < len(orig_photos) and orig_photos[idx]:
                        resolved_photos.append(orig_photos[idx])
                        if idx < len(orig_thumbs):
                            resolved_thumbs.append(orig_thumbs[idx])
                else:
                    resolved_photos.append(p)
                    # Thumbnail will be regenerated below for new uploads
                    resolved_thumbs.append("")

            # Resolve doc sentinels: doc with data == "__existing__:<idx>"
            resolved_docs = []
            for d in (item.get("documents", []) or []):
                if not isinstance(d, dict):
                    continue
                data = d.get("data", "") or ""
                if isinstance(data, str) and data.startswith("__existing__:"):
                    try:
                        idx = int(data.split(":", 1)[1])
                    except (ValueError, IndexError):
                        continue
                    if 0 <= idx < len(orig_docs):
                        resolved_docs.append(orig_docs[idx])
                else:
                    resolved_docs.append({"name": d.get("name", "document.pdf"), "data": data})

            # Regenerate any missing photo thumbnails for newly added photos
            final_thumbs = []
            for i, ph in enumerate(resolved_photos):
                t = resolved_thumbs[i] if i < len(resolved_thumbs) else ""
                if not t and ph:
                    t = generate_photo_thumbnail(ph) or ""
                final_thumbs.append(t)

            new_checklist.append({
                "name": name,
                "checked": bool(item.get("checked", False)),
                "notes": item.get("notes", ""),
                "photos": resolved_photos,
                "photo_thumbnails": final_thumbs,
                "documents": resolved_docs,
            })
        update_data["document_checklist"] = new_checklist

    # Extract deferred rollback info before DB write
    deferred_delete_gids = update_data.pop("__rollback_old_removed_gids__", [])

    # Stamped on every write so the offline snapshot delta sync
    # (GET /assets/offline-snapshot?since=...) picks this change up.
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()

    try:
        # Atomic CAS: only succeeds if version is still what client saw.
        # Support legacy docs without version field.
        cas_filter = _build_cas_filter(asset_id, current_version)
        result = await db.assets.update_one(
            cas_filter,
            {"$set": update_data, "$inc": {"version": 1}},
        )
        if result.matched_count == 0:
            # 409 — rollback newly uploaded GridFS blobs
            for gid in newly_uploaded_gridfs:
                try:
                    await delete_photo_from_gridfs(gid)
                except Exception:
                    pass
            fresh = await db.assets.find_one({"id": asset_id}, {"_id": 0, "version": 1, "asset_code": 1, "asset_name": 1})
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Aset telah diubah oleh pengguna lain. Muat ulang dan coba lagi.",
                    "current_version": (fresh or {}).get("version", current_version + 1),
                    "your_version": current_version,
                    "current": fresh or {},
                },
            )
    except HTTPException:
        raise
    except Exception as e:
        # Rollback newly uploaded blobs on DB error
        for gid in newly_uploaded_gridfs:
            try:
                await delete_photo_from_gridfs(gid)
            except Exception:
                pass
        error_msg = str(e)
        if "document too large" in error_msg.lower():
            raise HTTPException(status_code=413, detail="Ukuran data terlalu besar (melebihi 16MB). Kurangi jumlah atau ukuran foto.")
        raise HTTPException(status_code=500, detail=f"Gagal menyimpan: {error_msg}")

    # DB write succeeded — now safe to delete orphaned old GridFS blobs
    for gid in deferred_delete_gids:
        try:
            await delete_photo_from_gridfs(gid)
        except Exception:
            pass

    logger.info(f"Asset patched: {asset_id} — fields: {list(update_data.keys())}")
    invalidate_asset_cache()
    audit_user = _user.get("name") or _user.get("username") or request.headers.get("X-Audit-User", "unknown")
    audit_user_id = _user.get("id") or request.headers.get("X-Audit-User-Id", "")
    merged = {**existing, **update_data}
    changes = compute_changes(existing, merged)
    if changes:
        await log_audit(
            "update", merged.get("activity_id", ""), asset_id,
            merged.get("asset_code", ""), merged.get("asset_name", ""),
            audit_user, changes=changes, nup=merged.get("NUP", "")
        )
    # Respons TANPA media (lihat _strip_media) — juga memperkecil dokumen
    # idempotency yang disimpan di bawah.
    updated_asset = _strip_media(await db.assets.find_one({"id": asset_id}, {"_id": 0}))
    await notify_asset_change(
        merged.get("activity_id", ""), "asset_updated",
        {"id": asset_id, "asset_code": merged.get("asset_code", ""), "asset_name": merged.get("asset_name", "")},
        audit_user, user_id=audit_user_id
    )
    response = AssetResponse(**updated_asset)
    if idem_key:
        await store_idempotent_response(idem_key, response.model_dump(mode="json"), 200)
    return response

@assets_router.delete("/assets/{asset_id}")
async def delete_asset(asset_id: str, request: Request, _admin: dict = Depends(require_admin)):
    """Delete an asset (admin only)"""
    asset_doc = await db.assets.find_one({"id": asset_id}, {"_id": 0})
    if not asset_doc:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")

    # Kegiatan yang sudah disahkan terkunci — tolak penghapusan aset (423)
    await ensure_activity_not_sealed(asset_doc.get("activity_id"))

    result = await db.assets.delete_one({"id": asset_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")

    # Clean up GridFS blobs the doc referenced so they don't leak as orphans.
    # Best-effort: a blob-delete failure must NOT block the (already-done) doc
    # delete — just log it.
    blob_ids = await _collect_asset_blob_ids(asset_doc)
    for gid in blob_ids["photos"]:
        try:
            await delete_photo_from_gridfs(gid)
        except Exception as e:
            logger.warning(f"delete_asset: gagal hapus foto GridFS {gid}: {e}")
    for gid in blob_ids["documents"]:
        try:
            await delete_document_from_gridfs(gid)
        except Exception as e:
            logger.warning(f"delete_asset: gagal hapus dokumen GridFS {gid}: {e}")

    logger.info(f"Asset deleted: {asset_id}")
    invalidate_asset_cache()
    audit_user = _admin.get("name") or _admin.get("username") or request.headers.get("X-Audit-User", "unknown")
    audit_user_id = _admin.get("id") or request.headers.get("X-Audit-User-Id", "")
    await log_audit("delete", asset_doc.get("activity_id", ""), asset_id, asset_doc.get("asset_code", ""), asset_doc.get("asset_name", ""), audit_user, detail="Aset dihapus", nup=asset_doc.get("NUP", ""))
    # Real-time notification
    await notify_asset_change(asset_doc.get("activity_id", ""), "asset_deleted", {"id": asset_id, "asset_code": asset_doc.get("asset_code", "")}, audit_user, user_id=audit_user_id)
    
    return {"message": "Aset berhasil dihapus"}


@assets_router.post("/assets/migrate-gridfs")
async def migrate_photos_to_gridfs(_admin: dict = Depends(require_admin)):
    """Migrate existing inline base64 photos to GridFS + generate per-photo thumbnails.
    Safe to run multiple times — skips assets that already have gridfs_ids."""
    cursor = db.assets.find(
        {"photos": {"$exists": True, "$ne": []}, "$or": [{"photo_gridfs_ids": {"$exists": False}}, {"photo_gridfs_ids": []}]},
        {"_id": 0, "id": 1, "photos": 1, "document_checklist": 1}
    )
    migrated = 0
    async for asset in cursor:
        try:
            photos = asset.get("photos", []) or []
            if not photos:
                continue
            result = await process_photos_for_storage(photos)
            update = {
                "photo_gridfs_ids": result["gridfs_ids"],
                "photo_thumbnails": result["thumbnails"],
            }
            # Also migrate document_checklist photos
            checklist = asset.get("document_checklist", []) or []
            updated_cl = []
            for item in checklist:
                item_photos = item.get("photos", []) or []
                if item_photos:
                    item_thumbs = [generate_photo_thumbnail(p) or "" for p in item_photos]
                    updated_cl.append({**item, "photo_thumbnails": item_thumbs})
                else:
                    updated_cl.append(item)
            if any(it.get("photo_thumbnails") for it in updated_cl):
                update["document_checklist"] = updated_cl
            await db.assets.update_one({"id": asset["id"]}, {"$set": update})
            migrated += 1
        except Exception as e:
            logger.error(f"Migration error for asset {asset.get('id')}: {e}")
    return {"migrated": migrated, "message": f"Berhasil migrasi {migrated} aset ke GridFS"}

