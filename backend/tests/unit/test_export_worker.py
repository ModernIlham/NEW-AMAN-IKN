import asyncio
import json
from decimal import Decimal

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient
from pydantic import ValidationError
from pymongo.results import UpdateResult
from starlette.datastructures import QueryParams

import export_worker as worker
import shared_utils
import auth_utils

USER = {"id": "export-owner", "username": "export-user", "role": "admin", "kode_satker": "001", "is_active": True}


def run(coro):
    return asyncio.run(coro)


class Bucket:
    def __init__(self):
        self.files = {}
        self.deleted = []

    def open_upload_stream_with_id(self, file_id, **kwargs):
        bucket = self
        class Stream:
            buffer = bytearray()
            async def write(self, data):
                self.buffer.extend(data)
            async def close(self):
                bucket.files[file_id] = bytes(self.buffer)
            async def abort(self):
                bucket.files.pop(file_id, None)
        return Stream()

    async def delete(self, file_id):
        self.deleted.append(file_id)
        self.files.pop(file_id, None)


@pytest.fixture
def database(monkeypatch, tmp_path):
    db = AsyncMongoMockClient()["unit_export_worker"]
    monkeypatch.setattr(shared_utils, "db", db)
    monkeypatch.setattr(auth_utils, "db", db)
    monkeypatch.setenv("AMAN_EXPORT_DURABLE_XLSX_ENABLED", "1")
    monkeypatch.setenv("AMAN_EXPORT_GLOBAL_BUDGET_ENABLED", "1")
    monkeypatch.setenv("AMAN_EXPORT_GLOBAL_SLOTS", "1")
    monkeypatch.setenv("AMAN_EXPORT_SATKER_SLOTS", "1")
    monkeypatch.setenv("AMAN_EXPORT_LOCK_DIR", str(tmp_path / "locks"))
    run(db.users.insert_one(USER))
    run(db.inventory_activities.insert_one({"id": "k1", "kode_satker": "001"}))
    return db


async def submit(database):
    return await worker.submit(worker.ExportParameters(activity_id="k1"), USER, 1, database)


async def renderer(*_):
    return b"PK-synthetic-xlsx"


def test_typed_filters_preserve_lists_numbers_and_refuse_raw_query():
    params = worker.parameters_from_query(QueryParams("category=A&category=B&price_min=100.5&search=%24ne"), "k1", "https://example.test")
    assert params.filters.category == ["A", "B"] and params.filters.price_min == Decimal("100.5")
    assert params.filters.search == "$ne"  # literal search string, not an executable operator
    with pytest.raises(ValidationError):
        worker.ExportFilters.model_validate({"$or": [{"kode_satker": {"$ne": ""}}]})
    with pytest.raises(ValidationError):
        worker.ExportParameters(base_url="https://secret@example.test")


def test_submit_is_bounded_typed_and_survives_request_end(database):
    async def scenario():
        result = await submit(database)
        record = await database.background_jobs.find_one({"job_id": result["job_id"]})
        encoded = json.dumps(record["job_spec"])
        assert "Bearer" not in encoded and "Authorization" not in encoded and '"query"' not in encoded
        assert record["status"] == "queued" and record["job_spec"]["renderer"] == "assets_xlsx"
        with pytest.raises(HTTPException) as error:
            await submit(database)
        assert error.value.status_code == 409 and error.value.detail["job_id"] == result["job_id"]
        bucket = Bucket()
        assert await worker.run_one(database, bucket, renderer)
        complete = await database.background_jobs.find_one({"job_id": result["job_id"]})
        assert complete["status"] == "done" and complete["attempt"] == 1
        assert len(bucket.files) == 1
        assert not await worker.run_one(database, bucket, renderer)
        assert not (await database.export_resource_budget.find_one({"_id": worker.POOL_ID}))["pending_jobs"]
    run(scenario())


@pytest.mark.parametrize("change", [{"is_active": False}, {"kode_satker": "002"}, {"sesi_epoch": 1}])
def test_reauth_revocation_before_execution_never_builds_or_publishes(database, change):
    async def scenario():
        result = await submit(database)
        await database.users.update_one({"id": USER["id"]}, {"$set": change})
        bucket = Bucket()
        async def forbidden(*_):
            pytest.fail("revoked principal must not enter renderer")
        assert await worker.run_one(database, bucket, forbidden)
        job = await database.background_jobs.find_one({"job_id": result["job_id"]})
        assert job["status"] == "error" and not job.get("artifact_id") and not bucket.files
    run(scenario())


