"""GERBANG MEDIA — satu aturan kompresi untuk satu aplikasi utuh.

Permintaan pemilik, apa adanya: *"pastikan kembali setiap gerbang agar mematuhi
aturan agar terkompresi terlebih dahulu sesuai jenjang yang ada apapun itu dan
di modul manapun dan di satker manapun … baik foto maupun pdf."*

Pemicunya: foto KAMERA yang disimpan dari HALAMAN EDIT aset tidak terkompres.
Audit atas 113 jalur tulis bita menemukan 25 jalur tanpa kompresi dan 7 jalur
yang justru TIDAK BOLEH dikompres.

Berkas ini menjaga dua hal yang berbeda:

  • **Perilaku gerbang** — aturannya benar (magic byte, alfa, PDF ber-TTD,
    idempoten, fail-open, hasil hanya dipakai bila lebih kecil).
  • **Jangkauan gerbang** — ANTI-PINTAS. Inilah yang membedakan "sudah
    dipanggil di satu tempat" dari "universal". Daftar jalur yang belum
    bermigrasi dikunci: ia boleh MENYUSUT, tak boleh bertambah. Modul
    kesembilan yang menyalin cetakan lampiran → CI merah, bukan diam-diam
    lolos seperti selama ini.
"""
import ast
import io
import os

import pytest
from PIL import Image as PILImage

import gerbang_media as gm

BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _gambar(fmt="JPEG", size=(400, 300), mode="RGB"):
    buf = io.BytesIO()
    img = PILImage.new(mode, size, (200, 120, 40) if mode == "RGB" else (200, 120, 40, 128))
    img.save(buf, format=fmt)
    return buf.getvalue()


def _pdf(halaman=1) -> bytes:
    from pypdf import PdfWriter
    w = PdfWriter()
    for _ in range(halaman):
        w.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Pengenalan jenis: MAGIC BYTE, bukan ekstensi
# ---------------------------------------------------------------------------

class TestJenisMedia:
    def test_pdf_dikenali(self):
        assert gm.jenis_media(b"%PDF-1.7\n%\xe2\xe3") == "pdf"

    @pytest.mark.parametrize("fmt", ["JPEG", "PNG", "GIF", "WEBP"])
    def test_gambar_dikenali(self, fmt):
        assert gm.jenis_media(_gambar(fmt)) == "gambar"

    def test_bukan_media_dilewati(self):
        assert gm.jenis_media(b"PK\x03\x04zip") == "lain"
        assert gm.jenis_media(b"<html>") == "lain"

    def test_kosong_aman(self):
        assert gm.jenis_media(b"") == "lain"
        assert gm.jenis_media(None) == "lain"

    def test_ekstensi_palsu_tak_menipu(self):
        """Beberapa modul HANYA memeriksa ekstensi. Gerbang tak boleh ikut
        tertipu: ZIP bernama .jpg tetap "lain" dan lewat tanpa disentuh."""
        assert gm.jenis_media(b"PK\x03\x04" + b"\x00" * 40) == "lain"


class TestAlfa:
    def test_rgba_terdeteksi(self):
        assert gm.punya_alfa(_gambar("PNG", mode="RGBA")) is True

    def test_jpeg_opak_tidak(self):
        assert gm.punya_alfa(_gambar("JPEG")) is False

    def test_sampah_tidak_meledak(self):
        assert gm.punya_alfa(b"bukan gambar") is False


class TestIdempoten:
    """Tanpa penanda, gerbang di lapisan tulis mengompres ULANG bita yang sudah
    lewat rantai di hulu — membakar kuota dua kali untuk berkas yang sama."""

    def test_penanda_gerbang_dihormati(self):
        assert gm.sudah_diolah({"kompresi": {"v": 1, "metode": "tinify"}}) is True

    def test_penanda_webp_dihormati(self):
        """Konverter WebP latar belakang SUDAH membakar kuota Tinify untuk
        blob itu; mengolahnya lagi memboroskan kuota tanpa manfaat."""
        assert gm.sudah_diolah({"webp": True}) is True

    def test_blob_baru_tidak_dilewati(self):
        assert gm.sudah_diolah({"content_type": "image/jpeg"}) is False
        assert gm.sudah_diolah({}) is False
        assert gm.sudah_diolah(None) is False


