"""Uji logika murni register pemanfaatan (PMK 115/2020)."""
import pytest

from pemanfaatan_utils import (
    BENTUK_PEMANFAATAN, LABEL_STATUS_PERJANJIAN, dokumen_kurang,
    peringatan_kontribusi, rekap_pemanfaatan, status_perjanjian,
    tahun_tertunggak, validate_kontribusi, validate_pemanfaatan,
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


def test_tahun_tertunggak_dan_peringatan():
    # Tanpa kewajiban kontribusi → tanpa tunggakan
    assert tahun_tertunggak(_p(), HARI_INI) == []
    # KSP 2024-2033 kontribusi tahunan: 2024-2026 wajib; 2025 sudah dibayar
    ksp = _p(bentuk="ksp", mulai="2024-03-01", berakhir="2033-12-31",
             kontribusi_tahunan=50_000_000,
             kontribusi=[{"tahun": "2025", "ntpn": "X1"}])
    assert tahun_tertunggak(ksp, HARI_INI) == [2024, 2026]
    assert any("2024, 2026" in w for w in peringatan_kontribusi(ksp, HARI_INI))
    # Perjanjian sudah berakhir: kewajiban berhenti di tahun berakhir
    lama = _p(bentuk="ksp", mulai="2020-01-01", berakhir="2022-06-30",
              kontribusi_tahunan=1_000_000,
              kontribusi=[{"tahun": 2020}, {"tahun": "2021"}])
    assert tahun_tertunggak(lama, HARI_INI) == [2022]
    # Semua terbayar → tertib
    assert peringatan_kontribusi(
        _p(bentuk="ksp", mulai="2026-01-01", kontribusi_tahunan=5,
           kontribusi=[{"tahun": "2026"}]), HARI_INI) == []


def test_validasi_kontribusi():
    p = _p(bentuk="ksp", kontribusi_tahunan=5_000_000,
           kontribusi=[{"tahun": "2025", "ntpn": "X1"}])
    assert validate_kontribusi(
        {"tahun": "2026", "ntpn": "N9", "tanggal": "2026-07-01"}, p, HARI_INI) == []
    assert any("Tahun" in e for e in validate_kontribusi(
        {"tahun": "26", "ntpn": "N9"}, p, HARI_INI))
    assert any("NTPN" in e for e in validate_kontribusi(
        {"tahun": "2026", "ntpn": " "}, p, HARI_INI))
    assert any("masa depan" in e for e in validate_kontribusi(
        {"tahun": "2026", "ntpn": "N9", "tanggal": "2026-07-13"}, p, HARI_INI))
    assert any("sudah tercatat" in e for e in validate_kontribusi(
        {"tahun": "2025", "ntpn": "N9"}, p, HARI_INI))


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
