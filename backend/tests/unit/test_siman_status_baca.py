"""SIMAN read views count and paginate only references for today's owner.

These exercise the routes against a private Mongo-compatible database. Old
references remain audit evidence in storage, while invalid references must
neither inflate counts nor consume the first page of actionable differences.
"""

import asyncio
from copy import deepcopy
import io
from unittest.mock import AsyncMock

from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient
import pytest

import routes.siman as rs


SHORT = "621001"
FULL = "126011600621001000KP"
MOVED = "126011601621001000KP"
ADMIN = {"username": "siman-read-unit", "name": "SIMAN read unit",
         "role": "admin", "kode_satker": ""}


@pytest.mark.parametrize("malformed", [
    [], [{"status": "selisih"}], "selisih", True, 1,
    {"status": "selisih", "selisih": {"brand": "New"}},
    {"status": "selisih", "selisih": ["brand"]},
])
def test_apply_rejects_malformed_old_reference_without_writes(database, malformed):
    async def scenario():
        await seed_activity(database)
        await database.assets.insert_one(asset(siman=malformed))
        before = await snapshot(database)
        with pytest.raises(HTTPException) as error:
            await rs.terapkan_siman("valid", rs.TerapkanIn(), user=ADMIN)
        assert error.value.status_code == 409
        assert await snapshot(database) == before
        rs.log_audit.assert_not_awaited()

    run(scenario())


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def database(monkeypatch, mongomock_update_sort_compat):
    import shared_utils
    import siman_provenance

    fake = AsyncMongoMockClient()["siman_status_baca"]
    for module in (rs, shared_utils, siman_provenance):
        monkeypatch.setattr(module, "db", fake)
    monkeypatch.setattr(rs, "log_audit", AsyncMock())
    return fake


def reference(status="selisih", source=FULL, snapshot=FULL):
    return {"status": status, "kode_satker": source, "kode_satker_aset": snapshot,
            "selisih": [{"field": "brand", "aman": "Old", "siman": "New"}]}


def asset(identifier="valid", **changes):
    return {"id": identifier, "activity_id": "activity", "kode_satker": SHORT,
            "asset_code": "3999900001", "NUP": "1", "asset_name": identifier,
            "version": 7, "siman": reference(), **changes}


async def seed_activity(database):
    await database.inventory_activities.insert_one({
        "id": "activity", "kode_satker": SHORT, "kode_satker_lengkap": FULL,
        "nama_kegiatan": "Inventarisasi unit",
    })


async def snapshot(database):
    return await database.assets.find({}, {"_id": 0}).sort("id").to_list(None)


def test_foreign_legacy_and_changed_owner_references_become_unchecked_without_writes(database):
    async def scenario():
        await seed_activity(database)
        await database.assets.insert_many([
            asset(), asset("matched", siman=reference("cocok")),
            asset("not-found", siman=reference("tidak_di_siman")),
            asset("foreign", siman=reference(source="621002", snapshot="621002")),
            asset("legacy", siman={"status": "selisih", "selisih": []}),
            asset("contradictory", siman=reference(source=FULL, snapshot=MOVED)),
            asset("no-owner-snapshot", siman={"status": "cocok", "kode_satker": FULL}),
            asset("unknown-status", siman=reference("invented-status")),
            asset("without-reference", siman=None),
        ])
        before = await snapshot(database)

        summary = await rs.ringkasan_siman(_user=ADMIN)

        assert (summary["selisih"], summary["cocok"], summary["tidak_di_siman"],
                summary["belum_dicek"]) == (1, 1, 1, 6)
        assert len(summary["per_kegiatan"]) == 1
        assert summary["per_kegiatan"][0]["total"] == 3
        assert await snapshot(database) == before

        await database.inventory_activities.update_one(
            {"id": "activity"}, {"$set": {"kode_satker_lengkap": MOVED}})
        moved = await rs.ringkasan_siman(_user=ADMIN)
        assert (moved["selisih"], moved["cocok"], moved["tidak_di_siman"],
                moved["belum_dicek"]) == (0, 0, 0, 9)
        assert moved["per_kegiatan"] == []
        assert await snapshot(database) == before

    run(scenario())