# ---------------------------------------------------------------------------
# Perilaku olahan
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestOlahGambar:
    async def test_gambar_kecil_tak_membakar_kuota(self):
        """Foto di bawah ambang cukup Pillow lokal. Membakar kuota berbayar
        untuk ikon dan avatar itu pemborosan yang tak terlihat."""
        kecil = _gambar("JPEG", size=(60, 60))
        assert len(kecil) < gm.AMBANG_JARINGAN
        hasil = await gm.olah_media(kecil)
        assert hasil.metode in ("pillow", "none")

    async def test_alfa_tak_pernah_jadi_jpeg(self):
        """Tiga dari empat mata rantai MEMAKSA JPEG. Spesimen tanda tangan dan
        logo instansi akan jadi kotak buram menimpa naskah dokumen resmi."""
        png = _gambar("PNG", mode="RGBA")
        hasil = await gm.olah_media(png, kelas="alfa")
        assert hasil.content_type != "image/jpeg"
        assert gm.punya_alfa(hasil.bita), "transparansi hilang"

    async def test_content_type_dari_bita_bukan_label(self):
        """Rantai lama selalu melabeli hasilnya image/jpeg walau cabang alfa
        mengembalikan PNG. Metadata yang berbohong membuat penyaji mengirim
        header salah dan peramban menampilkan berkas rusak."""
        hasil = await gm.olah_media(_gambar("PNG", mode="RGBA"), kelas="alfa")
        assert hasil.content_type == "image/png"

    async def test_hasil_tak_pernah_lebih_besar(self):
        """Blob lama dihapus setelah ditukar; hasil yang membengkak berarti
        kompresi yang sudah didapat musnah permanen."""
        for fmt in ("JPEG", "PNG"):
            hasil = await gm.olah_media(_gambar(fmt))
            assert hasil.ukuran_hasil <= hasil.ukuran_asli, fmt

    async def test_bukan_media_dilewati_utuh(self):
        zip_palsu = b"PK\x03\x04" + b"\x00" * 100
        hasil = await gm.olah_media(zip_palsu)
        assert hasil.bita == zip_palsu
        assert hasil.metode == "lewat"

    async def test_kelas_mentah_tak_menyentuh_apa_pun(self):
        """Restore backup WAJIB bita identik: koleksi lama sudah dihapus lebih
        dulu, jadi gagal di tengah = kehilangan permanen."""
        data = _gambar("JPEG")
        hasil = await gm.olah_media(data, kelas="mentah")
        assert hasil.bita == data
        assert hasil.metode == "lewat"

    async def test_kosong_aman(self):
        hasil = await gm.olah_media(b"")
        assert hasil.ukuran_asli == 0


@pytest.mark.asyncio
class TestOlahPdf:
    async def test_pdf_ber_tanda_tangan_tak_pernah_disentuh(self, monkeypatch):
        """PENJAGA PALING PENTING. Dulu ia hidup DI DALAM kompres_pdf_lokal
        sementara iLovePDF berjalan LEBIH DULU — dokumen ber-TTE bisa dikirim
        ke pihak ketiga dan tanda tangannya batal."""
        import pdf_compress_utils as pcu
        monkeypatch.setattr(pcu, "_pdf_bertanda_tangan", lambda p: True)

        dipanggil = []

        async def _jangan(*a, **k):
            dipanggil.append(1)
            return (b"x", "ilovepdf", "")

        import routes.pdf_compress as rpc
        monkeypatch.setattr(rpc, "compress_pdf_ilovepdf", _jangan)

        data = _pdf()
        hasil = await gm.olah_media(data)
        assert hasil.bita == data
        assert hasil.metode == "lewat"
        assert not dipanggil, "PDF ber-TTD dikirim ke penyedia luar"

    async def test_pdf_tak_terbaca_dianggap_terkunci(self):
        """Kebijakan modulnya sendiri: 'ragu = anggap bertanda tangan'."""
        rusak = b"%PDF-1.7\nrusak parah"
        hasil = await gm.olah_media(rusak)
        assert hasil.bita == rusak
        assert hasil.metode == "lewat"

    async def test_pdf_biasa_tetap_pdf(self):
        hasil = await gm.olah_media(_pdf())
        assert hasil.content_type == "application/pdf"
        assert hasil.bita.startswith(b"%PDF")


