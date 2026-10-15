"""Real Mongo/GridFS HTTP compatibility and archive roundtrip with storage flag enabled."""
import base64
import asyncio
import copy
import hashlib
import json
import uuid
import zipfile

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jhV8AAAAASUVORK5CYII=")
SIGNED = b"%PDF-1.7\n/ByteRange [0 10 20 30] /Contents <c0ffee>\noriginal signed bytes\n%%EOF"


def inline(raw, kind):
    return "data:" + kind + ";base64," + base64.b64encode(raw).decode()


def payload():
    return {"asset_code": "storage-" + uuid.uuid4().hex, "asset_name": "Checklist storage",
        "NUP": "1", "category": "Storage", "activity_id": "contract-activity-a",
        "document_checklist": [{"name": "STNK", "checked": True,
            "photos": [inline(PNG, "image/png")],
            "documents": [{"name": "signed.pdf", "data": inline(SIGNED, "application/pdf")}]}]}


async def create(contract):
    response = await contract.http.post("/api/assets", headers=contract.headers["a"], json=payload())
    assert response.status_code == 200, response.text
    return response.json()["id"]


async def test_flag_on_all_readers_full_get_old_put_and_sentinel_patch(contract, monkeypatch):
    monkeypatch.setenv("AMAN_CHECKLIST_GRIDFS_WRITE", "1")
    aid = await create(contract)
    asset = await contract.db.assets.find_one({"id": aid})
    first = copy.deepcopy(asset["document_checklist"][0])
    assert first["photos"] == [] and first["documents"][0]["data"] == ""
    assert first["photo_gridfs_ids"] and first["documents"][0]["sha256"] == hashlib.sha256(SIGNED).hexdigest()
    full = await contract.http.get("/api/assets/" + aid, headers=contract.headers["a"])
    assert full.status_code == 200, full.text
    item = full.json()["document_checklist"][0]
    assert base64.b64decode(item["photos"][0].split(",", 1)[1]) == PNG
    assert base64.b64decode(item["documents"][0]["data"].split(",", 1)[1]) == SIGNED
    for endpoint, key in [("?exclude_media=true", "document_checklist"), ("/media", "document_checklist_media"),
                           ("/checklist-full", "document_checklist")]:
        result = await contract.http.get("/api/assets/" + aid + endpoint, headers=contract.headers["a"])
        assert result.status_code == 200, result.text
        assert result.json()[key][0]["photo_count"] == 1
    for path, expected in [("/checklist/0/photos/0", PNG), ("/checklist/0/documents/0", SIGNED),
                            ("/doc-file/0/photo/0", PNG), ("/doc-file/0/document/0", SIGNED)]:
        served = await contract.http.get("/api/assets/" + aid + path, headers=contract.headers["a"])
        assert served.status_code == 200 and served.content == expected
        forbidden = await contract.http.get("/api/assets/" + aid + path, headers=contract.headers["b"])
        assert forbidden.status_code in {403, 404}
    put = {key: value for key, value in full.json().items() if key in payload() or key == "document_checklist"}
    updated = await contract.http.put("/api/assets/" + aid, json=put,
        headers={**contract.headers["a"], "If-Match": "1"})
    assert updated.status_code == 200, updated.text
    saved = await contract.db.assets.find_one({"id": aid})
    assert saved["document_checklist"][0]["id"] == first["id"]
    assert saved["document_checklist"][0]["photo_gridfs_ids"] == first["photo_gridfs_ids"]
    assert saved["document_checklist"][0]["documents"][0]["gridfs_id"] == first["documents"][0]["gridfs_id"]
    patched = await contract.http.patch("/api/assets/" + aid, headers={**contract.headers["a"], "If-Match": "2"},
        json={"document_checklist": [{"id": first["id"], "name": "STNK", "checked": False,
            "photos": ["__existing__:0"], "documents": [{"data": "__existing__:0"}]}]})
    assert patched.status_code == 200, patched.text
    saved = await contract.db.assets.find_one({"id": aid})
    assert saved["version"] == 3 and not saved["document_checklist"][0]["checked"]
    assert saved["document_checklist"][0]["documents"][0]["id"] == first["documents"][0]["id"]


