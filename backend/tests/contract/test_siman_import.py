"""Actual ASGI multipart + Mongo bulk import; no mongomock compatibility shim."""

import io
import uuid

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]


def _workbook(satker):
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Master Aset"
    sheet.append([
        "Kode Barang", "NUP", "Nama Barang", "Nilai Perolehan", "Merk",
        "Tipe", "Kondisi", "Tanggal Perolehan", "Nama Pengguna",
        "Kode Register", "Kode Satker", "Umur Aset", "Nilai Penyusutan", "Nilai Buku",
    ])
    for index, code in enumerate(("3999700001", "3999800001"), 1):
        sheet.append([
            code, "1", "Laptop", "16000000", "Lenovo", "T14", "Baik",
            "2024-03-01", "Budi", f"SIMAN-REG-{index}", satker,
            "7", "2000000", "14000000",
        ])
    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


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
