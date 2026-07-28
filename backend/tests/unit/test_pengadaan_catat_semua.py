"""Uji ENDPOINT rantai penerimaan barang (Pengadaan → Pencatatan → LPB).

Tiga janji yang hanya terbukti dengan menjalankan handler-nya:

1. **Barang persediaan TIDAK ikut jadi aset tetap.** Ini bug nyata sebelum
   penjaga golongan ditambahkan: menekan "Daftarkan ke Persediaan" lalu
   "Buat Draft Aset" atas BAST yang sama membuat satu baris kertas HVS
   tercatat DUA KALI, dan keduanya berjurnal ke Neraca.
2. **PPK dibekukan di dokumen**, bukan di-join saat baca — dan ikut turun ke
   aset yang lahir dari BAST itu.
3. **LPB aset terbit** dengan satu baris per NUP nyata.
"""
import asyncio

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.pengadaan as rp

USER = {"username": "operator", "role": "admin", "name": "Operator",
        "kode_satker": ""}


def _unwrap(fn):
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn


def _jalan(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


async def _diam(*a, **k):
    return None


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import routes.assets as ra
    import routes.persediaan as rps
    import shared_utils as su
    for mod in (rp, ra, rps, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)
        if hasattr(mod, "log_audit"):
            monkeypatch.setattr(mod, "log_audit", _diam, raising=False)
    # Efek samping yang tak diuji di sini (notifikasi realtime, indeks cari,
    # cache) dimatikan supaya kegagalannya tak menyamar jadi kegagalan alur.
    for nama in ("notify_asset_change", "broadcast_event", "invalidate_asset_caches"):
        for mod in (ra, rps, su):
            if hasattr(mod, nama):
                monkeypatch.setattr(mod, nama, _diam, raising=False)
    for mod in (ra, rps):
        for nama in ("jadwalkan_sync", "jadwalkan_hapus"):
            if hasattr(mod, nama):
                monkeypatch.setattr(mod, nama, lambda *a, **k: None, raising=False)
    monkeypatch.setattr(rp, "catat_mutasi_bmn", _diam, raising=False)
    monkeypatch.setattr(su, "catat_mutasi_bmn", _diam, raising=False)
    return fake


async def _seed(dbx, ppk=True):
    await dbx.inventory_activities.insert_one(
        {"id": "keg1", "nama_kegiatan": "Inventarisasi 2026", "kode_satker": "",
         "status": "berjalan"})
    if ppk:
        await dbx.pejabat.insert_one({
            "id": "pj-ppk", "nama": "Budi Santoso", "nip": "199001012015011001",
            "jabatan": "Pejabat Pembuat Komitmen", "peran": ["ppk"],
            "kode_satker": "", "berlaku_mulai": "2026-01-01",
            "status_kepegawaian": "pns"})
    await dbx.categories.insert_one(
        {"kode_aset": "3050102001", "label": "Peralatan Kantor"})


def _perolehan_baru():
    return rp.PerolehanIn(
        jenis="pembelian", pihak="PT Sumber Rejeki",
        nomor_kontrak="KTR-001/PPK/2026", nomor_bast="BAST-001/2026",
        tanggal_bast="2026-03-10",
        barang=[
            rp.BarangIn(uraian="Printer LaserJet", kode="3050102001",
                        jumlah=2, harga_satuan=2_500_000),
            rp.BarangIn(uraian="Kertas HVS A4", kode="1010301001",
                        jumlah=10, harga_satuan=55_000),
            rp.BarangIn(uraian="Barang belum berkode", kode="",
                        jumlah=1, harga_satuan=100_000),
        ])


def test_ppk_dibekukan_saat_perolehan_dicatat(dbx):
    async def skenario():
        await _seed(dbx)
        rec = await _unwrap(rp.buat_perolehan)(_perolehan_baru(), user=USER)
        assert rec["ppk_nama"] == "Budi Santoso"
        assert rec["ppk_nip"] == "199001012015011001"
        assert rec["ppk_pejabat_id"] == "pj-ppk"
        # Pejabat berganti SETELAH dokumen terbit → dokumen TIDAK ikut berubah.
        await dbx.pejabat.update_one({"id": "pj-ppk"},
                                     {"$set": {"nama": "Nama Baru"}})
        segar = await dbx.pengadaan.find_one({"id": rec["id"]})
        assert segar["ppk_nama"] == "Budi Santoso"
    _jalan(skenario())


def test_tanpa_pejabat_ppk_snapshot_kosong_bukan_galat(dbx):
    """Satker yang belum mengisi Referensi Pejabat tetap bisa mencatat BAST."""
    async def skenario():
        await _seed(dbx, ppk=False)
        rec = await _unwrap(rp.buat_perolehan)(_perolehan_baru(), user=USER)
        assert rec["ppk_nama"] == ""
        assert rec["ppk_pejabat_id"] == ""
    _jalan(skenario())


def test_catat_semua_memilah_dan_tidak_mencatat_ganda(dbx):
    """INTI: kertas HVS masuk persediaan SAJA, printer jadi aset SAJA."""
    async def skenario():
        await _seed(dbx)
        rec = await _unwrap(rp.buat_perolehan)(_perolehan_baru(), user=USER)
        hasil = await _unwrap(rp.catat_semua_barang)(
            rec["id"], rp.CatatSemuaIn(activity_id="keg1", booking_nomor=False),
            user=USER)

        # Printer jumlah 2 → dua aset ber-NUP 1 dan 2.
        assert hasil["aset_dibuat"] == 2
        aset = await dbx.assets.find({}).to_list(100)
        assert len(aset) == 2
        assert {a["asset_code"] for a in aset} == {"3050102001"}
        assert sorted(a["NUP"] for a in aset) == ["1", "2"]

        # Kertas HVS TIDAK BOLEH punya aset tetap.
        assert not [a for a in aset if a["asset_code"] == "1010301001"]
        # …dan memang masuk master persediaan.
        assert hasil["persediaan_masuk"] == 1
        psd = await dbx.persediaan.find({}).to_list(100)
        # Master persediaan menomori sendiri: kode 10 digit dilengkapi nomor
        # urut jadi 16 digit (`next_kode_penuh`) — yang dijaga di sini adalah
        # ASAL kodenya, bukan panjang akhirnya.
        assert len(psd) == 1
        assert psd[0]["kode_barang"].startswith("1010301001")

        # Baris tanpa kode dilaporkan, bukan ditelan diam-diam.
        assert hasil["tanpa_kode"] == 1
        assert hasil["baris_tanpa_kode"] == [3]
    _jalan(skenario())


def test_urutan_terbalik_pun_tak_mencatat_ganda(dbx):
    """Persediaan dulu, baru aset — jalur yang DULU melahirkan catatan ganda."""
    async def skenario():
        await _seed(dbx)
        rec = await _unwrap(rp.buat_perolehan)(_perolehan_baru(), user=USER)
        await _unwrap(rp.daftarkan_persediaan)(rec["id"], user=USER)
        await _unwrap(rp.buat_draft_aset_dari_perolehan)(
            rec["id"], rp.BuatDraftAsetIn(activity_id="keg1"), user=USER)
        aset = await dbx.assets.find({}).to_list(100)
        assert {a["asset_code"] for a in aset} == {"3050102001"}, \
            "kode golongan 1 tak boleh pernah menjadi aset tetap"
    _jalan(skenario())


def test_ppk_ikut_turun_ke_aset_yang_lahir_dari_bast(dbx):
    async def skenario():
        await _seed(dbx)
        rec = await _unwrap(rp.buat_perolehan)(_perolehan_baru(), user=USER)
        await _unwrap(rp.catat_semua_barang)(
            rec["id"], rp.CatatSemuaIn(activity_id="keg1", booking_nomor=False),
            user=USER)
        a = await dbx.assets.find_one({"asset_code": "3050102001"})
        assert a["perolehan"]["ppk_nama"] == "Budi Santoso"
        assert a["perolehan"]["nomor_bast"] == "BAST-001/2026"
    _jalan(skenario())


def test_lpb_aset_terbit_satu_baris_per_nup(dbx):
    async def skenario():
        await _seed(dbx)
        rec = await _unwrap(rp.buat_perolehan)(_perolehan_baru(), user=USER)
        hasil = await _unwrap(rp.catat_semua_barang)(
            rec["id"], rp.CatatSemuaIn(activity_id="keg1", booking_nomor=False),
            user=USER)
        assert hasil["lpb_id"]
        lpb = await dbx.lpb.find_one({"id": hasil["lpb_id"]})
        assert lpb["kategori"] == "aset"
        assert lpb["jumlah_barang"] == 2
        assert sorted(b["nup"] for b in lpb["items"]) == ["1", "2"]
        assert all(b["jumlah"] == 1 for b in lpb["items"])
        assert lpb["total_nilai"] == 5_000_000
        # PPK ikut ke LPB — inilah yang dicari pemeriksa saat menelusurinya.
        assert lpb["ppk_nama"] == "Budi Santoso"
        # Kertas HVS bukan urusan LPB aset.
        assert not [b for b in lpb["items"] if b["kode_barang"] == "1010301001"]
    _jalan(skenario())


def test_catat_semua_idempoten_pada_panggilan_kedua(dbx):
    """Menekan tombolnya dua kali tak menggandakan apa pun."""
    async def skenario():
        await _seed(dbx)
        rec = await _unwrap(rp.buat_perolehan)(_perolehan_baru(), user=USER)
        args = (rec["id"], rp.CatatSemuaIn(activity_id="keg1",
                                           booking_nomor=False))
        await _unwrap(rp.catat_semua_barang)(*args, user=USER)
        kedua = await _unwrap(rp.catat_semua_barang)(*args, user=USER)
        assert kedua["aset_dibuat"] == 0
        assert kedua["persediaan_masuk"] == 0
        assert await dbx.assets.count_documents({}) == 2
        assert await dbx.persediaan.count_documents({}) == 1
        # Tak ada LPB kedua untuk nol aset baru.
        assert kedua["lpb_id"] == ""
        assert await dbx.lpb.count_documents({"kategori": "aset"}) == 1
    _jalan(skenario())


def test_tetapkan_ppk_menyusul_dan_ikut_memperbarui_aset(dbx):
    """Register lama tanpa PPK bisa dilengkapi tanpa membuat ulang dokumen."""
    async def skenario():
        await _seed(dbx, ppk=False)
        rec = await _unwrap(rp.buat_perolehan)(_perolehan_baru(), user=USER)
        await _unwrap(rp.catat_semua_barang)(
            rec["id"], rp.CatatSemuaIn(activity_id="keg1", booking_nomor=False),
            user=USER)
        assert rec["ppk_nama"] == ""

        await dbx.pejabat.insert_one({
            "id": "pj-baru", "nama": "Siti Aminah", "nip": "198505052010012002",
            "jabatan": "PPK", "peran": ["ppk"], "kode_satker": "",
            "berlaku_mulai": "2026-01-01", "status_kepegawaian": "pns"})
        await _unwrap(rp.tetapkan_ppk)(
            rec["id"], rp.TetapkanPpkIn(ppk_pejabat_id="auto"), user=USER)

        segar = await dbx.pengadaan.find_one({"id": rec["id"]})
        assert segar["ppk_nama"] == "Siti Aminah"
        # Proyeksi ulang: aset yang sudah tercatat ikut diperbaiki.
        a = await dbx.assets.find_one({"asset_code": "3050102001"})
        assert a["perolehan"]["ppk_nama"] == "Siti Aminah"
    _jalan(skenario())


def test_bast_persediaan_saja_tak_menuntut_kegiatan(dbx):
    """Satu rim kertas tak butuh kegiatan inventarisasi.

    Kegiatan hanya bermakna untuk aset ber-NUP; menuntutnya pada BAST yang
    seluruhnya persediaan adalah syarat kosong yang menghalangi pencatatan.
    """
    async def skenario():
        await _seed(dbx)
        rec = await _unwrap(rp.buat_perolehan)(rp.PerolehanIn(
            jenis="pembelian", pihak="PT Sumber Rejeki",
            nomor_bast="BAST-002/2026", tanggal_bast="2026-03-11",
            barang=[rp.BarangIn(uraian="Kertas HVS A4", kode="1010301001",
                                jumlah=10, harga_satuan=55_000)]), user=USER)
        hasil = await _unwrap(rp.catat_semua_barang)(
            rec["id"], rp.CatatSemuaIn(activity_id="", booking_nomor=False),
            user=USER)
        assert hasil["persediaan_masuk"] == 1
        assert hasil["aset_dibuat"] == 0
        # Tak ada aset → tak ada LPB aset.
        assert hasil["lpb_id"] == ""
    _jalan(skenario())


def test_bast_ber_aset_tetap_menuntut_kegiatan(dbx):
    """Sebaliknya: begitu ada barang golongan aset, kegiatan wajib —
    dan penolakannya menyebut berapa baris yang menuntutnya."""
    from fastapi import HTTPException

    async def skenario():
        await _seed(dbx)
        rec = await _unwrap(rp.buat_perolehan)(_perolehan_baru(), user=USER)
        with pytest.raises(HTTPException) as e:
            await _unwrap(rp.catat_semua_barang)(
                rec["id"], rp.CatatSemuaIn(activity_id="", booking_nomor=False),
                user=USER)
        assert e.value.status_code == 400
        assert "kegiatan inventarisasi" in str(e.value.detail).lower()
        # Penolakan terjadi SEBELUM apa pun tercatat.
        assert await dbx.assets.count_documents({}) == 0
        assert await dbx.persediaan.count_documents({}) == 0
    _jalan(skenario())


def test_ppk_id_yang_tak_ada_ditolak_404(dbx):
    from fastapi import HTTPException

    async def skenario():
        await _seed(dbx)
        rec = await _unwrap(rp.buat_perolehan)(_perolehan_baru(), user=USER)
        with pytest.raises(HTTPException) as e:
            await _unwrap(rp.tetapkan_ppk)(
                rec["id"], rp.TetapkanPpkIn(ppk_pejabat_id="tidak-ada"),
                user=USER)
        assert e.value.status_code == 404
    _jalan(skenario())
