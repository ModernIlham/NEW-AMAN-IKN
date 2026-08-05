"""Uji pemrosesan foto TTD → PNG transparan (Mandat-2, murni Pillow/numpy)."""
import io

from PIL import Image, ImageDraw
import numpy as np

from ttd_utils import _otsu, foto_ke_png_transparan, png_transparan_valid


def _foto_ttd(cahaya_miring=True):
    """Foto sintetis: kertas terang (gradasi cahaya opsional) + goresan gelap."""
    img = Image.new("RGB", (400, 200), (235, 232, 228))
    if cahaya_miring:
        px = np.asarray(img, dtype=np.float32)
        grad = np.linspace(-25, 20, 400)[None, :, None]
        img = Image.fromarray(np.clip(px + grad, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    d.line([(60, 120), (120, 60), (180, 140), (260, 70), (330, 130)],
           fill=(20, 20, 30), width=6)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return buf.getvalue()


def test_foto_ke_png_transparan():
    png = foto_ke_png_transparan(_foto_ttd())
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert png_transparan_valid(png)
    out = Image.open(io.BytesIO(png)).convert("RGBA")
    a = np.asarray(out)[:, :, 3]
    # Ter-crop lebih kecil dari kanvas asal
    assert out.width < 400 and out.height < 200
    # Sudut = latar transparan; ada goresan tinta
    assert a[0, 0] == 0
    assert (a > 200).sum() > 100


def test_png_transparan_valid_menolak_kosong():
    kosong = Image.new("RGBA", (50, 50), (0, 0, 0, 0))
    buf = io.BytesIO()
    kosong.save(buf, "PNG")
    assert png_transparan_valid(buf.getvalue()) is False
    # JPEG (bukan PNG) ditolak
    assert png_transparan_valid(_foto_ttd()) is False


def _png_transparan(tinta=(20, 20, 30, 255)):
    """PNG berlatar TRANSPARAN + goresan — bentuk berkas yang diunggah pemilik.

    Ini bukan foto kertas: hasil hapus-BG aplikasi lain, atau TTD yang pernah
    diproses di sini lalu diunggah ulang.
    """
    im = Image.new("RGBA", (400, 200), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.line([(60, 120), (120, 60), (180, 140), (260, 70), (330, 130)],
           fill=tinta, width=6)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def _alpha(png):
    return np.asarray(Image.open(io.BytesIO(png)).convert("RGBA"))[:, :, 3]


class TestSumberSudahTransparan:
    """Laporan pemilik: unggah berkas .png → yang muncul kotak gelap.

    Akarnya `convert("RGB")`, yang membuang alpha dengan mengomposit ke HITAM.
    Latar transparan jadi hitam pekat, lalu pipeline "gelap = tinta" mencap
    SELURUH bekas latar sebagai tinta. Hasil nyatanya bahkan bukan kotak pekat
    melainkan alpha 127 RATA — nol piksel tinta sungguhan — dan tetap lolos
    `png_transparan_valid` (127 > 10), jadi gagalnya senyap.
    """
    def test_goresan_bertahan_bukan_jadi_bidang_rata(self):
        a = _alpha(foto_ke_png_transparan(_png_transparan()))
        pekat = (a > 200).sum()
        assert pekat > 100, "goresan hilang — tak ada tinta pekat sama sekali"
        # Sebagian besar bidang HARUS transparan; dulu 0% pekat & 100% ber-alpha 127.
        assert (a < 10).sum() > a.size * 0.5

    def test_latar_transparan_tak_berubah_jadi_tinta(self):
        a = _alpha(foto_ke_png_transparan(_png_transparan()))
        assert a[0, 0] == 0

    def test_tak_ada_alpha_rata_separuh(self):
        """Gejala persisnya: satu nilai alpha untuk hampir seluruh piksel."""
        a = _alpha(foto_ke_png_transparan(_png_transparan()))
        terbanyak = np.bincount(a.ravel(), minlength=256).max()
        assert terbanyak < a.size * 0.95 or a.ravel()[np.argmax(
            np.bincount(a.ravel(), minlength=256))] == 0
        assert (np.abs(a.astype(int) - 127) < 5).sum() < a.size * 0.5

    def test_ter_crop_ke_goresan_bukan_sebesar_kanvas(self):
        """Dulu keluarannya 400x200 penuh karena 'tinta' memenuhi bidang."""
        out = Image.open(io.BytesIO(foto_ke_png_transparan(_png_transparan())))
        assert out.width < 400 and out.height < 200

    def test_tinta_TERANG_di_latar_transparan_tak_lenyap(self):
        """Jalur luminance menganggap terang = kertas, sehingga TTD putih di
        latar transparan akan hilang seluruhnya. Alpha sumber tak peduli warna."""
        a = _alpha(foto_ke_png_transparan(_png_transparan(tinta=(245, 245, 250, 255))))
        assert (a > 200).sum() > 100

    def test_hasilnya_setara_dengan_foto_kertas_yang_sama(self):
        """Goresan yang sama, dua bentuk berkas → luas tinta sebanding."""
        a_png = _alpha(foto_ke_png_transparan(_png_transparan()))
        a_foto = _alpha(foto_ke_png_transparan(_foto_ttd(cahaya_miring=False)))
        r_png = (a_png > 200).sum() / a_png.size
        r_foto = (a_foto > 200).sum() / a_foto.size
        assert abs(r_png - r_foto) < 0.03

    def test_png_buram_penuh_tetap_lewat_jalur_foto(self):
        """PNG tanpa transparansi (mis. tangkapan layar) tak boleh berubah
        jalur — alpha-nya 255 semua, bukan topeng goresan."""
        # Goresan sama dengan `_foto_ttd`: garis lurus tunggal terlalu tipis
        # untuk jalur luminance (radius blur latar menelannya) — itu sifat lama
        # yang tak disentuh perubahan ini, bukan yang sedang diuji di sini.
        im = Image.new("RGBA", (400, 200), (235, 232, 228, 255))
        d = ImageDraw.Draw(im)
        d.line([(60, 120), (120, 60), (180, 140), (260, 70), (330, 130)],
               fill=(20, 20, 30, 255), width=6)
        buf = io.BytesIO()
        im.save(buf, "PNG")
        a = _alpha(foto_ke_png_transparan(buf.getvalue()))
        assert (a > 200).sum() > 100
        assert a[0, 0] == 0


def test_otsu_di_rentang_valid():
    lum = np.asarray(Image.open(io.BytesIO(_foto_ttd())).convert("L"),
                     dtype=np.float32)
    t = _otsu(lum)
    assert 0 <= t <= 255