async def test_flag_on_export_photo_links_and_metadata_legacy_shape(contract, monkeypatch):
    monkeypatch.setenv("AMAN_CHECKLIST_GRIDFS_WRITE", "1")
    aid = await create(contract)
    response = await contract.http.get("/api/export/csv", headers=contract.headers["a"],
        params={"activity_id": "contract-activity-a", "category": "Storage", "base_url": "http://contract"})
    assert response.status_code == 200
    assert f"/assets/{aid}/doc-file/0/photo/0" in response.text
    # Malformed old arrays remain writable via a scalar edit and readable;
    # read adaptation must never rewrite the persisted legacy field.
    await contract.db.assets.update_one({"id": aid}, {"$set": {
        "document_checklist": [None, "bad", {"name": "Bad arrays", "photos": "bad", "documents": "bad"}]}})
    for tail in ["", "?exclude_media=true", "/media", "/checklist-full"]:
        response = await contract.http.get("/api/assets/" + aid + tail, headers=contract.headers["a"])
        assert response.status_code == 200, response.text
    changed = await contract.http.patch("/api/assets/" + aid,
        headers={**contract.headers["a"], "If-Match": "1"}, json={"notes": "safe scalar"})
    assert changed.status_code == 200, changed.text
    saved = await contract.db.assets.find_one({"id": aid})
    assert saved["document_checklist"][0] is None


@pytest.mark.parametrize("operation", ["create", "put", "patch"])
async def test_flag_on_commit_then_raise_retains_referenced_checklist_bytes(contract, monkeypatch, operation):
    monkeypatch.setenv("AMAN_CHECKLIST_GRIDFS_WRITE", "1")
    aid = await create(contract)
    import routes.assets as route
    original_db = route.db
    collection = original_db.assets
    body = payload()
    body["document_checklist"][0]["documents"][0]["data"] = inline(SIGNED + b"\nupdated", "application/pdf")
    class Collection:
        def __getattr__(self, name):
            return getattr(collection, name)
        async def update_one(self, query, update, **kw):
            result = await collection.update_one(query, update, **kw)
            if query.get("id") == aid and "document_checklist" in update.get("$set", {}):
                raise IOError("injected acknowledged commit response loss")
            return result
        async def insert_one(self, document, **kw):
            result = await collection.insert_one(document, **kw)
            if operation == "create" and document.get("asset_code") == body["asset_code"]:
                raise IOError("injected acknowledged insert response loss")
            return result
    class Database:
        assets = Collection()
        def __getattr__(self, name):
            return getattr(original_db, name)
        def __getitem__(self, name):
            return original_db[name]
    monkeypatch.setattr(route, "db", Database())
    lease_ids_before = {lease["_id"] async for lease in contract.db.restore_write_leases.find({})}
    if operation == "create":
        result = await contract.http.post("/api/assets", headers=contract.headers["a"], json=body)
        committed = await collection.find_one({"asset_code": body["asset_code"]})
        aid = committed["id"]
    elif operation == "put":
        result = await contract.http.put("/api/assets/" + aid,
            headers={**contract.headers["a"], "If-Match": "1"}, json=body)
    else:
        result = await contract.http.patch("/api/assets/" + aid, headers={**contract.headers["a"], "If-Match": "1"},
            json={"document_checklist": body["document_checklist"]})
    assert result.status_code == 500, result.text
    saved = await collection.find_one({"id": aid})
    assert saved["version"] == (1 if operation == "create" else 2)
    served = await contract.http.get("/api/assets/" + aid + "/checklist/0/documents/0", headers=contract.headers["a"])
    assert served.status_code == 200 and served.content == SIGNED + b"\nupdated"
    leases = [lease async for lease in contract.db.restore_write_leases.find({})
              if lease["_id"] not in lease_ids_before]
    assert len(leases) == 1 and leases[0]["status"] == "uncertain_write"
    # This fixture's simulated server write has synchronously completed before
    # the injected error, and its persisted version/bytes were verified above.
    # Release only that known request, preserving every pre-existing admission.
    await contract.db.restore_write_leases.delete_one({"_id": leases[0]["_id"]})


