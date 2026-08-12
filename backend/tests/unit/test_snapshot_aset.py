"""Penyegaran snapshot identitas aset (Prinsip 1 Bab 5):

  1. Perakit operasi murni — bentuk datar vs array, dan field yang TIDAK
     disebut tak boleh ikut ditulis (ganti nama ≠ menghapus kode).
  2. Reklasifikasi menyegarkan register datar DAN baris array `aset[]`;
     aset lain dalam dokumen yang sama tidak ikut berubah.
  3. Registry menutup seluruh koleksi register yang menyimpan snapshot.
"""
import asyncio

import pytest
from mongomock_motor import AsyncMongoMockClient

from snapshot_aset import (FIELD_IDENTITAS, REGISTER_SNAPSHOT_ASET,
                           operasi_segar, segarkan_snapshot_aset)


def _jalan(coro):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_operasi_murni_datar_dan_array():
    filt, upd = operasi_segar("datar", "as-1", {"asset_code": "K2", "NUP": "7"})
    assert filt == {"asset_id": "as-1"}
    assert upd == {"$set": {"asset_code": "K2", "NUP": "7"}}

    filt, upd = operasi_segar("aset", "as-1", {"asset_code": "K2"})
    assert filt == {"aset.asset_id": "as-1"}
    assert upd == {"$set": {"aset.$.asset_code": "K2"}}


def test_field_tak_disebut_tak_ditulis():
    """Ganti nama saja tak boleh menimpa kode/NUP dengan nilai kosong."""
    _, upd = operasi_segar("datar", "as-1", {"asset_name": "Meja Baru"})
    assert upd == {"$set": {"asset_name": "Meja Baru"}}
    # Nilai None diabaikan; tanpa nilai sah sama sekali → tidak ada operasi.
    assert operasi_segar("datar", "as-1", {"asset_code": None}) == (None, None)
    assert operasi_segar("datar", "", {"asset_code": "K2"}) == (None, None)
    # Kunci di luar identitas tak boleh menyelinap masuk.
    _, upd = operasi_segar("datar", "as-1",
                           {"asset_code": "K2", "purchase_price": "9"})
    assert upd == {"$set": {"asset_code": "K2"}}


def test_registry_menutup_register_siklus():
    nama = {k for k, _ in REGISTER_SNAPSHOT_ASET}
    # Register yang lahir dari gelombang permohonan aset WAJIB ikut, kalau
    # tidak dokumen resminya memuat identitas usang setelah reklasifikasi.
    for wajib in ("tgr_register", "pemanfaatan_usulan", "pemusnahan_usulan",
                  "henti_guna", "psp", "penggunaan_proses", "pemanfaatan",
                  "usulan_penghapusan", "pemindahtanganan"):
        assert wajib in nama, wajib
    assert {b for _, b in REGISTER_SNAPSHOT_ASET} == {"datar", "aset"}
    assert FIELD_IDENTITAS == ("asset_code", "NUP", "asset_name")


def test_penyebaran_menyegarkan_datar_dan_array():
    async def skenario():
        db = AsyncMongoMockClient()["uji"]
        await db.tgr_register.insert_one({
            "id": "t1", "asset_id": "as-1", "asset_code": "3050104001",
            "NUP": "9", "asset_name": "Mesin Cetak"})
        await db.henti_guna.insert_one({
            "id": "h1", "asset_id": "as-1", "asset_code": "3050104001",
            "NUP": "9", "asset_name": "Mesin Cetak"})
        await db.pemusnahan.insert_one({"id": "b1", "aset": [
            {"asset_id": "as-1", "asset_code": "3050104001", "NUP": "9",
             "asset_name": "Mesin Cetak"},
            {"asset_id": "as-2", "asset_code": "3100102001", "NUP": "3",
             "asset_name": "PC Unit"}]})

        hasil = await segarkan_snapshot_aset(
            db, "as-1", asset_code="3050104002", NUP="12")

        t = await db.tgr_register.find_one({"id": "t1"}, {"_id": 0})
        assert (t["asset_code"], t["NUP"]) == ("3050104002", "12")
        assert t["asset_name"] == "Mesin Cetak"  # tak disebut → utuh
        h = await db.henti_guna.find_one({"id": "h1"}, {"_id": 0})
        assert (h["asset_code"], h["NUP"]) == ("3050104002", "12")

        ba = await db.pemusnahan.find_one({"id": "b1"}, {"_id": 0})
        assert ba["aset"][0]["asset_code"] == "3050104002"
        assert ba["aset"][0]["NUP"] == "12"
        # Aset LAIN dalam dokumen yang sama tak boleh ikut berubah.
        assert ba["aset"][1]["asset_code"] == "3100102001"
        assert ba["aset"][1]["NUP"] == "3"

        assert hasil.get("tgr_register") == 1
        assert hasil.get("pemusnahan") == 1
    _jalan(skenario())


def test_reklasifikasi_menyegarkan_register(monkeypatch):
    """Jalur nyata: POST /pembukuan/reklasifikasi → snapshot ikut segar."""
    import routes.mutasi_bmn as rm
    import shared_utils as su

    fake = AsyncMongoMockClient()["uji"]

    async def _diam(*a, **k):
        return None

    for mod in (rm, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)
        if hasattr(mod, "log_audit"):
            monkeypatch.setattr(mod, "log_audit", _diam, raising=False)
    monkeypatch.setattr(su, "pastikan_akses_aset", _diam)

    async def skenario():
        await fake.assets.insert_one({
            "id": "as-1", "asset_code": "3050104001", "NUP": "9",
            "asset_name": "Mesin Cetak", "purchase_price": "12000000",
            "activity_id": "", "dihapus": False, "version": 1})
        await fake.tgr_register.insert_one({
            "id": "t1", "asset_id": "as-1", "asset_code": "3050104001",
            "NUP": "9", "asset_name": "Mesin Cetak"})

        fn = rm.reklasifikasi_aset
        while hasattr(fn, "__wrapped__"):
            fn = fn.__wrapped__
        await fn(rm.ReklasifikasiIn(asset_id="as-1",
                                    kode_baru="3050104002",
                                    tanggal_buku="2026-08-12",
                                    alasan="Koreksi kodefikasi"),
                 request=None, user={"username": "adm1", "role": "admin",
                                     "kode_satker": ""})

        master = await fake.assets.find_one({"id": "as-1"}, {"_id": 0})
        assert master["asset_code"] == "3050104002"
        t = await fake.tgr_register.find_one({"id": "t1"}, {"_id": 0})
        assert t["asset_code"] == "3050104002", "snapshot TGR tertinggal usang"
        assert t["NUP"] == master["NUP"]
    _jalan(skenario())
