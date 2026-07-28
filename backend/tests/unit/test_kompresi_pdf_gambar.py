"""Uji kompresi PDF & gambar — kontrak yang TAK BISA diuji lewat jaringan.

Kebijakan jaringan CI menolak CONNECT ke SEMUA host penyedia (iLovePDF,
Tinify, Compresto, Uploadcare) dengan 403. Maka tak ada satu pun uji di sini
yang boleh berpura-pura membuktikan bahwa penyedia menerima permintaan kita.

Yang dijaga justru hal yang lebih tahan lama: **bentuk permintaan yang kita
kirim** dan **cara kita menafsirkan jawaban** — lewat `httpx.MockTransport`.
Itulah yang dulu salah dan tak ketahuan berbulan-bulan: host tak ada, tanpa
Authorization, `/v1/start` sebagai POST, dan buta terhadap TaskError.
"""
import io
import json

import httpx
import pytest
from PIL import Image

import pdf_compress_utils as pcu


# ── Fungsi murni ───────────────────────────────────────────────────────────

def test_tingkat_kompresi_dijepit_ke_nilai_sah():
    """Nilai asing dibetulkan diam-diam, BUKAN diteruskan.

    Meneruskannya berarti 400 dari iLovePDF — dan 400 itu datang SETELAH
    berkas terunggah, yaitu setelah kuota mulai terpakai.
    """
    assert pcu.tingkat_kompresi_sah("extreme") == "extreme"
    assert pcu.tingkat_kompresi_sah("LOW") == "low"
    for buruk in ("ngawur", "", None, 5, "maximum"):
        assert pcu.tingkat_kompresi_sah(buruk) == pcu.TINGKAT_KOMPRESI_BAWAAN


def test_proses_200_ber_taskerror_dianggap_GAGAL():
    """HTTP 200 tidak menjamin sukses — inilah kebutaan versi lama.

    Tanpa gerbang ini, berkas galat diunduh lalu disajikan sebagai hasil
    kompresi: dokumen bukti tergantikan sampah, sementara layar merayakan
    penghematan.
    """
    assert pcu.proses_berhasil({"status": "TaskSuccess"})[0] is True
    assert pcu.proses_berhasil({"status": "TaskError"})[0] is False
    assert pcu.proses_berhasil({"status": ""})[0] is False
    assert pcu.proses_berhasil({})[0] is False
    assert pcu.proses_berhasil("bukan dict")[0] is False


def test_keluaran_jamak_ditolak_karena_itu_ZIP_bukan_pdf():
    ok, sebab = pcu.proses_berhasil({"status": "TaskSuccess",
                                     "output_filenumber": 3})
    assert ok is False and "ZIP" in sebab


def test_layak_dipakai_menolak_yang_bukan_pdf_atau_lebih_besar():
    asli = b"%PDF-1.4" + b"x" * 1000
    assert pcu.layak_dipakai(asli, b"%PDF-1.4" + b"x" * 100) is True
    assert pcu.layak_dipakai(asli, b"<html>galat</html>") is False, "HTML lolos"
    assert pcu.layak_dipakai(asli, b"PK\x03\x04zip") is False, "ZIP lolos"
    assert pcu.layak_dipakai(asli, b"%PDF" + b"x" * 5000) is False, "lebih besar"
    assert pcu.layak_dipakai(asli, None) is False


def test_nama_berkas_tak_bisa_menyuntik_header():
    """Nama berkas dari unggahan masuk ke Content-Disposition."""
    for jahat in ('a"\r\nX-Jahat: 1', "a/../../etc/passwd", "a\nb"):
        bersih = pcu.nama_berkas_aman(jahat)
        assert "\r" not in bersih and "\n" not in bersih
        assert '"' not in bersih and "/" not in bersih


def test_token_ditandatangani_lokal_dan_memuat_public_key():
    """Secret key adalah kunci PENANDATANGAN, bukan kredensial yang dikirim."""
    import jwt
    t = pcu.token_ilovepdf("pub-abc", "rahasia-panjang-sekali-untuk-hs256")
    isi = jwt.decode(t, "rahasia-panjang-sekali-untuk-hs256", algorithms=["HS256"])
    assert isi["jti"] == "pub-abc"
    assert isi["exp"] > isi["iat"]
    # Ditandatangani secret: kunci lain harus GAGAL memverifikasi.
    with pytest.raises(Exception):
        jwt.decode(t, "kunci-lain-yang-juga-panjang-sekali", algorithms=["HS256"])


