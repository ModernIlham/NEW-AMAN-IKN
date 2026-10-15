import asyncio
import threading

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import export_budget as budget


@pytest.fixture
def database(monkeypatch, tmp_path):
    monkeypatch.setenv("AMAN_EXPORT_LOCK_DIR", str(tmp_path / "render"))
    monkeypatch.setenv("AMAN_EXPORT_GLOBAL_SLOTS", "1")
    monkeypatch.setenv("AMAN_EXPORT_SATKER_SLOTS", "1")
    return AsyncMongoMockClient()["unit_export_budget"]


def run(coro):
    return asyncio.run(coro)


def test_global_physical_slot_and_nested_internal_call(database):
    async def scenario():
        events = []
        async def inner():
            events.append("inner")
            return 7
        async def outer():
            # Trusted nested ASGI/job calls reuse the exact process context.
            return await budget.run_budgeted(inner, "owner", "satker", database=database, force=True)
        assert await budget.run_budgeted(outer, "owner", "satker", database=database, force=True) == 7
        assert events == ["inner"]
        doc = await database.export_resource_budget.find_one({"_id": budget.POOL_ID})
        assert doc["holders"] == [] and doc["queue"] == []
    run(scenario())


def test_cancel_waits_for_thread_before_releasing_physical_slot(database):
    async def scenario():
        started, finish = threading.Event(), threading.Event()
        def builder():
            started.set()
            finish.wait(timeout=5)
            return "file"
        async def render():
            return await asyncio.to_thread(builder)
        task = asyncio.create_task(budget.run_budgeted(render, "owner-1", "satker", database=database, force=True))
        while not started.is_set():
            await asyncio.sleep(.01)
        task.cancel()
        await asyncio.sleep(.02)
        assert not task.done()
        with pytest.raises(HTTPException) as error:
            async with budget.budget_slot("owner-2", "other-satker", database=database, force=True, wait_seconds=.15):
                pytest.fail("cancelled renderer thread still owns the only physical slot")
        assert error.value.status_code == 429
        finish.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        async with budget.budget_slot("owner-2", "other-satker", database=database, force=True, wait_seconds=.2):
            pass
    run(scenario())


def test_physical_slots_survive_metadata_disagreement(database):
    async def scenario():
        directory = budget._lock_directory(database)
        config = budget._configuration(directory)
        held = budget._physical_claim(directory, config, "owner-1", "satker-1")
        assert held
        try:
            # Even a missing Mongo holder cannot allow another CPU renderer.
            with pytest.raises(HTTPException):
                async with budget.budget_slot("owner-2", "satker-2", database=database, force=True, wait_seconds=.1):
                    pytest.fail("physical cap exceeded")
        finally:
            import os
            for fd in held:
                os.close(fd)
    run(scenario())


def test_cancelled_unknown_admission_reply_removes_queued_ticket(database):
    from types import SimpleNamespace
    collection = database.export_resource_budget
    class InterruptedReply:
        def __getattr__(self, name):
            return getattr(collection, name)
        async def find_one_and_update(self, *args, **kwargs):
            await collection.find_one_and_update(*args, **kwargs)
            raise asyncio.CancelledError
    interrupted = SimpleNamespace(name=database.name, export_resource_budget=InterruptedReply())
    async def scenario():
        with pytest.raises(asyncio.CancelledError):
            async with budget.budget_slot("owner", "satker", database=interrupted, force=True):
                pytest.fail("admission reply was cancelled")
        document = await collection.find_one({"_id": budget.POOL_ID})
        assert document["queue"] == [] and document["holders"] == []
        async with budget.budget_slot("owner", "satker", database=database, force=True):
            pass
    run(scenario())


def test_capacity_configuration_cannot_drift_between_live_workers(database, monkeypatch):
    directory = budget._lock_directory(database)
    budget._configuration(directory)
    monkeypatch.setenv("AMAN_EXPORT_GLOBAL_SLOTS", "2")
    with pytest.raises(RuntimeError, match="drain"):
        budget._configuration(directory)


def test_route_registry_covers_renderers_and_excludes_file_downloads():
    for path in ("/api/export/xlsx", "/api/export/pdf", "/api/export/geo", "/api/pegawai/export-xlsx",
                 "/api/inventory-activities/k/rhi-pdf", "/api/pelaporan/lbp-docx", "/api/stiker/label",
                 "/api/inventory-activities/k/dbhi/ditemukan/docx", "/api/assets/a/card",
                 "/api/pembukuan/kib-pdf/a", "/api/persediaan/nota-dinas",
                 "/api/pembukuan/permohonan/p/dokumen", "/api/documents/proposal",
                 "/api/integritas/ekspor-ringkasan", "/api/siman/import/i/belum-tercatat.csv",
                 "/api/spasial/ekspor/template", "/api/inventory-activities/k/executive-summary-html"):
        assert budget.heavy_route(path), path
    assert budget.heavy_route("/api/assets/cards/bulk", "POST")
    assert budget.heavy_route("/api/inventory-activities/k/batch-pdf-zip", "POST")
    assert budget.heavy_route("/api/bast/b/kirim-ttd", "POST")
    for path in ("/api/assets", "/api/health", "/api/jobs/x/download", "/api/unduhan/x/file", "/api/backup/download/x"):
        assert not budget.heavy_route(path), path
    assert not budget.heavy_route("/api/export/xlsx/async", "POST")


