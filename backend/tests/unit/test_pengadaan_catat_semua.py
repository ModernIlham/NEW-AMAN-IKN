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


def test_ppk_diresolusi_pada_tanggal_bast_bukan_hari_ini(dbx):
    """PPK yang dipakai adalah yang BERLAKU saat BAST ditandatangani.

    Register perolehan lazim diisi berbulan setelah barang datang. Kalau
    resolusinya memakai tanggal HARI INI, dokumen akan menyebut pejabat yang
    belum menjabat waktu itu — atau tak menyebut siapa pun karena PPK-nya
    sudah purna. Uji ini memakai dua pejabat dengan masa berlaku berbeda
    supaya jawabannya berbeda antara "tanggal BAST" dan "hari ini"; tanpa itu
    uji apa pun akan lulus untuk kedua perilaku.
    """
    async def skenario():
        await _seed(dbx, ppk=False)
        await dbx.pejabat.insert_many([
            # Menjabat SAAT BAST (Maret 2026), berakhir sebelum hari ini.
            # NB: field-nya `berlaku_selesai` (lihat pejabat_utils._berlaku_pada).
            # Salah nama = rentangnya terbuka = uji ini lulus untuk KEDUA
            # perilaku, alias tak menjaga apa pun.
            {"id": "pj-lama", "nama": "PPK Masa BAST", "nip": "1",
             "jabatan": "PPK", "peran": ["ppk"], "kode_satker": "",
             "berlaku_mulai": "2026-01-01", "berlaku_selesai": "2026-04-30"},
            # Baru menjabat SETELAH BAST.
            {"id": "pj-baru", "nama": "PPK Sekarang", "nip": "2",
             "jabatan": "PPK", "peran": ["ppk"], "kode_satker": "",
             "berlaku_mulai": "2026-05-01"},
        ])
        rec = await _unwrap(rp.buat_perolehan)(_perolehan_baru(), user=USER)
        assert rec["ppk_nama"] == "PPK Masa BAST", (
            "dokumen menyebut PPK yang menjabat hari ini, bukan yang "
            "menandatangani komitmennya")
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


# ═══════════════════════════════════════════════════════════════════════════
# TEMUAN AUDIT ADVERSARIAL GELOMBANG-2 (5 TINGGI)
# ═══════════════════════════════════════════════════════════════════════════

def test_ppk_pejabat_satker_lain_tak_pernah_dipakai(dbx):
    """Klaim "dokumen satker ini hanya menyebut pejabatnya sendiri" DIUJI.

    Dua mutasi dulu LOLOS seluruh suite: membuang `kode_satker` dari
    `resolve_pejabat_peran`, dan membuang `_q_pejabat_satker` dari lookup id
    eksplisit. Fixture lamanya memakai `kode_satker=""` (super-admin) dan tak
    pernah menaruh pejabat milik satker lain — jadi penjaga apa pun lulus.
    """
    async def skenario():
        await dbx.inventory_activities.insert_one(
            {"id": "keg1", "nama_kegiatan": "Inv", "kode_satker": "111111"})
        await dbx.pejabat.insert_one({
            "id": "pj-asing", "nama": "PPK Satker Lain",
            "nip": "199901012020011001", "jabatan": "PPK", "peran": ["ppk"],
            "kode_satker": "999999", "berlaku_mulai": "2026-01-01"})
        user_a = {"username": "op-a", "role": "admin", "name": "Op",
                  "kode_satker": "111111"}
        rec = await _unwrap(rp.buat_perolehan)(_perolehan_baru(), user=user_a)
        assert rec["ppk_nama"] == "", (
            "nama & NIP pejabat satker lain tercetak di BAST satker ini")
    _jalan(skenario())


def test_tetapkan_ppk_id_satker_lain_ditolak(dbx):
    """Jalur id EKSPLISIT juga ber-scope — bukan hanya resolusi otomatis."""
    from fastapi import HTTPException

    async def skenario():
        await dbx.inventory_activities.insert_one(
            {"id": "keg1", "nama_kegiatan": "Inv", "kode_satker": "111111"})
        await dbx.pejabat.insert_one({
            "id": "pj-asing", "nama": "PPK Satker Lain", "nip": "1",
            "jabatan": "PPK", "peran": ["ppk"], "kode_satker": "999999",
            "berlaku_mulai": "2026-01-01"})
        user_a = {"username": "op-a", "role": "admin", "name": "Op",
                  "kode_satker": "111111"}
        rec = await _unwrap(rp.buat_perolehan)(_perolehan_baru(), user=user_a)
        with pytest.raises(HTTPException) as e:
            await _unwrap(rp.tetapkan_ppk)(
                rec["id"], rp.TetapkanPpkIn(ppk_pejabat_id="pj-asing"),
                user=user_a)
        assert e.value.status_code == 404
    _jalan(skenario())