@pytest.mark.asyncio
class TestFailOpen:
    async def test_kegagalan_kompresi_tak_menggagalkan_unggahan(self, monkeypatch):
        """Foto bukti inventarisasi tak boleh hilang gara-gara kompresi gagal.
        Fail-CLOSED di sini berarti petugas lapangan kehilangan pekerjaannya."""
        import routes.media as rm

        def _meledak(*a, **k):
            raise RuntimeError("Pillow tumbang")

        monkeypatch.setattr(rm, "compress_with_pillow", _meledak)
        data = _gambar("JPEG", size=(60, 60))
        hasil = await gm.olah_media(data)
        assert hasil.bita == data, "bita asli harus tetap kembali"


# ---------------------------------------------------------------------------
# ANTI-PINTAS — inilah yang membuktikan "universal"
# ---------------------------------------------------------------------------

# Jalur yang menulis GridFS TANPA lewat gerbang. Dua kelompok:
#
#   (a) PENGECUALIAN TETAP — memang tidak boleh dikompres, dengan alasannya.
#   (b) BELUM BERMIGRASI — utang yang sudah dipetakan audit dan akan ditutup
#       PR berikutnya.
#
# Daftar ini boleh MENYUSUT, tak boleh BERTAMBAH. Modul kesembilan yang
# menyalin cetakan lampiran akan membuat CI merah — bukan lolos diam-diam
# seperti yang terjadi selama ini.
PENGECUALIAN_TETAP = {
    "routes/backup.py",        # restore wajib bita IDENTIK
    "routes/unduhan.py",       # artefak job ditulis berpotongan 64KB
    "jobs.py",                 # XLSX — bukan gambar/PDF, sudah ZIP-deflate
    "webp_converter.py",       # sudah WebP & sudah membakar kuota
    "routes/ttd.py",           # alfa load-bearing + bita di-sha256 sbg bukti
}

# Daftar ini WAJIB berisi hanya berkas yang BENAR-BENAR menulis GridFS hari
# ini. Mencantumkan berkas yang tak menulis apa pun akan diam-diam MENGIZINKAN
# berkas itu mulai menulis langsung nanti — daftar yang kelebihan isi membuat
# ujinya lebih lemah daripada yang terlihat.
# KOSONG — utangnya lunas. Keempat belas modul yang dulu di sini kini menulis
# lewat `tulis_media`. Himpunan ini sengaja DIPERTAHANKAN (bukan dihapus)
# supaya plafon di bawah tetap punya sesuatu untuk dijaga: tak ada modul yang
# boleh masuk lagi.
BELUM_BERMIGRASI = set()

_TULIS_GRIDFS = {"open_upload_stream_with_id", "open_upload_stream",
                 "upload_from_stream"}


def _berkas_penulis_gridfs():
    """Setiap berkas backend yang memanggil API tulis GridFS."""
    ketemu = set()
    for akar, _dirs, berkas in os.walk(BACKEND):
        if any(x in akar for x in ("/tests", "/venv", "__pycache__", "/scripts")):
            continue
        for nama in berkas:
            if not nama.endswith(".py"):
                continue
            path = os.path.join(akar, nama)
            rel = os.path.relpath(path, BACKEND)
            try:
                pohon = ast.parse(open(path, encoding="utf-8").read())
            except SyntaxError:
                continue
            for simpul in ast.walk(pohon):
                if (isinstance(simpul, ast.Call)
                        and isinstance(simpul.func, ast.Attribute)
                        and simpul.func.attr in _TULIS_GRIDFS):
                    ketemu.add(rel)
                    break
    return ketemu


