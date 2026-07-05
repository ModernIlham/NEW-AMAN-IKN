"""
Image compression routes with multi-service fallback chain.
Chain: Tinify → Compresto → Uploadcare → Local (Pillow)
Quota tracking stored in MongoDB.

Provides: POST /compress-image, GET /compression-stats, GET /compression-quotas
Dependencies: tinify (optional), Pillow, httpx
"""
import io
import os
import base64
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from PIL import Image as PILImage
import httpx

from db import db
from auth_utils import require_user
from shared_utils import TINIFY_API_KEY, TINIFY_AVAILABLE

logger = logging.getLogger(__name__)
media_router = APIRouter()

# API Keys from environment
COMPRESTO_API_KEY = os.environ.get("COMPRESTO_API_KEY", "")
UPLOADCARE_PUBLIC_KEY = os.environ.get("UPLOADCARE_PUBLIC_KEY", "")

# Service limits
SERVICE_LIMITS = {
    "tinify": 500,
    "compresto": 500,
    "uploadcare": 1000,  # Free tier ~1000/month
}


# ============================================================================
# QUOTA TRACKING
# ============================================================================
async def get_current_month():
    return datetime.now(timezone.utc).strftime("%Y-%m")


async def get_quota(service: str) -> dict:
    """Get quota usage for a service in current month."""
    month = await get_current_month()
    quota = await db.compression_quotas.find_one(
        {"service": service, "month": month}, {"_id": 0}
    )
    if not quota:
        return {"service": service, "month": month, "used": 0, "limit": SERVICE_LIMITS.get(service, 500)}
    return quota


async def increment_quota(service: str):
    """Increment usage count for a service."""
    month = await get_current_month()
    await db.compression_quotas.update_one(
        {"service": service, "month": month},
        {
            "$inc": {"used": 1},
            "$setOnInsert": {"limit": SERVICE_LIMITS.get(service, 500)},
        },
        upsert=True,
    )


async def is_quota_available(service: str) -> bool:
    """Check if quota is still available for a service."""
    quota = await get_quota(service)
    return quota["used"] < quota.get("limit", SERVICE_LIMITS.get(service, 500))


# ============================================================================
# COMPRESSION METHODS
# ============================================================================
def compress_with_pillow(image_bytes: bytes, max_size_kb: int = 500) -> bytes:
    """Local compression using Pillow (always available)."""
    try:
        img = PILImage.open(io.BytesIO(image_bytes))
        if img.mode in ('RGBA', 'LA', 'P'):
            background = PILImage.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'RGBA':
                background.paste(img, mask=img.split()[-1])
            else:
                background.paste(img)
            img = background

        current_size = len(image_bytes) / 1024
        if current_size > max_size_kb:
            ratio = (max_size_kb / current_size) ** 0.5
            new_width = int(img.width * ratio)
            new_height = int(img.height * ratio)
            img = img.resize((new_width, new_height), PILImage.LANCZOS)

        output = io.BytesIO()
        quality = 85
        img.save(output, format='JPEG', quality=quality, optimize=True)
        while output.tell() / 1024 > max_size_kb and quality > 30:
            output = io.BytesIO()
            quality -= 10
            img.save(output, format='JPEG', quality=quality, optimize=True)
        return output.getvalue()
    except Exception as e:
        logger.error(f"Pillow compression error: {e}")
        raise


async def compress_with_tinify(image_bytes: bytes) -> Optional[bytes]:
    """Compress using Tinify API."""
    if not TINIFY_AVAILABLE:
        return None
    if not await is_quota_available("tinify"):
        logger.info("Tinify quota exhausted")
        return None
    try:
        import tinify
        compressed = await asyncio.to_thread(tinify.from_buffer(image_bytes).to_buffer)
        await increment_quota("tinify")
        return compressed
    except Exception as e:
        logger.warning(f"Tinify error: {e}")
        return None


async def compress_with_compresto(image_bytes: bytes) -> Optional[bytes]:
    """Compress using Compresto API."""
    if not COMPRESTO_API_KEY:
        return None
    if not await is_quota_available("compresto"):
        logger.info("Compresto quota exhausted")
        return None
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.compresto.app/v1/compress",
                headers={"X-API-Key": COMPRESTO_API_KEY},
                files={"image": ("photo.jpg", image_bytes, "image/jpeg")},
                data={"quality": "80", "format": "jpeg"},
            )
            if response.status_code == 200:
                await increment_quota("compresto")
                return response.content
            elif response.status_code == 429:
                logger.warning("Compresto rate limit reached")
                return None
            else:
                logger.warning(f"Compresto error {response.status_code}: {response.text[:200]}")
                return None
    except Exception as e:
        logger.warning(f"Compresto error: {e}")
        return None


async def compress_with_uploadcare(image_bytes: bytes) -> Optional[bytes]:
    """Compress using Uploadcare Upload API + CDN transformations."""
    if not UPLOADCARE_PUBLIC_KEY:
        return None
    if not await is_quota_available("uploadcare"):
        logger.info("Uploadcare quota exhausted")
        return None
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Upload to Uploadcare
            response = await client.post(
                "https://upload.uploadcare.com/base/",
                data={
                    "UPLOADCARE_PUB_KEY": UPLOADCARE_PUBLIC_KEY,
                    "UPLOADCARE_STORE": "0",  # Don't store permanently
                },
                files={"file": ("photo.jpg", image_bytes, "image/jpeg")},
            )
            if response.status_code != 200:
                logger.warning(f"Uploadcare upload error: {response.status_code}")
                return None

            file_id = response.json().get("file")
            if not file_id:
                return None

            # Download compressed version via CDN with quality reduction
            cdn_url = f"https://ucarecdn.com/{file_id}/-/quality/smart/-/format/jpeg/"
            dl_response = await client.get(cdn_url)
            if dl_response.status_code == 200:
                await increment_quota("uploadcare")
                return dl_response.content
            else:
                logger.warning(f"Uploadcare CDN error: {dl_response.status_code}")
                return None
    except Exception as e:
        logger.warning(f"Uploadcare error: {e}")
        return None


