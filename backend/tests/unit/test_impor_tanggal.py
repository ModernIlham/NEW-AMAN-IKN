"""Uji pembacaan tanggal impor — format resmi, serial Excel, dan penolakan."""
from datetime import date, datetime

import pytest

from impor_tanggal import (
    FORMAT_RESMI, TANGGAL_MIN, TANGGAL_MAKS,
    baca_tanggal, normalkan_tanggal_baris,
)


class TestFormatResmi:
    def test_dd_mm_yyyy_adalah_format_resmi(self):
        assert FORMAT_RESMI == "DD/MM/YYYY"
        assert baca_tanggal("17/08/2025") == ("2025-08-17", None)

    def test_digit_tunggal_diterima_karena_URUTAN_yang_mengikat_makna(self):
        # Longgar soal nol di depan, KETAT soal urutan. Di bawah aturan
        # DD/MM/YYYY, "3/4/2025" tetap berarti 3 April — tak ada ambiguitas
        # yang ditambahkan, dan operator tak dihukum karena Excel memangkas
        # nol di depan saat sel bertipe teks.
        assert baca_tanggal("17/8/2025") == ("2025-08-17", None)
        assert baca_tanggal("3/4/2025") == ("2025-04-03", None)

    def test_pemisah_lain_yang_tak_ambigu_tetap_diterima(self):
        assert baca_tanggal("17-08-2025") == ("2025-08-17", None)
        assert baca_tanggal("17.08.2025") == ("2025-08-17", None)

    def test_iso_tetap_diterima_agar_berkas_lama_tak_tertolak(self):
        assert baca_tanggal("2025-08-17") == ("2025-08-17", None)
        assert baca_tanggal("2025/08/17") == ("2025-08-17", None)

    def test_dd_mm_menang_atas_mm_dd_pada_tanggal_ambigu(self):
        # 03/04/2025 = 3 April, bukan 4 Maret.
        assert baca_tanggal("03/04/2025") == ("2025-04-03", None)


class TestSerialExcel:
    def test_serial_dikonversi_dengan_basis_1899_12_30(self):
        # Serial 45658 = 1 Januari 2025 di Excel.
        assert baca_tanggal(45658) == ("2025-01-01", None)
        assert baca_tanggal(45658.0) == ("2025-01-01", None)

    def test_serial_sebagai_teks_juga_terbaca(self):
        assert baca_tanggal("45658") == ("2025-01-01", None)
        assert baca_tanggal("45658.0") == ("2025-01-01", None)

    def test_serial_pecahan_mengambil_harinya_saja(self):
        # 45658.75 = 1 Jan 2025 pukul 18:00 — jamnya tak dipakai.
        assert baca_tanggal(45658.75) == ("2025-01-01", None)

    def test_serial_di_wilayah_bug_1900_ditolak(self):
        # 1..60 adalah wilayah bug tahun kabisat 1900 Excel; angka sekecil itu
        # jauh lebih mungkin salah ketik daripada tanggal sungguhan.
        iso, galat = baca_tanggal(45)
        assert iso is None and "bukan tanggal Excel yang wajar" in galat

    def test_serial_kelewat_besar_ditolak(self):
        iso, galat = baca_tanggal(999999)
        assert iso is None and galat


class TestObjekTanggalAsli:
    def test_datetime_dari_openpyxl(self):
        assert baca_tanggal(datetime(2025, 8, 17, 0, 0)) == ("2025-08-17", None)

    def test_date_polos(self):
        assert baca_tanggal(date(2025, 8, 17)) == ("2025-08-17", None)

    def test_teks_hasil_str_datetime_dibersihkan_dari_jam(self):
        # Inilah bentuk yang dulu masuk basis data apa adanya.
        assert baca_tanggal("2024-01-01 00:00:00") == ("2024-01-01", None)

    def test_iso_ber_T_juga_dibersihkan(self):
        assert baca_tanggal("2024-01-01T13:45:00") == ("2024-01-01", None)


class TestKosongDanSampah:
    @pytest.mark.parametrize("kosong", ["", "   ", None])
    def test_kosong_bukan_galat_kolom_tanggal_opsional(self, kosong):
        assert baca_tanggal(kosong) == (None, None)

    def test_tanggal_mustahil_ditolak(self):
        iso, galat = baca_tanggal("32/01/2025")
        assert iso is None and galat
        iso, galat = baca_tanggal("2025-13-01")
        assert iso is None and galat

    def test_29_februari_bukan_kabisat_ditolak(self):
        iso, galat = baca_tanggal("29/02/2025")
        assert iso is None and galat

    def test_29_februari_kabisat_diterima(self):
        assert baca_tanggal("29/02/2024") == ("2024-02-29", None)

    def test_teks_bebas_ditolak_dengan_petunjuk_format(self):
        iso, galat = baca_tanggal("17 Agustus 2025")
        assert iso is None and FORMAT_RESMI in galat

    def test_boolean_bukan_tanggal(self):
        iso, galat = baca_tanggal(True)
        assert iso is None and galat


class TestRentangWajar:
    def test_tahun_terlalu_lampau_ditolak(self):
        iso, galat = baca_tanggal("01/01/1801")
        assert iso is None and str(TANGGAL_MIN.year) in galat

    def test_batas_rentang_diterima(self):
        assert baca_tanggal(TANGGAL_MIN.strftime("%d/%m/%Y"))[0] == TANGGAL_MIN.isoformat()
        assert baca_tanggal(TANGGAL_MAKS.strftime("%d/%m/%Y"))[0] == TANGGAL_MAKS.isoformat()


class TestNormalkanBaris:
    def test_menormalkan_di_tempat_dan_tak_mengeluh(self):
        row = {"asset_code": "3030103001", "purchase_date": "17/08/2025",
               "garansi_hingga": 45658}
        galat = normalkan_tanggal_baris(row, 5)
        assert galat == []
        assert row["purchase_date"] == "2025-08-17"
        assert row["garansi_hingga"] == "2025-01-01"
        assert row["asset_code"] == "3030103001"   # kolom lain tak disentuh

    def test_galat_menyebut_nomor_baris_dan_nama_kolom(self):
        row = {"purchase_date": "17 Agustus 2025"}
        galat = normalkan_tanggal_baris(row, 12)
        assert len(galat) == 1
        assert "Baris 12" in galat[0] and "purchase_date" in galat[0]

    def test_nilai_asli_dipertahankan_saat_galat(self):
        # Operator harus masih bisa melihat apa yang dia ketik saat membetulkan.
        row = {"purchase_date": "abc"}
        normalkan_tanggal_baris(row, 3)
        assert row["purchase_date"] == "abc"

    def test_kolom_kosong_jadi_string_kosong_bukan_None(self):
        row = {"purchase_date": None}
        assert normalkan_tanggal_baris(row, 1) == []
        assert row["purchase_date"] == ""

    def test_kolom_yang_tak_ada_dilewati(self):
        row = {"asset_code": "3030103001"}
        assert normalkan_tanggal_baris(row, 1) == []
        assert "purchase_date" not in row

    def test_beberapa_kolom_bermasalah_dilaporkan_semua(self):
        row = {"purchase_date": "abc", "garansi_hingga": "32/13/2025"}
        galat = normalkan_tanggal_baris(row, 7)
        assert len(galat) == 2
