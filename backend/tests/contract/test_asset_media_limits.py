"""Actual mutation limits, byte-preserving legacy edits and resilient list CSV."""
import base64
import uuid

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]
PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jhV8AAAAASUVORK5CYII="
PDF = "data:application/pdf;base64," + base64.b64encode(b"%PDF-1.7\nexact signed bytes /ByteRange [0 1 2 3]\n%%EOF").decode()


def payload(**changes):
    return {"asset_code": "media-" + uuid.uuid4().hex, "NUP": "1", "asset_name": "Media limits",
        "category": "Media limits", "activity_id": "contract-activity-a", "purchase_price": "10", **changes}


async def test_new_checklist_limits_reject_before_any_media_commit(contract):
    before = await contract.db["fs.files"].count_documents({})
    data = payload(photos=[PNG], document_checklist=[{"name": "STNK", "photos": [PNG] * 4}])
    response = await contract.http.post("/api/assets", headers=contract.headers["a"], json=data)
    assert response.status_code == 413, response.text
    assert await contract.db["fs.files"].count_documents({}) == before
    assert not await contract.db.assets.find_one({"asset_code": data["asset_code"]})
    foreign = payload(document_checklist=[{"name": "STNK", "documents": [{"name": "foreign.pdf", "gridfs_id": "foreign"}]}])
    response = await contract.http.post("/api/assets", headers=contract.headers["a"], json=foreign)
    assert response.status_code == 400
    photos = await contract.http.post("/api/assets", headers=contract.headers["a"], json=payload(photos=[PNG] * 7))
    assert photos.status_code == 413


async def test_preserved_pdf_sentinel_reorder_uncheck_and_put_omission(contract):
    data = payload(document_checklist=[{"name": "STNK", "checked": True, "documents": [{"name": "signed.pdf", "data": PDF}]},
                                       {"name": "BPKB", "checked": False}])
    created = await contract.http.post("/api/assets", headers=contract.headers["a"], json=data)
    assert created.status_code == 200, created.text
    aid = created.json()["id"]
    changed = await contract.http.patch("/api/assets/" + aid, headers={**contract.headers["a"], "If-Match": "1"}, json={
        "document_checklist": [{"name": "BPKB", "checked": False}, {"name": "STNK", "checked": False,
            "documents": [{"name": "signed.pdf", "data": "__existing__:0"}]}]})
    assert changed.status_code == 200, changed.text
    doc = await contract.db.assets.find_one({"id": aid})
    assert doc["document_checklist"][1]["documents"][0]["data"] == PDF
    assert not doc["document_checklist"][1]["checked"]
    # PUT from an older scalar-only client must not remove attachments.
    put = await contract.http.put("/api/assets/" + aid, headers={**contract.headers["a"], "If-Match": "2"},
        json={key: value for key, value in data.items() if key != "document_checklist"})
    assert put.status_code == 200, put.text
    doc = await contract.db.assets.find_one({"id": aid})
    assert doc["document_checklist"][1]["documents"][0]["data"] == PDF
    served = await contract.http.get(f"/api/assets/{aid}/checklist/1/documents/0", headers=contract.headers["a"])
    assert served.status_code == 200 and served.content == base64.b64decode(PDF.split(",", 1)[1])


@pytest.mark.parametrize("checklist", ["legacy bad field", [{"name": "Bad arrays", "checked": False, "photos": "bad", "documents": "bad"}], [None, "broken"]])
async def test_legacy_bad_arrays_do_not_break_list_snapshot_or_csv(contract, checklist):
    data = payload(id="legacy-" + uuid.uuid4().hex, document_checklist=checklist, photos="bad", photo_gridfs_ids=None if isinstance(checklist, str) else "bad")
    await contract.db.assets.insert_one(data)
    for endpoint, params in [("/api/assets", {"category": "Media limits"}),
        ("/api/assets/offline-snapshot", {"activity_id": "contract-activity-a"}),
        ("/api/export/csv", {"activity_id": "contract-activity-a"}),
        ("/api/export/xlsx", {"activity_id": "contract-activity-a", "category": "Media limits"})]:
        response = await contract.http.get(endpoint, headers=contract.headers["a"], params=params)
        assert response.status_code == 200, response.text[:1000]
        if endpoint.endswith("/xlsx"):
            import io
            import openpyxl
            workbook = openpyxl.load_workbook(io.BytesIO(response.content), read_only=True)
            assert workbook.sheetnames
            workbook.close()
        elif endpoint.endswith("/csv"):
            import csv
            rows = list(csv.reader(response.text.splitlines()))
            header = next(row for row in rows if "jumlah_foto" in row)
            row = next(row for row in rows if data["asset_code"] in row)
            assert row[header.index("jumlah_foto")] == "0"
        else:
            items = response.json()["items"]
            assert data["id"] in {row["id"] for row in items}
