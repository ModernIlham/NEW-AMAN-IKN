"""Dua penjaga keamanan yang selama ini bekerja tanpa jaring pengaman.

`cek_magic_gambar` — satu-satunya pemeriksa ISI berkas unggahan di enam titik
(TTD, BAST, foto pegawai, lampiran pemanfaatan, dokumen aset). Ia menolak
berkas yang menyamar sebagai gambar lewat ekstensi. Bila ia diam-diam
melonggar, sebuah HTML/skrip berekstensi `.jpg` masuk ke GridFS lalu
disajikan kembali ke peramban pengguna lain.

`periksa_kekuatan_password` — gerbang tunggal kekuatan sandi pada pendaftaran
DAN reset sandi. Kembaliannya adalah PESAN GALAT, bukan boolean: string kosong
berarti LULUS. Membaliknya jadi boolean membuat semua sandi diterima, karena
pemanggil menulis `if _galat_pw:`.

Semua uji di sini murni: tanpa Mongo, tanpa jaringan, tanpa berkas sementara.
"""
import io
import os
import re

import pytest
from PIL import Image as PILImage

from auth_utils import periksa_kekuatan_password
from shared_utils import _MAGIC_GAMBAR, cek_magic_gambar

BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _gambar(fmt, size=(8, 8)):
    """Byte gambar SUNGGUHAN dari Pillow — bukan tiruan tanda tangan, supaya
    uji ini gagal bila daftar magic ternyata tak cocok dengan berkas nyata."""
    buf = io.BytesIO()
    PILImage.new("RGB", size, (12, 34, 56)).save(buf, format=fmt)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# cek_magic_gambar — menerima yang sah
# ---------------------------------------------------------------------------

class TestMenerimaGambarAsli:
    @pytest.mark.parametrize("fmt,ext", [
        ("JPEG", ".jpg"), ("JPEG", ".jpeg"), ("PNG", ".png"),
        ("WEBP", ".webp"), ("GIF", ".gif"),
    ])
    def test_gambar_pillow_lolos(self, fmt, ext):
        assert cek_magic_gambar(_gambar(fmt), ext) is True

    def test_ekstensi_huruf_besar_dinormalkan(self):
        """Nama berkas dari kamera iOS kerap `.JPG`; menolaknya = unggahan sah
        ditolak."""
        assert cek_magic_gambar(_gambar("JPEG"), ".JPG") is True
        assert cek_magic_gambar(_gambar("PNG"), ".PNG") is True

    def test_gif87a_dan_gif89a_sama_sama_sah(self):
        assert cek_magic_gambar(b"GIF87a" + b"\x00" * 20, ".gif") is True
        assert cek_magic_gambar(b"GIF89a" + b"\x00" * 20, ".gif") is True

    def test_byte_ekstra_setelah_tanda_tangan_tak_masalah(self):
        assert cek_magic_gambar(b"\xff\xd8\xff" + os.urandom(500), ".jpg") is True


# ---------------------------------------------------------------------------
# cek_magic_gambar — menolak yang menyamar
# ---------------------------------------------------------------------------

class TestMenolakPenyamaran:
    def test_png_berkedok_jpg_ditolak(self):
        """Inti fungsi ini: ekstensi berbohong, isi yang menentukan."""
        assert cek_magic_gambar(_gambar("PNG"), ".jpg") is False

    def test_jpeg_berkedok_png_ditolak(self):
        assert cek_magic_gambar(_gambar("JPEG"), ".png") is False

    def test_html_berkedok_jpg_ditolak(self):
        """Skenario nyata paling berbahaya: berkas HTML/skrip diunggah sebagai
        foto lalu disajikan balik ke peramban pengguna lain."""
        jahat = b"<html><script>alert(1)</script></html>"
        assert cek_magic_gambar(jahat, ".jpg") is False
        assert cek_magic_gambar(jahat, ".png") is False
        assert cek_magic_gambar(jahat, ".webp") is False

    def test_pdf_berkedok_gambar_ditolak(self):
        assert cek_magic_gambar(b"%PDF-1.7\n%\xe2\xe3", ".png") is False

    def test_zip_berkedok_gambar_ditolak(self):
        assert cek_magic_gambar(b"PK\x03\x04" + b"\x00" * 40, ".jpg") is False

    def test_berkas_kosong_ditolak(self):
        for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
            assert cek_magic_gambar(b"", ext) is False, ext

    def test_potongan_lebih_pendek_dari_tanda_tangan_ditolak(self):
        assert cek_magic_gambar(b"\xff\xd8", ".jpg") is False
        assert cek_magic_gambar(b"\x89PNG", ".png") is False

    def test_gif88a_yang_mirip_tetap_ditolak(self):
        assert cek_magic_gambar(b"GIF88a" + b"\x00" * 20, ".gif") is False


