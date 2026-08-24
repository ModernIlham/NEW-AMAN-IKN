"""Uji ENDPOINT: LPB PERSEDIAAN membawa nama PPK dari BAST yang ditautkan.

Jalur ini punya satu mode gagal yang SENYAP: `_ambil_snapshot_perolehan`
memproyeksikan hanya sebagian field perolehan. Bila `ppk_*` tak ikut
diproyeksikan, `snapshot_perolehan` membaca None → nama PPK kosong di jurnal
dan di LPB, tanpa satu pun galat. Uji ini ada supaya proyeksi itu tak bisa
dipersempit lagi tanpa ketahuan.
"""
import asyncio

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.persediaan as rps

USER = {"username": "gudang", "role": "admin", "kode_satker": ""}
# Operator yang TERIKAT satker — dipakai uji yang benar-benar
# menerbitkan nomor surat.
USER_SATKER = {"username": "gudang", "role": "admin",
               "kode_satker": "527001"}


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
    import shared_utils as su
    # `routes.persuratan` WAJIB ikut ditambal: jalur booking nomor LPB membaca
    # setelan penomoran & counter agenda lewat db MILIKNYA SENDIRI. Tanpa ini
    # ia menyentuh koneksi asli dan meledak dengan "attached to a different
    # loop" — kegagalan yang menyamar sebagai galat infrastruktur, bukan bug.
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


async def _seed(dbx, ppk_di_bast=True):
    await dbx.pengadaan.insert_one({
        "id": "perol-1", "kode_satker": "", "jenis": "pembelian",
        "pihak": "PT Sumber Rejeki", "nomor_bast": "BAST-001/2026",
        "tanggal_bast": "2026-03-10",
        **({"ppk_nama": "Budi Santoso",
            "ppk_nip": "199001012015011001"} if ppk_di_bast else {})})
    await dbx.persediaan.insert_one({
        "id": "psd-1", "kode_satker": "", "kode_barang": "1010301001000001",
        "nup": "1", "nama_barang": "Kertas HVS A4", "satuan": "Rim",
        "stok": 0, "batches": [], "harga_satuan": 0})


def _massal():
    return rps.TransaksiMassalIn(
        arah="masuk", jenis="pembelian", perolehan_id="perol-1",
        no_bukti="LPB-001", jenis_dokumen="BAST", tgl_dokumen="2026-03-10",
        penyedia="PT Sumber Rejeki", booking_otomatis=False,
        items=[rps.ItemMassalIn(persediaan_id="psd-1", jumlah=10,
                                harga_satuan=55_000)])


def test_lpb_persediaan_membawa_ppk_dari_bast(dbx):
    async def skenario():
        await _seed(dbx)
        hasil = await _unwrap(rps.transaksi_massal)(_massal(), user=USER)
        assert hasil["sukses"] == 1
        lpb = await dbx.lpb.find_one({"id": hasil["lpb_id"]})
        assert lpb["ppk_nama"] == "Budi Santoso"
        assert lpb["ppk_nip"] == "199001012015011001"
    _jalan(skenario())


def test_jurnal_persediaan_juga_membawa_ppk(dbx):
    """Snapshot PPK menempel di JURNAL-nya, bukan hanya di dokumen cetak.

    Tanpa ini, LPB bisa menyebut satu nama sementara jurnal yang menjadi
    dasarnya tak bisa membuktikan dari mana nama itu datang.
    """
    async def skenario():
        await _seed(dbx)
        await _unwrap(rps.transaksi_massal)(_massal(), user=USER)
        j = await dbx.transaksi_persediaan.find_one({"perolehan_id": "perol-1"})
        assert j is not None
        assert j["perolehan_ppk_nama"] == "Budi Santoso"
        assert j["perolehan_ppk_nip"] == "199001012015011001"
    _jalan(skenario())


