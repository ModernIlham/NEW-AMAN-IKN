"""Current SIMAN indicators require evidence for the asset's current owner."""

import asyncio
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from mongomock_motor import AsyncMongoMockClient

from siman_provenance import (
    bersihkan_referensi_siman,
    identitas_satker_aset,
    referensi_siman_terverifikasi,
)


SHORT = "621001"
FULL = "126011600621001000KP"
OTHER_FULL = "126011601621001000KP"


def run(coro):
    return asyncio.run(coro)


def reference(source=FULL, snapshot=FULL):
    return {"status": "cocok", "kode_satker": source,
            "kode_satker_aset": snapshot, "import_id": "import-a",
            "selisih": [], "referensi": {"no_psp": "SIMAN-A", "tanggal_psp": "2025-01-02"}}


@pytest.mark.parametrize("owner,source,snapshot", [
    (FULL, FULL, FULL), (FULL, SHORT, FULL), (SHORT, FULL, SHORT),
    (SHORT, SHORT, SHORT),
    (FULL, "126.01.1600.621001.000.kp", FULL),
    ("legacy-A", "legacy-A", "legacy-A"),
])
def test_verified_reference_preserves_legitimate_short_full_and_opaque_identities(owner, source, snapshot):
    assert referensi_siman_terverifikasi(reference(source, snapshot), owner)


@pytest.mark.parametrize("sub,owner", [
    (None, FULL), ([], FULL), ({}, FULL),
    ({"status": "cocok"}, FULL),
    ({"kode_satker": FULL}, FULL),
    ({"kode_satker_aset": FULL}, FULL),
    (reference(), ""), (reference(), None),
    (reference("621002", FULL), FULL),
    (reference(FULL, OTHER_FULL), FULL),
    (reference(FULL, FULL), OTHER_FULL),
    # Two complete identities must not become equal through a short owner.
    (reference(FULL, OTHER_FULL), SHORT),
    (reference("legacy-A", "legacy-A"), "LEGACYA"),
])
def test_unverified_foreign_moved_and_contradictory_references_are_not_current_matches(sub, owner):
    assert not referensi_siman_terverifikasi(sub, owner)


@pytest.mark.parametrize("bad", [[], [SHORT], {}, {"code": SHORT}, True, False])
@pytest.mark.parametrize("field", ["identity", "kode_satker", "kode_satker_aset"])
def test_malformed_provenance_does_not_become_an_opaque_string_alias(bad, field):
    sub = reference()
    owner = FULL
    if field == "identity":
        owner = bad
        sub = reference(str(bad), str(bad))
    else:
        sub[field] = bad
        owner = str(bad)
        sub["kode_satker_aset" if field == "kode_satker" else "kode_satker"] = str(bad)
    assert not referensi_siman_terverifikasi(sub, owner)


@pytest.mark.parametrize("bad_activity", [[], ["activity"], {}, {"id": "activity"}, True, 1])
def test_malformed_activity_id_is_unknown_even_with_an_asset_owner_stamp(bad_activity):
    async def scenario():
        database = AsyncMongoMockClient()["provenance_malformed_activity"]
        rows = [{"id": "asset", "activity_id": bad_activity, "kode_satker": SHORT,
                 "kode_satker_lengkap": FULL, "siman": reference()}]

        assert await identitas_satker_aset(rows, database=database) == {"asset": ""}
        await bersihkan_referensi_siman(rows, database=database)
        assert rows[0]["siman"] is None

    run(scenario())


