"""Register TGR aset hilang (ASET-TGR, PP 38/2016 + PMK 83/2016):

  1. Tiket hanya untuk aset Tidak Ditemukan; kronologi & penanggung jawab
     wajib.
  2. Keputusan berdokumen: tgr_ditetapkan wajib nomor SKTJM + nilai > 0.
  3. GERBANG: SK penghapusan jalur tidak_ditemukan DITOLAK tanpa tiket TGR
     berkeputusan; dengan tiket bebas_tgr → lolos.
"""
import asyncio

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import routes.penghapusan as rph
import routes.tgr as rt

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
    for mod in (rt, rph, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)
        if hasattr(mod, "log_audit"):
            monkeypatch.setattr(mod, "log_audit", _diam, raising=False)
    monkeypatch.setattr(su, "ensure_activity_not_sealed", _diam)
    # mongomock: find_one_and_update + projection → None (siasat kelas,
    # lihat test_penggunaan_henti_guna) — transisi penghapusan memakainya.
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
        "id": "as-h", "asset_code": "3100102001", "NUP": "7",
        "asset_name": "Proyektor Hilang", "purchase_price": "5000000",
        "inventory_status": "Tidak Ditemukan", "activity_id": "",
        "version": 1})
    await dbx.assets.insert_one({
        "id": "as-b", "asset_code": "3050104001", "NUP": "1",
        "asset_name": "PC Baik", "inventory_status": "ditemukan",
        "condition": "Baik", "activity_id": "", "version": 1})


async def _buka(asset_id="as-h"):
    return await _unwrap(rt.buka_tiket_tgr)(
        rt.TiketTgrIn(asset_id=asset_id, penanggung_jawab="Sdr. Budi",
                      nip_penanggung_jawab="19800101...",
                      kronologi="Hilang saat pindahan gedung B, sudah dicari."),
        user=USER)


def test_tiket_hanya_untuk_aset_tidak_ditemukan(dbx):
    async def skenario():
        await _seed(dbx)
        t = await _buka()
        assert t["status"] == "penelusuran"
        with pytest.raises(HTTPException) as e:
            await _buka("as-b")
        assert e.value.status_code == 400
        # Kronologi pendek ditolak.
        with pytest.raises(HTTPException) as e2:
            await _unwrap(rt.buka_tiket_tgr)(
                rt.TiketTgrIn(asset_id="as-h", penanggung_jawab="Budi",
                              kronologi="hilang"), user=USER)
        assert e2.value.status_code in (400, 409)
    _jalan(skenario())


def test_tgr_ditetapkan_wajib_dokumen_dan_nilai(dbx):
    async def skenario():
        await _seed(dbx)
        t = await _buka()
        await _unwrap(rt.transisi_tgr)(
            t["id"], rt.TransisiTgrIn(status="telaah"), admin=ADMIN)
        with pytest.raises(HTTPException) as e:
            await _unwrap(rt.transisi_tgr)(
                t["id"], rt.TransisiTgrIn(status="tgr_ditetapkan"),
                admin=ADMIN)
        assert e.value.status_code == 400
        # Nomor terisi tetapi nilai ganti rugi 0 → tetap ditolak.
        with pytest.raises(HTTPException) as e0:
            await _unwrap(rt.transisi_tgr)(
                t["id"], rt.TransisiTgrIn(status="tgr_ditetapkan",
                                          nomor_dokumen="SKTJM-1/2026",
                                          nilai_ganti_rugi=0),
                admin=ADMIN)
        assert e0.value.status_code == 400
        assert "Nilai ganti rugi" in str(e0.value.detail)
        r = await _unwrap(rt.transisi_tgr)(
            t["id"], rt.TransisiTgrIn(status="tgr_ditetapkan",
                                      nomor_dokumen="SKTJM-1/2026",
                                      nilai_ganti_rugi=5_000_000),
            admin=ADMIN)
        assert r["status"] == "tgr_ditetapkan"
        assert r["nilai_ganti_rugi"] == 5_000_000
    _jalan(skenario())


def test_gerbang_sk_penghapusan_aset_hilang(dbx):
    async def skenario():
        await _seed(dbx)
        await dbx.usulan_penghapusan.insert_one({
            "id": "uh-1", "kode_satker": "", "asset_id": "as-h",
            "asset_code": "3100102001", "NUP": "7",
            "asset_name": "Proyektor Hilang", "jalur": "tidak_ditemukan",
            "status": "diproses", "riwayat": [],
            "created_at": "2026-08-01"})
        # TANPA tiket TGR berkeputusan → SK ditolak.
        with pytest.raises(HTTPException) as e:
            await _unwrap(rph.transisi_usulan)(
                "uh-1", rph.TransisiIn(status="sk_terbit",
                                       nomor_sk="SK-9/2026",
                                       tanggal_sk="2026-08-09"),
                admin=ADMIN)
        assert e.value.status_code == 400
        assert "TGR" in str(e.value.detail)
        # Tiket TGR bebas_tgr → SK lolos.
        t = await _buka()
        await _unwrap(rt.transisi_tgr)(
            t["id"], rt.TransisiTgrIn(status="telaah"), admin=ADMIN)
        await _unwrap(rt.transisi_tgr)(
            t["id"], rt.TransisiTgrIn(status="bebas_tgr",
                                      nomor_dokumen="SKB-2/2026"),
            admin=ADMIN)
        r = await _unwrap(rph.transisi_usulan)(
            "uh-1", rph.TransisiIn(status="sk_terbit", nomor_sk="SK-9/2026",
                                   tanggal_sk="2026-08-09"),
            admin=ADMIN)
        assert r["status"] == "sk_terbit"
    _jalan(skenario())
