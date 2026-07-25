"""Uji thumbnail WebP: generasi baru (shared_utils) + re-encode migrasi
(webp_converter) — logika murni PIL, tanpa Mongo/jaringan."""
import base64
import io

from PIL import Image

import shared_utils as su
import webp_converter as wc


def _jpeg_data_uri(size=(256, 256), quality=95):
    """Data-URI JPEG dari gradien MULUS (frekuensi rendah, mirip foto) — WebP
    andal lebih kecil dari JPEG di sini (deterministik)."""
    w, h = size
    img = Image.new("RGB", size)
    px = img.load()
    for y in range(h):
        for x in range(w):
            px[x, y] = (x * 255 // max(1, w - 1),
                        y * 255 // max(1, h - 1),
                        (x + y) * 255 // max(1, w + h - 2))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def _decode(uri):
    return base64.b64decode(uri.split(",", 1)[1])


# ── Generasi thumbnail baru = WebP ──────────────────────────────────────────
def test_create_thumbnail_webp():
    out = su.create_thumbnail(_jpeg_data_uri())
    assert out.startswith("data:image/webp;base64,")
    img = Image.open(io.BytesIO(_decode(out)))
    img.load()
    assert (img.format or "").upper() == "WEBP"
    assert max(img.size) <= 100          # 100px cover


def test_create_gallery_thumbnail_webp():
    out = su.create_gallery_thumbnail(_jpeg_data_uri())
    assert out.startswith("data:image/webp;base64,")
    img = Image.open(io.BytesIO(_decode(out)))
    img.load()
    assert (img.format or "").upper() == "WEBP"
    assert max(img.size) <= 256


def test_create_thumbnail_input_buruk():
    assert su.create_thumbnail(None) is None
    assert su.create_thumbnail("bukan-data-uri") is None


# ── Re-encode migrasi (JPEG→WebP, hanya bila lebih kecil) ───────────────────
def test_reencode_uri_bukan_jpeg():
    assert wc._reencode_thumb_uri(None) is None
    assert wc._reencode_thumb_uri(123) is None
    assert wc._reencode_thumb_uri("data:image/webp;base64,AAAA") is None  # sudah webp
    assert wc._reencode_thumb_uri("data:image/png;base64,AAAA") is None


def test_reencode_uri_jpeg_ke_webp_lebih_kecil():
    # JPEG q95 256px besar → WebP q80 lebih kecil → dikonversi.
    src = _jpeg_data_uri(quality=95)
    out = wc._reencode_thumb_uri(src)
    assert out is not None and out.startswith("data:image/webp;base64,")
    assert len(_decode(out)) < len(_decode(src))         # tak pernah memperburuk
    img = Image.open(io.BytesIO(_decode(out)))
    img.load()
    assert (img.format or "").upper() == "WEBP"
    assert img.size == (256, 256)                        # dimensi dipertahankan


def test_reencode_uri_kontrak_umum():
    # Untuk JPEG apa pun: hasil None ATAU webp yang lebih kecil (tak memperburuk).
    src = _jpeg_data_uri(size=(48, 48), quality=60)
    out = wc._reencode_thumb_uri(src)
    if out is not None:
        assert out.startswith("data:image/webp;base64,")
        assert len(_decode(out)) < len(_decode(src))


# ── _reencode_thumbs (per aset) ─────────────────────────────────────────────
def test_reencode_thumbs_konversi():
    src = _jpeg_data_uri(quality=95)
    a = {"thumbnail": src, "gallery_thumbnail": src, "photo_thumbnails": [src, src]}
    up = wc._reencode_thumbs(a)
    assert "thumbnail" in up and up["thumbnail"].startswith("data:image/webp")
    assert "gallery_thumbnail" in up
    assert "photo_thumbnails" in up and len(up["photo_thumbnails"]) == 2
    assert all(t.startswith("data:image/webp") for t in up["photo_thumbnails"])


def test_reencode_thumbs_sudah_webp_kosong():
    webp = su.create_thumbnail(_jpeg_data_uri())      # sudah webp
    a = {"thumbnail": webp, "gallery_thumbnail": None, "photo_thumbnails": []}
    assert wc._reencode_thumbs(a) == {}               # tak ada JPEG → tak ada update


def test_reencode_thumbs_aset_kosong():
    assert wc._reencode_thumbs({}) == {}
    assert wc._reencode_thumbs({"photo_thumbnails": None}) == {}


# ── Konfigurasi migrasi ─────────────────────────────────────────────────────
def test_konfigurasi_migrasi():
    assert wc.THUMB_BATCH > 0
    assert 1 <= wc.THUMB_WEBP_Q <= 100
    assert wc._THUMB_CURSOR_ID == "webp_thumb_cursor"
