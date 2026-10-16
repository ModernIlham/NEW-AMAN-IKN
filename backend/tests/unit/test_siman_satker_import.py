"""SIMAN identity includes satker for both matching and applying a difference.

These tests exercise the complete route against a private in-memory database:
an administrator may view several satker, but a workbook for one satker must
never supply another satker's values for the same goods code, NUP or register.
"""
import asyncio
import io
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import routes.siman as rs


ADMIN = {"username": "unit-siman", "name": "Unit SIMAN", "role": "admin", "kode_satker": ""}
CODE = "3100102001"
SATKER_A = "621001"
SATKER_B = "621002"
FULL_A = "126011600621001000KP"
HEADER = ["Kode Barang", "NUP", "Nama Barang", "Nilai Perolehan", "Merk",
          "Tipe", "Kondisi", "Tanggal Perolehan", "Nama Pengguna",
          "Kode Register", "Kode Satker", "Umur Aset", "Nilai Penyusutan", "Nilai Buku"]


def _run(coro):
    return asyncio.run(coro)


def _unwrap(fn):
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn


class _Upload:
    filename = "siman.xlsx"

    def __init__(self, rows, header=HEADER):
        from openpyxl import Workbook

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Master Aset"
        sheet.append(header)
        for row in rows:
            sheet.append(row)
        buffer = io.BytesIO()
        workbook.save(buffer)
        workbook.close()
        self._content = buffer.getvalue()

    async def read(self):
        return self._content


def _row(satker=SATKER_A, brand="Lenovo", register="", code=CODE, nup="1"):
    return [code, nup, "Laptop", "15000000", brand, "T14", "Baik",
            "2024-03-01", "Budi", register, satker, "7", "1000000", "14000000"]


def _asset(identifier, activity="activity-a", brand="Lenovo", register="", **extra):
    return {"id": identifier, "activity_id": activity, "asset_code": CODE, "NUP": "1",
            "category": "Laptop", "asset_name": "Laptop", "purchase_price": "15000000",
            "brand": brand, "model": "T14", "condition": "Baik", "purchase_date": "2024-03-01",
            "user": "Budi", "kode_register": register, "version": 7, **extra}


@pytest.fixture
def dbx(monkeypatch, mongomock_update_sort_compat):
    import meili_utils
    import shared_utils

    database = AsyncMongoMockClient()["siman_satker_identity"]
    monkeypatch.setattr(rs, "db", database)
    monkeypatch.setattr(shared_utils, "db", database)
    monkeypatch.setattr(rs, "log_audit", AsyncMock())
    monkeypatch.setattr(meili_utils, "jadwalkan_sync", lambda *_args, **_kwargs: None)
    return database


async def _activities(database):
    await database.inventory_activities.insert_many([
        {"id": "activity-a", "nama_kegiatan": "Inventarisasi A", "kode_satker": SATKER_A},
        {"id": "activity-b", "nama_kegiatan": "Inventarisasi B", "kode_satker": SATKER_B},
    ])


async def _import(rows, *, mark_missing=False, header=HEADER, user=ADMIN):
    return await _unwrap(rs.import_siman)(
        request=None, file=_Upload(rows, header), tandai_tidak_ditemukan=mark_missing, user=user)


async def _snapshot(database):
    return {name: await database[name].find({}, {"_id": 0}).sort("id", 1).to_list(None)
            for name in ("assets", "siman_imports", "masa_manfaat", "inventory_activities", "satker")}


@pytest.mark.parametrize("register", ["", "SHARED-REGISTER"])
def test_file_one_satker_does_not_match_another_satker_same_code_nup_or_register(dbx, register):
    async def scenario():
        await _activities(dbx)
        await dbx.assets.insert_many([
            _asset("a", register=register),
            _asset("b", "activity-b", brand="Acer", register=register),
        ])
        foreign_before = await dbx.assets.find_one({"id": "b"}, {"_id": 0})

        result = await _import([_row(register=register)])

        assert result["ringkasan"]["aset_dicek"] == 1
        assert result["ringkasan"]["cocok"] == 1
        assert await dbx.assets.find_one({"id": "b"}, {"_id": 0}) == foreign_before
        own = await dbx.assets.find_one({"id": "a"})
        assert own["siman"]["kode_satker"] == SATKER_A
        assert own["siman"]["status"] == "cocok"

    _run(scenario())


