"""Authenticated real ASGI render admission, cancellation and fairness.

Small synthetic fixtures measure responsiveness; these numbers are evidence for
this run, not a production SLO or a capacity claim for the VPS.
"""
import asyncio
import io
import json
import os
import resource
import statistics
import threading
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]


@pytest.fixture
def budget_flags(monkeypatch, tmp_path):
    monkeypatch.setenv("AMAN_EXPORT_GLOBAL_BUDGET_ENABLED", "1")
    monkeypatch.setenv("AMAN_EXPORT_DURABLE_XLSX_ENABLED", "0")
    monkeypatch.setenv("AMAN_EXPORT_GLOBAL_SLOTS", "1")
    monkeypatch.setenv("AMAN_EXPORT_SATKER_SLOTS", "1")
    monkeypatch.setenv("AMAN_EXPORT_LOCK_DIR", str(tmp_path / "asgi-budget"))


async def until(condition, seconds=3):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if await condition():
            return
        await asyncio.sleep(.005)
    raise AssertionError("ASGI render checkpoint timed out")


async def queue_size(contract, count):
    record = await contract.db.export_resource_budget.find_one({"_id": "render_v1"}) or {}
    return len(record.get("queue", [])) == count


async def thread_ready(event):
    return event.is_set()


async def seed(contract):
    await contract.db.pegawai.delete_many({"id": {"$in": ["asgi-employee-a", "asgi-employee-b"]}})
    await contract.db.pegawai.insert_many([
        {"id": "asgi-employee-a", "nama": "ASGI A", "kode_satker": contract.users["a"]["kode_satker"]},
        {"id": "asgi-employee-b", "nama": "ASGI B", "kode_satker": contract.users["b"]["kode_satker"]},
    ])


def check_xlsx(response, expected):
    assert response.status_code == 200, response.text[:150]
    from openpyxl import load_workbook
    book = load_workbook(io.BytesIO(response.content), read_only=True)
    assert any(expected in row for row in book["Data Pegawai"].values)


