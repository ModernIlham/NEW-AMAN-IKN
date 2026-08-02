"""Uji grid stiker optimal (memenuhi seluruh ruang kertas) — murni."""
from stiker_utils import (GAP_MM, MARGIN_MM, TARGET_STIKER, grid_optimal,
                          kelompokkan_per_ukuran)

A4 = (210.0, 297.0)
A3 = (297.0, 420.0)


def _cek_penuh(page, kolom, baris, lw, lh):
    """Grid harus mengisi PENUH area cetak (sisa hanya margin+gap)."""
    w_total = kolom * lw + (kolom - 1) * GAP_MM
    h_total = baris * lh + (baris - 1) * GAP_MM
    assert abs(w_total - (page[0] - 2 * MARGIN_MM)) < 0.01
    assert abs(h_total - (page[1] - 2 * MARGIN_MM)) < 0.01


def test_grid_optimal_a4():
    t = TARGET_STIKER
    k, b, lw, lh = grid_optimal(*A4, t["besar"]["w"], t["besar"]["h"])
    assert (k, b) == (2, 6) and abs(lw - 98.25) < 0.01 and abs(lh - 46.25) < 0.01
    _cek_penuh(A4, k, b, lw, lh)
    k, b, lw, lh = grid_optimal(*A4, t["sedang"]["w"], t["sedang"]["h"])
    assert (k, b) == (3, 9)
    _cek_penuh(A4, k, b, lw, lh)
    k, b, lw, lh = grid_optimal(*A4, t["kecil"]["w"], t["kecil"]["h"])
    assert (k, b) == (4, 12)
    _cek_penuh(A4, k, b, lw, lh)


def test_grid_optimal_a3_lebih_padat():
    t = TARGET_STIKER
    hasil = {}
    for u in ("besar", "sedang", "kecil"):
        k, b, lw, lh = grid_optimal(*A3, t[u]["w"], t[u]["h"])
        _cek_penuh(A3, k, b, lw, lh)
        hasil[u] = k * b
        # dimensi label tidak melenceng jauh dari target (±20%)
        assert abs(lw - t[u]["w"]) / t[u]["w"] < 0.2
        assert abs(lh - t[u]["h"]) / t[u]["h"] < 0.2
    assert hasil["besar"] == 27   # 3x9 — jauh melebihi 16 grid lama
    assert hasil["sedang"] == 65  # 5x13
    assert hasil["kecil"] == 102  # 6x17


def test_grid_optimal_kertas_kecil_tetap_satu():
    k, b, lw, lh = grid_optimal(80, 60, 95, 45)
    assert k == 1 and b == 1 and lw > 0 and lh > 0


def test_kelompokkan_per_ukuran():
    aset = [
        {"id": "1", "stiker_ukuran": "kecil"},
        {"id": "2", "stiker_ukuran": "besar"},
        {"id": "3"},                       # kosong → default sedang
        {"id": "4", "stiker_ukuran": "aneh"},  # tak dikenal → default
        {"id": "5", "stiker_ukuran": "BESAR"},  # case-insensitive
    ]
    hasil = kelompokkan_per_ukuran(aset)
    urutan = [u for u, _ in hasil]
    assert urutan == ["besar", "sedang", "kecil"]
    peta = dict(hasil)
    assert [a["id"] for a in peta["besar"]] == ["2", "5"]
    assert [a["id"] for a in peta["sedang"]] == ["3", "4"]
    assert [a["id"] for a in peta["kecil"]] == ["1"]
    assert kelompokkan_per_ukuran([]) == []


# ── Tipografi stiker (hierarki, pemenggalan, kepala adaptif) ──────────────
from stiker_utils import (bagi_baris, format_dimensi, muat_satu_baris,
                          rencana_badan, susun_header, tinggi_header,
                          ukuran_font)


def _ukur(teks, size):
    """Pengukur palsu deterministik: tiap huruf = 0,5 × ukuran font."""
    return len(str(teks)) * size * 0.5


def test_hierarki_font_terjaga_di_semua_ukuran():
    """Kode barang selalu paling besar, lalu nama, lalu sub-sub kelompok —
    dulu semuanya menumpuk di ±4,2-4,6 pt pada stiker kecil."""
    for lebar, tinggi in ((98.25, 46.25), (65.0, 30.5), (48.0, 22.5)):
        f = ukuran_font(lebar, tinggi)
        assert f["kode"] > f["nama"] > f["subsub"] >= f["label"]
        assert f["instansi"] > f["sub"]
        # lantai keterbacaan cetak: tak ada peran di bawah 4,8 pt
        assert min(f.values()) >= 4.8


def test_font_stiker_kecil_jauh_lebih_terbaca_dari_ambang_lama():
    f = ukuran_font(48.0, 22.5)
    assert f["kode"] >= 6.6 and f["nama"] >= 6.0 and f["subsub"] >= 5.2


