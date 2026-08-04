"""Uji pemendek tautan internal (/s/{kode}).

Mandat pemilik: "link yang dibagikan terlalu panjang". Tautan e-sign ±396
karakter, 315 di antaranya token tanda tangan. Dipendekkan DI RUMAH SENDIRI
(bukan TinyURL/PicSee) karena tautan itu KREDENSIAL: pemegangnya bisa
menandatangani dokumen BMN resmi, dan menitipkannya ke pemendek pihak ketiga
sama dengan menyimpan kredensial itu di server orang lain.

Yang dijaga uji ini: kodenya benar-benar acak & cukup panjang, tautan mati
saat dicabut/kedaluwarsa, pencabutan per-penanda-tangan TIDAK menyeret rekan
yang lain, dan kegagalan memendekkan TIDAK menggagalkan penerbitan tautan.
"""
import asyncio

import pytest
from mongomock_motor import AsyncMongoMockClient

import tautan_pendek_utils as tp


def _jalan(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    monkeypatch.setattr(tp, "db", fake, raising=False)
    return fake


# ── Panjang & keacakan kode ────────────────────────────────────────────────

def test_kode_panjang_10_dan_base62():
    kode = tp.kode_acak()
    assert len(kode) == tp.PANJANG_KODE == 10
    assert all(c.isalnum() and c.isascii() for c in kode)


def test_kode_tidak_berulang():
    """Kode berdiri MENGGANTIKAN tautan ber-kredensial — kalau bisa ditebak
    atau berulang, ia jadi pintu masuk ke dokumen orang lain."""
    kumpulan = {tp.kode_acak() for _ in range(500)}
    assert len(kumpulan) == 500


# ── Panjang tautan yang dihasilkan ────────────────────────────────────────

def test_tautan_jauh_lebih_pendek_dari_tautan_e_sign(monkeypatch):
    """Angka inilah yang dijanjikan ke pemilik: ±46 karakter, dari ±396."""
    monkeypatch.setenv("APP_PUBLIC_URL", "https://amanikn-inventarisasi.com")
    u = tp.url_pendek("K7m2QxV9pT")
    assert u == "https://amanikn-inventarisasi.com/s/K7m2QxV9pT"
    assert len(u) == 46


def test_tanpa_basis_url_jatuh_ke_relatif(monkeypatch):
    """Dev lokal tanpa APP_PUBLIC_URL/ALLOWED_ORIGINS: jangan mengarang host."""
    for v in ("APP_PUBLIC_URL", "ALLOWED_ORIGINS", "CORS_ORIGINS"):
        monkeypatch.delenv(v, raising=False)
    assert tp.url_pendek("abc") == "/s/abc"


def test_basis_url_abaikan_localhost(monkeypatch):
    monkeypatch.delenv("APP_PUBLIC_URL", raising=False)
    monkeypatch.setenv("ALLOWED_ORIGINS",
                       "http://localhost:3000,https://amanikn-inventarisasi.com")
    assert tp.basis_url_publik() == "https://amanikn-inventarisasi.com"


# ── Siklus hidup tautan ───────────────────────────────────────────────────

def test_buat_lalu_resolve(dbx):
    async def skenario():
        kode = await tp.buat_tautan_pendek("/ttd/xyz?token=abc", jenis="ttd",
                                           ref="sr-1", sub_ref="s1")
        return kode, await tp.resolve_tautan(kode)
    kode, tujuan = _jalan(skenario())
    assert len(kode) == 10
    assert tujuan == "/ttd/xyz?token=abc"


def test_kode_tak_dikenal_mengembalikan_none(dbx):
    assert _jalan(tp.resolve_tautan("TidakAda99")) is None


def test_kode_kosong_atau_kepanjangan_ditolak_tanpa_kueri(dbx):
    assert _jalan(tp.resolve_tautan("")) is None
    assert _jalan(tp.resolve_tautan("x" * 200)) is None


def test_tautan_kedaluwarsa_mati(dbx):
    async def skenario():
        kode = await tp.buat_tautan_pendek(
            "/ttd/xyz?token=abc", jenis="ttd", ref="sr-1",
            kedaluwarsa="2020-01-01T00:00:00+00:00")
        return await tp.resolve_tautan(kode)
    assert _jalan(skenario()) is None


def test_kedaluwarsa_tak_terbaca_tidak_mematikan_tautan(dbx):
    """Nilai rusak ≠ mati. Menganggapnya mati akan memutus tautan yang sah
    hanya karena satu field cacat."""
    async def skenario():
        kode = await tp.buat_tautan_pendek(
            "/ttd/xyz?token=abc", jenis="ttd", ref="sr-1",
            kedaluwarsa="bukan-tanggal")
        return await tp.resolve_tautan(kode)
    assert _jalan(skenario()) == "/ttd/xyz?token=abc"


def test_pencabutan_mematikan_tautan(dbx):
    async def skenario():
        kode = await tp.buat_tautan_pendek("/ttd/xyz?token=abc", jenis="ttd",
                                           ref="sr-1")
        await tp.cabut_tautan("ttd", "sr-1")
        return await tp.resolve_tautan(kode)
    assert _jalan(skenario()) is None


def test_cabut_satu_penanda_tangan_tak_menyeret_rekannya(dbx):
    """Menerbitkan ulang link SEORANG penanda tangan hanya boleh mematikan
    tautan orang itu — rekan yang belum meneken masih memegang tautan sah."""
    async def skenario():
        k1 = await tp.buat_tautan_pendek("/ttd/a?token=1", jenis="ttd",
                                         ref="sr-1", sub_ref="s1")
        k2 = await tp.buat_tautan_pendek("/ttd/a?token=2", jenis="ttd",
                                         ref="sr-1", sub_ref="s2")
        n = await tp.cabut_tautan("ttd", "sr-1", sub_ref="s1")
        return n, await tp.resolve_tautan(k1), await tp.resolve_tautan(k2)
    n, t1, t2 = _jalan(skenario())
    assert n == 1
    assert t1 is None                    # yang diterbitkan ulang → mati
    assert t2 == "/ttd/a?token=2"        # rekannya TETAP hidup


def test_cabut_tanpa_sub_ref_mematikan_seluruh_permintaan(dbx):
    """Permintaan TTD dibatalkan → semua tautannya mati sekaligus."""
    async def skenario():
        k1 = await tp.buat_tautan_pendek("/ttd/a?token=1", jenis="ttd",
                                         ref="sr-1", sub_ref="s1")
        k2 = await tp.buat_tautan_pendek("/ttd/a?token=2", jenis="ttd",
                                         ref="sr-1", sub_ref="s2")
        await tp.cabut_tautan("ttd", "sr-1")
        return await tp.resolve_tautan(k1), await tp.resolve_tautan(k2)
    assert _jalan(skenario()) == (None, None)


def test_cabut_tak_menyentuh_dokumen_lain(dbx):
    async def skenario():
        k = await tp.buat_tautan_pendek("/ttd/b?token=9", jenis="ttd",
                                        ref="sr-LAIN")
        await tp.cabut_tautan("ttd", "sr-1")
        return await tp.resolve_tautan(k)
    assert _jalan(skenario()) == "/ttd/b?token=9"


def test_pakai_ulang_memberi_kode_yang_sama(dbx):
    """QR verifikasi dirender ulang tiap unduhan. Tanpa pemakaian ulang, dua
    salinan dokumen yang sama membawa QR ber-alamat berbeda."""
    async def skenario():
        a = await tp.buat_tautan_pendek("/ttd/verifikasi/x", jenis="verifikasi",
                                        ref="sr-1", pakai_ulang=True)
        b = await tp.buat_tautan_pendek("/ttd/verifikasi/x", jenis="verifikasi",
                                        ref="sr-1", pakai_ulang=True)
        return a, b, await dbx.tautan_pendek.count_documents({})
    a, b, n = _jalan(skenario())
    assert a == b and n == 1


def test_tanpa_pakai_ulang_selalu_kode_baru(dbx):
    """Tautan e-sign TIDAK memakai ulang: tiap penerbitan harus token baru."""
    async def skenario():
        a = await tp.buat_tautan_pendek("/ttd/a?token=1", jenis="ttd", ref="sr-1")
        b = await tp.buat_tautan_pendek("/ttd/a?token=1", jenis="ttd", ref="sr-1")
        return a, b
    a, b = _jalan(skenario())
    assert a != b


def test_tujuan_kosong_ditolak(dbx):
    assert _jalan(tp.buat_tautan_pendek("   ", jenis="ttd", ref="sr-1")) == ""


def test_gagal_simpan_mengembalikan_kosong_bukan_melempar(dbx, monkeypatch):
    """Memendekkan itu kenyamanan. Kalau Mongo bermasalah, penerbitan
    permintaan TTD TETAP jalan — pemanggil jatuh ke tautan panjang."""
    class Meledak:
        async def insert_one(self, *a, **k):
            raise RuntimeError("mongo mati")

    class DbPalsu:
        tautan_pendek = Meledak()
    monkeypatch.setattr(tp, "db", DbPalsu(), raising=False)
    assert _jalan(tp.buat_tautan_pendek("/ttd/a", jenis="ttd", ref="sr-1")) == ""
