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


UKURAN_NYATA = ((98.25, 46.25), (65.0, 30.333), (48.375, 22.375))  # A4
#: Peran yang benar-benar muncul di stiker yang DITEMPEL. `label` hanya ada di
#: stiker CONTOH (alat ukur bahan, tak pernah ditempel) dan penggambarnya
#: memberi lantai cetak sendiri — lihat `gambar_sampel`.
PERAN_NYATA = ("kode", "instansi", "nup", "nama", "subsub", "sub")


def test_hierarki_font_terjaga_di_semua_ukuran():
    """Kode barang selalu paling besar, lalu nama, lalu sub-sub kelompok —
    dulu semuanya menumpuk di ±4,2-4,6 pt pada stiker kecil."""
    from stiker_utils import LANTAI_CETAK_PT
    for lebar, tinggi in UKURAN_NYATA:
        f = ukuran_font(lebar, tinggi)
        assert f["kode"] > f["nama"] > f["subsub"] >= f["label"]
        assert f["instansi"] > f["sub"]
        # Lantai cetak dikenakan pada peran yang sungguh ditempel.
        assert min(f[p] for p in PERAN_NYATA) >= LANTAI_CETAK_PT


def test_stiker_kecil_hurufnya_IKUT_mengecil():
    """Keluhan pemilik: *"saya lihat ukuran stiker kecil masih terasa besar
    ukuran fontnya"*.

    Penyebabnya lantai per-peran: di stiker kecil SEMUA peran mentok lantai
    masing-masing (kode 6,6 · nama 6,0 · sub-sub 5,5 · sub 5,0), jadi huruf
    berhenti mengecil jauh sebelum stikernya berhenti mengecil. Angka-angka
    itulah yang dipatok di sini sebagai batas ATAS: kalau lantai per-peran
    kembali, uji ini jatuh."""
    f = ukuran_font(48.375, 22.375)
    assert f["kode"] < 6.6
    assert f["nama"] < 6.0
    assert f["subsub"] < 5.5
    assert f["sub"] < 5.0


def test_pengecilan_antar_ukuran_SERAGAM_untuk_semua_peran():
    """Permintaan pemilik: stiker kecil harus terlihat *"seolah-olah
    merupakan pengecilan penyesuaian dari font di stiker besar"*.

    Artinya SATU angka pengecilan untuk seluruh peran. Dulu tiap peran punya
    angkanya sendiri karena masing-masing menyentuh lantainya pada saat yang
    berbeda: pada stiker kecil rentangnya 0,558–0,729 — kode barang menyusut
    44% sementara keterangan ukur cuma 27%, dan itulah yang membuat stiker
    kecil terlihat sebagai rancangan lain, bukan rancangan yang sama."""
    besar = ukuran_font(*UKURAN_NYATA[0])
    for lebar, tinggi in UKURAN_NYATA[1:]:
        f = ukuran_font(lebar, tinggi)
        nisbah = [f[p] / besar[p] for p in besar]
        # Simpangan hanya boleh dari pembulatan 2 desimal, bukan dari
        # kebijakan yang berbeda antar peran.
        assert max(nisbah) - min(nisbah) < 0.005, (
            f"pengecilan tak seragam di {lebar}×{tinggi}: {nisbah}")


def test_hierarki_PERSIS_sama_di_semua_ukuran():
    """Perbandingan kode:nama dulu runtuh dari 1,278 (besar) ke 1,100
    (kecil) — di stiker kecil kode barang praktis sebesar nama barang,
    sehingga mata tak lagi menemukan kode lebih dulu."""
    acuan = None
    for lebar, tinggi in UKURAN_NYATA:
        f = ukuran_font(lebar, tinggi)
        nisbah = f["kode"] / f["nama"]
        if acuan is None:
            acuan = nisbah
        assert abs(nisbah - acuan) < 0.01, f"hierarki bergeser di {lebar}"
    assert abs(acuan - 1.618033988749895 ** 0.5) < 0.01   # φ^(1/2)