def test_hasil_catat_semua_bisa_diserialkan_json(dbx):
    """Nilai balik route WAJIB lolos `jsonable_encoder`.

    `buat_aset_draft` mengembalikan dict YANG SAMA yang dioper ke
    `insert_one()`, dan Motor menyisipkan `_id: ObjectId` in-place. Menyalin
    dokumen itu ke respons membuat FastAPI melempar 500 SETELAH aset, jurnal,
    dan audit tertulis — operator hanya melihat "gagal" padahal datanya ada.
    Uji unit biasa tak menangkapnya karena melewati lapisan serialisasi.
    """
    from fastapi.encoders import jsonable_encoder

    async def skenario():
        await _seed(dbx)
        rec = await _unwrap(rp.buat_perolehan)(_perolehan_baru(), user=USER)
        hasil = await _unwrap(rp.catat_semua_barang)(
            rec["id"], rp.CatatSemuaIn(activity_id="keg1", booking_nomor=False),
            user=USER)
        jsonable_encoder(hasil)          # meledak bila ada ObjectId tersisa
        draft = await _unwrap(rp.buat_draft_aset_dari_perolehan)(
            rec["id"], rp.BuatDraftAsetIn(activity_id="keg1"), user=USER)
        jsonable_encoder(draft)

        # `jsonable_encoder` saja TIDAK CUKUP sebagai penjaga: mongomock tak
        # menyisipkan `_id` ke dict yang dioper seperti Motor sungguhan, jadi
        # kebocorannya tak akan pernah muncul di sini. Yang dijaga adalah
        # bentuk DAFTAR PUTIH-nya — sifat yang sama di kedua driver, dan yang
        # justru menjadi aturannya: jangan salin dokumen aset mentah.
        BOLEH = {"id", "asset_code", "NUP", "asset_name",
                 "harga_satuan", "jumlah_bast"}
        for a in draft.get("aset_dibuat") or []:
            asing = set(a) - BOLEH
            assert not asing, (
                f"dokumen aset mentah ikut ke respons: {sorted(asing)} — "
                "Motor menyisipkan _id in-place dan FastAPI akan 500")
    _jalan(skenario())


def test_bast_yang_asetnya_sudah_tercatat_tak_jadi_jalan_buntu(dbx):
    """BAST setengah-jalan: aset sudah dicatat, persediaan belum.

    Dulu `pilah_barang_perolehan` tetap menghitung baris yang SUDAH jadi aset,
    sehingga gerbang `activity_id` menuntut kegiatan untuk pekerjaan yang
    sudah selesai — sementara layar tak merender dropdown-nya. Kertasnya tak
    akan pernah bisa masuk stok lewat layar mana pun.
    """
    async def skenario():
        await _seed(dbx)
        rec = await _unwrap(rp.buat_perolehan)(_perolehan_baru(), user=USER)
        # Langkah 1: hanya sisi ASET yang dicatat (jalur lama).
        await _unwrap(rp.buat_draft_aset_dari_perolehan)(
            rec["id"], rp.BuatDraftAsetIn(activity_id="keg1"), user=USER)
        # Langkah 2: "Catat Semua" TANPA activity_id — persis seperti yang
        # dikirim layar, karena tak ada lagi baris aset yang belum tertaut.
        hasil = await _unwrap(rp.catat_semua_barang)(
            rec["id"], rp.CatatSemuaIn(activity_id="", booking_nomor=False),
            user=USER)
        assert hasil["persediaan_masuk"] == 1, "kertas macet permanen"
    _jalan(skenario())


