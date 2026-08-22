"""Dua celah audit persediaan (SEDIA-KPB, temuan audit 45 kode).

1. M94 (Batal Catat Tak Dikuasai) dulu lewat jalur /masuk GENERIK tanpa
   validasi apa pun terhadap sisa daftar Tak Dikuasai — bisa dicatat tanpa
   pernah ada K09, dengan qty & harga bebas, menaikkan stok+nilai sewenang;
   dan karena rekap_nonaktif membuang baris ber-sisa <= 0, over-pembatalan
   tak terlihat di layar mana pun. Kontras H03 yang sejak lama divalidasi
   `jumlah <= sisa`. Kini M94 dipagari paritas yang sama.

2. transaksi-massal mem-booking nomor LPB SEBELUM loop (harus — nomornya
   distempel ke tiap jurnal), sehingga saat SEMUA baris gagal, surat
   'dibooking' menggantung di buku agenda tanpa LPB selamanya. Kini surat
   itu dibatalkan beralasan; nomornya tetap hangus (by design).
"""
import asyncio

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import routes.persediaan as rps

USER = {"username": "gudang", "role": "admin", "kode_satker": ""}


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
    import routes.persuratan as rsu
    for mod in (rps, su, rsu):
        monkeypatch.setattr(mod, "db", fake, raising=False)
        if hasattr(mod, "log_audit"):
            monkeypatch.setattr(mod, "log_audit", _diam, raising=False)
    for nama in ("jadwalkan_sync", "jadwalkan_hapus"):
        if hasattr(rps, nama):
            monkeypatch.setattr(rps, nama, lambda *a, **k: None, raising=False)
    monkeypatch.setattr(su, "catat_mutasi_bmn", _diam, raising=False)
    return fake


async def _seed_barang(dbx, stok=0, batches=None):
    await dbx.persediaan.insert_one({
        "id": "psd-1", "kode_satker": "", "kode_barang": "1010301001000001",
        "nup": "1", "nama_barang": "Kertas HVS A4", "satuan": "Rim",
        "stok": stok, "batches": batches or [], "harga_satuan": 0,
        "version": 1})


def _masuk(jenis, jumlah, harga=10_000):
    return rps.TransaksiMasukIn(jenis=jenis, jumlah=jumlah,
                                harga_satuan=harga)


class TestPagarM94:
    def test_m94_tanpa_k09_ditolak(self, dbx):
        async def skenario():
            await _seed_barang(dbx)
            with pytest.raises(HTTPException) as e:
                await _unwrap(rps.transaksi_masuk)(
                    "psd-1", _masuk("batal_catat_tak_dikuasai", 1), user=USER)
            assert e.value.status_code == 400
            assert "sisa tercatat" in e.value.detail
            # Stok TIDAK bergeser dan tak ada jurnal sampah.
            item = await dbx.persediaan.find_one({"id": "psd-1"})
            assert int(item["stok"]) == 0
            assert await dbx.transaksi_persediaan.count_documents({}) == 0
        _jalan(skenario())

    def test_m94_dibatasi_sisa_dan_sisa_menyusut(self, dbx):
        async def skenario():
            await _seed_barang(dbx)
            # K09 tercatat 5 unit → sisa daftar Tak Dikuasai = 5.
            await dbx.transaksi_persediaan.insert_one({
                "persediaan_id": "psd-1", "jenis": "catat_tak_dikuasai",
                "jumlah": 5, "total": 50_000,
                "timestamp": "2026-01-01T00:00:00+00:00"})
            # Melebihi sisa → ditolak dengan angka sisanya.
            with pytest.raises(HTTPException) as e:
                await _unwrap(rps.transaksi_masuk)(
                    "psd-1", _masuk("batal_catat_tak_dikuasai", 6), user=USER)
            assert "(5)" in e.value.detail
            # Tepat sebesar sisa → sah; stok naik, jurnal M94 tercatat.
            r = await _unwrap(rps.transaksi_masuk)(
                "psd-1", _masuk("batal_catat_tak_dikuasai", 5), user=USER)
            assert r["transaksi"]["kode_sakti"] == "M94"
            assert r["stok"] == 5
            # Sisa kini 0 — pembatalan berikutnya ditolak (rekap
            # memperhitungkan M94 yang barusan tercatat).
            with pytest.raises(HTTPException) as e2:
                await _unwrap(rps.transaksi_masuk)(
                    "psd-1", _masuk("batal_catat_tak_dikuasai", 1), user=USER)
            assert e2.value.status_code == 400
        _jalan(skenario())

    def test_jenis_masuk_lain_tak_tersentuh_pagar(self, dbx):
        # Pembelian biasa tanpa jurnal apa pun harus tetap jalan — pagar
        # HANYA untuk M94.
        async def skenario():
            await _seed_barang(dbx)
            r = await _unwrap(rps.transaksi_masuk)(
                "psd-1", _masuk("pembelian", 3), user=USER)
            assert r["stok"] == 3
        _jalan(skenario())