@pytest.mark.parametrize("fault", ["none", "cas_miss", "lost_reply", "delayed_commit"])
async def test_batch_refs_only_append_preserves_originals_and_replay_proof(contract, monkeypatch, fault):
    monkeypatch.setenv("AMAN_CHECKLIST_GRIDFS_WRITE", "1")
    aid = await create(contract)
    import batch_operations as batch
    first = await contract.db.assets.find_one({"id": aid})
    original_photo = first["document_checklist"][0]["photo_gridfs_ids"][0]
    original_pdf = first["document_checklist"][0]["documents"][0]["gridfs_id"]
    preflight = await contract.http.post("/api/assets/batch-v2/preflight", json={"asset_ids": [aid]},
                                        headers=contract.headers["a"])
    assert preflight.status_code == 200
    operation = f"b2_{int(batch.now_utc().timestamp() * 1000)}_{uuid.uuid4()}"
    request = {"operation_id": operation, "asset_ids": [aid],
        "expected_versions": {aid: 1}, "dataset_generation": preflight.json()["dataset_generation"],
        "updates": {"location": "Batch checklist", "document_checklist_items": [
            {"name": "STNK", "checked": False, "photos": [inline(PNG, "image/png")]},
            {"name": "NEWITEM", "checked": True, "documents": [
                {"name": "new-signed.pdf", "data": inline(SIGNED + b"\nnew", "application/pdf")}]}]}}
    original_changes = batch._asset_changes
    original_db = batch.db
    delayed = []
    release_commit = asyncio.Event()
    if fault == "cas_miss":
        async def race(snapshot, *args):
            changes = await original_changes(snapshot, *args)
            await contract.db.assets.update_one({"id": aid}, {
                "$inc": {"version": 1}, "$set": {"notes": "concurrent"}})
            return changes
        monkeypatch.setattr(batch, "_asset_changes", race)
    elif fault in {"lost_reply", "delayed_commit"}:
        collection = original_db.assets
        raised = []
        class Collection:
            def __getattr__(self, name):
                return getattr(collection, name)
            async def update_one(self, query, update, **kw):
                if not raised and fault == "delayed_commit" and batch.MARKERS in update.get("$set", {}):
                    raised.append(True)
                    async def complete_later():
                        await release_commit.wait()
                        return await collection.update_one(query, update, **kw)
                    delayed.append(asyncio.create_task(complete_later()))
                    raise IOError("injected write still in flight with unknown outcome")
                result = await collection.update_one(query, update, **kw)
                if not raised and batch.MARKERS in update.get("$set", {}):
                    raised.append(True)
                    raise IOError("injected batch acknowledged response loss")
                return result
        class Database:
            assets = Collection()
            def __getattr__(self, name):
                return getattr(original_db, name)
            def __getitem__(self, name):
                return original_db[name]
        monkeypatch.setattr(batch, "db", Database())
    files_before = await contract.db["fs.files"].count_documents({})
    lease_ids_before = {lease["_id"] async for lease in contract.db.restore_write_leases.find({})}
    result = await contract.http.put("/api/assets/batch-v2", headers=contract.headers["a"], json=request)
    assert result.status_code == 200, result.text
    if fault == "delayed_commit":
        from routes.backup import _wait_writer_drain
        uncertainty = [lease async for lease in contract.db.restore_write_leases.find({})
                       if lease["_id"] not in lease_ids_before]
        assert len(uncertainty) == 1 and uncertainty[0]["status"] == "uncertain_write"
        assert uncertainty[0]["uncertainty_reason"] == "batch_asset"
        with pytest.raises(RuntimeError):
            await _wait_writer_drain(timeout=0.01)
        assert result.json()["applied"] == 0
        assert (await contract.db.assets.find_one({"id": aid}))["version"] == 1
        assert await contract.db["fs.files"].count_documents({}) > files_before
        release_commit.set()
        assert (await delayed[0]).matched_count == 1
        result = await contract.http.post(f"/api/assets/batch-v2/{operation}/resume", headers=contract.headers["a"])
        assert result.status_code == 200, result.text
    saved = await contract.db.assets.find_one({"id": aid})
    first_item = saved["document_checklist"][0]
    assert first_item["photo_gridfs_ids"][0] == original_photo
    assert first_item["documents"][0]["gridfs_id"] == original_pdf
    if fault == "cas_miss":
        assert result.json()["conflicts"] == 1 and result.json()["applied"] == 0
        assert saved["notes"] == "concurrent" and len(first_item["photo_gridfs_ids"]) == 1
        assert await contract.db["fs.files"].count_documents({}) == files_before
        assert {lease["_id"] async for lease in contract.db.restore_write_leases.find({})} == lease_ids_before
    else:
        assert result.json()["applied"] == 1 and saved["version"] == 2
        assert saved["location"] == "Batch checklist" and len(first_item["photo_gridfs_ids"]) == 2
        assert first_item["id"] == first["document_checklist"][0]["id"]
        assert first_item["photos"] == []
        proof_ids = [marker["operation_id"] for marker in saved[batch.MARKERS]]
        assert proof_ids == [operation]
        files_after = await contract.db["fs.files"].count_documents({})
        resumed = await contract.http.post(f"/api/assets/batch-v2/{operation}/resume", headers=contract.headers["a"])
        assert resumed.status_code == 200 and resumed.json()["applied"] == 1
        again = await contract.db.assets.find_one({"id": aid})
        assert again["version"] == 2 and again["document_checklist"] == saved["document_checklist"]
        assert await contract.db["fs.files"].count_documents({}) == files_after
    for path, expected in [("/checklist/0/photos/0", PNG), ("/checklist/0/documents/0", SIGNED)]:
        served = await contract.http.get("/api/assets/" + aid + path, headers=contract.headers["a"])
        assert served.status_code == 200 and served.content == expected
    if fault == "delayed_commit":
        # Explicit test-operator release only after awaiting the known Mongo
        # operation and verifying its exact persisted proof/media outcome.
        await contract.db.restore_write_leases.delete_one({"_id": uncertainty[0]["_id"]})


