"""Uji akun neraca Persediaan (sub-kelompok 1171xx)."""
from akun_bas_utils import AKUN_NERACA_DEFAULT
from persediaan_akun_utils import (
    AKUN_PERSEDIAAN_DEFAULT, AKUN_PERSEDIAAN_UTAMA,
    akun_persediaan, validate_akun_persediaan,
)


def test_akun_utama_satu_sumber_dari_akun_bas():
    # Evaluasi #2: akun golongan-1 persediaan diturunkan dari akun_bas (satu sumber).
    assert AKUN_PERSEDIAAN_UTAMA == AKUN_NERACA_DEFAULT["1"]["akun"]


def test_default_memuat_akun_utama_dan_sub():
    assert AKUN_PERSEDIAAN_UTAMA == "117111"
    assert AKUN_PERSEDIAAN_DEFAULT["117111"]  # Barang Konsumsi (terkonfirmasi)
    # sub-akun rujukan tersedia untuk pelaporan per akun
    for k in ("117113", "117114", "117131", "117199"):
        assert k in AKUN_PERSEDIAAN_DEFAULT
    # semua kode 6 digit diawali 1171
    for k in AKUN_PERSEDIAAN_DEFAULT:
        assert len(k) == 6 and k.startswith("1171")


def test_validate_akun_persediaan():
    assert validate_akun_persediaan("117111") == []
    assert validate_akun_persediaan("117131") == []
    assert any("1171" in e for e in validate_akun_persediaan("132111"))  # bukan persediaan
    assert any("1171" in e for e in validate_akun_persediaan("11711"))   # 5 digit
    assert any("1171" in e for e in validate_akun_persediaan("abc"))


def test_akun_persediaan_default():
    r = akun_persediaan("1010101001")
    assert r["akun"] == "117111" and r["sumber"].startswith("default")
    # kode kosong tetap aman → default
    assert akun_persediaan("")["akun"] == "117111"


def test_akun_persediaan_override():
    peta = {"10105": {"akun": "117131", "uraian": "utk Diserahkan"}}
    r = akun_persediaan("1010501001", peta)  # sub-kelompok 10105
    assert r["akun"] == "117131" and r["sumber"] == "override satker"
    # sub-kelompok lain tetap default
    assert akun_persediaan("1010101001", peta)["akun"] == "117111"
    # override tanpa uraian → ambil dari default bila dikenal
    peta2 = {"10101": {"akun": "117113"}}
    assert akun_persediaan("1010101001", peta2)["uraian"] == AKUN_PERSEDIAAN_DEFAULT["117113"]
