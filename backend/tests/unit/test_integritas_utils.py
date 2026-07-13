"""Uji logika murni integritas identitas aset (§5A Prinsip 1, #261)."""
from integritas_utils import FIELD_IDENTITAS, identitas_drift


def _snap(**over):
    base = {"asset_code": "3050104001", "NUP": "12", "asset_name": "Laptop"}
    base.update(over)
    return base


def test_konsisten_tak_ada_drift():
    assert identitas_drift(_snap(), _snap()) == {}


def test_satu_field_basi():
    drift = identitas_drift(_snap(NUP="12"), _snap(NUP="15"))
    assert drift == {"NUP": {"snapshot": "12", "master": "15"}}


def test_banyak_field_basi():
    drift = identitas_drift(
        _snap(asset_code="3050104001", asset_name="Laptop"),
        _snap(asset_code="3050104002", asset_name="Notebook"))
    assert set(drift) == {"asset_code", "asset_name"}
    assert drift["asset_code"] == {"snapshot": "3050104001", "master": "3050104002"}


def test_normalisasi_none_kosong_spasi_tak_drift_palsu():
    # None vs "" vs "  X  " → dinormalisasi (strip), tak dianggap basi
    snap = {"asset_code": "  3050104001  ", "NUP": None, "asset_name": "Laptop"}
    master = {"asset_code": "3050104001", "NUP": "", "asset_name": "Laptop"}
    assert identitas_drift(snap, master) == {}


def test_snapshot_atau_master_kosong_kembalikan_kosong():
    # master hilang/kosong → {} (kasus 'aset_master_hilang' ditangani pemanggil)
    assert identitas_drift(_snap(), None) == {}
    assert identitas_drift(_snap(), {}) == {}
    assert identitas_drift(None, _snap()) == {}


def test_field_identitas_tiga_kolom():
    assert FIELD_IDENTITAS == ("asset_code", "NUP", "asset_name")
