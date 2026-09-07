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


# ── Kepala stiker punya setelannya SENDIRI ──────────────────────────────
#
# Permintaan pemilik: *"pada bagian header jangan gunakan 'Nama Instansi
# (baris 1 kop)' akan tetapi buatkan sendiri Header buat stiker yang bisa
# disesuaikan di setelan sistem juga."*

def test_header_stiker_MENGGANTIKAN_nama_instansi():
    kop = {**KOP_PANJANG, "header_stiker": "OTORITA IBU KOTA NUSANTARA"}
    teks = _teks(_render(ASET, "besar", kop=kop, sampel_ukuran=False))
    assert "OTORITA IBU KOTA NUSANTARA" in teks
    # Nama instansi kop laporan TIDAK ikut tercetak — itulah gunanya setelan
    # tersendiri: nama resmi yang panjang menyusut sampai nyaris tak terbaca.
    assert "Kementerian Pekerjaan Umum" not in teks


def test_tanpa_setelan_header_stiker_TETAP_memakai_nama_instansi():
    """Satker yang belum mengisinya tak boleh mendapat stiker berkepala kosong."""
    teks = _teks(_render(ASET, "besar", sampel_ukuran=False))
    assert "Kementerian Pekerjaan Umum" in teks


def test_header_stiker_kosong_tak_dianggap_terisi():
    kop = {**KOP_PANJANG, "header_stiker": "   "}
    teks = _teks(_render(ASET, "besar", kop=kop, sampel_ukuran=False))
    assert "Kementerian Pekerjaan Umum" in teks


# ── Susunan badan: sub-sub di bawah kode, nama menempel dasar ───────────

def _posisi_teks(pdf_bytes, cari, halaman=0):
    """Ordinat-Y (dari bawah) kemunculan pertama sebuah teks di halaman."""
    pdfium = pytest.importorskip("pypdfium2")
    dok = pdfium.PdfDocument(io.BytesIO(pdf_bytes))
    hal = dok[halaman]
    tp = hal.get_textpage()
    penuh = tp.get_text_range()
    idx = penuh.find(cari)
    assert idx >= 0, f"{cari!r} tak tergambar"
    # rect (kiri, bawah, kanan, atas) untuk potongan itu
    n = tp.count_rects(idx, len(cari))
    assert n > 0
    return tp.get_rect(0)


@pytest.mark.parametrize("ukuran", ["besar", "sedang", "kecil"])
def test_urutan_badan_KODE_lalu_SUBSUB_lalu_NAMA(ukuran):
    """Sub-sub kelompok menerangkan KODE, jadi ia menempel pada kode — dan
    nama barang berada di bawahnya, menempel dasar stiker.

    Diuji sebagai URUTAN, bukan sebagai jarak: ambang jarak longgar tetap
    lolos ketika sub-sub terlempar ke bawah nama barang (susunan lama), sebab
    pada stiker pendek ketiganya memang berdekatan. Urutan tak punya celah
    seperti itu.
    """
    pdf = _render(ASET[:1], ukuran, sampel_ukuran=False)
    kode = _posisi_teks(pdf, "3050102001")
    subsub = _posisi_teks(pdf, "P.C Unit")
    # "Lenovo", bukan "Personal Computer": yang terakhir juga muncul DI DALAM
    # teks sub-sub ("P.C Unit (Personal Computer)"), sehingga ujinya akan
    # membandingkan sub-sub dengan dirinya sendiri dan lulus tanpa arti.
    nama = _posisi_teks(pdf, "Lenovo")
    # rect = (kiri, bawah, kanan, atas) — makin ke bawah, ordinatnya mengecil.
    assert kode[1] > subsub[1], "sub-sub tidak berada di bawah kode"
    assert subsub[1] > nama[1], "nama barang tidak berada di bawah sub-sub"


