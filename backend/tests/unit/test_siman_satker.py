"""Identitas SIMAN tidak bercampur saat barang/NUP sama di satker berbeda."""

import pytest

from siman_satker import (
    IndeksSatker,
    identitas_satker,
    kode_satker_sama,
    norm_kode_satker,
)


LENGKAP = "126011600691778000KP"


@pytest.mark.parametrize("nilai", [
    LENGKAP, "126.01.1600.691778.000.KP", "126 01 1600 691778 000 kp",
    " 126-01-1600-691778-000-KP ",
])
def test_pemisah_dan_huruf_tidak_mengubah_identitas(nilai):
    assert norm_kode_satker(nilai) == LENGKAP


@pytest.mark.parametrize("nilai,hasil", [
    (691778, "691778"), (691778.0, "691778"), ("691778.0", "691778"),
    ("001234.0", "001234"), ("001234.00", "001234"),
    ("001234", "001234"), ("000000", "000000"),
    (1234.0, "1234"),  # Nol depan yang sudah hilang tidak boleh ditebak.
    ("satker-A", "satker-A"), ("  lama_01 ", "lama_01"),
    (None, ""), ("", ""), (True, ""), (float("inf"), ""),
    (float("nan"), ""), (-1.0, ""), (691778.25, ""),
    ("691778.25", ""), ("1234.5", ""),
    (12601160069177800000.0, ""),
    ("12601160069177800000.0", ""), ("1.26011600691778e+19", ""),
    ("12601160069177800000", "12601160069177800000"),
    (12601160069177800000, "12601160069177800000"),
])
def test_normalisasi_excel_dan_kode_lama(nilai, hasil):
    assert norm_kode_satker(nilai) == hasil


def test_enam_digit_hanya_segmen_satker_yang_benar():
    assert kode_satker_sama("691778", LENGKAP)
    assert kode_satker_sama(LENGKAP, "691778")
    assert not kode_satker_sama("160069", LENGKAP)
    assert not kode_satker_sama("126011", LENGKAP)
    assert not kode_satker_sama("778000", LENGKAP)


@pytest.mark.parametrize("lain", [
    "127011600691778000KP",  # BA.
    "126021600691778000KP",  # Eselon.
    "126011601691778000KP",  # Wilayah.
    "126011600691779000KP",  # Satker.
    "126011600691778001KP",  # Subsatker.
    "126011600691778000KD",  # Kewenangan.
])
def test_full_berbeda_satu_segmen_tidak_digabung(lain):
    assert not kode_satker_sama(LENGKAP, lain)
    assert not kode_satker_sama(lain, LENGKAP)
    assert identitas_satker(LENGKAP, lain) == ""


@pytest.mark.parametrize("a,b", [
    ("", ""), (None, LENGKAP), (LENGKAP, None),
    ("691778", "691779"), ("691778", "126011600691778000"),
    ("160069", LENGKAP), ("SATKER", "SATKERA"),
])
def test_kosong_dan_potongan_tidak_menjadi_wildcard(a, b):
    assert not kode_satker_sama(a, b)


def test_kode_opaque_lama_hanya_cocok_persis():
    assert kode_satker_sama("satker-A", " satker-A ")
    assert identitas_satker("satker-A") == "satker-A"
    assert identitas_satker("", "legacy-A") == "legacy-A"
    assert identitas_satker("legacy-A", "legacy-A") == "legacy-A"
    assert identitas_satker("legacy-A", LENGKAP) == ""


@pytest.mark.parametrize("lain", ["SATKERA", "satker_A", "SATKER-A", "satker A", "Satker-A"])
def test_opaque_namespace_tidak_digabung_oleh_pemisah_atau_case(lain):
    assert norm_kode_satker("satker-A") == "satker-A"
    assert norm_kode_satker(lain) == lain
    assert not kode_satker_sama("satker-A", lain)
    assert identitas_satker("satker-A", lain) == ""
    indeks = IndeksSatker(["satker-A", lain])
    assert indeks.kunci("satker-A") == "satker-A"
    assert indeks.kunci(lain) == lain


def test_identitas_memilih_full_yang_sesuai():
    assert identitas_satker("691778", LENGKAP) == LENGKAP
    assert identitas_satker("691778.0", LENGKAP) == LENGKAP
    assert identitas_satker("", LENGKAP) == LENGKAP
    assert identitas_satker(LENGKAP) == LENGKAP
    assert identitas_satker("160069", LENGKAP) == ""
    assert identitas_satker("691779", LENGKAP) == ""
    assert identitas_satker(LENGKAP, "691778") == ""
    assert identitas_satker("691778", float("inf")) == ""


def test_full_numeric_duapuluh_tetap_utuh_dan_bersegmen():
    penuh = "12601160069177800000"
    assert kode_satker_sama("691778", penuh)
    assert not kode_satker_sama("160069", penuh)
    assert not kode_satker_sama(penuh, "12601160069177800001")
    assert identitas_satker("691778", penuh) == penuh


def test_indeks_satu_full_menyatukan_bentuk_enam_digit():
    indeks = IndeksSatker(["691778", LENGKAP, "126.01.1600.691778.000.KP"])
    assert indeks.kunci("691778") == LENGKAP
    assert indeks.kunci(LENGKAP) == LENGKAP
    assert indeks.kunci("160069") == "160069"
    assert indeks.kunci("001234.0") == "001234"
    assert indeks.kunci("satker-A") == "satker-A"
    assert indeks.kunci("") == ""


def test_indeks_enam_digit_ambigu_tidak_memilih_full_pertama():
    lain = "126011601691778000KD"
    for daftar in ([LENGKAP, lain], [lain, LENGKAP]):
        indeks = IndeksSatker(daftar)
        assert indeks.kunci("691778") == ""
        assert indeks.kunci(LENGKAP) == LENGKAP
        assert indeks.kunci(lain) == lain
        assert indeks.kunci("691779") == "691779"


def test_indeks_tanpa_identitas_tidak_menciptakan_alias():
    indeks = IndeksSatker([None, "", "legacy-A", "160069"])
    assert indeks.kunci("691778") == "691778"
    assert indeks.kunci(LENGKAP) == LENGKAP
    assert indeks.kunci(None) == ""
    assert indeks.kunci(12601160069177800000.0) == ""
