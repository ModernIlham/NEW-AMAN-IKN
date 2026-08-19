"""Susunan nomor yang sedang dirancang bisa dilihat SEBELUM disimpan.

Dua keluhan pemilik, satu akar:

  1. "pada saat komposisi Nomor dipilih, Format Nomor tidak berubah" — memang:
     penyisipan placeholder dikerjakan server saat SIMPAN, sehingga memilih
     komposisi tampak tidak berpengaruh apa-apa sampai tombol ditekan.
  2. "pada format nomor kita tidak tahu nama header kepalanya untuk memanggil
     datanya" — kolomnya menerima template mentah, sementara nama bagiannya
     hanya tertulis sebagai deretan `{...}` di keterangan dialog.

Jawabannya SATU endpoint, bukan dua aturan. `pratinjau-nomor` kini menerima
template rancangan (dan/atau komposisi) lalu mengembalikan template hasil
penyisipannya beserta contoh nomornya.

Menaruhnya di server, bukan menghitungnya di klien, adalah keputusan sadar:
aturan penyisipan placeholder dan perakitan nomor hanya boleh ada di satu
tempat. Menyalinnya ke JavaScript berarti dua aturan yang wajib tetap sama
selamanya — dan yang pertama kali berbeda tak akan terlihat siapa pun, sebab
keduanya sama-sama menghasilkan nomor yang "kelihatan benar".
"""
import asyncio

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.persuratan as rp
from persuratan_utils import (
    FORMAT_NOMOR_DEFAULT, PLACEHOLDER_NOMOR, _PLACEHOLDER_DIKENAL,
)

USER = {"username": "op", "role": "admin", "name": "Op", "kode_satker": ""}


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
    return fake


async def _pra(**kw):
    return await _unwrap(rp.pratinjau_nomor)(_user=USER, **kw)


class TestDaftarPlaceholder:
    """Jawaban untuk "tidak tahu nama header kepalanya"."""

    def test_menutupi_seluruh_placeholder_yang_sah(self):
        """Kalau daftar untuk manusia dan daftar untuk validator berbeda,
        layar menawarkan bagian yang ditolak saat disimpan — atau
        menyembunyikan bagian yang sebenarnya boleh dipakai."""
        assert {p["kunci"] for p in PLACEHOLDER_NOMOR} == _PLACEHOLDER_DIKENAL

    def test_tiap_entri_menjelaskan_dirinya(self):
        for ph in PLACEHOLDER_NOMOR:
            assert ph["label"].strip(), ph
            assert ph["arti"].strip(), ph
            assert ph["contoh"].strip(), ph

    def test_urutannya_mengikuti_susunan_peranri(self):
        """Menyisipkan chip berurutan harus langsung menghasilkan bentuk yang
        benar — kalau tidak, kemudahannya semu."""
        urut = [p["kunci"] for p in PLACEHOLDER_NOMOR]
        assert urut[:4] == ["kode_keamanan", "urut", "kode_klasifikasi", "kode_unit"]

    def test_ikut_terkirim_di_pengaturan(self, dbx):
        async def skenario():
            hasil = await _unwrap(rp.get_pengaturan_persuratan)(_user=USER)
            assert hasil["placeholder"] == PLACEHOLDER_NOMOR
        _jalan(skenario())


class TestPratinjauRancangan:
    def test_komposisi_mengembalikan_template_hasil_penyisipan(self, dbx):
        """Inilah yang membuat kolom Format Nomor berubah seketika."""
        async def skenario():
            hasil = await _pra(komposisi="klasifikasi_saja", tanggal_surat="2026-08-19")
            assert "{kode_klasifikasi}" in hasil["format_nomor"]
            assert "{kode_keamanan}" not in hasil["format_nomor"]
        _jalan(skenario())

    def test_template_rancangan_dipakai_apa_adanya(self, dbx):
        async def skenario():
            hasil = await _pra(format_nomor="{urut}/{tahun}",
                               tanggal_surat="2026-08-19")
            assert hasil["format_nomor"] == "{urut}/{tahun}"
            assert hasil["nomor"] == "001/2026", hasil["nomor"]
        _jalan(skenario())

    def test_komposisi_diterapkan_di_atas_rancangan(self, dbx):
        async def skenario():
            hasil = await _pra(format_nomor="{urut}/{bulan_romawi}/{tahun}",
                               komposisi="keamanan_saja", tanggal_surat="2026-08-19")
            assert hasil["format_nomor"] == "{kode_keamanan}-{urut}/{bulan_romawi}/{tahun}"
            assert hasil["nomor"].startswith("B-001/VIII/")
        _jalan(skenario())

    def test_tanpa_rancangan_memakai_setelan_tersimpan(self, dbx):
        async def skenario():
            hasil = await _pra(tanggal_surat="2026-08-19")
            assert hasil["format_nomor"] == FORMAT_NOMOR_DEFAULT
        _jalan(skenario())

    def test_pratinjau_tidak_menyimpan_apa_pun(self, dbx):
        """Ia hanya membaca — setelan tak boleh berubah karena seseorang
        mengetik di kolom Format Nomor."""
        async def skenario():
            await _pra(format_nomor="{urut}/{tahun}", komposisi="tanpa",
                       tanggal_surat="2026-08-19")
            tersimpan = await dbx.persuratan_settings.find_one({"type": "global"})
            assert tersimpan is None
            lagi = await _unwrap(rp.get_pengaturan_persuratan)(_user=USER)
            assert lagi["format_nomor"] == FORMAT_NOMOR_DEFAULT
        _jalan(skenario())

    def test_counter_tidak_naik(self, dbx):
        """Pratinjau dipanggil tiap ketikan — kalau ia memesan nomor, satu
        sesi mengetik menghabiskan puluhan nomor agenda."""
        async def skenario():
            a = await _pra(format_nomor="{urut}/{tahun}", tanggal_surat="2026-08-19")
            b = await _pra(format_nomor="{urut}/{tahun}", tanggal_surat="2026-08-19")
            assert a["urut_berikut"] == b["urut_berikut"] == 1
            assert await dbx.counters.count_documents({}) == 0
        _jalan(skenario())

    def test_contoh_nomor_ikut_kembali(self, dbx):
        async def skenario():
            hasil = await _pra(komposisi="keamanan_klasifikasi", kode_klasifikasi="PL.02",
                               kode_keamanan="T", tanggal_surat="2026-08-19")
            assert hasil["nomor"].startswith("T-001/PL.02/"), hasil["nomor"]
        _jalan(skenario())
