"""Checklist media adapter: stable identities, exact bytes and bounded CAS backfill.

The write flag is off by default. Reads understand both inline legacy media and
exclusive asset-owned GridFS references. Backfill retains inline bytes; deletion
of unreferenced stored media is deliberately a separate operator decision.
"""
import base64
import asyncio
import copy
import contextlib
import hashlib
import inspect
import os
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from fastapi import HTTPException

SCHEMA = 1
MAX_READ_BYTES = 16 * 1024 * 1024
GC_GRACE_DAYS = 7


def array(value):
    return value if isinstance(value, list) else []


def photo_count(item):
    return max(len(array(item.get("photos"))), len(array(item.get("photo_gridfs_ids"))))


def write_enabled():
    return os.environ.get("AMAN_CHECKLIST_GRIDFS_WRITE", "").strip().lower() in {"1", "true"}


def _identifier(value):
    return isinstance(value, str) and 0 < len(value) <= 80


def normalize_checklist(items, existing=None):
    """Resolve lightweight sentinels while preserving stable identity and refs.

    Photo arrays and reference arrays share indexes; empty inline slots are
    allowed only where a reference supplies that slot. Duplicate names consume
    old items once, and existing stable IDs survive rename/reorder.
    """
    if not isinstance(items, list):
        raise HTTPException(400, "Kelengkapan dokumen harus berupa daftar")
    old = [item for item in array(existing) if isinstance(item, dict)]
    by_name = defaultdict(deque)
    by_id = {item["id"]: item for item in old if _identifier(item.get("id"))}
    for item in old:
        by_name[item.get("name", "") if isinstance(item.get("name"), str) else ""].append(item)
    consumed = set()
    normalized = []
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise HTTPException(400, "Item kelengkapan tidak valid")
        if item.get("id") is not None and not _identifier(item["id"]):
            raise HTTPException(400, "Identitas item kelengkapan tidak valid")
        before = by_id.get(item.get("id")) if _identifier(item.get("id")) else None
        if before is None or id(before) in consumed:
            queue = by_name[item["name"]]
            while queue and id(queue[0]) in consumed:
                queue.popleft()
            before = queue.popleft() if queue else {}
        consumed.add(id(before))
        item_id = before.get("id") if _identifier(before.get("id")) else uuid.uuid4().hex
        photos, refs, thumbs = [], [], []
        supplied_photos = item.get("photos") or []
        supplied_refs = item.get("photo_gridfs_ids") or []
        documents = item.get("documents") or []
        if not all(isinstance(value, list) for value in (supplied_photos, supplied_refs, documents)):
            raise HTTPException(400, "Lampiran kelengkapan harus berupa daftar")
        old_photos, old_refs = array(before.get("photos")), array(before.get("photo_gridfs_ids"))
        old_thumbs = array(before.get("photo_thumbnails"))
        for index in range(max(len(supplied_photos), len(supplied_refs))):
            value = supplied_photos[index] if index < len(supplied_photos) else ""
            ref = supplied_refs[index] if index < len(supplied_refs) else ""
            thumb = ""
            if isinstance(value, str) and value.startswith("__existing__:"):
                try:
                    position = int(value.split(":", 1)[1])
                    if position < 0 or position >= photo_count(before):
                        raise ValueError()
                except (ValueError, TypeError):
                    raise HTTPException(400, "Posisi foto lama tidak valid. Muat ulang aset.")
                value = old_photos[position] if position < len(old_photos) else ""
                ref = old_refs[position] if position < len(old_refs) else ""
                thumb = old_thumbs[position] if position < len(old_thumbs) else ""
            else:
                # A full old-client GET returns inline bytes, while stored
                # arrays may already have references. Reuse only an exact slot.
                for position, previous in enumerate(old_photos):
                    if value and value == previous:
                        if not ref and position < len(old_refs):
                            ref = old_refs[position]
                        thumb = old_thumbs[position] if position < len(old_thumbs) else ""
                        break
                if ref and ref in old_refs:
                    position = old_refs.index(ref)
                    thumb = old_thumbs[position] if position < len(old_thumbs) else ""
            photos.append(value)
            refs.append(ref)
            thumbs.append(thumb)
        docs = []
        old_docs = array(before.get("documents"))
        for document in documents:
            if not isinstance(document, dict):
                raise HTTPException(400, "Dokumen kelengkapan tidak valid")
            data = document.get("data") or ""
            if isinstance(data, str) and data.startswith("__existing__:"):
                try:
                    position = int(data.split(":", 1)[1])
                    if position < 0 or position >= len(old_docs) or not isinstance(old_docs[position], dict):
                        raise ValueError()
                except (ValueError, TypeError):
                    raise HTTPException(400, "Posisi dokumen lama tidak valid. Muat ulang aset.")
                result = copy.deepcopy(old_docs[position])
            else:
                result = {key: copy.deepcopy(value) for key, value in document.items()
                          if key in {"name", "data", "id", "gridfs_id", "sha256", "length", "content_type"}}
            match = next((doc for doc in old_docs if isinstance(doc, dict) and (
                result.get("gridfs_id") and doc.get("gridfs_id") == result["gridfs_id"]
                or result.get("data") and doc.get("data") == result["data"])), {})
            result["id"] = match.get("id") if _identifier(match.get("id")) else uuid.uuid4().hex
            docs.append(result)
        normalized.append({"id": item_id, "name": item["name"],
            "checked": item.get("checked", False), "notes": item.get("notes") or "",
            "photos": photos if any(photos) else [],
            "photo_gridfs_ids": refs if any(refs) else [],
            "photo_thumbnails": thumbs, "documents": docs})
    return normalized


