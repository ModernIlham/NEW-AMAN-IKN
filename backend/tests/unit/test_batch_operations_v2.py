"""Operation proofs and receipts, with real handlers and injected failures.

Mongo semantics are also exercised by the separate managed integration gate.
These deterministic tests force interleavings not practical to schedule there.
"""
import asyncio
import uuid
from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

import batch_operations as batch
import shared_utils
from auth_utils import require_writer
from routes.batch import batch_router

USER = {"id": "operator-1", "name": "Operator Uji", "username": "uji", "kode_satker": "001", "role": "admin"}


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def database(monkeypatch):
    database = AsyncMongoMockClient()["unit_batch_v2"]
    monkeypatch.setattr(batch, "db", database)
    monkeypatch.setattr(shared_utils, "db", database)
    monkeypatch.setattr(batch, "store_photo_to_gridfs", AsyncMock(side_effect=lambda _: str(uuid.uuid4())))
    monkeypatch.setattr(batch, "delete_photo_from_gridfs", AsyncMock())
    monkeypatch.setattr(batch, "_prepare_photos", AsyncMock(return_value=[]))
    monkeypatch.setattr(batch, "create_thumbnail", lambda _: "cover")
    monkeypatch.setattr(batch, "create_gallery_thumbnail", lambda _: "gallery")
    import meili_utils
    import routes.websocket
    monkeypatch.setattr(meili_utils, "jadwalkan_sync_id", lambda *_: None)
    monkeypatch.setattr(routes.websocket, "notify_asset_change", AsyncMock())
    run(database.inventory_activities.insert_many([
        {"id": "k1", "kode_satker": "001"}, {"id": "k2", "kode_satker": "002"},
    ]))
    return database


async def payload(database, ids=None, updates=None, versions=None, **extra):
    ids = ids or ["a1"]
    return {"operation_id": f"b2_{int(batch.now_utc().timestamp() * 1000)}_{uuid.uuid4()}",
            "dataset_generation": await batch.dataset_generation(),
            "asset_ids": ids, "expected_versions": versions or dict.fromkeys(ids, 1),
            "updates": updates or {"location": "Ruang baru"}, **extra}


async def asset(database, aid="a1", **fields):
    await database.assets.insert_one({"id": aid, "activity_id": "k1", "version": 1,
                                     "asset_code": "3050101", "NUP": aid, "location": "Lama", **fields})


def test_preflight_deduplicates_versions_and_preserves_missing(database):
    async def scenario():
        await asset(database)
        result = await batch.preflight(["a1", "a1", "missing"], USER)
        assert result["targets"] == [{"id": "a1", "version": 1, "status": "ready"}, {"id": "missing", "status": "missing"}]
        assert result["max_targets"] == 200 and result["dataset_generation"]
        await asset(database, "foreign", activity_id="k2")
        with pytest.raises(HTTPException) as error:
            await batch.preflight(["a1", "foreign"], USER)
        assert error.value.status_code == 403
    run(scenario())


def test_unique_applied_missing_conflict_and_unchanged_counts(database):
    async def scenario():
        await asset(database)
        await asset(database, "stale", version=2)
        await asset(database, "same", location="Ruang baru")
        request = await payload(database, ["a1", "a1", "stale", "same", "gone"])
        result = await batch.execute(request, USER)
        assert {k: result[k] for k in ("requested_unique", "applied", "unchanged", "conflicts", "missing", "updated")} == {
            "requested_unique": 4, "applied": 1, "unchanged": 1, "conflicts": 1, "missing": 1, "updated": 2}
        assert result["state"] == "partial"
        assert (await database.assets.find_one({"id": "same"}))["version"] == 1
        assert await database.audit_logs.count_documents({}) == 1
    run(scenario())


