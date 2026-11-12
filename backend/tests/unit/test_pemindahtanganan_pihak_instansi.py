"""Tautan pihak usulan Pemindahtanganan ke direktori instansi luar (PGW-11).

Pemindahtanganan sengaja di luar matriks kebijakan penerima → tanpa
pemeriksaan skema; hanya peringatan bila instansinya nonaktif. Teks `pihak`
tetap tersimpan; instansi yang dirujuk tak bisa dihapus dari direktori.
"""
import asyncio

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import routes.pemindahtanganan as rpt
import tautan_instansi as ti

USER = {"username": "op1", "role": "admin", "kode_satker": ""}


def _unwrap(fn):
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn


def _jalan(coro):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _diam(*a, **k):
    return None


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import shared_utils as su
    for mod in (rpt, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)
    monkeypatch.setattr(rpt, "pastikan_akses_aset", _diam)
    _jalan(fake.assets.insert_one({"id": "a1", "asset_code": "3020101001", "NUP": 1,
                                   "asset_name": "Mobil Dinas", "purchase_price": 250_000_000,
                                   "condition": "RB"}))
    _jalan(fake.instansi_luar.insert_many([
        {"id": "kab1", "nama": "Kabupaten Penajam Paser Utara", "kelompok": "eksternal",
         "tataran": "daerah", "jenis": "pemerintah_kabkota", "aktif": True},
        {"id": "yay1", "nama": "Yayasan Lama", "kelompok": "pihak_ketiga", "tataran": "",
         "jenis": "yayasan", "aktif": False}]))
    return fake


def _usul(**kw):
    dasar = {"bentuk": "hibah", "pihak": "Pemkab PPU", "asset_ids": ["a1"]}
    dasar.update(kw)
    return _jalan(_unwrap(rpt.buat_usulan_pt)(rpt.UsulanPtIn(**dasar), user=USER))


def test_tanpa_tautan_perilaku_lama(dbx):
    r = _usul()
    assert r["peringatan_kebijakan"] == [] and r["pihak_instansi_id"] == ""


def test_tautan_disalin_teks_tetap_tanpa_pemeriksaan_skema(dbx):
    r = _usul(pihak_instansi_id="kab1")
    assert r["peringatan_kebijakan"] == [] and r["pihak"] == "Pemkab PPU"
    simpan = _jalan(dbx.pemindahtanganan.find_one({"id": r["id"]}, {"_id": 0}))
    assert (simpan["pihak_instansi_id"], simpan["pihak_kelompok"], simpan["pihak_tataran"]) == (
        "kab1", "eksternal", "daerah")
    assert "peringatan_kebijakan" not in simpan


def test_nonaktif_diperingatkan_dan_tautan_patah_400(dbx):
    assert _usul(pihak_instansi_id="yay1")["peringatan_kebijakan"] == [
        "Instansi pihak ini berstatus nonaktif di direktori"]
    _jalan(dbx.pemindahtanganan.delete_many({}))
    with pytest.raises(HTTPException) as e:
        _usul(pihak_instansi_id="hantu")
    assert e.value.status_code == 400
    assert _jalan(dbx.pemindahtanganan.count_documents({})) == 0


def test_terdaftar_sebagai_perujuk(dbx):
    _usul(pihak_instansi_id="kab1")
    assert _jalan(ti.modul_perujuk(dbx, "kab1")) == ["Pemindahtanganan"]
