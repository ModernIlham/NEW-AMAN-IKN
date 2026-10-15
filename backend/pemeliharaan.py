"""Restore maintenance separates durable data safety from worker liveness.

A stale heartbeat never proves a half-restored dataset is safe. restore_control
is local, excluded from archives/reset and has no TTL. Request writer leases
let the restore coordinator drain requests admitted just before the gate rose.
"""
import asyncio
import contextlib
import time
import uuid
import logging
from contextvars import ContextVar
from datetime import datetime, timezone

from fastapi import HTTPException
from fastapi.responses import JSONResponse

JALUR_BEBAS = ("/health", "/api/health/deep", "/api/backup/", "/api/ws")
_RESTORE_STATES = {"preparing", "restoring", "rolling_back", "recovery_required"}
_CACHE_TTL = 3.0
_cache = (0.0, False)
logger = logging.getLogger(__name__)


_writer_lease_context = ContextVar("aman_current_writer_lease_id", default=None)
_writer_state_context = ContextVar("aman_current_writer_state", default=None)
_UNCERTAINTY_REASONS = {"asset_create", "asset_put", "asset_patch", "batch_asset", "checklist_backfill", "export_publish"}


def current_writer_lease_id():
    return _writer_lease_context.get()


async def mark_current_writer_uncertain(reason):
    """Keep the existing physical lease until an operator proves write outcome.

    The mutable context value is intentional: ASGI inner tasks inherit the
    same admission object, so their mark is visible to outer finally cleanup.
    """
    if reason not in _UNCERTAINTY_REASONS:
        raise ValueError("Alasan ketidakpastian penulis tidak dikenal")
    state = _writer_state_context.get()
    if state is None:
        logger.error("Unknown write outcome has no admitted writer context")
        return False
    state["uncertain"] = True  # Set BEFORE any fallible database operation.
    state["reason"] = reason
    try:
        result = await state["database"].restore_write_leases.update_one(
            {"_id": state["lease_id"]}, {"$set": {"status": "uncertain_write",
                "uncertainty_reason": reason, "updated_at": datetime.now(timezone.utc)}})
        if not result.matched_count:
            logger.error("Unknown write outcome lost its persistent writer admission")
        return bool(result.matched_count)
    except Exception:
        logger.warning("Writer uncertainty metadata unavailable; physical lease remains held")
        return False


def jalur_bebas(path):
    return any((path or "").startswith(p) for p in JALUR_BEBAS)


def pemeliharaan_dari_job(job, sekarang, batas_menit=30):
    """Legacy pre-control jobs, only; current restore uses durable control."""
    if not job or job.get("type") != "restore" or job.get("status") not in ("queued", "running"):
        return False
    try:
        updated = datetime.fromisoformat(str(job.get("updated_at") or ""))
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        return (sekarang - updated).total_seconds() < batas_menit * 60
    except ValueError:
        return False


def pemeliharaan_dari_kontrol(control):
    return bool(control and (control.get("state") in _RESTORE_STATES
                            or (control.get("destructive_started") is True
                                and control.get("state") not in {"completed", "rolled_back", "aborted", "deploying"})))


async def pemeliharaan_aktif_uncached(untuk_penulisan=False, database=None):
    if database is None:
        from db import db
    else:
        db = database
    control = await db.restore_control.find_one({"_id": "GLOBAL"})
    if pemeliharaan_dari_kontrol(control) or (untuk_penulisan and control and control.get("state") == "deploying"):
        return True
    job = await db.backup_jobs.find_one({"active_lock": "GLOBAL"},
                                        {"type": 1, "status": 1, "updated_at": 1})
    return pemeliharaan_dari_job(job, datetime.now(timezone.utc))


async def penulisan_ditahan(database=None):
    return await pemeliharaan_aktif_uncached(untuk_penulisan=True, database=database)


