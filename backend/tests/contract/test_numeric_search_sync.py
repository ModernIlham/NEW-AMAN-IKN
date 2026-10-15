"""Numeric price, tombstone boundaries and Meili recovery on actual Mongo."""
from decimal import Decimal
from types import SimpleNamespace

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]


async def test_numeric_prices_match_pdf_helper_and_exact_bounds(contract):
    from asset_sorting import tahapan_urutan_aset, urutkan_harga_aset
    rows = [{"id": "opt11-" + key, "asset_code": "opt11-" + key, "NUP": "1", "purchase_price": value,
             "activity_id": "contract-activity-a", "category": "OPT11"}
            for key, value in [("negative", "-1"), ("zero", 0), ("empty", ""),
                ("null", None), ("invalid", "abc"), ("two", "2"), ("ten", 10),
                ("hundred", "100"), ("a-tie", "10.00"),
                ("large1", "9007199254740992.01"), ("large2", "9007199254740992.02"),
                ("invalid35", "12345678901234567890123456789012345"),
                ("subnormal-invalid", "1.1e-6176"), ("valid34", "1234567890123456789012345678901234"),
                ("upper-invalid", "1e6145"), ("valid-trailing", "10000000000000000000000000000000000")]]
    await contract.db.assets.insert_many(rows)
    for direction in ("price_asc", "price_desc"):
        mongo = await contract.db.assets.aggregate([
            {"$match": {"category": "OPT11"}}, *tahapan_urutan_aset(direction),
        ]).to_list(100)
        pdf = urutkan_harga_aset(list(rows), direction)
        assert [r["id"] for r in mongo] == [r["id"] for r in pdf]
        response = await contract.http.get("/api/assets", headers=contract.headers["a"], params={
            "category": "OPT11", "sort_by": direction, "page_size": 50,
        })
        assert response.status_code == 200, response.text
        assert [r["id"] for r in response.json()["items"]] == [r["id"] for r in pdf]
    response = await contract.http.get("/api/assets", headers=contract.headers["a"], params={
        "category": "OPT11", "price_min": "9007199254740992.02", "price_max": "9007199254740992.02",
    })
    assert response.status_code == 200, response.text
    assert [r["id"] for r in response.json()["items"]] == ["opt11-large2"]
    zero = await contract.http.get("/api/assets", headers=contract.headers["a"], params={
        "category": "OPT11", "price_min": "0", "price_max": "0",
    })
    assert zero.status_code == 200, zero.text
    assert {r["id"] for r in zero.json()["items"]} == {"opt11-zero", "opt11-empty", "opt11-null", "opt11-invalid", "opt11-invalid35", "opt11-subnormal-invalid", "opt11-upper-invalid"}
    invalid = await contract.http.get("/api/assets", headers=contract.headers["a"], params={"price_min": "10", "price_max": "0"})
    assert invalid.status_code == 400


@pytest.mark.parametrize("count,overflow", [(9999, False), (10000, False), (10001, True)])
async def test_tombstones_never_truncate_silently(contract, count, overflow):
    activity = f"opt27-{count}"
    await contract.db.inventory_activities.insert_one({"id": activity, "kode_satker": "99000a"})
    await contract.db.audit_logs.insert_many([{"action": "delete", "activity_id": activity,
        "asset_id": f"opt27-{i}", "timestamp": "2026-10-15T01:00:00+00:00"} for i in range(count)])
    # A foreign activity's deletes must not trigger full refresh in this one.
    await contract.db.audit_logs.insert_one({"action": "bulk_delete", "activity_id": "contract-activity-b",
        "timestamp": "2026-10-15T01:00:00+00:00"})
    result = await contract.http.get("/api/assets/offline-snapshot", headers=contract.headers["a"], params={
        "activity_id": activity, "since": "2026-10-15T00:00:00+00:00",
    })
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["requires_full_refresh"] is overflow
    assert len(body["deleted_ids"]) == (0 if overflow else count)