def test_register_match_from_foreign_satker_cannot_override_own_code_nup_match(dbx):
    async def scenario():
        await _activities(dbx)
        await dbx.assets.insert_one(_asset("a", register="REGISTER-A"))

        result = await _import([
            _row(SATKER_B, "Foreign brand", "REGISTER-A", code="3999900001"),
            _row(SATKER_A, "Lenovo", "REGISTER-A"),
        ])

        own = await dbx.assets.find_one({"id": "a"})
        assert result["ringkasan"]["cocok"] == 1
        assert own["siman"]["status"] == "cocok"
        assert own["siman"]["selisih"] == []
        assert own["siman"]["kode_satker"] == SATKER_A

    _run(scenario())


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("shared_register", [False, True])
def test_mixed_workbook_matches_each_satker_independently_of_row_order(dbx, reverse, shared_register):
    async def scenario():
        await _activities(dbx)
        register = "REGISTER-SHARED" if shared_register else ""
        await dbx.assets.insert_many([
            _asset("a", brand="Old A", register=register),
            _asset("b", "activity-b", brand="Old B", register=register),
        ])
        rows = [_row(SATKER_A, "New A", register), _row(SATKER_B, "New B", register)]
        result = await _import(list(reversed(rows)) if reverse else rows)

        assert result["ringkasan"]["aset_dicek"] == 2
        assert result["ringkasan"]["selisih"] == 2
        assert result["duplikat_kunci"] == 0
        for identifier, satker, brand in (("a", SATKER_A, "New A"), ("b", SATKER_B, "New B")):
            asset = await dbx.assets.find_one({"id": identifier})
            assert asset["siman"]["kode_satker"] == satker
            changes = {change["field"]: change["siman"] for change in asset["siman"]["selisih"]}
            assert changes["brand"] == brand

    _run(scenario())


@pytest.mark.parametrize("full_source", ["activity", "master", "short_only"])
def test_full_siman_satker_matches_its_six_digit_activity_identity(dbx, full_source):
    async def scenario():
        activity = {"id": "activity-a", "kode_satker": SATKER_A}
        if full_source == "activity":
            activity["kode_satker_lengkap"] = FULL_A
        elif full_source == "master":
            await dbx.satker.insert_one({"kode_satker": SATKER_A, "kode_satker_lengkap": FULL_A})
        await dbx.inventory_activities.insert_one(activity)
        await dbx.assets.insert_one(_asset("a"))

        result = await _import([_row(FULL_A)])

        assert result["ringkasan"]["cocok"] == 1
        asset = await dbx.assets.find_one({"id": "a"})
        assert asset["siman"]["status"] == "cocok"
        assert asset["siman"]["kode_satker"] == FULL_A

    _run(scenario())


@pytest.mark.parametrize("foreign_full", [
    "126011601621001000KP",  # wilayah berbeda
    "126011600621001001KP",  # subsatker berbeda
    "126011600621001000KD",  # jenis kewenangan berbeda
])
def test_different_full_satker_is_distinct_even_when_six_digit_segment_is_identical(dbx, foreign_full):
    async def scenario():
        await dbx.inventory_activities.insert_many([
            {"id": "activity-a", "kode_satker": SATKER_A, "kode_satker_lengkap": FULL_A},
            {"id": "activity-b", "kode_satker": SATKER_A, "kode_satker_lengkap": foreign_full},
        ])
        await dbx.assets.insert_many([_asset("a"), _asset("b", "activity-b", brand="Foreign")])
        foreign_before = await dbx.assets.find_one({"id": "b"}, {"_id": 0})

        result = await _import([_row(FULL_A)])

        assert result["ringkasan"]["aset_dicek"] == 1
        assert await dbx.assets.find_one({"id": "b"}, {"_id": 0}) == foreign_before

    _run(scenario())


