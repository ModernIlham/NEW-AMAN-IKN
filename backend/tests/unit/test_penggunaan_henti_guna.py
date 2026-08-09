"""Jalur HENTI GUNA pada tiket BMN idle (mandat aset tetap 2026-08-09):

  usul_serah          → jurnal 401 Penghentian Aset Dari Penggunaan
  digunakan_kembali   → jurnal 402 Penggunaan kembali — HANYA bila aset
                        sempat dihentikan (pernah usul_serah); digunakan
                        kembali langsung dari klarifikasi tidak berjurnal.

Kedua kode dulu referensi mati (tak pernah ditulis modul mana pun).
"""
import asyncio

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.penggunaan as rpg

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
    for mod in (rpg, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)
        if hasattr(mod, "log_audit"):
            monkeypatch.setattr(mod, "log_audit", _diam, raising=False)
    # mongomock_motor mengembalikan None bila find_one_and_update dipanggil
    # dengan kwarg projection (kombinasi projection+return_document) — kode
    # produksi benar di Mongo asli, jadi emulasikan di sisi uji saja. Patch
    # di tingkat kelas karena tiap akses atribut membuat objek koleksi baru.
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


async def _seed(dbx, status="klarifikasi", riwayat=None):
    await dbx.assets.insert_one({
        "id": "as-1", "asset_code": "3050104001", "NUP": "1",
        "purchase_price": "9000000", "version": 1})
    await dbx.bmn_idle.insert_one({
        "id": "idle-1", "asset_id": "as-1", "kode_satker": "",
        "status": status, "riwayat": riwayat or []})


def test_usul_serah_berjurnal_401(dbx):
    async def skenario():
        await _seed(dbx)
        await _unwrap(rpg.transisi_idle)(
            "idle-1", rpg.TransisiIdleIn(status="usul_serah",
                                         nomor_usulan="US-1/2026"),
            admin=ADMIN)
        j = await dbx.mutasi_bmn.find_one({"kode_transaksi": "401"})
        assert j and j["asset_id"] == "as-1" and j["nilai"] == 9_000_000
        assert await dbx.mutasi_bmn.count_documents({}) == 1
    _jalan(skenario())


def test_digunakan_kembali_setelah_henti_berjurnal_402(dbx):
    async def skenario():
        await _seed(dbx, status="usul_serah",
                    riwayat=[{"status": "usul_serah", "tanggal": "t"}])
        await _unwrap(rpg.transisi_idle)(
            "idle-1", rpg.TransisiIdleIn(status="digunakan_kembali"),
            admin=ADMIN)
        j = await dbx.mutasi_bmn.find_one({"kode_transaksi": "402"})
        assert j and j["asset_id"] == "as-1"
    _jalan(skenario())


def test_digunakan_kembali_tanpa_henti_tidak_berjurnal(dbx):
    async def skenario():
        await _seed(dbx)   # klarifikasi, belum pernah usul_serah
        await _unwrap(rpg.transisi_idle)(
            "idle-1", rpg.TransisiIdleIn(status="digunakan_kembali"),
            admin=ADMIN)
        assert await dbx.mutasi_bmn.count_documents({}) == 0
    _jalan(skenario())