def test_tanpa_ppk_di_bast_jatuh_ke_registry_pejabat(dbx):
    """BAST lama (belum punya field PPK) tetap melahirkan LPB ber-PPK.

    Sumber keduanya: peran `ppk` yang BERLAKU pada tanggal LPB.
    """
    async def skenario():
        await _seed(dbx, ppk_di_bast=False)
        await dbx.pejabat.insert_one({
            "id": "pj-ppk", "nama": "Siti Aminah", "nip": "198505052010012002",
            "jabatan": "PPK", "peran": ["ppk"], "kode_satker": "",
            "berlaku_mulai": "2026-01-01"})
        hasil = await _unwrap(rps.transaksi_massal)(_massal(), user=USER)
        lpb = await dbx.lpb.find_one({"id": hasil["lpb_id"]})
        assert lpb["ppk_nama"] == "Siti Aminah"
    _jalan(skenario())


def test_tanpa_ppk_sama_sekali_lpb_tetap_terbit(dbx):
    """Ketiadaan PPK bukan alasan menolak mencatat barang yang sudah datang."""
    async def skenario():
        await _seed(dbx, ppk_di_bast=False)
        hasil = await _unwrap(rps.transaksi_massal)(_massal(), user=USER)
        lpb = await dbx.lpb.find_one({"id": hasil["lpb_id"]})
        assert lpb["ppk_nama"] == ""
        assert lpb["jumlah_barang"] == 1
    _jalan(skenario())


def test_bast_satker_lain_tak_bisa_ditautkan(dbx):
    """Temuan audit adversarial: `_ambil_snapshot_perolehan` tak ter-scope.

    Tanpa scope, writer satker A yang memegang uuid BAST satker B dapat
    MENYALIN identitas dokumen B — nomor BAST, penyedia, dan (sejak PR ini)
    nama + NIP PPK — ke jurnal dan LPB satker A. Bukan sekadar terbaca:
    tersimpan permanen di dokumen resmi, lengkap dengan data pribadi.
    """
    from fastapi import HTTPException

    async def skenario():
        await _seed(dbx)
        # BAST di atas ber-`kode_satker: ""` (era lama, terbuka). Ganti jadi
        # milik satker lain supaya penjaganya benar-benar diuji.
        await dbx.pengadaan.update_one({"id": "perol-1"},
                                       {"$set": {"kode_satker": "999999"}})
        await dbx.persediaan.update_one({"id": "psd-1"},
                                        {"$set": {"kode_satker": "111111"}})
        user_a = {"username": "gudang-a", "role": "admin",
                  "kode_satker": "111111"}
        with pytest.raises(HTTPException) as e:
            await _unwrap(rps.transaksi_massal)(_massal(), user=user_a)
        assert e.value.status_code == 404
        # Penolakan terjadi DI MUKA — tak ada stok yang terlanjur bergerak.
        assert await dbx.transaksi_persediaan.count_documents({}) == 0
        assert await dbx.lpb.count_documents({}) == 0
    _jalan(skenario())


def test_lpb_persediaan_berkategori_persediaan_dan_tampil_di_filter(dbx):
    """Dokumen lama tanpa field `kategori` tak boleh lenyap dari filter."""
    async def skenario():
        await _seed(dbx)
        await _unwrap(rps.transaksi_massal)(_massal(), user=USER)
        # LPB era-lama: sengaja TANPA field `kategori` sama sekali.
        await dbx.lpb.insert_one({
            "id": "lpb-lama", "kode_satker": "", "nomor": "LPB-000",
            "tanggal": "2025-01-01", "items": [], "jumlah_barang": 0,
            "created_at": "2025-01-01T00:00:00+00:00"})

        semua = await _unwrap(rps.daftar_lpb)(_user=USER)
        assert semua["total"] == 2

        psd = await _unwrap(rps.daftar_lpb)(kategori="persediaan", _user=USER)
        ids = {i["id"] for i in psd["items"]}
        assert "lpb-lama" in ids, "riwayat lama hilang dari filter persediaan"
        assert psd["total"] == 2

        aset = await _unwrap(rps.daftar_lpb)(kategori="aset", _user=USER)
        assert aset["total"] == 0
    _jalan(skenario())


# ═══════════════════════════════════════════════════════════════════════════
# TEMUAN AUDIT: privasi NIP, scope penerbit, cakupan penomoran
# ═══════════════════════════════════════════════════════════════════════════