@pytest.mark.parametrize("count", [51, 200])
def test_live_lock_respected_for_large_batches(database, count):
    async def scenario():
        ids = [f"a{i}" for i in range(count)]
        await database.assets.insert_many([{"id": aid, "activity_id": "k1", "version": 1} for aid in ids])
        await database.row_locks.insert_one({"asset_id": ids[-1], "session_id": "other", "expires_at": batch.now_utc() + timedelta(minutes=1)})
        result = await batch.execute(await payload(database, ids), USER, "mine")
        assert result["applied"] == count - 1
        assert result["results"][-1]["reason"] == "locked"
        assert (await database.assets.find_one({"id": ids[-1]}))["version"] == 1
    run(scenario())


def test_201_targets_rejected_before_receipt(database):
    async def scenario():
        request = await payload(database, [f"a{i}" for i in range(201)])
        with pytest.raises(HTTPException) as error:
            await batch.execute(request, USER)
        assert error.value.status_code == 400
        assert await database.batch_operations.count_documents({}) == 0
    run(scenario())


def test_legacy_missing_version_gets_logical_version_two(database):
    async def scenario():
        await asset(database)
        await database.assets.update_one({"id": "a1"}, {"$unset": {"version": ""}})
        result = await batch.execute(await payload(database), USER)
        assert result["results"][0]["version"] == 2
        assert (await database.assets.find_one({"id": "a1"}))["version"] == 2
    run(scenario())


def test_scalar_and_photo_atomic_upload_failure_rolls_back_only_new(database, monkeypatch):
    async def scenario():
        await asset(database, photo_gridfs_ids=["old"], photo_thumbnails=["oldthumb"])
        monkeypatch.setattr(batch, "_prepare_photos", AsyncMock(return_value=[{"data": "p1", "thumb": "t1"}, {"data": "p2", "thumb": "t2"}]))
        monkeypatch.setattr(batch, "store_photo_to_gridfs", AsyncMock(side_effect=["new1", IOError("disk full")]))
        result = await batch.execute(await payload(database, updates={"location": "New", "batch_photos": ["data:image/png;base64,AA=="]}), USER)
        document = await database.assets.find_one({"id": "a1"})
        assert result["failed"] == 1 and result["updated"] == 0
        assert document["location"] == "Lama" and document["version"] == 1
        assert document["photo_gridfs_ids"] == ["old"]
        batch.delete_photo_from_gridfs.assert_awaited_once_with("new1")
    run(scenario())


def test_scalar_photo_checklist_one_cas_preserves_legacy_slots(database, monkeypatch):
    import base64
    import io
    from PIL import Image
    image = io.BytesIO()
    Image.new("RGB", (2, 2), (40, 80, 120)).save(image, format="PNG")
    checklist_photo = "data:image/png;base64," + base64.b64encode(image.getvalue()).decode()
    async def scenario():
        await asset(database, photos=["inline-legacy"], photo_gridfs_ids=[""], photo_thumbnails=["legacy-thumb"],
                    document_checklist=[{"name": "STNK", "checked": False, "photos": ["old-document-photo"], "documents": []}])
        monkeypatch.setattr(batch, "_prepare_photos", AsyncMock(return_value=[{"data": "p1", "thumb": "t1"}]))
        monkeypatch.setattr(batch, "store_photo_to_gridfs", AsyncMock(return_value="new-photo"))
        request = await payload(database, updates={"location": "New", "batch_photos": ["data:image/png;base64,AA=="],
            "document_checklist_items": [{"name": "STNK", "checked": True, "photos": [checklist_photo]}]})
        result = await batch.execute(request, USER)
        document = await database.assets.find_one({"id": "a1"})
        assert result["applied"] == 1 and document["version"] == 2
        assert document["photo_gridfs_ids"] == ["", "new-photo"]
        assert document["photos"] == ["inline-legacy", "p1"]
        assert document["document_checklist"][0]["photos"] == ["old-document-photo", checklist_photo]
        assert document["location"] == "New" and len(document[batch.MARKERS]) == 1
        await batch.execute(request, USER)
        assert (await database.assets.find_one({"id": "a1"}))["version"] == 2
        batch.store_photo_to_gridfs.assert_awaited_once()
    run(scenario())


