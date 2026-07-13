"""Unit: filter pemegang aset (Nama Pengguna + NIK/NIP) pada
build_asset_search_query — dipakai GET /assets, offline snapshot, dan ekspor
geo. Bebas infra — motor lazy, env dummy dari conftest."""
import re

from routes.assets import build_asset_search_query


class TestFilterPengguna:
    def test_user_filter_contains_literal(self):
        q = build_asset_search_query(user_filter="Budi Santoso")
        assert q["user"] == {"$regex": re.escape("Budi Santoso"), "$options": "i"}

    def test_pengguna_nip_contains_literal(self):
        q = build_asset_search_query(pengguna_nip="19700101")
        assert q["pengguna_nip"] == {"$regex": re.escape("19700101"), "$options": "i"}

    def test_kosong_tak_menambah_kunci(self):
        q = build_asset_search_query()
        assert "user" not in q
        assert "pengguna_nip" not in q
        # string kosong eksplisit juga tidak menambah kunci
        q2 = build_asset_search_query(user_filter="", pengguna_nip="")
        assert "user" not in q2
        assert "pengguna_nip" not in q2

    def test_input_regex_diescape(self):
        # Karakter regex diperlakukan literal (anti-ReDoS / anti-500)
        q = build_asset_search_query(user_filter="(a+)+")
        assert q["user"] == {"$regex": re.escape("(a+)+"), "$options": "i"}

    def test_kombinasi_dengan_filter_lain(self):
        # Filter pengguna berdampingan dengan search & filter lain (irisan)
        q = build_asset_search_query(
            search="meja", user_filter="Rina", pengguna_nip="123", condition="Baik"
        )
        assert q["user"] == {"$regex": re.escape("Rina"), "$options": "i"}
        assert q["pengguna_nip"] == {"$regex": re.escape("123"), "$options": "i"}
        assert q["condition"] == "Baik"
        assert "$or" in q  # search tetap aktif
