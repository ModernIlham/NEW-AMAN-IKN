"""Uji M-SEC (Mandat-2): require_writer (viewer read-only ditegakkan server)
+ gabung_ambang (ambang kapitalisasi jadi setelan)."""
import asyncio

import pytest
from fastapi import HTTPException

from pembukuan_utils import (
    AMBANG_KAPITALISASI_DEFAULT, gabung_ambang, klasifikasi_komptabel,
)


# ------------------------------------------------------------ require_writer
def test_require_writer_tolak_viewer_izinkan_lainnya():
    import auth_utils as au

    with pytest.raises(HTTPException) as e:
        asyncio.run(au.require_writer({"role": "viewer", "username": "v"}))
    assert e.value.status_code == 403

    for role in ("admin", "operator", "user", "", None):
        u = {"role": role, "username": "x"}
        assert asyncio.run(au.require_writer(u)) is u


# ------------------------------------------------------------- gabung_ambang
def test_gabung_ambang_default_dan_override():
    # Tanpa override → default PMK 181 utuh
    assert gabung_ambang(None) == AMBANG_KAPITALISASI_DEFAULT
    assert gabung_ambang({}) == AMBANG_KAPITALISASI_DEFAULT
    # Override sah menimpa; golongan lain tetap default
    out = gabung_ambang({"3": 2_500_000})
    assert out["3"] == 2_500_000 and out["4"] == AMBANG_KAPITALISASI_DEFAULT["4"]
    # Format rupiah Indonesia ikut diparse
    assert gabung_ambang({"4": "Rp30.000.000"})["4"] == 30_000_000


def test_gabung_ambang_abaikan_nilai_rusak():
    # Nilai tak valid / kunci aneh diabaikan — jatuh ke default
    out = gabung_ambang({"3": "abc", "44": 5, "": 9, "4": 0, "x": -1})
    assert out == AMBANG_KAPITALISASI_DEFAULT


def test_klasifikasi_ikut_ambang_override():
    # Default: Rp1,5 jt peralatan-mesin = intra
    assert klasifikasi_komptabel("3050104001", 1_500_000) == "intra"
    # Override ambang naik 2,5 jt → barang yang sama jadi ekstra
    amb = gabung_ambang({"3": 2_500_000})
    assert klasifikasi_komptabel("3050104001", 1_500_000, amb) == "ekstra"
    assert klasifikasi_komptabel("3050104001", 2_500_000, amb) == "intra"