def test_crash_after_asset_commit_before_receipt_reconciles_after_later_operation(database, monkeypatch):
    class ProcessDied(BaseException):
        pass

    async def scenario():
        await asset(database, purchase_price="100")
        request = await payload(database, updates={"location": "First", "purchase_price": "200"})
        original = batch._after_asset_commit
        monkeypatch.setattr(batch, "_after_asset_commit", AsyncMock(side_effect=ProcessDied()))
        with pytest.raises(ProcessDied):
            await batch.execute(request, USER)
        document = await database.assets.find_one({"id": "a1"})
        assert document["version"] == 2 and document[batch.MARKERS]
        assert await database.audit_logs.count_documents({}) == 0
        monkeypatch.setattr(batch, "_after_asset_commit", original)
        later = await payload(database, updates={"location": "Later"}, versions={"a1": 2})
        assert (await batch.execute(later, USER))["applied"] == 1
        retry = await batch.execute(request, USER)
        assert retry["applied"] == 1 and retry["results"][0]["version"] == 2
        current = await database.assets.find_one({"id": "a1"})
        assert current["version"] == 3 and current["location"] == "Later"
        assert await database.audit_logs.count_documents({}) == 2
        assert await database.mutasi_bmn.count_documents({}) == 1
        await batch.resume(request["operation_id"], USER)
        assert await database.mutasi_bmn.count_documents({}) == 1
    run(scenario())


def test_delete_reconciliation_preserves_result_after_asset_removed(database, monkeypatch):
    class ProcessDied(BaseException):
        pass

    async def scenario():
        await asset(database)
        request = await payload(database)
        monkeypatch.setattr(batch, "_after_asset_commit", AsyncMock(side_effect=ProcessDied()))
        with pytest.raises(ProcessDied):
            await batch.execute(request, USER)
        document = await database.assets.find_one({"id": "a1"}, {"_id": 0})
        await batch.reconcile_before_asset_delete(document)
        assert (await database.assets.delete_one(batch.cas_filter(document))).deleted_count == 1
        result = await batch.resume(request["operation_id"], USER)
        assert result["applied"] == 1 and result["missing"] == 0
        assert await database.audit_logs.count_documents({}) == 1
    run(scenario())


def test_payload_owner_satker_and_dataset_are_bound_to_identity(database):
    async def scenario():
        await asset(database)
        request = await payload(database)
        await batch.execute(request, USER)
        for altered, user in [({**request, "updates": {"location": "Different"}}, USER),
                               (request, {**USER, "id": "other"}),
                               (request, {**USER, "kode_satker": ""})]:
            with pytest.raises(HTTPException) as error:
                await batch.execute(altered, user)
            assert error.value.status_code == 409
        with pytest.raises(HTTPException) as error:
            await batch.status(request["operation_id"], {**USER, "id": "other"})
        assert error.value.status_code == 404
        await batch.rotate_dataset_generation("unit-restore")
        with pytest.raises(HTTPException) as error:
            await batch.resume(request["operation_id"], USER)
        assert error.value.detail["code"] == "dataset_changed"
        assert (await database.assets.find_one({"id": "a1"}))["version"] == 2
    run(scenario())


def test_replay_horizon_never_re_admits_expired_key(database):
    async def scenario():
        await asset(database)
        old = batch.now_utc() - timedelta(days=8)
        request = await payload(database, operation_id=f"b2_{int(old.timestamp() * 1000)}_{uuid.uuid4()}")
        with pytest.raises(HTTPException) as error:
            await batch.execute(request, USER)
        assert error.value.detail["code"] == "operation_expired"
        assert await database.batch_operations.count_documents({}) == 0
    run(scenario())


def test_marker_budget_does_not_evict_unexpired_proofs(database):
    async def scenario():
        markers = [{"operation_id": str(i), "issued_epoch": batch.now_utc().timestamp()} for i in range(batch.MAX_ASSET_MARKERS)]
        await asset(database, **{batch.MARKERS: markers})
        result = await batch.execute(await payload(database), USER)
        assert result["failed"] == 1 and result["results"][0]["reason"] == "proof_budget_exceeded"
        assert (await database.assets.find_one({"id": "a1"}))[batch.MARKERS] == markers
    run(scenario())


