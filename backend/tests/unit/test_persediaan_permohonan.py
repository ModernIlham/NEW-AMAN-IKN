"""Alur permohonan → persetujuan KPB transaksi persediaan — SEDIA-KPB.

Keputusan pemilik (2026-08-09): SEMUA transaksi persediaan lewat permohonan;
eksekusi hanya saat disetujui admin yang BUKAN pengajunya; terbit Surat
Persetujuan ber-nomor dengan ttd KPB. Uji di bawah menegakkan empat sifat
yang masing-masing pernah jadi kelas kegagalan di preseden repo:

  1. PEMISAHAN PERAN ditegakkan kode — pengaju tak bisa menyetujui dirinya.
  2. ANTI-GANDA — dua admin menekan Setujui bersamaan: satu jalan, satu 409;
     stok TIDAK pernah naik dua kali.
  3. GAGAL ≠ HILANG — eksekusi gagal mengembalikan status ke diusulkan
     dengan galat tercatat, bukan menelan permohonannya.
  4. GERBANG hormat pada asal panggilan — setelan aktif menolak HTTP
     langsung, tapi eksekusi internal (request=None) tetap jalan; setelan
     mati = perilaku lama utuh (kompatibilitas sampai UI siap).
"""
import asyncio

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import routes.persediaan as rps
import routes.persediaan_permohonan as rpp

PENGAJU = {"username": "op1", "role": "operator", "kode_satker": ""}
PENYETUJU = {"username": "adm1", "role": "admin", "kode_satker": ""}


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
    for mod in (rps, rpp, su, rsu):
        monkeypatch.setattr(mod, "db", fake, raising=False)
        if hasattr(mod, "log_audit"):
            monkeypatch.setattr(mod, "log_audit", _diam, raising=False)
    for nama in ("jadwalkan_sync", "jadwalkan_hapus"):
        if hasattr(rps, nama):
            monkeypatch.setattr(rps, nama, lambda *a, **k: None, raising=False)
    monkeypatch.setattr(su, "catat_mutasi_bmn", _diam, raising=False)

    # Booking nomor dipalsukan (deret asli butuh setelan penomoran lengkap).
    async def _booking(user, tgl, perihal, tujuan="", keterangan="",
                       kode_satker="", jenis_naskah="Laporan", referensi=""):
        return "SP-001/UJI/2026", "surat-sp-1"
    monkeypatch.setattr(rsu, "booking_nomor_otomatis", _booking)
    return fake


async def _seed_barang(dbx):
    await dbx.persediaan.insert_one({
        "id": "psd-1", "kode_satker": "", "kode_barang": "1010301001000001",
        "nup": "1", "nama_barang": "Kertas HVS A4", "satuan": "Rim",
        "stok": 0, "batches": [], "harga_satuan": 0, "version": 1})


def _ajukan_masuk(jumlah=10):
    return rpp.PermohonanIn(
        jalur="masuk", item_id="psd-1",
        payload={"jenis": "pembelian", "jumlah": jumlah,
                 "harga_satuan": 50_000},
        catatan="pembelian ATK triwulan III")


class TestAjukan:
    def test_ajukan_tersimpan_tanpa_menyentuh_stok(self, dbx):
        async def skenario():
            await _seed_barang(dbx)
            r = await _unwrap(rpp.ajukan_permohonan)(_ajukan_masuk(),
                                                     user=PENGAJU)
            p = r["permohonan"]
            assert p["status"] == "diusulkan"
            assert p["diajukan_oleh"] == "op1"
            assert "Kertas HVS A4" in p["ringkasan"]
            item = await dbx.persediaan.find_one({"id": "psd-1"})
            assert int(item["stok"]) == 0
            assert await dbx.transaksi_persediaan.count_documents({}) == 0
        _jalan(skenario())

    def test_jalur_asing_dan_payload_kosong_ditolak(self, dbx):
        async def skenario():
            with pytest.raises(HTTPException):
                await _unwrap(rpp.ajukan_permohonan)(
                    rpp.PermohonanIn(jalur="edit_jurnal", item_id="x",
                                     payload={"a": 1}), user=PENGAJU)
            with pytest.raises(HTTPException):
                await _unwrap(rpp.ajukan_permohonan)(
                    rpp.PermohonanIn(jalur="masuk", item_id="psd-1",
                                     payload={}), user=PENGAJU)
        _jalan(skenario())


