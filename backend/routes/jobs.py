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
    """Hanya PEMILIK job, atau admin DARI SATKER YANG SAMA. FAIL-CLOSED: job
    tanpa pemilik (dibuat_oleh kosong) TIDAK terbuka untuk user biasa.

    ISOLASI SATKER (REVIEW-9 R15): dulu SEMUA admin lolos tanpa cek satker,
    sehingga admin satker A dapat mengunduh artifact ekspor satker B — berisi
    register aset lengkap milik B. Kini bypass admin dibatasi satkernya
    sendiri; job era-lama tanpa stempel tetap terbuka bagi admin (konvensi
    dokumen tanpa kode_satker), pemiliknya sendiri selalu boleh.
    """
    from shared_utils import kode_satker_user

    pemilik = str(job.get("dibuat_oleh") or "").strip()
    username = str(user.get("username") or "").strip()
    if bool(pemilik) and bool(username) and pemilik == username:
        return True
    if str(user.get("role") or "") in ("admin", "super_admin"):
        milik = str(job.get("kode_satker") or "").strip()
        kode = kode_satker_user(user)
        if not kode:
            return True          # super-admin pusat: lintas satker
        # FAIL-CLOSED untuk job TANPA stempel (REVIEW-9 R15b). Pada dokumen
        # biasa kode kosong berarti "era lama, terbuka"; pada JOB artinya
        # pembuatnya super-admin pusat — dan artifact ekspornya justru berisi
        # register LINTAS SATKER. Membukanya untuk admin satker persis
        # membalikkan maksud isolasi. Job lama tanpa stempel pun ikut tertutup;
        # pemiliknya sendiri tetap bisa mengunduh lewat cabang di atas.
        return bool(milik) and milik == kode
    return False


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
