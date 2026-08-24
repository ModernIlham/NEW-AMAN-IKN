"""Sifat urgensi adalah SUMBU TERSENDIRI, bukan bagian kode keamanan.

Permintaan pemilik, dengan contoh dari halaman Legend aplikasi lain: naskah
dinas perlu penanda Biasa / Segera / Sangat Segera.

Keduanya sering tertukar karena sama-sama terasa "sifat surat", padahal
menjawab pertanyaan yang berbeda:

  · kode keamanan  → SIAPA BOLEH MEMBACA   (Biasa/Terbatas/Rahasia/Sangat Rahasia)
  · sifat urgensi  → SEBERAPA CEPAT DITINDAKLANJUTI (Biasa/Segera/Sangat Segera)

Satu surat bisa Biasa sekaligus Sangat Segera. Menggabungkan keduanya jadi satu
daftar pilihan memaksa operator memilih salah satu — dan yang dikorbankan
biasanya urgensi, sebab kode keamanan ikut tercetak di nomor.

Perhatikan pula bahwa kata "Biasa" ada di KEDUA daftar dengan arti berbeda.
Itulah sebabnya keduanya tak boleh dijadikan satu enum.
"""
import asyncio

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.persuratan as rp
from persuratan_utils import (
    KODE_KEAMANAN, SIFAT_URGENSI, SIFAT_URGENSI_DEFAULT, baris_agenda_csv,
    validate_surat_keluar, validate_surat_masuk,
)

# Admin BER-SATKER. Registrasi persuratan kini menolak pemanggil tanpa
# satker (lihat satker_wajib.py): surat berstempel "" tampil di register
# SETIAP satker sekaligus menghabiskan nomor agenda mereka.
ADMIN = {"username": "admin", "role": "admin", "name": "Admin",
         "kode_satker": "527001"}


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
    monkeypatch.setattr(rp, "jadwalkan_sync", lambda *a, **k: None, raising=False)
    return fake


class TestSumbuTerpisah:
    def test_bukan_himpunan_yang_sama(self):
        assert set(SIFAT_URGENSI) != set(KODE_KEAMANAN)

    def test_kata_biasa_ada_di_keduanya_dengan_arti_berbeda(self):
        """Bukti paling gamblang bahwa keduanya tak boleh disatukan."""
        assert SIFAT_URGENSI["biasa"] == "Biasa"
        assert KODE_KEAMANAN["B"] == "Biasa"
        assert "biasa" not in KODE_KEAMANAN

    def test_tiga_tingkat_sesuai_contoh_pemilik(self):
        assert list(SIFAT_URGENSI) == ["biasa", "segera", "sangat_segera"]


class TestValidasi:
    def test_nilai_sah_diterima(self):
        for u in SIFAT_URGENSI:
            assert validate_surat_keluar({"perihal": "x", "sifat_urgensi": u}) == []

    def test_nilai_asing_ditolak(self):
        pesan = validate_surat_keluar({"perihal": "x", "sifat_urgensi": "kilat"})
        assert pesan and "Sifat urgensi" in pesan[0]

    def test_kosong_jatuh_ke_biasa_bukan_galat(self):
        """Surat lama & pemanggil yang belum diperbarui tak boleh ditolak."""
        assert validate_surat_keluar({"perihal": "x"}) == []
        assert validate_surat_keluar({"perihal": "x", "sifat_urgensi": ""}) == []

    def test_surat_masuk_juga_divalidasi(self):
        pesan = validate_surat_masuk({"nomor_surat": "1", "pengirim": "A",
                                      "perihal": "x", "sifat_urgensi": "kilat"})
        assert pesan and "Sifat urgensi" in pesan[0]

    def test_kode_keamanan_tidak_menerima_nilai_urgensi(self):
        """Penjaga silang: kalau suatu saat keduanya disatukan, uji ini
        memerah lebih dulu."""
        pesan = validate_surat_keluar({"perihal": "x", "kode_keamanan": "segera"})
        assert pesan and "Kode keamanan" in pesan[0]


class TestTersimpanPadaSurat:
    def test_surat_keluar_menyimpannya(self, dbx):
        async def skenario():
            rec = await _unwrap(rp.booking_surat_keluar)(
                rp.SuratKeluarIn(perihal="Undangan", sifat_urgensi="sangat_segera",
                                 tanggal_surat="2026-08-19"), user=ADMIN)
            assert rec["sifat_urgensi"] == "sangat_segera"
            # Kode keamanannya TIDAK ikut berubah — dua sumbu, dua nilai.
            assert rec["kode_keamanan"] == "B"
        _jalan(skenario())

    def test_surat_masuk_menyimpan_yang_ditulis_pengirim(self, dbx):
        async def skenario():
            rec = await _unwrap(rp.agenda_surat_masuk)(
                rp.SuratMasukIn(nomor_surat="S-9/2026", pengirim="KPKNL",
                                perihal="Rekon", sifat_urgensi="segera"),
                user=ADMIN)
            assert rec["sifat_urgensi"] == "segera"
        _jalan(skenario())

    def test_tanpa_disebut_tersimpan_sebagai_biasa(self, dbx):
        async def skenario():
            rec = await _unwrap(rp.booking_surat_keluar)(
                rp.SuratKeluarIn(perihal="Rutin", tanggal_surat="2026-08-19"),
                user=ADMIN)
            assert rec["sifat_urgensi"] == SIFAT_URGENSI_DEFAULT
        _jalan(skenario())

    def test_pilihan_tersedia_untuk_layar(self, dbx):
        async def skenario():
            ref = await _unwrap(rp.referensi_persuratan)(_user=ADMIN)
            kode = [u["kode"] for u in ref["sifat_urgensi"]]
            assert kode == list(SIFAT_URGENSI)
        _jalan(skenario())


class TestBukuAgenda:
    def test_kolom_sifat_urgensi_ada_dan_berlabel_manusia(self):
        rows = baris_agenda_csv([{
            "jenis": "keluar", "no_agenda": 1, "status": "disahkan",
            "nomor": "B-001/2026", "perihal": "x", "sifat_urgensi": "sangat_segera",
        }])
        kolom = {n: i for i, n in enumerate(rows[0])}
        assert "Sifat Urgensi" in kolom
        assert rows[1][kolom["Sifat Urgensi"]] == "Sangat Segera"

    def test_baris_lama_tanpa_urgensi_tampil_kosong(self):
        """Buku agenda tak boleh menyatakan sesuatu yang tak pernah dicatat."""
        rows = baris_agenda_csv([{
            "jenis": "masuk", "no_agenda": 1, "status": "diterima",
            "nomor": "S-1", "perihal": "x",
        }])
        kolom = {n: i for i, n in enumerate(rows[0])}
        assert rows[1][kolom["Sifat Urgensi"]] == ""
