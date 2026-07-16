"""Uji referensi Akun Neraca (BAS) per golongan BMN."""
from akun_bas_utils import (
    AKUN_NERACA_DEFAULT, akun_untuk_golongan, validate_akun_bas,
)


def test_default_mencakup_8_golongan():
    assert set(AKUN_NERACA_DEFAULT) == {"1", "2", "3", "4", "5", "6", "7", "8"}
    # akun neraca terkonfirmasi (sumber sekunder resmi)
    assert AKUN_NERACA_DEFAULT["2"]["akun"] == "131111"  # Tanah
    assert AKUN_NERACA_DEFAULT["3"]["akun"] == "132111"  # Peralatan dan Mesin
    assert AKUN_NERACA_DEFAULT["4"]["akun"] == "133111"  # Gedung dan Bangunan
    assert AKUN_NERACA_DEFAULT["7"]["akun"] == "136111"  # KDP


def test_validate_akun_bas():
    assert validate_akun_bas("3", "132111") == []
    assert any("Golongan" in e for e in validate_akun_bas("9", "132111"))
    assert any("Kode akun" in e for e in validate_akun_bas("3", "abc"))
    assert any("Kode akun" in e for e in validate_akun_bas("3", "1234567"))  # 7 digit


def test_akun_untuk_golongan():
    # kode barang → golongan (digit pertama) → akun
    r = akun_untuk_golongan("3020101001")
    assert r["golongan"] == "3" and r["akun"] == "132111"
    assert akun_untuk_golongan("2010101001")["akun"] == "131111"  # Tanah
    # golongan tak dikenal / kosong → None
    assert akun_untuk_golongan("9xxxx") is None
    assert akun_untuk_golongan("") is None
    # override peta menang
    peta = {**{g: dict(v) for g, v in AKUN_NERACA_DEFAULT.items()},
            "3": {"akun": "132211", "uraian": "custom"}}
    assert akun_untuk_golongan("3020101001", peta)["akun"] == "132211"
