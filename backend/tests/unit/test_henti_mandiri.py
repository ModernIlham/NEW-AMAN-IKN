"""Henti guna MANDIRI (ASET-HENTI-MANDIRI) — SK/BA di luar jalur idle:

  1. Pencatatan wajib nomor SK/BA + alasan; jurnal 401 terbit; tiket
     dihentikan aktif ganda ditolak (409).
  2. Aset dalam tiket BMN idle berjalan diarahkan ke jalur idle (400) —
     jurnal 401/402 di sana, register ganda = jurnal ganda.
  3. Gunakan kembali wajib dokumen; jurnal 402 terbit; klik ulang 409.
"""
import asyncio

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import routes.penggunaan as rg

USER = {"username": "op1", "role": "operator", "kode_satker": ""}
ADMIN = {"username": "adm1", "role": "admin", "kode_satker": ""}


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
    for mod in (rg, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)
        if hasattr(mod, "log_audit"):
            monkeypatch.setattr(mod, "log_audit", _diam, raising=False)
    monkeypatch.setattr(rg, "pastikan_akses_dok_satker", _diam)
    monkeypatch.setattr(su, "pastikan_akses_aset", _diam)
    rekaman = []

    async def _rekam(entri):
        rekaman.append(entri)
        return True

    monkeypatch.setattr(su, "catat_mutasi_bmn", _rekam)
    fake.jurnal_rekaman = rekaman
    from mongomock_motor import AsyncMongoMockCollection
    asli = AsyncMongoMockCollection.find_one_and_update

    async def _fau(self, filter, update, **kw):
        kw.pop("projection", None)
        doc = await asli(self, filter, update, **kw)
        if doc:
            doc.pop("_id", None)
        return doc

    monkeypatch.setattr(AsyncMongoMockCollection, "find_one_and_update", _fau)
    return fake


async def _seed(dbx):
    await dbx.assets.insert_one({
        "id": "as-1", "asset_code": "3050104001", "NUP": "9",
        "asset_name": "Mesin Cetak", "purchase_price": "12000000",
        "condition": "Baik", "activity_id": "", "version": 1})


async def _catat(asset_id="as-1"):
    return await _unwrap(rg.catat_henti_guna)(
        rg.HentiGunaIn(asset_id=asset_id, nomor_dokumen="SK-4/KPB/2026",
                       tanggal_dokumen="2026-08-01",
                       alasan="Rusak menunggu perbaikan besar"),
        user=USER)


def test_catat_henti_dokumen_jurnal_dan_anti_ganda(dbx):
    async def skenario():
        await _seed(dbx)
        # Tanpa nomor SK/BA → ditolak.
        with pytest.raises(HTTPException) as e:
            await _unwrap(rg.catat_henti_guna)(
                rg.HentiGunaIn(asset_id="as-1", alasan="Rusak menunggu"),
                user=USER)
        assert e.value.status_code == 400
        t = await _catat()
        assert t["status"] == "dihentikan"
        j401 = [e for e in dbx.jurnal_rekaman
                if e.get("kode_transaksi") == "401"]
        assert len(j401) == 1
        assert j401[0]["asset_id"] == "as-1"
        assert j401[0]["nilai"] == 12_000_000
        assert j401[0]["ref_id"] == t["id"]
        # Tiket dihentikan masih aktif → catat lagi ditolak.
        with pytest.raises(HTTPException) as e2:
            await _catat()
        assert e2.value.status_code == 409
    _jalan(skenario())


def test_aset_dalam_tiket_idle_diarahkan_ke_jalur_idle(dbx):
    async def skenario():
        await _seed(dbx)
        await dbx.bmn_idle.insert_one({
            "id": "idle-1", "asset_id": "as-1", "status": "klarifikasi",
            "kode_satker": ""})
        with pytest.raises(HTTPException) as e:
            await _catat()
        assert e.value.status_code == 400
        assert "idle" in str(e.value.detail).lower()
    _jalan(skenario())


def test_gunakan_kembali_dokumen_dan_jurnal_402(dbx):
    async def skenario():
        await _seed(dbx)
        t = await _catat()
        # Tanpa nomor dokumen → ditolak.
        with pytest.raises(HTTPException) as e:
            await _unwrap(rg.gunakan_kembali_henti)(
                t["id"], rg.GunakanKembaliIn(), admin=ADMIN)
        assert e.value.status_code == 400
        r = await _unwrap(rg.gunakan_kembali_henti)(
            t["id"], rg.GunakanKembaliIn(nomor_dokumen="SK-9/KPB/2026",
                                         tanggal_dokumen="2026-08-09"),
            admin=ADMIN)
        assert r["status"] == "digunakan_kembali"
        j402 = [e for e in dbx.jurnal_rekaman
                if e.get("kode_transaksi") == "402"]
        assert len(j402) == 1
        assert j402[0]["asset_id"] == "as-1"
        # Klik ulang: tiket sudah bukan dihentikan → 409 (CAS).
        with pytest.raises(HTTPException) as e2:
            await _unwrap(rg.gunakan_kembali_henti)(
                t["id"], rg.GunakanKembaliIn(nomor_dokumen="SK-9/KPB/2026"),
                admin=ADMIN)
        assert e2.value.status_code == 409
    _jalan(skenario())
