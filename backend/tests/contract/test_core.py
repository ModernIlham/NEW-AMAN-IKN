"""Kontrak transport+otorisasi+Mongo nyata, bukan tiruan operator database."""
import asyncio
import uuid

import pytest
from pymongo.errors import DuplicateKeyError

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def create_asset(contract, letter="a", **changes):
    data = {"asset_code": "31001" + uuid.uuid4().hex[:8], "asset_name": "Meja sintetis",
            "NUP": "1", "category": "Peralatan dan Mesin", "condition": "Baik",
            "activity_id": "contract-activity-" + letter, "purchase_price": "100"}
    data.update(changes)
    return await contract.http.post("/api/assets", json=data, headers=contract.headers[letter])


async def test_bootstrap_login_and_anonymous_gate(contract):
    denied = await contract.http.get("/api/assets")
    assert denied.status_code == 401
    again = await contract.http.post("/api/auth/bootstrap", json={
        "username": "second-root", "password": contract.password,
    }, headers={"X-Admin-Bootstrap-Token": contract.bootstrap})
    assert again.status_code == 409
    login = await contract.http.post("/api/auth/login", json={
        "username": "contract-a", "password": contract.password,
    })
    assert login.status_code == 200 and login.json()["access_token"]


async def test_create_replay_occ_and_tenant_media(contract):
    headers = {**contract.headers["a"], "Idempotency-Key": str(uuid.uuid4())}
    body = {"asset_code": "310-" + uuid.uuid4().hex, "asset_name": "Aset kontrak",
            "category": "Peralatan dan Mesin", "NUP": "1",
            "activity_id": "contract-activity-a", "purchase_price": "100"}
    first = await contract.http.post("/api/assets", json=body, headers=headers)
    assert first.status_code == 200, first.text
    repeated = await contract.http.post("/api/assets", json=body, headers=headers)
    assert repeated.status_code == 200 and first.json()["id"] == repeated.json()["id"]
    identifier = first.json()["id"]
    v = first.json()["version"]
    patch = await contract.http.patch("/api/assets/" + identifier, json={"condition": "Rusak Ringan"},
        headers={**contract.headers["a"], "If-Match": str(v)})
    assert patch.status_code == 200, patch.text
    stale = await contract.http.patch("/api/assets/" + identifier, json={"condition": "Baik"},
        headers={**contract.headers["a"], "If-Match": str(v)})
    assert stale.status_code == 409, stale.text
    forbidden = await contract.http.get("/api/assets/" + identifier, headers=contract.headers["b"])
    assert forbidden.status_code == 403
    listing = await contract.http.get("/api/assets", params={"activity_id": "contract-activity-a"},
                                      headers=contract.headers["a"])
    assert listing.status_code == 200 and identifier in {d["id"] for d in listing.json()["items"]}
    other = await contract.http.get("/api/assets", headers=contract.headers["b"])
    assert identifier not in {d["id"] for d in other.json()["items"]}


async def test_real_unique_index_and_atomic_cas(contract):
    asset = {"id": str(uuid.uuid4()), "asset_code": uuid.uuid4().hex, "NUP": "1",
             "activity_id": "contract-activity-a", "version": 1}
    await contract.db.assets.insert_one(asset)
    with pytest.raises(DuplicateKeyError):
        await contract.db.assets.insert_one({**asset, "_id": "different", "id": str(uuid.uuid4())})
    async def write(value):
        return await contract.db.assets.update_one({"id": asset["id"], "version": 1},
            {"$set": {"notes": value}, "$inc": {"version": 1}})
    results = await asyncio.gather(write("one"), write("two"))
    assert sum(result.matched_count for result in results) == 1
    assert (await contract.db.assets.find_one({"id": asset["id"]}))["version"] == 2


async def test_real_gridfs_byte_roundtrip(contract):
    data = bytes(range(256)) * 2048
    identifier = await contract.fs.upload_from_stream("sintetis.bin", data,
                                                     metadata={"contract": True})
    stream = await contract.fs.open_download_stream(identifier)
    chunks = []
    while chunk := await stream.readchunk():
        chunks.append(chunk)
    assert b"".join(chunks) == data
    await contract.fs.delete(identifier)
    assert await contract.db["fs.chunks"].count_documents({"files_id": identifier}) == 0


async def test_real_redis_generation_invalidation(contract):
    import redis_utils as cache
    if not cache.redis_aktif():
        pytest.fail("AMAN_CONTRACT_REDIS_URL wajib untuk suite kontrak CI")
    ns = "contract-" + uuid.uuid4().hex
    await cache.redis_set(ns, "satker-a", {"total": 1}, 30)
    assert await cache.redis_get(ns, "satker-a") == {"total": 1}
    assert await cache.redis_get(ns, "satker-b") is None
    await cache._bump([ns])
    assert await cache.redis_get(ns, "satker-a") is None
    # Touch only this run's namespace; never FLUSHDB a shared Redis service.
    client = cache._get_client()
    async for key in client.scan_iter(match="aman:*:" + ns + "*"):
        await client.delete(key)