def test_old_attempt_cannot_publish_or_delete_new_attempt_artifact(database):
    async def scenario():
        result = await submit(database)
        job = await database.background_jobs.find_one({"job_id": result["job_id"]})
        job.update(attempt=1, worker_token="old")
        await database.background_jobs.update_one({"job_id": job["job_id"]}, {"$set": {
            "status": "running", "attempt": 2, "worker_token": "new", "artifact_id": "new-attempt-file"}})
        bucket = Bucket()
        with pytest.raises(RuntimeError, match="Fenced"):
            await worker._publish(database, bucket, job, "old", b"PK-old-output")
        current = await database.background_jobs.find_one({"job_id": job["job_id"]})
        assert current["artifact_id"] == "new-attempt-file" and current["worker_token"] == "new"
        assert not bucket.files and len(bucket.deleted) == 1
    run(scenario())


def test_generation_change_holds_job_and_download_rechecks_owner(database):
    async def scenario():
        result = await submit(database)
        bucket = Bucket()
        assert await worker.run_one(database, bucket, renderer)
        job = await database.background_jobs.find_one({"job_id": result["job_id"]})
        await worker.authorize_download(job, USER, database)
        await database.users.update_one({"id": USER["id"]}, {"$set": {"is_active": False}})
        with pytest.raises(HTTPException) as error:
            await worker.authorize_download(job, USER, database)
        assert error.value.status_code == 403
        await database.users.update_one({"id": USER["id"]}, {"$set": {"is_active": True}})
        from dataset_epoch import rotate_generation
        await rotate_generation(database, "unit-restore")
        with pytest.raises(HTTPException) as error:
            await worker.authorize_download(job, USER, database)
        assert error.value.status_code == 409
    run(scenario())


def test_authorization_failure_before_publication_cleans_new_blob_and_releases_lease(database):
    async def scenario():
        result = await submit(database)
        bucket = Bucket()
        async def revoke_during_render(*_):
            await database.users.update_one({"id": USER["id"]}, {"$set": {"is_active": False}})
            return b"PK-revoked-output"
        assert await worker.run_one(database, bucket, revoke_during_render)
        job = await database.background_jobs.find_one({"job_id": result["job_id"]})
        assert job["status"] == "error" and not job.get("artifact_id")
        assert not bucket.files and len(bucket.deleted) == 1
        assert await database.restore_write_leases.count_documents({}) == 0
    run(scenario())


def test_acknowledged_terminal_cas_miss_cleans_only_its_blob_and_releases_lease(database, monkeypatch):
    async def scenario():
        result = await submit(database)
        real_update = database.background_jobs.update_one
        async def miss_terminal(query, changes, *args, **kwargs):
            if changes.get("$set", {}).get("status") == "done":
                await real_update({"job_id": result["job_id"]}, {"$set": {
                    "worker_token": "replacement", "attempt": 2, "artifact_id": "replacement-file"},
                    "$unset": {"publication_pending": ""}})
                return UpdateResult({"n": 0, "nModified": 0, "ok": 1}, True)
            return await real_update(query, changes, *args, **kwargs)
        class Jobs:
            update_one = staticmethod(miss_terminal)
            def __getattr__(self, name):
                return getattr(database.background_jobs, name)
        class Database:
            background_jobs = Jobs()
            def __getattr__(self, name):
                return getattr(database, name)
        publish = worker._publish
        async def intercepted_publish(_database, *args):
            return await publish(Database(), *args)
        monkeypatch.setattr(worker, "_publish", intercepted_publish)
        bucket = Bucket()
        assert await worker.run_one(database, bucket, renderer)
        job = await database.background_jobs.find_one({"job_id": result["job_id"]})
        assert job["worker_token"] == "replacement" and job["artifact_id"] == "replacement-file"
        assert not bucket.files and len(bucket.deleted) == 1
        assert await database.restore_write_leases.count_documents({}) == 0
    run(scenario())


@pytest.mark.parametrize("price",["1000000000000000000.01","9007199254740992.02",
    "-9007199254740992.01","1234567890123456789012345678901234","1e6144","1e-6176","0"])
def test_price_bounds_keep_exact_shared_decimal128_domain(price):
    from asset_sorting import batas_harga
    filters=worker.ExportFilters(price_min=price,price_max=price)
    encoded=filters.model_dump(mode="json")
    assert Decimal(encoded["price_min"])==Decimal(price)
    assert Decimal(encoded["price_max"])==Decimal(price)
    assert filters.price_min==batas_harga(price).to_decimal()
    # The persisted JSON JobSpec roundtrip never goes through binary float.
    restored=worker.ExportFilters.model_validate(encoded)
    assert restored.price_min==filters.price_min and restored.price_max==filters.price_max


@pytest.mark.parametrize("price",["NaN","Infinity","-Infinity","1e6145","1.1e-6176",
    "12345678901234567890123456789012345"])
def test_invalid_or_inexact_decimal128_price_bounds_never_enter_job_spec(price):
    with pytest.raises(ValidationError):
        worker.ExportFilters(price_min=price)
