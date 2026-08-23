"""Helper murni penjatuh baris kepala surat LPB.

Laporan pemilik: *"hilangkan informasi yang berulang di bagian header karena
sudah terjabarkan di setiap pembagian row per kategori BAST."*

Yang menentukan bukan JENIS dokumennya melainkan NILAINYA: baris hanya
dijatuhkan bila teksnya memang sudah ada di area tabel. LPB lama tanpa bundel
apa pun karena itu tetap berkepala lengkap tanpa perlakuan khusus.
"""
from lpb_utils import (
    AWALAN_KETERANGAN_GABUNGAN, keterangan_berulang, nilai_berulang,
)

TABEL = ("Penyedia: CV Sumber Rejeki · PPK: Bimo Ananto Pamungkas · Kontrak "
         "· BAST PPK-KPB B-001/SATKER-D/OIKN/VIII/2026")


class TestNilaiBerulang:
    def test_nilai_yang_sudah_ada_di_tabel(self):
        assert nilai_berulang("CV Sumber Rejeki", TABEL) is True
        assert nilai_berulang("Bimo Ananto Pamungkas", TABEL) is True

    def test_nilai_yang_BERBEDA_tetap_dipertahankan(self):
        assert nilai_berulang("PT Lain Sendiri", TABEL) is False

    def test_nilai_kosong_bukan_pengulangan(self):
        """Kosong `in` teks apa pun selalu True — tanpa penjagaan ini SELURUH
        baris kepala akan dijatuhkan pada dokumen tanpa penyedia."""
        assert nilai_berulang("", TABEL) is False
        assert nilai_berulang(None, TABEL) is False

    def test_tanpa_area_tabel_tak_ada_yang_dijatuhkan(self):
        assert nilai_berulang("CV Sumber Rejeki", "") is False


class TestKeteranganBerulang:
    def test_bangkitan_sendiri_yang_nomornya_sudah_tercetak(self):
        k = f"{AWALAN_KETERANGAN_GABUNGAN} B-001/SATKER-D/OIKN/VIII/2026"
        assert keterangan_berulang(k, TABEL) is True

    def test_bangkitan_sendiri_dengan_nomor_yang_BELUM_tercetak(self):
        k = f"{AWALAN_KETERANGAN_GABUNGAN} B-009/BELUM/ADA"
        assert keterangan_berulang(k, TABEL) is False

    def test_semua_nomor_harus_tercetak_bukan_salah_satu(self):
        k = (f"{AWALAN_KETERANGAN_GABUNGAN} B-001/SATKER-D/OIKN/VIII/2026; "
             "B-009/BELUM/ADA")
        assert keterangan_berulang(k, TABEL) is False

    def test_tulisan_OPERATOR_selalu_bertahan(self):
        """Membuang kalimat orang karena kebetulan memuat nomor yang sama
        adalah kehilangan informasi, bukan pemangkasan pengulangan."""
        assert keterangan_berulang(
            "Barang datang terlambat; BAST PPK-KPB B-001/SATKER-D/OIKN/VIII/2026",
            TABEL) is False

    def test_tulisan_operator_yang_PERSIS_ADA_di_tabel_pun_bertahan(self):
        """Kasus yang membedakan. Operator yang menulis nama penyedia sebagai
        keterangan tetap harus terbaca — yang boleh dijatuhkan HANYA bentuk
        bangkitan sendiri, bukan apa pun yang kebetulan ada di tabel."""
        assert keterangan_berulang("CV Sumber Rejeki", TABEL) is False
        assert keterangan_berulang("Kontrak", TABEL) is False

    def test_awalan_tanpa_nomor_apa_pun_bukan_pengulangan(self):
        assert keterangan_berulang(AWALAN_KETERANGAN_GABUNGAN, TABEL) is False

    def test_kosong_aman(self):
        assert keterangan_berulang("", TABEL) is False
        assert keterangan_berulang(None, TABEL) is False
