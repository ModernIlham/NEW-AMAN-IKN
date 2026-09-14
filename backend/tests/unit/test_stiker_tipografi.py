"""Panduan font mengambil angka dan wajah huruf yang benar-benar dicetak."""
import io

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pypdf import PdfReader
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from stiker_render import gambar_grup
from stiker_utils import (KERTAS_STIKER_MM, TARGET_STIKER, FONT_STIKER_TEBAL,
                          FONT_STIKER_BIASA, grid_optimal, ukuran_font,
                          spesifikasi_tipografi)


@pytest.mark.parametrize("kertas", ["A4", "A3"])
def test_panduan_mengikuti_grid_dan_tangga_ukuran_asli(kertas):
    spec = spesifikasi_tipografi(kertas)
    assert {p["kode"] for p in spec["peran"] if p["tebal"]} == {"instansi", "kode", "nup", "nama"}
    for p in spec["peran"]:
        assert p["font"] == (FONT_STIKER_TEBAL if p["tebal"] else FONT_STIKER_BIASA)
    for u in spec["ukuran"]:
        target = TARGET_STIKER[u["kode"]]
        kol, brs, w, h = grid_optimal(*KERTAS_STIKER_MM[kertas], target["w"], target["h"])
        assert u["font_pt"] == ukuran_font(w, h)
        assert u["lebar_mm"] == round(w, 2) and u["tinggi_mm"] == round(h, 2)
        assert u["kapasitas"] == kol * brs


def test_kertas_dinormalisasi_dan_tidak_ditebak_bila_salah():
    assert spesifikasi_tipografi(" a3 ")["kertas"] == "A3"
    with pytest.raises(ValueError, match="Kertas harus"):
        spesifikasi_tipografi("Letter")


@pytest.mark.parametrize("kertas", ["A4", "A3"])
@pytest.mark.parametrize("ukuran", ["besar", "sedang", "kecil"])
def test_font_pdf_sama_pada_empat_peran_tebal_dan_keterangan_regular(kertas, ukuran):
    buf = io.BytesIO()
    page = tuple(n * mm for n in KERTAS_STIKER_MM[kertas])
    c = canvas.Canvas(buf, pagesize=page)
    gambar_grup(c, [{"asset_code": "3050102001", "NUP": "7", "asset_name": "Terminal",
                     "_subsub": "Kategori"}], ukuran, *page,
                 {"header_stiker": "AMAN", "_baris2_stiker": "SATKER"}, None, mm,
                 mulai_halaman_baru=False, sampel_ukuran=False)
    c.save()
    tercetak = {}
    def rekam(teks, cm, tm, font, size):
        if teks.strip() and font:
            tercetak[teks.strip()] = (str(font["/BaseFont"]), size)
    PdfReader(io.BytesIO(buf.getvalue())).pages[0].extract_text(visitor_text=rekam)
    spec = next(u for u in spesifikasi_tipografi(kertas)["ukuran"] if u["kode"] == ukuran)["font_pt"]
    for teks, peran in (("AMAN", "instansi"), ("NUP: 7", "nup"), ("Terminal", "nama")):
        assert tercetak[teks][0] == "/Helvetica-Bold"
        assert tercetak[teks][1] == pytest.approx(spec[peran])
    assert tercetak["3050102001"][0] == "/Helvetica-Bold"
    assert spec["kode"] * .78 <= tercetak["3050102001"][1] <= spec["kode"]
    for teks, peran in (("Kategori", "subsub"), ("SATKER", "sub")):
        assert tercetak[teks] == ("/Helvetica", pytest.approx(spec[peran]))


def test_endpoint_memerlukan_login_dan_hanya_mengirim_desain_universal():
    from auth_utils import require_user
    from routes.stiker import stiker_router
    app = FastAPI()
    app.include_router(stiker_router)
    with TestClient(app) as client:
        assert client.get("/stiker/tipografi").status_code == 401
        app.dependency_overrides[require_user] = lambda: {"id": "petugas-uji", "kode_satker": "UJI"}
        r = client.get("/stiker/tipografi", params={"kertas": "A3"})
        assert r.status_code == 200 and r.json() == spesifikasi_tipografi("A3")
        assert client.get("/stiker/tipografi", params={"kertas": "keliru"}).status_code == 400


def test_generator_panduan_dua_halaman_ilustratif_ukuran_aktual(tmp_path):
    import runpy
    from pathlib import Path
    from reportlab.lib.pagesizes import A4
    skrip = Path(__file__).resolve().parents[3] / "scripts" / "contoh_tipografi_stiker.py"
    generator = runpy.run_path(str(skrip))["buat_contoh"]
    tujuan = tmp_path / "panduan.pdf"
    assert generator(tujuan) == tujuan
    pdf = PdfReader(tujuan)
    assert len(pdf.pages) == 2
    for halaman, kertas in zip(pdf.pages, ("A4", "A3")):
        assert float(halaman.mediabox.width) == pytest.approx(A4[0])
        assert float(halaman.mediabox.height) == pytest.approx(A4[1])
        teks = halaman.extract_text()
        assert f"Tipografi stiker - grid {kertas}" in teks
        assert "BUKAN ASET NYATA" in teks and "Garis uji 50 mm" in teks
        assert teks.count("STIKER CONTOH") == 3
        assert teks.count("Contoh Meja Kerja") == 3
        for u in spesifikasi_tipografi(kertas)["ukuran"]:
            assert u["nama"] + " / " in teks
            assert f"{u['font_pt']['instansi']:.2f}".replace(".", ",") in teks
