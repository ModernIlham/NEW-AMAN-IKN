"""Bounded, resumable batch_v2 operations on standalone MongoDB.

The asset CAS carries its application proof. A receipt is a materialized view,
not the authority for whether an asset was changed. Never delete a fresh proof
until its receipt and durable derived records have been reconciled.
"""
import asyncio
import copy
import hashlib
import json
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from asset_fields import BATCHABLE_FIELD_NAMES
from db import db, fs_bucket
from checklist_storage import (array as media_array, photo_count as checklist_photo_count,
                               prepare_checklist, discard_staged)
from inventarisasi_stempel import stempel
from marker_pin import bersihkan_marker_doc
from shared_utils import (
    kode_satker_user, pastikan_akses_kegiatan_id,
    enforce_pegawai_terdaftar, store_photo_to_gridfs, delete_photo_from_gridfs,
    create_thumbnail, create_gallery_thumbnail, generate_photo_thumbnail,
)
from spasial_utils import normalisasi_koordinat_doc, sisip_geo_ke_update

logger = logging.getLogger(__name__)
MAX_TARGETS = 200
MAX_PAYLOAD_BYTES = 8 * 1024 * 1024
REPLAY_HORIZON_SECONDS = 7 * 24 * 3600
RECEIPT_RETENTION_DAYS = 30
MAX_ASSET_MARKERS = 128
LEASE_SECONDS = 90
MARKERS = "_batch_applications"
REVISION = "_batch_revision"
OPERATION_RE = re.compile(r"^b2_(\d{13})_([0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})$")
SPECIAL_FIELDS = {"batch_photo", "batch_photos", "document_checklist_items", "clear_photos", "clear_document_checklist"}


def now_utc():
    return datetime.now(timezone.utc)


def error(code, message, status=409):
    raise HTTPException(status_code=status, detail={"code": code, "message": message})


def normalize_ids(asset_ids):
    if not isinstance(asset_ids, list) or not asset_ids or len(asset_ids) > MAX_TARGETS * 2:
        error("invalid_targets", f"Pilih 1–{MAX_TARGETS} ID unik per operasi.", 400)
    ids = list(dict.fromkeys(str(a).strip() for a in asset_ids if isinstance(a, str) and a.strip()))
    if not ids or len(ids) > MAX_TARGETS or any(len(a) > 128 for a in ids):
        error("invalid_targets", f"Pilih 1–{MAX_TARGETS} ID unik per operasi.", 400)
    if len(ids) != len(set(str(a).strip() for a in asset_ids)):
        error("invalid_targets", "ID aset harus berupa teks yang tidak kosong.", 400)
    return ids


def operation_issued_at(operation_id, *, enforce_horizon=True):
    match = OPERATION_RE.fullmatch(str(operation_id))
    if not match:
        error("invalid_operation_id", "Identitas operasi batch tidak valid.", 400)
    issued = datetime.fromtimestamp(int(match.group(1)) / 1000, timezone.utc)
    age = (now_utc() - issued).total_seconds()
    if age < -300:
        error("operation_in_future", "Waktu perangkat terlalu jauh di depan server.")
    if enforce_horizon and age > REPLAY_HORIZON_SECONDS:
        error("operation_expired", "Operasi berumur lebih dari 7 hari; rekonsiliasi hasil sebelum membuat operasi baru.")
    return issued


def owner_scope(user):
    owner = str(user.get("id") or user.get("username") or "").strip()
    if not owner:
        error("owner_required", "Identitas akun tidak tersedia.", 403)
    return {"owner_id": owner, "kode_satker": kode_satker_user(user)}


async def dataset_generation():
    from dataset_epoch import get_generation
    return await get_generation(db)


async def rotate_dataset_generation(reason="restore"):
    """Call before restore starts wiping; dataset_state MUST be restore-excluded."""
    from dataset_epoch import rotate_generation
    return await rotate_generation(db, reason)


