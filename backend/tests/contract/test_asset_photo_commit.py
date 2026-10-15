"""Actual GridFS bytes survive Mongo commit replies lost on all single writers."""
import asyncio
import base64
import uuid

import pytest
from bson import ObjectId
from pymongo.errors import AutoReconnect
from pymongo.results import UpdateResult

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]
PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jhV8AAAAASUVORK5CYII="


def payload():
    return {"asset_code": "commit-" + uuid.uuid4().hex, "NUP": "1", "asset_name": "Commit proof",
            "category": "Photo commit", "activity_id": "contract-activity-a", "photos": [PNG]}


async def raw(bucket, gid):
    stream = await bucket.open_download_stream(ObjectId(gid))
    return await stream.read()


class AssetFault:
    def __init__(self, contract, mode, target):
        self.contract, self.mode, self.target = contract, mode, target
        self.real = contract.db.assets
        self.fired, self.bytes = False, {}
        self.release, self.pending = asyncio.Event(), None

    def __getattr__(self, name):
        return getattr(self.real, name)

    async def capture(self, document):
        for gid in document.get("photo_gridfs_ids", []):
            self.bytes[gid] = await raw(self.contract.fs, gid)

    async def insert_one(self, document, *args, **kwargs):
        if self.mode in {"create", "delayed_create", "cancelled_create"} and document.get("asset_code") == self.target and not self.fired:
            self.fired = True
            await self.capture(document)
            if self.mode in {"delayed_create", "cancelled_create"}:
                async def finish():
                    await self.release.wait()
                    return await self.real.insert_one(document, *args, **kwargs)
                self.pending = asyncio.create_task(finish())
                if self.mode == "cancelled_create":
                    raise asyncio.CancelledError()
                raise AutoReconnect("injected reply lost while server write remains in flight")
            await self.real.insert_one(document, *args, **kwargs)
            raise AutoReconnect("injected commit reply lost")
        return await self.real.insert_one(document, *args, **kwargs)

    async def update_one(self, query, changes, *args, **kwargs):
        if query.get("id") == self.target and "$inc" in changes and not self.fired:
            self.fired = True
            await self.capture(changes.get("$set", {}))
            if self.mode == "cas_miss":
                await self.real.update_one({"id": self.target}, {"$inc": {"version": 1}})
                return UpdateResult({"n": 0, "nModified": 0, "ok": 1}, True)
            if self.mode in {"delayed", "cancelled"}:
                async def finish():
                    await self.release.wait()
                    return await self.real.update_one(query, changes, *args, **kwargs)
                self.pending = asyncio.create_task(finish())
                if self.mode == "cancelled":
                    raise asyncio.CancelledError()
                raise AutoReconnect("injected reply lost while server CAS remains in flight")
            await self.real.update_one(query, changes, *args, **kwargs)
            raise AutoReconnect("injected commit reply lost")
        return await self.real.update_one(query, changes, *args, **kwargs)


class DatabaseFault:
    def __init__(self, database, assets):
        self.database, self.assets = database, assets

    def __getattr__(self, name):
        return getattr(self.database, name)

    def __getitem__(self, name):
        return self.assets if name == "assets" else self.database[name]


@pytest.mark.parametrize("method", ["create", "put", "patch"])
@pytest.mark.parametrize("timing", ["visible", "pending", "cancelled"])
async def test_commit_reply_lost_preserves_new_references_and_full_bytes(contract, monkeypatch, method, timing):
    from routes import assets as routes
    data = payload()
    old_ids = []
    if method != "create":
        initial = await contract.http.post("/api/assets", headers=contract.headers["a"], json=data)
        assert initial.status_code == 200, initial.text
        aid = initial.json()["id"]
        old_ids = (await contract.db.assets.find_one({"id": aid}))["photo_gridfs_ids"]
    mode = ("cancelled_create" if method == "create" else "cancelled") if timing == "cancelled" else (
        ("delayed_create" if method == "create" else "delayed") if timing == "pending" else ("create" if method == "create" else "lost"))
    lease_ids_before = {row["_id"] async for row in contract.db.restore_write_leases.find({}, {"_id": 1})}
    fault = AssetFault(contract, mode, data["asset_code"] if method == "create" else aid)
    async def perform():
        with monkeypatch.context() as patch:
            patch.setattr(routes, "db", DatabaseFault(contract.db, fault))
            if method == "create":
                return await contract.http.post("/api/assets", headers=contract.headers["a"], json=data)
            if method == "put":
                return await contract.http.put("/api/assets/" + aid, headers={**contract.headers["a"], "If-Match": "1"}, json=data)
            return await contract.http.patch("/api/assets/" + aid, headers={**contract.headers["a"], "If-Match": "1"}, json={
                "photo_ops": {"keep": [], "add": [PNG], "base_version": 1}})
    if timing == "cancelled":
        with pytest.raises(asyncio.CancelledError):
            await perform()
        assert fault.fired
    else:
        result = await perform()
        assert fault.fired and result.status_code == 500, result.text
    if fault.pending is not None:
        # At this point no reference to the new ID is visible. It still MUST
        # survive, because the original server write can finish after timeout.
        try:
            for gid, expected in fault.bytes.items():
                assert await raw(contract.fs, gid) == expected
        finally:
            fault.release.set()
            await fault.pending
    document = await contract.db.assets.find_one({"asset_code": data["asset_code"]})
    aid = document["id"]
    assert document["photo_gridfs_ids"] and set(document["photo_gridfs_ids"]) == set(fault.bytes)
    full = await contract.http.get("/api/assets/" + aid, headers=contract.headers["a"])
    assert full.status_code == 200, full.text
    decoded = [base64.b64decode(value.split(",", 1)[1]) for value in full.json()["photos"]]
    assert decoded == [fault.bytes[gid] for gid in document["photo_gridfs_ids"]]
    for gid, expected in fault.bytes.items():
        assert await raw(contract.fs, gid) == expected
        record = await contract.db["fs.files"].find_one({"_id": ObjectId(gid)})
        proof = record["metadata"]["asset_photo_commit"]
        assert proof["owner_asset_id"] == aid and proof["state"] == "pending"
    for gid in old_ids:
        assert await raw(contract.fs, gid)  # Old media is not removed before acknowledgement.
    leases = [row async for row in contract.db.restore_write_leases.find({"_id": {"$nin": list(lease_ids_before)}})]
    assert len(leases) == 1 and leases[0]["status"] == "uncertain_write"
    assert leases[0]["uncertainty_reason"] == {"create": "asset_create", "put": "asset_put", "patch": "asset_patch"}[method]
    # The injected server future has positively finished above; remove only
    # this synthetic request lease to keep the shared fixture isolated.
    await contract.db.restore_write_leases.delete_one({"_id": leases[0]["_id"]})


