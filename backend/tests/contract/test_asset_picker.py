"""Picker traverses the authoritative scoped dataset, then saves exact IDs."""
import uuid
from unittest.mock import AsyncMock

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]


async def test_asset_picker_pages_exact_nup_and_psp_save(contract, monkeypatch):
    import routes.assets as ra

    prefix = "picker-" + uuid.uuid4().hex
    code = "3999901777"
    common = {"asset_code": code, "asset_name": "Laptop pemilih", "category": "Laptop",
              "activity_id": "contract-activity-a", "condition": "Baik", "version": 1,
              "created_at": "2026-10-28T00:00:00+00:00", "purchase_price": "35"}
    rows = [{**common, "id": f"{prefix}-{n:03}", "NUP": str(n)} for n in range(1, 36)]
    rows += [{**common, "id": prefix + "-350", "NUP": "350", "asset_name": "Laptop 35"},
             {**common, "id": prefix + "-foreign", "NUP": "35", "activity_id": "contract-activity-b"}]
    await contract.db.assets.insert_many(rows)
    # A nonempty stale/limited search index must not hide later NUP pages.
    index = AsyncMock(return_value=[rows[0]["id"]])
    monkeypatch.setattr(ra, "cari_id_aset", index)
    ids = [a["id"] for a in rows]
    sk_id = None
    try:
        base = {"search": code, "pencarian_lengkap": "true", "page_size": 20, "sort_by": "oldest"}
        pages = []
        for page in (1, 2):
            response = await contract.http.get("/api/assets", headers=contract.headers["a"], params={**base, "page": page})
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 36 and data["total_pages"] == 2
            pages.append([a["id"] for a in data["items"]])
        assert len(pages[0]) == 20 and len(pages[1]) == 16
        assert not set(pages[0]) & set(pages[1])
        assert set(pages[0] + pages[1]) == set(ids) - {prefix + "-foreign"}
        for nup in ("1", "001", "35"):
            response = await contract.http.get("/api/assets", headers=contract.headers["a"], params={**base, "nup": nup})
            assert response.status_code == 200
            assert [a["NUP"] for a in response.json()["items"]] == [str(int(nup))]
        stats = await contract.http.get("/api/assets/stats", headers=contract.headers["a"], params={**base, "nup": "35"})
        assert stats.status_code == 200 and stats.json()["total_assets"] == 1
        invalid = await contract.http.get("/api/assets", headers=contract.headers["a"], params={**base, "nup": "35x"})
        assert invalid.status_code == 400
        index.assert_not_awaited()
        selected = [pages[0][0], f"{prefix}-035"]
        created = await contract.http.post("/api/penggunaan/psp", headers=contract.headers["a"], json={
            "nomor_sk": "SK-PICKER-" + prefix, "tanggal_sk": "2026-01-01", "jenis": "psp",
            "asset_ids": selected,
        })
        assert created.status_code == 200
        record = await contract.db.psp.find_one({"nomor_sk": "SK-PICKER-" + prefix})
        sk_id = record["id"]
        assert {a["asset_id"] for a in record["aset"]} == set(selected)
        assert {a["NUP"] for a in record["aset"]} == {"1", "35"}
        denied = await contract.http.post("/api/penggunaan/psp", headers=contract.headers["a"], json={
            "nomor_sk": "SK-FOREIGN-" + prefix, "tanggal_sk": "2026-01-01", "jenis": "psp",
            "asset_ids": [prefix + "-foreign"],
        })
        assert denied.status_code == 403
        assert await contract.db.psp.count_documents({"nomor_sk": "SK-FOREIGN-" + prefix}) == 0
    finally:
        await contract.db.assets.delete_many({"id": {"$in": ids}})
        if sk_id:
            await contract.db.psp.delete_one({"id": sk_id})
