"""Delete asset references with CAS, then release their exclusive media.

Receipts are made durable before their only asset proof can disappear. Failed
or concurrently changed assets retain both their proofs and their media.
"""
import logging

logger = logging.getLogger(__name__)


async def delete_activity_assets(activity_id, database):
    from batch_operations import reconcile_before_asset_delete, cas_filter
    from meili_utils import jadwalkan_hapus
    import shared_utils

    result = {"deleted": 0, "conflicts": 0, "conflict_ids": [], "photos": 0, "documents": 0}
    async for asset in database.assets.find({"activity_id": activity_id}):
        await reconcile_before_asset_delete(asset)
        deleted = await database.assets.delete_one(cas_filter(asset))
        if not deleted.deleted_count:
            result["conflicts"] += 1
            if len(result["conflict_ids"]) < 20:
                result["conflict_ids"].append(asset["id"])
            continue
        result["deleted"] += 1
        # Snapshot survives the successful delete. Reverse order could destroy
        # photos for an asset whose deletion CAS failed.
        photos = set(g for g in asset.get("photo_gridfs_ids", []) if g)
        documents = {asset["bast_file_id"]} if asset.get("bast_file_id") else set()
        for item in asset.get("document_checklist", []) or []:
            if isinstance(item, dict):
                photos.update(gid for gid in item.get("photo_gridfs_ids", []) or [] if gid)
                documents.update(d["gridfs_id"] for d in item.get("documents", []) or []
                                 if isinstance(d, dict) and d.get("gridfs_id"))
        for gid in photos:
            try:
                await shared_utils.delete_photo_from_gridfs(gid)
                result["photos"] += 1
            except Exception:
                logger.warning("Could not release deleted asset photo asset=%s", asset["id"])
        for gid in documents:
            try:
                await shared_utils.delete_document_from_gridfs(gid)
                result["documents"] += 1
            except Exception:
                logger.warning("Could not release deleted asset document asset=%s", asset["id"])
        jadwalkan_hapus("assets", asset["id"])
    return result
