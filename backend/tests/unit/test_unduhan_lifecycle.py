import asyncio
from datetime import timedelta

import pytest
from bson import ObjectId
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import jobs
import routes.jobs as job_routes
import routes.unduhan as ru


@pytest.fixture
def collection(monkeypatch):
    db = AsyncMongoMockClient()["unduhan_unit"]
    col = db.unduhan
    monkeypatch.setattr(ru, "db", db)
    monkeypatch.setattr(ru, "_COL", col)
    monkeypatch.setattr(jobs, "_JOBS", db.background_jobs)
    return col


@pytest.mark.asyncio
async def test_denyut_fail_once_recovers(collection, monkeypatch):
    await collection.insert_one({"unduhan_id": "a", "status": "queued", "updated_at": ru._now()})
    original, calls = ru._update, []

    async def transient(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("transient DB failure")
        return await original(*args, **kwargs)

    monkeypatch.setattr(ru, "_update", transient)
    monkeypatch.setattr(ru, "HEARTBEAT_DETIK", 0.005)
    task = asyncio.create_task(ru._denyut("a"))
    await asyncio.sleep(0.03)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert len(calls) >= 3


@pytest.mark.asyncio
async def test_heartbeat_covers_semaphore_queue_and_cleans_up(collection, monkeypatch):
    await collection.insert_one({"unduhan_id": "a", "status": "queued",
                                 "active_lock": True, "updated_at": ru._now() - timedelta(hours=1)})
    monkeypatch.setattr(ru, "_SEM", asyncio.Semaphore(0))
    monkeypatch.setattr(ru, "HEARTBEAT_DETIK", 0.005)
    task = asyncio.create_task(ru._jalankan_unduhan("a", "/export", {}))
    await asyncio.sleep(0.025)
    doc = await collection.find_one({"unduhan_id": "a"})
    assert doc["updated_at"] > ru._naive_utc(ru._now() - timedelta(seconds=1))
    assert doc["status"] == "queued"
    assert await ru.db.restore_write_leases.count_documents({"kind": "background"}) == 1
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    doc = await collection.find_one({"unduhan_id": "a"})
    assert doc["status"] == "error" and "active_lock" not in doc
    assert await ru.db.restore_write_leases.count_documents({}) == 0
    before = doc["updated_at"]
    await asyncio.sleep(0.02)
    assert (await collection.find_one({"unduhan_id": "a"}))["updated_at"] == before


@pytest.mark.asyncio
async def test_terminal_state_cannot_be_overwritten_or_relocked(collection):
    await collection.insert_one({"unduhan_id": "a", "status": "running", "active_lock": True})
    assert await ru._update("a", status="error")
    assert not await ru._update("a", status="done", artifact_id="late")
    doc = await collection.find_one({"unduhan_id": "a"})
    assert doc["status"] == "error" and "artifact_id" not in doc and "active_lock" not in doc
    await jobs._JOBS.insert_one({"job_id": "j", "status": "error"})
    assert not await jobs.update_job("j", status="done")
    assert (await jobs._JOBS.find_one({"job_id": "j"}))["status"] == "error"


@pytest.mark.asyncio
async def test_admission_fails_closed_when_claim_index_unavailable(collection, monkeypatch):
    async def fail_index(*args, **kwargs):
        raise RuntimeError("cannot establish unique invariant")
    monkeypatch.setattr(collection, "create_index", fail_index)
    handler = ru.mulai_unduhan
    while hasattr(handler, "__wrapped__"):
        handler = handler.__wrapped__
    with pytest.raises(HTTPException) as unavailable:
        await handler(ru.MulaiUnduhanIn(path="/export", nama_file="x.bin"),
                      type("Request", (), {"headers": {}})(), user={"username": "a"})
    assert unavailable.value.status_code == 503
    assert await collection.count_documents({}) == 0


@pytest.mark.asyncio
async def test_deploy_gate_rejects_admission_without_creating_claim(collection):
    await ru.db.restore_control.insert_one({"_id": "GLOBAL", "state": "deploying", "active": True})
    handler = ru.mulai_unduhan
    while hasattr(handler, "__wrapped__"):
        handler = handler.__wrapped__
    with pytest.raises(HTTPException) as unavailable:
        await handler(ru.MulaiUnduhanIn(path="/export", nama_file="x.bin"),
                      type("Request", (), {"headers": {}})(), user={"username": "a"})
    assert unavailable.value.status_code == 503
    assert await collection.count_documents({}) == 0


@pytest.mark.asyncio
async def test_migration_audit_is_read_only_and_detects_legacy_claims(collection):
    from audit_unduhan_claims import audit
    await collection.insert_one({"unduhan_id": "a", "status": "running", "dibuat_oleh": "a"})
    original = await collection.find_one({"unduhan_id": "a"})
    report = await audit(collection)
    assert report["legacy_active"] == 1 and not report["safe_to_deploy_without_active_legacy"]
    assert await collection.find_one({"unduhan_id": "a"}) == original


@pytest.mark.asyncio
async def test_unknown_publication_reply_preserves_referenced_blob(collection, monkeypatch):
    await collection.insert_one({"unduhan_id": "a", "status": "running", "nama_file": "a.pdf"})
    stored, deleted = set(), []
    class Bucket:
        def open_upload_stream_with_id(self, file_id, **kwargs):
            class Stream:
                async def write(self, chunk):
                    pass
                async def close(self):
                    stored.add(str(file_id))
                async def abort(self):
                    pass
            return Stream()
        async def delete(self, file_id):
            deleted.append(str(file_id))
            stored.discard(str(file_id))
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200})
        await send({"type": "http.response.body", "body": b"complete"})
    original = ru._update
    async def lose_reply(uid, **fields):
        result = await original(uid, **fields)
        if fields.get("status") == "done":
            raise RuntimeError("lost reply after committed write")
        return result
    monkeypatch.setattr(ru, "fs_bucket", Bucket())
    monkeypatch.setattr(ru, "_app_internal", lambda: app)
    monkeypatch.setattr(ru, "_update", lose_reply)
    with pytest.raises(RuntimeError, match="lost reply"):
        await ru._ambil_dan_simpan("a", "/fixture", {})
    doc = await collection.find_one({"unduhan_id": "a"})
    assert doc["status"] == "done" and doc["artifact_id"] in stored and deleted == []