def test_clear_empty_media_is_unchanged_and_stale_lock_is_ignored(database):
    async def scenario():
        await asset(database)
        await database.row_locks.insert_one({"asset_id": "a1", "session_id": "other", "expires_at": batch.now_utc() - timedelta(seconds=1)})
        result = await batch.execute(await payload(database, updates={"clear_photos": True, "clear_document_checklist": True}), USER)
        assert result["unchanged"] == 1 and result["applied"] == 0
        assert (await database.assets.find_one({"id": "a1"}))["version"] == 1
    run(scenario())


@pytest.mark.parametrize("updates", [
    {"clear_photos": True, "batch_photos": ["data:image/png;base64,AA=="]},
    {"clear_document_checklist": True, "document_checklist_items": [{"name": "STNK"}]},
    {"location": {"$set": "bad"}}, {"field_not_allowed": "bad"},
])
def test_invalid_combinations_fail_before_admission(database, updates):
    async def scenario():
        await asset(database)
        with pytest.raises(HTTPException) as error:
            await batch.execute(await payload(database, updates=updates), USER)
        assert error.value.status_code == 400
        assert await database.batch_operations.count_documents({}) == 0
    run(scenario())


def test_handlers_require_auth_and_validate_expected_versions(database):
    app = FastAPI()
    app.include_router(batch_router, prefix="/api")
    client = TestClient(app)
    assert client.post("/api/assets/batch-v2/preflight", json={"asset_ids": ["a1"]}).status_code == 401
    app.dependency_overrides[require_writer] = lambda: USER
    run(asset(database))
    preflight = client.post("/api/assets/batch-v2/preflight", json={"asset_ids": ["a1"]})
    assert preflight.status_code == 200
    request = run(payload(database))
    request["expected_versions"] = {}
    response = client.put("/api/assets/batch-v2", json=request)
    assert response.status_code == 400 and response.json()["detail"]["code"] == "expected_versions_required"
    request["expected_versions"] = {"a1": 1}
    response = client.put("/api/assets/batch-v2", json=request)
    assert response.status_code == 200 and response.json()["applied"] == 1
    response = client.get(f"/api/assets/batch-v2/{request['operation_id']}")
    assert response.status_code == 200 and response.json()["applied"] == 1
    response = client.post(f"/api/assets/batch-v2/{request['operation_id']}/resume")
    assert response.status_code == 200 and response.json()["updated"] == 1


def test_prepare_all_chunks_can_resume_without_client_payload(database):
    async def scenario():
        await asset(database)
        await asset(database, "a2")
        first = await payload(database, ["a1"])
        second = await payload(database, ["a2"])
        assert (await batch.execute(first, USER, prepare_only=True))["pending"] == 1
        assert (await batch.execute(second, USER, prepare_only=True))["pending"] == 1
        assert (await database.assets.find_one({"id": "a1"}))["version"] == 1
        assert (await database.assets.find_one({"id": "a2"}))["version"] == 1
        assert (await batch.resume(first["operation_id"], USER))["applied"] == 1
        # A fresh client only knows child identity; server retained its draft.
        assert (await batch.status(second["operation_id"], USER))["pending"] == 1
        assert (await batch.resume(second["operation_id"], USER))["applied"] == 1
        assert (await database.assets.find_one({"id": "a2"}))["version"] == 2
    run(scenario())


