"""
Audit log routes.
Extracted from assets.py for clean separation of concerns.
Provides: GET /audit-logs
"""
import logging
from fastapi import APIRouter
from db import db

logger = logging.getLogger(__name__)
audit_router = APIRouter()


@audit_router.get("/audit-logs")
async def get_audit_logs(activity_id: str = "", asset_id: str = "", page: int = 1, page_size: int = 50):
    """Get audit logs with optional filtering"""
    query = {}
    if activity_id:
        query["activity_id"] = activity_id
    if asset_id:
        query["asset_id"] = asset_id

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
