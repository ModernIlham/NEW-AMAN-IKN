"""Uji logika murni register BA pemusnahan (PMK 83/2016)."""
import pytest

from pemusnahan_utils import (
    CARA_PEMUSNAHAN, alasan_usulan_dari_ba, kelayakan_musnah,
    rekap_pemusnahan, usulan_penghapusan_dari_ba, validate_pemusnahan,
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


def test_alasan_usulan_merujuk_ba():
    alasan = alasan_usulan_dari_ba(_ba())
    assert "BA-01/VII/2026" in alasan
    assert "2026-07-10" in alasan and "S-9/KNL.05/2026" in alasan
    # Field kosong tidak membuat crash — tanda strip sebagai penampung
    assert "-" in alasan_usulan_dari_ba({})


def test_usulan_penghapusan_taut_sumber_ba():
    ba = _ba(id="ba-123")
    aset = {"asset_id": "a1", "asset_code": "3.05.01", "NUP": "7",
            "asset_name": "Laptop"}
    rec = usulan_penghapusan_dari_ba(ba, aset, "2026-07-13T00:00:00", "budi", "u-1")
    # Identitas aset tersalin
    assert rec["id"] == "u-1" and rec["asset_id"] == "a1"
    assert rec["asset_code"] == "3.05.01" and rec["NUP"] == "7"
    assert rec["jalur"] == "rusak_berat" and rec["status"] == "diusulkan"
    # TAUT SUMBER struktural (Pemusnahan -> Penghapusan) — bukan sekadar teks
    assert rec["sumber_modul"] == "pemusnahan"
    assert rec["sumber_ba_id"] == "ba-123"
    assert rec["sumber_ba_nomor"] == "BA-01/VII/2026"
    # Keterangan tetap merujuk BA + riwayat awal terisi
    assert "BA-01/VII/2026" in rec["keterangan"]
    assert rec["riwayat"][0]["status"] == "diusulkan" and rec["riwayat"][0]["oleh"] == "budi"


def test_usulan_penghapusan_ba_tanpa_nomor_tak_crash():
    rec = usulan_penghapusan_dari_ba({"id": "ba-x"}, {"asset_id": "a2"},
                                     "2026-07-13T00:00:00", "ani", "u-2")
    assert rec["sumber_ba_id"] == "ba-x" and rec["sumber_ba_nomor"] == ""


def test_rekap():
    records = [
        {"aset": [{"harga": 100_000}, {"harga": 250_000}]},
        {"aset": [{"harga": "Rp1.000.000"}]},
    ]
    r = rekap_pemusnahan(records)
    assert r == {"jumlah_ba": 2, "jumlah_aset": 3,
                 "nilai": pytest.approx(1_350_000)}
    assert rekap_pemusnahan([]) == {"jumlah_ba": 0, "jumlah_aset": 0, "nilai": 0.0}
