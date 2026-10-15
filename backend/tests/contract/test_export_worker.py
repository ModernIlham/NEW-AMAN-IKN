"""Real standalone-Mongo + single-VPS process fencing for OPT-22 prototype."""
import asyncio
import os
import signal
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]


@pytest.fixture
def export_flags(monkeypatch, tmp_path):
    monkeypatch.setenv("AMAN_EXPORT_DURABLE_XLSX_ENABLED", "1")
    monkeypatch.setenv("AMAN_EXPORT_GLOBAL_BUDGET_ENABLED", "1")
    monkeypatch.setenv("AMAN_EXPORT_GLOBAL_SLOTS", "1")
    monkeypatch.setenv("AMAN_EXPORT_SATKER_SLOTS", "1")
    monkeypatch.setenv("AMAN_EXPORT_LOCK_DIR", str(tmp_path / "render-locks"))


def child(script):
    return subprocess.Popen([sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[2],
        env=dict(os.environ), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


async def line(process, timeout=8):
    result = await asyncio.wait_for(asyncio.to_thread(process.stdout.readline), timeout)
    if not result:
        raise AssertionError("Child exited before checkpoint: " + (await asyncio.to_thread(process.stderr.read))[:1500])
    return result.strip()


async def stop(process):
    if process.poll() is None:
        process.kill()
    await asyncio.to_thread(process.wait, 5)
    process.stdout.close()
    process.stderr.close()


async def seed(contract):
    activity_id = "contract-worker-" + uuid.uuid4().hex
    await contract.db.inventory_activities.insert_one({"id": activity_id,
        "kode_satker": contract.users["a"]["kode_satker"], "status_pengesahan": "draft",
        "nama_kegiatan": "Worker sintetis", "nomor_surat": "SYNTHETIC"})
    aid = "contract-worker-asset-" + uuid.uuid4().hex
    await contract.db.assets.insert_one({"id": aid, "activity_id": activity_id,
        "asset_code": "3050104001", "NUP": "1", "asset_name": "Worker sintetis", "purchase_price": "100", "version": 1})
    return activity_id


async def test_sigstop_retains_hard_cap_and_sigkill_recovers_across_processes(contract, export_flags):
    import export_budget
    script = """
import asyncio
from export_budget import budget_slot
async def main():
    from db import db
    async with budget_slot(OWNER, 'synthetic', database=db, force=True, wait_seconds=10):
        print('ACQUIRED', flush=True)
        await asyncio.Event().wait()
asyncio.run(main())
"""
    first = child("OWNER='process-1'\n" + script)
    second = None
    try:
        assert await line(first) == "ACQUIRED"
        first.send_signal(signal.SIGSTOP)
        async with asyncio.timeout(3):
            while (await contract.db.export_resource_budget.find_one({"_id": export_budget.POOL_ID}))["holders"][0]["pid"] != first.pid:
                await asyncio.sleep(.01)
        second = child("OWNER='process-2'\n" + script)
        waiting = asyncio.create_task(line(second))
        await asyncio.sleep(.3)
        assert not waiting.done(), "SIGSTOP must keep its physical CPU slot"
        first.kill()
        await asyncio.to_thread(first.wait, 5)
        assert await waiting == "ACQUIRED", "SIGKILL must release flock without waiting for a heartbeat TTL"
        await stop(second)
        second = None
        # The next process positively reaps dead metadata and acquires the
        # same physical slot; no manual Mongo lock deletion is required.
        async with export_budget.budget_slot("parent", "other", database=contract.db, force=True, wait_seconds=2):
            record = await contract.db.export_resource_budget.find_one({"_id": export_budget.POOL_ID})
            assert len(record["holders"]) == 1 and record["holders"][0]["pid"] == os.getpid()
    finally:
        await stop(first)
        if second:
            await stop(second)


async def test_durable_job_restart_after_sigkill_publishes_one_valid_xlsx(contract, export_flags):
    activity_id = await seed(contract)
    response = await contract.http.post("/api/export/xlsx/async", params={"activity_id": activity_id}, headers=contract.headers["a"])
    assert response.status_code == 200, response.text
    job_id = response.json()["job_id"]
    script = """
import asyncio
from export_worker import run_one
async def paused_renderer(*_):
    print('RENDERING', flush=True)
    await asyncio.Event().wait()
async def main():
    from db import db, fs_bucket
    await run_one(db, fs_bucket, paused_renderer)
asyncio.run(main())
"""
    process = child(script)
    try:
        assert await line(process) == "RENDERING"
        process.kill()
        await asyncio.to_thread(process.wait, 5)
        # Restart worker using the actual production builder and fresh owner
        # authorization. Positive PID fencing makes the old claim reclaimable.
        from export_worker import run_one
        assert await run_one(contract.db, contract.fs)
        job = await contract.db.background_jobs.find_one({"job_id": job_id})
        assert job["status"] == "done" and job["attempt"] == 2
        assert await contract.db.restore_write_leases.count_documents({}) == 0
        assert await contract.db.fs.files.count_documents({"metadata.job_id": job_id}) == 1
        download = await contract.http.get(f"/api/jobs/{job_id}/download", headers=contract.headers["a"])
        assert download.status_code == 200, download.text[:100]
        import io
        import zipfile
        with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
            assert "xl/workbook.xml" in archive.namelist()
            assert "Worker sintetis" in archive.read("xl/sharedStrings.xml").decode()
        # Revoking the original principal also blocks a central administrator
        # from obtaining this formerly authorized dataset artifact.
        await contract.db.users.update_one({"id": contract.users["a"]["id"]}, {"$set": {"is_active": False}})
        denied = await contract.http.get(f"/api/jobs/{job_id}/download", headers=contract.headers["root"])
        assert denied.status_code == 403
    finally:
        await contract.db.users.update_one({"id": contract.users["a"]["id"]}, {"$set": {"is_active": True}})
        await stop(process)


async def test_typed_spec_and_fenced_publish_on_real_gridfs(contract, export_flags):
    activity_id = await seed(contract)
    response = await contract.http.post("/api/export/xlsx/async", params={"activity_id": activity_id}, headers=contract.headers["a"])
    assert response.status_code == 200, response.text
    job_id = response.json()["job_id"]
    job = await contract.db.background_jobs.find_one({"job_id": job_id})
    spec = job["job_spec"]
    assert spec["renderer"] == "assets_xlsx" and "query" not in spec and "Authorization" not in str(spec)
    from export_worker import _publish
    job.update(attempt=1, worker_token="stale")
    await contract.db.background_jobs.update_one({"job_id": job_id}, {"$set": {"attempt": 2, "worker_token": "fresh", "status": "running"}})
    with pytest.raises(RuntimeError, match="Fenced"):
        await _publish(contract.db, contract.fs, job, "stale", b"PK-stale-attempt")
    current = await contract.db.background_jobs.find_one({"job_id": job_id})
    assert current["worker_token"] == "fresh" and not current.get("artifact_id")
    assert await contract.db.fs.files.count_documents({"metadata.job_id": job_id}) == 0
    await contract.db.background_jobs.update_one({"job_id": job_id}, {"$set": {"status": "error", "done": True}})


@pytest.mark.parametrize("minimum,maximum,values,selected",[
    ("1000000000000000000.01","1000000000000000000.02",
     ["1000000000000000000.00","1000000000000000000.01","1000000000000000000.02","1000000000000000000.03"],{1,2}),
    ("9007199254740992.02","9007199254740992.02",
     ["9007199254740992.01","9007199254740992.02","9007199254740992.03"],{1}),
])
async def test_actual_durable_worker_and_legacy_xlsx_preserve_exact_price_filter_ids(
        contract,export_flags,minimum,maximum,values,selected):
    from decimal import Decimal
    import io
    import openpyxl
    from export_worker import run_one
    activity="worker-price-"+uuid.uuid4().hex
    await contract.db.inventory_activities.insert_one({"id":activity,"kode_satker":contract.users["a"]["kode_satker"],
        "status_pengesahan":"draft","nama_kegiatan":"Harga eksak worker","nomor_surat":"SYNTHETIC"})
    rows=[{"id":f"{activity}-{index}","asset_code":activity,"NUP":str(index),"asset_name":f"{activity}-{index}",
        "activity_id":activity,"purchase_price":price,"version":1} for index,price in enumerate(values)]
    await contract.db.assets.insert_many(rows)
    await contract.db.assets.insert_one({"id":activity+"-foreign","asset_code":activity,"NUP":"foreign",
        "asset_name":activity+"-foreign","activity_id":"contract-activity-b","purchase_price":minimum})
    params={"activity_id":activity,"price_min":minimum,"price_max":maximum}
    expected={f"{activity}-{index}" for index in selected}
    listed=await contract.http.get("/api/assets",headers=contract.headers["a"],params=params)
    assert listed.status_code==200,listed.text
    assert {row["id"] for row in listed.json()["items"]}==expected
    legacy=await contract.http.get("/api/export/xlsx",headers=contract.headers["a"],params=params)
    assert legacy.status_code==200,legacy.text[:500]
    submitted=await contract.http.post("/api/export/xlsx/async",headers=contract.headers["a"],params=params)
    assert submitted.status_code==200,submitted.text
    job_id=submitted.json()["job_id"]
    job=await contract.db.background_jobs.find_one({"job_id":job_id})
    saved=job["job_spec"]["parameters"]["filters"]
    assert Decimal(saved["price_min"])==Decimal(minimum) and Decimal(saved["price_max"])==Decimal(maximum)
    assert await run_one(contract.db,contract.fs)
    completed=await contract.db.background_jobs.find_one({"job_id":job_id})
    assert completed["status"]=="done",completed.get("error_message")
    downloaded=await contract.http.get(f"/api/jobs/{job_id}/download",headers=contract.headers["a"])
    assert downloaded.status_code==200,downloaded.text[:500]
    def identifiers(data):
        workbook=openpyxl.load_workbook(io.BytesIO(data),read_only=True)
        try:
            return {value for sheet in workbook for row in sheet.iter_rows(values_only=True)
                for value in row if isinstance(value,str) and value.startswith(activity+"-")}
        finally:
            workbook.close()
    assert identifiers(legacy.content)==identifiers(downloaded.content)==expected
