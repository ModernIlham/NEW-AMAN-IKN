"""Uji render stiker ke PDF sungguhan — TANPA MongoDB.

Menguji hal yang tak terlihat dari logika murni: teks benar-benar tergambar,
muat di dalam kotaknya, dan stiker CONTOH berisi dimensi nyata per satuan.
Ekstraksi teks memakai pypdfium2 (sudah dipakai uji laporan persediaan).
"""
import io

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas

from stiker_render import gambar_grup
from stiker_utils import TARGET_STIKER, format_dimensi, grid_optimal

KOP_PANJANG = {
    "nama_instansi": "Kementerian Pekerjaan Umum dan Perumahan Rakyat "
                     "Republik Indonesia",
    "_baris2_stiker": "Satuan Kerja Balai Prasarana Permukiman Wilayah "
                      "Kalimantan Timur",
}
ASET = [
    {"asset_code": "3050102001", "NUP": "12",
     "asset_name": "Personal Computer Lengkap Merek Lenovo ThinkCentre M70q",
     "_subsub": "P.C Unit (Personal Computer)", "kode_register": "126011"},
    {"asset_code": "3100102002", "NUP": "115", "asset_name": "Meja Kerja Kayu",
     "_subsub": "Meubelair", "kode_register": ""},
]


def _render(aset, ukuran, kop=None, sampel_ukuran=True):
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    gambar_grup(c, aset, ukuran, A4[0], A4[1], kop or KOP_PANJANG, None, mm,
                mulai_halaman_baru=False, sampel_ukuran=sampel_ukuran)
    c.save()
    return buf.getvalue()


def _teks(pdf_bytes, halaman=0):
    pdfium = pytest.importorskip("pypdfium2")
    dok = pdfium.PdfDocument(io.BytesIO(pdf_bytes))
    return dok[halaman].get_textpage().get_text_range()


@pytest.mark.parametrize("ukuran", ["besar", "sedang", "kecil"])
def test_render_semua_ukuran_menghasilkan_pdf(ukuran):
    data = _render(ASET, ukuran)
    assert data.startswith(b"%PDF") and len(data) > 1500


@pytest.mark.parametrize("ukuran", ["besar", "sedang", "kecil"])
def test_kode_nup_nama_dan_subsub_semuanya_tercetak(ukuran):
    """Sub-sub kelompok DAN nama barang wajib ada di SEMUA ukuran — dulu
    sub-sub kelompok bisa tergusur di stiker kecil."""
    teks = _teks(_render(ASET, ukuran)).replace("\r", " ").replace("\n", " ")
    assert "3050102001" in teks and "NUP: 12" in teks
    assert "Personal Computer" in teks          # nama barang
    assert "P.C Unit" in teks                   # sub-sub kelompok
    assert "Meubelair" in teks                  # sub-sub kelompok aset kedua


def test_nama_instansi_panjang_utuh_bukan_dipotong():
    """Kepala boleh tumbuh: nama instansi panjang pecah dua baris, tidak
    berakhir '...' seperti sebelumnya."""
    teks = _teks(_render(ASET, "kecil")).replace("\n", " ").replace("\r", " ")
    assert "Republik Indonesia" in teks


def test_stiker_contoh_memuat_dimensi_nyata():
    _, _, lw_mm, lh_mm = grid_optimal(210.0, 297.0, TARGET_STIKER["besar"]["w"],
                                      TARGET_STIKER["besar"]["h"])
    teks = _teks(_render(ASET, "besar")).replace("\n", " ").replace("\r", " ")
    assert "CONTOH UKURAN" in teks
    assert format_dimensi(lw_mm, lh_mm) in teks          # "98,3 × 46,3 mm"
    assert "bukan untuk ditempel" in teks


def test_stiker_contoh_bisa_dimatikan():
    teks = _teks(_render(ASET, "besar", sampel_ukuran=False))
    assert "CONTOH UKURAN" not in teks


def test_daftar_kosong_tidak_menggambar_contoh():
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    assert gambar_grup(c, [], "besar", A4[0], A4[1], KOP_PANJANG, None, mm,
                       mulai_halaman_baru=False) is False


def test_aset_tanpa_nup_dan_tanpa_subsub_tidak_meledak():
    aset = [{"asset_code": "1010101001", "asset_name": "Tanah Bangunan Kantor"}]
    teks = _teks(_render(aset, "sedang"))
    assert "1010101001" in teks and "NUP" not in teks