class TestAntiPintas:
    def test_gerbang_sendiri_menulis_gridfs(self):
        assert "gerbang_media.py" in _berkas_penulis_gridfs()

    def test_tak_ada_penulis_gridfs_di_luar_daftar(self):
        """INTI. Berkas baru yang menulis GridFS langsung — atau modul yang
        menyalin cetakan lampiran — membuat uji ini merah. Tanpa uji ini,
        "universal" hanya berlaku sampai orang berikutnya menambah endpoint."""
        diketahui = {"gerbang_media.py"} | PENGECUALIAN_TETAP | BELUM_BERMIGRASI
        liar = _berkas_penulis_gridfs() - diketahui
        assert not liar, (
            "Berkas menulis GridFS tanpa lewat gerbang_media dan tanpa "
            f"terdaftar sebagai pengecualian: {sorted(liar)}")

    def test_daftar_tak_kelebihan_isi(self):
        """Daftar yang memuat berkas TAK MENULIS GridFS diam-diam mengizinkan
        berkas itu mulai menulis langsung nanti. Versi pertama uji ini
        kelebihan tujuh berkas — persis jenis kelemahan yang tak terlihat."""
        nyata = _berkas_penulis_gridfs()
        palsu = (PENGECUALIAN_TETAP | BELUM_BERMIGRASI) - nyata
        assert not palsu, f"terdaftar tapi tak menulis GridFS: {sorted(palsu)}"

    def test_daftar_belum_migrasi_hanya_boleh_menyusut(self):
        """Merekam utangnya secara TERUKUR. Plafonnya 14 pada PR gerbang,
        lalu 0 setelah sapuan — dan 0 adalah angka yang tak bisa turun lagi.
        Sejak titik ini, SATU modul yang menulis GridFS langsung membuat CI
        merah tanpa jalan keluar selain lewat gerbang atau menambah
        pengecualian tetap yang wajib beralasan tertulis."""
        assert len(BELUM_BERMIGRASI) == 0

    def test_pengecualian_tetap_punya_alasan_tertulis(self):
        """Pengecualian tanpa alasan berubah jadi tempat sampah."""
        src = open(__file__, encoding="utf-8").read()
        blok = src.split("PENGECUALIAN_TETAP = {", 1)[1].split("}", 1)[0]
        for berkas in PENGECUALIAN_TETAP:
            baris = [b for b in blok.splitlines() if berkas in b]
            assert baris and "#" in baris[0], f"{berkas} tanpa alasan"


class TestTitikCekikTerpasang:
    """Satu perubahan di `shared_utils` menutup enam jalur tulis foto —
    termasuk PATCH /assets/{id} yang dipakai halaman EDIT, jalur yang
    dilaporkan pemilik."""

    @staticmethod
    def _src():
        with open(os.path.join(BACKEND, "shared_utils.py"), encoding="utf-8") as f:
            return f.read()

    def test_store_photo_lewat_gerbang(self):
        fn = self._src().split("async def store_photo_to_gridfs", 1)[1].split("\nasync def ", 1)[0]
        assert "tulis_media(" in fn
        # Bita mentah tak boleh lagi ditulis langsung di sini.
        assert "grid_in.write(photo_bytes)" not in fn

    def test_store_document_lewat_gerbang(self):
        fn = self._src().split("async def store_document_to_gridfs", 1)[1].split("\nasync def ", 1)[0]
        assert "tulis_media(" in fn
        assert "grid_in.write(doc_bytes)" not in fn

    def test_content_type_tak_lagi_dikeraskan(self):
        """Dulu `metadata={"content_type": "image/jpeg"}` dikeraskan walau
        isinya PNG."""
        fn = self._src().split("async def store_photo_to_gridfs", 1)[1].split("\nasync def ", 1)[0]
        assert '"content_type": "image/jpeg", "size"' not in fn


class TestCacatRantaiTertutup:
    """Tiga cacat yang ditemukan audit DI DALAM rantai itu sendiri."""

    @staticmethod
    def _media():
        with open(os.path.join(BACKEND, "routes", "media.py"), encoding="utf-8") as f:
            return f.read()

    def test_pillow_tak_memblokir_event_loop(self):
        """Tinify sudah dilempar ke thread sejak lama; Pillow tidak — padahal
        ia CPU-bound dan gerbang memperbanyak panggilannya belasan kali."""
        fn = self._media().split("async def auto_compress_image", 1)[1]
        assert "asyncio.to_thread(compress_with_pillow" in fn
        assert "= compress_with_pillow(image_bytes)" not in fn

    def test_label_tipe_tak_dikeraskan_jpeg(self):
        fn = self._media().split("async def auto_compress_image", 1)[1]
        assert 'f"data:image/jpeg;base64' not in fn
        assert "_tipe_hasil(" in fn

    def test_sniff_dua_modul_sepakat(self):
        """`routes/media._tipe_hasil` dan `gerbang_media._sniff_gambar`
        menjawab pertanyaan yang sama; jawaban berbeda = metadata berbeda
        untuk berkas identik tergantung pintu masuknya."""
        from routes.media import _tipe_hasil
        for fmt, harap in (("JPEG", "image/jpeg"), ("PNG", "image/png"),
                           ("GIF", "image/gif"), ("WEBP", "image/webp")):
            data = _gambar(fmt)
            assert _tipe_hasil(data) == gm._sniff_gambar(data) == harap, fmt