@pytest.mark.parametrize("bad_owner", [[], [SHORT], {}, {"code": SHORT}, True, False])
@pytest.mark.parametrize("source", ["activity", "master", "asset"])
def test_malformed_stored_owner_fields_are_unknown(source, bad_owner):
    async def scenario():
        database = AsyncMongoMockClient()["provenance_malformed_owner"]
        row = {"id": "asset", "activity_id": "activity", "kode_satker": SHORT,
               "kode_satker_lengkap": FULL, "siman": reference()}
        if source == "activity":
            await database.inventory_activities.insert_one({"id": "activity", "kode_satker": bad_owner,
                                                            "kode_satker_lengkap": FULL})
        elif source == "master":
            await database.inventory_activities.insert_one({"id": "activity", "kode_satker": SHORT})
            await database.satker.insert_one({"kode_satker": SHORT, "kode_satker_lengkap": bad_owner})
        else:
            row["kode_satker"] = bad_owner

        assert await identitas_satker_aset([row], database=database) == {"asset": ""}
        await bersihkan_referensi_siman([row], database=database)
        assert row["siman"] is None

    run(scenario())


def test_owner_resolution_prioritizes_activity_and_master_over_stale_asset_stamps():
    async def scenario():
        database = AsyncMongoMockClient()["provenance_owner"]
        await database.inventory_activities.insert_many([
            {"id": "full-activity", "kode_satker": SHORT, "kode_satker_lengkap": FULL},
            {"id": "master-activity", "kode_satker": SHORT},
            {"id": "conflicting-activity", "kode_satker": "621002", "kode_satker_lengkap": FULL},
        ])
        await database.satker.insert_one({"kode_satker": SHORT, "kode_satker_lengkap": FULL})
        rows = [
            {"id": "activity", "activity_id": "full-activity", "kode_satker_lengkap": OTHER_FULL},
            {"id": "master", "activity_id": "master-activity", "kode_satker_lengkap": OTHER_FULL},
            {"id": "conflict", "activity_id": "conflicting-activity", "kode_satker": SHORT},
            {"id": "legacy", "activity_id": "missing", "kode_satker": SHORT, "kode_satker_lengkap": FULL},
            {"id": "unknown", "activity_id": "missing"},
        ]
        before = deepcopy(rows)

        owners = await identitas_satker_aset(rows, database=database)

        assert owners == {"activity": FULL, "master": FULL, "conflict": "", "legacy": FULL, "unknown": ""}
        assert rows == before

    run(scenario())


def test_resolution_batches_activity_and_master_reads_instead_of_one_query_per_asset():
    async def scenario():
        database = AsyncMongoMockClient()["provenance_batch"]
        rows = [{"id": f"asset-{i}", "activity_id": f"activity-{i}"} for i in range(1001)]
        await database.inventory_activities.insert_many([
            {"id": row["activity_id"], "kode_satker": str(600000 + i)} for i, row in enumerate(rows)])
        calls = {"activities": [], "master": []}

        class CountedCollection:
            def __init__(self, collection, name):
                self.collection, self.name = collection, name

            def find(self, query, projection):
                calls[self.name].append(deepcopy(query))
                return self.collection.find(query, projection)

        counted_database = SimpleNamespace(
            inventory_activities=CountedCollection(database.inventory_activities, "activities"),
            satker=CountedCollection(database.satker, "master"),
        )

        owners = await identitas_satker_aset(rows, database=counted_database)

        assert owners == {row["id"]: str(600000 + i) for i, row in enumerate(rows)}
        assert [len(q["id"]["$in"]) for q in calls["activities"]] == [1000, 1]
        assert [len(q["kode_satker"]["$in"]) for q in calls["master"]] == [1000, 1]

    run(scenario())


def test_response_cleanup_is_explicit_and_preserves_stored_evidence_native_fields_and_versions():
    async def scenario():
        database = AsyncMongoMockClient()["provenance_response"]
        await database.inventory_activities.insert_one({"id": "activity", "kode_satker": SHORT,
                                                        "kode_satker_lengkap": FULL})
        rows = [
            {"id": "valid", "activity_id": "activity", "version": 7, "brand": "Native", "siman": reference()},
            {"id": "foreign", "activity_id": "activity", "version": 8, "brand": "Unchanged",
             "siman": reference("621002", "621002")},
            {"id": "legacy", "activity_id": "activity", "version": 9, "siman": {"status": "cocok"}},
            {"id": "missing", "activity_id": "activity", "version": 10},
        ]
        await database.assets.insert_many(deepcopy(rows))
        stored_before = await database.assets.find({}, {"_id": 0}).sort("id").to_list(None)

        result = await bersihkan_referensi_siman(rows, database=database)

        assert result is rows
        assert rows[0]["siman"] == reference()
        assert rows[0]["version"] == 7 and rows[0]["brand"] == "Native"
        assert rows[1]["siman"] is None and rows[1]["version"] == 8 and rows[1]["brand"] == "Unchanged"
        assert rows[2]["siman"] is None and rows[2]["version"] == 9
        assert "siman" in rows[3] and rows[3]["siman"] is None and rows[3]["version"] == 10
        assert await database.assets.find({}, {"_id": 0}).sort("id").to_list(None) == stored_before

    run(scenario())


