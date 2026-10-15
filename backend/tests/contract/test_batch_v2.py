"""batch_v2 route contracts on MongoDB, never the application's configured DB."""
import base64
import io
import uuid

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]


async def seed(contract, *, activity="a", **fields):
    aid = "contract-batch-" + uuid.uuid4().hex
    await contract.db.assets.insert_one({
        "id": aid, "activity_id": "contract-activity-" + activity,
        "asset_code": "3050104001", "NUP": aid, "asset_name": "Aset sintetis batch",
        "location": "Sebelum", "version": 1, "photos": [], "photo_gridfs_ids": [],
        **fields,
    })
    return aid


async def request_for(contract, ids, updates=None):
    response = await contract.http.post("/api/assets/batch-v2/preflight", json={"asset_ids": ids}, headers=contract.headers["a"])
    assert response.status_code == 200, response.text
    preflight = response.json()
    import batch_operations
    return {"operation_id": f"b2_{int(batch_operations.now_utc().timestamp() * 1000)}_{uuid.uuid4()}",
            "dataset_generation": preflight["dataset_generation"], "asset_ids": ids,
            "expected_versions": {a["id"]: a.get("version", 1) for a in preflight["targets"]},
            "updates": updates or {"location": "Sesudah"}}


def image_data():
    from PIL import Image
    output = io.BytesIO()
    Image.new("RGB", (24, 24), (48, 90, 120)).save(output, format="JPEG")
    return "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode()


async def test_old_snapshot_cannot_mutate_recreated_semantic_id(contract, monkeypatch):
    import batch_operations as batch
    aid = await seed(contract)
    old = await contract.db.assets.find_one({"id": aid})
    await contract.db.assets.delete_one({"_id": old["_id"]})
    replacement = {key: value for key, value in old.items() if key != "_id"}
    await contract.db.assets.insert_one(replacement)
    assert replacement["_id"] != old["_id"]
    write = await contract.db.assets.update_one(batch.cas_filter(old), {"$set": {"location": "Stale"}})
    assert write.matched_count == 0
    assert (await contract.db.assets.delete_one(batch.cas_filter(old))).deleted_count == 0
    # Exercise the same race after the actual batch read but before its CAS.
    request = await request_for(contract, [aid])
    original = batch._asset_changes
    replaced = []
    async def replace_after_read(snapshot, *args):
        changes = await original(snapshot, *args)
        await contract.db.assets.delete_one({"_id": snapshot["_id"]})
        fresh = {key: value for key, value in snapshot.items() if key != "_id"}
        await contract.db.assets.insert_one(fresh)
        replaced.append(fresh["_id"])
        return changes
    monkeypatch.setattr(batch, "_asset_changes", replace_after_read)
    response = await contract.http.put("/api/assets/batch-v2", json=request, headers=contract.headers["a"])
    assert response.status_code == 200, response.text
    assert response.json()["conflicts"] == 1 and response.json()["applied"] == 0
    fresh = await contract.db.assets.find_one({"id": aid})
    assert fresh["_id"] == replaced[0] and fresh["location"] == "Sebelum" and fresh["version"] == 1
    assert batch.MARKERS not in fresh


async def test_atomic_scalar_media_and_retry_after_later_operation(contract):
    aid = await seed(contract, purchase_price="100")
    request = await request_for(contract, [aid, aid], {"location": "Pertama", "purchase_price": "200", "batch_photos": [image_data()],
        "document_checklist_items": [{"name": "STNK", "checked": True, "photos": []}]})
    response = await contract.http.put("/api/assets/batch-v2", json=request, headers=contract.headers["a"])
    assert response.status_code == 200, response.text
    assert response.json()["requested_unique"] == 1 and response.json()["applied"] == 1
    first = await contract.db.assets.find_one({"id": aid})
    assert first["version"] == 2 and len(first["photo_gridfs_ids"]) == 1
    assert first["document_checklist"][0]["checked"]
    grid_id = first["photo_gridfs_ids"][0]
    from bson import ObjectId
    stream = await contract.fs.open_download_stream(ObjectId(grid_id))
    assert await stream.read()
    later = await request_for(contract, [aid], {"location": "Kedua"})
    response = await contract.http.put("/api/assets/batch-v2", json=later, headers=contract.headers["a"])
    assert response.status_code == 200, response.text
    response = await contract.http.put("/api/assets/batch-v2", json=request, headers=contract.headers["a"])
    assert response.status_code == 200 and response.json()["results"][0]["version"] == 2
    current = await contract.db.assets.find_one({"id": aid})
    assert current["version"] == 3 and current["location"] == "Kedua" and current["photo_gridfs_ids"] == [grid_id]
    assert await contract.db.mutasi_bmn.count_documents({"asset_id": aid}) == 1


async def test_cas_mismatch_does_not_overwrite_or_store_photo(contract):
    aid = await seed(contract)
    request = await request_for(contract, [aid], {"location": "Stale", "batch_photos": [image_data()]})
    await contract.db.assets.update_one({"id": aid, "version": 1}, {"$set": {"location": "Concurrent"}, "$inc": {"version": 1}})
    response = await contract.http.put("/api/assets/batch-v2", json=request, headers=contract.headers["a"])
    assert response.status_code == 200 and response.json()["conflicts"] == 1
    current = await contract.db.assets.find_one({"id": aid})
    assert current["version"] == 2 and current["location"] == "Concurrent" and current["photo_gridfs_ids"] == []


