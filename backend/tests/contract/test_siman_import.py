"""Actual ASGI multipart + Mongo bulk import; no mongomock compatibility shim."""

import io
import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]


def _workbook(satker):
    return _workbook_rows([
        {"code": code, "register": f"SIMAN-REG-{index}", "satker": satker}
        for index, code in enumerate(("3999700001", "3999800001"), 1)
    ])


def _workbook_rows(rows):
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Master Aset"
    sheet.append([
        "Kode Barang", "NUP", "Nama Barang", "Nilai Perolehan", "Merk",
        "Tipe", "Kondisi", "Tanggal Perolehan", "Nama Pengguna",
        "Kode Register", "Kode Satker", "Umur Aset", "Nilai Penyusutan", "Nilai Buku",
    ])
    for row in rows:
        sheet.append([
            row.get("code", "3999600001"), "1", "Laptop", "16000000",
            row.get("brand", "Lenovo"), "T14", "Baik", "2024-03-01", "Budi",
            row.get("register", "SIMAN-SHARED-REGISTER"), row["satker"],
            "7", "2000000", "14000000",
        ])
    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


@asynccontextmanager
async def _satker_case(contract, activities, *, user_satker=""):
    """Only generated users/activities/assets in the fixture's temporary DB.

    The importer has a per-principal quota, so every scenario gets its own
    real stored principal instead of exhausting the shared contract user.
    Asset satker identity intentionally exists on its activity only.
    """
    from auth_utils import create_token

    suffix = uuid.uuid4().hex
    user_id = "siman-scope-user-" + suffix
    activity_ids = {name: "siman-scope-activity-" + name + "-" + suffix
                    for name in activities}
    asset_ids = {name: "siman-scope-asset-" + name + "-" + suffix
                 for name in activities}
    await contract.db.users.insert_one({
        "id": user_id, "username": user_id, "name": "Kontrak scope SIMAN",
        "role": "admin", "is_active": True, "kode_satker": user_satker,
    })
    for name, identity in activities.items():
        await contract.db.inventory_activities.insert_one({
            "id": activity_ids[name], **identity,
        })
        await contract.db.assets.insert_one({
            "id": asset_ids[name], "activity_id": activity_ids[name],
            "asset_code": "3999600001", "NUP": "1", "category": "Laptop",
            "asset_name": "Laptop", "purchase_price": "16000000",
            "brand": "Lenovo", "model": "T14", "condition": "Baik",
            "purchase_date": "2024-03-01", "user": "Budi", "version": 1,
            "created_at": "2026-10-15T00:00:00+00:00",
            # A register is deliberately shared across the distinct satkers.
            "kode_register": "SIMAN-SHARED-REGISTER",
        })
    state = SimpleNamespace(
        headers={"Authorization": "Bearer " + create_token(user_id, user_id)},
        assets=asset_ids, activities=activity_ids, user=user_id,
    )
    try:
        yield state
    finally:
        owned_assets = [asset["id"] async for asset in contract.db.assets.find(
            {"activity_id": {"$in": list(activity_ids.values())}}, {"id": 1})]
        await contract.db.mutasi_bmn.delete_many({"asset_id": {"$in": owned_assets}})
        await contract.db.audit_logs.delete_many({"$or": [
            {"activity_id": {"$in": list(activity_ids.values())}}, {"username": user_id},
        ]})
        await contract.db.assets.delete_many({"activity_id": {"$in": list(activity_ids.values())}})
        await contract.db.inventory_activities.delete_many({"id": {"$in": list(activity_ids.values())}})
        await contract.db.users.delete_one({"id": user_id})
        await contract.db.siman_imports.delete_many({"oleh": user_id})
        await contract.db.masa_manfaat.delete_one({"kode": "39996"})


