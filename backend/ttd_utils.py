"""Tanda Tangan Digital — LOGIKA MURNI (tanpa Mongo/IO).

Pemrosesan foto TTD di kertas → PNG TRANSPARAN (hanya goresan) memakai
Pillow + numpy yang SUDAH terpasang (tanpa rembg/opencv/model berat — riset
Jul 2026): luminance → normalisasi pencahayaan (kurangi latar via blur kuat)
→ ambang adaptif dengan zona transisi (tepi anti-alias, tidak gerigi) →
auto-crop. Cocok untuk foto TTD pada kertas polos/terang (kasus mayoritas).
"""
import io


def foto_ke_png_transparan(img_bytes, warna=(15, 23, 42), ambang=None,
                           kepekaan=22):
    """Foto TTD → PNG RGBA transparan (goresan `warna`, latar alpha 0).

    - `ambang`: 0-255; None = otomatis (Otsu sederhana dari histogram).
    - `kepekaan`: lebar zona transisi tepi (anti-alias); makin besar makin lembut.
    Mengembalikan bytes PNG. MURNI (hanya Pillow/numpy in-memory)."""
    from PIL import Image, ImageFilter
    import numpy as np

    im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    # Batasi dimensi (hemat memori & seragam) — sisi terpanjang <= 1600px.
    maxdim = max(im.size)
    if maxdim > 1600:
        skala = 1600.0 / maxdim
        im = im.resize((max(1, int(im.width * skala)),
                        max(1, int(im.height * skala))), Image.LANCZOS)

    arr = np.asarray(im, dtype=np.float32)
    lum = (0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2])

    # Normalisasi pencahayaan: buang gradasi/bayangan kertas dgn latar blur kuat.
    radius = max(8, int(min(im.size) * 0.05))
    latar = np.asarray(
        Image.fromarray(lum.astype(np.uint8)).filter(
            ImageFilter.GaussianBlur(radius)), dtype=np.float32)
    lum_norm = np.clip(lum - latar + 200.0, 0, 255)  # kertas ~200, tinta gelap

    # Ambang otomatis (Otsu) bila tak diberikan.
    t = float(ambang) if ambang is not None else _otsu(lum_norm)
    # Alpha: gelap (< t) = tinta (255), terang (> t) = transparan (0), dengan
    # zona transisi ±kepekaan agar tepi halus.
    k = max(1.0, float(kepekaan))
    alpha = np.clip((t + k - lum_norm) / (2.0 * k), 0.0, 1.0) * 255.0
    alpha = alpha.astype(np.uint8)

    h, w = alpha.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[:, :, 0] = warna[0]
    rgba[:, :, 1] = warna[1]
    rgba[:, :, 2] = warna[2]
    rgba[:, :, 3] = alpha
    out = Image.fromarray(rgba, "RGBA")

    # Auto-crop ke bounding box goresan (alpha>10) + padding kecil.
    ys, xs = np.where(alpha > 10)
    if len(xs) and len(ys):
        pad = 8
        x0, x1 = max(0, xs.min() - pad), min(w, xs.max() + pad + 1)
        y0, y1 = max(0, ys.min() - pad), min(h, ys.max() + pad + 1)
        out = out.crop((x0, y0, x1, y1))

    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()


def _otsu(lum):
    """Ambang Otsu dari array luminance (0-255). MURNI (numpy)."""
    import numpy as np
    hist, _ = np.histogram(lum.astype(np.uint8), bins=256, range=(0, 256))
    total = lum.size
    sum_all = float(np.dot(np.arange(256), hist))
    sum_b = 0.0
    w_b = 0.0
    var_max = -1.0
    thr = 180.0
    for i in range(256):
        w_b += hist[i]
        if w_b == 0:
            continue
        w_f = total - w_b
        if w_f == 0:
            break
        sum_b += i * hist[i]
        m_b = sum_b / w_b
        m_f = (sum_all - sum_b) / w_f
        var_between = w_b * w_f * (m_b - m_f) ** 2
        if var_between > var_max:
            var_max = var_between
            thr = float(i)
    return thr


def png_transparan_valid(data) -> bool:
    """True bila `data` adalah PNG ber-kanal alpha yang tak sepenuhnya kosong."""
    try:
        from PIL import Image
        import numpy as np
        im = Image.open(io.BytesIO(data))
        if im.format != "PNG":
            return False
        im = im.convert("RGBA")
        a = np.asarray(im)[:, :, 3]
        return bool((a > 10).any())
    except Exception:
        return False