def test_assets_psp_fallback_uses_only_verified_siman_and_keeps_official_register(monkeypatch):
    import routes.assets as assets_route

    async def scenario():
        database = AsyncMongoMockClient()["provenance_psp"]
        monkeypatch.setattr(assets_route, "db", database)
        await database.inventory_activities.insert_one({"id": "activity", "kode_satker": SHORT,
                                                        "kode_satker_lengkap": FULL})
        await database.psp.insert_one({
            "kode_satker": SHORT, "nomor_sk": "OFFICIAL-REGISTER", "tanggal_sk": "2026-01-03",
            "jenis": "psp", "status_pengajuan": "ditetapkan", "aset": [{"asset_id": "registered"}],
        })
        rows = [
            {"id": "valid", "activity_id": "activity", "siman": reference()},
            {"id": "foreign", "activity_id": "activity", "siman": reference("621002", "621002")},
            {"id": "legacy", "activity_id": "activity", "siman": {
                "status": "cocok", "referensi": {"no_psp": "UNVERIFIED-PSP"}}},
            {"id": "registered", "activity_id": "activity", "siman": reference("621002", "621002")},
            {"id": "missing", "activity_id": "activity", "psp": {"no_psp": "STALE", "sumber": "siman"}},
        ]

        await assets_route.lengkapi_psp(rows, {"kode_satker": SHORT})

        assert rows[0]["psp"]["no_psp"] == "SIMAN-A" and rows[0]["psp"]["sumber"] == "siman"
        assert rows[1]["siman"] is None and rows[1]["psp"] is None
        assert rows[2]["siman"] is None and rows[2]["psp"] is None
        assert rows[3]["siman"] is None and rows[3]["psp"]["no_psp"] == "OFFICIAL-REGISTER"
        assert rows[3]["psp"]["sumber"] == "register"
        assert rows[4]["siman"] is None and rows[4]["psp"] is None

    run(scenario())


def test_list_projection_preserves_legacy_owner_stamps_for_provenance_resolution():
    from routes.assets import LIST_PROJECTION

    assert LIST_PROJECTION["kode_satker"] == 1
    assert LIST_PROJECTION["kode_satker_lengkap"] == 1


def test_asset_detail_sends_explicit_null_without_destroying_stored_import(monkeypatch):
    import routes.assets as assets_route

    async def scenario():
        database = AsyncMongoMockClient()["provenance_detail"]
        monkeypatch.setattr(assets_route, "db", database)
        monkeypatch.setattr(assets_route, "hydrate_checklist", AsyncMock(return_value=[]))
        await database.inventory_activities.insert_one({"id": "activity", "kode_satker": SHORT,
                                                        "kode_satker_lengkap": FULL})
        original = {"id": "asset", "activity_id": "activity", "asset_code": "3100102001", "NUP": "1",
                    "asset_name": "Native name", "category": "Laptop", "created_at": "2026-01-01",
                    "version": 7, "siman": reference("621002", "621002")}
        await database.assets.insert_one(deepcopy(original))

        response = await assets_route.get_asset("asset", exclude_media=False, _user={"kode_satker": ""})

        payload = response.model_dump(mode="json")
        assert "siman" in payload and payload["siman"] is None
        assert "psp" in payload and payload["psp"] is None
        assert payload["version"] == 7 and payload["asset_name"] == "Native name"
        assert await database.assets.find_one({"id": "asset"}, {"_id": 0}) == original

    run(scenario())