def test_mark_missing_only_changes_assets_in_satker_represented_by_workbook(dbx):
    async def scenario():
        await _activities(dbx)
        await dbx.assets.insert_many([
            _asset("a"), _asset("a-missing", NUP="2"),
            _asset("b", "activity-b"), _asset("b-missing", "activity-b", NUP="2"),
        ])
        foreign_before = await dbx.assets.find({"activity_id": "activity-b"}, {"_id": 0}).sort("id").to_list(None)

        result = await _import([_row()], mark_missing=True)

        assert result["ringkasan"]["aset_dicek"] == 1
        assert result["ringkasan"]["aman_tanpa_siman"] == 1
        missing = await dbx.assets.find_one({"id": "a-missing"})
        assert missing["siman"]["status"] == "tidak_di_siman"
        assert missing["version"] == 8
        assert await dbx.assets.find({"activity_id": "activity-b"}, {"_id": 0}).sort("id").to_list(None) == foreign_before

    _run(scenario())


@pytest.mark.parametrize("missing_header", [False, True])
@pytest.mark.parametrize("mark_missing", [False, True])
def test_missing_file_satker_is_rejected_before_any_write(dbx, missing_header, mark_missing):
    async def scenario():
        await _activities(dbx)
        await dbx.assets.insert_one(_asset("a"))
        await dbx.masa_manfaat.insert_one({"kode": "31001", "tahun": 3, "sumber": "siman"})
        before = await _snapshot(dbx)
        row = _row(satker="")
        header = HEADER
        if missing_header:
            row = [value for name, value in zip(HEADER, row) if name != "Kode Satker"]
            header = [name for name in HEADER if name != "Kode Satker"]

        with pytest.raises(HTTPException) as error:
            await _import([row], header=header, mark_missing=mark_missing)

        assert error.value.status_code == 400
        assert "satker" in str(error.value.detail).lower()
        assert await _snapshot(dbx) == before
        rs.log_audit.assert_not_awaited()

    _run(scenario())


@pytest.mark.parametrize("unknown_activity", ["missing-activity", "unknown-satker-activity", ""])
def test_asset_with_unknown_satker_identity_is_untouched_and_reported(dbx, unknown_activity):
    async def scenario():
        await _activities(dbx)
        await dbx.inventory_activities.insert_one({"id": "unknown-satker-activity", "kode_satker": ""})
        await dbx.assets.insert_many([
            _asset("a"),
            _asset("unknown", unknown_activity, brand="Must remain untouched"),
        ])
        unknown_before = await dbx.assets.find_one({"id": "unknown"}, {"_id": 0})

        result = await _import([_row()], mark_missing=True)

        assert result["ringkasan"]["aset_dicek"] == 1
        assert await dbx.assets.find_one({"id": "unknown"}, {"_id": 0}) == unknown_before
        assert any("satker" in warning.lower() for warning in result["peringatan"])

    _run(scenario())


@pytest.mark.parametrize("source", [SATKER_A, FULL_A])
def test_apply_accepts_verified_source_for_current_asset_satker(dbx, source):
    async def scenario():
        await _activities(dbx)
        await dbx.assets.insert_one(_asset("a", brand="Old", siman={
            "status": "selisih", "import_id": "current-import", "kode_satker": source,
            "kode_satker_aset": SATKER_A,
            "selisih": [{"field": "brand", "label": "Merk", "aman": "Old", "siman": "New"}],
        }))

        result = await rs.terapkan_siman("a", rs.TerapkanIn(fields=["brand"]), user=ADMIN)

        assert result["ok"] is True
        assert result["diterapkan"] == ["brand"]
        assert result["sisa_selisih"] == 0
        asset = await dbx.assets.find_one({"id": "a"})
        assert asset["brand"] == "New"
        assert asset["siman"]["status"] == "cocok"
        assert asset["version"] == 8
        rs.log_audit.assert_awaited_once()

    _run(scenario())