async def pemeliharaan_aktif():
    global _cache
    stamp, active = _cache
    now = time.monotonic()
    if now - stamp < _CACHE_TTL:
        return active
    try:
        active = await pemeliharaan_aktif_uncached()
    except Exception:
        # Retain a known active recovery gate across Mongo outages. Otherwise
        # unavailable Mongo is a storage failure, not evidence of restore.
        active = _cache[1]
    _cache = (now, active)
    return active


async def _lease_heartbeat(lease_id, database=None):
    if database is None:
        from db import db
    else:
        db = database
    while True:
        await asyncio.sleep(10)
        try:
            result = await db.restore_write_leases.update_one(
                {"_id": lease_id}, {"$set": {"updated_at": datetime.now(timezone.utc)}})
            if not result.matched_count:
                logger.error("Writer lease disappeared while its worker is live")
        except Exception:
            # No TTL: an outage leaves the persisted lease blocking restore.
            # Keep retrying heartbeat for operator observability.
            logger.warning("Writer lease heartbeat unavailable; persisted admission remains held")


@contextlib.asynccontextmanager
async def writer_admission(database=None):
    """Lease a detached writer for its ENTIRE claim/render/upload/publish life."""
    if database is None:
        from db import db
    else:
        db = database
    lease_id, heartbeat = str(uuid.uuid4()), None
    await db.restore_write_leases.insert_one({"_id": lease_id,
        "kind": "background", "status": "active", "updated_at": datetime.now(timezone.utc)})
    context_token = _writer_lease_context.set(lease_id)
    state = {"lease_id": lease_id, "database": db, "uncertain": False}
    state_token = _writer_state_context.set(state)
    try:
        if await penulisan_ditahan(database=db):
            raise HTTPException(503, "Penulis latar ditahan selama restore/deploy")
        heartbeat = asyncio.create_task(_lease_heartbeat(lease_id, database=db))
        yield lease_id
    finally:
        _writer_lease_context.reset(context_token)
        _writer_state_context.reset(state_token)
        if heartbeat:
            heartbeat.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await heartbeat
        if not state["uncertain"]:
            with contextlib.suppress(Exception):
                await db.restore_write_leases.delete_one({"_id": lease_id})


class PemeliharaanMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or scope.get("method") == "OPTIONS" or jalur_bebas(scope.get("path", "")):
            await self.app(scope, receive, send)
            return
        # Batch status GET reconciles durable receipts/audit and is a writer.
        is_writer = (scope.get("method") in {"POST", "PUT", "PATCH", "DELETE"}
                     or (scope.get("method") == "GET"
                         and scope.get("path", "").startswith("/api/assets/batch-v2/")))
        lease_id, heartbeat, context_token, state_token, state = None, None, None, None, None
        try:
            active = await pemeliharaan_aktif()
            if is_writer and not active:
                from db import db
                lease_id = str(uuid.uuid4())
                await db.restore_write_leases.insert_one({"_id": lease_id,
                    "kind": "http", "status": "active", "updated_at": datetime.now(timezone.utc)})
                context_token = _writer_lease_context.set(lease_id)
                state = {"lease_id": lease_id, "database": db, "uncertain": False}
                state_token = _writer_state_context.set(state)
                # Important: uncached second check AFTER admission registration.
                # Either coordinator sees this lease, or this check sees gate.
                active = await pemeliharaan_aktif_uncached(untuk_penulisan=True)
            if active:
                resp = JSONResponse(status_code=503,
                    content={"detail": "Sistem sedang dalam pemeliharaan (pemulihan data). Operator memverifikasi keamanan data sebelum layanan dibuka.",
                             "pemeliharaan": True}, headers={"Retry-After": "60"})
                await resp(scope, receive, send)
            else:
                if lease_id:
                    heartbeat = asyncio.create_task(_lease_heartbeat(lease_id))
                await self.app(scope, receive, send)
        finally:
            if context_token is not None:
                _writer_lease_context.reset(context_token)
            if state_token is not None:
                _writer_state_context.reset(state_token)
            if heartbeat:
                heartbeat.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await heartbeat
            if lease_id and not state["uncertain"]:
                from db import db
                with contextlib.suppress(Exception):
                    await db.restore_write_leases.delete_one({"_id": lease_id})
