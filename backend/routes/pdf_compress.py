"""
PDF Compression routes.
Chain: iLoveAPI → WhipDoc
Provides: POST /compress-pdf, GET /pdf-compression-quotas
"""
import os
import io
import logging
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, UploadFile, File
from fastapi.responses import StreamingResponse
import httpx

from db import db

logger = logging.getLogger(__name__)
pdf_compress_router = APIRouter()

ILOVEAPI_PUBLIC_KEY = os.environ.get("ILOVEAPI_PUBLIC_KEY", "")
ILOVEAPI_SECRET_KEY = os.environ.get("ILOVEAPI_SECRET_KEY", "")
WHIPDOC_API_KEY = os.environ.get("WHIPDOC_API_KEY", "")

PDF_SERVICE_LIMITS = {
    "iloveapi": 250,    # Free tier
    "whipdoc": 50,      # Free tier: 50/month
}


async def get_current_month():
    return datetime.now(timezone.utc).strftime("%Y-%m")


async def get_pdf_quota(service: str) -> dict:
    month = await get_current_month()
    quota = await db.pdf_compression_quotas.find_one(
        {"service": service, "month": month}, {"_id": 0}
    )
    if not quota:
        return {"service": service, "month": month, "used": 0, "limit": PDF_SERVICE_LIMITS.get(service, 100)}
    return quota


async def increment_pdf_quota(service: str):
    month = await get_current_month()
    await db.pdf_compression_quotas.update_one(
        {"service": service, "month": month},
        {"$inc": {"used": 1}, "$setOnInsert": {"limit": PDF_SERVICE_LIMITS.get(service, 100)}},
        upsert=True,
    )


async def is_pdf_quota_available(service: str) -> bool:
    quota = await get_pdf_quota(service)
    return quota["used"] < quota.get("limit", PDF_SERVICE_LIMITS.get(service, 100))


# ============================================================================
# iLoveAPI PDF Compression (4-step workflow)
# ============================================================================
async def compress_pdf_iloveapi(pdf_bytes: bytes, filename: str) -> tuple:
    """
    Compress PDF using iLoveAPI (4 steps: start → upload → process → download).
    Returns: (compressed_bytes, method) or (None, None)
    """
    if not ILOVEAPI_PUBLIC_KEY or not ILOVEAPI_SECRET_KEY:
        return None, None
    if not await is_pdf_quota_available("iloveapi"):
        logger.info("iLoveAPI quota exhausted")
        return None, None

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Step 1: Start task
            start_resp = await client.post(
                "https://api.iloveapi.com/v1/start",
                headers={"Content-Type": "application/json"},
                json={
                    "public_key": ILOVEAPI_PUBLIC_KEY,
                    "tool": "compress",
                },
            )
            if start_resp.status_code != 200:
                logger.warning(f"iLoveAPI start error: {start_resp.status_code} {start_resp.text[:200]}")
                return None, None

            start_data = start_resp.json()
            task_id = start_data.get("task")
            server = start_data.get("server")
            if not task_id or not server:
                logger.warning("iLoveAPI start: missing task/server")
                return None, None

            # Step 2: Upload file
            upload_resp = await client.post(
                f"https://{server}/v1/upload",
                data={"task": task_id},
                files={"file": (filename, pdf_bytes, "application/pdf")},
            )
            if upload_resp.status_code != 200:
                logger.warning(f"iLoveAPI upload error: {upload_resp.status_code}")
                return None, None

            upload_data = upload_resp.json()
            server_filename = upload_data.get("server_filename")
            if not server_filename:
                logger.warning("iLoveAPI upload: missing server_filename")
                return None, None

            # Step 3: Process (compress)
            process_resp = await client.post(
                f"https://{server}/v1/process",
                json={
                    "task": task_id,
                    "tool": "compress",
                    "files": [{"server_filename": server_filename, "filename": filename}],
                    "compression_level": "recommended",
                },
            )
            if process_resp.status_code != 200:
                logger.warning(f"iLoveAPI process error: {process_resp.status_code}")
                return None, None

            # Step 4: Download
            download_resp = await client.get(f"https://{server}/v1/download/{task_id}")
            if download_resp.status_code == 200:
                await increment_pdf_quota("iloveapi")
                return download_resp.content, "iloveapi"
            else:
                logger.warning(f"iLoveAPI download error: {download_resp.status_code}")
                return None, None

    except Exception as e:
        logger.warning(f"iLoveAPI error: {e}")
        return None, None


