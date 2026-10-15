"""System reset uses the restore journal, archive engine and recovery contract.

The HTTP façade still validates central-admin confirmation. This coordinator
owns admission/drain/safety/rollback; it never opens a partially reset dataset.
"""
import asyncio
import contextlib
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import uuid
import zipfile

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from backup_archive import (CHUNK_SIZE, iter_json_documents,
                            validate_archive, write_manifest)
from backup_utils import (RESET_KEEP_COLLECTIONS, collections_from_backup,
                          gridfs_dipertahankan_saat_reset)


def _reference_candidates(value):
    """Conservatively keep IDs mentioned by retained configuration/master data.

    Known owner paths are already validated by archive preflight. This walk also
    preserves future/nested owner fields and media URLs without relying solely
    on a blob's legacy metadata classification. False positives retain a blob;
    they never remove a referenced file.
    """
    if isinstance(value, dict):
        for nested in value.values():
            yield from _reference_candidates(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _reference_candidates(nested)
    elif isinstance(value, str):
        yield value
        yield from re.findall(r"(?<![0-9a-fA-F])[0-9a-fA-F]{24}(?![0-9a-fA-F])", value)


def _copy_entry(source, destination, name):
    with source.open(name) as reader, destination.open(name, "w", force_zip64=True) as writer:
        shutil.copyfileobj(reader, writer, CHUNK_SIZE)


def build_reset_archive(safety_path, target_path):
    """Build/verify the intended empty dataset from the immutable safety copy."""
    target_path = Path(target_path)
    owned = False
    try:
        with zipfile.ZipFile(safety_path) as safety:
            preflight = validate_archive(safety, False, True)
            media = preflight["gridfs"]
            available = {entry["_id"] for entry in media}
            referenced = set()
            stats = {}
            descriptor = os.open(target_path, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
            owned = True
            with os.fdopen(descriptor, "w+b") as raw, zipfile.ZipFile(raw, "w", zipfile.ZIP_DEFLATED) as target:
                for collection in collections_from_backup(safety.namelist()):
                    name = collection + ".json"
                    if collection in RESET_KEEP_COLLECTIONS:
                        with safety.open(name) as reader:
                            for document in iter_json_documents(reader):
                                referenced.update(candidate for candidate in _reference_candidates(document)
                                                  if candidate in available)
                        _copy_entry(safety, target, name)
                        stats[collection] = preflight["collections"][collection]
                    else:
                        target.writestr(name, "[]")
                        stats[collection] = 0
                retained = [entry for entry in media if entry["_id"] in referenced
                            or gridfs_dipertahankan_saat_reset(entry.get("metadata"))]
                for entry in retained:
                    _copy_entry(safety, target, "gridfs/" + entry["_id"] + ".bin")
                target.writestr("gridfs/manifest.json", json.dumps(retained, ensure_ascii=False))
                uploads = 0
                for name in safety.namelist():
                    if name.startswith("uploads/") and not name.endswith("/"):
                        _copy_entry(safety, target, name)
                        uploads += 1
                target.writestr("metadata.json", json.dumps({
                    "archive_schema_version": 1, "purpose": "system_reset",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }))
                write_manifest(target, stats, len(retained), uploads)
            with target_path.open("rb") as result:
                os.fsync(result.fileno())
            with zipfile.ZipFile(target_path) as target:
                validate_archive(target, True, True)
            directory = os.open(target_path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        return {**{name: count for name, count in preflight["collections"].items()
                    if name not in RESET_KEEP_COLLECTIONS},
                "gridfs_files": len(media) - len(retained)}
    except BaseException:
        if owned:
            target_path.unlink(missing_ok=True)
        raise


async def reset_system(username):
    """Run a synchronous reset; a killed process remains recoverable via CLI."""
    import routes.backup as backup
    from dataset_epoch import rotate_generation
    from pemeliharaan import current_writer_lease_id, _CACHE_TTL
    from portal_auth import cabut_semua_portal_akses

    database = backup.db
    await backup._guard_recovery()
    # The startup index helper reports failures rather than stopping the app.
    # Destructive admission must prove its unique single-flight gate exists.
    try:
        await database.backup_jobs.create_index("active_lock", unique=True,
            partialFilterExpression={"active_lock": {"$exists": True}},
            name="backup_jobs_active_lock_singleflight")
    except Exception as error:
        raise HTTPException(503, "Gerbang backup/reset tidak tersedia; tidak ada data dihapus") from error
    job_id = "reset-" + uuid.uuid4().hex[:16]
    source = backup.BACKUP_TEMP_DIR / ("reset_" + job_id + ".zip")
    safety = backup.BACKUP_TEMP_DIR / ("safety_data_" + job_id + ".zip")
    now = datetime.now(timezone.utc).isoformat()
    try:
        await database.backup_jobs.insert_one({"job_id": job_id, "type": "restore",
            "operation": "system_reset", "status": "running", "active_lock": "GLOBAL",
            "progress": 0, "started_at": now, "updated_at": now,
            "started_by": username, "message": "Menyiapkan reset aman..."})
    except DuplicateKeyError:
        raise HTTPException(409, "Sudah ada proses backup/restore/reset yang berjalan") from None
    claimed = destructive = verified_terminal = False
    safety_created = source_created = False
    heartbeat = None
    try:
        await backup._claim_restore_control(job_id, username, source)
        claimed = True
        heartbeat = asyncio.create_task(backup._restore_heartbeat(job_id))
        await backup._wait_writer_drain(exclude_lease_id=current_writer_lease_id())
        await asyncio.sleep(_CACHE_TTL + 0.05)
        await cabut_semua_portal_akses("Reset sistem", database=database)
        safety = await backup.create_safety_archive(job_id, username)
        safety_created = True
        deleted = await asyncio.to_thread(build_reset_archive, safety, source)
        source_created = True
        await backup._restore_state(job_id, "restoring", destructive_started=True)
        destructive = True
        with zipfile.ZipFile(source) as archive:
            stats, _, _ = await backup._apply_archive(archive, job_id,
                                                      preserve_collections=RESET_KEEP_COLLECTIONS)
            await backup._finish_recovered_data(archive, stats)
        await backup.update_job(job_id, status="completed", progress=100, recovery_required=False,
                                message="Reset berhasil dan terverifikasi", deleted=deleted)
        await backup._restore_state(job_id, "completed", verified_at=datetime.now(timezone.utc).isoformat())
        verified_terminal = True
        return {"message": "Semua data berhasil dihapus. Sistem telah direset.",
                "deleted": deleted, "job_id": job_id}
    except BaseException as error:
        if claimed and destructive:
            try:
                await backup._restore_state(job_id, "rolling_back", error=str(error))
                await rotate_generation(database, "system_reset_rollback")
                with zipfile.ZipFile(safety) as archive:
                    await asyncio.to_thread(validate_archive, archive, False, True)
                    stats, _, _ = await backup._apply_archive(archive, job_id)
                    await backup._finish_recovered_data(archive, stats)
                await backup.update_job(job_id, status="failed", error=str(error), recovery_required=False,
                                        message="Reset gagal; safety snapshot berhasil dipulihkan")
                await backup._restore_state(job_id, "rolled_back", verified_at=datetime.now(timezone.utc).isoformat())
                verified_terminal = True
            except BaseException as rollback_error:
                # Unknown Mongo write outcomes still leave the previous durable
                # restoring/rolling_back gate closed. Never delete its safety.
                with contextlib.suppress(Exception):
                    await backup._restore_state(job_id, "recovery_required", error=str(error),
                                                rollback_error=str(rollback_error))
                with contextlib.suppress(Exception):
                    await backup.update_job(job_id, status="failed", recovery_required=True,
                                            error=str(error), rollback_error=str(rollback_error))
        elif claimed:
            await backup.update_job(job_id, status="failed", error=str(error), recovery_required=False)
            await backup._restore_state(job_id, "aborted", error=str(error))
            verified_terminal = True
        else:
            await backup.update_job(job_id, status="failed", error=str(error))
        if not isinstance(error, Exception):
            raise
        if isinstance(error, HTTPException):
            raise
        detail = ("Reset gagal; safety snapshot telah dipulihkan dan diverifikasi" if destructive and verified_terminal
                  else "Reset gagal; layanan ditahan dan operator wajib memeriksa recovery" if destructive
                  else "Reset dibatalkan sebelum penghapusan data")
        raise HTTPException(500 if verified_terminal else 503, {"message": detail, "job_id": job_id}) from error
    finally:
        if heartbeat:
            heartbeat.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await heartbeat
        if verified_terminal or not claimed:
            if source_created:
                source.unlink(missing_ok=True)
            if safety_created:
                safety.unlink(missing_ok=True)
