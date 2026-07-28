#!/usr/bin/env python3
"""Verifikasi kompresi PDF ujung-ke-ujung — DIJALANKAN DI VPS.

KENAPA SKRIP INI ADA. Kompresi PDF adalah satu-satunya bagian aplikasi yang
kebenarannya TIDAK BISA dibuktikan di CI: kebijakan jaringan lingkungan build
menolak CONNECT ke seluruh host penyedia. Uji otomatis di
`tests/unit/test_kompresi_pdf_gambar.py` hanya bisa menjaga **bentuk
permintaan** yang kita kirim (lewat MockTransport), bukan bahwa iLovePDF
benar-benar menerimanya.

Sejarahnya membuktikan itu berbahaya: selama berbulan-bulan kode memanggil
host yang tidak ada, dan tak satu pun uji gagal karena tak satu pun uji
menyentuh jaringan. Skrip ini adalah penutup celah itu — dijalankan SEKALI
di VPS setelah kunci dipasang, dan setiap kali kunci berganti.

CARA PAKAI (di VPS, dari direktori backend):

    cd /path/ke/backend
    set -a; . ./.env; set +a          # muat kunci dari .env
    python3 ../scripts/verifikasi_kompresi_pdf.py

Skrip TIDAK PERNAH memuat kunci di dalam kodenya dan TIDAK PERNAH
mencetaknya. Ia hanya membaca `ILOVEAPI_PUBLIC_KEY` dan
`ILOVEAPI_SECRET_KEY` dari environment.

Keluar dengan kode 0 bila rantai hidup, 1 bila ada yang perlu dibetulkan.
"""
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


def _garis(judul):
    print(f"\n=== {judul} ===")


def _sensor(nilai: str) -> str:
    """Tampilkan kunci secukupnya untuk dikenali, tak cukup untuk dipakai."""
    if not nilai:
        return "(kosong)"
    return f"{nilai[:8]}…({len(nilai)} karakter)"


def buat_pdf_uji() -> bytes:
    """PDF ber-foto supaya kompresinya benar-benar punya sesuatu untuk dikerjakan."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from PIL import Image
    import random

    img = Image.new("RGB", (1600, 1200))
    piksel = img.load()
    for y in range(0, 1200, 4):
        for x in range(0, 1600, 4):
            w = (random.randint(0, 90) + x // 20, random.randint(0, 90) + y // 20, 128)
            for dy in range(4):
                for dx in range(4):
                    if x + dx < 1600 and y + dy < 1200:
                        piksel[x + dx, y + dy] = tuple(min(255, c) for c in w)
    g = io.BytesIO()
    img.save(g, "JPEG", quality=95)
    g.seek(0)

    b = io.BytesIO()
    c = canvas.Canvas(b, pagesize=A4)
    for hal in range(3):
        c.drawString(40, 800, f"Uji verifikasi kompresi — halaman {hal + 1}")
        c.drawImage(ImageReader(g), 40, 300, width=500, height=380)
        c.showPage()
    c.save()
    return b.getvalue()


def main() -> int:
    import asyncio

    gagal = []

    _garis("1. Kunci terbaca dari environment")
    pub = os.environ.get("ILOVEAPI_PUBLIC_KEY", "")
    sec = os.environ.get("ILOVEAPI_SECRET_KEY", "")
    print(f"  ILOVEAPI_PUBLIC_KEY = {_sensor(pub)}")
    print(f"  ILOVEAPI_SECRET_KEY = {_sensor(sec)}")
    if not pub:
        print("  ✗ public key kosong — kompresi awan tak akan pernah dicoba")
        gagal.append("public key kosong")
    if pub and not pub.startswith("project_public_"):
        print("  ! bentuk public key tak lazim (biasanya diawali project_public_)")
    if sec and not sec.startswith("secret_key_"):
        print("  ! bentuk secret key tak lazim (biasanya diawali secret_key_)")

    _garis("2. Resolusi DNS host penyedia")
    import socket
    for h in ("api.ilovepdf.com",):
        try:
            print(f"  ✓ {h} -> {socket.gethostbyname(h)}")
        except Exception as e:
            print(f"  ✗ {h} TIDAK teresolusi ({type(e).__name__})")
            gagal.append(f"DNS {h}")

    _garis("3. PDF uji")
    pdf = buat_pdf_uji()
    print(f"  dibuat {len(pdf) / 1024:.1f} KB, 3 halaman berisi foto")

    _garis("4. Kompresi LOKAL (pypdf) — harus jalan tanpa jaringan")
    import pdf_compress_utils as pcu
    lokal = pcu.kompres_pdf_lokal(pdf)
    if lokal:
        print(f"  ✓ {len(pdf) / 1024:.1f} KB -> {len(lokal) / 1024:.1f} KB "
              f"(hemat {pcu.persen_hemat(len(pdf), len(lokal))}%)")
    else:
        print("  ! tak menghemat (wajar bila PDF sudah optimal) — bukan kegagalan")

    _garis("5. Kompresi AWAN (iLovePDF) — inilah yang tak bisa diuji di CI")
    if not pub:
        print("  dilewati: kunci belum dipasang")
    else:
        import routes.pdf_compress as rp

        async def _coba():
            return await rp.compress_pdf_ilovepdf(pdf, "verifikasi.pdf")

        try:
            hasil, metode, alasan = asyncio.run(_coba())
        except Exception as e:
            hasil, metode, alasan = None, None, f"{type(e).__name__}: {e}"

        if hasil:
            print(f"  ✓ BERHASIL via {metode}: {len(pdf) / 1024:.1f} KB -> "
                  f"{len(hasil) / 1024:.1f} KB "
                  f"(hemat {pcu.persen_hemat(len(pdf), len(hasil))}%)")
            print(f"  ✓ hasil benar-benar PDF: {hasil[:4] == b'%PDF'}")
        else:
            print(f"  ✗ GAGAL: {alasan}")
            print("     Arti pesan yang lazim:")
            print("       'start gagal (401)'  -> kunci salah/dicabut, atau JWT")
            print("                               ditandatangani secret yang keliru")
            print("       'start gagal (429)'  -> kuota/kredit habis")
            print("       'tak terjangkau'     -> VPS tak bisa keluar ke internet")
            gagal.append(f"iLovePDF: {alasan}")

    _garis("HASIL")
    if gagal:
        print("  BELUM SIAP. Yang perlu dibetulkan:")
        for g in gagal:
            print(f"    - {g}")
        print("\n  Catatan: kompresi lokal tetap bekerja walau awan gagal, jadi")
        print("  dokumen TIDAK pernah gagal tersimpan — hanya kurang mengecil.")
        return 1
    print("  ✓ Rantai kompresi PDF hidup ujung-ke-ujung.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
