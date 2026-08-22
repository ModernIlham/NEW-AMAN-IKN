"""Satu penanda tangan, BANYAK pembubuhan pada dokumen yang sama.

Permintaan pemilik: *"pastikan TTD elektronik dapat melakukan penandatanganan
lebih sesuai jumlah yang harus dia tandatangani — sebagai contoh BAST
operasional ini, di mana terdapat tanda tangan lagi di lembar berikutnya di
surat pernyataan."*

Memang begitu keadaannya sebelum ini: tiap penanda tangan hanya punya SATU
`posisi_ttd`. Sejak BAST membawa lampiran Surat Pernyataan Tanggung Jawab,
orang yang sama harus meneken dua kali — blok tanda tangan Berita Acara dan
lembar pernyataannya sendiri. Dengan satu posisi, lembar kedua terbit KOSONG:
dokumen resmi yang tampak lengkap padahal belum diteken, dan tak ada galat
apa pun yang memberitahunya.

Yang diuji di sini PDF yang jadi, bukan niat kodenya — jejak identitas
(nama + tanggal) digambar di samping tiap pembubuhan, jadi kehadiran nama pada
sebuah halaman adalah bukti tanda tangannya benar-benar membekas di sana.
"""
import asyncio
import io

import pytest

import routes.ttd as rt


def _jalan(coro):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _pdf(halaman=4) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for i in range(halaman):
        c.drawString(72, 720, f"Naskah halaman {i + 1}")
        c.showPage()
    c.save()
    return buf.getvalue()


def _png() -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGBA", (120, 40), (10, 10, 120, 255)).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture()
def sadapan(monkeypatch):
    async def _blob(fid):
        return _png()

    async def _status(nip):
        return "PNS"

    async def _verif(sr_id, kode_satker="", oleh=""):
        return f"https://aman.uji/v/{sr_id[:8]}"

    monkeypatch.setattr(rt, "get_document_from_gridfs", _blob)
    monkeypatch.setattr(rt, "_link_verifikasi_pendek", _verif)
    import shared_utils
    monkeypatch.setattr(shared_utils, "status_kepegawaian_by_nip", _status)


def _teks(data: bytes):
    pdfium = pytest.importorskip("pypdfium2")
    dok = pdfium.PdfDocument(io.BytesIO(data))
    try:
        return [p.get_textpage().get_text_range() for p in dok]
    finally:
        dok.close()


def _pos(halaman, x=0.1, y=0.2, lebar=0.25):
    return {"halaman": halaman, "x": x, "y": y, "lebar": lebar}


class TestPembersihDaftarPosisi:
    def test_bukan_daftar_jadi_kosong(self):
        for x in (None, {}, "1", 7):
            assert rt._posisi_bersih_banyak(x) == []

    def test_entri_tak_sah_DIBUANG_bukan_menggagalkan_semuanya(self):
        """Tanda tangannya sendiri sudah sah dan sudah digambar orangnya.
        Menolak semuanya karena satu entri rusak memaksa ia menggambar ulang
        pekerjaan yang benar."""
        hasil = rt._posisi_bersih_banyak(
            [_pos(1), {"halaman": "x"}, None, _pos(2)])
        assert [p["halaman"] for p in hasil] == [1, 2]

    def test_dibatasi_supaya_satu_kiriman_tak_memaksa_ribuan_overlay(self):
        banyak = [_pos(1) for _ in range(rt.MAKS_PEMBUBUHAN + 15)]
        assert len(rt._posisi_bersih_banyak(banyak)) == rt.MAKS_PEMBUBUHAN

    def test_halaman_dijepit_ke_jumlah_halaman_dokumen(self):
        hasil = rt._posisi_bersih_banyak([_pos(99)], maks_halaman=4)
        assert hasil[0]["halaman"] == 4

    def test_payload_kiriman_membawa_kolomnya(self):
        assert "posisi_lain" in rt.SpesimenIn.model_fields


