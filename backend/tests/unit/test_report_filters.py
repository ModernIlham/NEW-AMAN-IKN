"""Unit: filter aset aktif untuk laporan posisi/nilai (kecualikan `dihapus`).
Bebas infra — fungsi murni."""
from report_filters import active_asset_filter


class TestActiveAssetFilter:
    def test_tanpa_base_hanya_syarat_dihapus(self):
        assert active_asset_filter() == {"dihapus": {"$ne": True}}
        assert active_asset_filter(None) == {"dihapus": {"$ne": True}}

    def test_gabung_dengan_base(self):
        q = active_asset_filter({"activity_id": "KEG-1"})
        assert q == {"activity_id": "KEG-1", "dihapus": {"$ne": True}}

    def test_base_tidak_dimutasi(self):
        base = {"activity_id": "KEG-1"}
        active_asset_filter(base)
        # base asli tetap utuh (dibuat salinan)
        assert base == {"activity_id": "KEG-1"}

    def test_dihapus_di_base_ditimpa_syarat_aktif(self):
        # bila pemanggil sudah menaruh `dihapus`, syarat aktif yang menang
        q = active_asset_filter({"dihapus": True})
        assert q["dihapus"] == {"$ne": True}

    def test_ne_true_mencakup_tanpa_field_dan_false(self):
        # dokumen tanpa field `dihapus` maupun `dihapus=False` LOLOS ($ne True),
        # hanya `dihapus=True` yang tersingkir — semantik yang diinginkan.
        cond = active_asset_filter()["dihapus"]
        assert cond == {"$ne": True}


def test_layak_hitung_kegiatan_w9():
    """Gerbang W9: hanya kegiatan disahkan / tanggal selesai lewat yang
    ikut perhitungan modul lain; belum dimulai/berlangsung tidak."""
    from report_filters import layak_hitung_kegiatan
    hari = "2026-07-19"
    # Disahkan → selalu masuk (meski tanggal belum lewat)
    assert layak_hitung_kegiatan(
        {"status_pengesahan": "disahkan", "tanggal_selesai": "2026-12-31"},
        hari) is True
    # Tanggal selesai lewat (fase selesai / belum lengkap) → masuk
    assert layak_hitung_kegiatan(
        {"status_pengesahan": "draft", "tanggal_selesai": "2026-06-30"},
        hari) is True
    # Berlangsung (tanggal selesai belum lewat) → TIDAK
    assert layak_hitung_kegiatan(
        {"status_pengesahan": "draft", "tanggal_selesai": "2026-12-31"},
        hari) is False
    # Hari terakhir kegiatan = masih berlangsung → TIDAK
    assert layak_hitung_kegiatan(
        {"tanggal_selesai": "2026-07-19"}, hari) is False
    # Tanpa tanggal selesai & belum disahkan → TIDAK
    assert layak_hitung_kegiatan({"tanggal_selesai": ""}, hari) is False
    assert layak_hitung_kegiatan({}, hari) is False
    assert layak_hitung_kegiatan(None, hari) is False


def test_tanpa_dummy_filter():
    """Aset berkategori dummy bukan aset — disaring dari perhitungan."""
    import re

    from report_filters import tanpa_dummy_filter
    q = tanpa_dummy_filter({"dihapus": {"$ne": True}})
    assert q["dihapus"] == {"$ne": True}
    rx = q["category"]["$not"]
    assert re.search(rx["$regex"], "Dummy Kategori", re.I)
    assert re.search(rx["$regex"], "kategori dummy", re.I)
    assert not re.search(rx["$regex"], "Peralatan Kantor", re.I)
    # base tak dimutasi + syarat category yang sudah ada tidak ditimpa
    base = {"category": "Elektronik"}
    q2 = tanpa_dummy_filter(base)
    assert q2["category"] == "Elektronik" and base == {"category": "Elektronik"}
    assert "category" in tanpa_dummy_filter(None)
