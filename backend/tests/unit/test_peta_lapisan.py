"""Registri lapisan citra eksisting peta: validasi, baca bersama, tulis terjaga."""
import asyncio

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import routes.peta_lapisan as rp
import shared_utils as su
from backup_utils import RESET_KEEP_COLLECTIONS
from peta_lapisan_utils import normalisasi_lapisan, validasi_url_template

SUPER = {"id": "s", "username": "pusat", "role": "admin", "kode_satker": ""}
ADMIN_A = {"id": "a", "username": "adm_a", "role": "admin", "kode_satker": "A"}
ADMIN_B = {"id": "b", "username": "adm_b", "role": "admin", "kode_satker": "B"}
USER_B = {"id": "ub", "username": "staf_b", "role": "user", "kode_satker": "B"}

SAH = {
    "nama": "Citra drone KIPP", "sumber": "Tim Satker", "tanggal_rekam": "2026-10-15",
    "url_template": "/uploads/ubin/kipp-2026-10/{z}/{x}/{y}.webp",
    "batas": {"barat": 116.69, "selatan": -0.98, "timur": 116.72, "utara": -0.95},
    "zoom_min": 14, "zoom_maks": 21, "opasitas": 0.85, "aktif": True,
}


@pytest.fixture
def database(monkeypatch):
    fake = AsyncMongoMockClient()["peta_lapisan"]
    monkeypatch.setattr(rp, "db", fake)
    monkeypatch.setattr(su, "db", fake)
    return fake


def _in(**ubah):
    return rp.LapisanIn(**{**SAH, **ubah})


# ── validasi murni ──────────────────────────────────────────────────────────

def test_masukan_sah_lolos_dan_dirapikan():
    dok, galat = normalisasi_lapisan({**SAH, "nama": "  Citra  "})
    assert galat == []
    assert dok["nama"] == "Citra" and dok["zoom_maks"] == 21 and dok["opasitas"] == 0.85


@pytest.mark.parametrize("url", [
    "javascript:alert(1)/{z}/{x}/{y}", "data:image/png;base64,{z}{x}{y}",
    "http://contoh.id/{z}/{x}/{y}.png", "//cdn.contoh.id/{z}/{x}/{y}.png",
    "/ubin/{z}/{x}.png", "/ubin/{z}/{x}/{y}/{token}.png", "/ubin/{z}/{x}/{y}.png\"onerror",
    "/ubin dengan spasi/{z}/{x}/{y}.png", "",
])
def test_alamat_ubin_berbahaya_atau_tak_lengkap_ditolak(url):
    assert validasi_url_template(url)


@pytest.mark.parametrize("url", [
    "/uploads/ubin/a/{z}/{x}/{y}.webp", "https://{s}.ubin.contoh.id/{z}/{x}/{y}.png",
])
def test_alamat_ubin_sah(url):
    assert validasi_url_template(url) == []


@pytest.mark.parametrize("ubah", [
    {"batas": {"barat": 117, "selatan": -1, "timur": 116, "utara": 0}},   # barat ≥ timur
    {"batas": {"barat": 116, "selatan": 0, "timur": 117, "utara": -1}},   # selatan ≥ utara
    {"batas": {"barat": 116, "selatan": -1, "timur": 117}},               # utara hilang
    {"zoom_min": 18, "zoom_maks": 15},
    {"zoom_min": 0, "zoom_maks": 23},
    {"tanggal_rekam": "15/10/2026"},
    {"tanggal_rekam": "9999-99-99"},
    {"nama": "  "},
    {"opasitas": 0},
])
def test_batas_zoom_tanggal_tak_wajar_ditolak(ubah):
    _, galat = normalisasi_lapisan({**SAH, **ubah})
    assert galat


# ── endpoint ────────────────────────────────────────────────────────────────

def test_dibaca_bersama_lintas_satker_tetapi_hanya_yang_aktif(database):
    async def run():
        aktif = await rp.buat_lapisan(_in(), user=ADMIN_A)
        await rp.buat_lapisan(_in(nama="Arsip", aktif=False,
                                  url_template="/uploads/ubin/lama/{z}/{x}/{y}.webp"),
                              user=ADMIN_A)
        # Pengguna satker B melihat citra satker A — citra itu geografis.
        hasil = await rp.daftar_lapisan(user=USER_B)
        assert [i["id"] for i in hasil["items"]] == [aktif["id"]]
        assert "kode_satker" not in hasil["items"][0]
        # Admin melihat semua, dengan hak ubah sesuai pengelola.
        adm = await rp.daftar_lapisan(user=ADMIN_B)
        assert adm["jumlah"] == 2 and all(i["bisa_ubah"] is False for i in adm["items"])
    asyncio.run(run())


def test_admin_satker_lain_tak_bisa_mengubah_atau_menghapus(database):
    async def run():
        dok = await rp.buat_lapisan(_in(), user=ADMIN_A)
        with pytest.raises(HTTPException) as e:
            await rp.ubah_lapisan(dok["id"], _in(nama="Ganti", version=1), user=ADMIN_B)
        assert e.value.status_code == 403
        with pytest.raises(HTTPException) as e:
            await rp.hapus_lapisan(dok["id"], user=ADMIN_B)
        assert e.value.status_code == 403
        # Super-admin boleh.
        await rp.ubah_lapisan(dok["id"], _in(nama="Ganti", version=1), user=SUPER)
    asyncio.run(run())


def test_lapisan_pusat_tak_bisa_diubah_admin_satker(database):
    async def run():
        dok = await rp.buat_lapisan(_in(), user=SUPER)
        with pytest.raises(HTTPException) as e:
            await rp.ubah_lapisan(dok["id"], _in(version=1), user=ADMIN_A)
        assert e.value.status_code == 403
    asyncio.run(run())


def test_ubah_wajib_versi_dan_menolak_versi_basi(database):
    async def run():
        dok = await rp.buat_lapisan(_in(), user=ADMIN_A)
        with pytest.raises(HTTPException) as e:
            await rp.ubah_lapisan(dok["id"], _in(), user=ADMIN_A)
        assert e.value.status_code == 428
        baru = await rp.ubah_lapisan(dok["id"], _in(aktif=False, version=1), user=ADMIN_A)
        assert baru["version"] == 2 and baru["aktif"] is False
        with pytest.raises(HTTPException) as e:
            await rp.ubah_lapisan(dok["id"], _in(version=1), user=ADMIN_A)
        assert e.value.status_code == 409
    asyncio.run(run())


def test_alamat_ubin_ganda_ditolak(database):
    async def run():
        await rp.buat_lapisan(_in(), user=ADMIN_A)
        with pytest.raises(HTTPException) as e:
            await rp.buat_lapisan(_in(nama="Lagi"), user=ADMIN_B)
        assert e.value.status_code == 409
    asyncio.run(run())


def test_masukan_tak_sah_400(database):
    async def run():
        with pytest.raises(HTTPException) as e:
            await rp.buat_lapisan(_in(url_template="javascript:x{z}{x}{y}"), user=ADMIN_A)
        assert e.value.status_code == 400
    asyncio.run(run())


def test_registri_selamat_dari_reset():
    assert "peta_lapisan" in RESET_KEEP_COLLECTIONS


def test_router_terdaftar_di_server():
    from pathlib import Path
    src = (Path(__file__).resolve().parents[2] / "server.py").read_text(encoding="utf-8")
    assert "from routes.peta_lapisan import peta_lapisan_router" in src
    assert "api_router.include_router(peta_lapisan_router)" in src
