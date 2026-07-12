"""
Audit log routes.
Extracted from assets.py for clean separation of concerns.
Provides: GET /audit-logs
"""
import logging
from fastapi import APIRouter, Depends
from db import db
from auth_utils import require_user
from penghapusan_utils import normalisasi_jejak_terhapus, rekap_jejak_terhapus

logger = logging.getLogger(__name__)
audit_router = APIRouter()


@audit_router.get("/audit-logs")
async def get_audit_logs(activity_id: str = "", asset_id: str = "", page: int = 1, page_size: int = 50,
                         _user: dict = Depends(require_user)):
    """Get audit logs with optional filtering"""
    query = {}
    if activity_id:
        query["activity_id"] = activity_id
    if asset_id:
        query["asset_id"] = asset_id

    # Clamp pagination so a caller can't request an unbounded page and dump the
    # entire audit trail (or drive huge memory use) in one request.
    page = max(page, 1)
    page_size = min(max(page_size, 1), 200)

    total = await db.audit_logs.count_documents(query)
    skip = (page - 1) * page_size
    logs = await db.audit_logs.find(query, {"_id": 0}).sort("timestamp", -1).skip(skip).limit(page_size).to_list(page_size)

    return {
        "logs": logs,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total > 0 else 1
    }


@audit_router.get("/audit-logs/aset-terhapus")
async def get_jejak_aset_terhapus(activity_id: str = "", page: int = 1,
                                  page_size: int = 50,
                                  _user: dict = Depends(require_user)):
    """Jejak Aset Terhapus — arsip read-only dari audit log.

    Aset yang dihapus permanen tetap tertelusur (kode/NUP/nama/nilai/oleh/
    waktu) tanpa mengubah mekanisme penghapusan. Nilai perolehan diambil
    dari perubahan yang direkam saat penghapusan.
    """
    query = {"action": {"$in": ["delete", "bulk_delete"]}}
    if activity_id:
        query["activity_id"] = activity_id
    page = max(page, 1)
    page_size = min(max(page_size, 1), 200)
    total = await db.audit_logs.count_documents(query)
    skip = (page - 1) * page_size
    logs = await db.audit_logs.find(query, {"_id": 0}).sort(
        "timestamp", -1).skip(skip).limit(page_size).to_list(page_size)
    rows = normalisasi_jejak_terhapus(logs)
    return {
        "items": rows,
        "ringkasan": rekap_jejak_terhapus(rows),
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total > 0 else 1,
        "catatan": (
            "Arsip jejak penghapusan aset (read-only) dari log audit. "
            "Penghapusan permanen tetap tercatat di sini untuk penelusuran; "
            "nilai perolehan direkam saat aset dihapus."),
    }