async def test_cancelled_http_render_keeps_slot_and_lease_light_routes_respond(contract, budget_flags, monkeypatch):
    import export_budget
    import routes.pegawai as pegawai
    await seed(contract)
    monkeypatch.setattr(export_budget, "QUEUE_LIMIT", 2)
    original = pegawai._build_pegawai_xlsx
    entered, finish = threading.Event(), threading.Event()
    starts, counts = [], {}
    mutex = threading.Lock()
    def controlled_builder(items):
        who = next(item["nama"] for item in items if item["nama"].startswith("ASGI "))
        with mutex:
            counts[who] = counts.get(who, 0) + 1
            sequence = counts[who]
            starts.append({"who": who, "sequence": sequence, "at": time.monotonic()})
        if who == "ASGI A" and sequence == 1:
            entered.set()
            if not finish.wait(timeout=15):
                raise AssertionError("Synthetic renderer was not released")
        return original(items)
    monkeypatch.setattr(pegawai, "_build_pegawai_xlsx", controlled_builder)
    route = "/api/pegawai/export-xlsx"
    baseline_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    first = asyncio.create_task(contract.http.get(route, headers=contract.headers["a"]))
    others = []
    try:
        await until(lambda: thread_ready(entered))
        assert await contract.db.restore_write_leases.count_documents({}) == 1
        first.cancel()
        await asyncio.sleep(.02)
        assert not first.done(), "The cancelled request must wait for its live renderer thread"
        second_at = time.monotonic()
        second = asyncio.create_task(contract.http.get(route, headers=contract.headers["b"]))
        others.append(second)
        await until(lambda: queue_size(contract, 1))
        third_at = time.monotonic()
        third = asyncio.create_task(contract.http.get(route, headers=contract.headers["a"]))
        others.append(third)
        await until(lambda: queue_size(contract, 2))
        overloaded = await contract.http.get(route, headers={**contract.headers["root"], "X-Render-Budget-Bypass": "1"})
        assert overloaded.status_code == 429 and overloaded.headers["Retry-After"] == "5"
        per_owner = await contract.http.get(route, headers=contract.headers["a"])
        assert per_owner.status_code == 429
        assert not second.done() and not third.done() and len(starts) == 1
        light_ms = []
        for _ in range(12):
            stamp = time.perf_counter()
            async with asyncio.timeout(3):
                response = await contract.http.get("/api/health")
            assert response.status_code == 200
            light_ms.append((time.perf_counter() - stamp) * 1000)
        # No request lease was created for an admission rejected before render.
        assert await contract.db.restore_write_leases.count_documents({}) == 1
        finish.set()
        with pytest.raises(asyncio.CancelledError):
            await first
        check_xlsx(await second, "ASGI B")
        check_xlsx(await third, "ASGI A")
        assert [(item["who"], item["sequence"]) for item in starts] == [("ASGI A", 1), ("ASGI B", 1), ("ASGI A", 2)]
        record = await contract.db.export_resource_budget.find_one({"_id": "render_v1"})
        assert record["holders"] == [] and record["queue"] == []
        assert await contract.db.restore_write_leases.count_documents({}) == 0
        measurements = {
            "measured_at": datetime.now(timezone.utc).isoformat(), "scope": "synthetic loopback ASGI, two satker, two employees",
            "global_slots": 1, "tested_queue_limit": 2, "production_default_queue_limit": 32,
            "executor_threads": 2, "executor_pending": 2, "light_requests": len(light_ms),
            "light_p50_ms": round(statistics.median(light_ms), 3),
            "light_p95_ms": round(sorted(light_ms)[int(.95 * (len(light_ms) - 1))], 3),
            "light_max_ms": round(max(light_ms), 3),
            "queued_wait_ms": [round((starts[1]["at"] - second_at) * 1000, 3), round((starts[2]["at"] - third_at) * 1000, 3)],
            "process_peak_rss_before_kib": baseline_rss,
            "process_peak_rss_after_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "cancel_holds_slot": True, "cancel_holds_writer_lease": True, "queue_and_owner_overload_429": True,
            "fifo_order": ["satker-a-first", "satker-b", "satker-a-second"], "artifacts_valid": True,
            "remaining_holders": 0, "remaining_waiters": 0, "remaining_request_leases": 0,
        }
        destination = os.environ.get("AMAN_EXPORT_STRESS_REPORT")
        if destination:
            Path(destination).parent.mkdir(parents=True, exist_ok=True)
            Path(destination).write_text(json.dumps(measurements, ensure_ascii=False, indent=2) + "\n")
    finally:
        finish.set()
        await asyncio.gather(first, *others, return_exceptions=True)


async def test_private_auth_and_public_product_documents_keep_existing_contract(contract, budget_flags):
    response = await contract.http.get("/api/pegawai/export-xlsx")
    assert response.status_code == 401
    assert await contract.db.restore_write_leases.count_documents({}) == 0
    for route, expected in (("/api/documents/proposal", "word/document.xml"), ("/api/documents/ppt", "ppt/presentation.xml")):
        public = await contract.http.get(route)
        assert public.status_code == 200, public.text[:150]
        with zipfile.ZipFile(io.BytesIO(public.content)) as artifact:
            assert expected in artifact.namelist()
    assert await contract.db.restore_write_leases.count_documents({}) == 0
    record = await contract.db.export_resource_budget.find_one({"_id": "render_v1"})
    assert record["queue"] == [] and record["holders"] == []