def test_actual_file_route_inventory_requires_budget_or_explicit_non_renderer_reason():
    """New file endpoints require an explicit admission/serving decision."""
    import ast
    from pathlib import Path
    exemptions = {
        "/api/backup/download/{job_id}": "download existing ZIP",
        "/api/backup/arsip/{nama}": "download existing ZIP",
        "/api/assets/{asset_id}/doc-file/{item_idx}/{file_type}/{file_idx}": "serve existing attachment",
        "/api/inventory-activities/{activity_id}/documents/{idx}": "serve existing attachment",
        "/api/assets/{asset_id}/checklist/{item_idx}/documents/{doc_idx}": "serve existing attachment",
        "/api/assets/{asset_id}/bast": "serve existing attachment",
        "/api/inventory-activities/{activity_id}/pengesahan-dokumen/{doc_id}": "serve existing attachment",
        "/api/ttd/permintaan/{sr_id}/dokumen": "serve existing attachment",
        "/api/ttd/tandatangan/{sr_id}/dokumen": "serve existing attachment",
        "/api/bast/{bast_id}/bukti": "upload/serve existing attachment",
        "/api/inventory-activities/{activity_id}/pengesahan-dokumen": "upload existing PDF",
        "/api/ttd/permintaan/unggah": "upload existing PDF",
        "/api/templates/csv": "fixed two-row CSV template",
        "/api/kodefikasi/template": "fixed CSV template",
        "/api/pegawai/template-impor": "fixed CSV template",
        "/api/persediaan/template": "fixed CSV template",
    }
    uncovered, used = [], set()
    for file in (Path(__file__).resolve().parents[2] / "routes").glob("*.py"):
        source = file.read_text()
        tree, prefixes = ast.parse(source), {}
        for node in tree.body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            call = node.value
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "APIRouter":
                prefix = next((kw.value.value for kw in call.keywords
                               if kw.arg == "prefix" and isinstance(kw.value, ast.Constant)), "")
                for target in node.targets if isinstance(node, ast.Assign) else [node.target]:
                    if isinstance(target, ast.Name):
                        prefixes[target.id] = prefix
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            function = ast.get_source_segment(source, node)
            # Owned attachment readers determine MIME from stored metadata.
            # Their serving routes still require an explicit non-renderer
            # decision even after a literal PDF MIME leaves the handler.
            reads_attachment = any(isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                                   and call.func.id == "read_media" for call in ast.walk(node))
            if not reads_attachment and not any(mime in function for mime in ("application/pdf", "spreadsheetml", "wordprocessingml",
                    "presentationml", "application/zip", "text/csv", "_DOCX_MIME", "_XLSX_MIME")):
                continue
            for decorator in node.decorator_list:
                if not (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)
                        and decorator.func.attr in {"get", "post", "put", "patch"}
                        and isinstance(decorator.func.value, ast.Name) and decorator.args
                        and isinstance(decorator.args[0], ast.Constant)):
                    continue
                route = "/api" + prefixes.get(decorator.func.value.id, "") + decorator.args[0].value
                if route in exemptions:
                    used.add(route)
                elif not budget.heavy_route(route, decorator.func.attr.upper()):
                    uncovered.append(f"{file.name}:{node.lineno} {decorator.func.attr.upper()} {route}")
    assert uncovered == [], "File routes missing render admission: " + ", ".join(uncovered)
    assert used == exemptions.keys(), "Remove stale non-renderer exceptions"


def test_capacity_defaults_and_runtime_attestation_share_pure_parser(monkeypatch):
    for name in ["AMAN_EXPORT_GLOBAL_SLOTS","AMAN_EXPORT_SATKER_SLOTS","AMAN_EXPORT_GLOBAL_BUDGET_ENABLED"]:
        monkeypatch.delenv(name,raising=False)
    assert budget.capacity_configuration()=={"schema":1,"capacity":2,"satker_slots":2}
    assert budget.runtime_capabilities()=={"enabled":False,"ok":True,"slots":2,"satker_slots":2,"error_category":None}
    monkeypatch.setenv("AMAN_EXPORT_GLOBAL_SLOTS","1")
    monkeypatch.setenv("AMAN_EXPORT_GLOBAL_BUDGET_ENABLED","1")
    assert budget.capacity_configuration()=={"schema":1,"capacity":1,"satker_slots":1}
    assert budget.runtime_capabilities()["slots"]==1


@pytest.mark.parametrize("global_slots,satker_slots",[("0","1"),("9","1"),("1","2"),("NaN","1"),("1","bad-private-value")])
def test_invalid_capacity_never_clamps_to_a_reported_valid_configuration(monkeypatch,global_slots,satker_slots):
    monkeypatch.setenv("AMAN_EXPORT_GLOBAL_SLOTS",global_slots)
    monkeypatch.setenv("AMAN_EXPORT_SATKER_SLOTS",satker_slots)
    with pytest.raises(ValueError):
        budget.capacity_configuration()
    assert budget.runtime_capabilities()["ok"] is False
    assert budget.runtime_capabilities()["error_category"]=="invalid_capacity_configuration"
    assert "bad-private-value" not in str(budget.runtime_capabilities())