def test_nama_barang_MENEMPEL_DASAR_stiker():
    """Sepuluh stiker berjajar punya garis dasar yang sama, sehingga mata
    petugas menyusuri satu baris alih-alih naik-turun mengikuti panjang nama.

    Diuji dengan DUA aset berpanjang nama berbeda: baris terbawah keduanya
    harus sejajar. Kalau nama mengalir dari atas (susunan lama), aset bernama
    pendek berakhir jauh di atas yang bernama panjang.
    """
    dua = [
        {"asset_code": "3050102001", "NUP": "1", "kode_register": "",
         "_subsub": "P.C Unit", "asset_name": "Lenovo"},
        {"asset_code": "3050102002", "NUP": "2", "kode_register": "",
         "_subsub": "P.C Unit", "asset_name":
             "Personal Computer Lengkap Merek Acer Veriton Seri Terbaru"},
    ]
    pdf = _render(dua, "besar", sampel_ukuran=False)
    pendek = _posisi_teks(pdf, "Lenovo")
    panjang = _posisi_teks(pdf, "Veriton")
    assert abs(pendek[3] - panjang[3]) < 1.0, (
        "baris terbawah nama tidak sejajar antar stiker")


def test_nama_barang_RATA_KIRI_sejajar_kode():
    pdf = _render(ASET[:1], "besar", sampel_ukuran=False)
    kode = _posisi_teks(pdf, "3050102001")
    nama = _posisi_teks(pdf, "Lenovo")
    assert abs(nama[0] - kode[0]) < 1.5, "nama barang tidak rata kiri dgn kode"


# ── Jarak teks dari garis potong (permintaan pemilik) ──────────────────────
#
# *"sebelah kiri dan yang paling bawah tolong berikan jarak dengan garisnya
# agar tidak terlalu dekat dan rapi dengan QRCodenya"*

def _kotak_stiker_pertama(ukuran):
    """(x_kiri, y_bawah, lebar_mm, tinggi_mm) stiker pertama di halaman."""
    from stiker_utils import MARGIN_MM
    t = TARGET_STIKER[ukuran]
    _, _, lw_mm, lh_mm = grid_optimal(A4[0] / mm, A4[1] / mm, t["w"], t["h"])
    return (MARGIN_MM * mm, A4[1] - MARGIN_MM * mm - lh_mm * mm, lw_mm, lh_mm)


#: Nama BERBUNTUT: "g" dan "y" turun di bawah garis alas. Justru inilah yang
#: dikeluhkan pemilik — "Dedicated Cloud Server - NAS Synology" tampak
#: menempel garis bawah karena yang ditaruh sejarak inset adalah GARIS ALAS,
#: bukan tintanya. Nama sependek ini muat satu baris, jadi baris yang diukur
#: memang baris terbawah.
ASET_BUNTUT = [{"asset_code": "3050102001", "NUP": "12",
                "asset_name": "Synology", "_subsub": "P.C Unit",
                "kode_register": ""}]

_SKALA_RENDER = 4          # px per pt saat halaman dijadikan bitmap