async def test_crash_after_commit_receipt_reconstruction_and_delete_guard(contract, monkeypatch):
    import batch_operations
    class WorkerDied(BaseException):
        pass
    aid = await seed(contract, purchase_price="100")
    request = await request_for(contract, [aid], {"location": "Committed", "purchase_price": "250"})
    original = batch_operations._after_asset_commit
    async def crash(*_):
        raise WorkerDied()
    monkeypatch.setattr(batch_operations, "_after_asset_commit", crash)
    # Invoke the very same service as the authenticated handler. BaseException
    # simulates a worker disappearance, escaping ordinary per-asset errors.
    with pytest.raises(WorkerDied):
        await batch_operations.execute(request, contract.users["a"])
    committed = await contract.db.assets.find_one({"id": aid}, {"_id": 0})
    assert committed["version"] == 2 and committed["location"] == "Committed"
    assert await contract.db.mutasi_bmn.count_documents({"asset_id": aid}) == 0
    monkeypatch.setattr(batch_operations, "_after_asset_commit", original)
    # Actual admin delete must persist the missing receipt before deleting proof.
    deleted = await contract.http.delete(f"/api/assets/{aid}", headers=contract.headers["a"])
    assert deleted.status_code == 200, deleted.text
    response = await contract.http.post(f"/api/assets/batch-v2/{request['operation_id']}/resume", headers=contract.headers["a"])
    assert response.status_code == 200, response.text
    assert response.json()["applied"] == 1 and response.json()["missing"] == 0
    assert await contract.db.assets.count_documents({"id": aid}) == 0
    assert await contract.db.mutasi_bmn.count_documents({"asset_id": aid}) == 1


async def test_scope_and_required_versions_rejected_before_write(contract):
    own = await seed(contract)
    foreign = await seed(contract, activity="b")
    response = await contract.http.post("/api/assets/batch-v2/preflight", json={"asset_ids": [own, foreign]}, headers=contract.headers["a"])
    assert response.status_code == 403
    request = await request_for(contract, [own])
    request["expected_versions"] = {}
    response = await contract.http.put("/api/assets/batch-v2", json=request, headers=contract.headers["a"])
    assert response.status_code == 400 and response.json()["detail"]["code"] == "expected_versions_required"
    assert (await contract.db.assets.find_one({"id": own}))["version"] == 1


async def test_two_workers_same_identity_commit_once(contract):
    import asyncio
    aid = await seed(contract)
    request = await request_for(contract, [aid], {"location": "Once", "batch_photos": [image_data()]})
    responses = await asyncio.gather(*[
        contract.http.put("/api/assets/batch-v2", json=request, headers=contract.headers["a"]) for _ in range(2)
    ])
    assert all(r.status_code == 200 for r in responses), [r.text for r in responses]
    response = await contract.http.get(f"/api/assets/batch-v2/{request['operation_id']}", headers=contract.headers["a"])
    assert response.status_code == 200 and response.json()["applied"] == 1
    current = await contract.db.assets.find_one({"id": aid})
    assert current["version"] == 2 and len(current["photo_gridfs_ids"]) == 1
    response = await contract.http.get(f"/api/assets/batch-v2/{request['operation_id']}", headers=contract.headers["b"])
    assert response.status_code == 404


async def test_prepare_has_no_mutation_and_resume_uses_server_draft(contract):
    aid = await seed(contract)
    request = await request_for(contract, [aid])
    response = await contract.http.post("/api/assets/batch-v2/prepare", json=request, headers=contract.headers["a"])
    assert response.status_code == 200 and response.json()["pending"] == 1
    assert (await contract.db.assets.find_one({"id": aid}))["version"] == 1
    response = await contract.http.post(f"/api/assets/batch-v2/{request['operation_id']}/resume", headers=contract.headers["a"])
    assert response.status_code == 200 and response.json()["applied"] == 1
    assert (await contract.db.assets.find_one({"id": aid}))["version"] == 2


@pytest.mark.parametrize("remove_activity", [False, True])
async def test_bulk_paths_reconcile_proofs_and_release_real_media(contract, monkeypatch, remove_activity):
    import batch_operations
    from bson import ObjectId
    class WorkerDied(BaseException):
        pass
    activity_id = "contract-bulk-" + uuid.uuid4().hex
    await contract.db.inventory_activities.insert_one({"id": activity_id, "kode_satker": contract.users["a"]["kode_satker"], "status_pengesahan": "draft"})
    aid = await seed(contract, activity_id=activity_id, purchase_price="100")
    request = await request_for(contract, [aid], {"purchase_price": "300", "batch_photos": [image_data()]})
    original = batch_operations._after_asset_commit
    async def crash(*_):
        raise WorkerDied()
    monkeypatch.setattr(batch_operations, "_after_asset_commit", crash)
    with pytest.raises(WorkerDied):
        await batch_operations.execute(request, contract.users["a"])
    monkeypatch.setattr(batch_operations, "_after_asset_commit", original)
    document = await contract.db.assets.find_one({"id": aid})
    gid = ObjectId(document["photo_gridfs_ids"][0])
    assert await contract.db.fs.files.count_documents({"_id": gid}) == 1
    route = f"/api/inventory-activities/{activity_id}" if remove_activity else f"/api/assets/bulk-delete/{activity_id}"
    response = await contract.http.delete(route, headers=contract.headers["a"])
    assert response.status_code == 200, response.text
    assert await contract.db.assets.count_documents({"id": aid}) == 0
    assert await contract.db.fs.files.count_documents({"_id": gid}) == 0
    response = await contract.http.post(f"/api/assets/batch-v2/{request['operation_id']}/resume", headers=contract.headers["a"])
    assert response.status_code == 200 and response.json()["applied"] == 1
    assert await contract.db.mutasi_bmn.count_documents({"asset_id": aid}) == 1