class TestWebpDuaLapis:
    """WebP dibungkus kontainer RIFF yang juga dipakai WAV/AVI. Memeriksa
    'RIFF' saja TIDAK cukup — berkas audio akan lolos sebagai gambar."""

    def test_riff_wave_bukan_webp(self):
        wav = b"RIFF" + b"\x24\x08\x00\x00" + b"WAVEfmt "
        assert cek_magic_gambar(wav, ".webp") is False

    def test_riff_avi_bukan_webp(self):
        avi = b"RIFF" + b"\x00\x00\x10\x00" + b"AVI LIST"
        assert cek_magic_gambar(avi, ".webp") is False

    def test_webp_asli_lolos(self):
        data = _gambar("WEBP")
        assert data[:4] == b"RIFF" and data[8:12] == b"WEBP"
        assert cek_magic_gambar(data, ".webp") is True

    def test_webp_tanpa_awalan_riff_ditolak(self):
        palsu = b"XXXX" + b"\x00\x00\x00\x00" + b"WEBPVP8 "
        assert cek_magic_gambar(palsu, ".webp") is False

    def test_riff_terpotong_sebelum_offset_delapan_ditolak(self):
        assert cek_magic_gambar(b"RIFF", ".webp") is False
        assert cek_magic_gambar(b"RIFF\x00\x00\x00\x00WEB", ".webp") is False


class TestKontrakLolosUntukEkstensiTakDikenal:
    """Ekstensi di luar daftar sengaja DILOLOSKAN — pemeriksaannya dilakukan
    terpisah oleh pemanggil (mis. `%PDF` untuk .pdf). Karena itu setiap
    pemanggil WAJIB menyaring ekstensi lebih dulu; uji terakhir kelas ini
    menjaga janji tersebut tetap ditepati."""

    def test_ekstensi_tak_dikenal_lolos(self):
        assert cek_magic_gambar(b"apa saja", ".pdf") is True
        assert cek_magic_gambar(b"apa saja", ".bmp") is True

    def test_ekstensi_kosong_atau_none_lolos(self):
        assert cek_magic_gambar(b"apa saja", "") is True
        assert cek_magic_gambar(b"apa saja", None) is True

    def test_pdf_tidak_ada_di_tabel_magic(self):
        assert ".pdf" not in _MAGIC_GAMBAR
        assert set(_MAGIC_GAMBAR) == {".jpg", ".jpeg", ".png", ".webp", ".gif"}

    @pytest.mark.parametrize("berkas", [
        "routes/assets.py", "routes/pemanfaatan.py",
    ])
    def test_pemanggil_pdf_punya_pemeriksa_sendiri(self, berkas):
        """`cek_magic_gambar` meloloskan .pdf; jalur yang menerima PDF harus
        memeriksa `%PDF` sendiri — kalau tidak, tak ada yang menjaganya."""
        with open(os.path.join(BACKEND, berkas), encoding="utf-8") as f:
            src = f.read()
        assert 'b"%PDF"' in src, berkas

    def test_semua_pemanggil_menyaring_ekstensi_lebih_dulu(self):
        """Meloloskan ekstensi tak dikenal hanya aman bila pemanggil sudah
        membatasi ekstensinya. Pemanggil baru yang mengoper ekstensi mentah
        akan mematikan penjaga ini tanpa error apa pun."""
        pola = re.compile(r"\.jpe?g|\.png|\.webp")
        for berkas in ("routes/ttd.py", "routes/bast.py", "routes/assets.py",
                       "routes/pemanfaatan.py", "routes/pegawai.py"):
            with open(os.path.join(BACKEND, berkas), encoding="utf-8") as f:
                src = f.read()
            assert "cek_magic_gambar" in src and pola.search(src), berkas


class TestKekokohanTipe:
    def test_data_bertipe_str_ditolak_bukan_meledak(self):
        """Perbandingan str vs bytes selalu False — penjaga tetap menutup."""
        assert cek_magic_gambar("\xff\xd8\xff bukan bytes", ".jpg") is False

    def test_bytearray_diperlakukan_sama_dengan_bytes(self):
        jpg = _gambar("JPEG")
        assert cek_magic_gambar(bytearray(jpg), ".jpg") is True
        assert cek_magic_gambar(bytearray(jpg), ".png") is False

    def test_selalu_mengembalikan_boolean(self):
        """Pemanggil menulis `if not cek_magic_gambar(...)`; kembalian yang
        'truthy tapi bukan bool' menyamarkan regresi."""
        for hasil in (cek_magic_gambar(_gambar("PNG"), ".png"),
                      cek_magic_gambar(b"", ".png"),
                      cek_magic_gambar(b"", ".pdf")):
            assert isinstance(hasil, bool)


