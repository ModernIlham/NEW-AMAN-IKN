import pytest

import laporan_jenjang as ljj


@pytest.mark.parametrize("aset,hasil", [
    ({"lokasi_spasial": {"node_id": "", "titik": [116.9, -1.5]}}, True),
    ({"lokasi_spasial": {"titik": [0, 1]}}, True),
    ({"koordinat_latitude": "-1.5", "koordinat_longitude": "116.9"}, False),
    ({"lokasi_spasial": {"node_id": "node-hilang", "titik": [116.9, -1.5]}}, False),
    ({"lokasi_spasial": None}, False),
    ({"lokasi_spasial": {"titik": [0, 0]}}, False),
    ({"lokasi_spasial": {"titik": [None, None]}}, False),
    ({"lokasi_spasial": {"titik": [116, 95]}}, False),
    ({"lokasi_spasial": {"titik": [float("nan"), 1]}}, False),
])
def test_luar_denah_hanya_dari_penempatan_yang_sah(aset, hasil):
    assert ljj.di_luar_denah(aset) is hasil


@pytest.mark.parametrize("levels", [[], ["GEDUNG"], ["GEDUNG", "LANTAI", "RUANGAN"]])
def test_luar_dan_belum_ditempatkan_terpisah_total_tidak_ganda(levels):
    luar = {"id": "luar", "location": "Teras", "lokasi_spasial": {"titik": [116.9, -1.5]}}
    belum = {"id": "belum", "location": "Teras"}
    rows = ljj.baris_hierarki_lokasi([luar, belum], levels, {})
    roots = [r for r in rows if r["depth"] == 0]
    assert {r["label"]: [a["id"] for a in r["aset"]] for r in roots} == {
        ljj.DI_LUAR_DENAH: ["luar"], ljj.TANPA_DENAH: ["belum"]}
    assert sum(len(r["aset"]) for r in roots) == 2
    assert len([r for r in rows if r["label"] == ljj.DI_LUAR_DENAH]) == 1
    assert all(r["depth"] <= 1 for r in rows)