def test_stok_tak_masuk_kartu_barang_yang_salah(dbx):
    """Dua barang berbeda pada kodefikasi 10-digit yang SAMA.

    Enam digit terakhir kode 16-digit justru yang membedakan keduanya.
    Mencocokkan per-awalan saja lalu mengambil nomor urut terkecil akan
    membuang stok & layer FIFO ke kartu barang yang salah — lebih merusak
    daripada kartu yang pecah.
    """
    async def skenario():
        await _seed(dbx)
        await dbx.persediaan.insert_many([
            {"id": "psd-a4", "kode_satker": "", "kode_barang": "1010301001000001",
             "nup": "1", "nama_barang": "Kertas HVS A4", "satuan": "Rim",
             "stok": 0, "batches": [], "harga_satuan": 0},
            {"id": "psd-f4", "kode_satker": "", "kode_barang": "1010301001000002",
             "nup": "2", "nama_barang": "Kertas HVS F4", "satuan": "Rim",
             "stok": 0, "batches": [], "harga_satuan": 0},
        ])
        rec = await _unwrap(rp.buat_perolehan)(rp.PerolehanIn(
            jenis="pembelian", pihak="PT X", nomor_bast="BAST-9/2026",
            tanggal_bast="2026-03-12",
            barang=[rp.BarangIn(uraian="Kertas HVS F4", kode="1010301001",
                                jumlah=5, harga_satuan=60_000)]), user=USER)
        await _unwrap(rp.daftarkan_persediaan)(rec["id"], user=USER)

        a4 = await dbx.persediaan.find_one({"id": "psd-a4"})
        f4 = await dbx.persediaan.find_one({"id": "psd-f4"})
        assert a4["stok"] == 0, "stok masuk ke kartu barang yang SALAH"
        assert f4["stok"] == 5
    _jalan(skenario())


# ── Pintu MANUAL ke pencatatan ganda ───────────────────────────────────────

def test_baris_yang_sudah_di_kartu_stok_tak_bisa_ditautkan_ke_aset(dbx):
    """Tombol "Tautkan" adalah pintu KEDUA ke baris `barang[]` yang sama.

    Jalur otomatis sudah dijaga penjaga golongan, tetapi `tautkan_barang`
    tidak — dan ia menulis `asset_id` ke baris yang sudah memegang
    `psd_item_id`. Satu rim kertas HVS lalu berdiri di kartu stok DAN sebagai
    BMN ber-NUP sekaligus, keduanya berjurnal ke Neraca. Penjaga otomatis
    yang bisa dilangkahi lewat tombol di sebelahnya bukan penjaga.
    """
    async def skenario():
        await _seed(dbx)
        rec = await _unwrap(rp.buat_perolehan)(_perolehan_baru(), user=USER)
        await _unwrap(rp.daftarkan_persediaan)(rec["id"], user=USER)
        segar = await dbx.pengadaan.find_one({"id": rec["id"]})
        assert segar["barang"][1].get("psd_item_id"), "prasyarat: baris 1 di kartu stok"

        await dbx.assets.insert_one({
            "id": "aset-x", "asset_code": "3050102001", "NUP": "9",
            "asset_name": "Printer", "kode_satker": "", "activity_id": "keg1"})
        with pytest.raises(Exception) as ex:
            await _unwrap(rp.tautkan_barang)(
                rec["id"], rp.TautkanIn(index=1, asset_id="aset-x"), _user=USER)
        assert getattr(ex.value, "status_code", None) == 400
        assert "persediaan" in str(getattr(ex.value, "detail", "")).lower()

        segar = await dbx.pengadaan.find_one({"id": rec["id"]})
        assert not segar["barang"][1].get("asset_id"), "tautan tetap tertulis"
    _jalan(skenario())


def test_kode_golongan_satu_tak_bisa_ditautkan_ke_aset(dbx):
    """Barang golongan 1 = persediaan menurut kodefikasi BMN.

    Menautkannya ke BMN ber-NUP berarti mencatat barang habis pakai sebagai
    aset tetap — salah kelas, salah neraca, salah penyusutan. Ditolak SEBELUM
    ia pernah masuk kartu stok, bukan hanya sesudahnya.
    """
    async def skenario():
        await _seed(dbx)
        rec = await _unwrap(rp.buat_perolehan)(_perolehan_baru(), user=USER)
        await dbx.assets.insert_one({
            "id": "aset-y", "asset_code": "3050102001", "NUP": "8",
            "asset_name": "Printer", "kode_satker": "", "activity_id": "keg1"})
        with pytest.raises(Exception) as ex:
            await _unwrap(rp.tautkan_barang)(
                rec["id"], rp.TautkanIn(index=1, asset_id="aset-y"), _user=USER)
        assert getattr(ex.value, "status_code", None) == 400
        assert "golongan 1" in str(getattr(ex.value, "detail", ""))
    _jalan(skenario())


