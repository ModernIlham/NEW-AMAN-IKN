"""Unit: pembatasan `ids` pada build_asset_search_query (dipakai ekspor geo
terseleksi di peta). Bebas infra — motor lazy, env dummy dari conftest."""
from routes.assets import build_asset_search_query


class TestBuildQueryIds:
    def test_ids_menambah_filter_in(self):
        q = build_asset_search_query(ids=["a1", "b2", "c3"])
        assert q["id"] == {"$in": ["a1", "b2", "c3"]}

    def test_ids_kosong_atau_none_tanpa_filter_id(self):
        assert "id" not in build_asset_search_query()
        assert "id" not in build_asset_search_query(ids=None)
        assert "id" not in build_asset_search_query(ids=[])

    def test_ids_irisan_dengan_filter_lain(self):
        # ids + activity_id → keduanya ada di query (irisan filter ∩ pilihan)
        q = build_asset_search_query(activity_id="KEG-1", ids=["x"])
        assert q["activity_id"] == "KEG-1"
        assert q["id"] == {"$in": ["x"]}