def test_setiap_ukuran_huruf_duduk_di_ANAK_TANGGA_emas():
    """Seluruh ukuran huruf di seluruh ukuran stiker adalah `9 × φ^(k/8)`
    untuk k bulat — satu deret, bukan tujuh angka yang disetel tangan."""
    import math

    from stiker_utils import ACUAN_PT, LANGKAH_EMAS
    for lebar, tinggi in UKURAN_NYATA:
        for peran, pt in ukuran_font(lebar, tinggi).items():
            k = math.log(pt / ACUAN_PT) / math.log(LANGKAH_EMAS)
            assert abs(k - round(k)) < 0.02, (
                f"{peran} {pt} pt bukan anak tangga emas (k={k:.3f})")


def test_padding_mengecil_bersama_stiker_sampai_lantai_fisik():
    """Inset tepi ikut mengecil, tetapi toleransi mesin potong itu besaran
    FISIK: stiker sekecil apa pun tetap butuh jarak yang sama dari garis
    potong, jadi ada lantai yang tak boleh ditembus."""
    from stiker_utils import PAD_MIN_MM, padding_stiker
    besar = padding_stiker(46.25)
    sedang = padding_stiker(30.333)
    kecil = padding_stiker(22.375)
    assert besar > sedang >= kecil >= PAD_MIN_MM
    # Dulu teks memakai 1,6 mm mati di SEMUA ukuran — pada stiker besar itu
    # membuat teks terlihat menempel garis sementara QR (1,8 mm) tidak.
    assert besar > 1.6
    assert padding_stiker(5.0) == PAD_MIN_MM


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


# ── Susunan badan stiker: sub-sub di bawah kode, nama menempel dasar ────
#
# Permintaan pemilik: *"disemua ukuran stiker design stikernya bagian sub sub
# kelompok tempatkan tepat dibawah kode barangnya langsung dan sesuaikan
# ukurannya agar serasi, dan untuk nama barang buat dari arah paling bawah
# bottom dan align left, yang akan terus keatas hingga 3 baris saja maksimal
# panjangnya jika lebih gunakan '...'"*

def test_nama_barang_paling_banyak_TIGA_baris():
    """Nama yang mengalir sampai enam baris memakan ruang kode barang, dan
    kode barang itulah kunci pencocokannya dengan catatan."""
    from stiker_utils import MAKS_BARIS_NAMA, rencana_badan, ukuran_font
    f = ukuran_font(100, 70)          # stiker besar, ruang berlimpah
    assert rencana_badan(1000.0, f)["nama"] == MAKS_BARIS_NAMA == 3


def test_subsub_paling_banyak_DUA_baris():
    from stiker_utils import MAKS_BARIS_SUBSUB, rencana_badan, ukuran_font
    f = ukuran_font(100, 70)
    assert rencana_badan(1000.0, f)["subsub"] == MAKS_BARIS_SUBSUB == 2


def test_ruang_mepet_NAMA_tetap_didahulukan():
    """Nama barang yang dicari petugas saat mencocokkan fisik; sub-sub
    kelompok mengalah lebih dulu."""
    from stiker_utils import rencana_badan, ukuran_font
    f = ukuran_font(50, 25)
    jatah = rencana_badan(f["kode"] * 1.32 + f["nama"] * 1.2, f)
    assert jatah == {"nama": 1, "subsub": 0}


def test_subsub_TERBACA_tetapi_tetap_di_bawah_nama():
    """Sub-sub kini duduk tepat di bawah kode sebagai keterangannya, jadi ia
    dinaikkan agar terbaca — tetapi hierarkinya tak boleh terbalik: ia tetap
    lebih kecil daripada nama barang dan kode."""
    from stiker_utils import ukuran_font
    for lebar, tinggi in ((100, 70), (70, 40), (50, 25), (38, 19)):
        f = ukuran_font(lebar, tinggi)
        assert f["subsub"] < f["nama"] < f["kode"], (lebar, tinggi)


def test_elipsis_dipakai_saat_nama_melebihi_jatah():
    """Di stiker, elipsis memang yang diminta — beda dari laporan."""
    from stiker_utils import bagi_baris
    def ukur(t, size):
        return len(t) * size * 0.5
    baris = bagi_baris("Alat Laboratorium Pendidikan Kedokteran Bedah dan "
                       "Perawatan Intensif Terpadu Bergerak Nomor Seri 12",
                       60.0, ukur, 8.0, maks_baris=3)
    assert len(baris) == 3
    assert baris[-1].endswith("...")
