"""Sisi PENERIMAAN alih status penggunaan (ASET-TRANSFER-MASUK):

  1. Tiket alih status ARAH MASUK memakai daftar barang manual (barang
     belum tercatat di pembukuan penerima) — tanpa barang → 400; arah
     keluar tetap wajib asset_ids.
  2. Terminal `dihapus_dibukukan` arah masuk MEMBUKUKAN aset baru +
     jurnal 102 Transfer Masuk + taut balik asset_id ke snapshot tiket.
  3. Helper murni build_asset_transfer_masuk mengisi field inti aset
     (kategori default, harga string, jejak perolehan_transfer).
"""
import asyncio

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import routes.penggunaan as rg
from penggunaan_utils import build_asset_transfer_masuk

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
    # Jurnal Buku Barang direkam, bukan ditulis sungguhan — efek 102
    # diperiksa dari rekaman (catat_mutasi_bmn diimpor lokal dari
    # shared_utils saat transisi, jadi patch atribut modulnya cukup).
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


async def _buka_masuk():
    return await _unwrap(rg.buat_proses)(
        rg.ProsesIn(jenis_proses="alih_status", arah="masuk",
                    pihak_asal="Kementerian PUPR",
                    pihak_tujuan="Otorita IKN",
                    barang_masuk=[rg.BarangMasukIn(
                        asset_code="3100102001", nup="12",
                        asset_name="Genset Kiriman", nilai=25_000_000)]),
        user=USER)


def test_tiket_masuk_pakai_barang_manual(dbx):
    async def skenario():
        t = await _buka_masuk()
        assert t["status"] == "draf"
        assert t["aset"][0]["asset_id"] == ""
        assert t["aset"][0]["nilai"] == 25_000_000
        # Arah masuk tanpa barang → ditolak.
        with pytest.raises(HTTPException) as e:
            await _unwrap(rg.buat_proses)(
                rg.ProsesIn(jenis_proses="alih_status", arah="masuk",
                            pihak_asal="A", pihak_tujuan="B"), user=USER)
        assert e.value.status_code == 400
        assert "barang masuk" in str(e.value.detail).lower()
        # Arah keluar tetap wajib asset_ids.
        with pytest.raises(HTTPException) as e2:
            await _unwrap(rg.buat_proses)(
                rg.ProsesIn(jenis_proses="alih_status", arah="keluar",
                            pihak_asal="A", pihak_tujuan="B"), user=USER)
        assert e2.value.status_code == 400
        assert "aset" in str(e2.value.detail).lower()
    _jalan(skenario())


def test_terminal_masuk_membukukan_aset_dan_jurnal_102(dbx):
    async def skenario():
        t = await _buka_masuk()
        for ke, nomor in (("diajukan", ""), ("disetujui", "S-5/KNL/2026"),
                          ("bast_selesai", "BAST-9/2026"),
                          ("dihapus_dibukukan", "KEP-2/2026")):
            r = await _unwrap(rg.transisi_proses)(
                t["id"], rg.TransisiProsesIn(status=ke, nomor_dokumen=nomor),
                user=ADMIN)
        assert r["status"] == "dihapus_dibukukan"
        # Aset BARU terbukukan dari barang manual.
        aset = await dbx.assets.find_one({"asset_code": "3100102001"},
                                         {"_id": 0})
        assert aset is not None
        assert aset["asset_name"] == "Genset Kiriman"
        assert aset["purchase_price"] == "25000000"
        assert aset["perolehan_transfer"]["tiket_id"] == t["id"]
        assert aset["perolehan_transfer"]["nomor_bast"] == "BAST-9/2026"
        # Snapshot tiket tertaut balik ke aset baru.
        assert r["aset"][0]["asset_id"] == aset["id"]
        # Jurnal 102 Transfer Masuk tercatat dengan nilai perolehan.
        j102 = [e for e in dbx.jurnal_rekaman
                if e.get("kode_transaksi") == "102"]
        assert len(j102) == 1
        assert j102[0]["asset_id"] == aset["id"]
        assert j102[0]["nilai"] == 25_000_000
        assert j102[0]["ref_id"] == t["id"]
    _jalan(skenario())


def test_build_asset_transfer_masuk_field_inti():
    tiket = {"id": "tk-1", "kode_satker": "527xxx", "pihak_asal": "PUPR",
             "nomor_bast": "BAST-9", "nomor_sk_penghapusan": "KEP-2",
             "created_by": "op1"}
    barang = {"asset_code": "3050101001", "nup": "4",
              "asset_name": "Mesin Uji", "nilai": "1500000.0"}
    doc = build_asset_transfer_masuk(tiket, barang, "2026-08-09T00:00:00",
                                     "as-baru")
    assert doc["id"] == "as-baru"
    assert doc["NUP"] == "4"
    assert doc["purchase_price"] == "1500000"
    assert doc["category"] == "Peralatan dan Mesin"
    assert doc["condition"] == "Baik"
    assert doc["kode_satker"] == "527xxx"
    assert doc["perolehan_transfer"]["pihak_asal"] == "PUPR"
    assert doc["version"] == 1
