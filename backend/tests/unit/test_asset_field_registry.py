"""Anti-drift: registry field aset (asset_fields.py) vs seluruh turunannya.

Kelas bug yang dijaga: "field ada di form tapi hilang di ekspor/impor/
audit/patch/proyeksi" — persis yang terjadi saat pengguna_nip ditambahkan.
Bila menambah field skalar baru, cukup ikuti daftar langkah di docstring
asset_fields.py; test di sini menagih titik yang belum ikut.
"""
from asset_fields import (
    ASSET_SCALAR_FIELDS,
    BATCHABLE_FIELD_NAMES,
    SCALAR_FIELD_NAMES,
    import_row_value,
)

# Field AssetCreate yang BUKAN skalar-string registry (media/posisi/relasi).
NON_SCALAR_CREATE_FIELDS = {
    "photo", "photos", "thumbnail", "thumbnail_index",
    "document_checklist", "activity_id", "stiker_photo_index",
}


def test_registry_unik_dan_konsisten():
    assert len(set(SCALAR_FIELD_NAMES)) == len(SCALAR_FIELD_NAMES)
    assert BATCHABLE_FIELD_NAMES <= set(SCALAR_FIELD_NAMES)
    for f in ASSET_SCALAR_FIELDS:
        assert f.xlsx_label, f"field {f.name} tanpa label kolom XLSX"


def test_registry_selaras_model_create():
    """Registry harus = field AssetCreate minus field non-skalar.
    Gagal di sini berarti field baru ditambah di salah satu sisi saja."""
    from models import AssetCreate
    assert set(SCALAR_FIELD_NAMES) == set(AssetCreate.model_fields) - NON_SCALAR_CREATE_FIELDS


def test_registry_selaras_model_response():
    from models import AssetResponse
    missing = set(SCALAR_FIELD_NAMES) - set(AssetResponse.model_fields)
    assert not missing, f"field registry hilang di AssetResponse: {sorted(missing)}"


def test_patchable_dan_proyeksi_list_mencakup_semua_skalar():
    from routes.assets import LIST_PROJECTION, PATCHABLE_FIELDS
    assert set(SCALAR_FIELD_NAMES) <= PATCHABLE_FIELDS
    assert set(SCALAR_FIELD_NAMES) <= set(LIST_PROJECTION)


def test_batch_allowed_diturunkan_dari_registry():
    from routes.batch import BATCH_ALLOWED_FIELDS
    assert BATCH_ALLOWED_FIELDS == set(BATCHABLE_FIELD_NAMES)


def test_audit_trail_melacak_semua_skalar():
    from shared_utils import TRACKED_FIELDS
    missing = set(SCALAR_FIELD_NAMES) - set(TRACKED_FIELDS)
    assert not missing, f"field registry tak terlacak audit: {sorted(missing)}"


def test_kolom_xlsx_mencakup_semua_skalar():
    from routes.exports import ASSET_SHEET_HEADERS
    missing = {f.name: f.xlsx_label for f in ASSET_SCALAR_FIELDS
               if f.xlsx_label not in ASSET_SHEET_HEADERS}
    assert not missing, f"field registry tanpa kolom di sheet Data Aset: {missing}"


def test_template_impor_mencakup_semua_skalar():
    from routes.templates import ASSET_TEMPLATE_SCHEMA
    template_fields = {c["field"] for c in ASSET_TEMPLATE_SCHEMA}
    missing = set(SCALAR_FIELD_NAMES) - template_fields
    assert not missing, f"field registry hilang di template impor: {sorted(missing)}"


def test_import_row_value_mempertahankan_aturan_default_lama():
    by = {f.name: f for f in ASSET_SCALAR_FIELDS}
    # condition/status/stiker/inventory: default saat kolom absen ATAU kosong
    assert import_row_value({}, by["condition"]) == "Baik"
    assert import_row_value({"condition": "  "}, by["condition"]) == "Baik"
    assert import_row_value({}, by["status"]) == "Aktif"
    assert import_row_value({}, by["stiker_status"]) == "Belum Terpasang"
    assert import_row_value({}, by["inventory_status"]) == "Belum Diinventarisasi"
    # category: default HANYA saat kolom absen (perilaku impor lama)
    assert import_row_value({}, by["category"]) == "Lainnya"
    assert import_row_value({"category": ""}, by["category"]) == ""
    # field biasa: strip + string kosong bila absen
    assert import_row_value({"brand": " Asus "}, by["brand"]) == "Asus"
    assert import_row_value({}, by["brand"]) == ""
    assert import_row_value({"purchase_price": 1500000}, by["purchase_price"]) == "1500000"