async def test_duplicate_authentication_values_use_same_principal_as_handler(contract, budget_flags, monkeypatch):
    import export_budget
    await seed(contract)
    admitted = []
    physical_claim = export_budget._physical_claim
    def capture(directory, config, owner, satker):
        admitted.append((owner, satker))
        return physical_claim(directory, config, owner, satker)
    monkeypatch.setattr(export_budget, "_physical_claim", capture)
    response = await contract.http.get("/api/pegawai/export-xlsx", headers=[
        ("Authorization", contract.headers["a"]["Authorization"]),
        ("Authorization", contract.headers["b"]["Authorization"]),
    ])
    check_xlsx(response, "ASGI A")
    assert admitted and set(admitted) == {(contract.users["a"]["id"], contract.users["a"]["kode_satker"])}
    admitted.clear()
    # FastAPI takes the first header and last duplicate query parameter.
    response = await contract.http.get("/api/inventory-activities/contract-activity-b/rhi-pdf", params=[
        ("token", contract.headers["a"]["Authorization"].split(" ", 1)[1]),
        ("token", contract.headers["b"]["Authorization"].split(" ", 1)[1]),
    ])
    assert response.status_code == 200 and response.content.startswith(b"%PDF-"), response.text[:150]
    assert admitted and set(admitted) == {(contract.users["b"]["id"], contract.users["b"]["kode_satker"])}
    assert await contract.db.restore_write_leases.count_documents({}) == 0


async def test_cancel_after_mongo_admission_before_reply_does_not_leave_waiter(contract, budget_flags, monkeypatch):
    await seed(contract)
    collection_type = type(contract.db.export_resource_budget)
    original = collection_type.find_one_and_update
    interrupted = False
    async def lose_admission_reply(collection, query, update, *args, **kwargs):
        nonlocal interrupted
        result = await original(collection, query, update, *args, **kwargs)
        if collection.name == "export_resource_budget" and "queue" in update.get("$push", {}) and not interrupted:
            interrupted = True
            raise asyncio.CancelledError
        return result
    monkeypatch.setattr(collection_type, "find_one_and_update", lose_admission_reply)
    with pytest.raises(asyncio.CancelledError):
        await contract.http.get("/api/pegawai/export-xlsx", headers=contract.headers["a"])
    assert interrupted
    record = await contract.db.export_resource_budget.find_one({"_id": "render_v1"})
    assert record["queue"] == [] and record["holders"] == []
    assert await contract.db.restore_write_leases.count_documents({}) == 0
    check_xlsx(await contract.http.get("/api/pegawai/export-xlsx", headers=contract.headers["a"]), "ASGI A")


async def test_blocked_owner_does_not_idle_free_slot_for_other_satker(contract, budget_flags, monkeypatch):
    import routes.pegawai as pegawai
    await seed(contract)
    monkeypatch.setenv("AMAN_EXPORT_GLOBAL_SLOTS", "2")
    monkeypatch.setenv("AMAN_EXPORT_SATKER_SLOTS", "1")
    original = pegawai._build_pegawai_xlsx
    first_started, foreign_started, release = threading.Event(), threading.Event(), threading.Event()
    counts = {}
    def builder(items):
        who = next(item["nama"] for item in items if item["nama"].startswith("ASGI "))
        counts[who] = counts.get(who, 0) + 1
        if who == "ASGI A" and counts[who] == 1:
            first_started.set()
            release.wait(timeout=10)
        if who == "ASGI B":
            foreign_started.set()
        return original(items)
    monkeypatch.setattr(pegawai, "_build_pegawai_xlsx", builder)
    route = "/api/pegawai/export-xlsx"
    first = asyncio.create_task(contract.http.get(route, headers=contract.headers["a"]))
    tasks = [first]
    try:
        await until(lambda: thread_ready(first_started))
        same_owner = asyncio.create_task(contract.http.get(route, headers=contract.headers["a"]))
        tasks.append(same_owner)
        await until(lambda: queue_size(contract, 1))
        foreign = asyncio.create_task(contract.http.get(route, headers=contract.headers["b"]))
        tasks.append(foreign)
        await until(lambda: thread_ready(foreign_started), seconds=1)
        check_xlsx(await foreign, "ASGI B")
        assert not first.done() and not same_owner.done()
    finally:
        release.set()
        await asyncio.gather(*tasks, return_exceptions=True)
    assert await contract.db.restore_write_leases.count_documents({}) == 0
