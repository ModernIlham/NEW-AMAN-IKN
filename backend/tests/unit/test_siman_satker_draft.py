"""Draft and CSV preserve the satker identity of unmatched SIMAN rows.

The route performs real matching, validation, database updates and bookkeeping
against an isolated in-memory database. The generic asset creation boundary is
replaced so these tests isolate which rows the SIMAN route is allowed to create.
"""
import asyncio
import csv
import io
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import routes.siman as rs


ADMIN = {"username": "unit-siman", "role": "admin", "kode_satker": ""}
CODE = "3100102001"
SATKER_A = "621001"
SATKER_B = "621002"
FULL_A = "126011600621001000KP"
FULL_B = "126011601621001000KP"


def _run(coro):
    return asyncio.run(coro)


def _unwrap(fn):
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn


@pytest.fixture
def context(monkeypatch):
    import routes.assets
    import shared_utils

    database = AsyncMongoMockClient()["siman_satker_draft"]
    monkeypatch.setattr(rs, "db", database)
    monkeypatch.setattr(shared_utils, "db", database)
    monkeypatch.setattr(rs, "log_audit", AsyncMock())

    async def create_asset(data, audit_user):
        identifier = f"created-{await database.assets.count_documents({})}"
        document = {**data.model_dump(), "id": identifier, "version": 1}
        await database.assets.insert_one(document)
        return document

    create = AsyncMock(side_effect=create_asset)
    monkeypatch.setattr(routes.assets, "buat_aset_draft", create)
    return database, create


def _row(satker=SATKER_A, name="Laptop A", nup="1"):
    return {"kode_barang": CODE, "nup": nup, "nama_barang": name,
            "nilai_perolehan": 15000000, "tanggal_perolehan": "2024-03-01",
            "merk": "Lenovo", "tipe": "T14", "kondisi": "Baik",
            "kode_register": "", "kode_satker": satker, "nama_satker": f"Satker {satker}"}


async def _seed(database, rows, *, target_full="", target_code=SATKER_A):
    await database.inventory_activities.insert_many([
        {"id": "activity-a", "nama_kegiatan": "Inventarisasi A", "kode_satker": target_code,
         "kode_satker_lengkap": target_full},
        {"id": "activity-b", "nama_kegiatan": "Inventarisasi B", "kode_satker": SATKER_B},
    ])
    await database.siman_imports.insert_one({
        "id": "import", "kode_satker": "", "filename": "siman.xlsx", "baris_belum_tercatat": rows,
    })


async def _draft():
    return await _unwrap(rs.buat_draft_dari_siman)(
        request=None, import_id="import", payload=rs.BuatDraftSimanIn(activity_id="activity-a"), user=ADMIN)


async def _snapshot(database):
    return {name: await database[name].find({}, {"_id": 0}).sort("id").to_list(None)
            for name in ("assets", "siman_imports", "mutasi_bmn", "inventory_activities")}


def test_foreign_asset_same_goods_and_nup_does_not_block_own_satker_draft(context):
    async def scenario():
        database, create = context
        await _seed(database, [_row()])
        await database.assets.insert_one({
            "id": "foreign", "activity_id": "activity-b", "asset_code": CODE, "NUP": "1", "version": 7,
        })
        foreign_before = await database.assets.find_one({"id": "foreign"}, {"_id": 0})

        result = await _draft()

        assert result["dibuat"] == 1
        assert result["dilewati_sudah_ada"] == 0
        create.assert_awaited_once()
        created = await database.assets.find_one({"activity_id": "activity-a"})
        assert created["siman"]["kode_satker"] == SATKER_A
        assert created["siman"]["kode_satker_aset"] == SATKER_A
        assert await database.assets.find_one({"id": "foreign"}, {"_id": 0}) == foreign_before

    _run(scenario())


def test_same_satker_existing_asset_is_skipped_even_in_another_activity(context):
    async def scenario():
        database, create = context
        await _seed(database, [_row()])
        await database.inventory_activities.insert_one({"id": "older-a", "kode_satker": SATKER_A})
        await database.assets.insert_one({"id": "existing", "activity_id": "older-a", "asset_code": CODE, "NUP": 1})

        result = await _draft()

        assert result["dibuat"] == 0
        assert result["dilewati_sudah_ada"] == 1
        create.assert_not_awaited()

    _run(scenario())


@pytest.mark.parametrize("reverse", [False, True])
def test_mixed_workbook_only_creates_rows_of_target_activity_satker(context, reverse):
    async def scenario():
        database, create = context
        rows = [_row(SATKER_A, "Laptop A"), _row(SATKER_B, "Laptop B")]
        await _seed(database, list(reversed(rows)) if reverse else rows)

        result = await _draft()

        assert result["dibuat"] == 1
        assert result["sisa"] == 0
        assert result["dilewati_satker_lain"] == 1
        create.assert_awaited_once()
        created_input = create.await_args.args[0]
        assert created_input.asset_name == "Laptop A"
        assert created_input.activity_id == "activity-a"
        assert await database.assets.count_documents({"siman.kode_satker": SATKER_B}) == 0

    _run(scenario())


