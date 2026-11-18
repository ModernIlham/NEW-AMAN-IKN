"""Penataan PDF tahan sel tabel kelewat tinggi (pdf_tata_letak_tahan.py).

Regresi tinjauan mutu Nov 2026: satu aset bernama ±2.500 karakter membuat
Ekspor PDF aset & Daftar Pemegang PDF seluruh kegiatan gagal 500
(``reportlab LayoutError``). Laporan normal TIDAK boleh berubah.
"""
import io

import pytest
from pypdf import PdfReader
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (Flowable, KeepTogether, Paragraph,
                                SimpleDocTemplate, Table)
from reportlab.platypus.doctemplate import BaseDocTemplate, LayoutError

import pdf_tata_letak_tahan as ptl

ST = getSampleStyleSheet()["Normal"]
PANJANG = "Meja kerja kayu jati dengan laci tiga dan kunci, ruang rapat lantai dua. " * 60
TANPA_SPASI = "A" * 4000


@pytest.fixture(autouse=True)
def _terpasang():
    ptl.pasang()
    yield


def _tabel(isi_besar=None, n=30):
    baris = [[Paragraph("No", ST), Paragraph("Nama", ST)]]
    baris += [[Paragraph(str(i), ST), Paragraph("Kursi lipat", ST)] for i in range(n)]
    if isi_besar:
        baris.append([Paragraph("X", ST), Paragraph(isi_besar, ST)])
    return Table(baris, colWidths=[30, 200], repeatRows=1)


def _bangun(cerita):
    buf = io.BytesIO()
    SimpleDocTemplate(buf).build(cerita)
    data = buf.getvalue()
    assert data.startswith(b"%PDF")
    return data


def _bangun_asli(monkeypatch, cerita):
    """Bangun dengan ReportLab ASLI (pembungkus dilepas sementara)."""
    with monkeypatch.context() as m:
        m.setattr(BaseDocTemplate, "build", BaseDocTemplate.build.__wrapped__)
        buf = io.BytesIO()
        SimpleDocTemplate(buf).build(cerita)
        return buf.getvalue()


def _teks(data):
    return " ".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(data)).pages)


def test_pasang_idempoten():
    asli = BaseDocTemplate.build
    ptl.pasang()
    assert BaseDocTemplate.build is asli
    assert ptl.terpasang()


def test_laporan_normal_tidak_berubah(monkeypatch):
    """Tanpa sel raksasa: hasil identik dengan ReportLab asli (jumlah halaman
    dan teks sama) — fallback sama sekali tidak tersentuh."""
    data = _bangun([Paragraph("Judul", ST), _tabel(n=120)])
    asli = _bangun_asli(monkeypatch, [Paragraph("Judul", ST), _tabel(n=120)])
    assert len(PdfReader(io.BytesIO(data)).pages) == len(PdfReader(io.BytesIO(asli)).pages)
    assert _teks(data) == _teks(asli)


@pytest.mark.parametrize("isi", [PANJANG, TANPA_SPASI])
def test_sel_raksasa_tidak_lagi_menggagalkan_dokumen(monkeypatch, isi):
    with pytest.raises(LayoutError):  # bukti: ReportLab asli memang gagal
        _bangun_asli(monkeypatch, [Paragraph("Judul", ST), _tabel(isi)])
    data = _bangun([Paragraph("Judul", ST), _tabel(isi)])
    teks = _teks(data)
    assert "Kursi lipat" in teks
    assert len(PdfReader(io.BytesIO(data)).pages) >= 2


def test_tabel_bersarang_di_keeptogether_ikut_ditangani():
    data = _bangun([KeepTogether([Paragraph("Judul", ST), _tabel(PANJANG)])])
    assert "Kursi lipat" in _teks(data)


def test_buffer_diatur_ulang_dan_list_pemanggil_boleh_habis():
    buf = io.BytesIO()
    cerita = [Paragraph("Judul", ST), _tabel(PANJANG)]
    SimpleDocTemplate(buf).build(cerita)
    data = buf.getvalue()
    # Tepat satu dokumen PDF (percobaan gagal tidak meninggalkan sisa).
    assert data.count(b"%PDF") == 1 and data.rstrip().endswith(b"%%EOF")


class _Raksasa(Flowable):
    """Flowable non-tabel yang tak pernah muat — fallback tak berlaku."""

    def wrap(self, aw, ah):
        return aw, ah * 10

    def draw(self):
        pass


def test_penyebab_bukan_tabel_tetap_dilempar():
    with pytest.raises(LayoutError):
        SimpleDocTemplate(io.BytesIO()).build([_Raksasa()])