async def _authorize_assets(ids, user):
    docs = {a["id"]: a async for a in db.assets.find(
        {"id": {"$in": ids}}, {"_id": 0, "id": 1, "version": 1, "activity_id": 1})}
    for activity_id in {d.get("activity_id", "") for d in docs.values()}:
        await pastikan_akses_kegiatan_id(user, activity_id)
    return docs


async def preflight(asset_ids, user):
    ids = normalize_ids(asset_ids)
    docs = await _authorize_assets(ids, user)
    return {
        "protocol": "batch_v2", "dataset_generation": await dataset_generation(),
        "max_targets": MAX_TARGETS, "replay_horizon_seconds": REPLAY_HORIZON_SECONDS,
        "targets": [{"id": aid, "version": int(docs[aid].get("version", 1) or 1), "status": "ready"}
                    if aid in docs else {"id": aid, "status": "missing"} for aid in ids],
    }


async def normalize_updates(updates):
    if not isinstance(updates, dict) or not updates:
        error("empty_updates", "Tidak ada perubahan yang dikirim.", 400)
    unknown = set(updates) - set(BATCHABLE_FIELD_NAMES) - SPECIAL_FIELDS
    if unknown:
        error("invalid_fields", "Field ubah massal tidak dikenali: " + ", ".join(sorted(unknown)), 400)
    scalars = {}
    for key in BATCHABLE_FIELD_NAMES:
        if key not in updates or updates[key] is None:
            continue
        value = updates[key]
        if not isinstance(value, (str, int, float)) or isinstance(value, bool):
            error("invalid_value", f"Nilai {key} harus berupa teks atau angka.", 400)
        scalars[key] = "" if value == "__clear__" else str(value)
    normalisasi_koordinat_doc(scalars)
    await bersihkan_marker_doc(scalars)
    if scalars.get("pengguna_nip"):
        await enforce_pegawai_terdaftar(scalars["pengguna_nip"])
    photos = []
    if updates.get("batch_photo"):
        photos.append(updates["batch_photo"])
    if updates.get("batch_photos") is not None:
        if not isinstance(updates["batch_photos"], list):
            error("invalid_photos", "Foto harus berupa daftar.", 400)
        photos.extend(updates["batch_photos"])
    if len(photos) > 6 or any(not isinstance(p, str) or not p.startswith("data:image/") for p in photos):
        error("invalid_photos", "Maksimal 6 foto gambar per operasi.", 400)
    clear_photos = updates.get("clear_photos") is True
    clear_checklist = updates.get("clear_document_checklist") is True
    checklist = updates.get("document_checklist_items") or []
    if not isinstance(checklist, list) or len(checklist) > 50:
        error("invalid_checklist", "Maksimal 50 item kelengkapan per operasi.", 400)
    seen = set()
    for item in checklist:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not item["name"].strip() or len(item["name"]) > 200:
            error("invalid_checklist", "Nama item kelengkapan tidak valid.", 400)
        if item["name"] in seen:
            error("invalid_checklist", "Nama item kelengkapan harus unik.", 400)
        seen.add(item["name"])
        if not isinstance(item.get("checked", False), bool):
            error("invalid_checklist", "Status item harus benar/salah.", 400)
        for field, limit in (("photos", 3), ("documents", 1)):
            values = item.get(field, [])
            if not isinstance(values, list) or len(values) > limit:
                error("invalid_checklist", f"Lampiran {field} melebihi batas.", 400)
            if field == "photos" and any(not isinstance(value, str) or not value.startswith("data:image/") for value in values):
                error("invalid_checklist", "Foto kelengkapan harus berupa data gambar baru.", 400)
            if field == "documents" and any(
                not isinstance(value, dict) or not isinstance(value.get("name"), str)
                or not value["name"].strip() or len(value["name"]) > 200
                or not isinstance(value.get("data"), str)
                or not value["data"].startswith("data:application/pdf;base64,") for value in values
            ):
                error("invalid_checklist", "Dokumen kelengkapan harus berupa PDF baru dengan nama valid.", 400)
    if clear_photos and photos or clear_checklist and checklist:
        error("contradictory_updates", "Menghapus semua dan menambah lampiran harus dilakukan terpisah.", 400)
    if not (scalars or photos or checklist or clear_photos or clear_checklist):
        error("empty_updates", "Tidak ada perubahan valid.", 400)
    return {"scalars": scalars, "photos": photos, "checklist": checklist,
            "clear_photos": clear_photos, "clear_checklist": clear_checklist}


