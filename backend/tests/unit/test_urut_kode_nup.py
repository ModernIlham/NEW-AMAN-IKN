import asyncio
import json
from pathlib import Path

import pytest
from asset_sorting import angka_identitas, urutkan_kode_nup_aset, tahapan_urutan_aset

FIXTURE = json.loads((Path(__file__).parents[1] / "fixtures/urut_kode_nup.json").read_text())


@pytest.mark.parametrize("value,expected", [("002", "2"), (2, "2"), ("2.0", "2"),
    ("0", "0"), ("  0010 ", "10"), (None, None), (True, None), ("-1", None),
    ("2.5", None), ("1e3", None), ("", None), ("belum ada", None),
    ("9" * 100, "9" * 100)])
def test_angka_tanpa_kehilangan_presisi(value, expected):
    assert angka_identitas(value) == expected


@pytest.mark.parametrize("sort", ["code_nup_asc", "code_nup_desc"])
def test_urutan_kode_lalu_nup_dengan_id_stabil(sort):
    actual = urutkan_kode_nup_aset(list(FIXTURE["rows"]), sort)
    assert [row["id"] for row in actual] == FIXTURE[sort]
    stages = tahapan_urutan_aset(sort)
    assert list(stages[1]["$sort"])[-1] == "id"
    assert stages[1]["$sort"]["_aman_code_sort.invalid"] == 1
    assert stages[1]["$sort"]["_aman_nup_sort.invalid"] == 1


@pytest.mark.parametrize("sort", ["code_nup_asc", "code_nup_desc"])
def test_pdf_builder_mengikuti_filter_dan_urutan_numerik(monkeypatch, sort):
    from mongomock_motor import AsyncMongoMockClient
    import routes.reports as reports
    import shared_utils
    db = AsyncMongoMockClient()["urut_kode_nup_uji"]
    monkeypatch.setattr(reports, "db", db)
    monkeypatch.setattr(shared_utils, "db", db)

    async def run():
        await db.inventory_activities.insert_one({"id": "k1", "kode_satker": "A"})
        rows = [{**row, "activity_id": "k1", "location": "Gedung Uji",
                 "asset_name": row["id"]} for row in FIXTURE["rows"]]
        await db.assets.insert_many(rows + [{"id": "tidak-ikut", "activity_id": "k1",
                                            "location": "Gedung Lain"}])
        data = await reports._build_executive_summary_data("k1", sort_by=sort,
            filter_aset=reports.filter_laporan_dari_map({"location": ["Gedung Uji"]}))
        assert [row["asset_name"] for row in data["assets"]] == FIXTURE[sort]
        assert data["asset_count"] == len(rows)
    asyncio.run(run())
