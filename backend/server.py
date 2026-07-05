# ============================================================================
# BACKEND SERVER - MODULAR ENTRY POINT
# ============================================================================
# Framework: FastAPI
# Database: MongoDB (Motor)
# Features: JWT Auth, CRUD Assets, Categories, Export (CSV/PDF/Excel), Import
# Optimizations: GZip, Connection Pooling, Indexing, Caching, Pagination
# ============================================================================

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

from fastapi import FastAPI, APIRouter, Depends
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# Load environment
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Shared modules
from db import db, client
from shared_utils import limiter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI()
api_router = APIRouter(prefix="/api")

# Rate Limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# GZip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# CORS — env-driven allowlist (never wildcard while allow_credentials=True).
# Reads ALLOWED_ORIGINS (comma-separated); falls back to the legacy CORS_ORIGINS
# used by the Hostinger deployment, then to a safe default that covers the prod
# domain (amanikn-inventarisasi.com, http+https) and local dev.
_default_origins = [
    "https://amanikn-inventarisasi.com",
    "http://amanikn-inventarisasi.com",
    "https://www.amanikn-inventarisasi.com",
    "http://localhost:3000",
]
_origins_env = os.environ.get("ALLOWED_ORIGINS") or os.environ.get("CORS_ORIGINS") or ""
ALLOWED_ORIGINS = [o.strip() for o in _origins_env.split(",") if o.strip()] or _default_origins
logger.info(f"CORS allowed origins: {ALLOWED_ORIGINS}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Log config status
from shared_utils import TINIFY_API_KEY, RESEND_API_KEY
if TINIFY_API_KEY:
    logger.info("Tinify API configured")
if RESEND_API_KEY:
    logger.info("Resend API configured for OTP emails")


# ============================================================================
# DATABASE INDEXES
# ----------------------------------------------------------------------------
# Moved to /app/backend/indexes.py to break a circular import with
# routes/backup.py (which re-creates indexes after a restore).
# ============================================================================

from indexes import create_indexes  # noqa: E402  (re-exported for back-compat)


# ============================================================================
# STARTUP & SHUTDOWN
# ============================================================================

@app.on_event("startup")
async def startup_event():
    await create_indexes()
    # Backfill OCC version field for legacy assets (data that was created before
    # OCC was introduced, or restored from older backups). Without this, the
    # CAS update query {"id": ..., "version": 1} will never match a document
    # that has no version field and every edit will produce a false 409.
    try:
        res = await db.assets.update_many(
            {"version": {"$exists": False}},
            {"$set": {"version": 1}},
        )
        if res.modified_count:
            logger.info(f"OCC backfill: set version=1 on {res.modified_count} legacy asset(s)")
    except Exception as e:
        logger.warning(f"OCC version backfill failed (non-fatal): {e}")
    # Backfill nomor tiket kegiatan (INV-{tahun}-{seq}) untuk kegiatan lama.
    # Idempotent & aman multi-worker (guard $exists per dokumen).
    try:
        from routes.pengesahan import backfill_ticket_numbers
        await backfill_ticket_numbers()
    except Exception as e:
        logger.warning(f"Ticket number backfill failed (non-fatal, lazy backfill covers it): {e}")
    # Start cross-worker WebSocket event bus (capped collection + tailable cursor)
    try:
        from routes.websocket import start_event_bus
        await start_event_bus()
    except Exception as e:
        logger.warning(f"Event bus startup failed (real-time fanout limited to single worker): {e}")
    logger.info("Application started successfully")
    logger.info(f"MongoDB connected: {os.environ['DB_NAME']}")

@app.on_event("shutdown")
async def shutdown_event():
    try:
        from routes.websocket import stop_event_bus
        await stop_event_bus()
    except Exception:
        pass
    client.close()
    logger.info("Application shutdown complete")


# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/health")
async def root_health_check():
    """Root-level health check for Kubernetes load balancer probes"""
    return {"status": "ok"}

@api_router.get("/health")
async def api_health_check():
    """Lightweight reachability probe for the frontend's offline detection
    (lib/connectivity.js). No auth, no DB — must stay instant and dependency-free."""
    return {"ok": True}

@api_router.get("/")
async def health_check():
    return {
        "status": "ok",
        "message": "Inventory API is running",
        "version": "3.0.0",
        "architecture": "modular"
    }

@api_router.get("/user/")
async def user_health_check():
    return {"status": "ok"}


# ============================================================================
# INCLUDE ALL ROUTE MODULES
# ============================================================================

from routes.auth import auth_router
from routes.categories import categories_router
from routes.assets import assets_router
from routes.imports import imports_router
from routes.templates import templates_router
from routes.validation import validation_router
from routes.cards import cards_router
from routes.activities import activities_router
from routes.users import users_router
from routes.reports import reports_router
from routes.websocket import ws_router
from routes.backup import backup_router
from routes.audit import audit_router
from routes.media import media_router
from routes.exports import exports_router
from routes.pdf_compress import pdf_compress_router
from routes.batch import batch_router
from routes.documents import documents_router
from routes.pengesahan import pengesahan_router

api_router.include_router(auth_router)
api_router.include_router(categories_router)
api_router.include_router(batch_router)      # MUST be before assets_router (specific routes before {asset_id} catch-all)
api_router.include_router(exports_router)    # MUST be before assets_router
api_router.include_router(pengesahan_router)  # MUST be before assets_router (/assets/kartu-inventarisasi)
api_router.include_router(assets_router)
api_router.include_router(imports_router)
api_router.include_router(templates_router)
api_router.include_router(validation_router)
api_router.include_router(cards_router)
api_router.include_router(activities_router)
api_router.include_router(users_router)
api_router.include_router(reports_router)
api_router.include_router(ws_router)
api_router.include_router(backup_router)
api_router.include_router(audit_router)
api_router.include_router(media_router)
api_router.include_router(pdf_compress_router)
api_router.include_router(documents_router)


# ============================================================================
# INVENTORY CLASSIFICATIONS (uses constants from shared_utils)
# ============================================================================

from shared_utils import (
    VALID_INVENTORY_STATUSES, VALID_KLASIFIKASI,
    VALID_SUB_KLASIFIKASI_PENCATATAN, VALID_SUB_KLASIFIKASI_LAINNYA
)

@api_router.get("/inventory-classifications")
async def get_inventory_classifications():
    return {
        "inventory_statuses": VALID_INVENTORY_STATUSES,
        "klasifikasi": VALID_KLASIFIKASI,
        "sub_klasifikasi": {
            "Kesalahan Pencatatan": VALID_SUB_KLASIFIKASI_PENCATATAN,
            "Tidak Ditemukan Lainnya": VALID_SUB_KLASIFIKASI_LAINNYA
        },
        "berlebih_info": {
            "pengertian": "BMN yang ditemukan secara fisik saat inventarisasi tetapi tidak tercatat dalam Daftar BMN.",
            "contoh": ["BMN tidak tercatat dalam SIMAK-BMN", "BMN dari satker lain tanpa proses administrasi", "Barang hibah yang belum dicatatkan", "Jumlah fisik lebih dari catatan pembukuan"],
            "tindak_lanjut": ["Daftarkan ke dalam Daftar BMN jika sah", "Proses serah terima resmi jika dari satker lain", "Pemindahtanganan jika melebihi SBSK", "Laporkan ke KPKNL/DJKN untuk penertiban"]
        },
        "sengketa_info": {
            "pengertian": "BMN yang sedang dalam perselisihan hukum mengenai status kepemilikan, penguasaan, atau keberadaannya.",
            "contoh": ["Tanah/bangunan yang digugat pihak lain di pengadilan", "BMN diklaim lebih dari satu instansi", "Sertifikat tanah tumpang tindih", "BMN disita/diblokir terkait perkara hukum"],
            "tindak_lanjut": ["Koordinasi dengan bagian hukum instansi", "Pantau perkembangan putusan pengadilan", "Tindak lanjut sesuai putusan inkracht", "Laporkan ke DJKN untuk penanganan"]
        }
    }


# ============================================================================
# SYSTEM RESET (admin only - hidden feature)
# ============================================================================

from models import ResetConfirmation
from auth_utils import require_admin

@api_router.delete("/system/reset-all")
async def reset_all_data(data: ResetConfirmation, _admin: dict = Depends(require_admin)):
    admin_user = await db.users.find_one({"id": data.admin_id})
    if not admin_user or admin_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Hanya admin yang dapat melakukan reset sistem")
    if data.confirmation != "HAPUS SEMUA":
        raise HTTPException(status_code=400, detail="Kata konfirmasi tidak valid")

    deleted_assets = await db.assets.delete_many({})
    deleted_activities = await db.inventory_activities.delete_many({})
    deleted_categories = await db.categories.delete_many({})
    deleted_audit_logs = await db.audit_logs.delete_many({})
    # Riwayat pengesahan (kartu inventarisasi) dan counter tiket ikut direset —
    # tanpa ini kartu masih menampilkan riwayat kegiatan yang sudah dihapus.
    deleted_history = await db.inventory_history.delete_many({})
    await db.counters.delete_many({})

    logger.warning(f"SYSTEM RESET by admin {admin_user.get('username')}: "
                   f"Deleted {deleted_assets.deleted_count} assets, "
                   f"{deleted_activities.deleted_count} activities, "
                   f"{deleted_categories.deleted_count} categories, "
                   f"{deleted_audit_logs.deleted_count} audit logs, "
                   f"{deleted_history.deleted_count} history records")

    return {
        "message": "Semua data berhasil dihapus. Sistem telah direset.",
        "deleted": {
            "assets": deleted_assets.deleted_count,
            "activities": deleted_activities.deleted_count,
            "categories": deleted_categories.deleted_count,
            "audit_logs": deleted_audit_logs.deleted_count,
            "inventory_history": deleted_history.deleted_count
        }
    }


# ============================================================================
# MOUNT ROUTER & RUN
# ============================================================================

from fastapi import HTTPException

app.include_router(api_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8001,
        log_level="info"
    )
