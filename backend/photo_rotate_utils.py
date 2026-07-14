"""Utilitas rotasi foto PERSISTEN (#2 permintaan lapangan).

Permintaan pengguna: memutar foto di lightbox harus mengubah gambar ASLI di
semua tempat (thumbnail, galeri, unduh, layar penuh) — bukan sekadar tampilan
sesaat. Endpoint putar-foto (routes/assets.py) memakai `rotate_jpeg_bytes` untuk
memutar byte JPEG lalu menyimpannya kembali ke GridFS + regen thumbnail.

`normalisasi_derajat` sengaja MURNI (tanpa PIL/IO) agar mudah diuji unit.
"""
import io
from PIL import Image as PILImage


def normalisasi_derajat(deg) -> int:
    """Bulatkan sudut (derajat) ke kelipatan 90 TERDEKAT, hasil di {0,90,180,270}.

    Aman untuk None / bukan-angka (→ 0) serta nilai negatif atau >360.
    Contoh: 89→90, 44→0, -90→270, 450→90.
    """
    try:
        d = float(deg)
    except (TypeError, ValueError):
        return 0
    return int(round(d / 90.0)) * 90 % 360


def rotate_jpeg_bytes(photo_bytes: bytes, degrees_cw, quality: int = 90) -> bytes:
    """Putar byte gambar `degrees_cw` derajat SEARAH jarum jam → kembalikan JPEG.

    `expand=True` agar bingkai mengikuti orientasi baru (tinggi↔lebar bertukar
    pada 90°/270°). Sudut dinormalisasi ke kelipatan 90; 0° hanya re-encode.
    RAISES bila `photo_bytes` bukan gambar valid (pemanggil menangani).
    """
    deg = normalisasi_derajat(degrees_cw)
    img = PILImage.open(io.BytesIO(photo_bytes))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    if deg:
        # PIL.rotate() BERLAWANAN jarum jam → sudut negatif = searah jarum jam.
        img = img.rotate(-deg, expand=True)
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=quality, optimize=True, progressive=True)
    return out.getvalue()
