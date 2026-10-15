"""System Backup & Restore routes with background processing. Admin only."""
import os
import json
import uuid
import asyncio
import zipfile
import logging
import shutil
import hashlib
import contextlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from fastapi import APIRouter, HTTPException, Header, UploadFile, File
from fastapi.responses import FileResponse
from bson import ObjectId
from pymongo.errors import DuplicateKeyError
from pymongo import ReturnDocument
from backup_archive import (MANIFEST_NAME, CHUNK_SIZE, digest_entry, iter_json_documents,
                            read_json, validate_archive, write_manifest)

from db import db, fs_bucket
from auth_utils import get_current_user, _KUNCI_EFEMERAL

logger = logging.getLogger(__name__)
backup_router = APIRouter(prefix="/backup", tags=["backup"])

# Strong-ref ke task latar backup/restore/scheduler: asyncio hanya pegang weak
# ref, task fire-and-forget bisa di-GC saat suspended → operasi integritas data
# mati diam-diam (pola sama seperti exports.py:_EKSPOR_TASKS).
_BG_TASKS: set = set()


def _track_bg(t):
    """Tahan strong-ref selama task berjalan, lepas otomatis saat selesai."""
    _BG_TASKS.add(t)
    t.add_done_callback(_BG_TASKS.discard)
    return t

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


def _amankan_portal_hasil_pulih(col_name: str, docs: list):
    """Persetujuan akses dan lease proses tidak boleh dihidupkan oleh arsip.

    Dipanggil SEBELUM insert, termasuk rollback: worker dapat berhenti sebelum
    hook pencabutan akhir. Riwayat persetujuan/penugasan tetap dipertahankan;
    hanya akses yang harus diverifikasi ulang dan lease sementara dibuang.
    """
    if col_name == "portal_pemegang_akses":
        now = datetime.now(timezone.utc)
        for doc in docs:
            doc["aktif"] = False
            doc["dicabut_pada"] = now
            doc["alasan_pencabutan"] = "Verifikasi ulang setelah pemulihan backup"
            for field in ("epoch", "version"):
                try:
                    doc[field] = max(0, int(doc.get(field, 0))) + 1
                except (TypeError, ValueError, OverflowError):
                    doc[field] = 1
    elif col_name == "portal_penugasan":
        for doc in docs:
            # Pemilik lease tidak hidup dalam DB hasil restore. Selain itu,
            # datetime BSON dalam JSON berubah menjadi teks sehingga tidak
            # akan cocok dengan pembanding waktu Mongo untuk pemulihan lease.
            doc.pop("laporan_aktif", None)
    elif col_name == "bast_serah_terima":
        for doc in docs:
            plan = doc.get("portal_otomasi")
            if isinstance(plan, dict):
                plan.pop("lease", None)
                plan["akses_otomatis_ditahan"] = True
    return docs


async def _tulis_koleksi_json(zf: zipfile.ZipFile, col_name: str,
                              keep_id: bool) -> int:
    """Tulis `<col_name>.json` ke dalam `zf` BERTAHAP (satu dokumen per baris).

    Pengganti pola `list penuh → json.dumps penuh → writestr` yang menahan
    TIGA salinan koleksi di RAM sekaligus — terukur 1,1 GB puncak pada
    200.000 dokumen aset vs 0,3 MB versi bertahap, dengan berkas ZIP yang
    identik. Hasilnya tetap SATU array JSON sah, jadi pembaca lama
    (`json.loads(zf.read(...))`) tak berubah. Satu dokumen per baris
    disengaja: membuka jalan membaca bertahap kelak tanpa mengubah format.

    Tiga pagar yang gampang hilang saat refactor (masing-masing ditagih uji):
    ZipInfo TIDAK mewarisi kompresi dari ZipFile (tanpa `compress_type`
    entri jadi STORED — arsip 9x lebih besar dan guard disk bisa jebol);
    ZipInfo eksplisit dipakai justru agar stempel waktu entri benar (via
    `zf.open(nama_str)` entri bertanggal 1980 — arsip cadangan punya nilai
    forensik); `force_zip64` wajib karena ukuran entri tak diketahui di muka
    dan tepat pada DB terbesar-lah batas 2 GiB terlampaui.
    """
    now = datetime.now(timezone.utc)
    zi = zipfile.ZipInfo(f"{col_name}.json",
                         date_time=(now.year, now.month, now.day,
                                    now.hour, now.minute, now.second))
    zi.compress_type = zf.compression
    n = 0
    with zf.open(zi, "w", force_zip64=True) as fp:
        fp.write(b"[")
        async for doc in db[col_name].find({}):
            fp.write(b",\n" if n else b"\n")
            fp.write(json.dumps(serialize_doc(doc, keep_id=keep_id),
                                ensure_ascii=False, default=str).encode("utf-8"))
            n += 1
            if n % 500 == 0:
                await asyncio.sleep(0)
        fp.write(b"\n]" if n else b"]")
    return n


async def require_super_admin(authorization: str):
    """Backup/restore/reset = operasi SELURUH-DB (mencakup data SEMUA satker) →
    KHUSUS super-admin pusat (role 'admin' + kode_satker kosong). Admin yang
    terikat satu satker ditolak: mereka tak boleh mengunduh/menimpa/menghapus
    data satker lain."""
    from auth_utils import is_super_admin
    user = await get_current_user(authorization)
    if not is_super_admin(user):
        raise HTTPException(
            status_code=403,
            detail=("Khusus super-admin pusat (admin lintas-satker) — admin satker "
                    "tidak dapat mengakses backup/restore/reset seluruh sistem."))
    return user


def _tolak_bila_act_as(x_satker_aktif: str) -> None:
    """Footgun "Satker Aktif" (temuan tinjauan): restore MENIMPA seluruh satker,
    sedangkan UI super-admin yang sedang ber-"act-as" satker X hanya menampilkan
    X — model mentalnya keliru dan ini tak bisa dibatalkan. Tolak (400) selagi
    act-as, sama seperti guard reset di server.py; ia harus beralih ke "Semua
    Satker" dulu secara sadar. (get_current_user/_decode_bearer membuang
    `_satker_aktif`, jadi kita baca langsung dari header X-Satker-Aktif.)"""
    kode = str(x_satker_aktif or "").strip()
    if kode:
        raise HTTPException(
            status_code=400,
            detail=(f"Anda sedang bertindak sebagai satker {kode}. Restore menimpa "
                    "SELURUH satker — beralih ke 'Semua Satker' dulu."))


