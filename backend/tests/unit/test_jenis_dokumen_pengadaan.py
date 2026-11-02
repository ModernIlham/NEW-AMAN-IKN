"""Jenis dokumen valid, data historis utuh, dan seluruh proyeksi selaras."""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from jenis_dokumen_pengadaan import (
    JENIS_DOKUMEN_PENGADAAN, normalisasi_jenis_dokumen_pengadaan,
    pertahankan_jenis_dokumen_lama,
)
from models import AssetCreate

FIELD = "jenis_dokumen_pengadaan"


@pytest.mark.parametrize("jenis", ["", *JENIS_DOKUMEN_PENGADAAN])
def test_model_menyimpan_pilihan_dan_mempertahankan_nomor_lama(jenis):
    data = AssetCreate(asset_code="3050101001", asset_name="Meja", category="Meja",
                       jenis_dokumen_pengadaan=f" {jenis} ", nomor_kontrak="K-1",
                       cara_bayar_kontrak="Sekaligus", nomor_bukti_perolehan="KW-1")
    assert data.jenis_dokumen_pengadaan == jenis
    assert data.nomor_kontrak == "K-1"
    assert data.cara_bayar_kontrak == "Sekaligus"
    assert data.nomor_bukti_perolehan == "KW-1"


@pytest.mark.parametrize("value", [True, 1, [], {}, {"$ne": None}, "lain-lain", "Non Kontrak"])
def test_jenis_di_luar_pilihan_ditolak(value):
    with pytest.raises(ValueError):
        normalisasi_jenis_dokumen_pengadaan(value)
    with pytest.raises(ValidationError):
        AssetCreate(asset_code="3", asset_name="Meja", category="Meja", **{FIELD: value})


def test_klien_lama_tidak_ditebak_dan_tidak_menghapus_klasifikasi():
    model = AssetCreate(asset_code="3", asset_name="Meja", category="Meja", nomor_kontrak="K-1")
    assert model.jenis_dokumen_pengadaan == ""
    assert normalisasi_jenis_dokumen_pengadaan(None) == ""
    data = model.model_dump()
    pertahankan_jenis_dokumen_lama(data, {FIELD: "Kontrak BLU"}, model.model_fields_set)
    assert data[FIELD] == "Kontrak BLU"
    data[FIELD] = ""
    pertahankan_jenis_dokumen_lama(data, {FIELD: "Kontrak BLU"}, {FIELD})
    assert data[FIELD] == ""  # pengosongan eksplisit tetap diizinkan


def test_pilihan_ui_model_dan_template_sama():
    from routes.templates import ASSET_TEMPLATE_SCHEMA
    root = Path(__file__).resolve().parents[3]
    frontend = root / "frontend/src/lib"
    assert json.loads((frontend / "jenisDokumenPengadaan.json").read_text()) == list(JENIS_DOKUMEN_PENGADAAN)
    registry = json.loads((frontend / "assetFields.json").read_text())
    assert registry[FIELD] == {"defaultValue": "", "label": "Jenis Dokumen Pengadaan"}
    schema = next(item for item in ASSET_TEMPLATE_SCHEMA if item["field"] == FIELD)
    assert schema["dropdown"] == list(JENIS_DOKUMEN_PENGADAAN)


def test_impor_memvalidasi_jenis_tanpa_mewajibkan_kolom_baru():
    from routes.imports import validate_import_row
    base = {"asset_code": "3050101001", "asset_name": "Meja", "category": "Meja"}
    for jenis in (None, "", *JENIS_DOKUMEN_PENGADAAN):
        assert not validate_import_row({**base, FIELD: jenis}, ["Meja"], 2)
    errors = validate_import_row({**base, FIELD: "salah"}, ["Meja"], 2)
    assert len(errors) == 1 and "Jenis dokumen pengadaan" in errors[0]
