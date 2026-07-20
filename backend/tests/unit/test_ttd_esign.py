"""Uji token e-sign via link (Mandat-2 slice 2) — logika murni tanpa DB."""
import asyncio
import time

import jwt as pyjwt
import pytest
from fastapi import HTTPException


def test_sign_token_claims():
    import auth_utils as au
    tok = au.create_sign_token("sr-1", "sg-1", "jti-1")
    dec = pyjwt.decode(tok, au.JWT_SECRET, algorithms=[au.JWT_ALGORITHM])
    assert dec["typ"] == "sign"
    assert dec["sr"] == "sr-1" and dec["signer"] == "sg-1" and dec["jti"] == "jti-1"
    # umur 14 hari
    assert dec["exp"] > time.time() + 13 * 86400


def test_require_sign_token_valid_dan_invalid():
    import auth_utils as au
    tok = au.create_sign_token("sr-9", "sg-9", "jti-9")
    out = asyncio.run(au.require_sign_token(tok))
    assert out == {"sr": "sr-9", "signer": "sg-9", "jti": "jti-9"}

    with pytest.raises(HTTPException) as e1:
        asyncio.run(au.require_sign_token(""))
    assert e1.value.status_code == 401

    with pytest.raises(HTTPException) as e2:
        asyncio.run(au.require_sign_token("bukan.token.valid"))
    assert e2.value.status_code == 401

    # Token sesi biasa (tanpa typ=sign) DITOLAK sebagai token e-sign.
    with pytest.raises(HTTPException) as e3:
        asyncio.run(au.require_sign_token(au.create_token("u1", "alice")))
    assert e3.value.status_code == 401


def test_fallback_sign_token_saat_bearer_basi():
    """Tamu dengan token sesi KEDALUWARSA di localStorage (interceptor global
    memasangnya otomatis) harus tetap bisa memakai link e-sign yang valid."""
    import time as _t

    import auth_utils as au
    basi = pyjwt.encode({"user_id": "u1", "username": "x",
                         "exp": _t.time() - 10}, au.JWT_SECRET,
                        algorithm=au.JWT_ALGORITHM)
    sign = au.create_sign_token("sr-1", "sg-1", "jti-1")
    out = asyncio.run(au.require_user_or_sign_token(
        authorization=f"Bearer {basi}", token=sign))
    assert out.get("guest") is True and out["sign"]["sr"] == "sr-1"
    # Bearer basi TANPA sign token → tetap 401 (pesan bearer)
    with pytest.raises(HTTPException):
        asyncio.run(au.require_user_or_sign_token(
            authorization=f"Bearer {basi}", token=""))


def test_link_ttd_relatif_dan_absolut():
    from routes import ttd as t
    lama = t._APP_URL
    try:
        t._APP_URL = ""
        assert t._link_ttd("abc", "tok") == "/ttd/abc?token=tok"
        t._APP_URL = "https://aman.example"
        assert t._link_ttd("abc", "tok") == "https://aman.example/ttd/abc?token=tok"
    finally:
        t._APP_URL = lama


def test_publik_signer_tanpa_rahasia():
    from routes.ttd import _publik_signer
    sg = {"signer_id": "s1", "nama": "Budi", "nip": "199", "jabatan": "Kasubbag",
          "urutan": 1, "status": "aktif", "signed_at": "", "jti": "RAHASIA",
          "signature_file_id": "f1", "hash": "h", "ip": "1.2.3.4"}
    pub = _publik_signer(sg)
    assert pub["nama"] == "Budi" and pub["status"] == "aktif"
    assert "jti" not in pub and "hash" not in pub and "ip" not in pub


class TestPosisiBersih:
    """Posisi pembubuhan pilihan penanda tangan: validasi + penjepitan."""

    def test_posisi_valid_dijepit_ke_rentang(self):
        from routes.ttd import _posisi_bersih
        p = _posisi_bersih({"halaman": 2, "x": 0.5, "y": 0.7, "lebar": 0.25}, 5)
        assert p == {"halaman": 2, "x": 0.5, "y": 0.7, "lebar": 0.25}
        # Nilai liar dijepit, bukan ditolak — x dijepit BERPASANGAN dengan
        # lebar (x + lebar ≤ 1) agar kotak tidak keluar tepi kanan.
        p = _posisi_bersih({"halaman": 99, "x": 7, "y": -3, "lebar": 9}, 4)
        assert p == {"halaman": 4, "x": 0.4, "y": 0.0, "lebar": 0.6}
        p = _posisi_bersih({"halaman": 1, "x": 0, "y": 0, "lebar": 0.01}, 0)
        assert p["lebar"] == 0.08

    def test_infinity_dan_nan_ditolak(self):
        # json.loads menerima Infinity/NaN — int(inf) melempar OverflowError
        # dan NaN merusak jepitan; keduanya harus jadi None, bukan 500.
        import json
        from routes.ttd import _posisi_bersih
        p = json.loads('{"halaman": 1e999, "x": 0.1, "y": 0.1, "lebar": 0.2}')
        assert _posisi_bersih(p, 3) is None
        p = json.loads('{"halaman": 1, "x": NaN, "y": 0.1, "lebar": 0.2}')
        assert _posisi_bersih(p, 3) is None

    def test_posisi_tak_valid_jadi_none(self):
        from routes.ttd import _posisi_bersih
        assert _posisi_bersih(None) is None
        assert _posisi_bersih("bukan-dict") is None
        assert _posisi_bersih({}) is None
        assert _posisi_bersih({"halaman": 0, "x": 0.1, "y": 0.1, "lebar": 0.2}) is None
        assert _posisi_bersih({"halaman": 1, "x": "abc", "y": 0.1, "lebar": 0.2}) is None