def test_font_tidak_meledak_di_stiker_raksasa():
    f = ukuran_font(200.0, 120.0)
    assert f["kode"] <= 15.0 and f["instansi"] <= 13.0


def test_tinggi_header_proporsional_terhadap_tinggi_nyata():
    assert abs(tinggi_header(45.0, "besar") - 12.0) < 0.01
    # label direntangkan → kepala ikut tumbuh proporsional
    assert tinggi_header(46.25, "besar") > 12.0
    assert abs(tinggi_header(22.0, "kecil") - 6.5) < 0.01


def test_bagi_baris_lanjut_ke_baris_berikutnya():
    teks = "Personal Computer Lengkap Merek Lenovo ThinkCentre"
    baris = bagi_baris(teks, 60.0, _ukur, 6.0, maks_baris=3)
    assert len(baris) >= 2                      # tidak dipotong di baris 1
    assert " ".join(baris) == teks              # utuh, tanpa elipsis
    assert all(_ukur(b, 6.0) <= 60.0 for b in baris)


def test_bagi_baris_elipsis_hanya_saat_jatah_habis():
    teks = " ".join(["Kata"] * 40)
    baris = bagi_baris(teks, 60.0, _ukur, 6.0, maks_baris=2)
    assert len(baris) == 2 and baris[-1].endswith("...")
    assert _ukur(baris[-1], 6.0) <= 60.0


def test_bagi_baris_penggal_kata_tanpa_spasi():
    baris = bagi_baris("A" * 60, 30.0, _ukur, 6.0, maks_baris=3)
    assert len(baris) == 3 and all(_ukur(b, 6.0) <= 30.0 for b in baris)


def test_bagi_baris_kosong():
    assert bagi_baris("", 50.0, _ukur, 6.0, 2) == []
    assert bagi_baris("Nama", 0.0, _ukur, 6.0, 2) == []


def test_muat_satu_baris_menyusut_lalu_memotong():
    teks, size = muat_satu_baris("Nama Instansi", 40.0, _ukur, 9.0, 6.0)
    assert teks == "Nama Instansi" and size < 9.0   # cukup disusutkan
    panjang = "Kementerian " * 6
    teks2, size2 = muat_satu_baris(panjang, 40.0, _ukur, 9.0, 6.0)
    assert size2 == 6.0 and teks2.endswith("...")   # lantai lalu dipotong
    assert _ukur(teks2, size2) <= 40.0


def test_susun_header_nama_panjang_pecah_dua_baris_bila_muat():
    nama = "Kementerian Pekerjaan Umum dan Perumahan Rakyat"
    h = susun_header(nama, "Satker Balai Wilayah", 140.0, 34.0, 9.6, 7.6,
                     _ukur, _ukur)
    assert len(h["baris"]) == 2 and h["size"] == 9.6
    assert " ".join(h["baris"]) == nama
    assert h["baris2"] == "Satker Balai Wilayah"


def test_susun_header_kepala_pendek_tetap_satu_baris_disusutkan():
    nama = "Kementerian Pekerjaan Umum dan Perumahan Rakyat"
    h = susun_header(nama, "", 90.0, 10.0, 9.6, 7.6, _ukur, _ukur)
    assert len(h["baris"]) == 1 and h["size"] < 9.6


def test_susun_header_tanpa_baris_kedua():
    h = susun_header("OIKN", "", 90.0, 30.0, 9.6, 7.6, _ukur, _ukur)
    assert h["baris"] == ["OIKN"] and h["baris2"] == ""


def test_rencana_badan_selalu_sisakan_ruang_subsub():
    f = ukuran_font(48.0, 22.5)          # stiker kecil
    tinggi_badan = (22.5 - tinggi_header(22.5, "kecil") - 3.2) * 72 / 25.4
    jatah = rencana_badan(tinggi_badan, f)
    assert jatah["nama"] >= 1 and jatah["subsub"] >= 1


def test_rencana_badan_stiker_besar_lebih_banyak_baris():
    f = ukuran_font(98.25, 46.25)
    tinggi_badan = (46.25 - tinggi_header(46.25, "besar") - 3.2) * 72 / 25.4
    jatah = rencana_badan(tinggi_badan, f)
    assert jatah["nama"] == 3 and jatah["subsub"] == 2


def test_rencana_badan_ruang_mepet_prioritaskan_nama():
    f = ukuran_font(48.0, 22.5)
    assert rencana_badan(f["kode"] * 1.32 + f["nama"] * 1.2, f) == {
        "nama": 1, "subsub": 0}
    assert rencana_badan(1.0, f)["nama"] == 0


def test_format_dimensi_gaya_indonesia():
    assert format_dimensi(98.25, 46.25) == "98,3 × 46,3 mm"
    assert format_dimensi(45, 22) == "45,0 × 22,0 mm"
