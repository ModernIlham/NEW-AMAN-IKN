"""Unsur tulisan milik satker: tersimpan, disisipkan, bisa dihapus.

Permintaan pemilik: *"pada bagian 'Perkiraan nomor yang akan terbit' kita dapat
menyisipkan kata/unsur baru sesuai ketikan, dan tersimpan dan dapat terhapus
juga agar konsisten bentuk penulisannya"*.

Yang dijawab: potongan teks tetap yang sering muncul di nomor surat satker
(mis. "SETJEN", "UND") kini disimpan sebagai daftar. Sekali ditetapkan, ia
disisipkan dengan satu ketukan alih-alih diketik ulang tiap kali — dan salah
ketik satu huruf pada satu surat tidak lagi mungkin. Itulah arti "konsisten"
di sini.

Aturan yang paling menentukan: kurung kurawal DITOLAK. `{...}` adalah bahasa
placeholder; unsur bernama `{apa saja}` akan lolos ke `format_nomor` lalu
ditolak validator placeholder dengan pesan yang menunjuk ke tempat yang SALAH
— pengguna diberi tahu formatnya rusak, padahal yang perlu diperbaiki daftar
unsurnya.
"""
import asyncio

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.persuratan as rp
from persuratan_utils import (
    MAKS_PANJANG_UNSUR, MAKS_UNSUR_KUSTOM, bangun_nomor,
    bersihkan_unsur_kustom, validate_unsur_kustom,
)

ADMIN = {"username": "admin", "role": "admin", "name": "Admin", "kode_satker": ""}


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


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import shared_utils as su
    for mod in (rp, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)

    async def _diam(*a, **k):
        return None

    monkeypatch.setattr(rp, "log_audit", _diam, raising=False)
    return fake


class TestPembersihan:
    def test_dipangkas_tanpa_kosong_tanpa_kembar(self):
        assert bersihkan_unsur_kustom(
            [" SETJEN ", "SETJEN", "", "   ", None, "UND"]) == ["SETJEN", "UND"]

    def test_urutan_dipertahankan(self):
        """Urutan chip di layar = urutan yang ditetapkan operator; mengurutkan
        ulang secara diam-diam membuat susunan yang sudah dihafal berubah."""
        assert bersihkan_unsur_kustom(["C", "A", "B"]) == ["C", "A", "B"]

    def test_masukan_bukan_daftar_tidak_meledak(self):
        assert bersihkan_unsur_kustom(None) == []


class TestValidasi:
    def test_kurung_kurawal_ditolak(self):
        pesan = validate_unsur_kustom(["{urut}"])
        assert pesan and "kurung kurawal" in pesan[0]

    def test_terlalu_panjang_ditolak(self):
        pesan = validate_unsur_kustom(["A" * (MAKS_PANJANG_UNSUR + 1)])
        assert pesan and "terlalu panjang" in pesan[0]

    def test_terlalu_banyak_ditolak(self):
        pesan = validate_unsur_kustom([f"U{i}" for i in range(MAKS_UNSUR_KUSTOM + 1)])
        assert pesan and "maksimal" in pesan[0]

    def test_teks_wajar_diterima(self):
        assert validate_unsur_kustom(["SETJEN", "UND", "B"]) == []

    def test_pemisah_tetap_boleh(self):
        """Garis miring & strip adalah bagian sah bentuk nomor — melarangnya
        akan memaksa operator kembali mengetik manual."""
        assert validate_unsur_kustom(["/B/", "-UND-"]) == []


class TestTersimpanDanTerhapus:
    def test_tersimpan_lalu_terbaca(self, dbx):
        async def skenario():
            hasil = await _unwrap(rp.set_pengaturan_persuratan)(
                rp.PengaturanIn(unsur_kustom=["SETJEN", "UND"]), user=ADMIN)
            assert hasil["unsur_kustom"] == ["SETJEN", "UND"]
            lagi = await _unwrap(rp.get_pengaturan_persuratan)(_user=ADMIN)
            assert lagi["unsur_kustom"] == ["SETJEN", "UND"]
        _jalan(skenario())

    def test_dapat_dihapus(self, dbx):
        async def skenario():
            await _unwrap(rp.set_pengaturan_persuratan)(
                rp.PengaturanIn(unsur_kustom=["SETJEN", "UND"]), user=ADMIN)
            hasil = await _unwrap(rp.set_pengaturan_persuratan)(
                rp.PengaturanIn(unsur_kustom=["SETJEN"]), user=ADMIN)
            assert hasil["unsur_kustom"] == ["SETJEN"]
        _jalan(skenario())

    def test_dikosongkan_seluruhnya(self, dbx):
        async def skenario():
            await _unwrap(rp.set_pengaturan_persuratan)(
                rp.PengaturanIn(unsur_kustom=["SETJEN"]), user=ADMIN)
            hasil = await _unwrap(rp.set_pengaturan_persuratan)(
                rp.PengaturanIn(unsur_kustom=[]), user=ADMIN)
            assert hasil["unsur_kustom"] == []
        _jalan(skenario())

    def test_unsur_bercurang_ditolak_di_gerbang(self, dbx):
        """Ditolak SEBELUM tersimpan — bukan dibiarkan lolos lalu memerahkan
        validator format dengan pesan yang menunjuk tempat yang salah."""
        async def skenario():
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as e:
                await _unwrap(rp.set_pengaturan_persuratan)(
                    rp.PengaturanIn(unsur_kustom=["{urut}"]), user=ADMIN)
            assert e.value.status_code == 400
            assert "kurung kurawal" in str(e.value.detail)
            tersimpan = await dbx.persuratan_settings.find_one({"type": "global"})
            assert tersimpan is None
        _jalan(skenario())


class TestUnsurBenarBenarMasukNomor:
    def test_tulisan_tetap_tampil_apa_adanya(self):
        """Unsur adalah teks biasa: ia tak diterjemahkan, hanya dicetak."""
        t = "{kode_keamanan}-{urut}/SETJEN/{kode_unit}/{bulan_romawi}/{tahun}"
        nomor = bangun_nomor(t, 1, "2026-08-19", kode_unit="OIKN",
                             kode_keamanan="B")
        assert nomor == "B-001/SETJEN/OIKN/VIII/2026", nomor
