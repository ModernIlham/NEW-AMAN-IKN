"""Direktori gabungan & pembaca backend yang mengenali orang luar (PGW-06).

Rencana: docs/RENCANA-MASTER-PEGAWAI-EKSTERNAL.md — kontrak 6.5, peta 7.2.
"""
import asyncio
from functools import partial

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient
from starlette.requests import Request

import direktori_pegawai as dp
import routes.direktori_pegawai as rdp
from shared_utils import scope_query_field_satker

USER_A = {"username": "a", "role": "admin", "kode_satker": "111111"}
USER_B = {"username": "b", "role": "admin", "kode_satker": "222222"}


def _jalan(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


def _req():
    return Request({"type": "http", "method": "POST", "path": "/", "headers": [],
                    "client": ("127.0.0.1", 1), "app": None})


def _galat(coro):
    with pytest.raises(HTTPException) as e:
        _jalan(coro)
    return e.value


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import db as db_mod
    import shared_utils as su
    for mod in (rdp, su, db_mod):
        monkeypatch.setattr(mod, "db", fake, raising=False)
    monkeypatch.setattr(su.limiter, "enabled", False)
    _jalan(fake.pegawai.insert_many([
        {"id": "pa", "nama": "Ani Internal A", "nip": "111", "kode_satker": "111111",
         "status": "aktif"},
        {"id": "pb", "nama": "Budi Internal B", "nip": "222", "kode_satker": "222222",
         "status": "aktif"},
        {"id": "pk", "nama": "Kembar Internal", "nip": "999", "kode_satker": "111111"},
    ]))
    _jalan(fake.pegawai_luar.insert_many([
        {"id": "l1", "nama": "Citra Pusat", "nip": "333", "kelompok": "eksternal",
         "tataran": "pusat", "instansi_nama": "Kementerian X",
         "satker_luar_nama": "Setjen", "status": "aktif"},
        {"id": "l2", "nama": "Dedi Daerah", "nip": "444", "kelompok": "eksternal",
         "tataran": "daerah", "instansi_nama": "Kab Y", "provinsi_nama": "Prov Z",
         "satker_luar_nama": "Dinas", "status": "aktif"},
        {"id": "l3", "nama": "Eka Badan", "nip": "555", "kelompok": "pihak_ketiga",
         "tataran": "", "instansi_nama": "PT A", "satker_luar_nama": "Pusat",
         "status": "aktif", "kapasitas_bertindak": "pengurus_berwenang"},
        {"id": "l4", "nama": "Fajar Keluar", "nip": "666", "kelompok": "pihak_ketiga",
         "tataran": "", "instansi_nama": "PT A", "satker_luar_nama": "Pusat",
         "status": "nonaktif"},
        {"id": "l5", "nama": "Kembar Luar", "nip": "999", "kelompok": "eksternal",
         "tataran": "pusat", "instansi_nama": "K", "satker_luar_nama": "S",
         "status": "aktif"},
    ]))
    return fake


# ── penjawab kelompok ──────────────────────────────────────────────────────
def test_kelompok_mengenali_internal_sendiri_dan_luar_aktif_saja(dbx):
    hasil = _jalan(rdp.kelompok_direktori_pegawai(
        _req(), rdp.NomorIn(nomor=["111", "222", "333", "444", "555", "666", "777"]),
        user=USER_A))["nomor"]
    assert hasil == {"111": "internal", "333": "eksternal_pusat",
                     "444": "eksternal_daerah", "555": "pihak_ketiga"}


def test_kelompok_tidak_mengembalikan_nomor_yang_tak_ditanyakan(dbx):
    hasil = _jalan(rdp.kelompok_direktori_pegawai(
        _req(), rdp.NomorIn(nomor=["333"]), user=USER_A))["nomor"]
    assert set(hasil) == {"333"}


def test_kelompok_lebih_dari_500_nomor_ditolak(dbx):
    e = _galat(rdp.kelompok_direktori_pegawai(
        _req(), rdp.NomorIn(nomor=[str(i) for i in range(501)]), user=USER_A))
    assert e.status_code == 400


def test_nomor_di_internal_dan_luar_dikenali_internal(dbx):
    hasil = _jalan(rdp.kelompok_direktori_pegawai(
        _req(), rdp.NomorIn(nomor=["999"]), user=USER_A))["nomor"]
    assert hasil == {"999": "internal"}
    satu = _jalan(dp.cari_orang(partial(scope_query_field_satker, USER_A), "999",
                                database=dbx))
    assert satu["ranah"] == "internal" and satu["nama"] == "Kembar Internal"


def test_cari_orang_luar_membawa_kelompok_dan_instansi(dbx):
    o = _jalan(dp.cari_orang(partial(scope_query_field_satker, USER_B), "444", database=dbx))
    assert (o["ranah"], o["kunci_ikon"], o["instansi_nama"]) == \
        ("luar", "eksternal_daerah", "Kab Y")
    assert _jalan(dp.cari_orang(partial(scope_query_field_satker, USER_B), "111",
                                database=dbx)) is None


# ── daftar direktori ───────────────────────────────────────────────────────
def test_direktori_wajib_kelompok(dbx):
    assert _galat(rdp.daftar_direktori_pegawai(user=USER_A)).status_code == 400


def test_direktori_internal_ter_scope_satker(dbx):
    hasil = _jalan(rdp.daftar_direktori_pegawai(kelompok="internal", user=USER_A))
    assert {i["nip"] for i in hasil["items"]} == {"111", "999"}
    assert all(i["kunci_ikon"] == "internal" for i in hasil["items"])


def test_direktori_luar_aktif_dan_membawa_instansi_serta_satker(dbx):
    hasil = _jalan(rdp.daftar_direktori_pegawai(kelompok="pihak_ketiga", user=USER_B))
    assert [i["nip"] for i in hasil["items"]] == ["555"]
    i = hasil["items"][0]
    assert i["instansi_nama"] == "PT A" and i["satker_luar_nama"] == "Pusat"
    assert i["kunci_ikon"] == "pihak_ketiga"
    daerah = _jalan(rdp.daftar_direktori_pegawai(kelompok="eksternal", tataran="daerah",
                                                 user=USER_A))
    assert [i["nip"] for i in daerah["items"]] == ["444"]
    cari = _jalan(rdp.daftar_direktori_pegawai(kelompok="eksternal", q="Kementerian",
                                               user=USER_A))
    assert [i["nip"] for i in cari["items"]] == ["333"]


def test_identifikasi_kartu_internal_dulu_lalu_luar(dbx):
    from kartu_utils import hash_kandidat
    _jalan(dbx.pegawai_luar.update_one({"id": "l1"}, {"$set": {
        "kartu_uid_hashes": hash_kandidat("04AABBCCDDEEFF")}}))
    hasil = _jalan(rdp.identifikasi_kartu_direktori(
        _req(), rdp.KartuDirektoriIn(uid="04AABBCCDDEEFF"), user=USER_A))
    assert hasil["pegawai"]["nip"] == "333" and hasil["pegawai"]["ranah"] == "luar"
    assert "kartu_uid_hashes" not in hasil["pegawai"]
    assert _galat(rdp.identifikasi_kartu_direktori(
        _req(), rdp.KartuDirektoriIn(uid="04112233445566"), user=USER_A)).status_code == 404
