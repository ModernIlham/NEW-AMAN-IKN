"""Uji logika murni register pemanfaatan (PMK 115/2020)."""
import pytest

from pemanfaatan_utils import (
    BENTUK_PEMANFAATAN, LABEL_STATUS_PERJANJIAN, dokumen_kurang,
    rekap_pemanfaatan, status_perjanjian, validate_pemanfaatan,
)

HARI_INI = "2026-07-12"


def _p(**over):
    base = {"bentuk": "sewa", "mitra": "PT Maju", "mulai": "2026-01-01",
            "berakhir": "2027-12-31", "nilai": 12_000_000,
            "nomor_persetujuan": "S-11/KNL/2026",
            "nomor_perjanjian": "PJ-01/2026", "ntpn": "A1B2C3"}
    base.update(over)
    return base


def test_validasi_lolos_dan_bentuk_jangka():
    assert validate_pemanfaatan(_p()) == []
    assert any("Bentuk" in e for e in validate_pemanfaatan(_p(bentuk="jual")))
    assert any("mitra" in e.lower() for e in validate_pemanfaatan(_p(mitra=" ")))
    assert any("setelah" in e for e in validate_pemanfaatan(
        _p(mulai="2026-01-01", berakhir="2026-01-01")))
    # Sewa maksimal 5 tahun (PMK 115/2020)
    errs = validate_pemanfaatan(_p(mulai="2026-01-01", berakhir="2032-01-02"))
    assert any("maksimal 5 tahun" in e for e in errs)
    # KSPI 50 tahun masih sah
    assert validate_pemanfaatan(_p(bentuk="kspi", mulai="2026-01-01",
                                   berakhir="2070-01-01")) == []


def test_dokumen_kurang_menahan_status_aktif():
    assert dokumen_kurang(_p()) == []
    kurang = dokumen_kurang(_p(nomor_persetujuan="", ntpn=""))
    assert len(kurang) == 2 and any("Pengelola" in k for k in kurang)
    # NTPN hanya wajib untuk sewa
    assert dokumen_kurang(_p(bentuk="pinjam_pakai", ntpn="")) == []
    assert status_perjanjian(_p(nomor_perjanjian=""), HARI_INI) == "tidak_lengkap"


def test_status_jatuh_tempo_dan_berakhir():
    assert status_perjanjian(_p(), HARI_INI) == "aktif"
    assert status_perjanjian(_p(berakhir="2026-08-01"), HARI_INI) == "jatuh_tempo"
    assert status_perjanjian(_p(berakhir="2026-09-10"), HARI_INI) == "jatuh_tempo"  # tepat 60 hari
    assert status_perjanjian(_p(berakhir="2026-07-11"), HARI_INI) == "berakhir"
    # Berakhir menang atas dokumen kurang (sudah lewat, bukan soal kelengkapan)
    assert status_perjanjian(_p(berakhir="2026-01-31", ntpn=""), HARI_INI) == "berakhir"


def test_rekap():
    items = [_p(), _p(berakhir="2026-08-01"), _p(ntpn=""),
             _p(bentuk="pinjam_pakai", nilai=0, ntpn="")]
    r = rekap_pemanfaatan(items, HARI_INI)
    assert r["jumlah"] == 4
    assert r["per_status"]["aktif"] == 2  # sewa lengkap + pinjam pakai
    assert r["per_status"]["jatuh_tempo"] == 1
    assert r["per_status"]["tidak_lengkap"] == 1
    assert r["per_bentuk"]["sewa"] == 3
    assert r["total_nilai"] == pytest.approx(36_000_000)
    assert set(LABEL_STATUS_PERJANJIAN) == set(r["per_status"])
    assert set(BENTUK_PEMANFAATAN) == set(r["per_bentuk"])