@pytest.mark.parametrize("field,value", [
    ("siman.status", ["selisih"]), ("siman.status", {"$ne": ""}),
    ("siman.kode_satker", [FULL]), ("siman.kode_satker", {"$ne": ""}),
    ("siman.kode_satker_aset", [FULL]), ("siman.kode_satker_aset", {"$ne": ""}),
    ("kode_satker", [SHORT]), ("kode_satker", {"$ne": ""}),
    ("kode_satker_lengkap", [FULL]), ("kode_satker_lengkap", {"$exists": True}),
    ("activity_id", ["activity"]), ("activity_id", {"$ne": ""}),
    ("siman", [reference()]),
])
def test_malformed_metadata_never_becomes_operator_or_array_alias(database, field, value):
    async def scenario():
        await seed_activity(database)
        malformed = asset("malformed", asset_code="2999900001")
        container = malformed
        path = field.split(".")
        for part in path[:-1]:
            container = container[part]
        container[path[-1]] = deepcopy(value)
        await database.assets.insert_many([asset(), malformed])
        before = await snapshot(database)

        summary = await rs.ringkasan_siman(_user=ADMIN)
        listed = await rs.daftar_selisih_siman(page=1, page_size=1, activity_id="", _user=ADMIN)

        assert (summary["selisih"], summary["belum_dicek"]) == (1, 1)
        assert listed["total"] == 1
        assert [row["id"] for row in listed["items"]] == ["valid"]
        assert await snapshot(database) == before

    run(scenario())


def test_unverified_rows_are_excluded_before_count_sort_and_pagination(database):
    async def scenario():
        await seed_activity(database)
        rows = [asset("valid-1", NUP="1"), asset("valid-2", NUP="2")]
        rows.extend(asset(f"legacy-{index}", asset_code=f"29999000{index:02}",
                          siman={"status": "selisih", "selisih": []}) for index in range(4))
        await database.assets.insert_many(rows)
        before = await snapshot(database)

        pages = [await rs.daftar_selisih_siman(page=page, page_size=1, activity_id="", _user=ADMIN)
                 for page in (1, 2, 3)]

        assert [page["total"] for page in pages] == [2, 2, 2]
        assert [page["total_pages"] for page in pages] == [2, 2, 2]
        assert [[row["id"] for row in page["items"]] for page in pages] == [
            ["valid-1"], ["valid-2"], [],
        ]
        assert await snapshot(database) == before

    run(scenario())


def test_missing_and_null_flat_stamps_do_not_admit_array_aliases(database):
    async def scenario():
        await seed_activity(database)
        unstamped = asset("missing-stamp")
        unstamped.pop("kode_satker")
        await database.assets.insert_many([
            unstamped, asset("null-stamp", kode_satker=None),
            asset("array-stamp", kode_satker=["", None], asset_code="2999900001"),
        ])

        summary = await rs.ringkasan_siman(_user=ADMIN)
        listed = await rs.daftar_selisih_siman(page=1, page_size=50, activity_id="", _user=ADMIN)

        assert (summary["selisih"], summary["belum_dicek"]) == (2, 1)
        assert listed["total"] == 2
        assert {row["id"] for row in listed["items"]} == {"missing-stamp", "null-stamp"}

    run(scenario())


@pytest.mark.parametrize("endpoint", ["summary", "differences"])
def test_group_limit_fails_explicitly_instead_of_returning_partial_counts(database, monkeypatch, endpoint):
    monkeypatch.setattr(rs, "_MAKS_KELOMPOK_STATUS", 2)

    async def scenario():
        await seed_activity(database)
        await database.assets.insert_many([
            asset("full"), asset("short", siman=reference(source=SHORT)),
            asset("formatted", siman=reference(source="126.01.1600.621001.000.KP")),
        ])
        before = await snapshot(database)
        with pytest.raises(HTTPException) as error:
            if endpoint == "summary":
                await rs.ringkasan_siman(_user=ADMIN)
            else:
                await rs.daftar_selisih_siman(page=1, page_size=1, activity_id="", _user=ADMIN)
        assert error.value.status_code == 503
        assert "Metadata sinkronisasi terlalu besar" in error.value.detail
        assert await snapshot(database) == before

    run(scenario())


