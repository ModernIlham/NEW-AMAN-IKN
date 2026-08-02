#!/usr/bin/env python3
"""Membuat tekstur permukaan cair panel kiri halaman masuk.

Komponen contoh `liquid1` memuat gambarnya dari blob penyimpanan pihak ketiga.
Aplikasi ini tidak boleh bergantung pada unduhan luar di layar MASUK (lihat
`frontend/src/components/ui/liquid-effect-animation.jsx`), jadi gambarnya
dibuat sendiri — dan dibuat lewat SKRIP, bukan ditempel sebagai berkas biner
tanpa asal-usul, supaya siapa pun bisa memeriksa dan membuat ulang isinya.

Motifnya sengaja meniru `login-pattern` di `index.css` (kubus isometrik slate)
agar cairan itu tampak memantulkan panel yang sama, bukan gambar asing.

Jalankan:  python3 scripts/buat_tekstur_login.py
Keluaran:  frontend/src/assets/tekstur-cair-login.jpg
"""
from __future__ import annotations

import math
import pathlib

from PIL import Image, ImageChops, ImageDraw, ImageFilter

SISI = 1024                      # tekstur persegi; dipetakan ke bidang cair
SEL_POLA_CSS = 40                # lebar satu sel `login-pattern` di index.css
LEBAR_PANEL_ACUAN = 720          # panel kiri pada layar 1440 (setengah lebar)
KELIR_DASAR = (15, 23, 42)       # slate-900 — sama dengan bg panel kiri
KELIR_KUBUS = (30, 41, 59)       # slate-800
KELIR_SISI = (51, 65, 85)        # slate-700
KELIR_KILAU = (45, 212, 191)     # teal-400 — aksen merek

KELUARAN = (pathlib.Path(__file__).resolve().parent.parent
            / "frontend" / "src" / "assets" / "tekstur-cair-login.jpg")


def gambar_kubus(d: ImageDraw.ImageDraw, cx: float, cy: float, r: float) -> None:
    """Satu kubus isometrik: tiga belah ketupat dengan terang berbeda."""
    # Titik heksagon (mulai -30°) = rangka kubus dilihat dari sudut isometrik.
    h = [(cx + r * math.cos(math.radians(60 * i - 30)),
          cy + r * math.sin(math.radians(60 * i - 30))) for i in range(6)]
    d.polygon([h[5], h[0], (cx, cy), h[4]], fill=KELIR_SISI)   # sisi atas
    d.polygon([h[4], (cx, cy), h[2], h[3]], fill=KELIR_KUBUS)  # sisi kiri
    d.polygon([(cx, cy), h[0], h[1], h[2]], fill=KELIR_DASAR)  # sisi kanan


def lapisan_kubus() -> Image.Image:
    """Hamparan kubus rapat; baris ganjil digeser setengah langkah.

    UKURAN KUBUS mengikuti `login-pattern` di `index.css` — sel 40 px pada
    panel selebar ±720 px, jadi sekitar 18 kubus melintang. Percobaan pertama
    memakai r=74 (hanya ±8 kubus melintang): tekstur 1024 px itu diregangkan
    ke lebar panel, sehingga kubusnya tampil ±2,5x lebih besar daripada pola
    aslinya dan latar terasa membesar. `LEBAR_PANEL_ACUAN` membuat kaitan itu
    tersurat — bukan angka ajaib yang ditebak ulang tiap kali.
    """
    img = Image.new("RGB", (SISI, SISI), KELIR_DASAR)
    d = ImageDraw.Draw(img)
    # Lebar sel pola CSS (40 px) diskalakan dari panel acuan ke lebar tekstur.
    lebar_sel = SEL_POLA_CSS * (SISI / LEBAR_PANEL_ACUAN)
    r = lebar_sel / math.sqrt(3)   # langkah_x = r*√3 = lebar satu kubus
    langkah_x = r * math.sqrt(3)
    langkah_y = r * 1.5
    baris, y = 0, -r
    while y < SISI + r:
        x = -r if baris % 2 == 0 else -r + langkah_x / 2
        while x < SISI + r:
            gambar_kubus(d, x, y, r)
            x += langkah_x
        y += langkah_y
        baris += 1
    return img


def lapisan_kilau() -> Image.Image:
    """Kilau teal lembut menyerong — memberi cairan sesuatu untuk dipantulkan
    selain abu-abu rata, dan menyambung dengan warna aksen antarmuka."""
    img = Image.new("RGB", (SISI, SISI), (0, 0, 0))
    d = ImageDraw.Draw(img)
    for i in range(6):
        t = i / 5
        jari = int(SISI * (0.18 + 0.10 * t))
        cx = int(SISI * (0.20 + 0.62 * t))
        cy = int(SISI * (0.70 + 0.18 * math.sin(t * math.pi)))
        kuat = 1 - 0.55 * t
        d.ellipse([cx - jari, cy - jari, cx + jari, cy + jari],
                  fill=tuple(int(c * 0.27 * kuat) for c in KELIR_KILAU))
    return img.filter(ImageFilter.GaussianBlur(SISI // 12))


def buat() -> Image.Image:
    # ADITIF, bukan campur: campur akan MENGGELAPKAN kubusnya (dicampur dengan
    # hitam di area tanpa kilau) alih-alih menyalakan warnanya.
    return ImageChops.add(lapisan_kubus(), lapisan_kilau())


if __name__ == "__main__":
    KELUARAN.parent.mkdir(parents=True, exist_ok=True)
    # JPEG kualitas 82: tekstur ini hanya dipantulkan permukaan bergelombang,
    # jadi detail per-piksel tak pernah terlihat — PNG hanya menggandakan
    # ukurannya tanpa satu pun perbedaan yang tampak.
    buat().save(KELUARAN, format="JPEG", quality=82, optimize=True)
    print(f"tertulis: {KELUARAN}  ({KELUARAN.stat().st_size // 1024} kB)")