def safe_checklist(items):
    """Sanitize legacy read shape without changing indexes or persisted bytes."""
    result = []
    for original in array(items):
        item = copy.deepcopy(original) if isinstance(original, dict) else {}
        if not _identifier(item.get("id")):
            item.pop("id", None)
        item["name"] = item.get("name") if isinstance(item.get("name"), str) else "Item lama"
        item["checked"] = bool(item.get("checked", False))
        item["notes"] = item.get("notes") if isinstance(item.get("notes"), str) else ""
        for name in ("photos", "photo_thumbnails", "photo_gridfs_ids"):
            item[name] = [value if isinstance(value, str) else "" for value in array(item.get(name))]
        item["documents"] = [{**document, "name": document.get("name") if isinstance(document.get("name"), str) else "document.pdf"}
                             if isinstance(document, dict) else {"name": "document.pdf", "data": ""}
                             for document in array(item.get("documents"))]
        result.append(item)
    return result


def decode_inline(value):
    if not isinstance(value, str) or not value:
        raise HTTPException(404, "Berkas kelengkapan kosong")
    encoded = value.split(",", 1)[1] if value.startswith("data:") and "," in value else value
    if len(encoded) > ((MAX_READ_BYTES + 2) // 3) * 4:
        raise HTTPException(413, "Berkas kelengkapan terlalu besar")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError):
        raise HTTPException(500, "Berkas kelengkapan rusak")
    if not raw or len(raw) > MAX_READ_BYTES:
        raise HTTPException(413, "Berkas kelengkapan terlalu besar atau kosong")
    return raw


def media_type(raw, kind):
    if kind == "document":
        return "application/pdf"
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if raw.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def coerce_id(value):
    return ObjectId(value) if ObjectId.is_valid(str(value)) else value


async def read_owned_blob(database, bucket, gid, asset_id, kind):
    """Caller already authorized the owning asset and its current reference."""
    record = await database["fs.files"].find_one({"_id": coerce_id(gid)})
    if not record:
        raise HTTPException(404, "Berkas kelengkapan tidak ditemukan")
    metadata = record.get("metadata") or {}
    managed = metadata.get("checklist_storage_schema") == SCHEMA
    if managed and (metadata.get("asset_id") != asset_id or metadata.get("media_kind") != kind):
        raise HTTPException(409, "Pemilik berkas kelengkapan tidak sesuai")
    length = record.get("length")
    if not isinstance(length, int) or not 0 < length <= MAX_READ_BYTES:
        raise HTTPException(413, "Ukuran berkas kelengkapan tidak aman")
    stream = await bucket.open_download_stream(coerce_id(gid))
    raw = bytearray()
    try:
        while True:
            chunk = await stream.readchunk()
            if not chunk:
                break
            raw.extend(chunk)
            if len(raw) > length or len(raw) > MAX_READ_BYTES:
                raise HTTPException(503, "Ukuran berkas kelengkapan tidak cocok")
    finally:
        closed = stream.close()
        if inspect.isawaitable(closed):
            await closed
    raw = bytes(raw)
    if len(raw) != length or managed and hashlib.sha256(raw).hexdigest() != metadata.get("sha256"):
        raise HTTPException(503, "Checksum berkas kelengkapan tidak cocok")
    return raw


