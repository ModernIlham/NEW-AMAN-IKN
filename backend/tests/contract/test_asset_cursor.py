"""Real Mongo keyset parity, null/ties, owner/context/epoch and mutable rows."""
import uuid

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]


@pytest.mark.parametrize("sort,direction", [("newest", -1), ("oldest", 1), ("unknown-sort", -1)])
async def test_cursor_matches_page_order_with_null_missing_and_ties(contract, sort, direction):
    category = "cursor-" + uuid.uuid4().hex
    rows = []
    for i in range(31):
        row = {"id": f"{category}-{i:03}", "asset_code": category, "NUP": str(i),
            "activity_id": "contract-activity-a", "category": category, "asset_name": "Cursor", "purchase_price": "10"}
        if i >= 7:
            row["created_at"] = None if i < 10 else "2026-01-01" if i < 20 else "2026-01-02"
        rows.append(row)
    await contract.db.assets.insert_many(rows)
    await contract.db.assets.insert_one({"id": category + "-foreign", "asset_code": category, "NUP": "1",
        "activity_id": "contract-activity-b", "category": category})
    expected = [doc["id"] async for doc in contract.db.assets.find({"category": category,
        "activity_id": "contract-activity-a"}, {"_id": 0, "id": 1}).sort([("created_at", direction), ("id", 1)])]
    cursor, received, page = "", [], 1
    while True:
        result = await contract.http.get("/api/assets", headers=contract.headers["a"], params={
            "category": category, "sort_by": sort, "page_size": 10, "pagination": "cursor", "cursor": cursor})
        assert result.status_code == 200, result.text
        body = result.json()
        assert body["total"] == 31 and body["page"] == page
        assert body["consistency"] == "mutable_dataset"
        received.extend(doc["id"] for doc in body["items"])
        cursor = body["next_cursor"]
        if not cursor:
            break
        page += 1
        assert page < 10
    assert received == expected and len(set(received)) == 31


async def test_cursor_context_expiry_forgery_and_epoch_are_explicit(contract):
    category = "cursor-context-" + uuid.uuid4().hex
    await contract.db.assets.insert_many([{"id": f"{category}-{i:03}", "asset_code": category,
        "NUP": str(i), "activity_id": "contract-activity-a", "category": category,
        "created_at": "2026-01-01", "purchase_price": "10"} for i in range(11)])
    params = {"category": category, "pagination": "cursor", "page_size": 10}
    first = await contract.http.get("/api/assets", headers=contract.headers["a"], params=params)
    assert first.status_code == 200, first.text
    token = first.json()["next_cursor"]
    for changes, headers, expected in [({"cursor": "not-a-token"}, contract.headers["a"], 400),
        ({"cursor": "a" * 2049}, contract.headers["a"], 400),
        ({"cursor": token, "category": "different"}, contract.headers["a"], 409),
        ({"cursor": token, "page_size": 11}, contract.headers["a"], 409),
        ({"cursor": token, "sort_by": "oldest"}, contract.headers["a"], 409),
        ({"cursor": token}, contract.headers["b"], 409)]:
        response = await contract.http.get("/api/assets", headers=headers, params={**params, **changes})
        assert response.status_code == expected, response.text
    # Cursor anchor need not remain in Mongo; deleting it doesn't skip following rows.
    await contract.db.assets.delete_one({"id": first.json()["items"][-1]["id"]})
    continuation = await contract.http.get("/api/assets", headers=contract.headers["a"], params={**params, "cursor": token})
    assert continuation.status_code == 200 and len(continuation.json()["items"]) == 1
    from dataset_epoch import rotate_generation
    await rotate_generation(contract.db, "contract-cursor-restore")
    stale = await contract.http.get("/api/assets", headers=contract.headers["a"], params={**params, "cursor": token})
    assert stale.status_code == 409
    # Signed wrong-purpose/expired tokens cannot become cursor or bearer tokens.
    import jwt
    from auth_utils import JWT_SECRET
    expired = jwt.encode({"purpose": "asset-list-cursor", "version": 1, "exp": 1}, JWT_SECRET, algorithm="HS256")
    response = await contract.http.get("/api/assets", headers=contract.headers["a"], params={**params, "cursor": expired})
    assert response.status_code == 409
    bearer = await contract.http.get("/api/assets", headers={"Authorization": "Bearer " + token})
    assert bearer.status_code == 401


