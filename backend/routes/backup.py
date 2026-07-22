"""System Backup & Restore routes with background processing. Admin only."""
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
from fastapi.responses import FileResponse
from bson import ObjectId

from db import db, fs_bucket
from auth_utils import get_current_user

logger = logging.getLogger(__name__)
backup_router = APIRouter(prefix="/backup", tags=["backup"])

UPLOADS_DIR = Path(__file__).parent.parent / "uploads"
BACKUP_TEMP_DIR = Path(__file__).parent.parent / "backup_temp"
BACKUP_TEMP_DIR.mkdir(exist_ok=True)
# Arsip backup PERSISTEN di server (tidak kena pembersihan 1 jam) — diisi
# backup otomatis terjadwal & backup manual ber-opsi "arsipkan di server".
BACKUP_ARSIP_DIR = Path(__file__).parent.parent / "backup_arsip"
BACKUP_ARSIP_DIR.mkdir(exist_ok=True)
# 3.4.0: + inventory_history & counters (tiket kegiatan) dalam backup
# 3.5.0: reset mempertahankan GridFS tertaut koleksi RESET_KEEP (foto pegawai
#        krop+asli & spesimen TTD pegawai/pejabat) agar referensi tak yatim.
#        Backup/restore tetap mencakup SELURUH GridFS (tak berubah).
APP_VERSION = "3.5.0"

# Kebijakan koleksi DINAMIS (#290): daftar koleksi di-ENUMERASI dari DB (bukan
# hardcode) lewat backup_utils (logika MURNI & teruji unit), sehingga SETIAP
# koleksi/modul baru otomatis ikut ter-backup, ter-restore, & ter-reset.
from backup_utils import (  # noqa: E402
    SKIP_COLLECTIONS, KEEP_ID_COLLECTIONS, RESET_KEEP_COLLECTIONS,
    LEGACY_COLLECTION_ALIASES, arsip_untuk_dihapus, collections_to_process,
    collections_from_backup, nama_arsip_valid, saat_jadwal_tiba,
)


async def _app_collections():
    """Semua koleksi data aplikasi di DB saat ini (dinamis)."""
    return collections_to_process(await db.list_collection_names())

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

