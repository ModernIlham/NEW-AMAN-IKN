"""Register perolehan bisa DIPERBAIKI — tapi tidak sampai membuat anaknya bohong.

Sebelum ini halaman Pengadaan tak punya tombol ubah sama sekali: satu salah
ketik nomor BAST atau harga satuan hanya bisa dibereskan dengan menghapus lalu
mencatat ulang — dan penjaga hapus justru menolak begitu barangnya sudah
tercatat ke stok/aset. Artinya register yang salah terkunci salah selamanya.

Menambah tombol ubah tanpa penjaga akan menukar satu masalah dengan masalah
yang lebih buruk. Register perolehan adalah **dokumen sumber**: aset menyimpan
snapshot-nya, stok persediaan lahir darinya, dan PDF BAST PPK→KPB disusun ULANG
dari data ini setiap kali diunduh. Mengubahnya bebas berarti diam-diam mengubah
isi dokumen resmi yang sudah bernomor — bahkan yang sudah dicetak.

Uji ini menjaga ketiga tingkat kunci itu (lihat `kunci_ubah_perolehan`), dan
menjaga bahwa yang ditolak ditolak DENGAN SUARA (409 + alasan), bukan diterima
lalu diabaikan.
"""
import asyncio

import pytest
from fastapi import HTTPException
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
    import shared_utils as su
    for mod in (rp, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)
        if hasattr(mod, "log_audit"):
            monkeypatch.setattr(mod, "log_audit", _diam, raising=False)
    return fake


def _payload(**ubah):
    dasar = dict(jenis="pembelian", pihak="PT Sumber Rejeki",
                 nomor_kontrak="KTR-001/PPK/2026", nomor_bast="BAST-001/2026",
                 tanggal_bast="2026-03-10", keterangan="",
                 barang=[rp.BarangUbahIn(uraian="Printer LaserJet",
                                         kode="3050102001", jumlah=2,
                                         harga_satuan=2_500_000)])
    dasar.update(ubah)
    return rp.PerolehanUbahIn(**dasar)


async def _catat(dbx, **ubah):
    """Satu register tersimpan langsung ke DB — melewati endpoint buat supaya
    uji ini hanya menguji jalur ubah."""
    rec = {"id": "p1", "kode_satker": "", "jenis": "pembelian",
           "pihak": "PT Sumber Rejeki", "nomor_kontrak": "KTR-001/PPK/2026",
           "nomor_bast": "BAST-001/2026", "tanggal_bast": "2026-03-10",
           "keterangan": "", "dokumen": {"bast": True, "kontrak": True},
           "barang": [{"uraian": "Printer LaserJet", "kode": "3050102001",
                       "jumlah": 2, "harga_satuan": 2_500_000,
                       "asset_id": "", "asset_code": "", "NUP": "",
                       "asset_name": ""}],
           "lampiran_berkas": [], "created_by": "operator"}
    rec.update(ubah)
    await dbx.pengadaan.insert_one(dict(rec))
    return rec


