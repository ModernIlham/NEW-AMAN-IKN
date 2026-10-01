"""Gerbang foto murni: gambar sintetis lokal, tanpa API, Mongo, atau foto asli."""
import io

import pytest
from PIL import Image, ImageDraw, ImageFile

import foto_kompresi as fk


def _bita(gambar, format="PNG", **opsi):
    buf = io.BytesIO()
    gambar.save(buf, format=format, **opsi)
    return buf.getvalue()


def _detail(ukuran=(256, 192)):
    gambar = Image.new("RGB", ukuran, "#d8dcdb")
    lukis = ImageDraw.Draw(gambar)
    for x in range(0, ukuran[0], 8):
        lukis.line((x, 0, x, ukuran[1]), fill=(x % 230, 35, 80), width=1)
    lukis.text((10, 10), "AMAN 123456 NUP 78", fill="black")
    lukis.rectangle((28, 55, 120, 110), outline="black", width=2)
    return gambar


def test_satu_persen_adalah_hemat_tambahan():
    assert fk.AMBANG_HEMAT_PERSEN == 1.0
    assert fk.hemat_persen(1000, 990) == 1.0
    assert fk.hemat_persen(1000, 995) == 0.5
    assert fk.hemat_persen(1000, 1100) == -10.0


@pytest.mark.parametrize("lama,baru", [(0, 1), (-1, 1), (None, 1), ("x", 1),
                                        (100, -1), (float("inf"), 1), (100, float("nan")),
                                        (1e-308, 1e308)])
def test_ukuran_tidak_sah_tidak_mengaku_hemat(lama, baru):
    assert fk.hemat_persen(lama, baru) == 0.0


@pytest.mark.parametrize("sumber_format", ["PNG", "JPEG", "WEBP", "BMP"])
def test_foto_utuh_dimensi_identik_diterima(sumber_format):
    sumber = _bita(_detail(), sumber_format)
    with Image.open(io.BytesIO(sumber)) as dekode:
        hasil = _bita(dekode, "WEBP", lossless=True)
    assert fk.verifikasi_foto(sumber, hasil)


def test_webp_lossy_bermutu_tinggi_tetap_diterima():
    # Bukan penjaga identik-byte: kompresi lossy ringan tetap boleh lewat.
    sumber = Image.new("RGB", (256, 192), (143, 175, 205))
    assert fk.verifikasi_foto(_bita(sumber), _bita(sumber, "WEBP", quality=90))


@pytest.mark.parametrize("hasil_format", ["JPEG", "PNG", "GIF"])
def test_format_hasil_bukan_webp_ditolak(hasil_format):
    gambar = _detail()
    assert not fk.verifikasi_foto(_bita(gambar), _bita(gambar, hasil_format))


@pytest.mark.parametrize("rusak", [b"", None, "bukan bytes", b"RIFFxxxxWEBP", b"sampah"])
def test_sumber_dan_hasil_rusak_ditolak(rusak):
    baik = _bita(_detail(), "WEBP", lossless=True)
    assert not fk.verifikasi_foto(rusak, baik)
    assert not fk.verifikasi_foto(baik, rusak)