class TestSamakanEkstensi:
    """Rantai gambar mengembalikan JPEG walau masukannya PNG. Modul lampiran
    menyimpan `filename` SENDIRI di dokumen Mongo — tanpa penyamaan ini
    pengguna mengunduh berkas bernama `.png` yang isinya JPEG."""

    def test_png_jadi_jpg_saat_isinya_jpeg(self):
        assert gm.samakan_ekstensi("bukti.png", "image/jpeg") == "bukti.jpg"

    def test_jpeg_dan_jpg_dianggap_sama(self):
        assert gm.samakan_ekstensi("a.jpeg", "image/jpeg") == "a.jpeg"
        assert gm.samakan_ekstensi("a.jpg", "image/jpeg") == "a.jpg"

    def test_pdf_tak_disentuh(self):
        assert gm.samakan_ekstensi("sk.pdf", "application/pdf") == "sk.pdf"

    def test_ekstensi_asing_dibiarkan(self):
        """Menebak lebih berbahaya daripada tidak menyentuh: berkas `.dwg`
        atau `.zip` bukan urusan gerbang dan namanya tak boleh dirombak."""
        assert gm.samakan_ekstensi("denah.dwg", "image/jpeg") == "denah.dwg"

    def test_tanpa_ekstensi_dibiarkan(self):
        assert gm.samakan_ekstensi("berkas", "image/jpeg") == "berkas"

    def test_tipe_kosong_dibiarkan(self):
        assert gm.samakan_ekstensi("a.png", "") == "a.png"

    def test_titik_di_nama_folder_tak_mengecoh(self):
        assert gm.samakan_ekstensi("v1.2/foto.png", "image/jpeg") == "v1.2/foto.jpg"


class TestSapuanModulTerpasang:
    """Empat belas modul yang dulu menulis GridFS langsung kini lewat gerbang.
    Uji ini membaca sumbernya, bukan mem-patch: mem-patch akan lulus walau
    pemanggilnya dihapus."""

    @staticmethod
    def _src(rel):
        with open(os.path.join(BACKEND, rel), encoding="utf-8") as f:
            return f.read()

    @pytest.mark.parametrize("rel", [
        "routes/pemanfaatan.py", "routes/pemindahtanganan.py",
        "routes/pemusnahan.py", "routes/pengadaan.py", "routes/pengamanan.py",
        "routes/penggunaan.py", "routes/penghapusan.py", "routes/wasdal.py",
        "routes/pengesahan.py", "routes/persediaan.py", "routes/bast.py",
        "routes/assets.py", "routes/spasial.py", "routes/pegawai.py",
        "routes/activities.py",
    ])
    def test_modul_memanggil_gerbang(self, rel):
        assert "tulis_media(" in self._src(rel), f"{rel} tak memanggil gerbang"

    def test_entri_lampiran_pakai_tipe_dari_gerbang(self):
        """Bila entri tetap memakai `_LAMPIRAN_MEDIA[ext]`, GridFS jujur tapi
        dokumen Mongo berbohong — dan yang dibaca layar adalah yang Mongo."""
        for rel in ("routes/pemanfaatan.py", "routes/wasdal.py",
                    "routes/pengadaan.py"):
            src = self._src(rel)
            blok = src.split('entri = {"file_id"', 1)[1][:200]
            assert '_meta["content_type"]' in blok, rel
            assert '_meta["filename"]' in blok, rel

    def test_overlay_denah_pakai_kelas_alfa(self):
        """Citra ini dihamparkan DI ATAS peta. Diratakan ke JPEG, alfanya jadi
        putih dan peta di bawahnya tertutup rapat."""
        src = self._src("routes/spasial.py")
        blok = src.split("FORMAT_OVERLAY[fmt]", 1)[1][:400]
        assert 'kelas="alfa"' in blok

    def test_activities_tak_punya_rantai_sendiri_lagi(self):
        """Rantai tangan sendiri di activities memanggil iLovePDF LANGSUNG —
        tanpa penjaga tanda tangan digital, karena `pdf_valid` hanya memeriksa
        ukuran dan magic byte. Sekaligus kompresi ganda sejak gerbang ada."""
        src = self._src("routes/activities.py")
        assert "compress_pdf_ilovepdf(pdf_bytes" not in src
        assert "kompres_pdf_lokal, pdf_bytes" not in src

    def test_tak_ada_lagi_metadata_size_dari_bita_masukan(self):
        """`len(pdf_bytes)` sebagai `size` berbohong sejak isinya dikompres."""
        src = self._src("routes/pengesahan.py")
        assert '"size": len(pdf_bytes)' not in src
