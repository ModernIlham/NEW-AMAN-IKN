"""System Backup & Restore routes with background processing. Admin only."""
import io
import os
import json
import uuid
import asyncio
import zipfile
import logging
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from fastapi import APIRouter, HTTPException, Header, UploadFile, File
from fastapi.responses import StreamingResponse, FileResponse
from bson import ObjectId

from db import db, fs_bucket
from auth_utils import get_current_user

logger = logging.getLogger(__name__)
backup_router = APIRouter(prefix="/backup", tags=["backup"])

UPLOADS_DIR = Path(__file__).parent.parent / "uploads"
BACKUP_TEMP_DIR = Path(__file__).parent.parent / "backup_temp"
BACKUP_TEMP_DIR.mkdir(exist_ok=True)
# 3.4.0: + inventory_history & counters (tiket kegiatan) dalam backup
APP_VERSION = "3.4.0"

# NOTE: Collection names MUST match what the rest of the app uses.
# Historically `activities` was listed here by mistake — the real collection
# is `inventory_activities`. Keeping both for backward compat on restore.
#
# Cakupan backup saat ini:
#   - users, categories, inventory_activities (termasuk ticket_number,
#     status_pengesahan, pengesahan_dokumen metadata), assets (termasuk
#     pengguna_melekat_ke/nomor_bast/bast_file_id), report_settings,
#     audit_logs, compression_quotas, pdf_compression_quotas
#   - inventory_history: riwayat pengesahan per aset (dasar Kartu Inventarisasi)
#   - counters: sequence nomor tiket kegiatan (INV-{tahun}-{seq}) — _id string
#     dipertahankan (lihat KEEP_ID_COLLECTIONS)
#   - GridFS (fs.files + fs.chunks): SEMUA file biner — foto aset, dokumen
#     kegiatan, dokumen pengesahan (PDF), dan dokumen BAST memakai satu
#     bucket default `fs` (db.py), jadi export_gridfs otomatis mencakup semuanya
#   - uploads/: file di disk (logo laporan dll.)
BACKUP_COLLECTIONS = [
    "users", "categories", "inventory_activities", "assets",
    "report_settings", "audit_logs",
    "compression_quotas", "pdf_compression_quotas",
    "inventory_history", "counters",
]
# Koleksi yang _id-nya bermakna (bukan ObjectId acak) dan harus ikut
# di-backup/restore: counters memakai _id string "inventory_activity_ticket_{tahun}".
KEEP_ID_COLLECTIONS = {"counters"}
# Legacy name → canonical name map (used when reading older backups)
LEGACY_COLLECTION_ALIASES = {
    "activities": "inventory_activities",
}
# Sengaja TIDAK di-backup (transient/derivable):
#   - row_locks: lock edit per baris, TTL 60 dtk — tidak bermakna lintas restore
#   - otp_store: OTP registrasi, TTL 11 menit
#   - backup_jobs: progress job backup/restore itu sendiri
#   - idempotency_keys: dedup replay antrian offline, TTL 24 jam — hanya valid
#     terhadap state DB saat key dibuat; membawa key ke DB hasil restore justru
#     bisa menelan save yang sah
#   - ws_events: capped collection bus event WebSocket (realtime, best-effort)
# Semua index (termasuk TTL) dibangun ulang oleh indexes.create_indexes()
# setelah restore dan pada setiap startup server.
SKIP_COLLECTIONS = ["row_locks", "otp_store", "backup_jobs", "idempotency_keys", "ws_events"]

# In-memory lock to prevent concurrent backup/restore
_active_lock = asyncio.Lock()


