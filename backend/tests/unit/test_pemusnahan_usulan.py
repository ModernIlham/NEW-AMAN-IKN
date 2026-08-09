"""Usulan pemusnahan berstatus (ASET-MUSNAH, PMK 83/2016):

  1. Usulan hanya untuk aset Rusak Berat; aset dalam usulan berjalan
     ditolak ganda (409).
  2. Dokumen wajib per tahap: nomor surat usulan (diajukan), nomor
     persetujuan (disetujui), nomor BA (dilaksanakan); tanggal BA tidak
     boleh di masa depan.
  3. Efek dilaksanakan: BA pemusnahan LAHIR otomatis dari usulan —
     nomor persetujuan & aset tersnapshot, ber-taut usulan_id.
"""
import asyncio
from datetime import date, timedelta

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import routes.pemusnahan as rm

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
    for mod in (rm, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)
        if hasattr(mod, "log_audit"):
            monkeypatch.setattr(mod, "log_audit", _diam, raising=False)
    # routes.pemusnahan mengimpor pastikan_akses_aset di tingkat modul —
    # patch di modulnya langsung (patch shared_utils tidak berefek).
    monkeypatch.setattr(rm, "pastikan_akses_aset", _diam)
    monkeypatch.setattr(rm, "pastikan_akses_dok_satker", _diam)
    # mongomock: find_one_and_update + kwarg projection → None (siasat
    # kelas, lihat test_tgr) — transisi usulan memakainya.
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
        "id": "as-rb", "asset_code": "3050104001", "NUP": "3",
        "asset_name": "Kursi Hancur", "purchase_price": "750000",
        "condition": "Rusak Berat", "activity_id": "", "version": 1})
    await dbx.assets.insert_one({
        "id": "as-ok", "asset_code": "3050104002", "NUP": "1",
        "asset_name": "Meja Baik", "purchase_price": "2000000",
        "condition": "Baik", "activity_id": "", "version": 1})


async def _buka(asset_ids=("as-rb",)):
    return await _unwrap(rm.buat_usulan_pemusnahan)(
        rm.UsulanPemusnahanIn(asset_ids=list(asset_ids), cara="dihancurkan",
                              keterangan="Rusak total"),
        user=USER)


def test_usulan_hanya_rusak_berat_dan_anti_ganda(dbx):
    async def skenario():
        await _seed(dbx)
        with pytest.raises(HTTPException) as e:
            await _buka(("as-ok",))
        assert e.value.status_code == 400
        assert "rusak berat" in str(e.value.detail).lower()
        u = await _buka()
        assert u["status"] == "draf"
        assert u["aset"][0]["harga"] == "750000"
        # Aset sama dalam usulan berjalan → 409.
        with pytest.raises(HTTPException) as e2:
            await _buka()
        assert e2.value.status_code == 409
    _jalan(skenario())


def test_dokumen_wajib_per_tahap(dbx):
    async def skenario():
        await _seed(dbx)
        u = await _buka()
        # diajukan tanpa nomor surat usulan → ditolak.
        with pytest.raises(HTTPException) as e:
            await _unwrap(rm.transisi_usulan_pemusnahan)(
                u["id"], rm.TransisiUsulanPemusnahanIn(status="diajukan"),
                admin=ADMIN)
        assert e.value.status_code == 400
        await _unwrap(rm.transisi_usulan_pemusnahan)(
            u["id"], rm.TransisiUsulanPemusnahanIn(
                status="diajukan", nomor_dokumen="ND-3/2026"), admin=ADMIN)
        await _unwrap(rm.transisi_usulan_pemusnahan)(
            u["id"], rm.TransisiUsulanPemusnahanIn(
                status="disetujui", nomor_dokumen="S-77/KNL/2026"),
            admin=ADMIN)
        # dilaksanakan bertanggal masa depan → ditolak.
        besok = (date.today() + timedelta(days=2)).isoformat()
        with pytest.raises(HTTPException) as e2:
            await _unwrap(rm.transisi_usulan_pemusnahan)(
                u["id"], rm.TransisiUsulanPemusnahanIn(
                    status="dilaksanakan", nomor_dokumen="BA-5/2026",
                    tanggal_dokumen=besok), admin=ADMIN)
        assert e2.value.status_code == 400
        assert "masa depan" in str(e2.value.detail)
    _jalan(skenario())


def test_efek_dilaksanakan_lahirkan_ba(dbx):
    async def skenario():
        await _seed(dbx)
        u = await _buka()
        await _unwrap(rm.transisi_usulan_pemusnahan)(
            u["id"], rm.TransisiUsulanPemusnahanIn(
                status="diajukan", nomor_dokumen="ND-3/2026"), admin=ADMIN)
        await _unwrap(rm.transisi_usulan_pemusnahan)(
            u["id"], rm.TransisiUsulanPemusnahanIn(
                status="disetujui", nomor_dokumen="S-77/KNL/2026"),
            admin=ADMIN)
        r = await _unwrap(rm.transisi_usulan_pemusnahan)(
            u["id"], rm.TransisiUsulanPemusnahanIn(
                status="dilaksanakan", nomor_dokumen="BA-5/2026",
                tanggal_dokumen=date.today().isoformat()), admin=ADMIN)
        assert r["status"] == "dilaksanakan"
        ba = await dbx.pemusnahan.find_one({"nomor_ba": "BA-5/2026"},
                                           {"_id": 0})
        assert ba is not None
        assert ba["nomor_persetujuan"] == "S-77/KNL/2026"
        assert ba["cara"] == "dihancurkan"
        assert [a["asset_id"] for a in ba["aset"]] == ["as-rb"]
        assert ba["usulan_id"] == u["id"]
        assert r["ba_id"] == ba["id"]
    _jalan(skenario())
