"""Feature-gated durable read-only XLSX worker for the existing single VPS.

Run from backend/: python -m export_worker. JobSpec stores validated parameters
and principal identity only, never Bearer tokens or executable Mongo queries.
"""
import argparse
import asyncio
import contextlib
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated, Literal

from bson import ObjectId
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pymongo import ReturnDocument

from export_budget import POOL_ID, QUEUE_LIMIT, process_identity, process_dead, run_budgeted

logger = logging.getLogger(__name__)
PROTOCOL = "export_v1"
LEASE_SECONDS = 60
MAX_ATTEMPTS = 3
MAX_BYTES = 200 * 1024 * 1024
MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
FilterList = Annotated[list[Annotated[str, Field(max_length=200)]], Field(max_length=100)]


def enabled():
    return os.environ.get("AMAN_EXPORT_DURABLE_XLSX_ENABLED", "").lower() in {"1", "true", "yes"}


def now():
    return datetime.now(timezone.utc)


class ExportFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    search: str = Field(default="", max_length=512)
    category: FilterList = Field(default_factory=list)
    condition: FilterList = Field(default_factory=list)
    status: FilterList = Field(default_factory=list)
    location: FilterList = Field(default_factory=list)
    eselon1_filter: FilterList = Field(default_factory=list)
    eselon2_filter: FilterList = Field(default_factory=list)
    eselon3_filter: FilterList = Field(default_factory=list)
    eselon4_filter: FilterList = Field(default_factory=list)
    eselon5_filter: FilterList = Field(default_factory=list)
    stiker_status: FilterList = Field(default_factory=list)
    inventory_status: FilterList = Field(default_factory=list)
    price_min: Decimal | None = None
    price_max: Decimal | None = None
    nomor_spm: str = Field(default="", max_length=200)
    perolehan_dari: str = Field(default="", max_length=200)
    user_filter: str = Field(default="", max_length=200)
    pengguna_nip: str = Field(default="", max_length=200)
    beli_dari: str = Field(default="", max_length=10, pattern=r"^(\d{4}-\d{2}-\d{2})?$")
    beli_sampai: str = Field(default="", max_length=10, pattern=r"^(\d{4}-\d{2}-\d{2})?$")

    @field_validator("price_min", "price_max")
    @classmethod
    def finite_price(cls, value):
        if value is None:
            return None
        # JobSpec must preserve the same exact Decimal128 price domain as
        # list/report/legacy export readers, including values above 2**53.
        from asset_sorting import batas_harga
        try:
            return batas_harga(value).to_decimal()
        except HTTPException as exc:
            raise ValueError(exc.detail) from None


class ExportParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    activity_id: str = Field(default="", max_length=128)
    base_url: str = Field(default="", max_length=512)
    filters: ExportFilters = Field(default_factory=ExportFilters)

    @field_validator("base_url")
    @classmethod
    def valid_url(cls, value):
        if value:
            from urllib.parse import urlsplit
            url = urlsplit(value)
            if url.scheme not in {"https", "http"} or not url.netloc or url.username or url.password or url.fragment:
                raise ValueError("Alamat dasar ekspor tidak valid")
        return value


class JobSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1] = 1
    renderer: Literal["assets_xlsx"] = "assets_xlsx"
    resource_class: Literal["cpu"] = "cpu"
    retry_policy: Literal["read_only_max3"] = "read_only_max3"
    principal_id: str = Field(min_length=1, max_length=128)
    principal_epoch: int = Field(ge=0)
    principal_satker: str = Field(max_length=128)
    effective_satker: str = Field(max_length=128)
    dataset_generation: str = Field(min_length=1, max_length=128)
    parameters: ExportParameters


def parameters_from_query(query, activity_id="", base_url=""):
    values = {}
    for name, field in ExportFilters.model_fields.items():
        if name not in query:
            continue
        values[name] = query.getlist(name) if isinstance(field.default_factory, type) and field.default_factory is list else query.get(name)
    return ExportParameters(activity_id=activity_id or "", base_url=base_url, filters=ExportFilters.model_validate(values))