class SearchEngine:
    def __init__(self):
        self.docs, self.tasks = {}, {}
        self.fail_next = False

    async def request(self, method, path, *, json=None, params=None):
        if path.startswith("/tasks/"):
            task = self.tasks[int(path.split("/")[-1])]
            if task["status"] == "succeeded":
                action, payload = task["apply"]
                if action == "upsert":
                    self.docs.update({doc["id"]: dict(doc) for doc in payload})
                elif action == "delete":
                    for did in payload:
                        self.docs.pop(did, None)
            return SimpleNamespace(json=lambda: {"status": task["status"]})
        if method == "GET" and path.endswith("/documents"):
            documents = [{"id": did} for did in sorted(self.docs)]
            offset, limit = params["offset"], params["limit"]
            return SimpleNamespace(json=lambda: {"results": documents[offset:offset + limit]})
        if method in {"PUT", "POST"}:
            tid = len(self.tasks) + 1
            self.tasks[tid] = {"status": "failed" if self.fail_next else "succeeded",
                               "apply": ("delete" if path.endswith("delete-batch") else "upsert", json)}
            self.fail_next = False
            return SimpleNamespace(json=lambda: {"taskUid": tid})
        raise AssertionError((method, path))


@pytest.mark.parametrize("count", [2001, 4001])
async def test_meili_composite_cursor_ack_lease_and_deletion(contract, monkeypatch, count):
    import meili_utils as m
    monkeypatch.setattr(m, "meili_aktif", lambda: True)
    monkeypatch.setattr(m, "INDEKS", {"assets": m.INDEKS["assets"]})
    engine = SearchEngine()
    monkeypatch.setattr(m, "_req", engine.request)
    monkeypatch.setattr(m, "_MONGO_COL", {"assets": "opt14_assets"})
    source = contract.db.opt14_assets
    await source.delete_many({})
    await source.create_index([("updated_at", 1), ("id", 1)], name="updated_at_1_id_1")
    await contract.db.meili_sync_state.delete_one({"_id": "assets"})
    timestamp = "2026-10-15T03:00:00+00:00"
    await source.insert_many([{"id": f"opt14-{i:05}", "asset_code": f"opt14-{i:05}", "NUP": "1", "updated_at": timestamp,
        "asset_name": "Indexed", "activity_id": "contract-activity-a"} for i in range(count)])
    plan = await contract.db.command("explain", {"find": "opt14_assets",
        "filter": {"updated_at": {"$gt": ""}}, "sort": {"updated_at": 1, "id": 1}, "limit": 2000}, verbosity="executionStats")
    assert "updated_at_1_id_1" in str(plan["queryPlanner"]["winningPlan"])
    assert plan["executionStats"]["totalDocsExamined"] <= 2000
    # Legacy timestamp-only watermark is unsafe; restart a bounded cycle.
    await contract.db.meili_sync_state.insert_one({"_id": "assets", "sejak": timestamp})
    await m.selaraskan_inkremental()  # migrate + legacy phase
    engine.fail_next = True
    await m.selaraskan_inkremental()  # submission HTTP succeeds, task fails
    state = await contract.db.meili_sync_state.find_one({"_id": "assets"})
    assert state["last_id"] == "" and not engine.docs
    await m.selaraskan_inkremental()
    state = await contract.db.meili_sync_state.find_one({"_id": "assets"})
    assert state["last_id"] == "opt14-01999" and state["sejak"] == timestamp
    # A second worker cannot steal an unexpired lease or regress a checkpoint.
    lease = await m._claim("assets")
    assert lease and await m._claim("assets") is None
    from datetime import datetime, timedelta, timezone
    await contract.db.meili_sync_state.update_one({"_id": "assets"}, {"$set": {"lease_until": datetime.now(timezone.utc) - timedelta(seconds=1)}})
    replacement = await m._claim("assets")
    assert replacement["owner"] != lease["owner"]
    with pytest.raises(RuntimeError, match="lease lost"):
        await m._checkpoint("assets", lease, {"last_id": "wrong"})
    await m._release("assets", lease)
    assert (await contract.db.meili_sync_state.find_one({"_id": "assets"}))["owner"] == replacement["owner"]
    await m._release("assets", replacement)
    for _ in range(8):
        await m.selaraskan_inkremental()
    assert len(engine.docs) == count
    # Deletes during engine downtime are reconciled even if hook was missed.
    await source.delete_one({"id": "opt14-00000"})
    # A same-timestamp edit behind cursor is revisited on the next full cycle.
    await source.update_one({"id": "opt14-00001"}, {"$set": {"asset_name": "Revisited"}})
    for _ in range(14):
        await m.selaraskan_inkremental()
    assert "opt14-00000" not in engine.docs
    assert engine.docs["opt14-00001"]["asset_name"] == "Revisited"