def _kotak_qr(ukuran):
    """(inset_kanan, inset_bawah) KOTAK gambar QR dari garis stiker, dlm pt.

    QR itu gambar vektor, tak terlihat oleh pengekstrak teks, jadi ia diukur
    dari piksel halaman yang dirender. Dua hal harus dibereskan supaya
    angkanya berarti:

    1. Garis kepala stiker membentang selebar penuh sampai menyentuh tepi
       kanan — mengukur seluruh isi kotak berarti mengukur garis itu, bukan
       QR (dan melaporkan 0,26 mm yang tak ada hubungannya dengan QR).
    2. Modul gelap terluar QR mundur SATU modul dari kotak gambarnya: zona
       sunyi yang diwajibkan spesifikasi QR. Membandingkan tinta itu dengan
       inset teks akan memaafkan inset QR yang meleset sampai selebar satu
       modul. Lebar modul dipulihkan dari pola pencari kanan-atas — persegi
       gelap selebar TEPAT tujuh modul — lalu dikurangkan.
    """
    np = pytest.importorskip("numpy")
    pdfium = pytest.importorskip("pypdfium2")
    data = _render(ASET_BUNTUT, ukuran, sampel_ukuran=False)
    dok = pdfium.PdfDocument(io.BytesIO(data))
    gbr = dok[0].render(scale=_SKALA_RENDER).to_pil().convert("L")
    a = np.array(gbr) < 128
    x_kiri, y_bawah, lw_mm, lh_mm = _kotak_stiker_pertama(ukuran)

    def px(v):
        return int(round(v * _SKALA_RENDER))

    x0, x1 = px(x_kiri), px(x_kiri + lw_mm * mm)
    y0, y1 = px(A4[1] - (y_bawah + lh_mm * mm)), px(A4[1] - y_bawah)
    tepi = 3                      # px garis kotak stiker (0,8 pt × skala)
    isi = a[y0 + tepi:y1 - tepi, x0 + tepi:x1 - tepi]
    lebar = isi.shape[1]
    penuh = np.nonzero(isi.sum(axis=1) > lebar * 0.9)[0]
    assert len(penuh), f"garis kepala tak ditemukan pada stiker {ukuran}"
    badan = isi[penuh[-1] + tepi:, lebar * 2 // 3:]
    ys, xs = np.nonzero(badan)
    assert len(xs), f"QR tak tergambar pada stiker {ukuran}"

    baris_atas = badan[ys.min(), :]
    i, n = int(np.nonzero(baris_atas)[0].max()), 0
    while i >= 0 and baris_atas[i]:
        n += 1
        i -= 1
    modul = n / 7.0
    assert modul > 1, f"pola pencari QR tak terbaca pada stiker {ukuran}"
    kanan = (badan.shape[1] - 1 - xs.max() + tepi - modul) / _SKALA_RENDER
    bawah = (badan.shape[0] - 1 - ys.max() + tepi - modul) / _SKALA_RENDER
    return kanan, bawah


@pytest.mark.parametrize("ukuran", ["besar", "sedang", "kecil"])
def test_teks_KIRI_dan_BAWAH_berjarak_penuh_dari_garis_potong(ukuran):
    """Tinta terbawah & terkiri harus berjarak sepenuh inset dari garis.

    Dulu jaraknya 1,6 mm di kiri dan — karena baris nama ditaruh dengan
    GARIS ALAS di 1,6 mm — hanya ~0,9 mm di bawah untuk huruf berbuntut.
    """
    from stiker_utils import padding_stiker
    x_kiri, y_bawah, _, lh_mm = _kotak_stiker_pertama(ukuran)
    pad = padding_stiker(lh_mm) * mm
    r = _posisi_teks(_render(ASET_BUNTUT, ukuran, sampel_ukuran=False),
                     "Synology")
    assert r[0] - x_kiri >= pad * 0.98, "teks terlalu dekat garis KIRI"
    assert r[1] - y_bawah >= pad * 0.98, "tinta terlalu dekat garis BAWAH"


@pytest.mark.parametrize("ukuran", ["besar", "sedang", "kecil"])
def test_inset_teks_TUMBUH_bersama_ukuran_stiker(ukuran):
    """Inset bukan angka mati: stiker besar mendapat tepi lebih lega.

    Patokannya 1,6 mm — inset mati yang lama. Stiker besar harus melewatinya
    dengan jelas, dan tak satu ukuran pun boleh turun di bawahnya.
    """
    x_kiri, y_bawah, _, lh_mm = _kotak_stiker_pertama(ukuran)
    r = _posisi_teks(_render(ASET_BUNTUT, ukuran, sampel_ukuran=False),
                     "Synology")
    assert min(r[0] - x_kiri, r[1] - y_bawah) >= 1.6 * mm
    if ukuran == "besar":
        assert min(r[0] - x_kiri, r[1] - y_bawah) > 2.4 * mm


def test_teks_dan_QR_memakai_INSET_yang_sama():
    """*"...dan rapi dengan QRCodenya"*.

    Dulu teks memakai 1,6 mm sementara QR 1,8 mm, sehingga pada stiker besar
    teks terlihat menempel garis sementara QR mengambang di dalam. Keduanya
    kini satu angka. QR diperiksa lewat GEOMETRI (kotak gambarnya), bukan
    lewat tinta: modul gelapnya memang mundur satu modul karena zona sunyi
    yang diwajibkan spesifikasi QR — itu bukan inset yang berbeda.
    """
    from stiker_utils import padding_stiker
    for ukuran in ("besar", "sedang", "kecil"):
        x_kiri, y_bawah, lw_mm, lh_mm = _kotak_stiker_pertama(ukuran)
        pad = padding_stiker(lh_mm) * mm
        r = _posisi_teks(_render(ASET_BUNTUT, ukuran, sampel_ukuran=False),
                         "Synology")
        # Sisi bawah kotak QR = pad; sisi bawah tinta teks = pad juga.
        assert abs((r[1] - y_bawah) - pad) < 0.35 * mm, (
            f"{ukuran}: inset teks {(r[1] - y_bawah) / mm:.2f} mm "
            f"≠ inset QR {pad / mm:.2f} mm")
        # Kotak QR duduk pada inset yang SAMA — bukan sekadar "tak lebih
        # dekat": inset QR sendiri (dulu 1,8 mm mati) harus ikut bergerak.
        kanan, bawah = _kotak_qr(ukuran)
        assert abs(kanan - pad) < 0.2 * mm and abs(bawah - pad) < 0.2 * mm, (
            f"{ukuran}: inset QR {kanan / mm:.2f}/{bawah / mm:.2f} mm "
            f"≠ inset teks {pad / mm:.2f} mm")


# ── Hierarki nama vs sub-sub kini dibawa KETEBALAN, bukan ukuran ─────────

def test_nama_barang_TEBAL_sub_sub_biasa_pada_ukuran_yang_SAMA():
    """Sub-sub kelompok kini seukuran nama barang (permintaan pemilik,
    bertahap tiga kali). Yang membedakan keduanya tinggal KETEBALAN — dan
    karena itu ketebalan itu wajib dijaga: tanpa uji ini, mengganti
    `Helvetica-Bold` menjadi `Helvetica` pada baris nama akan melenyapkan
    seluruh hierarki tanpa satu pun galat.

    Diuji lewat LEBAR TERGAMBAR, bukan lewat nama fontnya: pada ukuran huruf
    yang sama, Helvetica-Bold menggambar teks yang sama lebih lebar daripada
    Helvetica. Sub-sub dan nama sengaja diisi teks yang IDENTIK supaya yang
    dibandingkan benar-benar ketebalannya, bukan panjang katanya.
    """
    pdfium = pytest.importorskip("pypdfium2")
    sama = "Terminal"
    aset = [{"asset_code": "3100204013", "NUP": "1", "kode_register": "",
             "_subsub": sama, "asset_name": sama}]
    data = _render(aset, "besar", sampel_ukuran=False)
    tp = pdfium.PdfDocument(io.BytesIO(data))[0].get_textpage()
    penuh = tp.get_text_range()

    lebar = []
    idx = penuh.find(sama)
    while idx >= 0:
        assert tp.count_rects(idx, len(sama)) > 0
        kiri, _, kanan, _ = tp.get_rect(0)
        lebar.append(kanan - kiri)
        idx = penuh.find(sama, idx + 1)

    # Urutan gambar: kode → SUB-SUB → NAMA (lihat gambar_stiker).
    assert len(lebar) == 2, f"teks '{sama}' harusnya tergambar dua kali"
    subsub, nama = lebar
    assert nama > subsub, (
        f"nama barang ({nama:.2f} pt) tidak lebih tebal daripada sub-sub "
        f"({subsub:.2f} pt) — hierarkinya hilang")


def test_ukuran_huruf_nama_dan_subsub_memang_SAMA():
    """Pelengkap uji di atas: kalau ukurannya diam-diam dibedakan lagi,
    perbandingan lebar tak lagi mengukur ketebalan."""
    from stiker_utils import ukuran_font
    f = ukuran_font(98.25, 46.25)
    assert f["nama"] == f["subsub"]