# Gerbang single-flight: hanya SATU backup/restore boleh aktif. Dokumen job
# aktif (queued/running) membawa `active_lock="GLOBAL"`; partial unique index
# (indexes.py) menolak dokumen kedua. Lock dilepas (unset) saat job mencapai
# status terminal — lihat update_job / cleanup_stale_jobs.
_ACTIVE_LOCK = "GLOBAL"


async def update_job(job_id: str, **fields):
    """Update backup job progress in MongoDB. Saat status terminal
    (completed/failed), lepas gerbang single-flight (unset active_lock)."""
    fields["updated_at"] = datetime.now(timezone.utc).isoformat()
    update = {"$set": fields}
    if fields.get("status") in ("completed", "failed"):
        update["$unset"] = {"active_lock": ""}
    await db.backup_jobs.update_one({"job_id": job_id}, update)


async def cleanup_stale_jobs():
    """Tandai job MACET sebagai failed & LEPAS gerbang single-flight (unset
    active_lock) agar backup/restore baru bisa mulai — mencegah lock
    menggantung bila worker mati sebelum menyelesaikan.

    Macet = TIDAK ADA DENYUT PROGRES 30 menit (updated_at basi) — bukan umur
    sejak mulai (REVIEW-9 R6): restore besar yang masih rajin meng-update
    progres tidak boleh dibunuh di menit ke-30 lalu lock-nya direbut proses
    lain di tengah wipe+isi ulang koleksi."""
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    stale_restores = await db.backup_jobs.find(
        {"type": "restore", "status": {"$in": ["running", "queued"]},
         "updated_at": {"$lt": cutoff}}, {"job_id": 1}).to_list(100)
    for stale in stale_restores:
        control = await db.restore_control.find_one({"_id": "GLOBAL", "job_id": stale["job_id"]})
        if control and control.get("state") in _RESTORE_ACTIVE_STATES:
            await db.restore_control.update_one(
                {"_id": "GLOBAL", "job_id": stale["job_id"], "state": control["state"]},
                {"$set": {"state": "recovery_required", "active": True,
                          "error": "Worker lease expired; operator must stop old workers and verify recovery",
                          "updated_at": datetime.now(timezone.utc).isoformat()}})
    await db.backup_jobs.update_many(
        {"status": {"$in": ["running", "queued"]}, "updated_at": {"$lt": cutoff}},
        {"$set": {"status": "failed", "error": "Timeout: proses terlalu lama",
                  "updated_at": datetime.now(timezone.utc).isoformat()},
         "$unset": {"active_lock": ""}}
    )


async def cleanup_old_files():
    """Remove backup temp files older than 1 hour."""
    if not BACKUP_TEMP_DIR.exists():
        return
    control = await restore_control_status()
    protected = {control.get("source_artifact"), control.get("safety_artifact")} if control.get("state") in _RESTORE_ACTIVE_STATES else set()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    for f in BACKUP_TEMP_DIR.iterdir():
        if f.name in protected:
            continue
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
    """Stream every file; missing/unreadable source media fails the whole backup."""
    manifest = []
    async for meta in db["fs.files"].find({}):
        file_id = str(meta["_id"])
        stream = await fs_bucket.open_download_stream(meta["_id"])
        size, digest = 0, hashlib.sha256()
        try:
            with zf.open(f"gridfs/{file_id}.bin", "w", force_zip64=True) as fp:
                while True:
                    chunk = await stream.readchunk()
                    if not chunk:
                        break
                    fp.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
                    await asyncio.sleep(0)
        finally:
            close = getattr(stream, "close", None)
            if close:
                result = close()
                if asyncio.iscoroutine(result):
                    await result
        if size != int(meta.get("length", size)):
            raise ValueError(f"GridFS berubah atau tidak lengkap saat backup: {file_id}")
        manifest.append({
            "_id": file_id, "filename": meta.get("filename", file_id),
            "length": size, "sha256": digest.hexdigest(),
            "chunkSize": meta.get("chunkSize", 261120),
            "uploadDate": meta.get("uploadDate").isoformat() if meta.get("uploadDate") else None,
            "contentType": meta.get("contentType"), "metadata": meta.get("metadata"),
        })
        if progress_cb:
            await progress_cb(len(manifest))
    zf.writestr("gridfs/manifest.json", json.dumps(manifest, ensure_ascii=False, default=str))
    return len(manifest)


