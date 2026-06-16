"""
Batch operations & row locking routes.
Extracted from assets.py for clean separation of concerns.
Provides: lock/unlock/heartbeat, batch-update, groups, all-ids
"""
import io
import uuid
import base64
import logging
from datetime import datetime, timezone, timedelta
from typing import List
from fastapi import APIRouter, HTTPException, Request, Header, Depends
from pydantic import BaseModel
from pymongo import UpdateOne, ReturnDocument
from pymongo.errors import DuplicateKeyError

from auth_utils import require_user
from db import db
from shared_utils import (
    invalidate_asset_cache, log_audit,
    create_thumbnail, create_gallery_thumbnail,
)
from routes.websocket import notify_asset_change
from routes.media import auto_compress_image

logger = logging.getLogger(__name__)
batch_router = APIRouter()

# --- Row Locking for Concurrent Editing (Persistent via MongoDB) ---
LOCK_TTL_SECONDS = 300  # 5 minutes

class LockRequest(BaseModel):
    asset_id: str

@batch_router.post("/assets/lock")
async def lock_asset(data: LockRequest, request: Request, x_user_id: str = Header(None), x_user_name: str = Header(None), x_session_id: str = Header(None)):
    """Lock an asset row for editing. Atomic lock acquisition via find_one_and_update + insert fallback.
    Race-free: guaranteed only one user can hold the lock at any time."""
    asset_id = data.asset_id
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=LOCK_TTL_SECONDS)
    session_id = x_session_id or "unknown-session"

    lock_doc = {
        "asset_id": asset_id,
        "user_id": x_user_id or "unknown",
        "user_name": x_user_name or "Unknown",
        "session_id": session_id,
        "locked_at": now.isoformat(),
        "expires_at": expires_at,
    }

    # STEP 1: Try to acquire the lock atomically IF it's expired OR held by same session.
    # This single DB call prevents the read-then-write race condition.
    result = await db.row_locks.find_one_and_update(
        {
            "asset_id": asset_id,
            "$or": [
                {"expires_at": {"$lte": now}},      # expired lock — steal it
                {"session_id": session_id},          # our own session — renew it
            ],
        },
        {"$set": lock_doc},
        return_document=ReturnDocument.AFTER,
    )
    if result is not None:
        return {"locked": True}

    # STEP 2: No existing lock found (or existing one belongs to another active user).
    # Try to insert fresh lock — unique index on asset_id ensures atomicity.
    try:
        await db.row_locks.insert_one(lock_doc)
        return {"locked": True}
    except DuplicateKeyError:
        # Another user got the lock first (or still active). Return who holds it.
        existing = await db.row_locks.find_one({"asset_id": asset_id})
        if not existing:
            # Rare race: lock expired between steps — retry once
            try:
                await db.row_locks.insert_one(lock_doc)
                return {"locked": True}
            except DuplicateKeyError:
                existing = await db.row_locks.find_one({"asset_id": asset_id})
        return {
            "locked": False,
            "locked_by": (existing or {}).get("user_name", "Unknown"),
            "locked_by_id": (existing or {}).get("user_id", ""),
        }

@batch_router.post("/assets/heartbeat")
async def heartbeat_lock(data: LockRequest, request: Request, x_user_id: str = Header(None), x_user_name: str = Header(None), x_session_id: str = Header(None)):
    """Renew lock TTL (heartbeat). Call every ~15s while editing."""
    asset_id = data.asset_id
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=LOCK_TTL_SECONDS)
    session_id = x_session_id or "unknown-session"

    result = await db.row_locks.update_one(
        {"asset_id": asset_id, "session_id": session_id},
        {"$set": {"expires_at": expires_at}}
    )
    return {"renewed": result.modified_count > 0}

@batch_router.post("/assets/unlock")
async def unlock_asset(data: LockRequest, request: Request, x_user_id: str = Header(None), x_session_id: str = Header(None)):
    """Release the lock on an asset row."""
    asset_id = data.asset_id
    session_id = x_session_id or "unknown-session"
    await db.row_locks.delete_one({"asset_id": asset_id, "session_id": session_id})
    return {"unlocked": True}

@batch_router.get("/assets/locks")
async def get_all_locks(request: Request, activity_id: str = ""):
    """Get currently active (non-expired) locks. Optional activity_id filter for efficient per-activity polling.
    Also filters out expired locks defensively even if TTL index hasn't purged yet."""
    now = datetime.now(timezone.utc)
    locks = {}
    query = {"expires_at": {"$gt": now}}
    if activity_id:
        # Join with assets to filter by activity. For perf, get asset IDs for this activity first
        # (limit scan size). Fall back to returning all locks if activity scope is too large.
        asset_ids_cursor = db.assets.find({"activity_id": activity_id}, {"_id": 0, "id": 1}).limit(50000)
        asset_ids = [d["id"] async for d in asset_ids_cursor]
        if asset_ids:
            query["asset_id"] = {"$in": asset_ids}
        else:
            return {"locks": {}}
    cursor = db.row_locks.find(query, {"_id": 0, "asset_id": 1, "user_name": 1, "user_id": 1, "session_id": 1})
    async for doc in cursor:
        locks[doc["asset_id"]] = {
            "user_name": doc["user_name"],
            "user_id": doc["user_id"],
            "session_id": doc.get("session_id", ""),
        }
    return {"locks": locks}