@pytest.mark.parametrize("method", ["put", "patch"])
async def test_cas_miss_removes_only_new_unreferenced_photos(contract, monkeypatch, method):
    from routes import assets as routes
    data = payload()
    created = await contract.http.post("/api/assets", headers=contract.headers["a"], json=data)
    assert created.status_code == 200, created.text
    aid = created.json()["id"]
    old = await contract.db.assets.find_one({"id": aid})
    before = await contract.db["fs.files"].count_documents({})
    fault = AssetFault(contract, "cas_miss", aid)
    with monkeypatch.context() as patch:
        patch.setattr(routes, "db", DatabaseFault(contract.db, fault))
        if method == "put":
            response = await contract.http.put("/api/assets/" + aid, headers=contract.headers["a"], json=data)
        else:
            response = await contract.http.patch("/api/assets/" + aid, headers=contract.headers["a"], json={
                "photo_ops": {"keep": [], "add": [PNG], "base_version": 1}})
    assert response.status_code == 409 and fault.fired, response.text
    current = await contract.db.assets.find_one({"id": aid})
    assert current["photo_gridfs_ids"] == old["photo_gridfs_ids"]
    assert await contract.db["fs.files"].count_documents({}) == before
    for gid in fault.bytes:
        assert not await contract.db["fs.files"].find_one({"_id": ObjectId(gid)})
    for gid in old["photo_gridfs_ids"]:
        assert await raw(contract.fs, gid)


async def test_cleanup_unknown_database_or_wrong_owner_keeps_pending_ledger(contract):
    from asset_photo_commit import register_photos, discard_uncommitted_photos
    gid = await contract.fs.upload_from_stream("pending-photo", b"synthetic-original")
    await register_photos(contract.db, "expected-owner", [str(gid)])
    await discard_uncommitted_photos(contract.db, contract.fs, "wrong-owner", [str(gid)])
    assert await raw(contract.fs, str(gid)) == b"synthetic-original"
    class UnknownAssets:
        async def find_one(self, *args, **kwargs):
            raise AutoReconnect("injected unavailable cleanup proof")
    await discard_uncommitted_photos(DatabaseFault(contract.db, UnknownAssets()), contract.fs, "expected-owner", [str(gid)])
    assert await raw(contract.fs, str(gid)) == b"synthetic-original"
    record = await contract.db["fs.files"].find_one({"_id": gid})
    assert record["metadata"]["asset_photo_commit"]["state"] == "pending"
    await discard_uncommitted_photos(contract.db, contract.fs, "expected-owner", [str(gid)])
    assert not await contract.db["fs.files"].find_one({"_id": gid})


async def test_patch_precommit_checklist_failure_compensates_registered_main_photo(contract, monkeypatch):
    from routes import assets as routes
    data = payload()
    created = await contract.http.post("/api/assets", headers=contract.headers["a"], json=data)
    assert created.status_code == 200, created.text
    aid = created.json()["id"]
    before = await contract.db["fs.files"].count_documents({})
    async def fail_checklist(*args, **kwargs):
        from fastapi import HTTPException
        raise HTTPException(503, "injected owned checklist read failure")
    with monkeypatch.context() as patch:
        patch.setattr(routes, "prepare_checklist", fail_checklist)
        response = await contract.http.patch("/api/assets/" + aid, headers=contract.headers["a"], json={
            "photo_ops": {"keep": [0], "add": [PNG]}, "document_checklist": [{"name": "STNK"}]})
    assert response.status_code == 503, response.text
    assert await contract.db["fs.files"].count_documents({}) == before
    full = await contract.http.get("/api/assets/" + aid, headers=contract.headers["a"])
    assert full.status_code == 200 and len(full.json()["photos"]) == 1