def test_baris_aset_tetap_boleh_ditautkan_seperti_biasa(dbx):
    """Penjaganya tak boleh membunuh alur yang benar.

    Tanpa uji ini, `tautkan_barang` yang menolak SEGALANYA akan lulus kedua
    uji di atas — dan fitur penautan manual mati diam-diam.
    """
    async def skenario():
        await _seed(dbx)
        rec = await _unwrap(rp.buat_perolehan)(_perolehan_baru(), user=USER)
        await dbx.assets.insert_one({
            "id": "aset-z", "asset_code": "3050102001", "NUP": "7",
            "asset_name": "Printer LaserJet", "kode_satker": "",
            "activity_id": "keg1"})
        hasil = await _unwrap(rp.tautkan_barang)(
            rec["id"], rp.TautkanIn(index=0, asset_id="aset-z"), _user=USER)
        assert hasil["barang"][0]["asset_id"] == "aset-z"
        assert hasil["barang"][0]["NUP"] == "7"
    _jalan(skenario())


def test_melepas_tautan_tetap_boleh_pada_baris_persediaan(dbx):
    """Data lama yang telanjur salah harus bisa DIBETULKAN.

    Penjaga yang juga menutup jalan keluar akan mengunci kesalahan yang
    sudah terlanjur tersimpan menjadi permanen.
    """
    async def skenario():
        await _seed(dbx)
        rec = await _unwrap(rp.buat_perolehan)(_perolehan_baru(), user=USER)
        # Keadaan warisan: baris persediaan yang TELANJUR bertaut ke aset.
        await dbx.pengadaan.update_one(
            {"id": rec["id"]},
            {"$set": {"barang.1.asset_id": "aset-lama",
                      "barang.1.psd_item_id": "psd-lama"}})
        hasil = await _unwrap(rp.tautkan_barang)(
            rec["id"], rp.TautkanIn(index=1, asset_id=""), _user=USER)
        assert hasil["barang"][1]["asset_id"] == ""
    _jalan(skenario())


class TestPeringatanNupSampaiKeEndpoint:
    """Peringatan NUP harus benar-benar SAMPAI ke pemanggil.

    Helper murninya sudah diuji tersendiri, tetapi peringatan yang dihitung
    dengan benar lalu tak diteruskan ke respons TIDAK menghasilkan galat apa
    pun — layarnya sekadar tak menampilkannya, persis seperti keadaan sebelum
    fitur ini ada. Justru itu yang harus dibuktikan di sini.
    """

    def _perolehan_besar(self):
        return rp.PerolehanIn(
            jenis="pembelian", pihak="PT Sumber Rejeki",
            nomor_kontrak="KTR-002/PPK/2026", nomor_bast="BAST-002/2026",
            tanggal_bast="2026-03-10",
            barang=[
                # 100 unit: DI ATAS batas pecah — hanya 1 NUP yang terbentuk.
                rp.BarangIn(uraian="Kursi Rapat", kode="3050102001",
                            jumlah=100, harga_satuan=750_000),
            ])

    def test_catat_semua_meneruskan_peringatannya(self, dbx):
        async def skenario():
            await _seed(dbx)
            rec = await _unwrap(rp.buat_perolehan)(self._perolehan_besar(),
                                                   user=USER)
            hasil = await _unwrap(rp.catat_semua_barang)(
                rec["id"],
                rp.CatatSemuaIn(activity_id="keg1", booking_nomor=False),
                user=USER)
            w = hasil.get("peringatan_nup")
            assert w, hasil.keys()
            assert w[0]["sebab"] == "melebihi_batas"
            assert "100 unit" in w[0]["pesan"]
        _jalan(skenario())

    def test_buat_draft_aset_juga_meneruskannya(self, dbx):
        async def skenario():
            await _seed(dbx)
            rec = await _unwrap(rp.buat_perolehan)(self._perolehan_besar(),
                                                   user=USER)
            hasil = await _unwrap(rp.buat_draft_aset_dari_perolehan)(
                rec["id"], rp.BuatDraftAsetIn(activity_id="keg1"), user=USER)
            assert hasil.get("peringatan_nup"), hasil.keys()
        _jalan(skenario())

    def test_jumlah_yang_PAS_tak_memunculkan_peringatan(self, dbx):
        """Peringatan yang muncul untuk keadaan normal akan dilatih diabaikan,
        dan yang sungguhan ikut terlewat."""
        async def skenario():
            await _seed(dbx)
            rec = await _unwrap(rp.buat_perolehan)(_perolehan_baru(), user=USER)
            hasil = await _unwrap(rp.catat_semua_barang)(
                rec["id"],
                rp.CatatSemuaIn(activity_id="keg1", booking_nomor=False),
                user=USER)
            assert hasil.get("peringatan_nup") == []
        _jalan(skenario())