# --- Batch Update ---
class BatchUpdateRequest(BaseModel):
    asset_ids: List[str]
    updates: dict  # Fields to update: category, location, condition, inventory_status, stiker_status, stiker_ukuran, eselon1, eselon2

BATCH_ALLOWED_FIELDS = {
    "category", "location", "condition", "inventory_status",
    "stiker_status", "stiker_ukuran", "eselon1", "eselon2",
    "nomor_spm", "perolehan_dari_nama", "nomor_kontrak",
    "nomor_bukti_perolehan", "supplier", "purchase_date", "purchase_price",
    "koordinat_latitude", "koordinat_longitude", "brand", "model",
}

# Fields that need special handling (not simple $set)
BATCH_SPECIAL_FIELDS = {"batch_photo", "document_checklist_items"}

@batch_router.put("/assets/batch-update")
async def batch_update_assets(data: BatchUpdateRequest, request: Request, x_user_id: str = Header(None), x_user_name: str = Header(None), x_session_id: str = Header(None), _user: dict = Depends(require_user)):
    """Batch update multiple assets with the same field values."""
    if not data.asset_ids:
        raise HTTPException(status_code=400, detail="Tidak ada aset yang dipilih")
    if not data.updates:
        raise HTTPException(status_code=400, detail="Tidak ada perubahan yang dikirim")

    # Filter only allowed fields
    clean_updates = {k: v for k, v in data.updates.items() if k in BATCH_ALLOWED_FIELDS and v is not None}

    # Handle __clear__ sentinel: convert to empty string for DB
    for k, v in list(clean_updates.items()):
        if v == "__clear__":
            clean_updates[k] = ""

    # Handle batch photo (add 1 photo to all selected assets)
    batch_photo = data.updates.get("batch_photo")
    has_photo = batch_photo and isinstance(batch_photo, str) and batch_photo.startswith("data:")

    # Handle clear photos (remove all photos from selected assets)
    should_clear_photos = data.updates.get("clear_photos") is True

    # Handle clear document checklist
    should_clear_doc_checklist = data.updates.get("clear_document_checklist") is True

    # Handle document checklist items
    doc_checklist_items = data.updates.get("document_checklist_items")
    has_doc_checklist = doc_checklist_items and isinstance(doc_checklist_items, list) and len(doc_checklist_items) > 0

    if not clean_updates and not has_photo and not has_doc_checklist and not should_clear_photos and not should_clear_doc_checklist:
        raise HTTPException(status_code=400, detail="Tidak ada field valid untuk diupdate")

    # Skip lock check for large batches (own batch action) — only check for small batches
    session_id = x_session_id or "unknown-session"
    if len(data.asset_ids) <= 50:
        locked_assets = []
        cursor = db.row_locks.find({"asset_id": {"$in": data.asset_ids}, "session_id": {"$ne": session_id}}, {"_id": 0, "asset_id": 1, "user_name": 1})
        async for lock in cursor:
            locked_assets.append(f"{lock['asset_id']} (oleh {lock['user_name']})")
        if locked_assets:
            raise HTTPException(status_code=409, detail=f"Aset terkunci: {', '.join(locked_assets[:5])}")

    now_str = datetime.now(timezone.utc).isoformat()
    clean_updates["updated_at"] = now_str
    updated_count = len(data.asset_ids)

    # 1. Simple field updates — single update_many (fast)
    if len(clean_updates) > 1:
        await db.assets.update_many(
            {"id": {"$in": data.asset_ids}},
            {"$set": clean_updates}
        )

    # 2. Batch photo — auto-compress ONCE, then distribute to all assets
    if has_photo:
        # Compress photo before distributing (Tinify first, Pillow fallback)
        compressed_photo, compress_method, orig_size, comp_size = await auto_compress_image(batch_photo)
        if compress_method != "none":
            logger.info(f"Batch photo compressed via {compress_method}: {orig_size/1024:.0f}KB → {comp_size/1024:.0f}KB ({(1-comp_size/orig_size)*100:.0f}% reduction)")

        thumbnail = create_thumbnail(compressed_photo)
        gallery_thumbnail = create_gallery_thumbnail(compressed_photo)
        CHUNK = 50

        async def update_photo_chunk(chunk_ids):
            ops = []
            for aid in chunk_ids:
                asset = await db.assets.find_one({"id": aid}, {"_id": 0, "photos": 1})
                current_photos = asset.get("photos", []) if asset else []
                new_photos = current_photos + [compressed_photo]
                update_fields = {
                    "photos": new_photos,
                    "photo": new_photos[0] if new_photos else None,
                    "updated_at": now_str,
                }
                if len(current_photos) == 0:
                    update_fields["thumbnail"] = thumbnail
                    update_fields["gallery_thumbnail"] = gallery_thumbnail
                ops.append(UpdateOne({"id": aid}, {"$set": update_fields}))
            if ops:
                await db.assets.bulk_write(ops, ordered=False)

        chunks = [data.asset_ids[i:i+CHUNK] for i in range(0, len(data.asset_ids), CHUNK)]
        for chunk in chunks:
            await update_photo_chunk(chunk)

    # 3. Document checklist — process in parallel chunks
    if has_doc_checklist:
        CHUNK = 50

        async def update_doc_chunk(chunk_ids):
            ops = []
            for aid in chunk_ids:
                asset = await db.assets.find_one({"id": aid}, {"_id": 0, "document_checklist": 1})
                existing = asset.get("document_checklist", []) if asset else []
                existing_names = {item.get("name", ""): idx for idx, item in enumerate(existing)}

                updated_checklist = list(existing)
                for new_item in doc_checklist_items:
                    item_name = new_item.get("name", "")
                    item_checked = new_item.get("checked", False)
                    item_photos = new_item.get("photos", [])
                    item_documents = new_item.get("documents", [])

                    if item_name in existing_names:
                        idx = existing_names[item_name]
                        updated_checklist[idx]["checked"] = item_checked
                        if item_photos:
                            cur_photos = updated_checklist[idx].get("photos", [])
                            updated_checklist[idx]["photos"] = (cur_photos + item_photos)[:3]
                        if item_documents:
                            cur_docs = updated_checklist[idx].get("documents", [])
                            updated_checklist[idx]["documents"] = (cur_docs + item_documents)[:1]
                    else:
                        updated_checklist.append({
                            "name": item_name, "checked": item_checked, "notes": "",
                            "photos": item_photos[:3], "documents": item_documents[:1],
                        })
                ops.append(UpdateOne({"id": aid}, {"$set": {"document_checklist": updated_checklist, "updated_at": now_str}}))
            if ops:
                await db.assets.bulk_write(ops, ordered=False)

        chunks = [data.asset_ids[i:i+CHUNK] for i in range(0, len(data.asset_ids), CHUNK)]
        for chunk in chunks:
            await update_doc_chunk(chunk)

    # 4. Clear all photos from selected assets
    if should_clear_photos:
        await db.assets.update_many(
            {"id": {"$in": data.asset_ids}},
            {"$set": {"photos": [], "photo": None, "thumbnail": None, "gallery_thumbnail": None, "updated_at": now_str}}
        )

    # 5. Clear all document checklist from selected assets
    if should_clear_doc_checklist:
        await db.assets.update_many(
            {"id": {"$in": data.asset_ids}},
            {"$set": {"document_checklist": [], "updated_at": now_str}}
        )

    # 6. Audit log — batch insert (limit to 20 entries max for large batches)
    field_names_list = list(clean_updates.keys() - {"updated_at"})
    if has_photo:
        field_names_list.append("foto")
    if has_doc_checklist:
        field_names_list.append("kelengkapan_dokumen")
    if should_clear_photos:
        field_names_list.append("hapus_semua_foto")
    if should_clear_doc_checklist:
        field_names_list.append("hapus_semua_dokumen")
    field_names = ", ".join(field_names_list)

    # Single summary audit log entry (instead of one per asset)
    try:
        sample_asset = await db.assets.find_one({"id": data.asset_ids[0]}, {"_id": 0, "asset_code": 1, "asset_name": 1, "activity_id": 1})
        if sample_asset:
            changes = [{"field": k, "from": "(batch)", "to": str(v)[:100]} for k, v in clean_updates.items() if k != "updated_at"]
            await log_audit(
                "batch_update", sample_asset.get("activity_id", ""), data.asset_ids[0],
                sample_asset.get("asset_code", ""), sample_asset.get("asset_name", ""),
                x_user_name or "system", changes,
                f"Batch update {field_names} untuk {updated_count} aset"
            )
    except Exception as e:
        logger.warning(f"Audit log batch error: {e}")

    invalidate_asset_cache()

    # Broadcast WebSocket notification. notify_asset_change's signature is
    # (activity_id, event_type, asset_data, user_name, user_id=None) and it
    # broadcasts per-activity. The previous call passed a single dict, which
    # raised TypeError (swallowed below) so batch updates never reached other
    # viewers. Broadcast to the affected assets' activity instead.
    try:
        bcast_asset = await db.assets.find_one(
            {"id": data.asset_ids[0]}, {"_id": 0, "activity_id": 1}
        ) if data.asset_ids else None
        await notify_asset_change(
            (bcast_asset or {}).get("activity_id", ""),
            "batch_update",
            {"count": updated_count, "fields": field_names_list},
            x_user_name or "system",
        )
    except Exception:
        pass

    result = {
        "updated": updated_count,
        "total": len(data.asset_ids),
        "fields": field_names_list
    }

    # Add compression info if photo was compressed
    if has_photo and compress_method != "none":
        result["photo_compression"] = {
            "method": compress_method,
            "original_kb": round(orig_size / 1024, 1),
            "compressed_kb": round(comp_size / 1024, 1),
            "reduction_pct": round((1 - comp_size / orig_size) * 100) if orig_size > 0 else 0,
        }

    return result