@pytest.mark.parametrize("invalid_source", ["legacy", "moved_activity"])
def test_apply_rejects_unverified_or_stale_satker_provenance_without_writes(dbx, invalid_source):
    async def scenario():
        await _activities(dbx)
        siman = {"status": "selisih", "import_id": "old-import", "selisih": [
            {"field": "brand", "label": "Merk", "aman": "Old", "siman": "New"},
        ]}
        if invalid_source == "moved_activity":
            siman["kode_satker"] = SATKER_A
            siman["kode_satker_aset"] = SATKER_A
        activity = "activity-b" if invalid_source == "moved_activity" else "activity-a"
        await dbx.assets.insert_one(_asset("a", activity, brand="Old", siman=siman))
        before = await _snapshot(dbx)

        with pytest.raises(HTTPException) as error:
            await rs.terapkan_siman("a", rs.TerapkanIn(fields=["brand"]), user=ADMIN)

        assert error.value.status_code == 409
        assert "satker" in str(error.value.detail).lower()
        assert await _snapshot(dbx) == before
        rs.log_audit.assert_not_awaited()

    _run(scenario())


@pytest.mark.parametrize("changed_field,new_value", [("version", 8), ("activity_id", "activity-b")])
def test_apply_does_not_overwrite_asset_changed_after_identity_check(dbx, monkeypatch, changed_field, new_value):
    async def scenario():
        await _activities(dbx)
        source = {"status": "selisih", "import_id": "current-import", "kode_satker": SATKER_A,
                  "kode_satker_aset": SATKER_A,
                  "selisih": [{"field": "brand", "label": "Merk", "aman": "Old", "siman": "New"}]}
        await dbx.assets.insert_one(_asset("a", brand="Old", siman=source))
        collection_type = type(dbx.assets)
        original_update = collection_type.find_one_and_update

        async def change_before_compare_and_swap(collection, *args, **kwargs):
            if collection.name == "assets":
                await collection.update_one({"id": "a"}, {"$set": {changed_field: new_value}})
            return await original_update(collection, *args, **kwargs)

        # Motor's attribute accessor returns a fresh collection wrapper each
        # time, so intercept the collection type rather than one temporary
        # wrapper that the route would never reuse.
        monkeypatch.setattr(collection_type, "find_one_and_update", change_before_compare_and_swap)

        with pytest.raises(HTTPException) as error:
            await rs.terapkan_siman("a", rs.TerapkanIn(fields=["brand"]), user=ADMIN)

        assert error.value.status_code == 409
        asset = await dbx.assets.find_one({"id": "a"})
        assert asset[changed_field] == new_value
        assert asset["brand"] == "Old"
        assert asset["siman"] == source
        rs.log_audit.assert_not_awaited()

    _run(scenario())


@pytest.mark.parametrize("operation", ["matching", "mark_missing"])
def test_import_does_not_write_to_asset_moved_between_matching_and_bulk(dbx, monkeypatch, operation):
    async def scenario():
        await _activities(dbx)
        target = _asset("moving", asset_code=CODE if operation == "matching" else "3999900001")
        await dbx.assets.insert_one(target)
        original_document = await dbx.assets.find_one({"id": "moving"}, {"_id": 0})
        collection_type = type(dbx.assets)
        original_bulk = collection_type.bulk_write

        async def move_before_bulk(collection, *args, **kwargs):
            if collection.name == "assets":
                await collection.update_one({"id": "moving"}, {"$set": {"activity_id": "activity-b"}})
            return await original_bulk(collection, *args, **kwargs)

        monkeypatch.setattr(collection_type, "bulk_write", move_before_bulk)

        with pytest.raises(HTTPException) as error:
            await _import([_row(register="NEW-SIMAN-REGISTER")], mark_missing=operation == "mark_missing")

        assert error.value.status_code == 409
        assert await dbx.assets.find_one({"id": "moving"}, {"_id": 0}) == {
            **original_document, "activity_id": "activity-b",
        }
        assert await dbx.siman_imports.count_documents({}) == 0
        assert await dbx.masa_manfaat.count_documents({}) == 0
        rs.log_audit.assert_not_awaited()

    _run(scenario())


