"""Actual Mongo partial index/admission and GridFS streaming contract."""
import asyncio
import multiprocessing
import os

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]


def _cross_process_submit(uri, database, owner, barrier, results):
    """Child uses the parent's isolated contract DB, never an application DB."""
    from pathlib import Path
    import sys
    from urllib.parse import urlparse
    assert urlparse(uri).hostname in {"localhost", "127.0.0.1", "::1"}
    assert database.startswith("aman_ci_")
    os.environ.update(MONGO_URL=uri, DB_NAME=database)
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from motor.motor_asyncio import AsyncIOMotorClient
    from fastapi import HTTPException
    import routes.unduhan as route

    async def submit():
        client = AsyncIOMotorClient(uri)
        route.db = client[database]
        route._COL = route.db.unduhan
        original = route._COL.count_documents
        async def synchronized_count(query):
            count = await original(query)
            await asyncio.to_thread(barrier.wait, 15)
            return count
        route._COL.count_documents = synchronized_count
        async def no_render(*args):
            pass
        route._jalankan_unduhan = no_render
        handler = route.mulai_unduhan
        while hasattr(handler, "__wrapped__"):
            handler = handler.__wrapped__
        try:
            await handler(route.MulaiUnduhanIn(path="/export/csv", nama_file="process.csv"),
                          type("Request", (), {"headers": {}})(),
                          user={"username": owner, "kode_satker": "fixture"})
            results.put(200)
        except HTTPException as error:
            results.put(error.status_code)
        finally:
            client.close()
    asyncio.run(submit())


async def test_two_process_admission_has_one_winner(contract):
    ctx = multiprocessing.get_context("spawn")
    barrier, results = ctx.Barrier(2), ctx.Queue()
    uri = os.environ["AMAN_CONTRACT_MONGO_URL"]
    processes = [ctx.Process(target=_cross_process_submit,
                             args=(uri, contract.database, "process-owner", barrier, results))
                 for _ in range(2)]
    try:
        for process in processes:
            process.start()
        for process in processes:
            await asyncio.to_thread(process.join, 25)
            assert not process.is_alive() and process.exitcode == 0
        statuses = [await asyncio.to_thread(results.get, True, 2) for _ in range(2)]
        assert sorted(statuses) == [200, 409]
        assert await contract.db.unduhan.count_documents({"dibuat_oleh": "process-owner", "active_lock": True}) == 1
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                await asyncio.to_thread(process.join, 5)
        await contract.db.unduhan.delete_many({"dibuat_oleh": "process-owner"})


async def test_atomic_admission_and_running_delete_with_real_mongo(contract, monkeypatch):
    import routes.unduhan as route
    indexes = await contract.db.unduhan.index_information()
    assert indexes["unduhan_satu_aktif_per_owner"]["unique"] is True
    assert indexes["unduhan_satu_aktif_per_owner"]["partialFilterExpression"] == {"active_lock": True}
    original = route._COL.count_documents
    read_count, release, hold_worker = [], asyncio.Event(), asyncio.Event()

    async def racing_count(query):
        count = await original(query)
        if query.get("dibuat_oleh") == "contract-a":
            read_count.append(1)
            if len(read_count) == 2:
                release.set()
            await asyncio.wait_for(release.wait(), 5)
        return count

    async def worker(*args):
        await hold_worker.wait()

    monkeypatch.setattr(route._COL, "count_documents", racing_count)
    monkeypatch.setattr(route, "_jalankan_unduhan", worker)
    old_tasks = set(route._TASKS)
    try:
        responses = await asyncio.gather(*[
            contract.http.post("/api/unduhan/mulai", json={"path": "/export/csv", "nama_file": "fixture.csv"},
                               headers=contract.headers["a"]) for _ in range(2)])
        assert sorted(r.status_code for r in responses) == [200, 409]
        accepted = next(r.json()["unduhan_id"] for r in responses if r.status_code == 200)
        other = await contract.http.post("/api/unduhan/mulai", json={"path": "/export/csv", "nama_file": "other.csv"},
                                         headers=contract.headers["b"])
        assert other.status_code == 200, other.text
        await contract.db.unduhan.update_one({"unduhan_id": accepted}, {"$set": {"status": "running"}})
        denied = await contract.http.delete("/api/unduhan/" + accepted, headers=contract.headers["a"])
        assert denied.status_code == 409
        assert (await contract.db.unduhan.find_one({"unduhan_id": accepted}))["active_lock"] is True
        assert await route._update(accepted, status="error")
        assert not await route._update(accepted, status="done", artifact_id="late")
        doc = await contract.db.unduhan.find_one({"unduhan_id": accepted})
        assert "active_lock" not in doc and "artifact_id" not in doc
    finally:
        for task in route._TASKS - old_tasks:
            task.cancel()
        await asyncio.gather(*(route._TASKS - old_tasks), return_exceptions=True)
        await contract.db.unduhan.delete_many({"dibuat_oleh": {"$in": ["contract-a", "contract-b"]}})


async def test_actual_gridfs_stream_and_abort_never_publish_partial(contract, monkeypatch):
    import routes.unduhan as route
    from bson import ObjectId
    uid = "contract-stream"
    initial_chunks = await contract.db["fs.chunks"].count_documents({})
    data = b"fixture" * 10000
    producer_finished = False

    async def app(scope, receive, send):
        nonlocal producer_finished
        await send({"type": "http.response.start", "status": 200,
                    "headers": [(b"content-type", b"application/pdf")]})
        for _ in range(12):
            await send({"type": "http.response.body", "body": data, "more_body": True})
        producer_finished = True
        await send({"type": "http.response.body", "body": b""})

    monkeypatch.setattr(route, "_app_internal", lambda: app)
    await contract.db.unduhan.insert_one({"unduhan_id": uid, "status": "running",
                                         "nama_file": "fixture.pdf", "dibuat_oleh": "contract-a"})
    try:
        await route._ambil_dan_simpan(uid, "/fixture", {})
        job = await contract.db.unduhan.find_one({"unduhan_id": uid})
        assert producer_finished and job["status"] == "done" and job["ukuran"] == len(data) * 12
        stream = await contract.fs.open_download_stream(ObjectId(job["artifact_id"]))
        chunks = []
        while chunk := await stream.readchunk():
            chunks.append(chunk)
        assert b"".join(chunks) == data * 12
        await contract.fs.delete(ObjectId(job["artifact_id"]))
        await contract.db.unduhan.update_one({"unduhan_id": uid}, {"$set": {"status": "running"}, "$unset": {"artifact_id": ""}})

        async def broken(scope, receive, send):
            await send({"type": "http.response.start", "status": 200})
            await send({"type": "http.response.body", "body": data * 8, "more_body": True})
            raise RuntimeError("fixture failure after persisted chunks")
        monkeypatch.setattr(route, "_app_internal", lambda: broken)
        with pytest.raises(RuntimeError, match="fixture failure"):
            await route._ambil_dan_simpan(uid, "/fixture", {})
        job = await contract.db.unduhan.find_one({"unduhan_id": uid})
        assert job["status"] == "running" and "artifact_id" not in job
        assert await contract.db["fs.files"].count_documents({"metadata.unduhan_id": uid}) == 0
        # All chunks here belong to this isolated contract DB and the successful
        # blob was deleted first; abort must remove the partial GridFS chunks.
        assert await contract.db["fs.chunks"].count_documents({}) == initial_chunks
    finally:
        await contract.db.unduhan.delete_one({"unduhan_id": uid})