class TestRegisterMasihPolos:
    """Belum melahirkan apa pun → semua boleh diperbaiki."""

    def test_identitas_dan_barang_tersimpan(self, dbx):
        async def skenario():
            await _catat(dbx)
            hasil = await _unwrap(rp.ubah_perolehan)("p1", _payload(
                pihak="CV Sumber Rejeki",
                nomor_bast="BAST-001-REV/2026",
                keterangan="perbaikan salah ketik",
                barang=[rp.BarangUbahIn(uraian="Printer LaserJet Pro",
                                        kode="3050102001", jumlah=3,
                                        harga_satuan=2_600_000)]), user=USER)
            assert hasil["pihak"] == "CV Sumber Rejeki"
            assert hasil["nomor_bast"] == "BAST-001-REV/2026"
            assert hasil["barang"][0]["jumlah"] == 3
            assert hasil["nilai"] == 7_800_000
            segar = await dbx.pengadaan.find_one({"id": "p1"})
            assert segar["pihak"] == "CV Sumber Rejeki"
            assert segar["updated_by"] == "operator"
        _jalan(skenario())

    def test_tanggal_masa_depan_tetap_ditolak(self, dbx):
        """Validasi pencatatan berlaku sama saat mengubah — kalau tidak, aturan
        yang dijaga di pintu masuk bisa dilangkahi lewat pintu samping."""
        async def skenario():
            await _catat(dbx)
            with pytest.raises(HTTPException) as e:
                await _unwrap(rp.ubah_perolehan)(
                    "p1", _payload(tanggal_bast="2099-01-01"), user=USER)
            assert e.value.status_code == 400
            assert "masa depan" in str(e.value.detail)
        _jalan(skenario())

    def test_barang_null_tidak_mengosongkan_daftar(self, dbx):
        """Klien yang hanya memperbaiki keterangan mengirim `barang: null`.
        Kalau itu diartikan "daftar kosong", satu register kehilangan seluruh
        barangnya hanya karena salah ketik keterangan diperbaiki."""
        async def skenario():
            await _catat(dbx)
            hasil = await _unwrap(rp.ubah_perolehan)(
                "p1", _payload(barang=None, keterangan="hanya keterangan"),
                user=USER)
            assert len(hasil["barang"]) == 1
            assert hasil["keterangan"] == "hanya keterangan"
        _jalan(skenario())

    def test_tanpa_perubahan_tidak_menulis_apa_pun(self, dbx, monkeypatch):
        """Menekan Simpan tanpa mengubah apa pun tak boleh meninggalkan jejak.

        Register perolehan sering dibuka hanya untuk DIBACA. Kalau tiap
        penutupan form menulis satu baris audit "diubah", jejak yang seharusnya
        menjawab *siapa mengubah apa* berubah jadi daftar orang yang pernah
        melihat — dan yang sungguh mengubah tenggelam di dalamnya.
        """
        jejak = []

        async def _rekam(*a, **k):
            jejak.append((a, k))

        monkeypatch.setattr(rp, "log_audit", _rekam, raising=False)

        async def skenario():
            await _catat(dbx)
            hasil = await _unwrap(rp.ubah_perolehan)("p1", _payload(), user=USER)
            assert hasil["nomor_bast"] == "BAST-001/2026"
            assert jejak == [], "menulis audit padahal tak ada yang berubah"
            segar = await dbx.pengadaan.find_one({"id": "p1"})
            assert "updated_at" not in segar, "dokumen ikut disentuh tanpa perubahan"
        _jalan(skenario())


class TestBarangSudahTercatat:
    """Barang sudah jadi stok/aset → daftarnya dikunci, identitas masih boleh."""

    async def _dengan_aset(self, dbx):
        await _catat(dbx, barang=[{
            "uraian": "Printer LaserJet", "kode": "3050102001", "jumlah": 2,
            "harga_satuan": 2_500_000, "asset_id": "a1",
            "asset_code": "3050102001", "NUP": "1",
            "asset_name": "Printer LaserJet"}])
        await dbx.assets.insert_one({"id": "a1", "asset_name": "Printer LaserJet",
                                     "perolehan_id": "p1"})

    def test_mengubah_daftar_barang_ditolak_dengan_alasan(self, dbx):
        async def skenario():
            await self._dengan_aset(dbx)
            with pytest.raises(HTTPException) as e:
                await _unwrap(rp.ubah_perolehan)("p1", _payload(
                    barang=[rp.BarangUbahIn(uraian="Printer lain", kode="",
                                            jumlah=9, harga_satuan=1)]),
                    user=USER)
            assert e.value.status_code == 409
            assert "sudah tercatat" in str(e.value.detail)
            segar = await dbx.pengadaan.find_one({"id": "p1"})
            assert segar["barang"][0]["jumlah"] == 2, "daftar ikut tertulis meski ditolak"
        _jalan(skenario())

    def test_identitas_masih_boleh_diperbaiki(self, dbx):
        async def skenario():
            await self._dengan_aset(dbx)
            hasil = await _unwrap(rp.ubah_perolehan)(
                "p1", _payload(pihak="CV Nama Benar", barang=None), user=USER)
            assert hasil["pihak"] == "CV Nama Benar"
        _jalan(skenario())

    def test_snapshot_di_aset_ikut_disegarkan(self, dbx):
        """Aset menyimpan salinan identitas dokumen sumbernya. Tanpa proyeksi
        ulang, kartu aset tetap menyebut penyedia/nomor BAST yang lama —
        register benar, aset bohong, dan tak ada yang tahu mana yang benar."""
        async def skenario():
            await self._dengan_aset(dbx)
            await _unwrap(rp.ubah_perolehan)(
                "p1", _payload(pihak="CV Nama Benar",
                               nomor_bast="BAST-009/2026", barang=None),
                user=USER)
            aset = await dbx.assets.find_one({"id": "a1"})
            snap = aset.get("perolehan") or {}
            assert snap.get("pihak") == "CV Nama Benar", snap
            assert snap.get("nomor_bast") == "BAST-009/2026", snap
        _jalan(skenario())