async def test_backfill_unknown_dispatched_write_retains_bytes_until_late_cas_completes(contract, monkeypatch):
    monkeypatch.setenv("AMAN_CHECKLIST_GRIDFS_WRITE", "0")
    aid = await create(contract)
    from checklist_storage import backfill_asset
    original_db = contract.db
    collection = original_db.assets
    release = asyncio.Event()
    pending = []
    class Collection:
        def __getattr__(self, name):
            return getattr(collection, name)
        async def update_one(self, query, update, **kw):
            if "document_checklist" in update.get("$set", {}):
                async def complete_later():
                    await release.wait()
                    return await collection.update_one(query, update, **kw)
                pending.append(asyncio.create_task(complete_later()))
                raise IOError("injected backfill Mongo operation still in flight")
            return await collection.update_one(query, update, **kw)
    class Database:
        assets = Collection()
        def __getattr__(self, name):
            return getattr(original_db, name)
        def __getitem__(self, name):
            return original_db[name]
    before = await contract.db["fs.files"].count_documents({})
    lease_ids_before = {lease["_id"] async for lease in contract.db.restore_write_leases.find({})}
    with pytest.raises(IOError):
        await backfill_asset(Database(), contract.fs, aid, dry_run=False)
    assert (await collection.find_one({"id": aid}))["version"] == 1
    assert await contract.db["fs.files"].count_documents({}) == before + 2
    uncertainty = [lease async for lease in contract.db.restore_write_leases.find({})
                   if lease["_id"] not in lease_ids_before]
    assert len(uncertainty) == 1 and uncertainty[0]["uncertainty_reason"] == "checklist_backfill"
    from routes.backup import _wait_writer_drain
    with pytest.raises(RuntimeError):
        await _wait_writer_drain(timeout=0.01)
    release.set()
    assert (await pending[0]).matched_count == 1
    saved = await collection.find_one({"id": aid})
    assert saved["version"] == 2 and saved["document_checklist"][0]["photos"]
    served = await contract.http.get("/api/assets/" + aid + "/checklist/0/documents/0", headers=contract.headers["a"])
    assert served.status_code == 200 and served.content == SIGNED
    await contract.db.restore_write_leases.delete_one({"_id": uncertainty[0]["_id"]})


async def test_signed_media_actual_archive_export_import_hash_roundtrip(contract, monkeypatch, tmp_path):
    monkeypatch.setenv("AMAN_CHECKLIST_GRIDFS_WRITE", "1")
    aid = await create(contract)
    import routes.backup as backup
    from backup_archive import write_manifest, validate_archive
    from checklist_storage import read_media
    from motor.motor_asyncio import AsyncIOMotorGridFSBucket
    archive = tmp_path / "roundtrip.zip"
    columns = await backup._app_collections()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        stats = {name: await backup._tulis_koleksi_json(zf, name, name in backup.KEEP_ID_COLLECTIONS)
                 for name in columns}
        count = await backup.export_gridfs(zf)
        zf.writestr("metadata.json", json.dumps({"archive_schema_version": 1}))
        write_manifest(zf, stats, count, 0)
    target = contract.db.client["aman_ci_checklist_restore_" + uuid.uuid4().hex]
    bucket = AsyncIOMotorGridFSBucket(target)
    try:
        monkeypatch.setattr(backup, "db", target)
        monkeypatch.setattr(backup, "fs_bucket", bucket)
        with zipfile.ZipFile(archive) as zf:
            preflight = validate_archive(zf)
            assert preflight["collections"]["assets"] >= 1
            assert await backup.import_gridfs(zf) == count
            assets = json.loads(zf.read("assets.json"))
            asset = next(row for row in assets if row["id"] == aid)
        raw, _, _ = await read_media(asset, 0, 0, "document", target, bucket)
        assert raw == SIGNED
        raw, _, _ = await read_media(asset, 0, 0, "photo", target, bucket)
        assert raw == PNG
        for restored in assets:
            checklist = restored.get("document_checklist")
            for index, item in enumerate(checklist if isinstance(checklist, list) else []):
                if isinstance(item, dict) and item.get("name") == "NEWITEM":
                    raw, _, _ = await read_media(restored, index, 0, "document", target, bucket)
                    assert raw == SIGNED + b"\nnew"
    finally:
        await contract.db.client.drop_database(target.name)