async def reauthorize(spec, database):
    from auth_utils import _terapkan_satker_aktif
    from dataset_epoch import get_generation
    user = await database.users.find_one({"id": spec.principal_id}, {"_id": 0, "password": 0, "password_hash": 0})
    if not user or not user.get("is_active", True):
        raise HTTPException(403, "Pemilik ekspor tidak aktif lagi")
    original_satker = str(user.get("kode_satker") or "")
    if original_satker != spec.principal_satker or int(user.get("sesi_epoch") or 0) != spec.principal_epoch:
        raise HTTPException(403, "Izin/sesi pemilik ekspor telah berubah")
    if spec.dataset_generation != await get_generation(database):
        raise HTTPException(409, "Dataset berubah sejak ekspor dijadwalkan")
    if spec.effective_satker != original_satker:
        if original_satker:
            raise HTTPException(403, "Lingkup ekspor tidak cocok dengan akun")
        user = await _terapkan_satker_aktif(user, spec.effective_satker)
    from shared_utils import pastikan_akses_kegiatan_id
    await pastikan_akses_kegiatan_id(user, spec.parameters.activity_id)
    return user


async def authorize_download(job, user, database):
    if job.get("worker_protocol") != PROTOCOL:
        return
    spec = JobSpec.model_validate(job["job_spec"])
    await reauthorize(spec, database)
    # The old owner shortcut must not expose an artifact after changing active
    # satker. Central administrators retain their existing cross-satker access.
    current_scope = str(user.get("kode_satker") or "")
    if current_scope != spec.effective_satker and not (user.get("role") in {"admin", "super_admin"} and not current_scope):
        raise HTTPException(403, "Aktifkan satker pemilik hasil ekspor sebelum mengunduh")


async def _cleanup_admission(database):
    record = await database.export_resource_budget.find_one({"_id": POOL_ID}) or {}
    for ticket in record.get("pending_jobs", []):
        job = await database.background_jobs.find_one({"job_id": ticket["job_id"]}, {"status": 1})
        if job and job.get("status") in {"done", "error", "failed", "cancelled"} or not job and process_dead(ticket):
            await database.export_resource_budget.update_one({"_id": POOL_ID}, {"$pull": {"pending_jobs": {"job_id": ticket["job_id"]}}})


async def submit(parameters, user, total, database):
    from dataset_epoch import get_generation
    spec = JobSpec(principal_id=str(user.get("id") or ""), principal_epoch=int(user.get("sesi_epoch") or 0),
        principal_satker=str(user.get("_kode_satker_asli", user.get("kode_satker")) or ""),
        effective_satker=str(user.get("kode_satker") or ""), dataset_generation=await get_generation(database), parameters=parameters)
    await reauthorize(spec, database)
    await database.export_resource_budget.update_one({"_id": POOL_ID}, {"$setOnInsert": {"queue": [], "holders": [], "pending_jobs": []}}, upsert=True)
    await _cleanup_admission(database)
    job_id = uuid.uuid4().hex
    ticket = {"job_id": job_id, "owner": spec.principal_id, "satker": spec.effective_satker, **process_identity()}
    queue = {"$ifNull": ["$pending_jobs", []]}
    owner_count = {"$size": {"$filter": {"input": queue, "as": "job", "cond": {"$eq": ["$$job.owner", spec.principal_id]}}}}
    satker_count = {"$size": {"$filter": {"input": queue, "as": "job", "cond": {"$eq": ["$$job.satker", spec.effective_satker]}}}}
    admitted = await database.export_resource_budget.find_one_and_update(
        {"_id": POOL_ID, "$expr": {"$and": [{"$lt": [{"$size": queue}, QUEUE_LIMIT]}, {"$lt": [owner_count, 1]}, {"$lt": [satker_count, 8]}]}},
        {"$push": {"pending_jobs": ticket}}, return_document=ReturnDocument.AFTER)
    if not admitted:
        record = await database.export_resource_budget.find_one({"_id": POOL_ID})
        existing = next((t["job_id"] for t in record.get("pending_jobs", []) if t["owner"] == spec.principal_id), None)
        raise HTTPException(409 if existing else 429, {"message": "Antrean ekspor masih berisi pekerjaan aktif.", "job_id": existing}, headers={"Retry-After": "5"})
    filename = f"inventory_{(parameters.activity_id or 'semua')[:8]}.xlsx"
    document = {"job_id": job_id, "jenis": "ekspor_xlsx", "worker_protocol": PROTOCOL,
        "status": "queued", "progress": 0, "done": False, "total": total, "attempt": 0,
        "dibuat_oleh": user.get("username", ""), "kode_satker": spec.effective_satker,
        "created_at": now(), "updated_at": now(), "available_at": now(), "nama_file": filename,
        "job_spec": spec.model_dump(mode="json")}
    try:
        await database.background_jobs.insert_one(document)
    except BaseException:
        # Never remove admission after an unknown acknowledgement unless the
        # following read proves no job was inserted.
        with contextlib.suppress(Exception):
            if not await database.background_jobs.find_one({"job_id": job_id}):
                await database.export_resource_budget.update_one({"_id": POOL_ID}, {"$pull": {"pending_jobs": {"job_id": job_id}}})
        raise
    return {"job_id": job_id, "total": total, "message": f"Ekspor Excel masuk antrean untuk {total} aset.", "worker_protocol": PROTOCOL}


