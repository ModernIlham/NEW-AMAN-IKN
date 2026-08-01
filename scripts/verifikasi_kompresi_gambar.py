#!/usr/bin/env python3
"""Verifikasi layanan kompresi GAMBAR (Tinify / Compresto / Uploadcare) di VPS.

KENAPA SKRIP, BUKAN UJI OTOMATIS. Kunci API-nya hanya ada di `.env` server, dan
lingkungan pengembangan tak boleh (dan tak bisa) menghubungi layanan luar. Jadi
satu-satunya tempat kontrak API bisa DIBUKTIKAN adalah di VPS itu sendiri.

Skrip ini mengirim SATU gambar kecil buatan sendiri ke tiap layanan yang
kuncinya terpasang, lalu melaporkan apa yang sebenarnya terjadi — bukan sekadar
"gagal". Tidak ada kunci yang ditulis ke berkas mana pun; semuanya dibaca dari
lingkungan.

CARA PAKAI (di VPS):

    cd /path/ke/aplikasi
    set -a; . backend/.env; set +a
    python3 scripts/verifikasi_kompresi_gambar.py

Keluar dengan status 0 bila SEMUA layanan yang kuncinya terpasang berhasil,
1 bila ada yang gagal, dan 2 bila tak ada satu pun kunci terpasang.
"""
import io
import os
import sys

try:
    import httpx
except ImportError:
    print("httpx belum terpasang. Jalankan di lingkungan backend aplikasi.")
    sys.exit(2)


def gambar_uji() -> bytes:
    """Gambar JPEG kecil yang MASIH BISA dikompres.

    Sengaja bergradasi, bukan warna polos: berkas polos sudah minimal, sehingga
    layanan yang bekerja benar pun bisa mengembalikan berkas yang lebih besar —
    dan itu akan terbaca sebagai kegagalan palsu.
    """
    try:
        from PIL import Image
    except ImportError:
        print("Pillow belum terpasang.")
        sys.exit(2)
    img = Image.new("RGB", (600, 400))
    piksel = img.load()
    for y in range(400):
        for x in range(600):
            piksel[x, y] = ((x * 7) % 256, (y * 5) % 256, ((x + y) * 3) % 256)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def lapor(nama: str, ok: bool, pesan: str):
    tanda = "  OK  " if ok else " GAGAL"
    print(f"[{tanda}] {nama}: {pesan}")
    return ok


def cek_tinify(data: bytes) -> bool:
    kunci = os.environ.get("TINIFY_API_KEY", "")
    if not kunci:
        return lapor("Tinify", True, "dilewati — TINIFY_API_KEY tidak dipasang")
    try:
        import tinify
        tinify.key = kunci
        hasil = tinify.from_buffer(data).to_buffer()
        return lapor("Tinify", True,
                     f"{len(data)} → {len(hasil)} bytes "
                     f"(sisa kuota bulan ini: {tinify.compression_count})")
    except Exception as e:
        return lapor("Tinify", False, f"{type(e).__name__}: {e}")


def cek_compresto(data: bytes) -> bool:
    kunci = os.environ.get("COMPRESTO_API_KEY", "")
    if not kunci:
        return lapor("Compresto", True, "dilewati — COMPRESTO_API_KEY tidak dipasang")
    url = "https://api.compresto.app/v1/compress"
    try:
        with httpx.Client(timeout=45.0) as c:
            r = c.post(url, headers={"X-API-Key": kunci},
                       files={"image": ("uji.jpg", data, "image/jpeg")},
                       data={"quality": "80", "format": "jpeg"})
    except Exception as e:
        return lapor("Compresto", False,
                     f"tidak dapat menghubungi {url} — {type(e).__name__}: {e}")
    if r.status_code != 200:
        cuplik = (r.text or "")[:200].replace("\n", " ")
        return lapor("Compresto", False,
                     f"HTTP {r.status_code} dari {url} — {cuplik}\n"
                     f"          → periksa: alamat endpoint, nama header kunci "
                     f"(X-API-Key), dan nama field berkas ('image')")
    if not r.content:
        return lapor("Compresto", False, "HTTP 200 tetapi badan respons kosong")
    return lapor("Compresto", True, f"{len(data)} → {len(r.content)} bytes")


def cek_uploadcare(data: bytes) -> bool:
    kunci = os.environ.get("UPLOADCARE_PUBLIC_KEY", "")
    if not kunci:
        return lapor("Uploadcare", True, "dilewati — UPLOADCARE_PUBLIC_KEY tidak dipasang")
    try:
        with httpx.Client(timeout=45.0, follow_redirects=True) as c:
            r = c.post("https://upload.uploadcare.com/base/",
                       data={"UPLOADCARE_PUB_KEY": kunci, "UPLOADCARE_STORE": "0"},
                       files={"file": ("uji.jpg", data, "image/jpeg")})
            if r.status_code != 200:
                cuplik = (r.text or "")[:200].replace("\n", " ")
                return lapor("Uploadcare", False, f"unggah HTTP {r.status_code} — {cuplik}")
            berkas = (r.json() or {}).get("file")
            if not berkas:
                return lapor("Uploadcare", False,
                             "respons unggah tak memuat id berkas — kontrak API berubah?")
            cdn = f"https://ucarecdn.com/{berkas}/-/quality/smart/-/format/jpeg/"
            d = c.get(cdn)
            if d.status_code != 200:
                return lapor("Uploadcare", False, f"CDN HTTP {d.status_code} pada {cdn}")
            return lapor("Uploadcare", True, f"{len(data)} → {len(d.content)} bytes")
    except Exception as e:
        return lapor("Uploadcare", False, f"{type(e).__name__}: {e}")


def main():
    kunci_ada = [k for k in ("TINIFY_API_KEY", "COMPRESTO_API_KEY", "UPLOADCARE_PUBLIC_KEY")
                 if os.environ.get(k)]
    print("Verifikasi layanan kompresi gambar")
    print("Kunci terpasang:", ", ".join(kunci_ada) if kunci_ada else "(tidak ada)")
    if not kunci_ada:
        print("\nTak ada kunci terpasang. Isi di backend/.env lalu jalankan ulang:")
        print("  COMPRESTO_API_KEY=...")
        print("  UPLOADCARE_PUBLIC_KEY=...")
        print("  TINIFY_API_KEY=...")
        return 2
    print()

    data = gambar_uji()
    print(f"Gambar uji: {len(data)} bytes (600x400 JPEG bergradasi)\n")

    hasil = [cek_tinify(data), cek_compresto(data), cek_uploadcare(data)]
    print()
    if all(hasil):
        print("Semua layanan yang kuncinya terpasang MENJAWAB dengan benar.")
        return 0
    print("Ada layanan yang gagal — lihat baris GAGAL di atas.")
    print("Aplikasi tetap aman: rantai kompresi jatuh ke Pillow (lokal), jadi foto")
    print("tetap terkompres, hanya tidak seoptimal layanan luar.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