def cas_filter(asset):
    """Bind the Mongo row identity as well as version and proof revision."""
    conditions = [{"id": asset["id"]}]
    if "_id" in asset:
        conditions.append({"_id": asset["_id"]})
    conditions.append({"version": asset["version"]} if "version" in asset else {"version": {"$exists": False}})
    conditions.append({REVISION: asset[REVISION]} if REVISION in asset else {REVISION: {"$exists": False}})
    return {"$and": conditions}


def _find_marker(asset, operation_id):
    return next((m for m in (asset or {}).get(MARKERS, []) if m.get("operation_id") == operation_id), None)


async def _receipt_marker(operation, marker):
    """Idempotent durable side effects, then receipt; retry reconstructs both."""
    result = marker["result"]
    audit = marker.get("audit")
    if audit:
        key = f"batch:{operation['_id']}:{result['id']}"
        await db.audit_logs.update_one({"_id": key}, {"$setOnInsert": {"id": key, **audit}}, upsert=True)
    journal = marker.get("journal")
    if journal:
        key = f"batch:{operation['_id']}:{result['id']}"
        await db.mutasi_bmn.update_one({"_id": key}, {"$setOnInsert": {"id": key, **journal}}, upsert=True)
    for gid in marker.get("delete_gids", []):
        await delete_photo_from_gridfs(gid)
    index = operation["asset_ids"].index(result["id"])
    await db.batch_operations.update_one(
        {"_id": operation["_id"], "payload_hash": operation["payload_hash"]},
        {"$set": {f"results.{index}": result, "updated_at": now_utc().isoformat()}},
    )


async def reconcile_before_asset_delete(asset):
    """Reconcile first; caller MUST delete with cas_filter(asset), retry on miss.

    This also covers cascades. Do not delete_many assets with fresh markers.
    """
    for marker in asset.get(MARKERS, []):
        operation = await db.batch_operations.find_one({"_id": marker["operation_id"]})
        if operation:
            await _receipt_marker(operation, marker)
        elif (now_utc().timestamp() - marker.get("issued_epoch", 0)) < REPLAY_HORIZON_SECONDS:
            error("batch_reconciliation_required", "Bukti operasi belum dapat direkonsiliasi; coba hapus kembali nanti.", 503)
        else:
            # Receipt retention may already have elapsed. The immutable proof
            # still contains enough data to finish durable audit/journal effects.
            await _receipt_marker({"_id": marker["operation_id"], "payload_hash": marker["payload_hash"],
                                   "asset_ids": [marker["result"]["id"]]}, marker)


async def _reconcile(operation):
    applied_ids = []
    async for asset in db.assets.find({"id": {"$in": operation["asset_ids"]}}, {"id": 1, MARKERS: 1}):
        marker = _find_marker(asset, operation["_id"])
        if marker:
            if marker["payload_hash"] != operation["payload_hash"]:
                error("proof_mismatch", "Bukti operasi tidak cocok; rekonsiliasi administrator diperlukan.", 503)
            await _receipt_marker(operation, marker)
            if marker["result"]["status"] == "applied":
                applied_ids.append(asset["id"])
    if applied_ids:
        # Replays also repair derived projections after a crash before the
        # original writer reached its cache/search hooks.
        from shared_utils import invalidate_asset_cache
        from meili_utils import jadwalkan_sync_id
        invalidate_asset_cache()
        jadwalkan_sync_id("assets", applied_ids)