async def read_media(asset, item_index, file_index, kind, database, bucket):
    items = array(asset.get("document_checklist"))
    if item_index < 0 or item_index >= len(items) or not isinstance(items[item_index], dict):
        raise HTTPException(404, "Item kelengkapan tidak ditemukan")
    item = items[item_index]
    if kind == "photo":
        photos, refs = array(item.get("photos")), array(item.get("photo_gridfs_ids"))
        if file_index < 0 or file_index >= photo_count(item):
            raise HTTPException(404, "Foto kelengkapan tidak ditemukan")
        gid = refs[file_index] if file_index < len(refs) else ""
        data = photos[file_index] if file_index < len(photos) else ""
        name = f"foto_{item_index}_{file_index}"
    elif kind == "document":
        docs = array(item.get("documents"))
        if file_index < 0 or file_index >= len(docs) or not isinstance(docs[file_index], dict):
            raise HTTPException(404, "Dokumen kelengkapan tidak ditemukan")
        document = docs[file_index]
        gid, data = document.get("gridfs_id"), document.get("data")
        name = document.get("name") or "document.pdf"
    else:
        raise HTTPException(404, "Jenis berkas tidak ditemukan")
    if gid:
        raw = await read_owned_blob(database, bucket, gid, asset["id"], kind)
    else:
        raw = decode_inline(data)
    return raw, media_type(raw, kind), str(name)


async def hydrate_checklist(asset, database, bucket):
    items = safe_checklist(asset.get("document_checklist"))
    for index, item in enumerate(items):
        photos = []
        for position in range(photo_count(item)):
            refs = item["photo_gridfs_ids"]
            if position < len(refs) and refs[position]:
                raw, content_type, _ = await read_media(asset, index, position, "photo", database, bucket)
                photos.append(f"data:{content_type};base64," + base64.b64encode(raw).decode("ascii"))
            else:
                photos.append(item["photos"][position] if position < len(item["photos"]) else "")
        item["photos"] = photos
        for position, doc in enumerate(item["documents"]):
            if doc.get("gridfs_id"):
                raw, _, _ = await read_media(asset, index, position, "document", database, bucket)
                doc["data"] = "data:application/pdf;base64," + base64.b64encode(raw).decode("ascii")
    return items


@dataclass
class PreparedChecklist:
    items: list
    created_photos: list = field(default_factory=list)
    created_documents: list = field(default_factory=list)

    @property
    def created_ids(self):
        return self.created_photos + self.created_documents


async def discard_staged(bucket, prepared, *, database=None, asset_id=None):
    """Compensate ONLY pre-dispatch or acknowledged rejected/CAS-miss writes.

    A negative ownership read cannot disprove an unknown in-flight commit.
    Callers MUST retain all staged files after an unacknowledged dispatched
    write. Readback here additionally protects already visible references.
    """
    retained = set()
    if database is not None:
        try:
            current = await database.assets.find_one({"id": asset_id}, {"document_checklist": 1})
            for item in array((current or {}).get("document_checklist")):
                if isinstance(item, dict):
                    retained.update(str(gid) for gid in array(item.get("photo_gridfs_ids")) if gid)
                    retained.update(str(doc["gridfs_id"]) for doc in array(item.get("documents"))
                                    if isinstance(doc, dict) and doc.get("gridfs_id"))
        except Exception:
            return
    for gid in prepared.created_ids:
        if str(gid) not in retained:
            with contextlib.suppress(Exception):
                await bucket.delete(coerce_id(gid))


async def retire_if_managed(database, gid):
    """Existing deletion flows defer managed media to grace/owner accounting."""
    result = await database["fs.files"].update_one({"_id": coerce_id(gid),
        "metadata.checklist_storage_schema": SCHEMA}, {"$set": {
            "metadata.retired_at": datetime.now(timezone.utc)}})
    return bool(result.matched_count)


