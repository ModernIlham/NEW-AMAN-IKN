"""Respons login & /auth/me WAJIB membawa ikatan satker akun.

Frontend menentukan super-admin pusat dari `role == "admin" && !kode_satker`
(`frontend/src/lib/satkerAktif.js`). Selama `UserResponse` tidak memuat
`kode_satker`, SETIAP admin satker dianggap super-admin: tab Sistem
(backup/reset), tirai Satker Aktif, dan setelan universal tampil lalu
ditolak backend 403, dan kunci cache offline jatuh ke satker yang salah.
"""
import asyncio

import routes.auth as ra
from models import TokenResponse, UserResponse

DASAR = {"id": "u1", "username": "admin.a", "name": "Admin A", "role": "admin",
         "is_active": True, "created_at": "2026-01-01T00:00:00+00:00"}


def _jalan(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_model_respons_memuat_kode_satker():
    assert "kode_satker" in UserResponse.model_fields
    assert "kode_satker" in TokenResponse.model_fields["user"].annotation.model_fields


def test_kode_satker_akun_satker_dan_pusat():
    assert ra._kode_satker_akun({**DASAR, "kode_satker": " 990000 "}) == "990000"
    assert ra._kode_satker_akun({**DASAR, "kode_satker": ""}) == ""
    assert ra._kode_satker_akun(DASAR) == ""          # akun lama tanpa field
    assert ra._kode_satker_akun({**DASAR, "kode_satker": None}) == ""


def test_act_as_super_admin_tetap_dilaporkan_pusat():
    """Super-admin yang sedang memilih Satker Aktif: dokumen tersuntik membawa
    kode satker pilihan, tetapi identitas AKUN tetap pusat ("")."""
    u = {**DASAR, "kode_satker": "990001", "_kode_satker_asli": "",
         "_super_admin_asli": True, "_satker_aktif": "990001"}
    assert ra._kode_satker_akun(u) == ""


def test_auth_me_mengirim_kode_satker(monkeypatch):
    async def palsu(_authorization):
        return {**DASAR, "kode_satker": "990000"}

    monkeypatch.setattr(ra, "get_current_user", palsu)
    r = _jalan(ra.get_me(authorization="Bearer x"))
    assert r.kode_satker == "990000"
    assert r.model_dump()["kode_satker"] == "990000"