def _response(operation):
    results = operation["results"]
    counts = {"requested_unique": len(operation["asset_ids"]), "applied": 0, "unchanged": 0,
              "conflicts": 0, "missing": 0, "failed": 0, "pending": 0}
    for result in results:
        key = "conflicts" if result["status"] == "conflict" else result["status"]
        counts[key] += 1
    state = "running" if counts["pending"] else "partial" if counts["conflicts"] + counts["missing"] + counts["failed"] else "completed"
    expiry = operation["replay_until"]
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return {"protocol": "batch_v2", "operation_id": operation["_id"],
            "dataset_generation": operation["dataset_generation"], "state": state,
            "updated": counts["applied"] + counts["unchanged"], "total": counts["requested_unique"],
            "created_at": operation["created_at"], "expires_at": expiry.isoformat(),
            **counts, "results": results}


async def get_operation(operation_id, user, *, enforce_generation=True):
    operation_issued_at(operation_id)
    operation = await db.batch_operations.find_one({"_id": operation_id, **owner_scope(user)})
    if not operation:
        error("operation_not_found", "Operasi tidak ditemukan untuk akun/satker ini.", 404)
    if enforce_generation and operation["dataset_generation"] != await dataset_generation():
        error("dataset_changed", "Dataset telah dipulihkan; operasi lama ditahan untuk rekonsiliasi.")
    await _authorize_assets(operation["asset_ids"], user)
    await _reconcile(operation)
    return await db.batch_operations.find_one({"_id": operation_id})


async def status(operation_id, user):
    return _response(await get_operation(operation_id, user))


async def _prepare_photos(photos):
    from routes.media import auto_compress_image
    prepared = []
    for photo in photos:
        compressed, _, _, _ = await auto_compress_image(photo)
        thumb = await asyncio.to_thread(generate_photo_thumbnail, compressed)
        if not thumb:
            error("invalid_photos", "Foto tidak dapat dibaca sebagai gambar.", 400)
        prepared.append({"data": compressed, "thumb": thumb})
    return prepared


async def _asset_changes(asset, normalized, prepared, now_str, new_gids, checklist_staging=None):
    fields = copy.deepcopy(normalized["scalars"])
    unset = sisip_geo_ke_update(asset, fields)
    delete_gids = []
    if normalized["clear_photos"]:
        delete_gids = [g for g in asset.get("photo_gridfs_ids", []) if g]
        if any(asset.get(k) for k in ("photos", "photo", "photo_gridfs_ids", "photo_thumbnails", "thumbnail", "gallery_thumbnail")):
            fields.update(photos=[], photo=None, photo_gridfs_ids=[], photo_thumbnails=[], thumbnail=None, gallery_thumbnail=None)
    elif prepared:
        gids = list(asset.get("photo_gridfs_ids") or [])
        inline = list(asset.get("photos") or [])
        thumbs = list(asset.get("photo_thumbnails") or [])
        slots = max(len(gids), len(inline))
        gids += [""] * (slots - len(gids))
        thumbs += [""] * (slots - len(thumbs))
        for photo in prepared[:max(0, 6 - slots)]:
            gid = await store_photo_to_gridfs(photo["data"])
            if not gid:
                raise ValueError("GridFS tidak mengembalikan ID foto")
            new_gids.append(gid)
            gids.append(gid)
            thumbs.append(photo["thumb"])
        if new_gids:
            fields.update(photo_gridfs_ids=gids, photo_thumbnails=thumbs)
            if inline:
                fields["photos"] = inline + [""] * (slots - len(inline)) + [p["data"] for p in prepared[:len(new_gids)]]
            if slots == 0:
                fields["thumbnail"] = await asyncio.to_thread(create_thumbnail, prepared[0]["data"])
                fields["gallery_thumbnail"] = await asyncio.to_thread(create_gallery_thumbnail, prepared[0]["data"])
    if normalized["clear_checklist"]:
        if asset.get("document_checklist"):
            fields["document_checklist"] = []
    elif normalized["checklist"]:
        checklist = copy.deepcopy(media_array(asset.get("document_checklist")))
        for item in normalized["checklist"]:
            existing = next((d for d in checklist if isinstance(d, dict) and d.get("name") == item["name"]), None)
            if existing is None:
                existing = {"name": item["name"], "notes": "", "photos": [], "documents": []}
                checklist.append(existing)
            existing["checked"] = item.get("checked", False)
            slots = checklist_photo_count(existing)
            photos = list(media_array(existing.get("photos")))
            refs = list(media_array(existing.get("photo_gridfs_ids")))
            additions = item.get("photos", [])[:max(0, 3 - slots)]
            existing["photos"] = photos + [""] * (slots - len(photos)) + additions
            existing["photo_gridfs_ids"] = refs + [""] * (slots - len(refs) + len(additions))
            documents = list(media_array(existing.get("documents")))
            existing["documents"] = documents + item.get("documents", [])[:max(0, 1 - len(documents))]
        fields["document_checklist"] = checklist
    from asset_media_limits import validate_checklist, validate_asset_document
    if "document_checklist" in fields:
        validate_checklist(fields["document_checklist"], existing=asset.get("document_checklist") or [])
        staged = await prepare_checklist(fields["document_checklist"], asset["id"], db, fs_bucket,
                                          existing=asset.get("document_checklist"))
        if checklist_staging is not None:
            checklist_staging.append(staged)
        fields["document_checklist"] = staged.items
    validate_asset_document({**asset, **fields}, existing=asset)
    fields = {k: v for k, v in fields.items() if asset.get(k) != v}
    unset = {k: v for k, v in unset.items() if k in asset}
    if fields or unset:
        stempel(asset, fields, now_str)
        fields["updated_at"] = now_str
    return fields, unset, delete_gids