async def prepare_checklist(items, asset_id, database, bucket, *, existing=None,
                            store=None, retain_inline=False):
    from asset_media_limits import validate_checklist
    result = PreparedChecklist(normalize_checklist(items, existing))
    validate_checklist(result.items, existing=existing)
    # An owned ID authorizes reuse, never arbitrary replacement bytes hidden
    # behind that ID. Verify old-client full GET echoes before treating them
    # as unchanged; genuine replacement data must pass new-upload limits.
    for item in result.items:
        for position, gid in enumerate(item["photo_gridfs_ids"]):
            data = item["photos"][position] if position < len(item["photos"]) else ""
            if gid and data and decode_inline(data) != await read_owned_blob(database, bucket, gid, asset_id, "photo"):
                item["photo_gridfs_ids"][position] = ""
        for doc in item["documents"]:
            if doc.get("gridfs_id") and doc.get("data"):
                if decode_inline(doc["data"]) != await read_owned_blob(database, bucket, doc["gridfs_id"], asset_id, "document"):
                    for key in ("gridfs_id", "sha256", "length", "content_type"):
                        doc.pop(key, None)
    validate_checklist(result.items, existing=existing)
    if not (write_enabled() if store is None else store):
        return result
    old_refs = {str(gid) for item in array(existing) if isinstance(item, dict)
                for gid in array(item.get("photo_gridfs_ids")) if gid}
    old_docs = {str(doc["gridfs_id"]) for item in array(existing) if isinstance(item, dict)
                for doc in array(item.get("documents")) if isinstance(doc, dict) and doc.get("gridfs_id")}
    async def persist(raw, kind, item_id, file_id, name, old_gid):
        digest = hashlib.sha256(raw).hexdigest()
        if old_gid and str(old_gid) in (old_refs if kind == "photo" else old_docs):
            previous = await read_owned_blob(database, bucket, old_gid, asset_id, kind)
            if previous == raw:
                return str(old_gid), digest
        gid = ObjectId()
        target = result.created_photos if kind == "photo" else result.created_documents
        target.append(str(gid))
        await bucket.upload_from_stream_with_id(gid, name, raw, metadata={
            "checklist_storage_schema": SCHEMA, "asset_id": asset_id,
            "item_id": item_id, "file_id": file_id, "media_kind": kind,
            "sha256": digest, "content_type": media_type(raw, kind),
            "preserved_bytes": True, "created_at": datetime.now(timezone.utc)})
        if await read_owned_blob(database, bucket, str(gid), asset_id, kind) != raw:
            raise HTTPException(503, "Verifikasi penyimpanan berkas gagal")
        return str(gid), digest
    try:
        for item in result.items:
            refs = []
            thumbnails = []
            for position in range(photo_count(item)):
                photos = item["photos"]
                gid = item["photo_gridfs_ids"][position] if position < len(item["photo_gridfs_ids"]) else ""
                data = photos[position] if position < len(photos) else ""
                if data:
                    raw = decode_inline(data)
                elif gid and str(gid) in old_refs:
                    raw = await read_owned_blob(database, bucket, gid, asset_id, "photo")
                else:
                    raise HTTPException(400, "Referensi foto bukan milik aset ini")
                stored, _ = await persist(raw, "photo", item["id"], uuid.uuid4().hex,
                                          f"checklist-photo-{item['id']}", gid)
                refs.append(stored)
                previous_thumbs = array(item.get("photo_thumbnails"))
                thumb = previous_thumbs[position] if position < len(previous_thumbs) else ""
                if not thumb:
                    from shared_utils import generate_photo_thumbnail
                    inline = "data:" + media_type(raw, "photo") + ";base64," + base64.b64encode(raw).decode("ascii")
                    thumb = await asyncio.to_thread(generate_photo_thumbnail, inline) or ""
                thumbnails.append(thumb)
            item["photo_gridfs_ids"] = refs
            item["photo_thumbnails"] = thumbnails
            if not retain_inline:
                item["photos"] = []
            for doc in item["documents"]:
                if doc.get("data"):
                    raw = decode_inline(doc["data"])
                elif doc.get("gridfs_id") and str(doc["gridfs_id"]) in old_docs:
                    raw = await read_owned_blob(database, bucket, doc["gridfs_id"], asset_id, "document")
                else:
                    raise HTTPException(400, "Referensi dokumen bukan milik aset ini")
                gid, digest = await persist(raw, "document", item["id"], doc["id"],
                                            doc.get("name") or "document.pdf", doc.get("gridfs_id"))
                doc.update(gridfs_id=gid, sha256=digest, length=len(raw), content_type="application/pdf")
                if not retain_inline:
                    doc["data"] = ""
        validate_checklist(result.items, existing=existing, staged_photos=result.created_photos,
                           staged_documents=result.created_documents)
        return result
    except BaseException:
        await discard_staged(bucket, result)
        raise


