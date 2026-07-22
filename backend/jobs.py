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
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from db import db

_JOBS = db.background_jobs


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def buat_job(jenis: str, dibuat_oleh: str = "", **extra) -> str:
    """Buat dokumen job baru (status 'queued'); kembalikan job_id (12 hex).

    `extra` = field awal spesifik-konsumen (mis. total/processed untuk impor).
    `created_at` disimpan sebagai BSON datetime agar bisa dipakai TTL index."""
    job_id = uuid.uuid4().hex[:12]
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