# ── Kontrak HTTP iLovePDF (mock transport) ─────────────────────────────────

def _pdf_kecil() -> bytes:
    from reportlab.pdfgen import canvas
    b = io.BytesIO()
    c = canvas.Canvas(b)
    c.drawString(50, 700, "BAST contoh")
    c.showPage()
    c.save()
    return b.getvalue()


class _Rekam:
    """Mock iLovePDF yang MEREKAM bentuk tiap permintaan."""

    def __init__(self, gagal_pada=None, status_proses="TaskSuccess"):
        self.jejak = []
        self.gagal_pada = gagal_pada
        self.status_proses = status_proses

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        self.jejak.append({
            "metode": request.method, "url": url,
            "auth": request.headers.get("authorization", ""),
        })
        if self.gagal_pada and self.gagal_pada in url:
            return httpx.Response(500)
        if url.endswith("/v1/start/compress"):
            return httpx.Response(200, json={"server": "api9g.ilovepdf.com",
                                             "task": "TUGAS1",
                                             "remaining_files": 240})
        if url.endswith("/v1/upload"):
            return httpx.Response(200, json={"server_filename": "abc.pdf"})
        if url.endswith("/v1/process"):
            return httpx.Response(200, json={"status": self.status_proses,
                                             "output_filenumber": 1})
        if "/v1/download/" in url:
            return httpx.Response(200, content=b"%PDF-1.4 kecil")
        return httpx.Response(404)


@pytest.fixture()
def rp(monkeypatch):
    import routes.pdf_compress as m
    monkeypatch.setattr(m, "ILOVEPDF_PUBLIC_KEY", "pub-uji", raising=False)
    monkeypatch.setattr(m, "ILOVEPDF_SECRET_KEY", "rahasia-uji-panjang-sekali", raising=False)

    async def _kuota_ada(_s):
        return True

    async def _naik(*a, **k):
        return None

    monkeypatch.setattr(m, "is_pdf_quota_available", _kuota_ada, raising=False)
    monkeypatch.setattr(m, "increment_pdf_quota", _naik, raising=False)
    return m


def _jalan(coro):
    import asyncio
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


def test_alur_ilovepdf_memakai_host_urutan_dan_bearer_yang_benar(rp):
    """Kontrak yang dulu SELURUHNYA salah, kini dikunci.

    Versi lama: host api.iloveapi.com (tak ada), `/v1/start` sebagai POST
    ber-body, dan TANPA satu pun header Authorization.
    """
    perekam = _Rekam()
    hasil, metode, alasan = _jalan(rp.compress_pdf_ilovepdf(
        b"%PDF-1.4" + b"x" * 3000, "kontrak.pdf",
        transport=httpx.MockTransport(perekam)))

    assert metode == "ilovepdf" and hasil and not alasan
    url = [j["url"] for j in perekam.jejak]
    # Host benar — bukan api.iloveapi.com.
    assert url[0] == "https://api.ilovepdf.com/v1/start/compress"
    assert perekam.jejak[0]["metode"] == "GET", "start harus GET, bukan POST"
    # Langkah 2-4 pindah ke server hasil /v1/start.
    assert url[1] == "https://api9g.ilovepdf.com/v1/upload"
    assert url[2] == "https://api9g.ilovepdf.com/v1/process"
    assert url[3] == "https://api9g.ilovepdf.com/v1/download/TUGAS1"
    # SEMUA langkah membawa Bearer.
    for j in perekam.jejak:
        assert j["auth"].startswith("Bearer "), f"tanpa Authorization: {j['url']}"


def test_taskerror_tak_pernah_jadi_hasil_kompresi(rp):
    perekam = _Rekam(status_proses="TaskError")
    hasil, metode, alasan = _jalan(rp.compress_pdf_ilovepdf(
        b"%PDF-1.4" + b"x" * 3000, "a.pdf",
        transport=httpx.MockTransport(perekam)))
    assert hasil is None and metode is None
    assert "TaskError" in alasan
    # Dan ia BERHENTI — tak lanjut mengunduh berkas galat.
    assert not any("/v1/download/" in j["url"] for j in perekam.jejak)