def serialize_doc(doc, keep_id: bool = False):
    """Convert MongoDB doc to JSON-serializable dict.

    keep_id: pertahankan `_id` (sebagai string) — wajib untuk koleksi yang
    _id-nya bermakna (mis. `counters`); tanpa ini restore akan menghasilkan
    dokumen counter tanpa key sehingga sequence tiket rusak.
    """
    if doc is None:
        return None
    result = {}
    for k, v in doc.items():
        if k == "_id" and not keep_id:
            continue
        if isinstance(v, ObjectId):
            result[k] = str(v)
        elif isinstance(v, datetime):
            result[k] = v.isoformat()
        elif isinstance(v, list):
            result[k] = [serialize_doc(i) if isinstance(i, dict) else (str(i) if isinstance(i, ObjectId) else i) for i in v]
        elif isinstance(v, dict):
            result[k] = serialize_doc(v)
        else:
            result[k] = v
    return result


async def require_admin(authorization: str):
    user = await get_current_user(authorization)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Hanya admin yang dapat mengakses fitur backup")
    return user


async def update_job(job_id: str, **fields):
    """Update backup job progress in MongoDB."""
    fields["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.backup_jobs.update_one({"job_id": job_id}, {"$set": fields})


async def cleanup_stale_jobs():
    """Mark jobs that have been running for > 30 minutes as failed."""
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    await db.backup_jobs.update_many(
        {"status": "running", "started_at": {"$lt": cutoff}},
        {"$set": {"status": "failed", "error": "Timeout: proses terlalu lama", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )


async def cleanup_old_files():
    """Remove backup temp files older than 1 hour."""
    if not BACKUP_TEMP_DIR.exists():
        return
    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    for f in BACKUP_TEMP_DIR.iterdir():
        if f.is_file():
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                try:
                    f.unlink()
                except Exception:
                    pass


async def repair_ticket_counters():
    """Pastikan counter tiket kegiatan >= sequence tertinggi yang sudah terpakai.

    Dipanggil setelah restore: backup lama (< 3.4.0) tidak membawa counters.json,
    padahal koleksi `counters` ikut di-wipe saat restore. Tanpa perbaikan ini
    kegiatan baru bisa mendapat nomor tiket duplikat (INV-{tahun}-0001 lagi).
    Aman dipanggil kapan pun ($max hanya menaikkan, tidak pernah menurunkan).
    """
    seq_by_year = {}
    cursor = db.inventory_activities.find(
        {"ticket_number": {"$regex": "^INV-"}}, {"_id": 0, "ticket_number": 1}
    )
    async for act in cursor:
        parts = str(act.get("ticket_number", "")).split("-")
        if len(parts) != 3:
            continue
        try:
            year, seq = int(parts[1]), int(parts[2])
        except ValueError:
            continue
        if seq > seq_by_year.get(year, 0):
            seq_by_year[year] = seq
    for year, seq in seq_by_year.items():
        await db.counters.update_one(
            {"_id": f"inventory_activity_ticket_{year}"},
            {"$max": {"seq": seq}},
            upsert=True,
        )
    if seq_by_year:
        logger.info(f"Ticket counters repaired: {seq_by_year}")


# ============================================================================
# GRIDFS BACKUP / RESTORE HELPERS
# ============================================================================
# GridFS stores photos in two collections: `fs.files` (metadata) and
# `fs.chunks` (raw binary data). A JSON dump is awkward for binary payloads,
# so we write each GridFS file as a standalone binary blob inside the ZIP and
# ship a `gridfs/manifest.json` that records metadata + per-file IDs.

async def export_gridfs(zf: zipfile.ZipFile, progress_cb=None) -> int:
    """Stream every GridFS file into zf as `gridfs/<file_id>.bin` + return count.

    progress_cb is an optional async callable(count_so_far) for progress updates.
    """
    manifest = []
    count = 0
    async for meta in db["fs.files"].find({}):
        file_id = str(meta["_id"])
        out_name = f"gridfs/{file_id}.bin"
        # Read the full file from GridFS into memory (photos are typically < 2MB each)
        try:
            stream = await fs_bucket.open_download_stream(meta["_id"])
            data = await stream.read()
        except Exception as e:
            logger.warning(f"GridFS export: skip file {file_id}: {e}")
            continue
        zf.writestr(out_name, data)
        manifest.append({
            "_id": file_id,
            "filename": meta.get("filename", file_id),
            "length": meta.get("length", len(data)),
            "chunkSize": meta.get("chunkSize", 261120),
            "uploadDate": meta.get("uploadDate").isoformat() if meta.get("uploadDate") else None,
            "contentType": meta.get("contentType"),
            "metadata": meta.get("metadata"),
        })
        count += 1
        if count % 25 == 0:
            if progress_cb:
                await progress_cb(count)
            await asyncio.sleep(0)
    zf.writestr("gridfs/manifest.json", json.dumps(manifest, ensure_ascii=False, default=str))
    return count


async def import_gridfs(zf: zipfile.ZipFile, progress_cb=None) -> int:
    """Wipe existing GridFS and re-upload every file listed in gridfs/manifest.json.

    Preserves the original `_id` so that asset documents still resolve
    (photo_gridfs_ids refer to these ObjectIds).
    """
    if "gridfs/manifest.json" not in zf.namelist():
        # Legacy backup without GridFS section — skip silently.
        return 0

    # Wipe existing GridFS
    await db["fs.files"].delete_many({})
    await db["fs.chunks"].delete_many({})

    manifest = json.loads(zf.read("gridfs/manifest.json"))
    restored = 0
    for entry in manifest:
        file_id = entry["_id"]
        blob_name = f"gridfs/{file_id}.bin"
        if blob_name not in zf.namelist():
            logger.warning(f"GridFS import: missing blob for {file_id}")
            continue
        try:
            data = zf.read(blob_name)
            oid = ObjectId(file_id) if ObjectId.is_valid(file_id) else file_id
            stream = fs_bucket.open_upload_stream_with_id(
                oid,
                entry.get("filename") or str(file_id),
                metadata=entry.get("metadata"),
            )
            await stream.write(data)
            await stream.close()
            restored += 1
            if restored % 25 == 0:
                if progress_cb:
                    await progress_cb(restored)
                await asyncio.sleep(0)
        except Exception as e:
            logger.error(f"GridFS import: failed to restore {file_id}: {e}")
    return restored


# ============================================================================
# BACKGROUND BACKUP TASK
# ============================================================================

async def run_backup_task(job_id: str, username: str):
    """Background task that creates backup ZIP with progress tracking."""
    try:
        await update_job(job_id, status="running", progress=0, message="Memulai proses backup...")

        total_steps = len(BACKUP_COLLECTIONS) + 3  # collections + gridfs + files + finalize
        current_step = 0
        stats = {}

        zip_path = BACKUP_TEMP_DIR / f"{job_id}.zip"

        with zipfile.ZipFile(str(zip_path), 'w', zipfile.ZIP_DEFLATED) as zf:
            for col_name in BACKUP_COLLECTIONS:
                current_step += 1
                pct = int((current_step / total_steps) * 85)
                await update_job(job_id, progress=pct, message=f"Backup koleksi: {col_name}...")

                collection = db[col_name]
                docs = []
                async for doc in collection.find({}):
                    docs.append(serialize_doc(doc, keep_id=col_name in KEEP_ID_COLLECTIONS))
                stats[col_name] = len(docs)
                zf.writestr(f"{col_name}.json", json.dumps(docs, ensure_ascii=False, default=str))
                logger.info(f"Backup [{job_id}]: {col_name} = {len(docs)} docs")
                await asyncio.sleep(0)

            # Export GridFS photos (fs.files + fs.chunks reconstructed as binaries)
            current_step += 1
            await update_job(job_id, progress=88, message="Backup foto GridFS...")

            async def _gridfs_progress(n):
                await update_job(job_id, progress=88, message=f"Backup foto GridFS ({n} foto)...")

            gridfs_count = await export_gridfs(zf, progress_cb=_gridfs_progress)
            stats["gridfs_files"] = gridfs_count
            logger.info(f"Backup [{job_id}]: gridfs = {gridfs_count} files")

            # Export file uploads
            current_step += 1
            await update_job(job_id, progress=92, message="Backup file uploads...")
            file_count = 0
            if UPLOADS_DIR.exists():
                for file_path in UPLOADS_DIR.rglob("*"):
                    if file_path.is_file():
                        rel_path = file_path.relative_to(UPLOADS_DIR)
                        zf.write(file_path, f"uploads/{rel_path}")
                        file_count += 1
                        if file_count % 50 == 0:
                            await asyncio.sleep(0)

            # Write metadata
            metadata = {
                "version": APP_VERSION,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": username,
                "collections": stats,
                "total_records": sum(v for k, v in stats.items() if k != "gridfs_files"),
                "gridfs_files": gridfs_count,
                "upload_files": file_count,
            }
            zf.writestr("metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2))

        file_size = zip_path.stat().st_size
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"backup_{timestamp}.zip"

        await update_job(
            job_id, status="completed", progress=100,
            message="Backup selesai! Siap diunduh.",
            filename=filename,
            file_size=file_size,
            stats=stats,
            total_records=sum(v for k, v in stats.items() if k != "gridfs_files"),
            gridfs_files=gridfs_count,
            upload_files=file_count,
        )
        logger.info(f"Backup [{job_id}] complete: {filename} ({stats}, {file_count} files, {gridfs_count} gridfs)")

    except Exception as e:
        logger.error(f"Backup [{job_id}] failed: {e}")
        await update_job(job_id, status="failed", progress=0, error=str(e), message=f"Backup gagal: {str(e)}")
        # Cleanup partial file
        zip_path = BACKUP_TEMP_DIR / f"{job_id}.zip"
        if zip_path.exists():
            zip_path.unlink(missing_ok=True)


# ============================================================================
# BACKGROUND RESTORE TASK
# ============================================================================

async def run_restore_task(job_id: str, zip_path: Path, username: str):
    """Background task that restores from backup ZIP with progress tracking."""
    try:
        await update_job(job_id, status="running", progress=5, message="Memvalidasi file backup...")

        # Validate ZIP structure
        with zipfile.ZipFile(str(zip_path), 'r') as zf:
            names = zf.namelist()
            if "metadata.json" not in names:
                await update_job(job_id, status="failed", error="metadata.json tidak ditemukan", message="File backup tidak valid")
                return

            metadata = json.loads(zf.read("metadata.json"))

            # Accept legacy alias names for required collections (e.g. "activities" → "inventory_activities")
            required = ["users", "categories", "assets"]
            missing = [c for c in required if f"{c}.json" not in names]
            # inventory_activities may appear under legacy alias "activities.json"
            if "inventory_activities.json" not in names and "activities.json" not in names:
                missing.append("inventory_activities")
            if missing:
                await update_job(job_id, status="failed", error=f"Data tidak lengkap: {', '.join(missing)}", message="File backup tidak lengkap")
                return

        await update_job(job_id, progress=10, message="Membuat safety backup...")

        # Create safety backup of current data (collections + GridFS metadata)
        safety_data = {}
        for i, col_name in enumerate(BACKUP_COLLECTIONS):
            docs = []
            async for doc in db[col_name].find({}):
                docs.append(serialize_doc(doc, keep_id=col_name in KEEP_ID_COLLECTIONS))
            safety_data[col_name] = docs
            pct = 10 + int(((i + 1) / len(BACKUP_COLLECTIONS)) * 15)
            await update_job(job_id, progress=pct, message=f"Safety backup: {col_name}...")
            await asyncio.sleep(0)

        # Safety backup GridFS: snapshot file_ids + binaries into a temp zip so rollback can repopulate
        safety_gridfs_zip = BACKUP_TEMP_DIR / f"safety_{job_id}.zip"
        try:
            with zipfile.ZipFile(str(safety_gridfs_zip), 'w', zipfile.ZIP_STORED) as sz:
                await export_gridfs(sz)
        except Exception as e:
            logger.warning(f"Safety GridFS snapshot failed (will proceed without full rollback): {e}")

        await update_job(job_id, progress=30, message="Memulihkan data koleksi...")

        # Perform restore
        restore_stats = {}
        try:
            with zipfile.ZipFile(str(zip_path), 'r') as zf:
                zip_names = set(zf.namelist())
                for i, col_name in enumerate(BACKUP_COLLECTIONS):
                    pct = 30 + int(((i + 1) / len(BACKUP_COLLECTIONS)) * 35)
                    await update_job(job_id, progress=pct, message=f"Restore: {col_name}...")

                    await db[col_name].delete_many({})

                    json_file = f"{col_name}.json"
                    # Try canonical name first, then any legacy alias
                    if json_file not in zip_names:
                        for legacy, canonical in LEGACY_COLLECTION_ALIASES.items():
                            if canonical == col_name and f"{legacy}.json" in zip_names:
                                json_file = f"{legacy}.json"
                                break

                    if json_file in zip_names:
                        docs = json.loads(zf.read(json_file))
                        # Normalize: ensure every asset has a `version` field (backfills legacy data)
                        if col_name == "assets":
                            for d in docs:
                                if "version" not in d or d.get("version") is None:
                                    d["version"] = 1
                        if docs:
                            await db[col_name].insert_many(docs)
                        restore_stats[col_name] = len(docs)
                    else:
                        restore_stats[col_name] = 0
                    logger.info(f"Restore [{job_id}]: {col_name} = {restore_stats[col_name]} docs")
                    await asyncio.sleep(0)

                # Backup lama tidak membawa counters.json — bangun ulang sequence
                # tiket dari ticket_number kegiatan yang barusan direstore agar
                # nomor tiket baru tidak duplikat.
                await repair_ticket_counters()

                # Restore GridFS (photos stored outside regular collections)
                await update_job(job_id, progress=70, message="Memulihkan foto (GridFS)...")
                gridfs_restored = 0
                try:
                    async def _gr_progress(n):
                        await update_job(job_id, progress=70, message=f"Memulihkan foto ({n})...")
                    gridfs_restored = await import_gridfs(zf, progress_cb=_gr_progress)
                    logger.info(f"Restore [{job_id}]: gridfs = {gridfs_restored} files")
                except Exception as e:
                    logger.warning(f"Restore [{job_id}] GridFS import warning: {e}")

                # Restore upload files
                await update_job(job_id, progress=85, message="Memulihkan file uploads...")
                upload_files_restored = 0
                for name in zf.namelist():
                    if name.startswith("uploads/") and not name.endswith("/"):
                        rel_path = name[len("uploads/"):]
                        target = UPLOADS_DIR / rel_path
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with open(target, 'wb') as f:
                            f.write(zf.read(name))
                        upload_files_restored += 1
                        if upload_files_restored % 50 == 0:
                            await asyncio.sleep(0)

        except Exception as e:
            # ROLLBACK
            logger.error(f"Restore [{job_id}] failed, rolling back: {e}")
            await update_job(job_id, progress=90, message="Restore gagal, mengembalikan data...")
            try:
                for col_name in BACKUP_COLLECTIONS:
                    await db[col_name].delete_many({})
                    if safety_data.get(col_name):
                        await db[col_name].insert_many(safety_data[col_name])
                # Rollback GridFS
                if safety_gridfs_zip.exists():
                    with zipfile.ZipFile(str(safety_gridfs_zip), 'r') as sz:
                        await import_gridfs(sz)
                logger.info(f"Restore [{job_id}] rollback completed")
            except Exception as rb_err:
                logger.error(f"Restore [{job_id}] rollback also failed: {rb_err}")

            await update_job(job_id, status="failed", error=str(e), message="Restore gagal. Data telah dikembalikan ke kondisi semula.")
            return
        finally:
            # Always cleanup safety snapshot zip
            if safety_gridfs_zip.exists():
                safety_gridfs_zip.unlink(missing_ok=True)

        # Rebuild indexes
        await update_job(job_id, progress=95, message="Membangun ulang index database...")
        try:
            from indexes import create_indexes
            await create_indexes()
        except Exception as e:
            logger.warning(f"Index rebuild warning: {e}")

        await update_job(
            job_id, status="completed", progress=100,
            message="Data berhasil dipulihkan!",
            restore_stats=restore_stats,
            total_restored=sum(restore_stats.values()),
            gridfs_files_restored=gridfs_restored,
            upload_files_restored=upload_files_restored,
            backup_metadata={
                "created_at": metadata.get("created_at"),
                "created_by": metadata.get("created_by"),
                "version": metadata.get("version"),
            },
        )
        logger.info(f"Restore [{job_id}] complete: {sum(restore_stats.values())} records + {gridfs_restored} gridfs files")

    except Exception as e:
        logger.error(f"Restore [{job_id}] unexpected error: {e}")
        await update_job(job_id, status="failed", error=str(e), message=f"Error: {str(e)}")
    finally:
        # Cleanup uploaded zip
        if zip_path.exists():
            zip_path.unlink(missing_ok=True)


# ============================================================================
# API ENDPOINTS
# ============================================================================

@backup_router.get("/stats")
async def get_backup_stats(authorization: str = Header(None)):
    """Get current data statistics for backup preview."""
    await require_admin(authorization)
    stats = {}
    for col_name in BACKUP_COLLECTIONS:
        stats[col_name] = await db[col_name].count_documents({})
    return {"collections": stats, "total_records": sum(stats.values())}


@backup_router.post("/start")
async def start_backup(authorization: str = Header(None)):
    """Start a background backup job. Returns job_id for progress tracking."""
    user = await require_admin(authorization)
    await cleanup_stale_jobs()
    await cleanup_old_files()

    # Check for already running jobs
    active = await db.backup_jobs.find_one({"status": "running"}, {"_id": 0})
    if active:
        raise HTTPException(status_code=409, detail="Sudah ada proses backup/restore yang sedang berjalan")

    job_id = str(uuid.uuid4())[:12]
    job = {
        "job_id": job_id,
        "type": "backup",
        "status": "queued",
        "progress": 0,
        "message": "Menunggu mulai...",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "started_by": user.get("username"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.backup_jobs.insert_one(job)

    asyncio.create_task(run_backup_task(job_id, user.get("username")))
    logger.info(f"Backup job {job_id} started by {user.get('username')}")

    return {"job_id": job_id, "message": "Proses backup dimulai di background"}


@backup_router.post("/restore/start")
async def start_restore(
    file: UploadFile = File(...),
    authorization: str = Header(None),
):
    """Upload backup file and start background restore. Returns job_id."""
    user = await require_admin(authorization)
    await cleanup_stale_jobs()

    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="File harus berformat ZIP")

    active = await db.backup_jobs.find_one({"status": "running"}, {"_id": 0})
    if active:
        raise HTTPException(status_code=409, detail="Sudah ada proses backup/restore yang sedang berjalan")

    job_id = str(uuid.uuid4())[:12]

    # Save uploaded file to temp
    zip_path = BACKUP_TEMP_DIR / f"restore_{job_id}.zip"
    try:
        content = await file.read()
        with open(zip_path, 'wb') as f:
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gagal menyimpan file: {str(e)}")

    # Quick validation
    try:
        with zipfile.ZipFile(str(zip_path), 'r') as zf:
            if "metadata.json" not in zf.namelist():
                zip_path.unlink(missing_ok=True)
                raise HTTPException(status_code=400, detail="File backup tidak valid: metadata.json tidak ditemukan")
    except zipfile.BadZipFile:
        zip_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="File ZIP rusak atau tidak valid")
    except HTTPException:
        raise

    job = {
        "job_id": job_id,
        "type": "restore",
        "status": "queued",
        "progress": 0,
        "message": "Menunggu mulai...",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "started_by": user.get("username"),
        "source_file": file.filename,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.backup_jobs.insert_one(job)

    asyncio.create_task(run_restore_task(job_id, zip_path, user.get("username")))
    logger.info(f"Restore job {job_id} started by {user.get('username')}")

    return {"job_id": job_id, "message": "Proses restore dimulai di background"}


@backup_router.get("/progress/{job_id}")
async def get_job_progress(job_id: str, authorization: str = Header(None)):
    """Get progress of a backup/restore job."""
    await require_admin(authorization)
    job = await db.backup_jobs.find_one({"job_id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job tidak ditemukan")
    return job


@backup_router.get("/active")
async def get_active_job(authorization: str = Header(None)):
    """Get the currently active (running/queued) job, if any."""
    await require_admin(authorization)
    await cleanup_stale_jobs()
    job = await db.backup_jobs.find_one(
        {"status": {"$in": ["running", "queued"]}},
        {"_id": 0},
        sort=[("started_at", -1)]
    )
    # Also check recently completed (last 5 min) for download
    if not job:
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        job = await db.backup_jobs.find_one(
            {"status": "completed", "updated_at": {"$gt": cutoff}},
            {"_id": 0},
            sort=[("updated_at", -1)]
        )
    # Also check recently failed
    if not job:
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
        job = await db.backup_jobs.find_one(
            {"status": "failed", "updated_at": {"$gt": cutoff}},
            {"_id": 0},
            sort=[("updated_at", -1)]
        )
    return job or {"status": "idle"}


@backup_router.get("/download/{job_id}")
async def download_backup(
    job_id: str,
    authorization: str = Header(None),
    token: str | None = None,
):
    """Download the completed backup ZIP file.

    Accepts either an `Authorization: Bearer <token>` header (for axios/fetch)
    OR a `?token=<token>` query param (so the browser can follow a plain
    anchor/`window.open()` link without needing to keep the large file in
    memory — the blob approach was silently failing for multi-hundred-MB
    backups on the deployed ingress).
    """
    # Fall back to query-param token when the client can't set headers
    # (native browser navigation / anchor click).
    effective_auth = authorization
    if not effective_auth and token:
        effective_auth = f"Bearer {token}"
    await require_admin(effective_auth)

    job = await db.backup_jobs.find_one({"job_id": job_id, "type": "backup", "status": "completed"}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Backup tidak ditemukan atau belum selesai")

    zip_path = BACKUP_TEMP_DIR / f"{job_id}.zip"
    if not zip_path.exists():
        raise HTTPException(status_code=404, detail="File backup sudah dihapus (expired)")

    filename = job.get("filename", f"backup_{job_id}.zip")
    return FileResponse(
        path=str(zip_path),
        media_type="application/zip",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@backup_router.post("/dismiss/{job_id}")
async def dismiss_job(job_id: str, authorization: str = Header(None)):
    """Dismiss/acknowledge a completed or failed job so it stops showing."""
    await require_admin(authorization)
    await db.backup_jobs.update_one(
        {"job_id": job_id, "status": {"$in": ["completed", "failed"]}},
        {"$set": {"status": "dismissed", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    # Cleanup file
    for pattern in [f"{job_id}.zip", f"restore_{job_id}.zip"]:
        p = BACKUP_TEMP_DIR / pattern
        if p.exists():
            p.unlink(missing_ok=True)
    return {"ok": True}


# Legacy endpoints (kept for backward compatibility but redirect to new flow)
@backup_router.get("/create")
async def create_backup_legacy(authorization: str = Header(None)):
    """Legacy: synchronous backup. Still works but prefer /start for background."""
    user = await require_admin(authorization)
    logger.info(f"Legacy backup by {user.get('username')}")
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        stats = {}
        for col_name in BACKUP_COLLECTIONS:
            docs = []
            async for doc in db[col_name].find({}):
                docs.append(serialize_doc(doc, keep_id=col_name in KEEP_ID_COLLECTIONS))
            stats[col_name] = len(docs)
            zf.writestr(f"{col_name}.json", json.dumps(docs, ensure_ascii=False, default=str))
        if UPLOADS_DIR.exists():
            for file_path in UPLOADS_DIR.rglob("*"):
                if file_path.is_file():
                    rel_path = file_path.relative_to(UPLOADS_DIR)
                    zf.write(file_path, f"uploads/{rel_path}")
        metadata = {
            "version": APP_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": user.get("username"),
            "collections": stats,
            "total_records": sum(stats.values()),
        }
        zf.writestr("metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2))
    zip_buffer.seek(0)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"backup_{timestamp}.zip"
    return StreamingResponse(zip_buffer, media_type="application/zip", headers={"Content-Disposition": f"attachment; filename={filename}"})


@backup_router.post("/restore")
async def restore_backup_legacy(file: UploadFile = File(...), authorization: str = Header(None)):
    """Legacy: synchronous restore. Still works but prefer /restore/start for background."""
    await require_admin(authorization)  # auth side-effect only
    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="File harus berformat ZIP")
    try:
        content = await file.read()
        zip_buffer = io.BytesIO(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gagal membaca file: {str(e)}")
    try:
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            names = zf.namelist()
            if "metadata.json" not in names:
                raise HTTPException(status_code=400, detail="File backup tidak valid")
            metadata = json.loads(zf.read("metadata.json"))
            missing = [c for c in ["users", "categories", "activities", "assets"] if f"{c}.json" not in names]
            if missing:
                raise HTTPException(status_code=400, detail=f"Data tidak lengkap: {', '.join(missing)}")
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="File ZIP rusak")
    except HTTPException:
        raise
    safety_data = {}
    for col_name in BACKUP_COLLECTIONS:
        docs = []
        async for doc in db[col_name].find({}):
            docs.append(serialize_doc(doc, keep_id=col_name in KEEP_ID_COLLECTIONS))
        safety_data[col_name] = docs
    restore_stats = {}
    upload_files_restored = 0
    try:
        zip_buffer.seek(0)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            for col_name in BACKUP_COLLECTIONS:
                await db[col_name].delete_many({})
                json_file = f"{col_name}.json"
                if json_file in zf.namelist():
                    docs = json.loads(zf.read(json_file))
                    if docs:
                        await db[col_name].insert_many(docs)
                    restore_stats[col_name] = len(docs)
                else:
                    restore_stats[col_name] = 0
            for name in zf.namelist():
                if name.startswith("uploads/") and not name.endswith("/"):
                    rel_path = name[len("uploads/"):]
                    target = UPLOADS_DIR / rel_path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with open(target, 'wb') as f:
                        f.write(zf.read(name))
                    upload_files_restored += 1
    except Exception as e:
        for col_name in BACKUP_COLLECTIONS:
            await db[col_name].delete_many({})
            if safety_data.get(col_name):
                await db[col_name].insert_many(safety_data[col_name])
        raise HTTPException(status_code=500, detail=f"Restore gagal, data dikembalikan. Error: {str(e)}")
    try:
        await repair_ticket_counters()
    except Exception:
        pass
    try:
        from indexes import create_indexes
        await create_indexes()
    except Exception:
        pass
    return {
        "message": "Data berhasil dipulihkan",
        "backup_metadata": metadata,
        "restored": restore_stats,
        "total_restored": sum(restore_stats.values()),
        "upload_files_restored": upload_files_restored,
    }
