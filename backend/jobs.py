"""Infrastruktur job latar BERSAMA, persisten di MongoDB (db.background_jobs).

Menggantikan pola job yang tersebar & rapuh:
- Impor kategori dulu memakai dict IN-MEMORY yang RUSAK di multi-worker
  (uvicorn --workers 4): POST menaruh progres di memori satu worker, tetapi poll
  progres bisa mendarat di worker LAIN → 404 / progres macet. Dengan state di
  Mongo, job tahan multi-worker & restart proses.
- Backup/restore punya polanya sendiri (db.backup_jobs, artifact di disk) — tetap
  di routes/backup.py; modul ini fondasi untuk konsumen baru (mis. ekspor berat).

Dokumen job auto-hapus via TTL index pada `created_at` (lihat indexes.py) sehingga
tak menumpuk. Artifact besar (hasil ekspor) disimpan di GridFS (menyusul).
"""
import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from db import db

logger = logging.getLogger(__name__)
_JOBS = db.background_jobs


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def buat_job(jenis: str, dibuat_oleh: str = "", **extra) -> str:
    """Buat dokumen job baru (status 'queued'); kembalikan job_id (12 hex).

    `extra` = field awal spesifik-konsumen (mis. total/processed untuk impor).
    `created_at` disimpan sebagai BSON datetime agar bisa dipakai TTL index."""
    job_id = uuid.uuid4().hex   # 32 hex (128-bit) — tak dapat ditebak/enumerasi
    doc = {
        "job_id": job_id, "jenis": str(jenis or ""), "status": "queued",
        "dibuat_oleh": str(dibuat_oleh or ""),
        "created_at": _now(), "updated_at": _now(),
    }
    doc.update(extra)
    await _JOBS.insert_one(doc)
    return job_id


async def update_job(job_id: str, **fields) -> None:
    """Patch field job (selalu memperbarui updated_at). Aman dipanggil berkala."""
    fields["updated_at"] = _now()
    await _JOBS.update_one({"job_id": job_id}, {"$set": fields})


async def get_job(job_id: str) -> Optional[dict]:
    """Ambil dokumen job untuk klien (tanpa _id & timestamp BSON internal)."""
    return await _JOBS.find_one(
        {"job_id": job_id}, {"_id": 0, "created_at": 0, "updated_at": 0})


async def simpan_artifact(job_id: str, data: bytes, filename: str,
                          content_type: str) -> str:
    """Simpan HASIL job (mis. file ekspor) ke GridFS & catat referensinya di
    dokumen job. Kembalikan gridfs id. Dipakai worker saat job selesai — file
    ikut TTL GridFS/pembersihan terpisah; dokumen job auto-hapus 7 hari."""
    from bson import ObjectId
    from shared_utils import fs_bucket
    file_id = ObjectId()
    grid_in = fs_bucket.open_upload_stream_with_id(
        file_id, filename=filename,
        metadata={"content_type": content_type, "size": len(data),
                  "job_id": job_id})
    await grid_in.write(data)
    await grid_in.close()
    await update_job(job_id, artifact_id=str(file_id), artifact_nama=filename,
                     artifact_type=content_type, artifact_size=len(data))
    return str(file_id)


async def ambil_artifact(job_id: str):
    """(bytes, filename, content_type) artifact job dari GridFS; None bila job/
    artifact tak ada atau sudah kedaluwarsa."""
    job = await _JOBS.find_one({"job_id": job_id}, {"_id": 0})
    if not job or not job.get("artifact_id"):
        return None
    from shared_utils import get_document_from_gridfs
    data = await get_document_from_gridfs(job["artifact_id"])
    if data is None:
        return None
    return (data, job.get("artifact_nama") or "download.bin",
            job.get("artifact_type") or "application/octet-stream")


async def bersihkan_job_basi(menit: int = 60) -> int:
    """Relabel job 'queued'/'running' yang tak update > `menit` jadi 'failed'
    (task bisa mati diam-diam). Hanya menyentuh dokumen — tak menghentikan task
    asyncio yang mungkin masih jalan. Kembalikan jumlah job yang di-relabel."""
    batas = _now() - timedelta(minutes=max(1, menit))
    res = await _JOBS.update_many(
        {"status": {"$in": ["queued", "running", "importing"]},
         "updated_at": {"$lt": batas}},
        {"$set": {"status": "error", "error_message": "Timeout (job macet)",
                  "done": True, "updated_at": _now()}})
    return res.modified_count


async def bersihkan_artifact_yatim(hari: int = 7) -> int:
    """Hapus blob artifact ekspor di GridFS yang lebih tua dari `hari`. Dokumen
    job auto-hapus via TTL (7 hari) tetapi blob GridFS TIDAK ikut terhapus (koleksi
    terpisah, tanpa cascade) → tanpa sapuan ini GridFS tumbuh tak terbatas oleh
    hasil ekspor. Hanya menyasar file ber-`metadata.job_id` (artifact job), jadi
    foto/dokumen aset TAK tersentuh. Idempoten (aman jalan di banyak worker)."""
    from shared_utils import fs_bucket
    batas = _now() - timedelta(days=max(1, hari))
    n = 0
    try:
        async for f in db["fs.files"].find(
                {"metadata.job_id": {"$exists": True}, "uploadDate": {"$lt": batas}},
                {"_id": 1}):
            try:
                await fs_bucket.delete(f["_id"])
                n += 1
            except Exception:
                pass
    except Exception as e:
        logger.warning("bersihkan_artifact_yatim gagal: %s", e)
    return n


_maintenance_task = None


async def _job_maintenance_loop():
    """Pemeliharaan periodik: relabel job macet + sapu artifact ekspor yatim."""
    while True:
        try:
            await asyncio.sleep(3600)   # tiap jam
            n1 = await bersihkan_job_basi(60)
            n2 = await bersihkan_artifact_yatim(7)
            if n1 or n2:
                logger.info("Pemeliharaan job: %s job macet di-relabel, %s "
                            "artifact yatim dihapus", n1, n2)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("Pemeliharaan job (non-fatal): %s", e)


def start_job_maintenance() -> None:
    """Jadwalkan loop pemeliharaan job (dipanggil sekali saat startup)."""
    global _maintenance_task
    if _maintenance_task is not None:
        return
    _maintenance_task = asyncio.create_task(_job_maintenance_loop())