@pytest.mark.asyncio
async def test_delete_running_rejected_without_releasing_claim(collection):
    await collection.insert_one({"unduhan_id": "a", "status": "running",
                                 "active_lock": True, "dibuat_oleh": "a"})
    with pytest.raises(HTTPException) as error:
        await ru.hapus_unduhan("a", user={"username": "a"})
    assert error.value.status_code == 409
    assert (await collection.find_one({"unduhan_id": "a"}))["active_lock"] is True


@pytest.mark.asyncio
async def test_atomic_unique_admission_and_independent_owners(collection, monkeypatch):
    await collection.create_index("dibuat_oleh", name="unduhan_satu_aktif_per_owner", unique=True,
                                  partialFilterExpression={"active_lock": True})
    # Synchronize both legacy count guards, forcing the read/read/write race
    # that used to admit two jobs. Only the unique index arbitrates inserts.
    count_calls, release = [], asyncio.Event()
    original = collection.count_documents

    async def racing_count(query):
        count = await original(query)
        if query["dibuat_oleh"] == "a":
            count_calls.append(1)
            if len(count_calls) == 2:
                release.set()
            await release.wait()
        return count

    monkeypatch.setattr(collection, "count_documents", racing_count)

    async def no_worker(*args):
        pass
    monkeypatch.setattr(ru, "_jalankan_unduhan", no_worker)
    request = type("Request", (), {"headers": {}})()
    start = ru.mulai_unduhan
    while hasattr(start, "__wrapped__"):
        start = start.__wrapped__
    payload = ru.MulaiUnduhanIn(path="/export", nama_file="export.bin")
    result = await asyncio.gather(*[
        start(payload, request, user={"username": "a"}) for _ in range(2)],
        return_exceptions=True)
    assert sum(isinstance(r, dict) for r in result) == 1
    assert sum(isinstance(r, HTTPException) and r.status_code == 409 for r in result) == 1
    assert await start(payload, request, user={"username": "b"})


@pytest.mark.asyncio
async def test_rate_limit_retries_without_creating_error_artifact(collection, monkeypatch):
    await collection.insert_one({"unduhan_id": "a", "status": "running", "nama_file": "a.pdf"})
    attempts, writes = [], []

    async def app(scope, receive, send):
        attempts.append(scope["headers"])
        status = 429 if len(attempts) < 3 else 200
        await send({"type": "http.response.start", "status": status,
                    "headers": [(b"retry-after", b"0")]})
        await send({"type": "http.response.body", "body": b"busy" if status == 429 else b"result"})

    class Sink:
        async def write(self, chunk):
            writes.append(chunk)
        async def close(self):
            pass
        async def abort(self):
            raise AssertionError("successful upload should not abort")
    class Bucket:
        def open_upload_stream_with_id(self, *args, **kwargs):
            return Sink()

    monkeypatch.setattr(ru, "_app_internal", lambda: app)
    monkeypatch.setattr(ru, "fs_bucket", Bucket())
    await ru._ambil_dan_simpan("a", "/export", {"authorization": "Bearer transient"})
    assert len(attempts) == 3 and writes == [b"result"]
    assert (await collection.find_one({"unduhan_id": "a"}))["status"] == "done"


@pytest.mark.asyncio
async def test_job_download_reads_chunks_lazily_and_preserves_access(monkeypatch):
    reads = []
    stream = type("Stream", (), {})()
    chunks = iter([b"first", b"last", b""])

    async def readchunk():
        reads.append(1)
        return next(chunks)
    stream.readchunk = readchunk

    async def get_job(job_id):
        return {"status": "done", "artifact_id": str(ObjectId()),
                "dibuat_oleh": "a", "kode_satker": "A"}
    async def artifact(job_id):
        return stream, "download.pdf", "application/pdf"

    monkeypatch.setattr(job_routes, "get_job", get_job)
    monkeypatch.setattr(job_routes, "ambil_artifact", artifact)
    with pytest.raises(HTTPException) as denied:
        await job_routes.download_job("j", user={"username": "b", "role": "admin", "kode_satker": "B"})
    assert denied.value.status_code == 403 and reads == []
    response = await job_routes.download_job("j", user={"username": "a"})
    assert reads == []
    assert await anext(response.body_iterator) == b"first" and len(reads) == 1
    assert await anext(response.body_iterator) == b"last" and len(reads) == 2