async def backfill_asset(database, bucket, asset_id, *, dry_run=True):
    """One CAS-bounded asset per call; inline bytes are NEVER purged by backfill."""
    from dataset_epoch import get_generation
    from pemeliharaan import writer_admission
    from asset_media_limits import validate_asset_document
    async with writer_admission(database=database):
        asset = await database.assets.find_one({"id": asset_id})
        if not asset:
            raise HTTPException(404, "Aset tidak ditemukan")
        items = array(asset.get("document_checklist"))
        summary = {"asset_id": asset_id, "dry_run": dry_run, "inline_retained": True,
                   "items": len(items), "photos": sum(photo_count(item) for item in items if isinstance(item, dict)),
                   "documents": sum(len(array(item.get("documents"))) for item in items if isinstance(item, dict))}
        if dry_run:
            return summary
        generation = await get_generation(database)
        prepared = await prepare_checklist(items, asset_id, database, bucket, existing=items,
                                            store=True, retain_inline=True)
        dispatched = acknowledged = False
        try:
            validate_asset_document({**asset, "document_checklist": prepared.items}, existing=asset)
            if await get_generation(database) != generation:
                raise HTTPException(409, "Dataset berubah; backfill dibatalkan")
            query = {"_id": asset["_id"], "document_checklist": asset.get("document_checklist")}
            query["version"] = asset["version"] if "version" in asset else {"$exists": False}
            dispatched = True
            result = await database.assets.update_one(query, {"$set": {
                "document_checklist": prepared.items, "updated_at": datetime.now(timezone.utc).isoformat()},
                "$inc": {"version": 1}})
            acknowledged = True
            if not result.matched_count:
                raise HTTPException(409, "Aset berubah; backfill tidak menimpa perubahan")
        except BaseException:
            if not dispatched or acknowledged:
                await discard_staged(bucket, prepared, database=database, asset_id=asset_id)
            else:
                from pemeliharaan import mark_current_writer_uncertain
                await mark_current_writer_uncertain("checklist_backfill")
            raise
        # Metadata/version changes must also expire derived list projections.
        from shared_utils import invalidate_asset_cache
        from meili_utils import jadwalkan_sync
        invalidate_asset_cache()
        jadwalkan_sync("assets", {**asset, "document_checklist": prepared.items,
                                 "version": (asset.get("version") or 0) + 1})
        return {**summary, "created_files": len(prepared.created_ids)}


async def orphan_report(database, *, grace_days=GC_GRACE_DAYS, max_documents=10000, limit=100):
    """Read-only conservative accounting across EVERY collection, including history.

    An incomplete scan never marks a candidate eligible. No delete command is
    exposed here. Actual deletion needs a separate reviewed operator procedure.
    """
    if grace_days < GC_GRACE_DAYS or not 1 <= limit <= 100 or not 1 <= max_documents <= 100000:
        raise ValueError("Batas audit/grace tidak aman")
    cutoff = datetime.now(timezone.utc) - timedelta(days=grace_days)
    candidates = await database["fs.files"].find({"metadata.checklist_storage_schema": SCHEMA,
        "uploadDate": {"$lte": cutoff}, "$or": [{"metadata.retired_at": {"$exists": False}},
        {"metadata.retired_at": {"$lte": cutoff}}]}).limit(limit).to_list(limit)
    candidates_by_id = {str(item["_id"]): item for item in candidates}
    owners = {gid: 0 for gid in candidates_by_id}
    scanned, complete = 0, True
    def references(value):
        if isinstance(value, dict):
            for nested in value.values():
                yield from references(nested)
        elif isinstance(value, list):
            for nested in value:
                yield from references(nested)
        elif isinstance(value, str):
            for gid in owners:
                if gid in value:
                    yield gid
    for collection in await database.list_collection_names():
        if collection.startswith("fs."):
            continue
        async for document in database[collection].find({}):
            scanned += 1
            if scanned > max_documents:
                complete = False
                break
            for gid in set(references(document)):
                owners[gid] += 1
        if not complete:
            break
    return {"dry_run": True, "complete": complete, "scanned_documents": min(scanned, max_documents),
            "grace_days": grace_days, "candidates": [{"gridfs_id": gid, "owner_documents": owners[gid],
                "unreferenced": complete and owners[gid] == 0,
                "eligible_for_operator_review": complete and owners[gid] == 0
                    and isinstance((candidates_by_id[gid].get("metadata") or {}).get("retired_at"), datetime)}
                for gid in owners]}