async def run_backup_task(job_id: str, username: str, arsipkan: str = ""):
    """Background task that creates backup ZIP with progress tracking.

    `arsipkan` ("otomatis"/"manual") = pindahkan ZIP hasil ke arsip persisten
    server (BACKUP_ARSIP_DIR) — tidak kena pembersihan berkas temp 1 jam.
    """
    from log_setup import set_job_id
    set_job_id(job_id)   # korelasi log ke JOB, bukan request pemicu (task latar)
    try:
        await update_job(job_id, status="running", progress=0, message="Memulai proses backup...")

        cols = await _app_collections()  # DINAMIS: mencakup semua modul
        total_steps = len(cols) + 3  # collections + gridfs + files + finalize
        current_step = 0
        stats = {}

        # Guard ruang disk: perkirakan kebutuhan dari total byte GridFS (foto ~tak
        # terkompres) + margin JSON/overhead; batalkan LEBIH AWAL bila ruang tak
        # cukup agar backup tak memenuhi disk VPS (berdampak seluruh aplikasi).
        try:
            agg = await db["fs.files"].aggregate(
                [{"$group": {"_id": None, "total": {"$sum": "$length"}}}]).to_list(1)
            gridfs_bytes = int((agg[0]["total"] if agg else 0) or 0)
        except Exception:
            gridfs_bytes = 0
        butuh = gridfs_bytes + (200 * 1024 * 1024)
        bebas = shutil.disk_usage(str(BACKUP_TEMP_DIR)).free
        if bebas < butuh:
            raise RuntimeError(
                f"Ruang disk tidak cukup untuk backup: perlu ~{butuh // (1024 * 1024)} MB, "
                f"tersedia {bebas // (1024 * 1024)} MB. Kosongkan arsip lama / ruang disk server.")

        zip_path = BACKUP_TEMP_DIR / f"{job_id}.zip"

        with zipfile.ZipFile(str(zip_path), 'w', zipfile.ZIP_DEFLATED) as zf:
            for col_name in cols:
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

        arsip_nama = ""
        if arsipkan in ("otomatis", "manual"):
            arsip_nama = f"backup_{arsipkan}_{timestamp}.zip"
            try:
                shutil.move(str(zip_path), str(BACKUP_ARSIP_DIR / arsip_nama))
                filename = arsip_nama
            except Exception as e:
                logger.warning(f"Backup [{job_id}]: gagal arsipkan ({e}) — file tetap di temp")
                arsip_nama = ""

        await update_job(
            job_id, status="completed", progress=100,
            message=("Backup selesai & tersimpan di arsip server." if arsip_nama
                     else "Backup selesai! Siap diunduh."),
            filename=filename,
            arsip_nama=arsip_nama,
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
    from log_setup import set_job_id
    set_job_id(job_id)   # korelasi log ke JOB, bukan request pemicu (task latar)
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

        # Create safety backup of current data (SEMUA koleksi aplikasi + GridFS)
        safety_cols = await _app_collections()
        safety_data = {}
        for i, col_name in enumerate(safety_cols):
            docs = []
            async for doc in db[col_name].find({}):
                docs.append(serialize_doc(doc, keep_id=col_name in KEEP_ID_COLLECTIONS))
            safety_data[col_name] = docs
            pct = 10 + int(((i + 1) / max(1, len(safety_cols))) * 15)
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

        # Perform restore — iterasi SEMUA koleksi yang ADA di backup (dinamis),
        # petakan nama legacy → kanonik, lalu wipe + isi ulang tiap koleksi.
        restore_stats = {}
        try:
            with zipfile.ZipFile(str(zip_path), 'r') as zf:
                zip_names = set(zf.namelist())
                backup_cols = collections_from_backup(zip_names)
                for i, zip_col in enumerate(backup_cols):
                    col_name = LEGACY_COLLECTION_ALIASES.get(zip_col, zip_col)
                    pct = 30 + int(((i + 1) / max(1, len(backup_cols))) * 35)
                    await update_job(job_id, progress=pct, message=f"Restore: {col_name}...")

                    await db[col_name].delete_many({})
                    docs = json.loads(zf.read(f"{zip_col}.json"))
                    # Normalize: pastikan setiap aset punya `version` (backfill data lama)
                    if col_name == "assets":
                        for d in docs:
                            if not d.get("version"):
                                d["version"] = 1
                    if docs:
                        await db[col_name].insert_many(docs)
                    restore_stats[col_name] = len(docs)
                    logger.info(f"Restore [{job_id}]: {col_name} = {len(docs)} docs")
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
                uploads_root = UPLOADS_DIR.resolve()
                for name in zf.namelist():
                    if name.startswith("uploads/") and not name.endswith("/"):
                        rel_path = name[len("uploads/"):]
                        target = (UPLOADS_DIR / rel_path).resolve()
                        # Cegah zip-slip / path traversal: target WAJIB di dalam
                        # UPLOADS_DIR (tolak entri absolut atau ber-"..").
                        if uploads_root != target and uploads_root not in target.parents:
                            logger.warning(f"Restore [{job_id}] tolak entri di luar uploads: {name}")
                            continue
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
                # Kembalikan SEMUA koleksi yang di-snapshot safety ke kondisi semula
                for col_name, docs in safety_data.items():
                    await db[col_name].delete_many({})
                    if docs:
                        await db[col_name].insert_many(docs)
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
    for col_name in await _app_collections():
        stats[col_name] = await db[col_name].count_documents({})
    return {"collections": stats, "total_records": sum(stats.values())}


@backup_router.post("/start")
async def start_backup(authorization: str = Header(None), arsipkan: bool = False):
    """Start a background backup job. Returns job_id for progress tracking.

    `arsipkan=true` = simpan hasil ke arsip persisten server (selain tetap
    bisa diunduh) — untuk cadangan yang menetap tanpa perlu mengunduh.
    """
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

    asyncio.create_task(run_backup_task(job_id, user.get("username"),
                                        arsipkan="manual" if arsipkan else ""))
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

    # Simpan berkas unggahan ke temp secara STREAMING (per-chunk 1 MB) — jangan
    # muat seluruh ZIP (bisa ratusan MB–GB karena berisi foto GridFS) ke RAM
    # dulu; itu vektor OOM di VPS kecil.
    zip_path = BACKUP_TEMP_DIR / f"restore_{job_id}.zip"
    try:
        with open(zip_path, 'wb') as f:
            while True:
                chunk = await file.read(1 << 20)  # 1 MB
                if not chunk:
                    break
                f.write(chunk)
    except Exception:
        logger.exception("Restore: gagal menyimpan file upload")
        zip_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Gagal menyimpan file backup")

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
    # Hasil yang diarsipkan berpindah ke arsip persisten — layani dari sana.
    if not zip_path.exists() and nama_arsip_valid(job.get("arsip_nama")):
        zip_path = BACKUP_ARSIP_DIR / job["arsip_nama"]
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


# ============================================================================
# ARSIP BACKUP DI SERVER + JADWAL OTOMATIS HARIAN (audit backup #407)
# ============================================================================
# Setelan tersimpan di report_settings {"type": "backup_otomatis"}:
#   aktif (bool) · jam ("HH:MM" WIB) · retensi (jumlah arsip dipertahankan)
#   · terakhir ("YYYY-MM-DD" — tanggal WIB backup otomatis terakhir jalan).
# Scheduler dipanggil dari startup server; klaim tanggal via find_one_and_update
# ATOMIK sehingga aman multi-worker (hanya satu worker yang menjalankan).

WIB = timezone(timedelta(hours=7))
_SETELAN_OTOMATIS_DEFAULT = {"aktif": False, "jam": "02:00", "retensi": 7,
                             "terakhir": ""}


def _daftar_arsip():
    out = []
    for p in sorted(BACKUP_ARSIP_DIR.iterdir() if BACKUP_ARSIP_DIR.exists() else []):
        if p.is_file() and nama_arsip_valid(p.name):
            st = p.stat()
            out.append({
                "nama": p.name,
                "ukuran": st.st_size,
                "waktu": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
                "jenis": "otomatis" if "_otomatis_" in p.name else "manual",
            })
    out.sort(key=lambda x: x["nama"], reverse=True)
    return out


def _terapkan_retensi(retensi: int):
    nama_semua = [a["nama"] for a in _daftar_arsip()]
    for nama in arsip_untuk_dihapus(nama_semua, retensi):
        try:
            (BACKUP_ARSIP_DIR / nama).unlink(missing_ok=True)
            logger.info(f"Retensi arsip backup: {nama} dihapus")
        except Exception as e:
            logger.warning(f"Retensi arsip backup gagal hapus {nama}: {e}")


async def _jalankan_backup_otomatis(retensi: int):
    """Satu siklus backup otomatis: job + tunggu selesai + terapkan retensi."""
    job_id = str(uuid.uuid4())[:12]
    await db.backup_jobs.insert_one({
        "job_id": job_id, "type": "backup", "status": "queued", "progress": 0,
        "message": "Backup otomatis terjadwal...",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "started_by": "backup-otomatis",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    await run_backup_task(job_id, "backup-otomatis", arsipkan="otomatis")
    # Terapkan retensi HANYA bila backup SUKSES — kalau gagal, JANGAN pangkas
    # arsip lama (menghindari kehilangan cadangan yang masih valid saat backup
    # baru gagal, mis. disk penuh).
    job = await db.backup_jobs.find_one({"job_id": job_id}, {"_id": 0, "status": 1})
    if job and job.get("status") == "completed":
        _terapkan_retensi(retensi)
    else:
        logger.warning("Backup otomatis GAGAL — retensi arsip TIDAK diterapkan "
                       "(arsip lama dipertahankan)")


async def backup_scheduler_loop():
    """Loop harian: cek tiap 5 menit; jalankan pada/tepat setelah jam setelan."""
    while True:
        try:
            s = await db.report_settings.find_one(
                {"type": "backup_otomatis"}, {"_id": 0}) or {}
            if s.get("aktif"):
                now_wib = datetime.now(WIB)
                if saat_jadwal_tiba(s.get("jam", "02:00"), now_wib,
                                    s.get("terakhir", "")):
                    aktif_job = await db.backup_jobs.find_one(
                        {"status": {"$in": ["running", "queued"]}}, {"_id": 1})
                    if not aktif_job:
                        hari_ini = now_wib.strftime("%Y-%m-%d")
                        # Klaim ATOMIK — worker lain melihat `terakhir` sudah
                        # hari ini dan tidak ikut menjalankan.
                        klaim = await db.report_settings.find_one_and_update(
                            {"type": "backup_otomatis", "aktif": True,
                             "terakhir": {"$ne": hari_ini}},
                            {"$set": {"terakhir": hari_ini}})
                        if klaim:
                            logger.info("Backup otomatis terjadwal: mulai")
                            await _jalankan_backup_otomatis(
                                int(s.get("retensi", 7) or 7))
        except Exception as e:
            logger.warning(f"Scheduler backup otomatis: {e}")
        await asyncio.sleep(300)


def start_backup_scheduler():
    """Dipanggil dari startup server — jalankan loop di background."""
    asyncio.create_task(backup_scheduler_loop())


@backup_router.get("/otomatis")
async def get_setelan_otomatis(authorization: str = Header(None)):
    """Setelan backup otomatis + ringkas arsip (untuk panel Pengaturan)."""
    await require_admin(authorization)
    s = await db.report_settings.find_one(
        {"type": "backup_otomatis"}, {"_id": 0, "type": 0}) or {}
    arsip = _daftar_arsip()
    return {**_SETELAN_OTOMATIS_DEFAULT, **s,
            "jumlah_arsip": len(arsip),
            "total_ukuran": sum(a["ukuran"] for a in arsip)}


@backup_router.post("/otomatis")
async def set_setelan_otomatis(payload: dict, authorization: str = Header(None)):
    """Simpan setelan backup otomatis (aktif, jam WIB, retensi)."""
    user = await require_admin(authorization)
    import re as _re
    jam = str(payload.get("jam", "02:00")).strip()
    if not _re.match(r"^([01]\d|2[0-3]):[0-5]\d$", jam):
        raise HTTPException(status_code=400,
                            detail="Format jam harus HH:MM (24 jam, WIB)")
    try:
        retensi = max(1, min(60, int(payload.get("retensi", 7))))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Retensi harus angka 1-60")
    await db.report_settings.update_one(
        {"type": "backup_otomatis"},
        {"$set": {"aktif": bool(payload.get("aktif")), "jam": jam,
                  "retensi": retensi}},
        upsert=True)
    logger.info(f"Setelan backup otomatis diubah oleh {user.get('username')}: "
                f"aktif={bool(payload.get('aktif'))} jam={jam} retensi={retensi}")
    return {"ok": True}


@backup_router.get("/arsip")
async def daftar_arsip_backup(authorization: str = Header(None)):
    """Daftar berkas backup yang tersimpan di arsip server."""
    await require_admin(authorization)
    return {"items": _daftar_arsip()}


@backup_router.get("/arsip/{nama}")
async def unduh_arsip_backup(nama: str, authorization: str = Header(None),
                             token: str | None = None):
    """Unduh satu berkas arsip (dukung ?token= utk navigasi browser langsung)."""
    effective_auth = authorization
    if not effective_auth and token:
        effective_auth = f"Bearer {token}"
    await require_admin(effective_auth)
    if not nama_arsip_valid(nama):
        raise HTTPException(status_code=400, detail="Nama berkas arsip tidak dikenal")
    p = BACKUP_ARSIP_DIR / nama
    if not p.exists():
        raise HTTPException(status_code=404, detail="Berkas arsip tidak ditemukan")
    return FileResponse(path=str(p), media_type="application/zip", filename=nama,
                        headers={"Content-Disposition": f'attachment; filename="{nama}"'})


@backup_router.delete("/arsip/{nama}")
async def hapus_arsip_backup(nama: str, authorization: str = Header(None)):
    """Hapus satu berkas arsip backup (admin)."""
    user = await require_admin(authorization)
    if not nama_arsip_valid(nama):
        raise HTTPException(status_code=400, detail="Nama berkas arsip tidak dikenal")
    p = BACKUP_ARSIP_DIR / nama
    if not p.exists():
        raise HTTPException(status_code=404, detail="Berkas arsip tidak ditemukan")
    p.unlink(missing_ok=True)
    logger.info(f"Arsip backup {nama} dihapus oleh {user.get('username')}")
    return {"ok": True}


@backup_router.post("/restore/dari-arsip/{nama}")
async def restore_dari_arsip(nama: str, authorization: str = Header(None)):
    """Mulai restore langsung dari berkas arsip server (tanpa unggah ulang)."""
    user = await require_admin(authorization)
    await cleanup_stale_jobs()
    if not nama_arsip_valid(nama):
        raise HTTPException(status_code=400, detail="Nama berkas arsip tidak dikenal")
    sumber = BACKUP_ARSIP_DIR / nama
    if not sumber.exists():
        raise HTTPException(status_code=404, detail="Berkas arsip tidak ditemukan")
    active = await db.backup_jobs.find_one({"status": "running"}, {"_id": 0})
    if active:
        raise HTTPException(status_code=409,
                            detail="Sudah ada proses backup/restore yang sedang berjalan")
    job_id = str(uuid.uuid4())[:12]
    # Salin ke temp — proses restore boleh menghapus berkas kerjanya tanpa
    # mengorbankan arsip asli.
    zip_path = BACKUP_TEMP_DIR / f"restore_{job_id}.zip"
    shutil.copyfile(str(sumber), str(zip_path))
    await db.backup_jobs.insert_one({
        "job_id": job_id, "type": "restore", "status": "queued", "progress": 0,
        "message": "Menunggu mulai...",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "started_by": user.get("username"),
        "source_file": nama,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    asyncio.create_task(run_restore_task(job_id, zip_path, user.get("username")))
    logger.info(f"Restore dari arsip {nama} dimulai oleh {user.get('username')}")
    return {"job_id": job_id, "message": "Proses restore dari arsip dimulai di background"}
