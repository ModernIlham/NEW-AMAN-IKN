"""Tautan pelaksana (penyedia jasa) catatan Pemeliharaan ke direktori
instansi luar (PGW-11).

Pemeliharaan bukan penyerahan penguasaan BMN: tak ada pemeriksaan skema,
hanya peringatan bila penyedia nonaktif. Teks `pelaksana` tetap tersimpan.
"""
import asyncio

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import routes.pemeliharaan as rp

USER = {"username": "op1", "role": "operator", "kode_satker": ""}


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
    monkeypatch.setattr(rp, "db", fake)
    monkeypatch.setattr(rp, "pastikan_akses_aset", _diam)
    _jalan(fake.assets.insert_one({"id": "a1", "asset_code": "3100102001", "NUP": 1,
                                   "asset_name": "AC Split", "condition": "RR"}))
    _jalan(fake.instansi_luar.insert_many([
        {"id": "pt1", "nama": "PT Servis Andal", "kelompok": "pihak_ketiga", "tataran": "",
         "jenis": "badan_usaha_swasta", "aktif": True},
        {"id": "kop1", "nama": "Koperasi Lama", "kelompok": "pihak_ketiga", "tataran": "",
         "jenis": "koperasi", "aktif": False}]))
    return fake


def _catat(**kw):
    dasar = {"asset_id": "a1", "tanggal": "2026-11-01", "jenis": "berat",
             "uraian": "Ganti kompresor", "biaya": 1_500_000, "pelaksana": "CV Servis"}
    dasar.update(kw)
    return _jalan(_unwrap(rp.create_pemeliharaan)(rp.PemeliharaanIn(**dasar), user=USER))


def test_tanpa_tautan_perilaku_lama(dbx):
    r = _catat()
    assert r["peringatan_kebijakan"] == [] and r["pelaksana_instansi_id"] == ""
    simpan = _jalan(dbx.pemeliharaan.find_one({"id": r["id"]}, {"_id": 0}))
    assert "peringatan_kebijakan" not in simpan


def test_tautan_disalin_teks_tetap_tanpa_pemeriksaan_skema(dbx):
    r = _catat(pelaksana_instansi_id="pt1")
    assert r["peringatan_kebijakan"] == []
    simpan = _jalan(dbx.pemeliharaan.find_one({"id": r["id"]}, {"_id": 0}))
    assert simpan["pelaksana"] == "CV Servis"
    assert (simpan["pelaksana_instansi_id"], simpan["pelaksana_kelompok"],
            simpan["pelaksana_jenis_instansi"]) == ("pt1", "pihak_ketiga", "badan_usaha_swasta")


def test_penyedia_nonaktif_diperingatkan_tetap_tersimpan(dbx):
    r = _catat(pelaksana_instansi_id="kop1")
    assert r["peringatan_kebijakan"] == [
        "Instansi pelaksana ini berstatus nonaktif di direktori"]
    assert _jalan(dbx.pemeliharaan.count_documents({})) == 1


def test_tautan_patah_400_tanpa_menyimpan(dbx):
    with pytest.raises(HTTPException) as e:
        _catat(pelaksana_instansi_id="hantu")
    assert e.value.status_code == 400 and "Pelaksana" in e.value.detail
    assert _jalan(dbx.pemeliharaan.count_documents({})) == 0