# ============================================================================
# MAIN COMPRESSION FUNCTION (Fallback Chain)
# ============================================================================
async def auto_compress_image(image_data_b64: str) -> tuple:
    """
    Auto-compress image using fallback chain:
    Tinify → Compresto → Uploadcare → Pillow (local)
    Returns: (compressed_b64, method, original_size, compressed_size)
    """
    try:
        if ',' in image_data_b64:
            _, encoded = image_data_b64.split(',', 1)
        else:
            encoded = image_data_b64

        image_bytes = base64.b64decode(encoded)
        original_size = len(image_bytes)

        # CHAIN: Tinify → Compresto → Uploadcare → Pillow
        methods = [
            ("tinify", compress_with_tinify),
            ("compresto", compress_with_compresto),
            ("uploadcare", compress_with_uploadcare),
        ]

        for method_name, compress_fn in methods:
            compressed = await compress_fn(image_bytes)
            if compressed and len(compressed) < original_size:
                compressed_b64 = base64.b64encode(compressed).decode('utf-8')
                return f"data:image/jpeg;base64,{compressed_b64}", method_name, original_size, len(compressed)

        # Final fallback: Pillow (always works)
        compressed = compress_with_pillow(image_bytes)
        compressed_b64 = base64.b64encode(compressed).decode('utf-8')
        return f"data:image/jpeg;base64,{compressed_b64}", "pillow", original_size, len(compressed)

    except Exception as e:
        logger.error(f"Auto-compress failed: {e}, using original")
        return image_data_b64, "none", 0, 0


# ============================================================================
# API ENDPOINTS
# ============================================================================
class CompressRequest(BaseModel):
    image_data: str

class CompressResponse(BaseModel):
    success: bool
    compressed_data: Optional[str] = None
    original_size: int = 0
    compressed_size: int = 0
    method: str = "none"
    error: Optional[str] = None


@media_router.post("/compress-image", response_model=CompressResponse)
async def compress_image(request: CompressRequest, _user: dict = Depends(require_user)):
    """Compress image using fallback chain: Tinify → Compresto → Uploadcare → Pillow"""
    try:
        compressed_b64, method, original_size, compressed_size = await auto_compress_image(request.image_data)
        return CompressResponse(
            success=True,
            compressed_data=compressed_b64,
            original_size=original_size,
            compressed_size=compressed_size,
            method=method,
        )
    except Exception:
        # Never leak internal exception detail to the client; log it server-side.
        logger.exception("Compression error")
        return CompressResponse(success=False, error="Gagal mengompres gambar")


@media_router.get("/compression-stats")
async def get_compression_stats():
    """Get current Tinify compression usage stats (backward compatible)."""
    stats = {
        "tinify_available": TINIFY_AVAILABLE,
        "tinify_api_key_set": bool(TINIFY_API_KEY),
        "monthly_limit": 500,
        "compressions_this_month": 0,
        "remaining": 500,
    }
    if TINIFY_AVAILABLE:
        try:
            import tinify
            tinify.validate()
            stats["compressions_this_month"] = getattr(tinify, 'compression_count', 0) or 0
            stats["remaining"] = 500 - stats["compressions_this_month"]
        except Exception as e:
            stats["error"] = str(e)
    return stats


@media_router.get("/compression-quotas")
async def get_all_compression_quotas():
    """Get quota status for ALL compression services."""
    month = await get_current_month()
    quotas = []

    # Tinify
    tinify_quota = await get_quota("tinify")
    tinify_used = tinify_quota["used"]
    # Also check Tinify's own counter
    if TINIFY_AVAILABLE:
        try:
            import tinify
            tinify.validate()
            tinify_api_count = getattr(tinify, 'compression_count', 0) or 0
            if tinify_api_count > tinify_used:
                tinify_used = tinify_api_count
        except Exception:
            pass
    quotas.append({
        "service": "tinify",
        "name": "Tinify (TinyPNG)",
        "used": tinify_used,
        "limit": SERVICE_LIMITS["tinify"],
        "remaining": max(0, SERVICE_LIMITS["tinify"] - tinify_used),
        "available": bool(TINIFY_API_KEY),
        "month": month,
    })

    # Compresto
    compresto_quota = await get_quota("compresto")
    quotas.append({
        "service": "compresto",
        "name": "Compresto",
        "used": compresto_quota["used"],
        "limit": SERVICE_LIMITS["compresto"],
        "remaining": max(0, SERVICE_LIMITS["compresto"] - compresto_quota["used"]),
        "available": bool(COMPRESTO_API_KEY),
        "month": month,
    })

    # Uploadcare
    uploadcare_quota = await get_quota("uploadcare")
    quotas.append({
        "service": "uploadcare",
        "name": "Uploadcare",
        "used": uploadcare_quota["used"],
        "limit": SERVICE_LIMITS["uploadcare"],
        "remaining": max(0, SERVICE_LIMITS["uploadcare"] - uploadcare_quota["used"]),
        "available": bool(UPLOADCARE_PUBLIC_KEY),
        "month": month,
    })

    # Pillow (always available, unlimited)
    quotas.append({
        "service": "pillow",
        "name": "Lokal (Pillow)",
        "used": 0,
        "limit": -1,  # Unlimited
        "remaining": -1,
        "available": True,
        "month": month,
    })

    return {"quotas": quotas, "month": month}