def _audit_marker(asset, fields, operation, user, now_str):
    changes = [{"field": key, "from": str(asset.get(key, ""))[:200], "to": str(value)[:200]}
               for key, value in fields.items() if key in BATCHABLE_FIELD_NAMES]
    if any(k in fields for k in ("photos", "photo_gridfs_ids")):
        changes.append({"field": "photos", "from": "(sebelum batch)", "to": "(diperbarui)"})
    if "document_checklist" in fields:
        changes.append({"field": "document_checklist", "from": "(sebelum batch)", "to": "(diperbarui)"})
    audit = {"action": "batch_update", "activity_id": asset.get("activity_id", ""), "asset_id": asset["id"],
             "asset_code": asset.get("asset_code", ""), "asset_name": asset.get("asset_name", ""),
             "nup": asset.get("NUP", ""), "username": user.get("name") or user.get("username") or "system",
             "kode_satker": operation["kode_satker"], "timestamp": now_str, "changes": changes,
             "detail": "Ubah massal batch_v2", "operation_id": operation["_id"]}
    journal = None
    if "purchase_price" in fields:
        from pembukuan_utils import parse_harga
        old_price, price = parse_harga(asset.get("purchase_price")), parse_harga(fields["purchase_price"])
        delta = price - old_price
        if abs(delta) >= .005:
            journal = {"asset_id": asset["id"], "kode_transaksi": "204" if delta > 0 else "205",
                       "kode_barang": str(asset.get("asset_code") or ""), "nup": str(asset.get("NUP") or ""),
                       "tanggal_buku": now_str[:10], "jumlah": 0, "nilai": abs(delta), "sumber_modul": "batch",
                       "keterangan": "Edit massal nilai perolehan", "oleh": audit["username"],
                       "kode_satker": operation["kode_satker"], "created_at": now_str,
                       "ref_id": operation["_id"]}
    return audit, journal


async def _after_asset_commit(operation, marker):
    """Injection seam for crash tests; may never reapply the asset mutation."""
    await _receipt_marker(operation, marker)


