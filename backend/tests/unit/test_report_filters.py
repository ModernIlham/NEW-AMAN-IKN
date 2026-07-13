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
