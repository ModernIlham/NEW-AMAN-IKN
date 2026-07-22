"""Endpoint generik untuk job latar (jobs.py): status & unduh hasil.

Dipakai konsumen mana pun (mis. ekspor XLSX async). Status via header Bearer;
unduh mendukung DUAL-auth (header ATAU ?token=) agar bisa lewat anchor/window.open
native untuk file besar (pola sama dengan /backup/download). Akses dibatasi
PEMILIK job (dibuat_oleh) atau admin/super-admin.
"""
import io

from fastapi import APIRouter, Depends, HTTPException

from auth_utils import require_user, require_user_or_query_token
from fastapi.responses import StreamingResponse
from jobs import get_job, ambil_artifact
from shared_utils import nama_file_disposition

jobs_router = APIRouter()


def _boleh_akses(job: dict, user: dict) -> bool:
    """Hanya PEMILIK job atau admin/super-admin. FAIL-CLOSED: job tanpa pemilik
    (dibuat_oleh kosong) TIDAK terbuka untuk user biasa (cegah unduh silang)."""
    if str(user.get("role") or "") in ("admin", "super_admin"):
        return True
    pemilik = str(job.get("dibuat_oleh") or "").strip()
    username = str(user.get("username") or "").strip()
    return bool(pemilik) and bool(username) and pemilik == username


@jobs_router.get("/jobs/{job_id}")
async def status_job(job_id: str, user: dict = Depends(require_user)):
    """Status job latar (untuk polling progres klien)."""
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job tidak ditemukan")
    if not _boleh_akses(job, user):
        raise HTTPException(status_code=403, detail="Bukan job Anda")
    return job


@jobs_router.get("/jobs/{job_id}/download")
async def download_job(job_id: str,
                       user: dict = Depends(require_user_or_query_token)):
    """Unduh hasil (artifact) job yang sudah selesai — dari GridFS."""
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job tidak ditemukan")
    if not _boleh_akses(job, user):
        raise HTTPException(status_code=403, detail="Bukan job Anda")
    if job.get("status") != "done" or not job.get("artifact_id"):
        raise HTTPException(status_code=404, detail="Hasil belum siap atau kedaluwarsa")
    hasil = await ambil_artifact(job_id)
    if not hasil:
        raise HTTPException(status_code=404, detail="Hasil kedaluwarsa")
    data, filename, ctype = hasil
    aman = nama_file_disposition(filename)
    return StreamingResponse(
        io.BytesIO(data), media_type=ctype,
        headers={"Content-Disposition": f'attachment; filename="{aman}"'})