class TestSetujui:
    async def _ajukan(self, dbx):
        await _seed_barang(dbx)
        r = await _unwrap(rpp.ajukan_permohonan)(_ajukan_masuk(), user=PENGAJU)
        return r["permohonan"]["id"]

    def test_setujui_mengeksekusi_dan_menomori(self, dbx):
        async def skenario():
            pid = await self._ajukan(dbx)
            r = await _unwrap(rpp.setujui_permohonan)(pid, user=PENYETUJU)
            assert r["nomor"] == "SP-001/UJI/2026"
            item = await dbx.persediaan.find_one({"id": "psd-1"})
            assert int(item["stok"]) == 10
            jurnal = await dbx.transaksi_persediaan.find_one({})
            assert jurnal["kode_sakti"] == "M02"
            p = await dbx.persediaan_permohonan.find_one({"id": pid})
            assert p["status"] == "disetujui"
            assert p["disetujui_oleh"] == "adm1"
        _jalan(skenario())

    def test_pengaju_tak_boleh_menyetujui_diri_sendiri(self, dbx):
        async def skenario():
            pid = await self._ajukan(dbx)
            admin_pengaju = {**PENGAJU, "role": "admin"}
            with pytest.raises(HTTPException) as e:
                await _unwrap(rpp.setujui_permohonan)(pid, user=admin_pengaju)
            assert e.value.status_code == 403
            item = await dbx.persediaan.find_one({"id": "psd-1"})
            assert int(item["stok"]) == 0
        _jalan(skenario())

    def test_setujui_kedua_kali_409_dan_stok_tidak_ganda(self, dbx):
        async def skenario():
            pid = await self._ajukan(dbx)
            await _unwrap(rpp.setujui_permohonan)(pid, user=PENYETUJU)
            with pytest.raises(HTTPException) as e:
                await _unwrap(rpp.setujui_permohonan)(pid, user=PENYETUJU)
            assert e.value.status_code == 409
            item = await dbx.persediaan.find_one({"id": "psd-1"})
            assert int(item["stok"]) == 10   # bukan 20
        _jalan(skenario())

    def test_eksekusi_gagal_kembali_diusulkan_bergalat(self, dbx):
        async def skenario():
            await _seed_barang(dbx)
            r = await _unwrap(rpp.ajukan_permohonan)(
                rpp.PermohonanIn(jalur="keluar", item_id="psd-1",
                                 payload={"jenis": "habis_pakai",
                                          "jumlah": 99}),
                user=PENGAJU)
            pid = r["permohonan"]["id"]
            with pytest.raises(HTTPException) as e:
                await _unwrap(rpp.setujui_permohonan)(pid, user=PENYETUJU)
            assert "Eksekusi gagal" in str(e.value.detail)
            p = await dbx.persediaan_permohonan.find_one({"id": pid})
            assert p["status"] == "diusulkan"     # tidak hilang
            assert p["galat_terakhir"]
        _jalan(skenario())


class TestTolakDanBatal:
    async def _ajukan(self, dbx):
        await _seed_barang(dbx)
        r = await _unwrap(rpp.ajukan_permohonan)(_ajukan_masuk(), user=PENGAJU)
        return r["permohonan"]["id"]

    def test_tolak_beralasan_oleh_admin_lain(self, dbx):
        async def skenario():
            pid = await self._ajukan(dbx)
            await _unwrap(rpp.tolak_permohonan)(
                pid, rpp.TolakIn(alasan="bukti kontrak belum ada"),
                user=PENYETUJU)
            p = await dbx.persediaan_permohonan.find_one({"id": pid})
            assert p["status"] == "ditolak"
            assert p["alasan_tolak"] == "bukti kontrak belum ada"
        _jalan(skenario())

    def test_batal_hanya_pengaju(self, dbx):
        async def skenario():
            pid = await self._ajukan(dbx)
            with pytest.raises(HTTPException) as e:
                await _unwrap(rpp.batal_permohonan)(pid, user=PENYETUJU)
            assert e.value.status_code == 403
            await _unwrap(rpp.batal_permohonan)(pid, user=PENGAJU)
            p = await dbx.persediaan_permohonan.find_one({"id": pid})
            assert p["status"] == "dibatalkan"
        _jalan(skenario())


