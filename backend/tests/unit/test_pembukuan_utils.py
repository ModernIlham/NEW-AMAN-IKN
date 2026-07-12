"""Test logika murni pembukuan (pembukuan_utils.py) — tanpa Mongo.

Menjaga aturan intra/ekstrakomptabel (ambang kapitalisasi PMK 181) dan
rekap DBKP per golongan tidak bergeser diam-diam.
"""
from pembukuan_utils import (
    AMBANG_KAPITALISASI_DEFAULT, KONDISI_LKB, build_dbkp_rows,
    build_lbkp_rows, build_lkb_rows, golongan_of, klasifikasi_komptabel,
    parse_harga, posisi_neraca,
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


class TestPosisiNeraca:
    def test_persediaan_masuk_intra_dan_grand_total(self):
        rows, total = build_dbkp_rows([
            {"asset_code": "3060102135", "purchase_price": 5_000_000},   # intra
            {"asset_code": "3060102135", "purchase_price": 500_000},     # ekstra
        ])
        hasil = posisi_neraca(rows, total, persediaan_jumlah=3, persediaan_nilai=750_000)
        assert hasil["persediaan"] == {"jumlah": 3, "nilai": 750_000.0}
        assert hasil["total"]["jumlah_intra"] == 1 + 3
        assert hasil["total"]["nilai_intra"] == 5_000_000 + 750_000
        # Ekstra tidak terpengaruh persediaan
        assert hasil["total"]["jumlah_ekstra"] == total["jumlah_ekstra"] == 1
        assert hasil["total"]["nilai_total"] == 5_500_000 + 750_000

    def test_tanpa_persediaan_sama_dengan_total_aset(self):
        rows, total = build_dbkp_rows([
            {"asset_code": "2010104001", "purchase_price": 100_000_000},
        ])
        hasil = posisi_neraca(rows, total)
        assert hasil["total"] == {**total}
        assert hasil["persediaan"] == {"jumlah": 0, "nilai": 0.0}


class TestBuildLbkpRows:
    DARI, SAMPAI = "2026-01-01", "2026-06-30"

    def _aset(self, kode, harga, created):
        return {"asset_code": kode, "purchase_price": harga, "created_at": created}

    def test_awal_tambah_kurang_akhir_per_kelas(self):
        assets = [
            self._aset("3060102135", 5_000_000, "2025-03-01T08:00:00"),   # intra, awal
            self._aset("3060102135", 2_000_000, "2026-02-10T08:00:00"),   # intra, tambah
            self._aset("3060102135", 400_000, "2026-03-05T08:00:00"),     # ekstra, tambah
            self._aset("3060102135", 900_000, "2026-08-01T08:00:00"),     # setelah periode → abaikan
        ]
        tombstones = [
            {"asset_code": "3060102135", "timestamp": "2026-04-01T08:00:00", "nilai": 1_500_000},
            {"asset_code": "3060102135", "timestamp": "2025-12-01T08:00:00", "nilai": 999},  # di luar periode
        ]
        per_kelas, tanpa_nilai = build_lbkp_rows(assets, tombstones, self.DARI, self.SAMPAI,
                                                 {"3": "Peralatan dan Mesin"})
        assert tanpa_nilai == 0
        rows_i, tot_i = per_kelas["intra"]
        assert len(rows_i) == 1 and rows_i[0]["uraian"] == "Peralatan dan Mesin"
        assert (tot_i["jumlah_awal"], tot_i["jumlah_tambah"], tot_i["jumlah_kurang"]) == (1, 1, 1)
        assert tot_i["nilai_akhir"] == 5_000_000 + 2_000_000 - 1_500_000
        assert tot_i["jumlah_akhir"] == 1
        rows_e, tot_e = per_kelas["ekstra"]
        assert (tot_e["jumlah_tambah"], tot_e["nilai_tambah"]) == (1, 400_000)
        _, tot_g = per_kelas["gabungan"]
        assert tot_g["jumlah_akhir"] == tot_i["jumlah_akhir"] + tot_e["jumlah_akhir"]
        assert tot_g["nilai_akhir"] == tot_i["nilai_akhir"] + tot_e["nilai_akhir"]

    def test_tombstone_tanpa_nilai_terhitung_jumlahnya(self):
        per_kelas, tanpa_nilai = build_lbkp_rows(
            [], [{"asset_code": "3060102135", "timestamp": "2026-02-01T00:00:00", "nilai": 0}],
            self.DARI, self.SAMPAI)
        assert tanpa_nilai == 1
        _, tot_g = per_kelas["gabungan"]
        assert tot_g["jumlah_kurang"] == 1 and tot_g["nilai_kurang"] == 0.0
        assert tot_g["jumlah_akhir"] == -1  # jujur: saldo negatif menandakan data historis kurang

    def test_kosong(self):
        per_kelas, tanpa_nilai = build_lbkp_rows([], [], self.DARI, self.SAMPAI)
        assert tanpa_nilai == 0
        for kelas in ("intra", "ekstra", "gabungan"):
            rows, total = per_kelas[kelas]
            assert rows == [] and total["jumlah_akhir"] == 0


class TestBuildLkbRows:
    def test_rekap_per_kondisi(self):
        assets = [
            {"asset_code": "3100102001", "condition": "Baik",
             "purchase_price": 5_000_000},
            {"asset_code": "3100102002", "condition": "Rusak Ringan",
             "purchase_price": 2_000_000},
            {"asset_code": "3100102003", "condition": "Rusak Berat",
             "purchase_price": 1_000_000},
            {"asset_code": "3100102004", "condition": "",
             "purchase_price": 500_000},
            {"asset_code": "4010101001", "condition": "Baik",
             "purchase_price": 300_000_000},
        ]
        rows, total = build_lkb_rows(assets, {"3": "Peralatan dan Mesin"})
        assert KONDISI_LKB == ("Baik", "Rusak Ringan", "Rusak Berat")
        assert [r["golongan"] for r in rows] == ["3", "4"]
        pm = rows[0]
        assert pm["uraian"] == "Peralatan dan Mesin"
        assert (pm["baik"], pm["rusak_ringan"], pm["rusak_berat"],
                pm["belum"]) == (1, 1, 1, 1)
        assert pm["jumlah"] == 4 and pm["nilai"] == 8_500_000
        assert total["jumlah"] == 5 and total["baik"] == 2
        assert total["nilai"] == 308_500_000

    def test_kondisi_tak_dikenal_dan_kode_kosong(self):
        rows, total = build_lkb_rows([
            {"asset_code": "", "condition": "Hancur", "purchase_price": 10},
        ])
        assert rows[0]["golongan"] == "?" and rows[0]["belum"] == 1
        assert total["jumlah"] == 1

    def test_kosong(self):
        rows, total = build_lkb_rows([])
        assert rows == [] and total["jumlah"] == 0 and total["nilai"] == 0