# ---------------------------------------------------------------------------
# periksa_kekuatan_password
# ---------------------------------------------------------------------------

class TestKekuatanPassword:
    def test_sandi_memenuhi_syarat_mengembalikan_string_kosong(self):
        """KONTRAK: "" = lulus. Mengembalikan True di sini membuat pemanggil
        (`if _galat_pw: raise`) MENOLAK sandi yang benar; mengembalikan False
        untuk sandi lemah membuat semuanya lolos."""
        hasil = periksa_kekuatan_password("Rahasia1")
        assert hasil == ""
        assert isinstance(hasil, str)

    def test_delapan_karakter_pas_diterima(self):
        assert periksa_kekuatan_password("Abcdefg1") == ""

    def test_tujuh_karakter_ditolak(self):
        assert periksa_kekuatan_password("Abcdef1") == "Password minimal 8 karakter"

    @pytest.mark.parametrize("sandi", ["", "a", "Ab1", "Abcdef1"])
    def test_terlalu_pendek_selalu_pesan_panjang(self, sandi):
        assert periksa_kekuatan_password(sandi) == "Password minimal 8 karakter"

    def test_none_diperlakukan_sebagai_kosong(self):
        assert periksa_kekuatan_password(None) == "Password minimal 8 karakter"

    _PESAN_KOMPOSISI = "Password harus mengandung huruf besar, huruf kecil, dan angka"

    def test_tanpa_huruf_besar_ditolak(self):
        assert periksa_kekuatan_password("rahasia123") == self._PESAN_KOMPOSISI

    def test_tanpa_huruf_kecil_ditolak(self):
        assert periksa_kekuatan_password("RAHASIA123") == self._PESAN_KOMPOSISI

    def test_tanpa_angka_ditolak(self):
        assert periksa_kekuatan_password("RahasiaKu") == self._PESAN_KOMPOSISI

    def test_panjang_tapi_satu_kelas_saja_tetap_ditolak(self):
        """`aaaaaaaaaaaaaaaaaaaa` panjang namun tak punya keragaman apa pun."""
        assert periksa_kekuatan_password("a" * 40) == self._PESAN_KOMPOSISI

    def test_panjang_diperiksa_sebelum_komposisi(self):
        """Urutan pesan penting bagi pengguna: sandi 3 huruf lengkap kelasnya
        tetap harus diberi tahu soal panjang lebih dulu."""
        assert periksa_kekuatan_password("Ab1") == "Password minimal 8 karakter"

    def test_simbol_tidak_diwajibkan(self):
        """Kebijakan saat ini TIDAK menuntut simbol; menambahkannya diam-diam
        akan menolak sandi lama yang sah."""
        assert periksa_kekuatan_password("Rahasia1") == ""

    def test_simbol_boleh_ada(self):
        assert periksa_kekuatan_password("Rahasia1!@#") == ""

    def test_spasi_dihitung_sebagai_karakter(self):
        assert periksa_kekuatan_password("Rahasia 1") == ""

    def test_angka_dan_huruf_non_ascii(self):
        """Digit Arab-Hindi bukan `\\d` ASCII pada regex Python? Justru IYA —
        `\\d` cocok dengan digit Unicode. Uji ini merekam perilaku nyata agar
        perubahan flag regex tak lewat tanpa disadari."""
        assert periksa_kekuatan_password("Rahasia١") == ""

    def test_huruf_besar_kecil_non_latin_tidak_dianggap_kelas(self):
        """`[A-Z]`/`[a-z]` hanya Latin; sandi Sirilik murni tetap ditolak."""
        assert periksa_kekuatan_password("Пароль123") == \
            self._PESAN_KOMPOSISI


class TestGerbangSandiTerpasang:
    """Fungsi yang benar tapi tak dipanggil tidak menjaga apa pun."""

    def test_dipakai_di_pendaftaran_dan_reset(self):
        with open(os.path.join(BACKEND, "routes/auth.py"), encoding="utf-8") as f:
            src = f.read()
        assert src.count("periksa_kekuatan_password(") >= 2

    def test_hasilnya_benar_benar_menggagalkan_permintaan(self):
        """Memanggilnya lalu mengabaikan kembalian = gerbang hiasan."""
        with open(os.path.join(BACKEND, "routes/auth.py"), encoding="utf-8") as f:
            src = f.read()
        for var in ("_galat_pw", "_galat_baru"):
            assert re.search(rf"if {var}:\s*\n\s*raise HTTPException", src), var
