"""Tes util murni LBP (lbp_utils) — tanpa Mongo."""
from lbp_utils import (AKUN_AKUMULASI, DASAR_HUKUM_LBP,
                       baris_akumulasi_per_akun, baris_mutasi_golongan,
                       baris_perbandingan_lb_lk, baris_posisi_per_akun,
                       fmt_rp, label_periode_lbp, rupiah_terbilang,
                       struktur_daftar_isi, tanggal_akhir_periode)


def test_fmt_rp_dan_terbilang():
    assert fmt_rp(1234567) == "1.234.567"
    assert fmt_rp(-500) == "(500)"
    assert fmt_rp(None) == "0"
    t = rupiah_terbilang(1500000)
    assert t.startswith("Rp1.500.000,00 (") and t.endswith(" rupiah)")


def test_label_dan_tanggal_periode():
    assert label_periode_lbp(2026) == "Tahun 2026"
    assert label_periode_lbp(2026, 1) == "Semester I Tahun 2026"
    assert tanggal_akhir_periode(2026, 1) == "2026-06-30"
    assert tanggal_akhir_periode(2026, 2) == "2026-12-31"
    assert tanggal_akhir_periode(2026) == "2026-12-31"


def test_baris_posisi_per_akun():
    rows = [
        {"golongan": "2", "uraian": "Tanah", "nilai_intra": 1000.0},
        {"golongan": "3", "uraian": "Peralatan dan Mesin",
         "nilai_intra": 500.0},
        {"golongan": "8", "uraian": "ATB", "nilai_intra": 50.0},
    ]
    psd = [{"akun": "117111", "uraian": "Barang Konsumsi", "nilai": 30.0}]
    p = baris_posisi_per_akun(rows, psd)
    assert p["subtotal"] == {"aset_lancar": 30.0, "aset_tetap": 1500.0,
                             "aset_lainnya": 50.0}
    assert p["total"] == 1580.0
    # Akun default 131111 utk tanah, override master menang
    assert p["aset_tetap"][0][0] == "131111"
    p2 = baris_posisi_per_akun(rows, [], {"2": {"akun": "131119",
                                                "uraian": "Tanah X"}})
    assert p2["aset_tetap"][0][0] == "131119"
    assert baris_posisi_per_akun([], [])["total"] == 0


def test_baris_akumulasi_dan_perbandingan():
    susut = {"per_golongan": [
        {"golongan": "3", "akumulasi": 100.0},
        {"golongan": "2", "akumulasi": 0.0},   # tanah tak disusutkan
        {"golongan": "4", "akumulasi": 40.0},
    ]}
    ak = baris_akumulasi_per_akun(susut)
    assert ak["total"] == 140.0
    assert ak["baris"][0][0] == AKUN_AKUMULASI["3"][0]
    posisi = baris_posisi_per_akun(
        [{"golongan": "3", "uraian": "PM", "nilai_intra": 500.0}], [])
    b = baris_perbandingan_lb_lk(posisi, ak)
    # Semua baris LB = LK, selisih 0; akumulasi tampil negatif
    for _, rws in b["seksi"]:
        for akun, _u, lb, lk, sel in rws:
            assert lb == lk and sel == 0.0
            if akun.startswith("137"):
                assert lb < 0
    lb_t, lk_t, sel_t = b["total"]
    assert lb_t == lk_t and sel_t == 0.0
    assert lb_t == 500.0 - 140.0


def test_baris_mutasi_golongan():
    def rows(prefix):
        return [{"golongan": "3", "uraian": "Peralatan dan Mesin",
                 "jumlah_awal": 10, "nilai_awal": 1000,
                 "jumlah_tambah": 2, "nilai_tambah": 200,
                 "jumlah_kurang": 1, "nilai_kurang": 100,
                 "jumlah_akhir": 11, "nilai_akhir": 1100}]
    per_kelas = {"gabungan": (rows("g"), {}), "intra": (rows("i"), {}),
                 "ekstra": ([], {})}
    blok = baris_mutasi_golongan(per_kelas)
    assert len(blok) == 1 and blok[0]["golongan"] == "3"
    label_baris = [b[0] for b in blok[0]["baris"]]
    assert label_baris == ["Saldo Awal", "Mutasi Tambah", "Mutasi Kurang",
                           "Saldo Akhir"]
    # Gabungan terisi, ekstra 0
    assert blok[0]["baris"][0][1] == 10 and blok[0]["baris"][0][5] == 0
    assert baris_mutasi_golongan({}) == []


def test_struktur_dan_dasar_hukum():
    isi = struktur_daftar_isi()
    assert any("OVERVIEW" in j for _, j in isi)
    assert any("CATATAN ATAS LAPORAN" in j for _, j in isi)
    assert len(DASAR_HUKUM_LBP) >= 10


def test_susun_mutasi_per_transaksi():
    """Tabel per kode transaksi: saldo awal 000 + agregasi jurnal; kode
    3xx/4xx dinegatifkan; total = saldo awal + mutasi."""
    from lbp_utils import susun_mutasi_per_transaksi
    jurnal = [
        {"kode_transaksi": "101", "jumlah": 2, "nilai": 200.0},
        {"kode_transaksi": "101", "jumlah": 1, "nilai": 100.0},
        {"kode_transaksi": "301", "jumlah": 1, "nilai": 50.0},
    ]
    m = susun_mutasi_per_transaksi(jurnal, saldo_awal_qty=10,
                                   saldo_awal_nilai=1000.0)
    assert m["baris"][0] == ("000", "Saldo Awal", 10.0, 1000.0)
    peta = {b[0]: b for b in m["baris"]}
    assert peta["101"][2] == 3 and peta["101"][3] == 300.0
    assert peta["301"][2] == -1 and peta["301"][3] == -50.0
    assert m["total"] == (12.0, 1250.0)
    kosong = susun_mutasi_per_transaksi([], 5, 500.0)
    assert len(kosong["baris"]) == 1 and kosong["total"] == (5.0, 500.0)


def test_kebijakan_akuntansi_dan_daftar_isi_lengkap():
    from lbp_utils import kebijakan_akuntansi_lbp, struktur_daftar_isi_lengkap
    keb = kebijakan_akuntansi_lbp({"3": 1_000_000, "4": 25_000_000})
    judul = [k["judul"] for k in keb]
    for wajib in ("Persediaan", "Aset Tetap", "Kebijakan Penyusutan BMN",
                  "Amortisasi", "Kebijakan Kapitalisasi BMN",
                  "Akuntansi Berbasis Akrual"):
        assert wajib in judul, wajib
    kap = next(k for k in keb if k["judul"] == "Kebijakan Kapitalisasi BMN")
    assert any("1.000.000" in b for b in kap["daftar"])
    isi = struktur_daftar_isi_lengkap()
    for wajib in ("SURAT PENGANTAR", "LAMPIRAN",
                  "3.6 Tindak Lanjut Temuan Pemeriksaan",
                  "h. Laporan Barang Bersejarah"):
        assert any(wajib in j for _, j in isi), wajib
