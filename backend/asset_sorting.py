"""Urutan Mongo yang sama untuk daftar aset dan PDF Data Aset.

Tiebreaker id mencegah baris bertukar halaman saat nilai utama sama.
"""
ASSET_SORT_OPTIONS = {
    "newest": [("created_at", -1), ("id", 1)],
    "oldest": [("created_at", 1), ("id", 1)],
    "name_asc": [("asset_name", 1), ("id", 1)],
    "name_desc": [("asset_name", -1), ("id", 1)],
    "price_asc": [("purchase_price", 1), ("id", 1)],
    "price_desc": [("purchase_price", -1), ("id", 1)],
    "category_asc": [("category", 1), ("id", 1)],
    "category_desc": [("category", -1), ("id", 1)],
    "location_asc": [("location", 1), ("id", 1)],
    "eselon1_asc": [("eselon1", 1), ("id", 1)],
    "condition_asc": [("condition", 1), ("id", 1)],
    "status_asc": [("status", 1), ("id", 1)],
}
