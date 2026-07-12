"""Test logika murni pembukuan (pembukuan_utils.py) — tanpa Mongo.

Menjaga aturan intra/ekstrakomptabel (ambang kapitalisasi PMK 181) dan
rekap DBKP per golongan tidak bergeser diam-diam.
"""
from pembukuan_utils import (
    AMBANG_KAPITALISASI_DEFAULT, build_dbkp_rows, golongan_of,
    klasifikasi_komptabel, parse_harga,
)


class TestParseHarga:
    def test_angka_langsung(self):
        assert parse_harga(1500000) == 1500000.0
        assert parse_harga(0) == 0.0

    def test_format_indonesia(self):
        assert parse_harga("Rp1.234.567") == 1234567.0
        assert parse_harga("1.234.567,89") == 1234567.89
        assert parse_harga("25.000.000") == 25000000.0

    def test_tidak_valid_jadi_nol(self):
        assert parse_harga(None) == 0.0
        assert parse_harga("") == 0.0
        assert parse_harga("abc") == 0.0
        assert parse_harga(float("nan")) == 0.0
        assert parse_harga(float("inf")) == 0.0


class TestGolongan:
    def test_digit_pertama(self):
        assert golongan_of("3060102135") == "3"
        assert golongan_of("4010101001") == "4"
        assert golongan_of("1") == "1"

    def test_kosong_atau_non_digit(self):
        assert golongan_of("") == ""
        assert golongan_of(None) == ""
        assert golongan_of("X123") == ""


class TestKlasifikasiKomptabel:
    def test_ambang_default_sesuai_pmk_181(self):
        assert AMBANG_KAPITALISASI_DEFAULT == {"3": 1_000_000, "4": 25_000_000}

    def test_peralatan_mesin_golongan_3(self):
        assert klasifikasi_komptabel("3060102135", 1_000_000) == "intra"  # pas ambang
        assert klasifikasi_komptabel("3060102135", 999_999) == "ekstra"
        assert klasifikasi_komptabel("3060102135", "Rp2.500.000") == "intra"

    def test_gedung_golongan_4(self):
        assert klasifikasi_komptabel("4010101001", 25_000_000) == "intra"
        assert klasifikasi_komptabel("4010101001", 24_999_999) == "ekstra"

    def test_golongan_tanpa_ambang_selalu_intra(self):
        assert klasifikasi_komptabel("2010101001", 0) == "intra"       # tanah
        assert klasifikasi_komptabel("5010101001", 100) == "intra"     # jalan
        assert klasifikasi_komptabel("", 0) == "intra"                 # kode belum rapi

    def test_ambang_parameter_menimpa_default(self):
        assert klasifikasi_komptabel("3060102135", 500_000, {"3": 300_000}) == "intra"
        assert klasifikasi_komptabel("4010101001", 24_000_000, {"3": 300_000}) == "intra"


class TestBuildDbkpRows:
    def test_rekap_per_golongan_intra_ekstra(self):
        assets = [
            {"asset_code": "3060102135", "purchase_price": 2_000_000},   # 3 intra
            {"asset_code": "3060102136", "purchase_price": 500_000},     # 3 ekstra
            {"asset_code": "4010101001", "purchase_price": 30_000_000},  # 4 intra
            {"asset_code": "2010101001", "purchase_price": 0},           # 2 intra (tanpa ambang)
        ]
        rows, total = build_dbkp_rows(assets, {"2": "Tanah", "3": "Peralatan dan Mesin", "4": "Gedung dan Bangunan"})
        by = {r["golongan"]: r for r in rows}
        assert [r["golongan"] for r in rows] == ["2", "3", "4"]  # terurut
        assert by["3"]["jumlah_intra"] == 1 and by["3"]["jumlah_ekstra"] == 1
        assert by["3"]["nilai_intra"] == 2_000_000 and by["3"]["nilai_ekstra"] == 500_000
        assert by["3"]["jumlah_total"] == 2 and by["3"]["nilai_total"] == 2_500_000
        assert by["4"]["uraian"] == "Gedung dan Bangunan"
        assert total["jumlah_total"] == 4
        assert total["nilai_total"] == 32_500_000
        assert total["jumlah_ekstra"] == 1

    def test_barang_tanpa_golongan_masuk_baris_tanda_tanya_di_akhir(self):
        rows, total = build_dbkp_rows([
            {"asset_code": "", "purchase_price": 10_000},
            {"asset_code": "3060102135", "purchase_price": 5_000_000},
        ], {"3": "Peralatan dan Mesin"})
        assert [r["golongan"] for r in rows] == ["3", "?"]
        assert rows[-1]["uraian"].startswith("Tanpa Golongan")
        assert rows[-1]["jumlah_intra"] == 1  # tetap intra, tidak disembunyikan
        assert total["jumlah_total"] == 2

    def test_kosong(self):
        rows, total = build_dbkp_rows([])
        assert rows == []
        assert total["jumlah_total"] == 0 and total["nilai_total"] == 0.0

    def test_harga_string_indonesia_terhitung(self):
        rows, _ = build_dbkp_rows([{"asset_code": "3010101001", "purchase_price": "Rp1.500.000"}])
        assert rows[0]["jumlah_intra"] == 1
        assert rows[0]["nilai_intra"] == 1_500_000.0