def test_repeat_draft_skips_existing_own_satker_asset(context):
    async def scenario():
        database, create = context
        await _seed(database, [_row()])

        first = await _draft()
        second = await _draft()

        assert first["dibuat"] == 1
        assert second["dibuat"] == 0
        assert second["dilewati_sudah_ada"] == 1
        assert second["sisa"] == 0
        create.assert_awaited_once()
        assert await database.assets.count_documents({}) == 1

    _run(scenario())


def test_full_satker_same_six_digit_segment_does_not_cross_draft_targets(context):
    async def scenario():
        database, create = context
        await _seed(database, [_row(FULL_B, "Wrong location"), _row(FULL_A, "Correct location")], target_full=FULL_A)

        result = await _draft()

        assert result["dibuat"] == 1
        assert result["sisa"] == 0
        assert result["dilewati_satker_lain"] == 1
        create.assert_awaited_once()
        assert create.await_args.args[0].asset_name == "Correct location"
        created = await database.assets.find_one({"activity_id": "activity-a"})
        assert created["siman"]["kode_satker"] == FULL_A
        assert created["siman"]["kode_satker_aset"] == FULL_A

    _run(scenario())


@pytest.mark.parametrize("target_full,source", [("", SATKER_B), (FULL_A, FULL_B)])
def test_wrong_satker_target_rejected_before_creating_any_asset(context, target_full, source):
    async def scenario():
        database, create = context
        await _seed(database, [_row(source)], target_full=target_full)
        before = await _snapshot(database)

        with pytest.raises(HTTPException) as error:
            await _draft()

        assert error.value.status_code == 400
        assert "satker" in str(error.value.detail).lower()
        create.assert_not_awaited()
        assert await _snapshot(database) == before
        rs.log_audit.assert_not_awaited()

    _run(scenario())


def test_legacy_import_without_source_satker_cannot_create_draft(context):
    async def scenario():
        database, create = context
        row = _row()
        del row["kode_satker"]
        await _seed(database, [row])
        before = await _snapshot(database)

        with pytest.raises(HTTPException) as error:
            await _draft()

        assert error.value.status_code == 409
        assert "satker" in str(error.value.detail).lower()
        create.assert_not_awaited()
        assert await _snapshot(database) == before

    _run(scenario())


def test_target_without_satker_identity_cannot_create_draft(context):
    async def scenario():
        database, create = context
        await _seed(database, [_row()], target_code="")

        with pytest.raises(HTTPException) as error:
            await _draft()

        assert error.value.status_code == 400
        create.assert_not_awaited()
        assert await database.assets.count_documents({}) == 0

    _run(scenario())


def test_csv_includes_source_satker_for_identical_goods_and_nup(context):
    async def scenario():
        database, _create = context
        await _seed(database, [_row(FULL_A, "Laptop A"), _row(FULL_B, "Laptop B")])

        response = await rs.csv_belum_tercatat("import", _user=ADMIN)
        chunks = [chunk async for chunk in response.body_iterator]
        payload = b"".join(chunk if isinstance(chunk, bytes) else chunk.encode() for chunk in chunks)
        records = list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig"))))

        assert len(records) == 2
        assert [record["Kode Satker"] for record in records] == [FULL_A, FULL_B]
        assert [record["Nama Satker"] for record in records] == [f"Satker {FULL_A}", f"Satker {FULL_B}"]
        assert {record["Kode Barang"] for record in records} == {CODE}
        assert {record["NUP"] for record in records} == {"1"}

    _run(scenario())


def test_draft_rejects_parent_identity_changed_after_initial_read(context, monkeypatch):
    async def scenario():
        database, create = context
        await _seed(database, [_row()])
        source_before = await database.siman_imports.find_one({"id": "import"}, {"_id": 0})
        original_identity = rs._identitas_satker_aset
        first = True

        async def change_parent_after_read(assets):
            nonlocal first
            identities = await original_identity(assets)
            if first:
                first = False
                await database.inventory_activities.update_one(
                    {"id": "activity-a"}, {"$set": {"kode_satker": SATKER_B}})
            return identities

        monkeypatch.setattr(rs, "_identitas_satker_aset", change_parent_after_read)

        with pytest.raises(HTTPException) as error:
            await _draft()

        assert error.value.status_code == 409
        create.assert_not_awaited()
        assert await database.assets.count_documents({}) == 0
        assert await database.mutasi_bmn.count_documents({}) == 0
        assert await database.siman_imports.find_one({"id": "import"}, {"_id": 0}) == source_before
        assert (await database.inventory_activities.find_one({"id": "activity-a"}))["kode_satker"] == SATKER_B
        rs.log_audit.assert_not_awaited()

    _run(scenario())