def test_group_limit_counts_metadata_combinations_rather_than_asset_count(database, monkeypatch):
    monkeypatch.setattr(rs, "_MAKS_KELOMPOK_STATUS", 1)

    async def scenario():
        await seed_activity(database)
        await database.assets.insert_many([asset(f"valid-{i}", NUP=str(i)) for i in range(20)])
        summary = await rs.ringkasan_siman(_user=ADMIN)
        assert summary["selisih"] == 20 and summary["belum_dicek"] == 0
        assert summary["per_kegiatan"][0]["total"] == 20

    run(scenario())


def test_bson_budget_rejects_query_before_returning_partial_results(database, monkeypatch):
    monkeypatch.setattr(rs, "_MAKS_KUER_STATUS", 1)

    async def scenario():
        await seed_activity(database)
        await database.assets.insert_one(asset())
        before = await snapshot(database)
        with pytest.raises(HTTPException) as error:
            await rs.daftar_selisih_siman(page=1, page_size=1, activity_id="", _user=ADMIN)
        assert error.value.status_code == 503
        assert "Lingkup referensi SIMAN terlalu besar" in error.value.detail
        assert await snapshot(database) == before

    run(scenario())


def test_bson_budget_includes_base_query_when_no_metadata_group_matches(database, monkeypatch):
    monkeypatch.setattr(rs, "_MAKS_KUER_STATUS", 1000)

    async def scenario():
        await seed_activity(database)
        await database.assets.insert_one(asset())
        with pytest.raises(HTTPException) as error:
            await rs.daftar_selisih_siman(
                page=1, page_size=1, activity_id="nonexistent-" + "x" * 2000, _user=ADMIN)
        assert error.value.status_code == 503
        assert "Lingkup referensi SIMAN terlalu besar" in error.value.detail

    run(scenario())


def test_parent_change_after_grouping_is_detected_before_page_is_returned(database, monkeypatch):
    original = rs._identitas_satker_aset
    calls = 0

    async def resolve_with_parent_change(rows):
        nonlocal calls
        calls += 1
        if calls == 2:
            await database.inventory_activities.update_one(
                {"id": "activity"}, {"$set": {"kode_satker_lengkap": MOVED}})
        return await original(rows)

    monkeypatch.setattr(rs, "_identitas_satker_aset", resolve_with_parent_change)

    async def scenario():
        await seed_activity(database)
        await database.assets.insert_one(asset())
        before = await snapshot(database)
        with pytest.raises(HTTPException) as error:
            await rs.daftar_selisih_siman(page=1, page_size=1, activity_id="", _user=ADMIN)
        assert error.value.status_code == 409
        assert "berubah" in error.value.detail
        assert calls == 2
        assert await snapshot(database) == before

    run(scenario())


def test_new_missing_asset_marker_retains_proof_and_expires_when_owner_changes(database):
    class Upload:
        filename = "master-aset.xlsx"

        async def read(self):
            from openpyxl import Workbook

            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "Master Aset"
            sheet.append(["Kode Barang", "NUP", "Kode Satker"])
            sheet.append(["3999900001", "1", FULL])
            buffer = io.BytesIO()
            workbook.save(buffer)
            workbook.close()
            return buffer.getvalue()

    async def scenario():
        await seed_activity(database)
        await database.assets.insert_many([
            asset("present", siman=None), asset("absent", NUP="2", siman=None),
        ])
        importer = rs.import_siman
        while hasattr(importer, "__wrapped__"):
            importer = importer.__wrapped__
        await importer(request=None, file=Upload(), tandai_tidak_ditemukan=True, user=ADMIN)
        missing = await database.assets.find_one({"id": "absent"})
        assert missing["siman"]["status"] == "tidak_di_siman"
        assert missing["siman"]["kode_satker"] == FULL
        assert missing["siman"]["kode_satker_aset"] == FULL
        summary = await rs.ringkasan_siman(_user=ADMIN)
        assert (summary["cocok"], summary["tidak_di_siman"], summary["belum_dicek"]) == (1, 1, 0)

        await database.inventory_activities.update_one(
            {"id": "activity"}, {"$set": {"kode_satker_lengkap": MOVED}})
        changed = await rs.ringkasan_siman(_user=ADMIN)
        assert (changed["cocok"], changed["tidak_di_siman"], changed["belum_dicek"]) == (0, 0, 2)

    run(scenario())