class _ReqPalsu:
    headers: dict = {}
    method = "POST"


class TestGerbang:
    def test_setelan_aktif_menolak_http_langsung(self, dbx):
        async def skenario():
            await _seed_barang(dbx)
            await dbx.report_settings.insert_one(
                {"type": "global", "persediaan_wajib_persetujuan": True})
            with pytest.raises(HTTPException) as e:
                await _unwrap(rps.transaksi_masuk)(
                    "psd-1", rps.TransaksiMasukIn(
                        jenis="pembelian", jumlah=1, harga_satuan=100),
                    request=_ReqPalsu(), user=PENGAJU)
            assert e.value.status_code == 403
            assert "persetujuan" in str(e.value.detail).casefold()
        _jalan(skenario())

    def test_setelan_aktif_eksekusi_internal_tetap_jalan(self, dbx):
        # Jalur persetujuan memanggil dengan request=None — HARUS lolos,
        # kalau tidak, menyalakan gerbang justru mematikan alurnya sendiri.
        async def skenario():
            await _seed_barang(dbx)
            await dbx.report_settings.insert_one(
                {"type": "global", "persediaan_wajib_persetujuan": True})
            r = await _unwrap(rpp.ajukan_permohonan)(_ajukan_masuk(3),
                                                     user=PENGAJU)
            hasil = await _unwrap(rpp.setujui_permohonan)(
                r["permohonan"]["id"], user=PENYETUJU)
            assert hasil["hasil"]["stok"] == 3
        _jalan(skenario())

    def test_setelan_mati_perilaku_lama_utuh(self, dbx):
        async def skenario():
            await _seed_barang(dbx)
            r = await _unwrap(rps.transaksi_masuk)(
                "psd-1", rps.TransaksiMasukIn(
                    jenis="pembelian", jumlah=2, harga_satuan=100),
                request=_ReqPalsu(), user=PENGAJU)
            assert r["stok"] == 2
        _jalan(skenario())


class TestDokumenPersetujuan:
    def test_pdf_terbit_hanya_untuk_yang_disetujui(self, dbx):
        pdfium = pytest.importorskip("pypdfium2")

        async def skenario():
            await _seed_barang(dbx)
            r = await _unwrap(rpp.ajukan_permohonan)(_ajukan_masuk(),
                                                     user=PENGAJU)
            pid = r["permohonan"]["id"]
            with pytest.raises(HTTPException) as e:
                await rpp.bangun_persetujuan_pdf(pid, PENYETUJU)
            assert e.value.status_code == 409
            await _unwrap(rpp.setujui_permohonan)(pid, user=PENYETUJU)
            return await rpp.bangun_persetujuan_pdf(pid, PENYETUJU), pid

        data, pid = _jalan(skenario())
        assert data[:5] == b"%PDF-"
        teks = pdfium.PdfDocument(__import__("io").BytesIO(data))[0] \
            .get_textpage().get_text_range()
        assert "SURAT PERSETUJUAN" in teks
        assert "SP-001/UJI/2026" in teks
        assert "Kertas HVS A4" in teks
        assert "op1" in teks and "adm1" in teks


class TestPengaturanGerbang:
    def test_saklar_menulis_dan_terbaca_dua_arah(self, dbx):
        async def skenario():
            r = await _unwrap(rpp.ubah_pengaturan_permohonan)(
                rpp.PengaturanPermohonanIn(aktif=True), user=PENYETUJU)
            assert r["aktif"] is True
            baca = await _unwrap(rpp.baca_pengaturan_permohonan)(_user=PENGAJU)
            assert baca["aktif"] is True
            # Dialog transaksi membaca mode dari referensi yang SUDAH dimuat —
            # field wajib_persetujuan harus ikut di /jenis-transaksi.
            ref = await _unwrap(rps.list_jenis_transaksi)(_user=PENGAJU)
            assert ref["wajib_persetujuan"] is True
            await _unwrap(rpp.ubah_pengaturan_permohonan)(
                rpp.PengaturanPermohonanIn(aktif=False), user=PENYETUJU)
            ref2 = await _unwrap(rps.list_jenis_transaksi)(_user=PENGAJU)
            assert ref2["wajib_persetujuan"] is False
        _jalan(skenario())