@pytest.mark.parametrize("full_source", ["activity", "master"])
def test_authoritative_activity_or_master_full_satker_ignores_stale_asset_code(dbx, full_source):
    async def scenario():
        foreign_full = "126011601621001000KP"
        activity = {"id": "activity-a", "kode_satker": SATKER_A}
        if full_source == "activity":
            activity["kode_satker_lengkap"] = FULL_A
        else:
            await dbx.satker.insert_one({"kode_satker": SATKER_A, "kode_satker_lengkap": FULL_A})
        await dbx.inventory_activities.insert_one(activity)
        await dbx.assets.insert_one(_asset("a", kode_satker=SATKER_A, kode_satker_lengkap=foreign_full))

        result = await _import([_row(foreign_full, "Wrong location"), _row(FULL_A, "Lenovo")])

        assert result["ringkasan"]["cocok"] == 1
        own = await dbx.assets.find_one({"id": "a"})
        assert own["siman"]["kode_satker"] == FULL_A
        assert own["siman"]["kode_satker_aset"] == FULL_A
        assert own["siman"]["selisih"] == []

    _run(scenario())


def test_import_rejects_parent_identity_changed_after_initial_read(dbx, monkeypatch):
    async def scenario():
        await _activities(dbx)
        await dbx.assets.insert_one(_asset("a"))
        before = await dbx.assets.find_one({"id": "a"}, {"_id": 0})
        original_identity = rs._identitas_satker_aset
        first = True

        async def change_parent_after_read(assets):
            nonlocal first
            identities = await original_identity(assets)
            if first:
                first = False
                await dbx.inventory_activities.update_one(
                    {"id": "activity-a"}, {"$set": {"kode_satker": SATKER_B}})
            return identities

        monkeypatch.setattr(rs, "_identitas_satker_aset", change_parent_after_read)

        with pytest.raises(HTTPException) as error:
            await _import([_row(register="REGISTER-NOT-TO-ADOPT")])

        assert error.value.status_code == 409
        assert await dbx.assets.find_one({"id": "a"}, {"_id": 0}) == before
        assert (await dbx.inventory_activities.find_one({"id": "activity-a"}))["kode_satker"] == SATKER_B
        assert await dbx.siman_imports.count_documents({}) == 0
        assert await dbx.masa_manfaat.count_documents({}) == 0
        rs.log_audit.assert_not_awaited()

    _run(scenario())


def test_apply_rejects_parent_identity_changed_after_initial_read(dbx, monkeypatch):
    async def scenario():
        await _activities(dbx)
        await dbx.satker.insert_one({"kode_satker": SATKER_A, "kode_satker_lengkap": FULL_A})
        await dbx.assets.insert_one(_asset("a", brand="Old", siman={
            "status": "selisih", "import_id": "current-import", "kode_satker": FULL_A,
            "kode_satker_aset": FULL_A,
            "selisih": [{"field": "brand", "label": "Merk", "aman": "Old", "siman": "New"}],
        }))
        before = await dbx.assets.find_one({"id": "a"}, {"_id": 0})
        original_identity = rs._identitas_satker_aset
        first = True
        new_full = "126011601621001000KP"

        async def change_parent_after_read(assets):
            nonlocal first
            identities = await original_identity(assets)
            if first:
                first = False
                await dbx.satker.update_one(
                    {"kode_satker": SATKER_A}, {"$set": {"kode_satker_lengkap": new_full}})
            return identities

        monkeypatch.setattr(rs, "_identitas_satker_aset", change_parent_after_read)

        with pytest.raises(HTTPException) as error:
            await rs.terapkan_siman("a", rs.TerapkanIn(fields=["brand"]), user=ADMIN)

        assert error.value.status_code == 409
        assert await dbx.assets.find_one({"id": "a"}, {"_id": 0}) == before
        assert (await dbx.satker.find_one({"kode_satker": SATKER_A}))["kode_satker_lengkap"] == new_full
        rs.log_audit.assert_not_awaited()

    _run(scenario())
