"""Kontrak numerik daftar + pagination pada Mongo nyata, bukan emulasi sort."""
import json
from pathlib import Path
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]
FIXTURE = json.loads((Path(__file__).parents[1] / "fixtures/urut_kode_nup.json").read_text())


async def test_urutan_daftar_sama_pdf_dan_luring(contract):
    from asset_sorting import tahapan_urutan_aset, urutkan_kode_nup_aset
    rows = [{**row, "id": "kode-nup-" + row["id"], "category": "UJI-URUT-KODE",
             "activity_id": "contract-activity-a"} for row in FIXTURE["rows"]]
    await contract.db.assets.insert_many(rows)
    await contract.db.assets.insert_one({"id": "kode-nup-asing", "asset_code": "2", "NUP": "1",
        "category": "UJI-URUT-KODE", "activity_id": "contract-activity-b"})
    for sort in ("code_nup_asc", "code_nup_desc"):
        expected = ["kode-nup-" + key for key in FIXTURE[sort]]
        mongo = await contract.db.assets.aggregate([
            {"$match": {"category": "UJI-URUT-KODE", "activity_id": "contract-activity-a"}},
            *tahapan_urutan_aset(sort),
        ]).to_list(50)
        assert [row["id"] for row in mongo] == expected
        assert [row["id"] for row in urutkan_kode_nup_aset(list(rows), sort)] == expected
        actual = []
        for page in (1, 2):
            result = await contract.http.get("/api/assets", headers=contract.headers["a"], params={
                "category": "UJI-URUT-KODE", "sort_by": sort, "page_size": 10, "page": page,
            })
            assert result.status_code == 200, result.text
            body = result.json()
            assert body["total"] == len(rows)
            assert all(not any(k.startswith("_aman_") for k in row) for row in body["items"])
            actual.extend(row["id"] for row in body["items"])
        assert actual == expected
        assert len(set(actual)) == len(rows)