def test_cas_interleave_preserves_concurrent_media_and_rolls_back_new_blob(database, monkeypatch):
    async def scenario():
        await asset(database, photo_gridfs_ids=["old"])
        monkeypatch.setattr(batch, "_prepare_photos", AsyncMock(return_value=[{"data": "p", "thumb": "t"}]))
        monkeypatch.setattr(batch, "store_photo_to_gridfs", AsyncMock(return_value="uncommitted"))
        original = batch._asset_changes
        async def intervening(*args):
            fields = await original(*args)
            await database.assets.update_one({"id": "a1"}, {"$set": {
                "version": 2, "photo_gridfs_ids": ["concurrent"],
                "document_checklist": [{"name": "Concurrent", "checked": True}],
            }})
            return fields
        monkeypatch.setattr(batch, "_asset_changes", intervening)
        request = await payload(database, updates={"location": "New", "batch_photos": ["data:image/png;base64,AA=="],
            "document_checklist_items": [{"name": "STNK", "checked": True}]})
        result = await batch.execute(request, USER)
        assert result["conflicts"] == 1 and result["applied"] == 0
        current = await database.assets.find_one({"id": "a1"})
        assert current["location"] == "Lama" and current["version"] == 2
        assert current["photo_gridfs_ids"] == ["concurrent"]
        assert current["document_checklist"][0]["name"] == "Concurrent"
        batch.delete_photo_from_gridfs.assert_awaited_once_with("uncommitted")
        assert await database.audit_logs.count_documents({}) == 0
    run(scenario())


def test_pruning_expired_marker_finishes_audit_and_journal_after_receipt_ttl(database):
    async def scenario():
        old_marker = {"operation_id": "expired-receipt", "payload_hash": "old-hash",
                      "issued_epoch": (batch.now_utc() - timedelta(days=31)).timestamp(),
                      "result": {"id": "a1", "status": "applied", "version": 1},
                      "audit": {"action": "batch_update", "asset_id": "a1", "detail": "Old proof"},
                      "journal": {"asset_id": "a1", "nilai": 100}}
        await asset(database, **{batch.MARKERS: [old_marker]})
        result = await batch.execute(await payload(database), USER)
        assert result["applied"] == 1
        current = await database.assets.find_one({"id": "a1"})
        assert len(current[batch.MARKERS]) == 1
        assert current[batch.MARKERS][0]["operation_id"] == result["operation_id"]
        assert await database.audit_logs.count_documents({}) == 2
        assert await database.mutasi_bmn.count_documents({}) == 1
    run(scenario())


def test_final_proof_size_rejects_only_oversized_target_and_rolls_back_blob(database, monkeypatch):
    import asset_media_limits
    monkeypatch.setattr(asset_media_limits, "MAX_ASSET_BSON_BYTES", 16384)
    monkeypatch.setattr(batch, "_prepare_photos", AsyncMock(return_value=[{"data": "photo", "thumb": "thumb"}]))
    monkeypatch.setattr(batch, "store_photo_to_gridfs", AsyncMock(side_effect=["committed-photo", "rejected-photo"]))
    async def scenario():
        await asset(database)
        # The original fits. Its audit proof repeats asset_name and pushes the
        # final document beyond the limit by more than the legacy allowance.
        await asset(database, "large", asset_name="x" * 5000, legacy_text="y" * 10000)
        request = await payload(database, ["a1", "large"], updates={
            "location": "New", "batch_photos": ["data:image/png;base64,AA=="]})
        result = await batch.execute(request, USER)
        assert result["applied"] == 1 and result["failed"] == 1 and result["pending"] == 0
        rejected = result["results"][1]
        assert rejected["reason"] == "asset_payload_too_large" and rejected["retryable"] is False
        assert (await database.assets.find_one({"id": "a1"}))["photo_gridfs_ids"] == ["committed-photo"]
        large = await database.assets.find_one({"id": "large"})
        assert large["version"] == 1 and large["location"] == "Lama" and batch.MARKERS not in large
        batch.delete_photo_from_gridfs.assert_awaited_once_with("rejected-photo")
        # A permanent per-target rejection is a stable receipt, not an endless
        # resume that uploads and rejects the same photo on every attempt.
        replay = await batch.resume(request["operation_id"], USER)
        assert replay["results"] == result["results"]
        assert batch.store_photo_to_gridfs.await_count == 2
    run(scenario())
