"""Single-VPS global render budget, held until all renderer threads finish.

Mongo bounds/fairly orders admission. POSIX flock is the physical authority:
SIGSTOP retains a slot, SIGKILL closes it. A heartbeat expiry never permits two
live renderers to use one slot. All worker processes MUST share lock directory.
"""
import asyncio
import contextlib
import contextvars
import fcntl
import hashlib
import json
import os
import socket
import tempfile
import time
import uuid
from pathlib import Path

from fastapi import HTTPException
from pymongo import ReturnDocument

_ACTIVE = contextvars.ContextVar("aman_render_budget", default=None)
POOL_ID = "render_v1"
QUEUE_LIMIT = 32
OWNER_ADMISSION_LIMIT = 2


def enabled():
    return os.environ.get("AMAN_EXPORT_GLOBAL_BUDGET_ENABLED", "").lower() in {"1", "true", "yes"}


def capacity_configuration():
    """Pure capacity parser shared by admission and runtime health attestation."""
    try:
        capacity=int(os.environ.get("AMAN_EXPORT_GLOBAL_SLOTS","2"))
        satker_slots=int(os.environ.get("AMAN_EXPORT_SATKER_SLOTS",str(capacity)))
    except (ValueError,TypeError):
        raise ValueError("Invalid export capacity configuration") from None
    if not 1<=capacity<=8 or not 1<=satker_slots<=capacity:
        raise ValueError("Invalid export capacity configuration")
    return {"schema":1,"capacity":capacity,"satker_slots":satker_slots}


def runtime_capabilities():
    """No DB/FS I/O or sensitive values; this attests process configuration."""
    value={"enabled":enabled(),"ok":False,"slots":0,"satker_slots":0,"error_category":None}
    raw=os.environ.get("AMAN_EXPORT_GLOBAL_BUDGET_ENABLED","").lower()
    if raw not in {"","0","false","no","1","true","yes"}:
        value["error_category"]="invalid_enable_flag"
        return value
    try:
        config=capacity_configuration()
    except ValueError:
        value["error_category"]="invalid_capacity_configuration"
        return value
    return {**value,"ok":True,"slots":config["capacity"],"satker_slots":config["satker_slots"]}


def process_identity():
    try:
        boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        start = Path(f"/proc/{os.getpid()}/stat").read_text().rsplit(")", 1)[1].split()[19]
    except (OSError, IndexError):
        raise RuntimeError("Global export budget requires Linux /proc process fencing")
    return {"host": socket.gethostname(), "boot": boot, "pid": os.getpid(), "process_start": start}


def process_dead(identity):
    """Positive same-host proof only; SIGSTOP and permission errors stay alive."""
    if identity.get("host") != socket.gethostname():
        return False
    try:
        boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        if identity.get("boot") != boot:
            return True
        stat = Path(f"/proc/{int(identity['pid'])}/stat").read_text().rsplit(")", 1)[1].split()
        return stat[0] == "Z" or stat[19] != identity.get("process_start")
    except FileNotFoundError:
        return True
    except (OSError, ValueError, KeyError, IndexError):
        return False


def _lock_directory(database):
    suffix = hashlib.sha256(str(database.name).encode()).hexdigest()[:12]
    directory = Path(os.environ.get("AMAN_EXPORT_LOCK_DIR") or (Path(tempfile.gettempdir()) / f"aman-render-{os.getuid()}-{suffix}"))
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    stat = directory.lstat()
    if directory.is_symlink() or stat.st_uid != os.getuid() or stat.st_mode & 0o022:
        raise RuntimeError("Export lock directory must be owned by this Unix user and not writable by others")
    return directory


def _open_lock(path):
    return os.open(path, os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)


def _configuration(directory):
    config = capacity_configuration()
    fd = _open_lock(directory / "configuration.lock")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        target = directory / "configuration.json"
        if target.exists():
            if json.loads(target.read_text()) != config:
                raise RuntimeError("Export capacity changed while shared lock configuration exists; drain all workers before operator reconfiguration")
        else:
            with target.open("x") as output:
                json.dump(config, output)
                output.flush()
                os.fsync(output.fileno())
    finally:
        os.close(fd)
    return config