async def test_cursor_refuses_unsupported_type_without_affecting_page_api(contract):
    category = "cursor-types-" + uuid.uuid4().hex
    await contract.db.assets.insert_one({"id": category, "asset_code": category, "NUP": "1",
        "activity_id": "contract-activity-a", "category": category, "created_at": 123})
    regular = await contract.http.get("/api/assets", headers=contract.headers["a"], params={"category": category})
    assert regular.status_code == 200
    cursor = await contract.http.get("/api/assets", headers=contract.headers["a"], params={"category": category, "pagination": "cursor"})
    assert cursor.status_code == 400
    unsupported_sort = await contract.http.get("/api/assets", headers=contract.headers["a"], params={"category": category,
        "pagination": "cursor", "sort_by": "price_asc"})
    assert unsupported_sort.status_code == 400


async def test_cursor_changes_between_pages_follow_mutable_dataset_contract(contract):
    category = "cursor-mutable-" + uuid.uuid4().hex
    rows = [{"id": f"{category}-{i:03}", "asset_code": category, "NUP": str(i),
        "activity_id": "contract-activity-a", "category": category,
        "created_at": "2026-01-02" if i < 10 else "2026-01-01"} for i in range(11)]
    await contract.db.assets.insert_many(rows)
    params = {"category": category, "pagination": "cursor", "page_size": 10}
    first = await contract.http.get("/api/assets", headers=contract.headers["a"], params=params)
    assert first.status_code == 200, first.text
    first_ids = [row["id"] for row in first.json()["items"]]
    # Newer inserts precede this cursor; older ones can appear after it. A seen
    # row moved across the anchor can repeat: clients must dedup/reconcile.
    template = {key: value for key, value in rows[0].items() if key != "_id"}
    await contract.db.assets.insert_many([
        {**template, "id": category + "-new-ahead", "NUP": "ahead", "created_at": "2026-01-03"},
        {**template, "id": category + "-new-behind", "NUP": "behind", "created_at": "2025-01-01"}])
    await contract.db.assets.update_one({"id": first_ids[0]}, {"$set": {"created_at": "2024-01-01"}})
    second = await contract.http.get("/api/assets", headers=contract.headers["a"], params={
        **params, "cursor": first.json()["next_cursor"]})
    assert second.status_code == 200, second.text
    ids = {row["id"] for row in second.json()["items"]}
    assert second.json()["consistency"] == "mutable_dataset"
    assert category + "-new-ahead" not in ids
    assert category + "-new-behind" in ids and first_ids[0] in ids


async def test_psp_page_enrichment_keeps_latest_scoped_official_decision(contract):
    category = "cursor-psp-" + uuid.uuid4().hex
    asset_id = category + "-asset"
    await contract.db.assets.insert_one({"id": asset_id, "asset_code": category, "NUP": "1",
        "activity_id": "contract-activity-a", "category": category,
        "siman": {"referensi": {"no_psp": "SIMAN-FALLBACK"}}})
    await contract.db.psp.insert_many([
        {"id": category + "-old", "kode_satker": "99000a", "nomor_sk": "OLD",
         "tanggal_sk": "2025-01-01", "aset": [{"asset_id": asset_id}]},
        {"id": category + "-latest", "kode_satker": "99000a", "nomor_sk": "LATEST",
         "tanggal_sk": "2026-01-01", "status_pengajuan": "ditetapkan",
         "aset": [{"asset_id": asset_id}] + [{"asset_id": f"unrelated-{i}"} for i in range(1000)]},
        {"id": category + "-draft", "kode_satker": "99000a", "nomor_sk": "DRAFT",
         "tanggal_sk": "2027-01-01", "status_pengajuan": "draf", "aset": [{"asset_id": asset_id}]},
        {"id": category + "-foreign", "kode_satker": "99000b", "nomor_sk": "FOREIGN",
         "tanggal_sk": "2028-01-01", "aset": [{"asset_id": asset_id}]}])
    response = await contract.http.get("/api/assets", headers=contract.headers["a"], params={"category": category})
    assert response.status_code == 200, response.text
    assert response.json()["items"][0]["psp"]["no_psp"] == "LATEST"
