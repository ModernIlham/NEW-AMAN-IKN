"""Uji utilitas rotasi foto persisten (#2)."""
import io
from PIL import Image as PILImage
from photo_rotate_utils import normalisasi_derajat, rotate_jpeg_bytes


def test_normalisasi_kelipatan_90_pas():
    assert normalisasi_derajat(0) == 0
    assert normalisasi_derajat(90) == 90
    assert normalisasi_derajat(180) == 180
    assert normalisasi_derajat(270) == 270
    assert normalisasi_derajat(360) == 0
    assert normalisasi_derajat(450) == 90


def test_normalisasi_membulatkan_dan_negatif():
    assert normalisasi_derajat(89) == 90
    assert normalisasi_derajat(44) == 0
    assert normalisasi_derajat(46) == 90
    assert normalisasi_derajat(-90) == 270      # searah jarum jam 270°
    assert normalisasi_derajat(-180) == 180


def test_normalisasi_aman_non_angka():
    assert normalisasi_derajat(None) == 0
    assert normalisasi_derajat("x") == 0
    assert normalisasi_derajat("90") == 90       # string angka tetap diterima


def _img_bytes(w, h, color=(200, 30, 30)):
    """Buat JPEG di memori untuk pengujian (bukan data dummy DB — fixture uji)."""
    out = io.BytesIO()
    PILImage.new("RGB", (w, h), color).save(out, format="JPEG")
    return out.getvalue()


def test_rotate_90_menukar_dimensi():
    out = rotate_jpeg_bytes(_img_bytes(120, 60), 90)   # lanskap → potret
    im = PILImage.open(io.BytesIO(out))
    assert im.size == (60, 120)
    assert im.format == "JPEG"


def test_rotate_270_menukar_dimensi():
    out = rotate_jpeg_bytes(_img_bytes(120, 60), 270)
    assert PILImage.open(io.BytesIO(out)).size == (60, 120)


def test_rotate_180_dan_0_dimensi_tetap():
    assert PILImage.open(io.BytesIO(rotate_jpeg_bytes(_img_bytes(120, 60), 180))).size == (120, 60)
    assert PILImage.open(io.BytesIO(rotate_jpeg_bytes(_img_bytes(80, 40), 0))).size == (80, 40)


def test_rotate_byte_tak_valid_melempar():
    import pytest
    with pytest.raises(Exception):
        rotate_jpeg_bytes(b"bukan-gambar", 90)