class TestPeleburanKeAsetYangSudahAda:
    """Endpoint peleburan: nilai aset BERTAMBAH, kuantitasnya TIDAK.

    Yang membedakannya dari "Tautkan": menautkan hanya menyalin kode/NUP/nama
    ke barisnya — nilai asetnya tak berubah sama sekali. Uji ini membuktikan
    perbedaan itu benar-benar terjadi di basis data, bukan hanya di helper.
    """

    async def _siap(self, dbx, kode="3050102001", jumlah=1, harga=2_000_000,
                    kode_aset=None, harga_aset="15000000"):
        await _seed(dbx)
        rec = await _unwrap(rp.buat_perolehan)(rp.PerolehanIn(
            jenis="pembelian", pihak="PT Sumber Rejeki",
            nomor_kontrak="KTR-003/PPK/2026", nomor_bast="BAST-003/2026",
            tanggal_bast="2026-03-10",
            barang=[rp.BarangIn(uraian="RAM tambahan", kode=kode,
                                jumlah=jumlah, harga_satuan=harga)]),
            user=USER)
        await dbx.assets.insert_one({
            "id": "aset-lama", "asset_code": kode_aset or kode, "NUP": "7",
            "asset_name": "Server Rak", "purchase_price": harga_aset,
            "activity_id": "keg1", "kode_satker": "", "version": 1})
        return rec

    def test_nilai_aset_bertambah_dan_jurnal_202_tercatat(self, dbx, monkeypatch):
        import shared_utils as su
        jurnal = []

        async def _rekam(d):
            jurnal.append(d)

        # Endpoint mengimpor `catat_mutasi_bmn` LOKAL dari `shared_utils`;
        # menambal atribut modul `rp` tak berpengaruh sama sekali.
        monkeypatch.setattr(su, "catat_mutasi_bmn", _rekam, raising=False)

        async def skenario():
            rec = await self._siap(dbx)
            hasil = await _unwrap(rp.leburkan_ke_aset)(
                rec["id"], rp.LeburkanIn(index=0, asset_id="aset-lama"),
                user=USER)
            assert hasil["nilai_baru"] == 17_000_000
            segar = await dbx.assets.find_one({"id": "aset-lama"})
            assert segar["purchase_price"] == "17000000"
            assert jurnal and jurnal[0]["kode_transaksi"] == "202"
            # Murni transaksi NILAI — kuantitasnya tetap satu kesatuan.
            assert jurnal[0]["jumlah"] == 0
            assert jurnal[0]["nilai"] == 2_000_000
        _jalan(skenario())

    def test_barisnya_ditandai_TERLEBUR_bukan_sekadar_tertaut(self, dbx):
        """Tanpa penanda ini "Catat Semua Barang" tak bisa membedakannya dari
        baris yang menunggu dijadikan aset baru."""
        async def skenario():
            rec = await self._siap(dbx)
            await _unwrap(rp.leburkan_ke_aset)(
                rec["id"], rp.LeburkanIn(index=0, asset_id="aset-lama"),
                user=USER)
            segar = await dbx.pengadaan.find_one({"id": rec["id"]})
            baris = segar["barang"][0]
            assert baris["leburan"] is True
            assert baris["asset_id"] == "aset-lama"
            assert baris["NUP"] == "7"
        _jalan(skenario())

    def test_baris_terlebur_TIDAK_jadi_aset_baru_saat_catat_semua(self, dbx):
        """Kalau ikut terbuat, satu belanja tercatat DUA KALI: sebagai
        penambah nilai aset lama DAN sebagai aset baru ber-NUP sendiri."""
        async def skenario():
            rec = await self._siap(dbx)
            await _unwrap(rp.leburkan_ke_aset)(
                rec["id"], rp.LeburkanIn(index=0, asset_id="aset-lama"),
                user=USER)
            hasil = await _unwrap(rp.buat_draft_aset_dari_perolehan)(
                rec["id"], rp.BuatDraftAsetIn(activity_id="keg1"), user=USER)
            assert hasil["dibuat"] == 0
            assert hasil["dilewati_tertaut"] == 1
            assert hasil["peringatan_nup"] == []
        _jalan(skenario())

    def test_jumlah_lebih_dari_satu_DITOLAK_400(self, dbx):
        async def skenario():
            rec = await self._siap(dbx, jumlah=3)
            with pytest.raises(rp.HTTPException) as e:
                await _unwrap(rp.leburkan_ke_aset)(
                    rec["id"], rp.LeburkanIn(index=0, asset_id="aset-lama"),
                    user=USER)
            assert e.value.status_code == 400
            assert "1 NUP untuk 1 barang" in e.value.detail
            segar = await dbx.assets.find_one({"id": "aset-lama"})
            assert segar["purchase_price"] == "15000000"   # tak tersentuh
        _jalan(skenario())

    def test_aset_KDP_DITOLAK_400(self, dbx):
        async def skenario():
            rec = await self._siap(dbx, kode="7010101001")
            with pytest.raises(rp.HTTPException) as e:
                await _unwrap(rp.leburkan_ke_aset)(
                    rec["id"], rp.LeburkanIn(index=0, asset_id="aset-lama"),
                    user=USER)
            assert e.value.status_code == 400
            assert "KDP" in e.value.detail and "503" in e.value.detail
        _jalan(skenario())

    def test_kode_barang_berbeda_DITOLAK_400(self, dbx):
        async def skenario():
            rec = await self._siap(dbx, kode_aset="3060101001")
            with pytest.raises(rp.HTTPException) as e:
                await _unwrap(rp.leburkan_ke_aset)(
                    rec["id"], rp.LeburkanIn(index=0, asset_id="aset-lama"),
                    user=USER)
            assert e.value.status_code == 400 and "berbeda" in e.value.detail
        _jalan(skenario())

    def test_harga_nol_ditolak_bukan_menulis_jurnal_kosong(self, dbx):
        async def skenario():
            rec = await self._siap(dbx, harga=0)
            with pytest.raises(rp.HTTPException) as e:
                await _unwrap(rp.leburkan_ke_aset)(
                    rec["id"], rp.LeburkanIn(index=0, asset_id="aset-lama"),
                    user=USER)
            assert e.value.status_code == 400
        _jalan(skenario())

    def test_aset_tujuan_tak_ada_404(self, dbx):
        async def skenario():
            rec = await self._siap(dbx)
            with pytest.raises(rp.HTTPException) as e:
                await _unwrap(rp.leburkan_ke_aset)(
                    rec["id"], rp.LeburkanIn(index=0, asset_id="entah"),
                    user=USER)
            assert e.value.status_code == 404
        _jalan(skenario())

    def test_baris_di_luar_jangkauan_400(self, dbx):
        async def skenario():
            rec = await self._siap(dbx)
            with pytest.raises(rp.HTTPException) as e:
                await _unwrap(rp.leburkan_ke_aset)(
                    rec["id"], rp.LeburkanIn(index=9, asset_id="aset-lama"),
                    user=USER)
            assert e.value.status_code == 400
        _jalan(skenario())