def _physical_claim(directory, config, owner, satker):
    acquired = []
    def one(name):
        fd = _open_lock(directory / name)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            return False
        acquired.append(fd)
        return True
    def pool(prefix, count):
        return any(one(f"{prefix}-{index}.lock") for index in range(count))
    owner_key = hashlib.sha256(str(owner).encode()).hexdigest()
    scope_key = hashlib.sha256(str(satker).encode()).hexdigest()
    try:
        if not one(f"owner-{owner_key}.lock") or not pool(f"satker-{scope_key}", config["satker_slots"]) or not pool("cpu", config["capacity"]):
            for fd in acquired:
                os.close(fd)
            return None
        return acquired
    except BaseException:
        for fd in acquired:
            os.close(fd)
        raise


async def _reap_dead(database, record):
    tokens = [holder["token"] for holder in record.get("queue", []) + record.get("holders", []) if process_dead(holder)]
    if tokens:
        await database.export_resource_budget.update_one({"_id": POOL_ID}, {
            "$pull": {"queue": {"token": {"$in": tokens}}, "holders": {"token": {"$in": tokens}}}})


def _first_eligible(record, config):
    """FIFO among owners/scopes able to run; blocked owners cannot idle CPUs."""
    holders = record.get("holders", [])
    busy_owners = {item["owner"] for item in holders}
    by_scope = {}
    for item in holders:
        by_scope[item["satker"]] = by_scope.get(item["satker"], 0) + 1
    return next((ticket for ticket in record.get("queue", [])
                 if ticket["owner"] not in busy_owners
                 and by_scope.get(ticket["satker"], 0) < config["satker_slots"]), None)


@contextlib.asynccontextmanager
async def budget_slot(owner, satker, *, database=None, wait_seconds=15, force=False):
    """Bounded FIFO admission and physical slot. No HTTP header bypass exists."""
    if _ACTIVE.get() is not None or not force and not enabled():
        yield
        return
    if database is None:
        from db import db
        database = db
    directory = _lock_directory(database)
    config = _configuration(directory)
    token = uuid.uuid4().hex
    ticket = {"token": token, "owner": str(owner), "satker": str(satker), **process_identity()}
    await database.export_resource_budget.update_one({"_id": POOL_ID},
        {"$setOnInsert": {"queue": [], "holders": []}}, upsert=True)
    existing = await database.export_resource_budget.find_one({"_id": POOL_ID})
    await _reap_dead(database, existing)
    owner_count = {"$size": {"$filter": {"input": {"$concatArrays": ["$queue", "$holders"]}, "as": "t", "cond": {"$eq": ["$$t.owner", str(owner)]}}}}
    descriptors, context_token = None, None
    deadline = time.monotonic() + wait_seconds
    try:
        # Include admission in cleanup: cancellation can arrive after Mongo has
        # queued this ticket but before its reply reaches the requesting task.
        admitted = await database.export_resource_budget.find_one_and_update(
            {"_id": POOL_ID, "$expr": {"$and": [
                {"$lt": [{"$size": "$queue"}, QUEUE_LIMIT]},
                {"$lt": [owner_count, OWNER_ADMISSION_LIMIT]},
            ]}}, {"$push": {"queue": ticket}}, return_document=ReturnDocument.AFTER)
        if not admitted:
            raise HTTPException(429, "Antrean ekspor penuh; tunggu pekerjaan sebelumnya selesai.", headers={"Retry-After": "5"})
        while time.monotonic() < deadline:
            record = await database.export_resource_budget.find_one({"_id": POOL_ID})
            await _reap_dead(database, record)
            candidate = _first_eligible(record, config)
            if candidate and candidate["token"] == token:
                descriptors = _physical_claim(directory, config, owner, satker)
                if descriptors:
                    accepted = await database.export_resource_budget.update_one(
                        {"_id": POOL_ID, "queue.token": token},
                        {"$pull": {"queue": {"token": token}}, "$push": {"holders": ticket}})
                    if accepted.matched_count:
                        context_token = _ACTIVE.set(token)
                        yield
                        return
                    for fd in descriptors:
                        os.close(fd)
                    descriptors = None
            await asyncio.sleep(.1)
        raise HTTPException(429, "Semua slot ekspor sedang digunakan; coba lagi setelah pekerjaan selesai.", headers={"Retry-After": "5"})
    finally:
        if context_token is not None:
            _ACTIVE.reset(context_token)
        # flock closes even when Mongo is temporarily unavailable. Stale Mongo
        # metadata can deny admission, but cannot open an extra physical slot.
        if descriptors:
            for fd in descriptors:
                os.close(fd)
        async def release_metadata():
            await database.export_resource_budget.update_one({"_id": POOL_ID},
                {"$pull": {"queue": {"token": token}, "holders": {"token": token}}})
        cleanup = asyncio.create_task(release_metadata())
        cancelled = False
        while not cleanup.done():
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError:
                cancelled = True
        cleanup.result()
        if cancelled:
            raise asyncio.CancelledError


