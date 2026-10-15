"""Conservative cleanup for asset photo commits with uncertain Mongo replies.

Only newly allocated IDs registered to this asset may be compensated. A failed
Mongo read leaves the durable pending marker for later operator reconciliation;
this module deliberately does not implement timed deletion or background GC.
"""
import logging
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import HTTPException

logger = logging.getLogger(__name__)
PATH = "metadata.asset_photo_commit"


def _oid(value):
    return ObjectId(value) if ObjectId.is_valid(str(value)) else value


def _ids(values):
    return list(dict.fromkeys(str(value) for value in values if value))


async def register_photos(database, asset_id, values):
    """Persist ownership/pending evidence before attempting the asset CAS."""
    ids = _ids(values)
    if not ids:
        return
    result = await database["fs.files"].update_many({"_id": {"$in": [_oid(gid) for gid in ids]},
        "$or": [{PATH: {"$exists": False}}, {PATH + ".owner_asset_id": asset_id}]}, {"$set": {
            PATH: {"schema": 1, "owner_asset_id": asset_id, "state": "pending",
                   "created_at": datetime.now(timezone.utc)}}})
    if result.matched_count != len(ids):
        raise HTTPException(503, "Bukti penyimpanan foto belum lengkap. Coba simpan ulang.")


async def discard_uncommitted_photos(database, bucket, asset_id, values):
    """Only compensate known predispatch failure or acknowledged CAS rejection.

    A negative reference read cannot fence an in-flight write. Callers MUST NOT
    invoke this after an uncertain dispatched Mongo operation, even on timeout.
    """
    for gid in _ids(values):
        try:
            record = await database["fs.files"].find_one({"_id": _oid(gid)}, {PATH: 1})
            if record is None:
                continue
            proof = (record.get("metadata") or {}).get("asset_photo_commit") or {}
            if proof.get("owner_asset_id") != asset_id:
                logger.warning("Photo cleanup retained an ID without expected ownership proof")
                continue
            # Include other assets/checklist kinds defensively. New IDs are
            # exclusive, but a later reader must never lose a shared reference.
            referenced = await database.assets.find_one({"$or": [
                {"photo_gridfs_ids": gid}, {"document_checklist.photo_gridfs_ids": gid},
                {"document_checklist.documents.gridfs_id": gid}, {"bast_file_id": gid}]}, {"_id": 1})
            if referenced:
                continue
            await bucket.delete(_oid(gid))
        except Exception:
            logger.warning("Photo cleanup deferred; pending ownership ledger retained", exc_info=True)


async def acknowledge_photos(database, asset_id, values):
    """Best effort bookkeeping after an acknowledged successful asset commit."""
    ids = _ids(values)
    if not ids:
        return
    try:
        await database["fs.files"].update_many({"_id": {"$in": [_oid(gid) for gid in ids]},
            PATH + ".owner_asset_id": asset_id}, {"$set": {
                PATH + ".state": "committed", PATH + ".acknowledged_at": datetime.now(timezone.utc)}})
    except Exception:
        logger.warning("Photo commit acknowledged; pending ledger state retained", exc_info=True)