# ============================================================================
# WhipDoc PDF Compression (Simple POST)
# ============================================================================
async def compress_pdf_whipdoc(pdf_bytes: bytes, filename: str) -> tuple:
    """
    Compress PDF using WhipDoc API (single POST).
    Returns: (compressed_bytes, method) or (None, None)
    """
    if not WHIPDOC_API_KEY:
        return None, None
    if not await is_pdf_quota_available("whipdoc"):
        logger.info("WhipDoc quota exhausted")
        return None, None

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.whipdoc.com/v1/compress",
                headers={"X-API-Key": WHIPDOC_API_KEY},
                files={"file": (filename, pdf_bytes, "application/pdf")},
            )
            if response.status_code == 200:
                await increment_pdf_quota("whipdoc")
                return response.content, "whipdoc"
            elif response.status_code == 429:
                logger.warning("WhipDoc rate limit reached")
                return None, None
            else:
                logger.warning(f"WhipDoc error {response.status_code}: {response.text[:200]}")
                return None, None
    except Exception as e:
        logger.warning(f"WhipDoc error: {e}")
        return None, None


# ============================================================================
# API ENDPOINTS
# ============================================================================
@pdf_compress_router.post("/compress-pdf")
async def compress_pdf(file: UploadFile = File(...)):
    """
    Compress PDF using fallback chain: iLoveAPI → WhipDoc.
    Returns compressed PDF file.
    """
    try:
        pdf_bytes = await file.read()
        original_size = len(pdf_bytes)
        filename = file.filename or "document.pdf"

        # Try iLoveAPI first
        compressed, method = await compress_pdf_iloveapi(pdf_bytes, filename)

        # Fallback to WhipDoc
        if not compressed:
            compressed, method = await compress_pdf_whipdoc(pdf_bytes, filename)

        if compressed and len(compressed) < original_size:
            compressed_size = len(compressed)
            savings = round((1 - compressed_size / original_size) * 100)
            logger.info(f"PDF compressed: {original_size//1024}KB → {compressed_size//1024}KB ({savings}% via {method})")

            return StreamingResponse(
                io.BytesIO(compressed),
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f'attachment; filename="compressed_{filename}"',
                    "X-Original-Size": str(original_size),
                    "X-Compressed-Size": str(compressed_size),
                    "X-Compression-Method": method,
                    "X-Savings-Percent": str(savings),
                },
            )
        else:
            # Return original if no compression available or no savings
            return StreamingResponse(
                io.BytesIO(pdf_bytes),
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "X-Original-Size": str(original_size),
                    "X-Compressed-Size": str(original_size),
                    "X-Compression-Method": "none",
                    "X-Savings-Percent": "0",
                },
            )

    except Exception as e:
        logger.error(f"PDF compression error: {e}")
        return {"error": str(e), "success": False}


@pdf_compress_router.get("/pdf-compression-quotas")
async def get_pdf_compression_quotas():
    """Get quota status for all PDF compression services."""
    month = await get_current_month()
    quotas = []

    for service, limit in PDF_SERVICE_LIMITS.items():
        quota = await get_pdf_quota(service)
        key_available = bool(ILOVEAPI_PUBLIC_KEY) if service == "iloveapi" else bool(WHIPDOC_API_KEY)
        quotas.append({
            "service": service,
            "name": "iLoveAPI" if service == "iloveapi" else "WhipDoc",
            "used": quota["used"],
            "limit": limit,
            "remaining": max(0, limit - quota["used"]),
            "available": key_available,
            "month": month,
        })

    return {"quotas": quotas, "month": month}