async def _import_rows(contract, headers, rows, *, mark_missing=False):
    return await contract.http.post(
        "/api/siman/import", headers=headers,
        params={"tandai_tidak_ditemukan": str(mark_missing).lower()},
        files={"file": ("satker.xlsx", _workbook_rows(rows),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )


def _assert_own_reference(asset, *, satker, brand):
    assert asset["version"] == 2
    assert asset["siman"]["kode_satker"] == satker
    assert asset["siman"]["status"] == "selisih"
    assert [difference["siman"] for difference in asset["siman"]["selisih"]
            if difference["field"] == "brand"] == [brand]


async def test_siman_bulk_versions_upsert_and_satker_isolation(contract):
    from auth_utils import create_token

    suffix = uuid.uuid4().hex
    satker = "siman-" + suffix
    user_id = "siman-user-" + suffix
    activity_id = "siman-activity-" + suffix
    ids = ["siman-" + name + "-" + suffix for name in ("match", "protected", "missing", "foreign")]
    protected = {"kode": "39998", "tahun": 12, "sumber": "input satker", "note": "preserve"}
    await contract.db.users.insert_one({
        "id": user_id, "username": user_id, "name": "Kontrak SIMAN", "role": "admin",
        "is_active": True, "kode_satker": satker,
    })
    headers = {"Authorization": "Bearer " + create_token(user_id, user_id)}
    await contract.db.inventory_activities.insert_one({"id": activity_id, "kode_satker": satker})
    common = {
        "activity_id": activity_id, "NUP": "1", "category": "Laptop", "asset_name": "Laptop",
        "purchase_price": "16000000", "brand": "Lenovo", "model": "T14", "condition": "Baik",
        "purchase_date": "2024-03-01", "user": "Budi", "version": 1,
    }
    await contract.db.assets.insert_many([
        {**common, "id": ids[0], "asset_code": "3999700001"},
        {**common, "id": ids[1], "asset_code": "3999800001"},
        {**common, "id": ids[2], "asset_code": "3999900001"},
        {**common, "id": ids[3], "asset_code": "3999700001", "activity_id": "contract-activity-b", "version": 7},
    ])
    await contract.db.masa_manfaat.insert_one(dict(protected))
    imports = []
    try:
        created_at = None
        for expected_version in (2, 3):
            response = await contract.http.post(
                "/api/siman/import", params={"tandai_tidak_ditemukan": "true"}, headers=headers,
                files={"file": ("siman.xlsx", _workbook(satker),
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )
            assert response.status_code == 200, response.text
            result = response.json()
            imports.append(result["id"])
            assert result["sheet"] == "Master Aset"
            assert result["total_baris"] == 2
            assert result["ringkasan"]["aset_dicek"] == 2
            assert result["ringkasan"]["cocok"] == 2
            for identifier in ids[:2]:
                asset = await contract.db.assets.find_one({"id": identifier})
                assert asset["version"] == expected_version
                assert asset["siman"]["status"] == "cocok"
                assert asset["siman"]["import_id"] == result["id"]
                assert asset["kode_register"].startswith("SIMAN-REG-")
            missing = await contract.db.assets.find_one({"id": ids[2]})
            assert missing["version"] == expected_version
            assert missing["siman"]["status"] == "tidak_di_siman"
            foreign = await contract.db.assets.find_one({"id": ids[3]})
            assert foreign["version"] == 7
            assert "siman" not in foreign and "kode_register" not in foreign
            reference = await contract.db.masa_manfaat.find_one({"kode": "39997"})
            assert reference["tahun"] == 4 and reference["sumber"] == "siman"
            assert reference["observasi"] == 1
            if created_at is not None:
                assert reference["created_at"] == created_at
            created_at = reference["created_at"]
            assert await contract.db.masa_manfaat.count_documents({"kode": "39997"}) == 1
            assert await contract.db.masa_manfaat.find_one({"kode": "39998"}, {"_id": 0}) == protected
            saved = await contract.db.siman_imports.find_one({"id": result["id"]})
            assert saved["kode_satker"] == satker
            assert saved["register_diadopsi"] == (2 if expected_version == 2 else 0)
    finally:
        await contract.db.assets.delete_many({"id": {"$in": ids}})
        await contract.db.masa_manfaat.delete_many({"kode": {"$in": ["39997", "39998"]}})
        await contract.db.siman_imports.delete_many({"id": {"$in": imports}})
        await contract.db.inventory_activities.delete_one({"id": activity_id})
        await contract.db.users.delete_one({"id": user_id})


@pytest.mark.parametrize("mixed,mark_missing", [
    pytest.param(False, False, id="single-satker"),
    pytest.param(False, True, id="single-satker-mark-missing"),
    pytest.param(True, False, id="mixed-satker"),
])
async def test_pusat_active_satker_does_not_reuse_other_satker_row(
        contract, mixed, mark_missing):
    """Identical barang/NUP/register cannot borrow the other satker's brand."""
    identities = {"a": {"kode_satker": "621001"}, "b": {"kode_satker": "621002"}}
    async with _satker_case(contract, identities) as case:
        # The optional missing marker must also leave a genuinely absent B
        # asset untouched, not just the B asset sharing A's lookup keys.
        missing_b = case.assets["b"] + "-missing"
        await contract.db.assets.insert_one({
            "id": missing_b, "activity_id": case.activities["b"],
            "asset_code": "3999600002", "NUP": "2", "version": 7,
        })
        rows = [{"satker": "621001", "brand": "Merk satker A"}]
        if mixed:
            rows.append({"satker": "621002", "brand": "Merk satker B"})
        original_b = await contract.db.assets.find_one({"id": case.assets["b"]})
        original_missing = await contract.db.assets.find_one({"id": missing_b})
        response = await _import_rows(
            contract, {**case.headers, "X-Satker-Aktif": "621001"}, rows,
            mark_missing=mark_missing,
        )
        assert response.status_code == 200, response.text
        assert response.json()["ringkasan"]["aset_dicek"] == 1
        own = await contract.db.assets.find_one({"id": case.assets["a"]})
        _assert_own_reference(own, satker="621001", brand="Merk satker A")
        assert await contract.db.assets.find_one({"id": case.assets["b"]}) == original_b
        assert await contract.db.assets.find_one({"id": missing_b}) == original_missing

        if mixed:
            # Reusing the exact same mixed file under B's active scope must
            # select its second row even though all ordinary keys collide.
            response_b = await _import_rows(
                contract, {**case.headers, "X-Satker-Aktif": "621002"}, rows,
            )
            assert response_b.status_code == 200, response_b.text
            assert response_b.json()["ringkasan"]["aset_dicek"] == 1
            other = await contract.db.assets.find_one({"id": case.assets["b"]})
            _assert_own_reference(other, satker="621002", brand="Merk satker B")
            assert await contract.db.assets.find_one({"id": case.assets["a"]}) == own


@pytest.mark.parametrize("file_code", ["621001", "126011600621001000KP"])
async def test_siman_short_and_full_satker_code_match_the_same_activity(contract, file_code):
    identities = {"a": {"kode_satker": "621001", "kode_satker_lengkap": "126011600621001000KP"}}
    async with _satker_case(contract, identities, user_satker="621001") as case:
        response = await _import_rows(
            contract, case.headers, [{"satker": file_code, "brand": "Merk satker A"}],
        )
        assert response.status_code == 200, response.text
        assert response.json()["ringkasan"]["aset_dicek"] == 1
        own = await contract.db.assets.find_one({"id": case.assets["a"]})
        _assert_own_reference(own, satker=file_code, brand="Merk satker A")


async def test_siman_full_satker_code_keeps_wilayah_and_subsatker_distinct(contract):
    identities = {
        "a": {"kode_satker": "621001", "kode_satker_lengkap": "126011600621001000KP"},
        "other-wilayah": {"kode_satker": "621001", "kode_satker_lengkap": "126011601621001000KP"},
        "other-sub": {"kode_satker": "621001", "kode_satker_lengkap": "126011600621001001KP"},
    }
    async with _satker_case(contract, identities, user_satker="621001") as case:
        others_before = [await contract.db.assets.find_one({"id": case.assets[name]})
                         for name in ("other-wilayah", "other-sub")]
        response = await _import_rows(
            contract, case.headers,
            [{"satker": "126011600621001000KP", "brand": "Merk wilayah asal"}],
            mark_missing=True,
        )
        assert response.status_code == 200, response.text
        assert response.json()["ringkasan"]["aset_dicek"] == 1
        own = await contract.db.assets.find_one({"id": case.assets["a"]})
        _assert_own_reference(own, satker="126011600621001000KP", brand="Merk wilayah asal")
        for before in others_before:
            assert await contract.db.assets.find_one({"id": before["id"]}) == before


@pytest.mark.parametrize("unscoped_pusat", [False, True], ids=["foreign-file", "pusat-no-active-satker"])
async def test_siman_rejected_satker_import_has_no_data_writes(contract, unscoped_pusat):
    identities = {"a": {"kode_satker": "621001"}, "b": {"kode_satker": "621002"}}
    async with _satker_case(
            contract, identities, user_satker="" if unscoped_pusat else "621001") as case:
        asset_query = {"id": {"$in": list(case.assets.values())}}
        assets_before = await contract.db.assets.find(asset_query).sort("id").to_list(None)
        references_before = await contract.db.masa_manfaat.find({}).sort("kode").to_list(None)
        imports_before = await contract.db.siman_imports.count_documents({})
        response = await _import_rows(
            contract, case.headers, [{"satker": "621002", "brand": "Foreign brand"}],
            mark_missing=True,
        )
        assert response.status_code == 400, response.text
        assert await contract.db.assets.find(asset_query).sort("id").to_list(None) == assets_before
        assert await contract.db.masa_manfaat.find({}).sort("kode").to_list(None) == references_before
        assert await contract.db.siman_imports.count_documents({}) == imports_before


async def test_siman_unmatched_row_creates_own_draft_despite_foreign_duplicate(contract):
    """The complete import→draft path scopes duplicate detection to its satker."""
    identities = {"a": {"kode_satker": "621001"}, "b": {"kode_satker": "621002"}}
    async with _satker_case(contract, identities, user_satker="621001") as case:
        # A has no asset yet; B owns the same barang, NUP and register.
        await contract.db.assets.delete_one({"id": case.assets["a"]})
        await contract.db.assets.update_one({"id": case.assets["b"]}, {"$set": {"version": 7}})
        foreign_before = await contract.db.assets.find_one({"id": case.assets["b"]})
        imported = await _import_rows(
            contract, case.headers, [{"satker": "621001", "brand": "Merk draft A"}],
        )
        assert imported.status_code == 200, imported.text
        summary = imported.json()["ringkasan"]
        assert summary["aset_dicek"] == 0
        assert summary["siman_tanpa_aset"] == 1
        import_id = imported.json()["id"]
        url = f"/api/siman/import/{import_id}/buat-draft"
        payload = {"activity_id": case.activities["a"]}

        created = await contract.http.post(url, headers=case.headers, json=payload)
        assert created.status_code == 200, created.text
        assert created.json()["dibuat"] == 1
        assert created.json()["dilewati_sudah_ada"] == 0
        assert created.json()["gagal"] == []
        assert created.json()["sisa"] == 0
        drafts = await contract.db.assets.find({"activity_id": case.activities["a"]}).to_list(None)
        assert len(drafts) == 1
        draft = drafts[0]
        assert (draft["asset_code"], draft["NUP"], draft["brand"]) == (
            "3999600001", "1", "Merk draft A")
        assert draft["siman"]["kode_satker"] == "621001"
        assert draft["siman"]["kode_satker_aset"] == "621001"
        assert draft["siman"]["import_id"] == import_id

        repeated = await contract.http.post(url, headers=case.headers, json=payload)
        assert repeated.status_code == 200, repeated.text
        assert repeated.json()["dibuat"] == 0
        assert repeated.json()["dilewati_sudah_ada"] == 1
        assert repeated.json()["gagal"] == []
        assert repeated.json()["sisa"] == 0
        assert await contract.db.assets.count_documents({"activity_id": case.activities["a"]}) == 1
        assert await contract.db.assets.find_one({"id": case.assets["b"]}) == foreign_before


@pytest.mark.parametrize("source_b", ["621002", "126011600621002000KP"])
async def test_siman_reads_revalidate_saved_references_when_active_satker_changes(contract, source_b):
    """Historical marks must not become actionable merely by switching satker."""
    full_a, full_b = "126011600621001000KP", "126011600621002000KP"
    identities = {
        "a": {"kode_satker": "621001", "kode_satker_lengkap": full_a},
        "b": {"kode_satker": "621002", "kode_satker_lengkap": full_b},
    }
    async with _satker_case(contract, identities) as case:
        difference = [{"field": "brand", "label": "Merk", "aman": "Old", "siman": "New"}]
        valid_a = {"status": "selisih", "selisih": difference,
                   "kode_satker": full_a, "kode_satker_aset": full_a}
        valid_b = {"status": "selisih", "selisih": difference,
                   "kode_satker": source_b, "kode_satker_aset": full_b}
        for name, reference in (("a", valid_a), ("b", valid_b)):
            await contract.db.assets.update_one(
                {"id": case.assets[name]}, {"$set": {"siman": reference}})
        invalid = {
            "foreign": {"status": "selisih", "selisih": difference,
                        "kode_satker": full_a, "kode_satker_aset": full_b},
            "legacy": {"status": "selisih", "selisih": difference},
            "missing-owner": {"status": "selisih", "selisih": difference,
                              "kode_satker": source_b},
        }
        invalid_ids = set()
        for index, (name, reference) in enumerate(invalid.items()):
            identifier = case.assets["b"] + "-" + name
            invalid_ids.add(identifier)
            await contract.db.assets.insert_one({
                "id": identifier, "activity_id": case.activities["b"],
                # These sort before the valid asset: filtering after limit
                # would return an empty first page or an incorrect total.
                "asset_code": f"299960000{index}", "NUP": "1", "version": 7,
                "asset_name": name, "category": "Laptop", "siman": reference,
                "created_at": "2026-10-15T00:00:00+00:00",
            })
        history = [
            {"id": case.user + "-history-a", "kode_satker": "621001", "waktu": "2099-01-01"},
            {"id": case.user + "-history-b", "kode_satker": "621002", "waktu": "2099-01-02"},
            {"id": case.user + "-history-blank", "kode_satker": "", "waktu": "2099-01-04",
             "validasi_satker": {"kode_file": [full_a]}},
            {"id": case.user + "-history-missing", "waktu": "2099-01-03"},
        ]
        await contract.db.siman_imports.insert_many([
            {**row, "oleh": case.user, "filename": "historical-siman.xlsx"} for row in history])
        owned_query = {"activity_id": {"$in": list(case.activities.values())}}
        assets_before = await contract.db.assets.find(owned_query).sort("id").to_list(None)
        history_before = await contract.db.siman_imports.find({"oleh": case.user}).sort("id").to_list(None)

        for name, code, expected_unchecked in (("a", "621001", 0), ("b", "621002", 3)):
            headers = {**case.headers, "X-Satker-Aktif": code}
            summary = await contract.http.get("/api/siman/ringkasan", headers=headers)
            assert summary.status_code == 200, summary.text
            body = summary.json()
            assert (body["selisih"], body["cocok"], body["tidak_di_siman"], body["belum_dicek"]) == (
                1, 0, 0, expected_unchecked)
            assert [row["id"] for row in body["riwayat"]] == [case.user + "-history-" + name]
            assert body["import_terakhir"]["id"] == case.user + "-history-" + name
            assert sum(row["selisih"] for row in body["per_kegiatan"]) == 1
            assert {row["activity_id"] for row in body["per_kegiatan"]} == {case.activities[name]}
            listed = await contract.http.get(
                "/api/siman/selisih", headers=headers, params={"page_size": 1})
            assert listed.status_code == 200, listed.text
            assert listed.json()["total"] == 1
            assert [row["id"] for row in listed.json()["items"]] == [case.assets[name]]

        headers_b = {**case.headers, "X-Satker-Aktif": "621002"}
        for name in ("a", "blank", "missing"):
            history_id = case.user + "-history-" + name
            for suffix in ("", "/belum-tercatat.csv"):
                denied = await contract.http.get(
                    f"/api/siman/import/{history_id}{suffix}", headers=headers_b)
                assert denied.status_code == 403, denied.text
        for suffix in ("", "/belum-tercatat.csv"):
            own_history = await contract.http.get(
                f"/api/siman/import/{case.user}-history-b{suffix}", headers=headers_b)
            assert own_history.status_code == 200, own_history.text
        for endpoint in ("/api/assets", "/api/assets/offline-snapshot"):
            response = await contract.http.get(
                endpoint, headers=headers_b, params={"activity_id": case.activities["b"]})
            assert response.status_code == 200, response.text
            rows = {row["id"]: row for row in response.json()["items"]}
            assert set(rows) == {case.assets["b"], *invalid_ids}
            assert rows[case.assets["b"]]["siman"] == valid_b
            for identifier in invalid_ids:
                # Explicit null overwrites a previously cached wrong badge.
                assert "siman" in rows[identifier] and rows[identifier]["siman"] is None
        foreign_id = case.assets["b"] + "-foreign"
        for lightweight in (False, True):
            detail = await contract.http.get(
                "/api/assets/" + foreign_id, headers=headers_b,
                params={"exclude_media": str(lightweight).lower()})
            assert detail.status_code == 200, detail.text
            assert "siman" in detail.json() and detail.json()["siman"] is None
        assert await contract.db.assets.find(owned_query).sort("id").to_list(None) == assets_before
        assert await contract.db.siman_imports.find({"oleh": case.user}).sort("id").to_list(None) == history_before


async def test_siman_reads_hide_reference_after_parent_full_satker_identity_changes(contract):
    full_a, moved_full = "126011600621001000KP", "126011601621001000KP"
    identities = {"a": {"kode_satker": "621001", "kode_satker_lengkap": full_a}}
    async with _satker_case(contract, identities, user_satker="621001") as case:
        imported = await _import_rows(
            contract, case.headers, [{"satker": full_a, "brand": "Merk sebelum pindah"}],
        )
        assert imported.status_code == 200, imported.text
        assert imported.json()["ringkasan"]["selisih"] == 1
        await contract.db.inventory_activities.update_one(
            {"id": case.activities["a"]}, {"$set": {"kode_satker_lengkap": moved_full}})
        asset_before = await contract.db.assets.find_one({"id": case.assets["a"]})

        summary = await contract.http.get("/api/siman/ringkasan", headers=case.headers)
        assert summary.status_code == 200, summary.text
        assert summary.json()["selisih"] == 0
        assert summary.json()["belum_dicek"] == 1
        assert sum(row["selisih"] for row in summary.json()["per_kegiatan"]) == 0
        listed = await contract.http.get("/api/siman/selisih", headers=case.headers)
        assert listed.status_code == 200, listed.text
        assert listed.json()["total"] == 0 and listed.json()["items"] == []
        for endpoint in ("/api/assets", "/api/assets/offline-snapshot"):
            response = await contract.http.get(
                endpoint, headers=case.headers, params={"activity_id": case.activities["a"]})
            assert response.status_code == 200, response.text
            row = response.json()["items"][0]
            assert row["id"] == case.assets["a"]
            assert "siman" in row and row["siman"] is None
        for lightweight in (False, True):
            detail = await contract.http.get(
                "/api/assets/" + case.assets["a"], headers=case.headers,
                params={"exclude_media": str(lightweight).lower()})
            assert detail.status_code == 200, detail.text
            assert "siman" in detail.json() and detail.json()["siman"] is None
        applied = await contract.http.post(
            "/api/siman/terapkan/" + case.assets["a"], headers=case.headers,
            json={"fields": ["brand"]})
        assert applied.status_code == 409, applied.text
        assert await contract.db.assets.find_one({"id": case.assets["a"]}) == asset_before
