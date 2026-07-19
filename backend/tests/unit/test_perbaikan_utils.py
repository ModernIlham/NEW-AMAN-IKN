"""Uji Tabel Masa Manfaat II (perbaikan menambah umur) — KMK 295/266/339."""
from penilaian_utils import MASA_MANFAAT_DEFAULT
from perbaikan_utils import (
    TABEL_MASA_MANFAAT_II, hitung_penambahan_masa_manfaat,
)


class TestHitungPenambahan:
    def test_bracket_gedung_tempat_kerja(self):
        # 40101 Renovasi: >0-25% → 5 th; >25-50 → 10; >50-75 → 15; >75-100 → 50
        r = hitung_penambahan_masa_manfaat("4010101001", 20_000_000, 100_000_000)
        assert r == {"kelompok": "40101", "jenis": "Renovasi",
                     "persentase": 20.0, "tambah_tahun": 5,
                     "melebihi_rentang": False}
        assert hitung_penambahan_masa_manfaat(
            "4010101001", 60_000_000, 100_000_000)["tambah_tahun"] == 15

    def test_batas_atas_inklusif(self):
        # Pola KMK "> a% s.d. b%": tepat 25% masuk bracket pertama
        r = hitung_penambahan_masa_manfaat("3020101001", 25_000_000, 100_000_000)
        assert r["tambah_tahun"] == 1
        # sedikit di atas 25% → bracket kedua (2 th)
        r2 = hitung_penambahan_masa_manfaat("3020101001", 25_000_001, 100_000_000)
        assert r2["tambah_tahun"] == 2

    def test_alat_kantor_kecil_nol_tahun(self):
        # 30501 Overhaul >0-25% → 0 tahun (kapitalisasi nilai saja)
        r = hitung_penambahan_masa_manfaat("3050101001", 10_000_000, 100_000_000)
        assert r["tambah_tahun"] == 0 and r["jenis"] == "Overhaul"

    def test_melebihi_rentang_dipagari(self):
        # 40102 rentang tertinggi 65% (15 th); 90% → dipagari + ditandai
        r = hitung_penambahan_masa_manfaat("4010201001", 90_000_000, 100_000_000)
        assert r["tambah_tahun"] == 15 and r["melebihi_rentang"] is True

    def test_kmk_339_oil_gas(self):
        # 31304 Overhaul: >0-50% → 0; >50-100% → 10 (KMK 339/2024)
        assert hitung_penambahan_masa_manfaat(
            "3130401001", 40, 100)["tambah_tahun"] == 0
        assert hitung_penambahan_masa_manfaat(
            "3130401001", 80, 100)["tambah_tahun"] == 10

    def test_kelompok_tak_terdaftar_atau_input_buruk(self):
        assert hitung_penambahan_masa_manfaat("2010101001", 50, 100) is None  # tanah
        assert hitung_penambahan_masa_manfaat("4010101001", 0, 100) is None
        assert hitung_penambahan_masa_manfaat("4010101001", 50, 0) is None
        assert hitung_penambahan_masa_manfaat("", 50, 100) is None
        assert hitung_penambahan_masa_manfaat("401", "x", 100) is None


class TestKonsistensiTabel:
    def test_rentang_terurut_naik(self):
        for kel, e in TABEL_MASA_MANFAAT_II.items():
            batas = [b for b, _ in e["rentang"]]
            assert batas == sorted(batas), f"rentang {kel} tidak terurut"
            assert all(0 < b <= 100 for b in batas), f"batas {kel} di luar 0-100"
            assert all(t >= 0 for _, t in e["rentang"]), f"tahun negatif di {kel}"

    def test_kelompok_disusutkan_ada_di_tabel_i(self):
        # Setiap kelompok golongan 3/4/5 pada Tabel II harus punya masa
        # manfaat dasar di Tabel I (KMK yang sama) — anti-drift dua tabel.
        for kel in TABEL_MASA_MANFAAT_II:
            if kel[0] in ("3", "4", "5"):
                assert kel in MASA_MANFAAT_DEFAULT, f"{kel} tak ada di Tabel I"

    def test_tabel_i_lengkap_sesuai_kmk(self):
        # Sampel verifikasi lintas halaman transkrip KMK
        assert MASA_MANFAAT_DEFAULT["30205"] == 20   # Alat Angkutan Bermotor Udara
        assert MASA_MANFAAT_DEFAULT["40101"] == 50   # Gedung Tempat Kerja
        assert MASA_MANFAAT_DEFAULT["50102"] == 50   # Jembatan
        assert MASA_MANFAAT_DEFAULT["50101"] == 10   # Jalan
        assert MASA_MANFAAT_DEFAULT["32101"] == 15   # KMK 266/2023
        assert MASA_MANFAAT_DEFAULT["31305"] == 20   # KMK 339/2024
        assert len(MASA_MANFAAT_DEFAULT) >= 80
