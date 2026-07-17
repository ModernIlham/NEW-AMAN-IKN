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


def test_otsu_di_rentang_valid():
    lum = np.asarray(Image.open(io.BytesIO(_foto_ttd())).convert("L"),
                     dtype=np.float32)
    t = _otsu(lum)
    assert 0 <= t <= 255
