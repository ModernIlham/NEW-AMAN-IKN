"""Buat panduan cetak ilustratif dari renderer asli, tanpa DB atau data pegawai."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from stiker_render import gambar_stiker
from stiker_utils import (FONT_STIKER_BIASA, FONT_STIKER_TEBAL,
                          KERTAS_STIKER_MM, TARGET_STIKER, grid_optimal,
                          spesifikasi_tipografi)


def buat_contoh(tujuan):
    """Dua halaman A4, masing-masing memperlihatkan label grid A4/A3 skala 1:1."""
    tujuan = Path(tujuan)
    tujuan.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(tujuan), pagesize=A4)
    c.setTitle("AMAN - Panduan tipografi stiker (contoh, bukan data aset)")
    c.setAuthor("AMAN - Panduan aplikasi")
    aset = {"asset_code": "3050102001", "NUP": "7", "asset_name": "Contoh Meja Kerja",
            "_subsub": "Meja Kerja", "kode_register": "CONTOH-BUKAN-ASET"}
    kop = {"header_stiker": "STIKER CONTOH", "_baris2_stiker": "DATA ILUSTRASI"}
    tinta = colors.HexColor("#123B39")

    def teks(x, atas, isi, pt=9, tebal=False, warna=colors.black):
        c.setFillColor(warna)
        c.setFont(FONT_STIKER_TEBAL if tebal else FONT_STIKER_BIASA, pt)
        c.drawString(x * mm, A4[1] - atas * mm, isi)

    for nomor, kertas in enumerate(KERTAS_STIKER_MM, 1):
        spec = spesifikasi_tipografi(kertas)
        teks(15, 19, "AMAN / PANDUAN CETAK", 9, True, tinta)
        teks(15, 30, f"Tipografi stiker - grid {kertas}", 20, True, tinta)
        teks(15, 39, "DATA ILUSTRASI - BUKAN ASET NYATA DAN BUKAN UNTUK DITEMPEL", 8, True)
        teks(15, 47, f"Halaman panduan: A4. Contoh label mengikuti grid cetak {kertas}, ukuran aktual 1:1.", 9)
        teks(15, 53, "Empat bagian tebal: Helvetica-Bold. Keterangan: Helvetica biasa.", 9)

        for u, atas in zip(spec["ukuran"], (66, 128, 177)):
            target = TARGET_STIKER[u["kode"]]
            _, _, w, h = grid_optimal(*KERTAS_STIKER_MM[kertas], target["w"], target["h"])
            dimensi = f"{w:.2f} x {h:.2f} mm".replace(".", ",")
            teks(15, atas, f"{u['nama']} / {dimensi}", 10, True, tinta)
            c.saveState()
            c.setFillColor(colors.black)
            c.setStrokeColor(colors.black)
            gambar_stiker(c, 15 * mm, A4[1] - (atas + 4 + h) * mm,
                          w * mm, h * mm, u["kode"], aset, kop, None, mm)
            c.restoreState()
            teks(121, atas, "BAGIAN", 8, True, tinta)
            teks(181, atas, "PT*", 8, True, tinta)
            for i, peran in enumerate(spec["peran"], 1):
                y = atas + 5 * i
                teks(121, y, peran["nama"], 8, peran["tebal"])
                angka = f"{u['font_pt'][peran['kode']]:.2f}".replace(".", ",")
                teks(181, y, angka, 8, peran["tebal"])

        teks(15, 225, "* Ukuran dasar sebelum penyesuaian teks panjang.", 9, True)
        teks(15, 232, "Judul/kode dapat mengecil agar muat. Nama barang paling banyak tiga baris, lalu '...'.", 9)
        teks(15, 239, "Cetak 100% / Ukuran aktual; jangan pilih Sesuaikan halaman. Periksa garis ukur di bawah.", 9)
        teks(15, 246, "Helvetica adalah font standar PDF; ketajaman cetak tetap perlu diuji pada printer dan bahan Anda.", 9)
        c.setStrokeColor(tinta)
        c.setLineWidth(0.7)
        y = A4[1] - 258 * mm
        c.line(15 * mm, y, 65 * mm, y)
        for x in range(15, 66, 10):
            c.line(x * mm, y - 1.5 * mm, x * mm, y + 1.5 * mm)
        teks(15, 265, "Garis uji 50 mm", 8, False, tinta)
        teks(15, 281, "Sumber: perhitungan dan renderer stiker AMAN. QR pada contoh hanya memuat penanda ilustrasi.", 8)
        teks(187, 288, f"{nomor} / 2", 8)
        c.showPage()
    c.save()
    return tujuan


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="output/pdf/contoh-tipografi-stiker.pdf")
    print(buat_contoh(parser.parse_args().output))