class TestBookingLpbGagalTotal:
    def _payload_massal(self, items):
        return rps.TransaksiMassalIn(
            arah="masuk", jenis="pembelian", no_bukti="",
            jenis_dokumen="BAST", tgl_dokumen="2026-03-10",
            penyedia="PT X", booking_otomatis=True,
            items=items)

    @pytest.fixture()
    def booking_palsu(self, dbx, monkeypatch):
        import routes.persuratan as rsu

        # Tanda tangan DITULIS LENGKAP, bukan `**kwargs`: kalau yang asli
        # bertambah parameter, tiruan ini harus ikut gagal supaya
        # perbedaannya terlihat. `**kwargs` akan menelan perbedaan itu diam-
        # diam, dan uji ini berhenti menguji jalur yang sebenarnya.
        async def _booking(user, tgl_iso, perihal, tujuan="", keterangan="",
                           kode_satker="", kode_klasifikasi=""):
            await dbx.surat.insert_one({
                "id": "surat-1", "status": "dibooking",
                "nomor": "LPB-UJI-1", "riwayat": []})
            return "LPB-UJI-1", "surat-1"
        monkeypatch.setattr(rsu, "booking_nomor_lpb", _booking)

    def test_semua_baris_gagal_membatalkan_surat(self, dbx, booking_palsu):
        async def skenario():
            hasil = await _unwrap(rps.transaksi_massal)(
                self._payload_massal([rps.ItemMassalIn(
                    persediaan_id="tidak-ada", jumlah=1, harga_satuan=100)]),
                user=USER)
            assert hasil["sukses"] == 0
            surat = await dbx.surat.find_one({"id": "surat-1"})
            assert surat["status"] == "dibatalkan"
            assert "LPB tidak terbit" in surat["alasan_batal"]
            assert surat["riwayat"][-1]["status"] == "dibatalkan"
            # Tidak ada LPB yang lahir dari kegagalan total.
            assert hasil["lpb_id"] == ""
        _jalan(skenario())

    def test_sukses_sebagian_TIDAK_membatalkan_surat(self, dbx, booking_palsu):
        async def skenario():
            await _seed_barang(dbx)
            hasil = await _unwrap(rps.transaksi_massal)(
                self._payload_massal([
                    rps.ItemMassalIn(persediaan_id="psd-1", jumlah=2,
                                     harga_satuan=100),
                    rps.ItemMassalIn(persediaan_id="tidak-ada", jumlah=1,
                                     harga_satuan=100),
                ]), user=USER)
            assert hasil["sukses"] == 1 and hasil["gagal"] == 1
            surat = await dbx.surat.find_one({"id": "surat-1"})
            assert surat["status"] == "dibooking"
            assert hasil["lpb_id"] != ""
        _jalan(skenario())