@batch_router.get("/assets/groups")
async def get_asset_groups(activity_id: str = "", request: Request = None):
    """Group assets by same asset_code, asset_name, purchase_date, brand/model, price.
    Returns groups with count >= 2, including detailed member info."""
    match = {}
    if activity_id:
        match["activity_id"] = activity_id
    
    pipeline = [
        {"$match": match},
        {"$group": {
            "_id": {
                "asset_code": {"$ifNull": ["$asset_code", ""]},
                "asset_name": {"$ifNull": ["$asset_name", ""]},
                "purchase_date": {"$ifNull": ["$purchase_date", ""]},
                "brand": {"$ifNull": ["$brand", ""]},
                "model": {"$ifNull": ["$model", ""]},
                "purchase_price": {"$ifNull": ["$purchase_price", 0]}
            },
            "count": {"$sum": 1},
            "asset_ids": {"$push": "$id"},
            "NUPs": {"$push": "$NUP"},
            "members": {"$push": {
                "id": "$id",
                "NUP": "$NUP",
                "location": "$location",
                "eselon1": "$eselon1",
                "eselon2": "$eselon2",
                "user": "$user",
                "condition": "$condition",
                "inventory_status": "$inventory_status",
                "stiker_status": "$stiker_status",
                "nomor_spm": "$nomor_spm",
                "serial_number": "$serial_number",
                "kode_register": "$kode_register",
                "supplier": "$supplier",
                "perolehan_dari_nama": "$perolehan_dari_nama",
                "purchase_date": "$purchase_date",
                "purchase_price": "$purchase_price",
                "category": "$category",
            }}
        }},
        {"$match": {"count": {"$gte": 2}}},
        {"$sort": {"count": -1}},
        {"$limit": 100},
        {"$project": {
            "_id": 0,
            "asset_code": "$_id.asset_code",
            "asset_name": "$_id.asset_name",
            "purchase_date": "$_id.purchase_date",
            "brand": "$_id.brand",
            "model": "$_id.model",
            "purchase_price": "$_id.purchase_price",
            "count": 1,
            "asset_ids": 1,
            "NUPs": 1,
            "members": 1
        }}
    ]
    
    groups = []
    async for doc in db.assets.aggregate(pipeline):
        groups.append(doc)
    
    return {"groups": groups, "total_groups": len(groups)}