def test_nip_ppk_non_asn_tak_dicetak_di_info_lpb():
    """Aturan privasi Non-ASN berlaku juga di baris info, bukan hanya blok TTD.

    `snapshot_ppk` sengaja membekukan `ppk_status_kepegawaian` justru untuk
    keputusan ini. Mencetak `ppk_nip` mentah membatalkan aturan yang ditegakkan
    di seluruh dokumen lain lewat pintu belakang.
    """
    baris = rps._baris_nip_ppk({
        "ppk_nama": "Andi Pratama", "ppk_nip": "3201010101900001",
        "ppk_status_kepegawaian": "non_asn"})
    assert baris == "", "NIK/NIP Non-ASN tercetak di LPB"


def test_nip_ppk_asn_tetap_dicetak():
    baris = rps._baris_nip_ppk({
        "ppk_nama": "Budi Santoso", "ppk_nip": "199001012015011001",
        "ppk_status_kepegawaian": "pns"})
    assert "199001012015011001" in baris


def test_baris_nip_ppk_tanpa_ppk_tetap_bertitik():
    assert rps._baris_nip_ppk({}) == "NIP PPK: <b>-</b>"
    assert rps._baris_nip_ppk({"ppk_nama": ""}) == "NIP PPK: <b>-</b>"


def test_lpb_membekukan_status_kepegawaian_ppk(dbx):
    """Status ikut disimpan di dokumen — kalau tidak, `_baris_nip_ppk` buta."""
    async def skenario():
        await _seed(dbx, ppk_di_bast=False)
        await dbx.pejabat.insert_one({
            "id": "pj-ppk", "nama": "Andi Pratama", "nip": "3201010101900001",
            "jabatan": "PPK", "peran": ["ppk"], "kode_satker": "",
            "berlaku_mulai": "2026-01-01", "status_kepegawaian": "non_asn"})
        hasil = await _unwrap(rps.transaksi_massal)(_massal(), user=USER)
        lpb = await dbx.lpb.find_one({"id": hasil["lpb_id"]})
        assert lpb["ppk_status_kepegawaian"] == "non_asn"
        assert rps._baris_nip_ppk(lpb) == ""
    _jalan(skenario())


def test_booking_nomor_lpb_benar_benar_menerbitkan_nomor(dbx):
    """CAKUPAN PENOMORAN — seluruh uji lain mematikannya (temuan audit).

    Nomor LPB adalah nomor surat resmi yang tercatat di buku agenda satker.
    Jalur yang tak pernah dijalankan uji apa pun adalah jalur yang tak pernah
    dijamin bekerja.
    """
    async def skenario():
        await _seed(dbx)
        m = _massal()
        m.booking_otomatis = True
        m.no_bukti = ""                     # kosongkan agar booking dipakai
        # Pemanggil BER-SATKER. Penerbitan nomor otomatis kini menolak
        # pemanggil pusat tanpa satker (lihat satker_wajib.py): surat
        # berstempel "" tampil di register SETIAP satker dan menghabiskan
        # nomor agenda mereka. Yang diuji di sini penomorannya, jadi
        # pemanggilnya dibuat wajar.
        hasil = await _unwrap(rps.transaksi_massal)(m, user=USER_SATKER)
        assert hasil["nomor_lpb"], "nomor LPB tak pernah terbit"

        lpb = await dbx.lpb.find_one({"id": hasil["lpb_id"]})
        assert lpb["nomor"] == hasil["nomor_lpb"]
        assert lpb["surat_id"], "LPB tak tertaut ke surat yang dipesan"

        # Surat benar-benar tercatat di buku agenda, berstatus dibooking.
        surat = await dbx.surat.find_one({"id": lpb["surat_id"]})
        assert surat is not None
        assert surat["status"] == "dibooking"
        assert surat["jenis"] == "keluar"
        assert surat["referensi"] == "LPB"
        assert surat["nomor"] == hasil["nomor_lpb"]
    _jalan(skenario())


def test_nomor_lpb_tak_pernah_terpakai_dua_kali(dbx):
    """Deret nomor agenda maju — dua LPB tak boleh bernomor sama."""
    async def skenario():
        await _seed(dbx)
        nomor = []
        for _ in range(3):
            m = _massal()
            m.booking_otomatis = True
            m.no_bukti = ""
            hasil = await _unwrap(rps.transaksi_massal)(m, user=USER_SATKER)
            nomor.append(hasil["nomor_lpb"])
        assert len(set(nomor)) == 3, f"nomor LPB berulang: {nomor}"
    _jalan(skenario())