# ── Tautan ke barang persediaan yang SUDAH TERDAFTAR ───────────────────────

class TestTautPersediaanTerdaftar:
    """Operator memilih kartu stok tujuannya; server berhenti menebak.

    Tebakan lama (kode awalan + nama barang sama persis) sudah dua kali salah
    arah. Uji-uji di sini memakai nama barang yang SENGAJA berbeda dari master
    — "Kertas HVS A4 80gr" versus "Kertas HVS A4" — supaya tebakan itu PASTI
    meleset. Dengan begitu, lulusnya uji hanya bisa disebabkan tautannya
    dipakai, bukan kebetulan tebakannya benar.
    """

    async def _master(self, dbx, **ubah):
        doc = {"id": "psd-a4", "kode_satker": "", "kode_barang": "1010301001000001",
               "nup": "1", "nama_barang": "Kertas HVS A4", "satuan": "Rim",
               "stok": 0, "batches": [], "harga_satuan": 0}
        doc.update(ubah)
        await dbx.persediaan.insert_one(doc)
        return doc

    def _perolehan(self, **ubah):
        b = {"uraian": "Kertas HVS A4 80gr", "kode": "1010301001",
             "jumlah": 5, "harga_satuan": 60_000}
        b.update(ubah)
        return rp.PerolehanIn(
            jenis="pembelian", pihak="PT X", nomor_bast="BAST-TAUT/2026",
            tanggal_bast="2026-03-12", barang=[rp.BarangIn(**b)])

    def test_baris_mengadopsi_kode_16_digit_masternya(self, dbx):
        async def skenario():
            await _seed(dbx)
            await self._master(dbx)
            rec = await _unwrap(rp.buat_perolehan)(
                self._perolehan(psd_master_id="psd-a4"), user=USER)
            assert rec["barang"][0]["kode"] == "1010301001000001", (
                "kode baris tetap 10 digit — LPB & kartu stok akan mencetak "
                "kode yang berbeda untuk barang yang sama")
            assert rec["barang"][0]["psd_master_id"] == "psd-a4"
            assert rec["barang"][0]["psd_master_nama"] == "Kertas HVS A4"
        _jalan(skenario())

    def test_stok_masuk_ke_kartu_yang_DIPILIH_bukan_kembarannya(self, dbx):
        """DUA kartu ber-kode barang SAMA, NUP berbeda — sah menurut master
        persediaan (keunikannya kode+NUP, bukan kode saja).

        Tebakan apa pun buta terhadap perbedaan ini: kode 16 digitnya identik,
        namanya pun identik, dan `find_one` mengambil salah satu sekenanya.
        Hanya pilihan operator yang bisa membedakan keduanya — jadi inilah
        satu-satunya kasus yang membuktikan tautannya SUNGGUH dipakai, bukan
        kebetulan sejalan dengan tebakan.
        """
        async def skenario():
            await _seed(dbx)
            await self._master(dbx)                       # psd-a4, NUP 1
            await self._master(dbx, id="psd-a4-kedua", nup="2")
            rec = await _unwrap(rp.buat_perolehan)(
                self._perolehan(psd_master_id="psd-a4-kedua"), user=USER)
            hasil = await _unwrap(rp.daftarkan_persediaan)(rec["id"], user=USER)
            assert hasil["dibuat_master"] == 0, (
                "master BARU dibuat padahal kartunya sudah dipilih operator")
            pertama = await dbx.persediaan.find_one({"id": "psd-a4"})
            kedua = await dbx.persediaan.find_one({"id": "psd-a4-kedua"})
            assert kedua["stok"] == 5, "stok mendarat di kartu yang tak dipilih"
            assert pertama["stok"] == 0
        _jalan(skenario())

    def test_kartu_yang_namanya_beda_pun_tak_melahirkan_master_baru(self, dbx):
        """Nama di BAST kerap lebih panjang daripada nama di master."""
        async def skenario():
            await _seed(dbx)
            await self._master(dbx)
            rec = await _unwrap(rp.buat_perolehan)(
                self._perolehan(psd_master_id="psd-a4"), user=USER)
            hasil = await _unwrap(rp.daftarkan_persediaan)(rec["id"], user=USER)
            assert hasil["dibuat_master"] == 0
            a4 = await dbx.persediaan.find_one({"id": "psd-a4"})
            assert a4["stok"] == 5
        _jalan(skenario())

    def test_tanpa_tautan_nama_yang_beda_MEMANG_melahirkan_master_baru(self, dbx):
        """Pembanding yang membuat uji di atas bermakna.

        Tanpa uji ini, `dibuat_master == 0` bisa saja karena tebakannya
        kebetulan berhasil — dan tautannya tak membuktikan apa pun.
        """
        async def skenario():
            await _seed(dbx)
            await self._master(dbx)
            rec = await _unwrap(rp.buat_perolehan)(self._perolehan(), user=USER)
            hasil = await _unwrap(rp.daftarkan_persediaan)(rec["id"], user=USER)
            assert hasil["dibuat_master"] == 1
            a4 = await dbx.persediaan.find_one({"id": "psd-a4"})
            assert a4["stok"] == 0
        _jalan(skenario())

    def test_master_satker_LAIN_ditolak_400(self, dbx):
        async def skenario():
            await _seed(dbx)
            await self._master(dbx, id="psd-lain", kode_satker="999999")
            with pytest.raises(rp.HTTPException) as e:
                await _unwrap(rp.buat_perolehan)(
                    self._perolehan(psd_master_id="psd-lain"),
                    user={**USER, "role": "operator", "kode_satker": "111111"})
            assert e.value.status_code == 400
            assert "satker" in str(e.value.detail).lower()
        _jalan(skenario())

    def test_kode_yang_menunjuk_barang_LAIN_ditolak_400(self, dbx):
        async def skenario():
            await _seed(dbx)
            await self._master(dbx)
            with pytest.raises(rp.HTTPException) as e:
                await _unwrap(rp.buat_perolehan)(
                    self._perolehan(kode="1010302002", psd_master_id="psd-a4"),
                    user=USER)
            assert e.value.status_code == 400
            assert "tidak cocok" in str(e.value.detail)
        _jalan(skenario())

    def test_master_yang_LENYAP_sesudah_dipilih_dilaporkan_gagal(self, dbx):
        """Bukan diam-diam diganti master baru — itu kesalahan yang sama."""
        async def skenario():
            await _seed(dbx)
            await self._master(dbx)
            rec = await _unwrap(rp.buat_perolehan)(
                self._perolehan(psd_master_id="psd-a4"), user=USER)
            await dbx.persediaan.delete_one({"id": "psd-a4"})
            hasil = await _unwrap(rp.daftarkan_persediaan)(rec["id"], user=USER)
            assert hasil["masuk"] == 0
            assert hasil["dibuat_master"] == 0
            assert len(hasil["gagal"]) == 1
            assert "pilih ulang" in hasil["gagal"][0]
        _jalan(skenario())

    def test_peringatan_dipotret_sebelum_baris_diposting(self, dbx):
        """Dihitung sesudah perulangan, daftarnya SELALU kosong."""
        async def skenario():
            await _seed(dbx)
            rec = await _unwrap(rp.buat_perolehan)(self._perolehan(), user=USER)
            hasil = await _unwrap(rp.daftarkan_persediaan)(rec["id"], user=USER)
            assert hasil["masuk"] == 1, "barisnya tak jadi diposting"
            assert [w["index"] for w in hasil["peringatan_persediaan"]] == [0]
        _jalan(skenario())

    def test_baris_tertaut_tak_memunculkan_peringatan(self, dbx):
        async def skenario():
            await _seed(dbx)
            await self._master(dbx)
            rec = await _unwrap(rp.buat_perolehan)(
                self._perolehan(psd_master_id="psd-a4"), user=USER)
            hasil = await _unwrap(rp.daftarkan_persediaan)(rec["id"], user=USER)
            assert hasil["peringatan_persediaan"] == []
        _jalan(skenario())

    def test_catat_semua_meneruskan_peringatannya(self, dbx):
        async def skenario():
            await _seed(dbx)
            rec = await _unwrap(rp.buat_perolehan)(self._perolehan(), user=USER)
            hasil = await _unwrap(rp.catat_semua_barang)(
                rec["id"], rp.CatatSemuaIn(activity_id="keg1",
                                           booking_nomor=False), user=USER)
            assert [w["index"] for w in hasil["peringatan_persediaan"]] == [0]
        _jalan(skenario())

    def test_ubah_register_mempertahankan_tautan(self, dbx):
        """Form ubah mengirim ulang seluruh daftar barang. Bila `psd_master_id`
        tak ikut dibaca server, satu perbaikan salah ketik akan MELEPAS tautan
        yang sudah dipilih tanpa satu pun tanda di layar."""
        async def skenario():
            await _seed(dbx)
            await self._master(dbx)
            rec = await _unwrap(rp.buat_perolehan)(
                self._perolehan(psd_master_id="psd-a4"), user=USER)
            segar = await _unwrap(rp.ubah_perolehan)(
                rec["id"], rp.PerolehanUbahIn(
                    jenis="pembelian", pihak="PT X",
                    nomor_bast="BAST-TAUT/2026", tanggal_bast="2026-03-12",
                    barang=[rp.BarangUbahIn(
                        uraian="Kertas HVS A4 80gr", kode="1010301001000001",
                        jumlah=5, harga_satuan=60_000,
                        psd_master_id="psd-a4")]), user=USER)
            assert segar["barang"][0]["psd_master_id"] == "psd-a4"
        _jalan(skenario())