@batch_router.get("/assets/all-ids")
async def get_all_asset_ids(
    activity_id: str = "",
    search: str = "",
    category: str = "",
    condition: str = "",
    status: str = "",
    location: str = "",
    eselon1_filter: str = "",
    eselon2_filter: str = "",
    stiker_status: str = "",
    inventory_status: str = "",
):
    """Get all asset IDs matching current filters (for select-all-pages)."""
    query = {}
    if activity_id:
        query["activity_id"] = activity_id
    if search:
        query["$or"] = [
            {"asset_code": {"$regex": search, "$options": "i"}},
            {"asset_name": {"$regex": search, "$options": "i"}},
            {"serial_number": {"$regex": search, "$options": "i"}},
        ]
    if category:
        query["category"] = category
    if condition:
        query["condition"] = condition
    if status:
        query["status"] = status
    if location:
        query["location"] = {"$regex": location, "$options": "i"}
    if eselon1_filter:
        query["eselon1"] = eselon1_filter
    if eselon2_filter:
        query["eselon2"] = eselon2_filter
    if stiker_status:
        query["stiker_status"] = stiker_status
    if inventory_status:
        query["inventory_status"] = inventory_status

    ids = []
    async for doc in db.assets.find(query, {"_id": 0, "id": 1}):
        ids.append(doc["id"])
    return {"ids": ids, "total": len(ids)}