async def _heartbeat(database, job_id, token):
    while True:
        await asyncio.sleep(10)
        matched = await database.background_jobs.update_one({"job_id": job_id, "worker_token": token, "status": "running"},
            {"$set": {"updated_at": now(), "lease_until": now() + timedelta(seconds=LEASE_SECONDS)}})
        if not matched.matched_count:
            return


async def _render(spec, user, database):
    from routes.assets import build_asset_search_query
    from routes.exports import _query_ekspor, bangun_xlsx_bytes, _token_media, MAX_FOTO_EXPORT_ASSETS
    from shared_utils import scope_query_aset
    query = await scope_query_aset(user, _query_ekspor(build_asset_search_query(**spec.parameters.filters.model_dump()), spec.parameters.activity_id))
    count = await database.assets.count_documents(query)
    if not count or count > MAX_FOTO_EXPORT_ASSETS:
        raise HTTPException(400, "Jumlah aset ekspor berubah atau melebihi batas; jadwalkan ulang dengan filter baru.")
    return await bangun_xlsx_bytes(query, spec.parameters.activity_id, spec.parameters.base_url, _token_media(user))


async def _publish(database, bucket, job, token, data):
    if not isinstance(data, bytes) or not data or len(data) > MAX_BYTES:
        raise ValueError("Ukuran hasil ekspor tidak valid/melebihi 200 MiB")
    file_id = ObjectId()
    stream = bucket.open_upload_stream_with_id(file_id, filename=job["nama_file"],
        metadata={"job_id": job["job_id"], "worker_token": token, "content_type": MIME, "size": len(data)})
    closed = False
    try:
        for offset in range(0, len(data), 65536):
            await stream.write(data[offset:offset + 65536])
        await stream.close()
        closed = True
        spec = JobSpec.model_validate(job["job_spec"])
        await reauthorize(spec, database)
        result = await database.background_jobs.update_one(
            {"job_id": job["job_id"], "worker_token": token, "attempt": job["attempt"], "status": "running"},
            {"$set": {"status": "done", "done": True, "progress": 100, "message": "Ekspor Excel selesai.",
                "artifact_id": str(file_id), "artifact_nama": job["nama_file"], "artifact_type": MIME,
                "artifact_size": len(data), "updated_at": now()}, "$unset": {"lease_until": ""}})
        if not result.matched_count:
            raise RuntimeError("Fenced export attempt cannot publish")
    except BaseException:
        if not closed:
            with contextlib.suppress(Exception):
                await stream.abort()
        with contextlib.suppress(Exception):
            current = await database.background_jobs.find_one({"job_id": job["job_id"]}, {"artifact_id": 1})
            if not current or current.get("artifact_id") != str(file_id):
                await bucket.delete(file_id)
        raise
    return str(file_id)