class TestDokumenResmiSudahTerbit:
    """BAST PPK→KPB terbit / ada LPB → hanya keterangan."""

    def test_identitas_ditolak_setelah_bast_ppk_terbit(self, dbx):
        async def skenario():
            await _catat(dbx, bast_ppk={"nomor": "BAST-PPK-001/2026"})
            with pytest.raises(HTTPException) as e:
                await _unwrap(rp.ubah_perolehan)(
                    "p1", _payload(pihak="CV Ganti", barang=None), user=USER)
            assert e.value.status_code == 409
            assert "BAST PPK" in str(e.value.detail)
            assert "pihak" in str(e.value.detail), "alasan tak menyebut field yang ditolak"
        _jalan(skenario())

    def test_keterangan_tetap_boleh(self, dbx):
        async def skenario():
            await _catat(dbx, bast_ppk={"nomor": "BAST-PPK-001/2026"})
            hasil = await _unwrap(rp.ubah_perolehan)(
                "p1", _payload(keterangan="berkas fisik ada di lemari 3",
                               barang=None), user=USER)
            assert hasil["keterangan"] == "berkas fisik ada di lemari 3"
            assert hasil["pihak"] == "PT Sumber Rejeki"
        _jalan(skenario())

    def test_lpb_gabungan_ikut_membekukan(self, dbx):
        """LPB gabungan menunjuk banyak register lewat `perolehan_ids`. Kalau
        hanya `perolehan_id` tunggal yang diperiksa, register yang masuk LPB
        gabungan tetap bisa berubah isi di belakang dokumennya."""
        async def skenario():
            await _catat(dbx)
            await dbx.lpb.insert_one({"id": "l1", "perolehan_ids": ["p1", "p2"]})
            with pytest.raises(HTTPException) as e:
                await _unwrap(rp.ubah_perolehan)(
                    "p1", _payload(nomor_bast="BAST-BARU", barang=None), user=USER)
            assert e.value.status_code == 409
            assert "LPB" in str(e.value.detail)
        _jalan(skenario())


class TestIsolasiSatker:
    def test_register_satker_lain_tidak_dapat_diubah(self, dbx):
        async def skenario():
            await _catat(dbx, kode_satker="111111")
            with pytest.raises(HTTPException) as e:
                await _unwrap(rp.ubah_perolehan)(
                    "p1", _payload(pihak="Disusupi"),
                    user={**USER, "role": "operator", "kode_satker": "999999"})
            assert e.value.status_code == 403
            segar = await dbx.pengadaan.find_one({"id": "p1"})
            assert segar["pihak"] == "PT Sumber Rejeki"
        _jalan(skenario())

    def test_perolehan_hilang_404(self, dbx):
        async def skenario():
            with pytest.raises(HTTPException) as e:
                await _unwrap(rp.ubah_perolehan)("entah", _payload(), user=USER)
            assert e.value.status_code == 404
        _jalan(skenario())


class TestDaftarMembawaStatusKunci:
    def test_list_menyertakan_status_ubah(self, dbx):
        """Tombol di UI harus tahu apa yang terkunci SEBELUM operator mengetik —
        dan itu dihitung server, bukan ditebak klien dari field lain."""
        async def skenario():
            await _catat(dbx)
            await _catat(dbx, id="p2", bast_ppk={"nomor": "X"})
            hasil = await _unwrap(rp.list_pengadaan)(_user=USER)
            per_id = {p["id"]: p["ubah"] for p in hasil["items"]}
            assert per_id["p1"]["identitas"] is True
            assert per_id["p1"]["barang"] is True
            assert per_id["p2"]["identitas"] is False
            assert per_id["p2"]["alasan"]
        _jalan(skenario())