async def _apply_asset(operation, aid, expected_version, normalized, prepared, user, session_id):
    asset = await db.assets.find_one({"id": aid})
    if not asset:
        return {"id": aid, "status": "missing", "reason": "not_found"}
    await pastikan_akses_kegiatan_id(user, asset.get("activity_id", ""))
    marker = _find_marker(asset, operation["_id"])
    if marker:
        await _receipt_marker(operation, marker)
        return marker["result"]
    current_version = int(asset.get("version", 1) or 1)
    if current_version != expected_version:
        return {"id": aid, "status": "conflict", "version": current_version, "reason": "version_changed"}
    activity = await db.inventory_activities.find_one({"id": asset.get("activity_id", ""), "status_pengesahan": "disahkan"})
    if activity:
        return {"id": aid, "status": "conflict", "version": current_version, "reason": "activity_sealed"}
    now = now_utc()
    lock = await db.row_locks.find_one({"asset_id": aid, "expires_at": {"$gt": now}, "session_id": {"$ne": session_id}})
    if lock:
        return {"id": aid, "status": "conflict", "version": current_version, "reason": "locked"}
    valid_markers = []
    for existing_marker in asset.get(MARKERS, []):
        if now.timestamp() - existing_marker.get("issued_epoch", 0) < REPLAY_HORIZON_SECONDS:
            valid_markers.append(existing_marker)
        else:
            # Do not prune the only remaining audit/journal evidence merely
            # because its replay horizon elapsed while the browser was absent.
            await reconcile_before_asset_delete({MARKERS: [existing_marker]})
    if len(valid_markers) >= MAX_ASSET_MARKERS:
        return {"id": aid, "status": "failed", "reason": "proof_budget_exceeded", "retryable": True}
    new_gids = []
    checklist_staging = []
    attempted_commit = False
    committed = False
    try:
        fields, unset, delete_gids = await _asset_changes(asset, normalized, prepared, now.isoformat(), new_gids,
                                                        checklist_staging)
        changed = bool(fields or unset)
        version = current_version + 1 if changed else current_version
        result = {"id": aid, "status": "applied" if changed else "unchanged", "version": version}
        audit, journal = _audit_marker(asset, fields, operation, user, now.isoformat()) if changed else (None, None)
        marker = {"operation_id": operation["_id"], "payload_hash": operation["payload_hash"],
                  "issued_epoch": operation["issued_epoch"], "result": result,
                  "audit": audit, "journal": journal, "delete_gids": delete_gids}
        fields.update({MARKERS: valid_markers + [marker], REVISION: int(asset.get(REVISION, 0)) + 1})
        if changed:
            fields["version"] = version  # legacy missing version starts at logical 1 -> 2
        from asset_media_limits import validate_asset_document
        # The application proof and its audit snapshot consume BSON too. Size
        # admission before constructing that proof is not sufficient.
        validate_asset_document({**asset, **fields}, existing=asset)
        update = {"$set": fields}
        if unset:
            update["$unset"] = unset
        # Renew before checking generation. Restore rotates generation then
        # drains these leases before its first wipe; an already-uploading
        # worker must either stop here or remain visible to that barrier.
        renewed = await db.batch_operations.update_one(
            {"_id": operation["_id"], "lease_token": operation["lease_token"]},
            {"$set": {"lease_until": now_utc() + timedelta(seconds=LEASE_SECONDS)}},
        )
        if not renewed.matched_count:
            error("operation_lease_lost", "Operasi sedang dilanjutkan worker lain; periksa status.")
        if operation["dataset_generation"] != await dataset_generation():
            error("dataset_changed", "Dataset berubah selama unggahan; operasi ditahan untuk rekonsiliasi.")
        attempted_commit = True
        write = await db.assets.update_one(cas_filter(asset), update)
        if not write.matched_count:
            latest = await db.assets.find_one({"id": aid}, {"_id": 0})
            proof = _find_marker(latest, operation["_id"])
            if proof:
                await _receipt_marker(operation, proof)
                return proof["result"]
            if latest is None:
                return {"id": aid, "status": "missing", "reason": "concurrent_delete"}
            return {"id": aid, "status": "conflict", "version": int((latest or {}).get("version", 1) or 1), "reason": "concurrent_change"}
        committed = True
        await _after_asset_commit(operation, marker)
        return result
    except HTTPException as exc:
        if attempted_commit and not committed and 'write' not in locals():
            from pemeliharaan import mark_current_writer_uncertain
            await mark_current_writer_uncertain("batch_asset")
        if not attempted_commit and exc.status_code in {400, 413, 422}:
            return {"id": aid, "status": "failed", "reason": "asset_payload_too_large" if exc.status_code == 413 else "invalid_media",
                    "message": str(exc.detail)[:300], "retryable": False}
        raise
    except BaseException:
        if attempted_commit and not committed:
            # A network error may be an acknowledged-lost commit. Read proof
            # before deleting uploaded blobs; failed read leaves safe orphans.
            from pemeliharaan import mark_current_writer_uncertain
            try:
                latest = await db.assets.find_one({"id": aid}, {"_id": 0, MARKERS: 1})
            except BaseException:
                await mark_current_writer_uncertain("batch_asset")
                raise
            proof = _find_marker(latest, operation["_id"])
            if proof:
                committed = True
                await _receipt_marker(operation, proof)
                return proof["result"]
            await mark_current_writer_uncertain("batch_asset")
        raise
    finally:
        if not committed:
            # A successful CAS miss proves our new blobs were never referenced.
            # If CAS itself raised and proof read failed, do not delete them.
            if not attempted_commit or 'write' in locals():
                for staged in checklist_staging:
                    await discard_staged(fs_bucket, staged, database=db, asset_id=aid)
                for gid in new_gids:
                    await delete_photo_from_gridfs(gid)