@pytest.mark.parametrize("endpoint", ["create", "patch"])
def test_idempotent_replay_rechecks_current_owner_without_changing_native_snapshot(monkeypatch, endpoint):
    import routes.assets as assets_route
    from models import AssetCreate
    from starlette.requests import Request

    async def scenario():
        database = AsyncMongoMockClient()["provenance_replay"]
        monkeypatch.setattr(assets_route, "db", database)
        await database.inventory_activities.insert_many([
            {"id": "original-activity", "kode_satker": SHORT, "kode_satker_lengkap": FULL},
            {"id": "current-activity", "kode_satker": "621002"},
        ])
        cached_payload = {
            "id": "asset", "activity_id": "original-activity", "asset_code": "3100102001", "NUP": "1",
            "asset_name": "Original name", "category": "Laptop", "created_at": "2026-01-01",
            "version": 7, "siman": reference(), "psp": {"no_psp": "SIMAN-A", "sumber": "siman"},
        }
        current = {**deepcopy(cached_payload), "activity_id": "current-activity", "version": 8,
                   "asset_name": "Current name"}
        await database.assets.insert_one(deepcopy(current))
        cached_before = deepcopy(cached_payload)
        monkeypatch.setattr(assets_route, "get_idempotent_response", AsyncMock(return_value={"response": cached_payload}))
        request = Request({"type": "http", "headers": [(b"idempotency-key", b"provenance-replay") ]})
        user = {"id": "admin", "username": "admin", "role": "admin", "kode_satker": ""}

        if endpoint == "create":
            response = await assets_route.create_asset(AssetCreate(
                asset_code="3100102001", asset_name="Ignored repeat", category="Laptop"), request, _user=user)
        else:
            response = await assets_route.patch_asset("asset", request, _user=user)

        payload = response.model_dump(mode="json")
        assert payload["siman"] is None and payload["psp"] is None
        assert payload["activity_id"] == "original-activity" and payload["version"] == 7
        assert payload["asset_name"] == "Original name"
        assert cached_payload == cached_before
        assert await database.assets.find_one({"id": "asset"}, {"_id": 0}) == current

    run(scenario())


def test_permanent_create_replay_keeps_verified_legacy_flat_owner(monkeypatch):
    import routes.assets as assets_route
    from models import AssetCreate
    from starlette.requests import Request

    async def scenario():
        database = AsyncMongoMockClient()["provenance_permanent_replay"]
        monkeypatch.setattr(assets_route, "db", database)
        monkeypatch.setattr(assets_route, "get_idempotent_response", AsyncMock(return_value=None))
        request = Request({"type": "http", "headers": [(b"idempotency-key", b"permanent-legacy-replay")]})
        user = {"id": "admin", "username": "admin", "role": "admin", "kode_satker": ""}
        idem_key = assets_route.kunci_idem("permanent-legacy-replay", user)
        original = {
            "id": "asset", "idem_key": idem_key, "asset_code": "3100102001", "NUP": "1",
            "asset_name": "Legacy asset", "category": "Laptop", "created_at": "2026-01-01", "version": 7,
            "kode_satker": SHORT, "kode_satker_lengkap": FULL, "siman": reference(),
        }
        await database.assets.insert_one(deepcopy(original))

        response = await assets_route.create_asset(AssetCreate(
            asset_code="3100102001", asset_name="Ignored repeat", category="Laptop"), request, _user=user)

        payload = response.model_dump(mode="json")
        assert payload["siman"] == reference()
        assert payload["psp"]["no_psp"] == "SIMAN-A"
        assert payload["version"] == 7 and payload["asset_name"] == "Legacy asset"
        assert await database.assets.count_documents({}) == 1
        assert await database.assets.find_one({"id": "asset"}, {"_id": 0}) == original

    run(scenario())
