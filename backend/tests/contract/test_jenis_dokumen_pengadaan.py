"""Penyimpanan nyata, OCC, idempotensi, proyeksi dan ekspor jenis pengadaan."""
import csv
import io
import uuid

import openpyxl
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]
FIELD = "jenis_dokumen_pengadaan"
PILIHAN = ("", "Kontrak", "Non Kontrak/Penerimaan Barang", "Kontrak BLU", "Non Kontrak BLU")


async def test_jenis_pengadaan_tersimpan_dan_terekspor(contract):
    kategori = "Jenis pengadaan " + uuid.uuid4().hex
    records = []
    for i, jenis in enumerate(PILIHAN):
        data = {"asset_code": f"pgd-{uuid.uuid4().hex}", "NUP": str(i), "asset_name": "Meja uji",
                "category": kategori, "activity_id": "contract-activity-a", FIELD: jenis,
                "nomor_kontrak": "K-arsip", "cara_bayar_kontrak": "Sekaligus",
                "nomor_bukti_perolehan": "KW-1"}
        created = await contract.http.post("/api/assets", headers=contract.headers["a"], json=data)
        assert created.status_code == 200, created.text
        assert created.json()[FIELD] == jenis
        records.append(created.json())

    params = {"activity_id": "contract-activity-a", "category": kategori}
    for url in ("/api/assets", "/api/assets/offline-snapshot"):
        r = await contract.http.get(url, params=params, headers=contract.headers["a"])
        assert r.status_code == 200, r.text
        found = {a["id"]: a.get(FIELD) for a in r.json()["items"]}
        assert all(found[a["id"]] == a[FIELD] for a in records)
    r = await contract.http.get("/api/export/csv", params=params, headers=contract.headers["a"])
    assert r.status_code == 200, r.text
    rows = list(csv.reader(r.text.splitlines()))
    header = next(row for row in rows if FIELD in row)
    assert all(next(row for row in rows if a["asset_code"] in row)[header.index(FIELD)] == a[FIELD] for a in records)
    r = await contract.http.get("/api/export/xlsx", params=params, headers=contract.headers["a"])
    assert r.status_code == 200
    wb = openpyxl.load_workbook(io.BytesIO(r.content), read_only=True)
    rows = list(wb["Data Aset"].values)
    wb.close()
    header = next(row for row in rows if "Jenis Dokumen Pengadaan" in row)
    assert all((next(row for row in rows if a["asset_code"] in row)[header.index("Jenis Dokumen Pengadaan")] or "") == a[FIELD] for a in records)

    aid = records[1]["id"]
    url = f"/api/assets/{aid}"
    headers = {**contract.headers["a"], "If-Match": str(records[1]["version"])}
    invalid = await contract.http.patch(url, headers=headers, json={FIELD: "salah"})
    assert invalid.status_code == 422
    foreign = await contract.http.patch(url, headers=contract.headers["b"], json={FIELD: "Kontrak BLU"})
    assert foreign.status_code == 403
    idem = {**headers, "Idempotency-Key": uuid.uuid4().hex}
    patch = await contract.http.patch(url, headers=idem, json={FIELD: "Non Kontrak BLU"})
    assert patch.status_code == 200, patch.text
    assert patch.json()["nomor_kontrak"] == "K-arsip"
    replay = await contract.http.patch(url, headers=idem, json={FIELD: "Non Kontrak BLU"})
    assert replay.status_code == 200 and replay.json()["version"] == patch.json()["version"]
    stale = await contract.http.patch(url, headers=headers, json={FIELD: "Kontrak BLU"})
    assert stale.status_code == 409
    old_client = {k: records[1][k] for k in ("asset_code", "asset_name", "category", "activity_id", "NUP")}
    put = await contract.http.put(url, headers={**headers, "If-Match": str(patch.json()["version"])}, json=old_client)
    assert put.status_code == 200, put.text
    assert put.json()[FIELD] == "Non Kontrak BLU"


async def test_impor_tanpa_kolom_baru_mempertahankan_jenis_lama(contract):
    kode = f"3{uuid.uuid4().int % 10**9:09d}"
    category = "Impor pengadaan " + uuid.uuid4().hex
    await contract.db.categories.insert_one({"kode_aset": kode, "label": category})
    data = {"asset_code": kode, "NUP": "1", "asset_name": "Meja impor",
            "category": category, "activity_id": "contract-activity-a", FIELD: "Kontrak BLU"}
    created = await contract.http.post("/api/assets", headers=contract.headers["root"], json=data)
    assert created.status_code == 200, created.text
    aid = created.json()["id"]
    for explicit in (False, True):
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        columns = ["asset_code", "NUP", "asset_name", "category"] + ([FIELD] if explicit else [])
        writer.writerow(columns)
        writer.writerow([data.get(key, "") if key != FIELD else "" for key in columns])
        r = await contract.http.post("/api/import", headers=contract.headers["root"],
            params={"activity_id": "contract-activity-a", "force_update": "true"},
            files={"file": ("pengadaan.csv", buffer.getvalue().encode(), "text/csv")})
        assert r.status_code == 200 and r.json()["success"], r.text
        stored = await contract.db.assets.find_one({"id": aid})
        assert stored[FIELD] == ("" if explicit else "Kontrak BLU")