async def execute(payload, user, session_id="unknown-session", *, prepare_only=False):
    ids = normalize_ids(payload.get("asset_ids"))
    operation_id = payload.get("operation_id", "")
    issued = operation_issued_at(operation_id)
    scope = owner_scope(user)
    versions = payload.get("expected_versions")
    if not isinstance(versions, dict) or set(versions) != set(ids) or any(type(v) is not int or v < 1 for v in versions.values()):
        error("expected_versions_required", "Lakukan preflight dan kirim versi setiap ID target.", 400)
    generation = await dataset_generation()
    if payload.get("dataset_generation") != generation:
        error("dataset_changed", "Dataset berubah; lakukan rekonsiliasi sebelum mengulang.")
    canonical = {"asset_ids": sorted(ids), "expected_versions": versions, "updates": payload.get("updates"),
                 "dataset_generation": generation, **scope}
    try:
        serialized = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (ValueError, TypeError):
        error("invalid_payload", "Payload harus berupa JSON valid dengan angka berhingga.", 400)
    if len(serialized.encode()) > MAX_PAYLOAD_BYTES:
        error("payload_too_large", "Payload operasi melebihi batas 8 MiB.", 413)
    digest = hashlib.sha256(serialized.encode()).hexdigest()
    # Authenticate targets before admitting an operation; no silent cross-satker
    # partial commits, including a replay after permissions were revoked.
    await _authorize_assets(ids, user)
    normalized = await normalize_updates(payload.get("updates"))
    now = now_utc()
    record = {"_id": operation_id, **scope, "payload_hash": digest, "asset_ids": ids,
              "dataset_generation": generation, "issued_epoch": issued.timestamp(),
              "created_at": now.isoformat(), "updated_at": now.isoformat(),
              "replay_until": issued + timedelta(seconds=REPLAY_HORIZON_SECONDS),
              "expires_at": issued + timedelta(days=RECEIPT_RETENTION_DAYS),
              "request": {**payload, "asset_ids": ids},
              "results": [{"id": aid, "status": "pending"} for aid in ids]}
    try:
        await db.batch_operations.insert_one(record)
        operation = record
    except DuplicateKeyError:
        operation = await db.batch_operations.find_one({"_id": operation_id})
        if any(operation.get(key) != value for key, value in scope.items()) or operation["payload_hash"] != digest:
            error("operation_payload_mismatch", "Identitas operasi sudah dipakai dengan payload atau akun/satker berbeda.")
    await _reconcile(operation)
    if prepare_only:
        return _response(await db.batch_operations.find_one({"_id": operation_id}))
    token = str(uuid.uuid4())
    operation = await db.batch_operations.find_one_and_update(
        {"_id": operation_id, "$or": [{"lease_until": {"$lt": now}}, {"lease_until": {"$exists": False}}]},
        {"$set": {"lease_token": token, "lease_until": now + timedelta(seconds=LEASE_SECONDS)}},
        return_document=ReturnDocument.AFTER,
    )
    if not operation:
        return _response(await db.batch_operations.find_one({"_id": operation_id}))
    committed_ids = []
    try:
        prepared = await _prepare_photos(normalized["photos"])
        for index, old_result in enumerate(operation["results"]):
            if old_result["status"] in {"applied", "unchanged", "conflict", "missing"} or old_result["status"] == "failed" and not old_result.get("retryable"):
                continue
            lease = await db.batch_operations.update_one(
                {"_id": operation_id, "lease_token": token},
                {"$set": {"lease_until": now_utc() + timedelta(seconds=LEASE_SECONDS)}},
            )
            if not lease.matched_count:
                break
            if generation != await dataset_generation():
                error("dataset_changed", "Dataset berubah selama operasi; rekonsiliasi diperlukan.")
            aid = old_result["id"]
            try:
                result = await _apply_asset(operation, aid, versions[aid], normalized, prepared, user, session_id)
            except HTTPException:
                raise
            except Exception:
                logger.exception("batch_v2 target failed operation=%s asset=%s", operation_id, aid)
                # An atomic proof may exist even if receipt persistence failed.
                # Keep pending so status/resume reconciles, do not claim failure.
                result = {"id": aid, "status": "failed", "reason": "temporary_failure", "retryable": True}
                latest = await db.assets.find_one({"id": aid}, {"_id": 0, MARKERS: 1})
                if _find_marker(latest, operation_id):
                    result = {"id": aid, "status": "pending", "reason": "reconciliation_required"}
            await db.batch_operations.update_one({"_id": operation_id, "lease_token": token},
                {"$set": {f"results.{index}": result, "updated_at": now_utc().isoformat()}})
            if result["status"] == "applied":
                committed_ids.append(aid)
    finally:
        await db.batch_operations.update_one({"_id": operation_id, "lease_token": token},
            {"$unset": {"lease_token": "", "lease_until": ""}})
    # Reconcile again before reporting; projections are deliberately best effort.
    await _reconcile(operation)
    if committed_ids:
        from shared_utils import invalidate_asset_cache
        from meili_utils import jadwalkan_sync_id
        invalidate_asset_cache()
        jadwalkan_sync_id("assets", committed_ids)
        from routes.websocket import notify_asset_change
        counts_by_activity = {}
        async for asset in db.assets.find({"id": {"$in": committed_ids}}, {"activity_id": 1}):
            activity_id = asset.get("activity_id", "")
            counts_by_activity[activity_id] = counts_by_activity.get(activity_id, 0) + 1
        for activity_id, count in counts_by_activity.items():
            try:
                await notify_asset_change(activity_id, "batch_update", {"count": count, "operation_id": operation_id}, user.get("name") or user.get("username") or "system")
            except Exception:
                logger.warning("batch_v2 notification failed operation=%s", operation_id)
    return _response(await db.batch_operations.find_one({"_id": operation_id}))


async def resume(operation_id, user, session_id="unknown-session"):
    operation = await get_operation(operation_id, user)
    return await execute(operation["request"], user, session_id)
