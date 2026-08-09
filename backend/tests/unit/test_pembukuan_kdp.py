"""Modul pencatatan KDP (mandat aset tetap 2026-08-09) — tiga sifat:

  1. Aset baru golongan 7 berjurnal 502 (bukan 100/101) — helper murni.
  2. Pengembangan (503) menambah nilai berjalan KDP + jurnal nilai-murni
     (jumlah 0); aset non-golongan-7 ditolak.
  3. Penyelesaian menulis PASANGAN 505 (keluar kode 7) + 105 (masuk kode
     definitif) senilai akumulasi, aset dimutakhirkan in-place; tujuan
     golongan 7/1 ditolak.
"""
import asyncio

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import routes.mutasi_bmn as rmb

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
    import shared_utils as su
    for mod in (rmb, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)
        if hasattr(mod, "log_audit"):
            monkeypatch.setattr(mod, "log_audit", _diam, raising=False)
    monkeypatch.setattr(su, "ensure_activity_not_sealed", _diam)
    return fake


async def _seed_kdp(dbx):
    await dbx.assets.insert_one({
        "id": "kdp-1", "asset_code": "7010101001", "NUP": "1",
        "asset_name": "Pembangunan Gedung Arsip", "purchase_price": "500000000",
        "activity_id": "", "version": 1})


def test_kode_jurnal_aset_baru_golongan_7_menjadi_502():
    from mutasi_bmn_utils import kode_jurnal_aset_baru
    assert kode_jurnal_aset_baru("7010101001", "Kontrak pembangunan") == "502"
    assert kode_jurnal_aset_baru("3050104001", "Pembelian dari pengadaan") == "101"
    assert kode_jurnal_aset_baru("3050104001", "Hibah masyarakat") == "100"


def test_pengembangan_menambah_nilai_dan_berjurnal_503(dbx):
    async def skenario():
        await _seed_kdp(dbx)
        r = await _unwrap(rmb.pengembangan_kdp)(
            "kdp-1", rmb.KdpPengembanganIn(nilai=250_000_000,
                                           keterangan="termin II"),
            user=USER)
        assert r["nilai_berjalan"] == 750_000_000
        aset = await dbx.assets.find_one({"id": "kdp-1"})
        assert aset["purchase_price"] == "750000000"
        j = await dbx.mutasi_bmn.find_one({"kode_transaksi": "503"})
        assert j and j["jumlah"] == 0 and j["nilai"] == 250_000_000
        assert "termin II" in j["keterangan"]
    _jalan(skenario())


def test_pengembangan_menolak_aset_non_kdp(dbx):
    async def skenario():
        await dbx.assets.insert_one({
            "id": "pc-1", "asset_code": "3050104001", "NUP": "1",
            "asset_name": "PC", "purchase_price": "9000000", "version": 1})
        with pytest.raises(HTTPException) as e:
            await _unwrap(rmb.pengembangan_kdp)(
                "pc-1", rmb.KdpPengembanganIn(nilai=1), user=USER)
        assert e.value.status_code == 400
    _jalan(skenario())


def test_selesaikan_menulis_pasangan_505_dan_105_lalu_mutakhir_in_place(dbx):
    async def skenario():
        await _seed_kdp(dbx)
        r = await _unwrap(rmb.selesaikan_kdp)(
            "kdp-1", rmb.KdpSelesaiIn(kode_baru="4010101001",
                                      alasan="serah terima fisik"),
            user=USER)
        assert r["kode_baru"] == "4010101001"
        aset = await dbx.assets.find_one({"id": "kdp-1"})
        assert aset["asset_code"] == "4010101001"
        assert aset["riwayat_reklasifikasi"][0]["jenis"] == "penyelesaian_kdp"
        keluar = await dbx.mutasi_bmn.find_one({"kode_transaksi": "505"})
        masuk = await dbx.mutasi_bmn.find_one({"kode_transaksi": "105"})
        assert keluar and keluar["kode_barang"] == "7010101001"
        assert masuk and masuk["kode_barang"] == "4010101001"
        assert keluar["nilai"] == masuk["nilai"] == 500_000_000
        assert keluar["tanggal_buku"] == masuk["tanggal_buku"]
    _jalan(skenario())


def test_selesaikan_menolak_tujuan_kdp_lagi_dan_persediaan(dbx):
    async def skenario():
        await _seed_kdp(dbx)
        for kode in ("7010101002", "1010301001"):
            with pytest.raises(HTTPException) as e:
                await _unwrap(rmb.selesaikan_kdp)(
                    "kdp-1", rmb.KdpSelesaiIn(kode_baru=kode), user=USER)
            assert e.value.status_code == 400
    _jalan(skenario())


def test_daftar_kdp_hanya_golongan_7(dbx):
    async def skenario():
        await _seed_kdp(dbx)
        await dbx.assets.insert_one({
            "id": "pc-1", "asset_code": "3050104001", "NUP": "1",
            "asset_name": "PC", "purchase_price": "9000000", "version": 1})
        r = await _unwrap(rmb.daftar_kdp)(_user=USER)
        assert [it["id"] for it in r["items"]] == ["kdp-1"]
        assert r["total_nilai"] == 500_000_000
    _jalan(skenario())