class TestPembubuhanBanyakDiPdf:
    def _sr(self, utama, lain, nama="Sari Penanda"):
        return {"kode_satker": "111111",
                "signers": [{"nama": nama, "signature_file_id": "sig-1",
                             "signed_at": "2026-08-08T10:00:00",
                             "posisi_ttd": utama, "posisi_ttd_lain": lain}]}

    def test_tiga_pembubuhan_membekas_di_tiga_halaman(self, sadapan):
        """Inilah bentuk nyata permintaannya: Berita Acara di halaman 2, dua
        lembar Surat Pernyataan di halaman 3 dan 4."""
        out = _jalan(rt._bangun_pdf_ber_ttd(
            self._sr(_pos(2), [_pos(3), _pos(4)]), "sr-uji", _pdf()))
        hal = _teks(out.getvalue())
        assert len(hal) == 4
        assert "Sari Penanda" not in hal[0]
        for i in (1, 2, 3):
            assert "Sari Penanda" in hal[i], f"halaman {i + 1} tak berjejak"

    def test_tanpa_pembubuhan_tambahan_perilakunya_persis_seperti_dulu(self, sadapan):
        out = _jalan(rt._bangun_pdf_ber_ttd(
            self._sr(_pos(2), []), "sr-uji", _pdf()))
        hal = _teks(out.getvalue())
        assert "Sari Penanda" in hal[1]
        assert all("Sari Penanda" not in hal[i] for i in (0, 2))

    def test_kolom_lama_yang_belum_ada_tak_meledakkan_perakitan(self, sadapan):
        """Dokumen yang ditandatangani SEBELUM fitur ini tak punya
        `posisi_ttd_lain` sama sekali."""
        sr = {"kode_satker": "111111",
              "signers": [{"nama": "Budi Lama", "signature_file_id": "sig-1",
                           "signed_at": "2026-08-08T10:00:00",
                           "posisi_ttd": _pos(1)}]}
        hal = _teks(_jalan(rt._bangun_pdf_ber_ttd(sr, "sr-uji", _pdf())).getvalue())
        assert "Budi Lama" in hal[0]

    def test_slot_otomatis_TETAP_bekerja_bersama_pembubuhan_tambahan(self, sadapan):
        """Orang yang memakai slot otomatis di blok tanda tangan tetap boleh
        menambahkan pembubuhan di lembar pernyataannya."""
        sr = {"kode_satker": "111111",
              "signers": [{"nama": "Cici Otomatis", "signature_file_id": "sig-1",
                           "signed_at": "2026-08-08T10:00:00",
                           "nip": "197001011990031001",
                           "jabatan": "Kepala Sub Bagian",
                           "posisi_ttd_lain": [_pos(2)]}]}
        hal = _teks(_jalan(rt._bangun_pdf_ber_ttd(sr, "sr-uji", _pdf())).getvalue())
        assert "Cici Otomatis" in hal[-1]      # slot otomatis halaman terakhir
        assert "Cici Otomatis" in hal[1]       # pembubuhan tambahan halaman 2

    def test_halaman_di_luar_jangkauan_dijepit_bukan_menghilang(self, sadapan):
        """Dokumen bisa saja lebih pendek daripada saat posisinya dikirim
        (dokumen diganti). Menjatuhkan pembubuhannya berarti tanda tangan yang
        hilang tanpa jejak."""
        out = _jalan(rt._bangun_pdf_ber_ttd(
            self._sr(_pos(1), [_pos(99)]), "sr-uji", _pdf(halaman=2)))
        hal = _teks(out.getvalue())
        assert "Sari Penanda" in hal[0] and "Sari Penanda" in hal[1]

    def test_dua_orang_dengan_pembubuhan_ganda_tak_saling_menghapus(self, sadapan):
        sr = {"kode_satker": "111111",
              "signers": [
                  {"nama": "Sari Satu", "signature_file_id": "sig-1",
                   "signed_at": "2026-08-08T10:00:00",
                   "posisi_ttd": _pos(1, x=0.05),
                   "posisi_ttd_lain": [_pos(3, x=0.05)]},
                  {"nama": "Budi Dua", "signature_file_id": "sig-2",
                   "signed_at": "2026-08-08T11:00:00",
                   "posisi_ttd": _pos(1, x=0.55),
                   "posisi_ttd_lain": [_pos(3, x=0.55)]},
              ]}
        hal = _teks(_jalan(rt._bangun_pdf_ber_ttd(sr, "sr-uji", _pdf())).getvalue())
        for i in (0, 2):
            assert "Sari Satu" in hal[i] and "Budi Dua" in hal[i]
