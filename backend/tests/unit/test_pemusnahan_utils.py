"""Uji logika murni register BA pemusnahan (PMK 83/2016)."""
import pytest

from pemusnahan_utils import (
    CARA_PEMUSNAHAN, kelayakan_musnah, rekap_pemusnahan, validate_pemusnahan,
)

HARI_INI = "2026-07-12"


def _ba(**over):
    base = {"nomor_ba": "BA-01/VII/2026", "tanggal_ba": "2026-07-10",
            "cara": "dihancurkan", "nomor_persetujuan": "S-9/KNL.05/2026",
            "asset_ids": ["a1"]}
    base.update(over)
    return base


def test_validasi_lolos_dan_wajib():
    assert validate_pemusnahan(_ba(), HARI_INI) == []
    assert any("Nomor Berita Acara" in e for e in validate_pemusnahan(_ba(nomor_ba=" "), HARI_INI))
    assert any("masa depan" in e for e in validate_pemusnahan(_ba(tanggal_ba="2026-07-13"), HARI_INI))
    assert any("Cara" in e for e in validate_pemusnahan(_ba(cara="dijual"), HARI_INI))
    assert any("persetujuan" in e for e in validate_pemusnahan(_ba(nomor_persetujuan=""), HARI_INI))
    assert any("satu aset" in e for e in validate_pemusnahan(_ba(asset_ids=[]), HARI_INI))
    for c in CARA_PEMUSNAHAN:
        assert validate_pemusnahan(_ba(cara=c), HARI_INI) == []


def test_kelayakan_hanya_rusak_berat():
    ok, _ = kelayakan_musnah({"condition": "Rusak Berat"})
    assert ok is True
    ok, alasan = kelayakan_musnah({"condition": "Baik"})
    assert ok is False and "rusak berat" in alasan
    ok, alasan = kelayakan_musnah({"condition": ""})
    assert ok is False and "kosong" in alasan


def test_rekap():
    records = [
        {"aset": [{"harga": 100_000}, {"harga": 250_000}]},
        {"aset": [{"harga": "Rp1.000.000"}]},
    ]
    r = rekap_pemusnahan(records)
    assert r == {"jumlah_ba": 2, "jumlah_aset": 3,
                 "nilai": pytest.approx(1_350_000)}
    assert rekap_pemusnahan([]) == {"jumlah_ba": 0, "jumlah_aset": 0, "nilai": 0.0}