async def run_budgeted(factory, owner, satker, **options):
    """Keep budget when client cancellation arrives during a to_thread build."""
    if not options.get("force") and not enabled() and _ACTIVE.get() is None:
        return await factory()
    async with budget_slot(owner, satker, **options):
        task = asyncio.create_task(factory())
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            # shield keeps both coroutine and its thread await alive. Repeated
            # cancellations must not prematurely release a physical resource.
            while not task.done():
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    continue
                except Exception:
                    break
            if task.done() and not task.cancelled():
                with contextlib.suppress(Exception):
                    task.result()
            raise


def heavy_route(path, method="GET"):
    if method == "POST":
        return (path in {"/api/assets/cards/bulk", "/api/compress-pdf"}
                or path.endswith(("/batch-pdf-zip", "/kirim-ttd"))
                or path == "/api/persediaan/nota-dinas/terbitkan")
    if method != "GET":
        return False
    if path.startswith(("/api/jobs/", "/api/unduhan/", "/api/backup/")):
        return False
    return (path.startswith(("/api/export/", "/api/spasial/ekspor/")) or "/export" in path
            or path.endswith(("-pdf", "-docx", "-xlsx", "/pdf", "/docx", "/xlsx", "/card"))
            or any(segment.endswith(("-pdf", "-docx", "-xlsx")) for segment in path.split("/"))
            or path.endswith("-html")
            or path == "/api/stiker/label"
            or path.endswith("/belum-tercatat.csv")
            or path == "/api/integritas/ekspor-ringkasan"
            or path in {"/api/documents/ppt", "/api/documents/proposal", "/api/persediaan/nota-dinas"}
            or "/permohonan/" in path and path.endswith("/dokumen")
            or "/dbhi/" in path)


class ExportBudgetMiddleware:
    """One shared budget for sync endpoints and internal download-center GETs."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if not enabled() or scope.get("type") != "http" or not heavy_route(scope.get("path", ""), scope.get("method")) or _ACTIVE.get() is not None:
            await self.app(scope, receive, send)
            return
        from auth_utils import require_user_or_query_token
        from fastapi.responses import JSONResponse
        from starlette.datastructures import Headers, QueryParams
        # Match FastAPI/Starlette duplicate-header/query semantics exactly;
        # admission ownership must be the same principal as the actual route.
        headers = Headers(scope=scope)
        query = QueryParams(scope.get("query_string", b"").decode())
        response_started = False
        async def protected_send(message):
            nonlocal response_started
            if message.get("type") == "http.response.start":
                response_started = True
            await send(message)
        try:
            if scope.get("path") in {"/api/documents/ppt", "/api/documents/proposal"}:
                # Existing public product documents remain public; retain their
                # per-IP rate limit and give anonymous renderers a bounded owner.
                user = {"id": "public:" + str((scope.get("client") or ("unknown",))[0]), "kode_satker": "public"}
            else:
                user = await require_user_or_query_token(headers.get("authorization", ""),
                    query.get("token", ""), headers.get("x-satker-aktif", ""), query.get("sa", ""))
            async def render_request():
                # Read-only renderers also participate in the restore barrier:
                # their file must never combine halves of two datasets.
                from pemeliharaan import writer_admission
                async with writer_admission():
                    await self.app(scope, receive, protected_send)
            await run_budgeted(render_request,
                str(user.get("id") or user.get("username")), str(user.get("kode_satker") or ""))
        except HTTPException as exc:
            if response_started:
                raise
            response = JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)
            await response(scope, receive, send)
