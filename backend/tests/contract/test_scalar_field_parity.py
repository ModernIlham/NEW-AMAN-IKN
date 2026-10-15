"""One field's real patch/read/offline/export contract, including explicit clear."""
import csv
import io
import uuid

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]


async def test_heritage_scalar_patch_offline_and_csv_parity(contract):
    code = "OPT23-" + uuid.uuid4().hex
    created = await contract.http.post("/api/assets", headers=contract.headers["a"], json={
        "asset_code": code, "asset_name": "Benda sejarah sintetis", "NUP": "1",
        "category": "Peralatan dan Mesin", "activity_id": "contract-activity-a"})
    assert created.status_code == 200, created.text
    identifier, version = created.json()["id"], created.json()["version"]
    for value in ("Ya", ""):
        updated = await contract.http.patch("/api/assets/" + identifier,
            headers={**contract.headers["a"], "If-Match": str(version)},
            json={"barang_bersejarah": value})
        assert updated.status_code == 200, updated.text
        version = updated.json()["version"]
        detail = await contract.http.get("/api/assets/" + identifier, headers=contract.headers["a"])
        assert detail.json()["barang_bersejarah"] == value
        offline = await contract.http.get("/api/assets/offline-snapshot",
            params={"activity_id": "contract-activity-a"}, headers=contract.headers["a"])
        assert offline.status_code == 200, offline.text
        rows = offline.json().get("items", offline.json().get("assets", []))
        assert next(row for row in rows if row["id"] == identifier)["barang_bersejarah"] == value
        exported = await contract.http.get("/api/export/csv", params={"activity_id": "contract-activity-a"},
                                           headers=contract.headers["a"])
        assert exported.status_code == 200, exported.text
        lines = [line for line in exported.content.decode("utf-8-sig").splitlines() if not line.startswith("#")]
        data = list(csv.DictReader(io.StringIO("\n".join(lines))))
        assert next(row for row in data if row["asset_code"] == code)["barang_bersejarah"] == value