def test_kegagalan_selalu_memberi_ALASAN_bukan_diam(rp):
    """Kegagalan tanpa alasan adalah persis bagaimana host mati bertahan."""
    for gagal_di in ("/v1/start", "/v1/upload", "/v1/process"):
        hasil, _m, alasan = _jalan(rp.compress_pdf_ilovepdf(
            b"%PDF-1.4" + b"x" * 3000, "a.pdf",
            transport=httpx.MockTransport(_Rekam(gagal_pada=gagal_di))))
        assert hasil is None
        assert alasan, f"gagal di {gagal_di} tanpa alasan"


def test_tanpa_kunci_tak_menyentuh_jaringan_sama_sekali(rp, monkeypatch):
    monkeypatch.setattr(rp, "ILOVEPDF_PUBLIC_KEY", "", raising=False)
    perekam = _Rekam()
    hasil, _m, alasan = _jalan(rp.compress_pdf_ilovepdf(
        b"%PDF", "a.pdf", transport=httpx.MockTransport(perekam)))
    assert hasil is None and "belum dipasang" in alasan
    assert perekam.jejak == [], "menembak jaringan padahal kunci kosong"


# ── Kompresi lokal: jaring pengaman yang selalu ada ────────────────────────

def test_kompresi_lokal_tak_pernah_merusak_dokumen():
    from pypdf import PdfReader
    asli = _pdf_kecil()
    hasil = pcu.kompres_pdf_lokal(asli)
    if hasil:                     # PDF mungil bisa saja tak menghemat
        assert len(PdfReader(io.BytesIO(hasil)).pages) == 1


def test_kompresi_lokal_menolak_masukan_rusak_tanpa_meledak():
    for buruk in (b"", b"halo dunia", b"%PDF-1.4 rusak" * 50, b"\x00" * 100):
        assert pcu.kompres_pdf_lokal(buruk) is None


def test_pdf_valid_menyaring_sebelum_kuota_berbayar_terpakai():
    """Kuota iLovePDF terpakai di /process — berkas sampah pun memakan kredit."""
    assert pcu.pdf_valid(b"")[0] is False
    assert pcu.pdf_valid(b"bukan pdf")[0] is False
    assert pcu.pdf_valid(b"%PDF" + b"x" * (26 * 1024 * 1024))[0] is False
    assert pcu.pdf_valid(b"%PDF-1.4 isi")[0] is True


# ── Jalur GAMBAR: tiga kerusakan pada foto bukti ───────────────────────────

def test_orientasi_exif_diterapkan_bukan_dibuang():
    """Tanpa ini foto kamera HP tersimpan MIRING permanen — dan karena tag
    EXIF ikut hilang, tak ada lagi informasi untuk membetulkannya."""
    from routes.media import compress_with_pillow
    im = Image.new("RGB", (400, 200), (200, 50, 50))
    b = io.BytesIO()
    ex = Image.Exif()
    ex[274] = 6                                  # Orientation: putar 90°
    im.save(b, "JPEG", exif=ex)
    keluar = Image.open(io.BytesIO(compress_with_pillow(b.getvalue())))
    assert keluar.size == (200, 400), "foto tersimpan miring"


def test_png_transparan_tetap_png_dan_tetap_transparan():
    """Pindaian, tangkapan layar SIMAN, dan spesimen TTD potong."""
    from routes.media import compress_with_pillow
    p = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
    p.putpixel((10, 10), (255, 0, 0, 255))
    b = io.BytesIO()
    p.save(b, "PNG")
    keluar = Image.open(io.BytesIO(compress_with_pillow(b.getvalue())))
    assert keluar.mode in ("RGBA", "LA", "P"), "transparansi diratakan"


def test_gambar_raksasa_ditolak_sebelum_menghabiskan_memori():
    from routes.media import compress_with_pillow
    big = Image.new("RGB", (9000, 9000), (1, 2, 3))
    b = io.BytesIO()
    big.save(b, "JPEG", quality=20)
    with pytest.raises(Exception):
        compress_with_pillow(b.getvalue())


def test_jpeg_biasa_tetap_terkompresi():
    """Penjaga di atas tak boleh mematikan fungsi aslinya."""
    from routes.media import compress_with_pillow
    j = Image.new("RGB", (2000, 1500), (120, 130, 140))
    b = io.BytesIO()
    j.save(b, "JPEG", quality=98)
    hasil = compress_with_pillow(b.getvalue())
    assert 0 < len(hasil) < len(b.getvalue())