async def import_gridfs(zf: zipfile.ZipFile, progress_cb=None) -> int:
    """Reconstruct files with bounded chunks; any missing/corrupt media is fatal.

    Full archive preflight must precede destructive application. This helper also
    validates each manifest entry before its own wipe for independent callers.
    """
    # Preflight proves legacy archives without this section contain no media
    # references. Their media set is empty; do not retain stale private blobs.
    manifest = (read_json(zf, "gridfs/manifest.json")
                if "gridfs/manifest.json" in zf.namelist() else [])
    for entry in manifest:
        name = f"gridfs/{entry['_id']}.bin"
        result = await asyncio.to_thread(digest_entry, zf, name)
        if result["size"] != int(entry.get("length", result["size"])):
            raise ValueError(f"Ukuran blob tidak cocok: {name}")
        if entry.get("sha256") and result["sha256"] != entry["sha256"]:
            raise ValueError(f"Checksum blob tidak cocok: {name}")
    await db["fs.files"].delete_many({})
    await db["fs.chunks"].delete_many({})
    for count, entry in enumerate(manifest, 1):
        file_id = str(entry["_id"])
        oid = ObjectId(file_id) if ObjectId.is_valid(file_id) else file_id
        stream = fs_bucket.open_upload_stream_with_id(
            oid, entry.get("filename") or file_id, metadata=entry.get("metadata"))
        try:
            with zf.open(f"gridfs/{file_id}.bin") as fp:
                while True:
                    chunk = fp.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    await stream.write(chunk)
            await stream.close()
        except BaseException:
            with contextlib.suppress(Exception):
                await stream.abort()
            raise
        if progress_cb:
            await progress_cb(count)
        await asyncio.sleep(0)
    return len(manifest)


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

                stats[col_name] = await _tulis_koleksi_json(
                    zf, col_name, col_name in KEEP_ID_COLLECTIONS)
                logger.info(f"Backup [{job_id}]: {col_name} = {stats[col_name]} docs")
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
                    if file_path.is_symlink():
                        raise ValueError("Symlink dalam uploads tidak boleh diarsipkan")
                    if file_path.is_file():
                        rel_path = file_path.relative_to(UPLOADS_DIR)
                        zf.write(file_path, f"uploads/{rel_path}")
                        file_count += 1
                        if file_count % 50 == 0:
                            await asyncio.sleep(0)

            # Write metadata
            metadata = {
                "version": APP_VERSION,
                "archive_schema_version": 1,
                "consistency": "application_best_effort",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": username,
                "collections": stats,
                "total_records": sum(v for k, v in stats.items() if k != "gridfs_files"),
                "gridfs_files": gridfs_count,
                "upload_files": file_count,
            }
            zf.writestr("metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2))
            await asyncio.to_thread(write_manifest, zf, stats, gridfs_count, file_count)

        with zipfile.ZipFile(zip_path) as verify_zip:
            await asyncio.to_thread(validate_archive, verify_zip, False)
        file_size = zip_path.stat().st_size
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"backup_{timestamp}.zip"

        arsip_nama = ""
        archive_error = ""
        archive_state = "not_requested"
        if arsipkan in ("otomatis", "manual"):
            requested_name = f"backup_{arsipkan}_{timestamp}.zip"
            staging = BACKUP_ARSIP_DIR / f".{requested_name}.{job_id}.part"
            final = BACKUP_ARSIP_DIR / requested_name
            final_published = False
            try:
                # Copy keeps the manual download available if archival fails.
                shutil.copyfile(zip_path, staging)
                with staging.open("rb") as fp:
                    os.fsync(fp.fileno())
                with zipfile.ZipFile(staging) as verify_zip:
                    await asyncio.to_thread(validate_archive, verify_zip, False)
                if staging.stat().st_size != file_size:
                    raise ValueError("Ukuran arsip persisten tidak cocok")
                if final.exists():
                    raise FileExistsError("Nama arsip sudah digunakan; cadangan lama dipertahankan")
                os.replace(staging, final)
                final_published = True
                # Verify final path is readable before durable success/retention.
                with zipfile.ZipFile(final) as verify_zip:
                    await asyncio.to_thread(validate_archive, verify_zip, False)
                fd = os.open(BACKUP_ARSIP_DIR, os.O_RDONLY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
                arsip_nama, filename = requested_name, requested_name
                archive_state = "archived"
            except Exception as error:
                archive_error = str(error)
                archive_state = "archive_failed"
                staging.unlink(missing_ok=True)
                if final_published:
                    # An unverifiable final artifact must never count as a valid
                    # archive for future retention; preserve it quarantined.
                    os.replace(final, BACKUP_ARSIP_DIR / f".{requested_name}.{job_id}.failed")
                logger.error("Backup [%s] archival failed: %s", job_id, error)

        await update_job(
            job_id, status="completed", progress=100,
            message=("Backup selesai & tersimpan di arsip server." if arsip_nama
                     else ("Backup siap diunduh; gagal menyimpan arsip server: " + archive_error
                           if archive_error else "Backup selesai! Siap diunduh.")),
            filename=filename,
            arsip_nama=arsip_nama,
            download_ready=True, archive_state=archive_state,
            durable_verified=bool(arsip_nama), archive_error=archive_error,
            complete=True, archive_schema_version=1,
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

# Durable gate is installation-local, excluded from backup/reset and has no TTL.
_RESTORE_ACTIVE_STATES = {"preparing", "restoring", "rolling_back", "recovery_required"}
_RESTORE_TERMINAL_STATES = ["completed", "rolled_back", "aborted"]


async def restore_control_status():
    return await db.restore_control.find_one({"_id": "GLOBAL"}, {"_id": 0}) or {}


async def _guard_recovery():
    control = await restore_control_status()
    if (control.get("state") not in (None, *_RESTORE_TERMINAL_STATES)
            or (control.get("state") is None and (control.get("active") is True
                                                     or control.get("destructive_started") is True))):
        raise HTTPException(409, "Pemulihan/deploy belum selesai; periksa status recovery sebelum operasi baru")


async def _claim_restore_control(job_id, username, zip_path):
    now = datetime.now(timezone.utc).isoformat()
    try:
        row = await db.restore_control.find_one_and_update(
            {"_id": "GLOBAL", "$or": [{"state": {"$in": _RESTORE_TERMINAL_STATES}},
                                         {"state": {"$exists": False}, "active": {"$ne": True},
                                          "destructive_started": {"$ne": True}}]},
            {"$set": {"state": "preparing", "active": True,
                      "owner": f"restore:{job_id}", "job_id": job_id,
                      "started_by": username, "started_at": now,
                      "updated_at": now, "destructive_started": False,
                      "source_artifact": zip_path.name,
                      "safety_artifact": f"safety_data_{job_id}.zip"},
             "$unset": {"error": "", "rollback_error": "", "verified_at": ""}},
            upsert=True, return_document=ReturnDocument.AFTER)
    except DuplicateKeyError:
        raise RuntimeError("Recovery/deploy lain masih menguasai kontrol pemulihan") from None
    if not row:
        raise RuntimeError("Kontrol pemulihan tidak dapat diklaim")
    from dataset_epoch import rotate_generation
    try:
        await rotate_generation(db, "restore_claim")
    except BaseException as error:
        # Claim is already durable but no destructive IO has started. Release
        # only this owner's preflight claim; never overwrite another owner.
        await db.restore_control.update_one(
            {"_id": "GLOBAL", "job_id": job_id, "owner": f"restore:{job_id}",
             "state": "preparing", "destructive_started": False},
            {"$set": {"state": "aborted", "active": False,
                      "error": "Dataset generation rotation failed before wipe",
                      "updated_at": datetime.now(timezone.utc).isoformat()}})
        raise
    return row


async def _restore_state(job_id, state, **fields):
    result = await db.restore_control.update_one(
        {"_id": "GLOBAL", "job_id": job_id, "state": {"$in": list(_RESTORE_ACTIVE_STATES)}},
        {"$set": {"state": state, "active": state in _RESTORE_ACTIVE_STATES,
                  "updated_at": datetime.now(timezone.utc).isoformat(), **fields}})
    if not result.matched_count:
        raise RuntimeError("Kepemilikan kontrol pemulihan hilang")
    # Clear this worker's read cache immediately; other writers always recheck.
    import pemeliharaan
    pemeliharaan._cache = (0.0, False)


async def _wait_writer_drain(timeout=120):
    """Gate is already raised. Request leases close the admit-vs-start race."""
    deadline = asyncio.get_running_loop().time() + timeout
    while (await db.restore_write_leases.count_documents({})
           or await db.background_jobs.count_documents({
               "status": {"$nin": ["done", "error", "completed", "failed", "cancelled", "canceled", "dismissed", "downloaded"]},
               "done": {"$ne": True},
               "$nor": [{"worker_protocol": "export_v1", "status": "queued"}]})
           or await db.unduhan.count_documents({"status": {"$in": ["queued", "running"]}})):
        if asyncio.get_running_loop().time() > deadline:
            raise RuntimeError("Request penulis belum selesai; restore dibatalkan sebelum wipe")
        await asyncio.sleep(0.25)


async def _restore_heartbeat(job_id):
    while True:
        await asyncio.sleep(10)
        await update_job(job_id)  # Progress lease never silently expires during large IO.


async def _apply_archive(zf, job_id):
    """Apply prevalidated archive, batching BSON inserts and streaming all files."""
    restore_stats = {}
    cols = collections_from_backup(zf.namelist())
    for index, zip_col in enumerate(cols):
        col = LEGACY_COLLECTION_ALIASES.get(zip_col, zip_col)
        await update_job(job_id, progress=30 + int(35 * (index + 1) / max(1, len(cols))),
                         message=f"Restore: {col}...")
        await db[col].delete_many({})
        count, batch, batch_bytes, seen_satker = 0, [], 0, set()
        with zf.open(f"{zip_col}.json") as fp:
            for doc in iter_json_documents(fp):
                if col == "assets" and not doc.get("version"):
                    doc["version"] = 1
                if col == "satker":
                    key = doc.get("kode_satker")
                    if key in seen_satker:
                        continue
                    seen_satker.add(key)
                if col == "users":
                    for key in _KUNCI_EFEMERAL:
                        doc.pop(key, None)
                batch.append(doc)
                batch_bytes += len(json.dumps(doc, ensure_ascii=False, default=str).encode("utf-8"))
                if len(batch) >= 200 or batch_bytes >= 4 * 1024 * 1024:
                    _amankan_portal_hasil_pulih(col, batch)
                    await db[col].insert_many(batch)
                    count, batch, batch_bytes = count + len(batch), [], 0
                    await asyncio.sleep(0)
            if batch:
                _amankan_portal_hasil_pulih(col, batch)
                await db[col].insert_many(batch)
                count += len(batch)
        restore_stats[col] = count
    for col in await _app_collections():
        if col not in restore_stats and col != "users":
            await db[col].delete_many({})
    await repair_ticket_counters()
    await update_job(job_id, progress=70, message="Memulihkan foto (GridFS)...")
    async def progress(n):
        await update_job(job_id, progress=70, message=f"Memulihkan foto ({n})...")
    gridfs_count = await import_gridfs(zf, progress_cb=progress)
    # Safety snapshot includes uploads; replace complete directory contents too.
    # Backup without uploads means an empty uploads tree, not stale old files.
    if UPLOADS_DIR.exists():
        shutil.rmtree(UPLOADS_DIR)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    upload_count = 0
    for name in zf.namelist():
        if not name.startswith("uploads/") or name.endswith("/"):
            continue
        target = UPLOADS_DIR / name[len("uploads/"):]
        root = UPLOADS_DIR.resolve()
        if root not in target.resolve().parents:
            raise ValueError("Path upload di luar root")
        target.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(name) as source, target.open("wb") as dest:
            shutil.copyfileobj(source, dest, CHUNK_SIZE)
        upload_count += 1
        await asyncio.sleep(0)
    return restore_stats, gridfs_count, upload_count


async def _verify_applied(zf, stats):
    for col, expected in stats.items():
        # Ticket repair intentionally creates missing/maxes counters.
        actual = await db[col].count_documents({})
        if (col != "counters" and actual != expected) or (col == "counters" and actual < expected):
            raise ValueError(f"Verifikasi jumlah {col} gagal: {actual} != {expected}")
    if "gridfs/manifest.json" not in zf.namelist():
        if await db["fs.files"].count_documents({}) or await db["fs.chunks"].count_documents({}):
            raise ValueError("GridFS legacy hasil restore seharusnya kosong")
    else:
        manifest = read_json(zf, "gridfs/manifest.json")
        if await db["fs.files"].count_documents({}) != len(manifest):
            raise ValueError("Jumlah GridFS hasil restore tidak cocok")
        for entry in manifest:
            fid = str(entry["_id"])
            oid = ObjectId(fid) if ObjectId.is_valid(fid) else fid
            stream = await fs_bucket.open_download_stream(oid)
            actual = hashlib.sha256()
            size = 0
            try:
                while True:
                    chunk = await stream.readchunk()
                    if not chunk:
                        break
                    actual.update(chunk)
                    size += len(chunk)
            finally:
                close = getattr(stream, "close", None)
                if close:
                    result = close()
                    if asyncio.iscoroutine(result):
                        await result
            expected = await asyncio.to_thread(digest_entry, zf, f"gridfs/{fid}.bin")
            if expected != {"size": size, "sha256": actual.hexdigest()}:
                raise ValueError(f"Verifikasi checksum GridFS gagal: {fid}")
    for name in zf.namelist():
        if name.startswith("uploads/") and not name.endswith("/"):
            actual, size = hashlib.sha256(), 0
            with (UPLOADS_DIR / name[8:]).open("rb") as fp:
                while True:
                    chunk = fp.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    actual.update(chunk)
                    size += len(chunk)
            if await asyncio.to_thread(digest_entry, zf, name) != {"size": size, "sha256": actual.hexdigest()}:
                raise ValueError(f"Verifikasi upload gagal: {name}")


async def _invalidate_restored_projections():
    """Await cross-worker invalidation before reopening a replaced dataset."""
    import shared_utils
    import redis_utils
    for cache in shared_utils._CACHE_LOCAL.values():
        cache.clear()
    if redis_utils.redis_aktif():
        client = redis_utils._get_client()
        for namespace in shared_utils._CACHE_LOCAL:
            # Deliberately do not use best-effort fire-and-forget _bump here.
            await client.incr(redis_utils._GENP + namespace)
    from meili_utils import invalidate_after_restore
    await invalidate_after_restore(database=db)


async def _finish_recovered_data(zf, stats):
    from portal_auth import cabut_semua_portal_akses
    await cabut_semua_portal_akses("Verifikasi ulang setelah pemulihan backup", database=db)
    await _verify_applied(zf, stats)
    from indexes import create_indexes, _KEGAGALAN_INDEKS
    await create_indexes()
    if _KEGAGALAN_INDEKS:
        raise RuntimeError("Index pasca-restore gagal; layanan tetap ditahan")
    from shared_utils import bersihkan_penanda_migrasi
    await bersihkan_penanda_migrasi()
    await _invalidate_restored_projections()
    # Rollback/recovery may rotate more recently than the initial claim. Allow
    # all workers to expire their local epoch lookup before reopening reads.
    import shared_utils
    await asyncio.sleep(shared_utils._CACHE_EPOCH_TTL + 0.05)


async def recover_restore(job_id, username):
    """Operator recovery uses retained safety archive; never blindly clears gate."""
    control = await restore_control_status()
    if control.get("job_id") != job_id or control.get("state") != "recovery_required":
        raise HTTPException(409, "Tidak ada recovery_required untuk job ini")
    safety_name = control.get("safety_artifact", "")
    if safety_name != f"safety_data_{job_id}.zip":
        raise RuntimeError("Nama safety artifact tidak valid")
    safety = BACKUP_TEMP_DIR / safety_name
    with zipfile.ZipFile(safety) as zf:
        await asyncio.to_thread(validate_archive, zf, False)
    claim = await db.restore_control.update_one(
        {"_id": "GLOBAL", "job_id": job_id, "state": "recovery_required"},
        {"$set": {"state": "rolling_back", "active": True,
                  "recovered_by": username}})
    if not claim.modified_count:
        raise HTTPException(409, "Recovery sudah diklaim operator lain")
    try:
        await _wait_writer_drain()
        from dataset_epoch import rotate_generation
        await rotate_generation(db, "restore_recovery")
        with zipfile.ZipFile(safety) as zf:
            stats, _, _ = await _apply_archive(zf, job_id)
            await _finish_recovered_data(zf, stats)
        await update_job(job_id, status="failed", recovery_required=False,
                         message="Recovery terverifikasi; safety snapshot berhasil dipulihkan")
        await _restore_state(job_id, "rolled_back", verified_at=datetime.now(timezone.utc).isoformat())
        # Artifacts retained for operator review; cleanup only after terminal.
        return {"ok": True, "state": "rolled_back", "job_id": job_id}
    except BaseException as error:
        await _restore_state(job_id, "recovery_required", rollback_error=str(error))
        raise


async def run_restore_task(job_id: str, zip_path: Path, username: str):
    """Validate completely, snapshot, then replace; unsafe failure stays closed."""
    from log_setup import set_job_id
    set_job_id(job_id)
    destructive, claimed, verified_terminal = False, False, False
    safety_data_zip = BACKUP_TEMP_DIR / f"safety_data_{job_id}.zip"
    heartbeat = None
    try:
        await update_job(job_id, status="running", progress=5, message="Memvalidasi seluruh file backup...")
        with zipfile.ZipFile(zip_path) as zf:
            preflight = await asyncio.to_thread(validate_archive, zf)
        await _claim_restore_control(job_id, username, zip_path)
        claimed = True
        heartbeat = asyncio.create_task(_restore_heartbeat(job_id))
        await _wait_writer_drain()
        # Let all workers expire their negative read-maintenance cache before
        # touching data. Mutating admission already checks uncached above.
        import pemeliharaan
        await asyncio.sleep(pemeliharaan._CACHE_TTL + 0.05)
        from portal_auth import cabut_semua_portal_akses
        await cabut_semua_portal_akses("Pemulihan backup dimulai", database=db)
        safety_cols, safety_stats = await _app_collections(), {}
        with zipfile.ZipFile(safety_data_zip, "w", zipfile.ZIP_DEFLATED) as sz:
            for col_name in safety_cols:
                safety_stats[col_name] = await _tulis_koleksi_json(sz, col_name, col_name in KEEP_ID_COLLECTIONS)
                await update_job(job_id, progress=15, message=f"Safety backup: {col_name}...")
            # Safety backup GridFS is mandatory; errors abort BEFORE first wipe.
            gridfs = await export_gridfs(sz)
            uploads = 0
            if UPLOADS_DIR.exists():
                for source in UPLOADS_DIR.rglob("*"):
                    if source.is_symlink():
                        raise ValueError("Symlink dalam uploads tidak boleh dipulihkan")
                    if source.is_file():
                        sz.write(source, "uploads/" + source.relative_to(UPLOADS_DIR).as_posix())
                        uploads += 1
            sz.writestr("metadata.json", json.dumps({"version": APP_VERSION,
                        "created_by": username, "purpose": "restore_safety"}))
            await asyncio.to_thread(write_manifest, sz, safety_stats, gridfs, uploads)
        with safety_data_zip.open("rb") as safety_file:
            os.fsync(safety_file.fileno())
        with zipfile.ZipFile(safety_data_zip) as sz:
            await asyncio.to_thread(validate_archive, sz, False)
        # Persist BEFORE destructive IO. A killed process never auto-opens data.
        from dataset_epoch import rotate_generation
        await _restore_state(job_id, "restoring", destructive_started=True)
        destructive = True
        try:
            with zipfile.ZipFile(zip_path) as zf:
                stats, gridfs, uploads = await _apply_archive(zf, job_id)
                await _finish_recovered_data(zf, stats)
            await update_job(job_id, status="completed", progress=100,
                             message="Data berhasil dipulihkan dan diverifikasi!",
                             restore_stats=stats, total_restored=sum(stats.values()),
                             gridfs_files_restored=gridfs, upload_files_restored=uploads,
                             recovery_required=False, backup_metadata=preflight["metadata"])
            await _restore_state(job_id, "completed", verified_at=datetime.now(timezone.utc).isoformat())
            verified_terminal = True
        except BaseException as error:
            await _restore_state(job_id, "rolling_back", error=str(error))
            try:
                await rotate_generation(db, "restore_rollback")
                with zipfile.ZipFile(safety_data_zip) as sz:
                    await asyncio.to_thread(validate_archive, sz, False)
                    old_stats, _, _ = await _apply_archive(sz, job_id)
                    await _finish_recovered_data(sz, old_stats)
                await update_job(job_id, status="failed", error=str(error), recovery_required=False,
                                 message="Restore gagal; safety snapshot telah dipulihkan dan diverifikasi.")
                await _restore_state(job_id, "rolled_back", verified_at=datetime.now(timezone.utc).isoformat())
                verified_terminal = True
            except BaseException as rollback_error:
                await _restore_state(job_id, "recovery_required", error=str(error), rollback_error=str(rollback_error))
                await update_job(job_id, status="failed", error=str(error),
                                 rollback_error=str(rollback_error), recovery_required=True,
                                 message="Restore dan rollback gagal. Layanan ditahan; operator wajib menjalankan recovery.")
            if isinstance(error, asyncio.CancelledError):
                raise
    except BaseException as error:
        if claimed and not destructive:
            await _restore_state(job_id, "aborted", error=str(error))
            verified_terminal = True
        await update_job(job_id, status="failed", error=str(error),
                         message=f"Restore dibatalkan sebelum wipe: {error}" if not destructive
                         else "Pemulihan terhenti; periksa status recovery sebelum membuka layanan.")
        if isinstance(error, asyncio.CancelledError):
            raise
    finally:
        if heartbeat:
            heartbeat.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await heartbeat
        # Never delete source or safety files while recovery is unresolved.
        if verified_terminal or not claimed:
            zip_path.unlink(missing_ok=True)
            safety_data_zip.unlink(missing_ok=True)


# ============================================================================
# API ENDPOINTS
# ============================================================================

@backup_router.get("/stats")
async def get_backup_stats(authorization: str = Header(None)):
    """Get current data statistics for backup preview."""
    await require_super_admin(authorization)
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
    user = await require_super_admin(authorization)
    await cleanup_stale_jobs()
    await _guard_recovery()
    await cleanup_old_files()

    # Fast-path (ramah): tolak cepat bila ada job aktif; gerbang ATOMIK ada di
    # unique index active_lock (menangkap balapan yang lolos cek ini).
    active = await db.backup_jobs.find_one(
        {"status": {"$in": ["queued", "running"]}}, {"_id": 0})
    if active:
        raise HTTPException(status_code=409, detail="Sudah ada proses backup/restore yang sedang berjalan")

    job_id = str(uuid.uuid4())[:12]
    job = {
        "job_id": job_id,
        "type": "backup",
        "status": "queued",
        "active_lock": _ACTIVE_LOCK,
        "progress": 0,
        "message": "Menunggu mulai...",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "started_by": user.get("username"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        await db.backup_jobs.insert_one(job)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Sudah ada proses backup/restore yang sedang berjalan")

    _track_bg(asyncio.create_task(run_backup_task(
        job_id, user.get("username"),
        arsipkan="manual" if arsipkan else "")))
    logger.info(f"Backup job {job_id} started by {user.get('username')}")

    return {"job_id": job_id, "message": "Proses backup dimulai di background"}


@backup_router.post("/restore/start")
async def start_restore(
    file: UploadFile = File(...),
    authorization: str = Header(None),
    x_satker_aktif: str = Header(default="", alias="X-Satker-Aktif"),
):
    """Upload backup file and start background restore. Returns job_id."""
    user = await require_super_admin(authorization)
    _tolak_bila_act_as(x_satker_aktif)
    await cleanup_stale_jobs()
    await _guard_recovery()

    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="File harus berformat ZIP")

    active = await db.backup_jobs.find_one(
        {"status": {"$in": ["queued", "running"]}}, {"_id": 0})
    if active:
        raise HTTPException(status_code=409, detail="Sudah ada proses backup/restore yang sedang berjalan")

    job_id = str(uuid.uuid4())[:12]

    # Simpan berkas unggahan ke temp secara STREAMING (per-chunk 1 MB) — jangan
    # muat seluruh ZIP (bisa ratusan MB–GB karena berisi foto GridFS) ke RAM
    # dulu; itu vektor OOM di VPS kecil.
    zip_path = BACKUP_TEMP_DIR / f"restore_{job_id}.zip"
    try:
        upload_bytes = 0
        upload_budget = min(100 * 1024 ** 3, max(0, shutil.disk_usage(BACKUP_TEMP_DIR).free - 200 * 1024 ** 2))
        with open(zip_path, 'wb') as f:
            while True:
                chunk = await file.read(1 << 20)  # 1 MB
                if not chunk:
                    break
                upload_bytes += len(chunk)
                if upload_bytes > upload_budget:
                    raise ValueError("Berkas backup melebihi ruang disk aman atau batas ukuran")
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
        "active_lock": _ACTIVE_LOCK,
        "progress": 0,
        "message": "Menunggu mulai...",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "started_by": user.get("username"),
        "source_file": file.filename,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        await db.backup_jobs.insert_one(job)
    except DuplicateKeyError:
        zip_path.unlink(missing_ok=True)
        raise HTTPException(status_code=409, detail="Sudah ada proses backup/restore yang sedang berjalan")

    _track_bg(asyncio.create_task(run_restore_task(job_id, zip_path, user.get("username"))))
    logger.info(f"Restore job {job_id} started by {user.get('username')}")

    return {"job_id": job_id, "message": "Proses restore dimulai di background"}


@backup_router.get("/progress/{job_id}")
async def get_job_progress(job_id: str, authorization: str = Header(None)):
    """Get progress of a backup/restore job."""
    await require_super_admin(authorization)
    job = await db.backup_jobs.find_one({"job_id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job tidak ditemukan")
    return job


@backup_router.get("/active")
async def get_active_job(authorization: str = Header(None)):
    """Get the currently active (running/queued) job, if any."""
    await require_super_admin(authorization)
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
    await require_super_admin(effective_auth)

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
    await require_super_admin(authorization)
    await db.backup_jobs.update_one(
        {"job_id": job_id, "status": {"$in": ["completed", "failed"]}},
        {"$set": {"status": "dismissed", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    control = await restore_control_status()
    if control.get("job_id") == job_id and control.get("state") in _RESTORE_ACTIVE_STATES:
        return {"ok": True, "recovery_required": True}
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
# Scheduler dipanggil dari startup server; klaim tanggal via find_one_and_update
# ATOMIK sehingga aman multi-worker (hanya satu worker yang menjalankan).
#
# KLAIM vs HASIL — dua hal berbeda, dan membedakannya adalah inti temuan C5:
#   terakhir              KLAIM penjadwalan ("YYYY-MM-DD" WIB), ditulis SEBELUM
#                         backup berjalan sebagai penjaga anti-jalan-ganda.
#                         BUKAN bukti keberhasilan. JANGAN ditampilkan ke
#                         pengguna sebagai "Terakhir jalan".
#   terakhir_sukses       HASIL: ISO-8601 backup yang benar-benar `completed`.
#                         INI yang ditampilkan layar Pengaturan.
#   status_terakhir       "sukses" | "gagal"
#   galat_terakhir        pesan job saat gagal (dipotong 500 char)
#   waktu_hasil_terakhir  ISO-8601 kapan hasil terakhir dicatat
# Saat gagal, `terakhir` dikosongkan agar siklus 5 menit berikutnya mencoba
# lagi hari itu juga — bukan menyerah sampai besok.

WIB = timezone(timedelta(hours=7))
_SETELAN_OTOMATIS_DEFAULT = {"aktif": False, "jam": "02:00", "retensi": 7,
                             "terakhir": "", "terakhir_sukses": "",
                             "status_terakhir": "", "galat_terakhir": "",
                             "waktu_hasil_terakhir": ""}


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
    try:
        await _guard_recovery()
    except HTTPException:
        await db.report_settings.update_one({"type": "backup_otomatis"}, {"$set": {"terakhir": ""}})
        return
    job_id = str(uuid.uuid4())[:12]
    try:
        await db.backup_jobs.insert_one({
            "job_id": job_id, "type": "backup", "status": "queued",
            "active_lock": _ACTIVE_LOCK, "progress": 0,
            "message": "Backup otomatis terjadwal...",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "started_by": "backup-otomatis",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
    except DuplicateKeyError:
        # Ada backup/restore aktif — lewati siklus otomatis ini (bukan galat).
        logger.info("Backup otomatis dilewati: ada proses backup/restore aktif")
        await db.report_settings.update_one({"type": "backup_otomatis"}, {"$set": {"terakhir": ""}})
        return
    await run_backup_task(job_id, "backup-otomatis", arsipkan="otomatis")
    # Terapkan retensi HANYA bila backup SUKSES — kalau gagal, JANGAN pangkas
    # arsip lama (menghindari kehilangan cadangan yang masih valid saat backup
    # baru gagal, mis. disk penuh).
    job = await db.backup_jobs.find_one(
        {"job_id": job_id}, {"_id": 0, "status": 1, "message": 1, "durable_verified": 1,
                             "archive_state": 1, "arsip_nama": 1}) or {}
    berhasil = (job.get("status") == "completed"
                and job.get("durable_verified") is True
                and job.get("archive_state") == "archived"
                and nama_arsip_valid(job.get("arsip_nama")))

    # ── HASIL, terpisah dari KLAIM (temuan C5 tinjauan 2026-08) ─────────────
    #
    # Penjadwal menulis `terakhir = hari ini` SEBELUM backup dijalankan — itu
    # memang klaim penjadwalan yang atomik dan benar sebagai penjaga anti-ganda.
    # Masalahnya, layar Pengaturan menampilkan field yang SAMA sebagai
    # "Terakhir jalan", sehingga backup yang GAGAL tetap terbaca "sudah jalan
    # hari ini". Satu-satunya jejak kegagalan adalah satu baris logger.warning
    # yang tak pernah dibaca siapa pun.
    #
    # Karena itu hasilnya dicatat di field sendiri. `terakhir_sukses` yang
    # ditampilkan UI, `status_terakhir` + `galat_terakhir` yang menjelaskan.
    #
    # Dan saat GAGAL, klaim `terakhir` DIKOSONGKAN: siklus 5 menit berikutnya
    # akan mencoba lagi hari itu juga alih-alih menyerah sampai besok. Aman
    # dari backup ganda — percobaan berikutnya tetap melewati klaim atomik yang
    # sama, dan tetap dilewati bila ada job aktif.
    sekarang = datetime.now(timezone.utc).isoformat()
    hasil = {"status_terakhir": "sukses" if berhasil else "gagal",
             "waktu_hasil_terakhir": sekarang}
    if berhasil:
        hasil["terakhir_sukses"] = sekarang
        hasil["galat_terakhir"] = ""
    else:
        hasil["galat_terakhir"] = str(job.get("message") or "")[:500] \
            or "Backup gagal tanpa pesan — periksa log server"
        hasil["terakhir"] = ""   # buka kunci: coba lagi pada siklus berikutnya
    await db.report_settings.update_one(
        {"type": "backup_otomatis"}, {"$set": hasil}, upsert=True)

    if berhasil:
        _terapkan_retensi(retensi)
    else:
        logger.warning("Backup otomatis GAGAL — retensi arsip TIDAK diterapkan "
                       "(arsip lama dipertahankan); klaim harian dikosongkan "
                       "agar siklus berikutnya mencoba lagi")


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
        # Sapu sisa backup_temp (>1 jam) TIAP tick — dulu hanya saat admin
        # memulai backup manual, sehingga sisa restore yang crash (restore_*.zip
        # + safety_*.zip berisi snapshot penuh GridFS) menetap memakan disk.
        # PENTING: LEWATI bila ada job backup/restore AKTIF — restore DB besar
        # bisa berjalan > 1 jam dan file kerjanya (restore_*.zip, safety_*.zip)
        # masih dibutuhkan untuk rollback; menghapusnya di tengah jalan bisa
        # menggagalkan pemulihan dan meninggalkan DB ter-wipe separuh.
        try:
            aktif = await db.backup_jobs.find_one(
                {"status": {"$in": ["queued", "running"]}}, {"_id": 1})
            if not aktif:
                await cleanup_old_files()
        except Exception as e:
            logger.warning(f"Sapu backup_temp: {e}")
        await asyncio.sleep(300)


_scheduler_task = None


def start_backup_scheduler():
    """Dipanggil dari startup server — jalankan loop di background."""
    global _scheduler_task
    _scheduler_task = _track_bg(asyncio.create_task(backup_scheduler_loop()))


async def stop_backup_scheduler() -> None:
    """Hentikan HANYA loop penjadwal (temuan U22).

    Sengaja TIDAK membatalkan seluruh isi `_BG_TASKS`. Himpunan itu juga
    menampung `run_backup_task` dan `run_restore_task` yang sedang berjalan,
    dan membatalkan RESTORE di tengah jalan adalah keputusan integritas data —
    bukan kebersihan shutdown. Restore punya jalur rollback sendiri; memicunya
    dari shutdown berarti memulai pemulihan yang detik berikutnya ikut mati
    bersama prosesnya, dan itu lebih buruk daripada membiarkan supervisor
    menunggu atau membunuhnya.

    Yang dihentikan di sini hanya loop periodik: ia tak memegang keadaan
    setengah-jadi, jadi membatalkannya selalu aman.
    """
    global _scheduler_task
    t, _scheduler_task = _scheduler_task, None
    if t is None:
        return
    t.cancel()
    try:
        await t
    except (asyncio.CancelledError, Exception):    # noqa: BLE001
        pass


@backup_router.get("/otomatis")
async def get_setelan_otomatis(authorization: str = Header(None)):
    """Setelan backup otomatis + ringkas arsip (untuk panel Pengaturan)."""
    await require_super_admin(authorization)
    s = await db.report_settings.find_one(
        {"type": "backup_otomatis"}, {"_id": 0, "type": 0}) or {}
    arsip = _daftar_arsip()
    return {**_SETELAN_OTOMATIS_DEFAULT, **s,
            "jumlah_arsip": len(arsip),
            "total_ukuran": sum(a["ukuran"] for a in arsip)}


@backup_router.post("/otomatis")
async def set_setelan_otomatis(payload: dict, authorization: str = Header(None)):
    """Simpan setelan backup otomatis (aktif, jam WIB, retensi)."""
    user = await require_super_admin(authorization)
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
    await require_super_admin(authorization)
    return {"items": _daftar_arsip()}


@backup_router.get("/arsip/{nama}")
async def unduh_arsip_backup(nama: str, authorization: str = Header(None),
                             token: str | None = None):
    """Unduh satu berkas arsip (dukung ?token= utk navigasi browser langsung)."""
    effective_auth = authorization
    if not effective_auth and token:
        effective_auth = f"Bearer {token}"
    await require_super_admin(effective_auth)
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
    user = await require_super_admin(authorization)
    if not nama_arsip_valid(nama):
        raise HTTPException(status_code=400, detail="Nama berkas arsip tidak dikenal")
    p = BACKUP_ARSIP_DIR / nama
    if not p.exists():
        raise HTTPException(status_code=404, detail="Berkas arsip tidak ditemukan")
    p.unlink(missing_ok=True)
    logger.info(f"Arsip backup {nama} dihapus oleh {user.get('username')}")
    return {"ok": True}


@backup_router.post("/restore/dari-arsip/{nama}")
async def restore_dari_arsip(nama: str, authorization: str = Header(None),
                             x_satker_aktif: str = Header(default="", alias="X-Satker-Aktif")):
    """Mulai restore langsung dari berkas arsip server (tanpa unggah ulang)."""
    user = await require_super_admin(authorization)
    _tolak_bila_act_as(x_satker_aktif)
    await cleanup_stale_jobs()
    await _guard_recovery()
    if not nama_arsip_valid(nama):
        raise HTTPException(status_code=400, detail="Nama berkas arsip tidak dikenal")
    sumber = BACKUP_ARSIP_DIR / nama
    if not sumber.exists():
        raise HTTPException(status_code=404, detail="Berkas arsip tidak ditemukan")
    active = await db.backup_jobs.find_one(
        {"status": {"$in": ["queued", "running"]}}, {"_id": 0})
    if active:
        raise HTTPException(status_code=409,
                            detail="Sudah ada proses backup/restore yang sedang berjalan")
    job_id = str(uuid.uuid4())[:12]
    # Salin ke temp — proses restore boleh menghapus berkas kerjanya tanpa
    # mengorbankan arsip asli.
    zip_path = BACKUP_TEMP_DIR / f"restore_{job_id}.zip"
    shutil.copyfile(str(sumber), str(zip_path))
    try:
        await db.backup_jobs.insert_one({
            "job_id": job_id, "type": "restore", "status": "queued",
            "active_lock": _ACTIVE_LOCK, "progress": 0,
            "message": "Menunggu mulai...",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "started_by": user.get("username"),
            "source_file": nama,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
    except DuplicateKeyError:
        zip_path.unlink(missing_ok=True)
        raise HTTPException(status_code=409,
                            detail="Sudah ada proses backup/restore yang sedang berjalan")
    _track_bg(asyncio.create_task(run_restore_task(job_id, zip_path, user.get("username"))))
    logger.info(f"Restore dari arsip {nama} dimulai oleh {user.get('username')}")
    return {"job_id": job_id, "message": "Proses restore dari arsip dimulai di background"}


@backup_router.get("/restore/recovery")
async def get_restore_recovery(authorization: str = Header(None)):
    await require_super_admin(authorization)
    return await restore_control_status()


@backup_router.post("/restore/recovery/{job_id}")
async def retry_restore_recovery(job_id: str, confirm_workers_stopped: bool = False, authorization: str = Header(None),
                                  x_satker_aktif: str = Header(default="", alias="X-Satker-Aktif")):
    user = await require_super_admin(authorization)
    _tolak_bila_act_as(x_satker_aktif)
    if not confirm_workers_stopped:
        raise HTTPException(400, "Operator wajib menghentikan worker lama sebelum recovery; gunakan CLI recovery")
    return await recover_restore(job_id, user.get("username"))