async def test_meili_partial_candidates_and_literal_semantics_fall_back(contract, monkeypatch):
    import meili_utils as m
    from datetime import datetime, timezone
    monkeypatch.setattr(m, "meili_aktif", lambda: True)
    # Default literal substring cannot be implemented by a prefix/typo engine.
    monkeypatch.setattr(m, "MEILI_SEARCH_SEMANTICS", "literal")
    result = await m.kandidat_pencarian("assets", "kurs")
    assert result["reason"] == "literal_substring_requires_mongo" and not result["usable"]
    monkeypatch.setattr(m, "MEILI_SEARCH_SEMANTICS", "prefix_typo")
    await contract.db.meili_sync_state.update_one({"_id": "assets"}, {"$set": {
        "complete": True, "completed_at": datetime.now(timezone.utc)}}, upsert=True)
    async def partial(*args, **kwargs):
        return SimpleNamespace(json=lambda: {"hits": [{"id": str(i)} for i in range(5000)], "estimatedTotalHits": 5001})
    monkeypatch.setattr(m, "_req", partial)
    metadata = await m.kandidat_pencarian("assets", "kurs")
    assert metadata["truncated"] and not metadata["complete"] and not metadata["usable"]
    assert await m._cari_id("assets", "kurs", None) is None

    # A matching Mongo row beyond the 5000 candidate cap must remain visible,
    # including its count, while a different satker's row stays inaccessible.
    await contract.db.assets.insert_many([{"id": "opt14-fallback-" + letter,
        "asset_code": "opt14-fallback-" + letter, "NUP": "1", "category": "OPT14-fallback",
        "asset_name": "Unique completeness sentinel", "activity_id": "contract-activity-" + letter,
        "purchase_price": "10"} for letter in ("a", "b")])
    params = {"search": "Unique completeness sentinel", "category": "OPT14-fallback"}
    listing = await contract.http.get("/api/assets", headers=contract.headers["a"], params=params)
    assert listing.status_code == 200, listing.text
    assert [row["id"] for row in listing.json()["items"]] == ["opt14-fallback-a"]
    assert listing.json()["total"] == 1
    stats = await contract.http.get("/api/assets/stats", headers=contract.headers["a"], params=params)
    assert stats.status_code == 200, stats.text
    assert stats.json()["total_assets"] == 1


async def test_restore_invalidation_fences_meili_until_explicit_reindex(contract, monkeypatch):
    import meili_utils as m
    monkeypatch.setattr(m, "meili_aktif", lambda: True)
    monkeypatch.setattr(m, "MEILI_SEARCH_SEMANTICS", "prefix_typo")
    await m.invalidate_after_restore(contract.db)
    for collection in m.INDEKS:
        state = await contract.db.meili_sync_state.find_one({"_id": collection})
        assert state["force_mongo"] and not state["complete"] and "owner" not in state
    # A background cycle finishing cannot override the restore fence.
    await contract.db.meili_sync_state.update_one({"_id": "assets"}, {"$set": {"complete": True}})
    result = await m.kandidat_pencarian("assets", "sentinel")
    assert not result["usable"] and result["reason"] == "restore_requires_acknowledged_reindex"