def test_foto_terpotong_ditolak():
    sumber = _bita(_detail(), "JPEG")
    hasil = _bita(_detail(), "WEBP", lossless=True)
    assert not fk.verifikasi_foto(sumber[:len(sumber) // 2], hasil)
    assert not fk.verifikasi_foto(sumber, hasil[:-1])
    assert not fk.verifikasi_foto(sumber, hasil + b"sampah")


def test_dimensi_berubah_ditolak():
    gambar = _detail()
    assert not fk.verifikasi_foto(_bita(gambar), _bita(gambar.resize((128, 96)), "WEBP", lossless=True))


def test_alfa_harus_identik_meski_perubahannya_kecil():
    sumber = Image.new("RGBA", (32, 32), (50, 70, 90, 128))
    hasil = _bita(sumber, "WEBP", lossless=True, exact=True)
    assert fk.verifikasi_foto(_bita(sumber), hasil)
    diubah = sumber.copy()
    diubah.putpixel((12, 12), (50, 70, 90, 127))
    assert not fk.verifikasi_foto(_bita(sumber), _bita(diubah, "WEBP", lossless=True))
    assert not fk.verifikasi_foto(_bita(sumber), _bita(sumber.convert("RGB"), "WEBP", lossless=True))


def test_gambar_opak_tidak_boleh_menjadi_transparan():
    sumber = Image.new("RGB", (20, 20), (50, 70, 90))
    hasil = sumber.convert("RGBA")
    hasil.putpixel((1, 1), (50, 70, 90, 254))
    assert not fk.verifikasi_foto(_bita(sumber), _bita(hasil, "WEBP", lossless=True))


def test_transparansi_png_palet_dipertahankan():
    sumber = Image.new("P", (32, 32), 0)
    sumber.putpalette([255, 0, 0, 0, 120, 160] + [0] * 762)
    sumber.paste(1, (8, 8, 24, 24))
    sumber.info["transparency"] = bytes([0, 128])
    assert fk.verifikasi_foto(_bita(sumber), _bita(sumber.convert("RGBA"), "WEBP", lossless=True))


def test_rgb_piksel_tak_terlihat_tidak_menolak_hasil():
    sumber = Image.new("RGBA", (32, 32), (255, 0, 0, 0))
    hasil = Image.new("RGBA", (32, 32), (0, 255, 255, 0))
    assert fk.verifikasi_foto(_bita(sumber), _bita(hasil, "WEBP", lossless=True, exact=True))


@pytest.mark.parametrize("format", ["GIF", "WEBP", "PNG"])
def test_animasi_sumber_atau_hasil_ditolak(format):
    a = Image.new("RGB", (32, 32), "red")
    b = Image.new("RGB", (32, 32), "blue")
    animasi = _bita(a, format, save_all=True, append_images=[b], duration=100, loop=0)
    tunggal = _bita(a, "WEBP", lossless=True)
    assert not fk.verifikasi_foto(animasi, tunggal)
    if format == "WEBP":
        assert not fk.verifikasi_foto(tunggal, animasi)


def test_penurunan_kualitas_global_ditolak():
    sumber = Image.new("RGB", (256, 256), (100, 100, 100))
    hasil = Image.new("RGB", (256, 256), (118, 118, 118))
    # Tiap blok masih di bawah 24, tetapi rata-rata global melampaui 12.
    assert not fk.verifikasi_foto(_bita(sumber), _bita(hasil, "WEBP", lossless=True))


def test_kerusakan_lokal_tidak_hilang_di_rata_rata_global():
    sumber = Image.new("RGB", (1024, 1024), "white")
    hasil = sumber.copy()
    hasil.paste("black", (0, 0, 32, 32))
    # RMS global hanya ~8: kerusakan ini ditahan oleh batas blok, bukan global.
    assert not fk.verifikasi_foto(_bita(sumber), _bita(hasil, "WEBP", lossless=True))


def test_detail_dihapus_oleh_hasil_berkualitas_buruk_ditolak():
    sumber = _detail()
    hasil = Image.new("RGB", sumber.size, "#d8dcdb")
    assert not fk.verifikasi_foto(_bita(sumber), _bita(hasil, "WEBP", quality=1))


def test_blok_tepi_diperiksa_tanpa_mengubah_resolusi():
    sumber = _detail((257, 193))
    hasil = _bita(sumber, "WEBP", lossless=True)
    assert fk.verifikasi_foto(_bita(sumber), hasil)
    rusak = sumber.copy()
    rusak.paste("white", (256, 128, 257, 193))
    assert not fk.verifikasi_foto(_bita(sumber), _bita(rusak, "WEBP", lossless=True))


def test_gambar_presisi_16bit_tidak_ditipu_oleh_konversi_rgba():
    sumber = Image.new("I;16", (20, 20), 1000)
    hasil = sumber.convert("RGBA")
    # Walau cast keduanya putih, nilai 16-bit sumber tidak boleh dihilangkan.
    assert not fk.verifikasi_foto(_bita(sumber), _bita(hasil, "WEBP", lossless=True))


def test_batas_piksel_tidak_mendekode_foto_terlalu_besar(monkeypatch):
    gambar = _bita(_detail(), "WEBP", lossless=True)
    monkeypatch.setattr(fk, "MAKS_PIKSEL_FOTO", 100)
    assert not fk.verifikasi_foto(gambar, gambar)


def test_eksepsi_pillow_gagal_tertutup(monkeypatch):
    def gagal(*args, **kwargs):
        raise OSError("dekoder gagal")
    monkeypatch.setattr(fk.Image, "open", gagal)
    assert not fk.verifikasi_foto(b"foto", b"hasil")


@pytest.mark.parametrize("format", ["JPEG", "PNG", "WEBP", "AVIF"])
def test_preflight_sumber_format_foto_statis_diterima(format):
    assert fk.sumber_foto_valid(_bita(_detail(), format))


@pytest.mark.parametrize("format", ["BMP", "GIF", "TIFF"])
def test_preflight_format_di_luar_registry_ditolak(format):
    assert not fk.sumber_foto_valid(_bita(_detail(), format))


@pytest.mark.parametrize("format", ["GIF", "WEBP", "PNG"])
def test_preflight_animasi_ditolak_sebelum_memakai_kuota(format):
    a, b = Image.new("RGB", (20, 20), "red"), Image.new("RGB", (20, 20), "blue")
    data = _bita(a, format, save_all=True, append_images=[b], duration=100, loop=0)
    assert not fk.sumber_foto_valid(data)


def test_preflight_presisi_16bit_ditolak_sebelum_memakai_kuota():
    assert not fk.sumber_foto_valid(_bita(Image.new("I;16", (20, 20), 1000)))


def test_preflight_kosong_dan_truncated_gagal_tertutup():
    jpeg = _bita(_detail(), "JPEG")
    assert not fk.sumber_foto_valid(jpeg[:len(jpeg) // 2])
    assert not fk.sumber_foto_valid(b"")
    assert not fk.sumber_foto_valid(None)


@pytest.mark.parametrize("potongan", ["setengah", "eoi_hilang", "satu_bita_hilang"])
def test_jpeg_terpotong_ditolak_meski_pillow_global_permisif(monkeypatch, potongan):
    jpeg = _bita(_detail(), "JPEG")
    if potongan == "setengah":
        terpotong = jpeg[:len(jpeg) // 2]
    elif potongan == "eoi_hilang":
        terpotong = jpeg[:-2]
    else:
        terpotong = jpeg[:-1]
    with Image.open(io.BytesIO(jpeg)) as asal:
        hasil = _bita(asal, "WEBP", lossless=True)
    monkeypatch.setattr(ImageFile, "LOAD_TRUNCATED_IMAGES", True)
    assert not fk.sumber_foto_valid(terpotong)
    assert not fk.verifikasi_foto(terpotong, hasil)
    assert fk.sumber_foto_valid(jpeg)
    assert fk.verifikasi_foto(jpeg, hasil)
    # Helper tidak menyetel ulang global: thread milik modul lain tidak diubah.
    assert ImageFile.LOAD_TRUNCATED_IMAGES is True