async def run_one(database, bucket, renderer=None):
    """One claim/build/publication. Safe to execute in several worker processes."""
    from pemeliharaan import writer_admission
    from export_budget import enabled as budget_enabled
    if not enabled() or not budget_enabled():
        return False
    await _cleanup_admission(database)
    # A dead same-host process is positive fencing evidence; a paused process
    # retains its flock and cannot be evicted merely for missing heartbeats.
    async for abandoned in database.background_jobs.find({"worker_protocol": PROTOCOL, "status": "running"}):
        if abandoned.get("worker_identity") and process_dead(abandoned["worker_identity"]):
            await database.background_jobs.update_one({"job_id": abandoned["job_id"], "worker_token": abandoned["worker_token"], "status": "running"},
                {"$set": {"lease_until": now() - timedelta(seconds=1),
                    **({"status": "error", "done": True, "error_message": "Batas percobaan ekspor tercapai setelah worker berhenti"}
                       if abandoned.get("attempt", 0) >= MAX_ATTEMPTS else {})}})
            if abandoned.get("writer_lease_id"):
                # Exact lease belongs to a positively fenced dead process;
                # never clear unrelated admissions on heartbeat age alone.
                await database.restore_write_leases.delete_one({"_id": abandoned["writer_lease_id"]})
    candidate = await database.background_jobs.find_one(
        {"worker_protocol": PROTOCOL, "attempt": {"$lt": MAX_ATTEMPTS}, "$or": [
            {"status": "queued", "available_at": {"$lte": now()}},
            {"status": "running", "lease_until": {"$lt": now()}},
        ]}, sort=[("created_at", 1)])
    if not candidate:
        return False
    spec = JobSpec.model_validate(candidate["job_spec"])
    async def build():
        async with writer_admission(database=database) as writer_lease_id:
            token = uuid.uuid4().hex
            job = await database.background_jobs.find_one_and_update(
                {"job_id": candidate["job_id"], "attempt": candidate["attempt"], "$or": [{"status": "queued"}, {"status": "running", "lease_until": {"$lt": now()}}]},
                {"$set": {"status": "running", "worker_token": token, "worker_identity": process_identity(),
                    "writer_lease_id": writer_lease_id,
                    "updated_at": now(), "lease_until": now() + timedelta(seconds=LEASE_SECONDS), "progress": 10}, "$inc": {"attempt": 1}},
                return_document=ReturnDocument.AFTER)
            if not job:
                return False
            from log_setup import set_job_id
            set_job_id(job["job_id"])
            logger.info("Durable export claimed job=%s attempt=%s", job["job_id"], job["attempt"])
            heartbeat = asyncio.create_task(_heartbeat(database, job["job_id"], token))
            try:
                user = await reauthorize(spec, database)
                data = await (renderer or _render)(spec, user, database)
                await _publish(database, bucket, job, token, data)
                logger.info("Durable export published job=%s bytes=%s", job["job_id"], len(data))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                permanent = isinstance(exc, (HTTPException, ValueError)) or job["attempt"] >= MAX_ATTEMPTS
                await database.background_jobs.update_one({"job_id": job["job_id"], "worker_token": token, "status": "running"},
                    {"$set": {"status": "error" if permanent else "queued", "done": permanent,
                        "error_message": "Ekspor gagal: " + type(exc).__name__, "updated_at": now(),
                        "available_at": now() + timedelta(seconds=5 * job["attempt"])}, "$unset": {"lease_until": ""}})
                logger.warning("Durable export attempt failed job=%s type=%s", job["job_id"], type(exc).__name__)
            finally:
                heartbeat.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await heartbeat
                await _cleanup_admission(database)
            return True
    try:
        return await run_budgeted(build, spec.principal_id, spec.effective_satker, database=database, wait_seconds=2, force=True)
    except HTTPException as exc:
        if exc.status_code in {429, 503}:
            return False
        raise


async def main(once=False):
    from db import db, fs_bucket, client
    from log_setup import configure_logging
    configure_logging()
    from export_budget import enabled as budget_enabled
    if not enabled() or not budget_enabled():
        raise SystemExit("Enable AMAN_EXPORT_DURABLE_XLSX_ENABLED and AMAN_EXPORT_GLOBAL_BUDGET_ENABLED after staging validation")
    stop = asyncio.Event()
    import signal
    for signum in (signal.SIGTERM, signal.SIGINT):
        asyncio.get_running_loop().add_signal_handler(signum, stop.set)
    try:
        while not stop.is_set():
            worked = await run_one(db, fs_bucket)
            if once:
                return
            if not worked:
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(stop.wait(), 2)
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.once))
