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


# ── Kepala surat berhenti mengulang keterangan yang sudah ada di baris ──────

class TestKepalaTercakup:
    """Permintaan pemilik: *"pada header informasi mengenai tanggal
    kedatangan, PPK, dan No. Bukti/Faktur masih ada, tolong hapus karena sudah
    ada di informasi setiap row bagian BAST yang ada."*

    Yang dijaga: syaratnya "SETIAP baris", bukan "ada satu baris".
    """

    SUMBER = {"penyedia": "CV Sumber Rejeki", "ppk_nama": "Bimo",
              "ppk_nip": "198910282014021004", "ppk_status_kepegawaian": "pns",
              "tanggal_bast": "2026-08-10"}

    def test_semua_baris_lengkap_mencakup_semuanya(self):
        from lpb_utils import kepala_tercakup
        assert kepala_tercakup([{"sumber": self.SUMBER},
                                {"sumber": self.SUMBER}]) == {
            "penyedia", "ppk_nama", "ppk_nip", "tanggal"}

    def test_satu_baris_tanpa_tanggal_membatalkan_cakupan_tanggal(self):
        from lpb_utils import kepala_tercakup
        hasil = kepala_tercakup([
            {"sumber": self.SUMBER},
            {"sumber": {**self.SUMBER, "tanggal_bast": ""}}])
        assert "tanggal" not in hasil
        # Yang lain TIDAK ikut gugur — pemangkasan per-kunci, bukan per-baris.
        assert "ppk_nama" in hasil

    def test_satu_baris_TANPA_sumber_membatalkan_seluruhnya(self):
        """LPB campuran: baris lama tanpa snapshot tak mencakup apa pun."""
        from lpb_utils import kepala_tercakup
        assert kepala_tercakup([{"sumber": self.SUMBER}, {}]) == set()

    def test_daftar_kosong_tak_mencakup_apa_pun(self):
        """Kalau kosong dianggap 'tercakup', kepala surat LPB tanpa baris
        akan kehilangan seluruh identitasnya."""
        from lpb_utils import kepala_tercakup
        assert kepala_tercakup([]) == set()
        assert kepala_tercakup(None) == set()

    def test_NIP_Non_ASN_tidak_pernah_tercakup(self):
        """Aturan sistem melarang NIP Non-ASN dicetak, jadi barisnya TIDAK
        mencetak apa pun — dan kepala surat tak boleh mengira sudah."""
        from lpb_utils import kepala_tercakup
        hasil = kepala_tercakup([
            {"sumber": {**self.SUMBER, "ppk_status_kepegawaian": "non_asn"}}])
        assert "ppk_nip" not in hasil
        assert "ppk_nama" in hasil

    def test_baris_cacat_tak_melempar(self):
        from lpb_utils import kepala_tercakup
        assert kepala_tercakup(["bukan dict", None]) == set()
        assert kepala_tercakup([{"sumber": "bukan dict"}]) == set()


class TestSumberMelekatPadaBarisLpbAset:
    """LPB dari SATU BAST dulu tak membawa snapshot sumber sama sekali —
    sehingga kepala suratnya tak punya apa pun untuk dijatuhkan, dan
    tanggal/PPK/No. Bukti tercetak di kepala tanpa tandingan di barisnya."""

    def test_sumber_dilekatkan_ke_setiap_baris(self):
        from lpb_utils import baris_lpb_dari_aset
        baris = baris_lpb_dari_aset(
            [{"asset_code": "3050102001", "NUP": "1", "asset_name": "Printer",
              "harga_satuan": 2_500_000},
             {"asset_code": "3050102001", "NUP": "2", "asset_name": "Printer",
              "harga_satuan": 2_500_000}],
            sumber={"penyedia": "PT X", "ppk_nama": "Bimo"})
        assert [b["sumber"]["penyedia"] for b in baris] == ["PT X", "PT X"]

    def test_tanpa_sumber_barisnya_TIDAK_berkunci_sumber(self):
        """Kunci `sumber: None` akan membuat `bundel_sumber` dipanggil atas
        None di seluruh LPB lama — biarkan kuncinya memang tak ada."""
        from lpb_utils import baris_lpb_dari_aset
        baris = baris_lpb_dari_aset([{"asset_code": "3050102001"}])
        assert "sumber" not in baris[0]

    def test_snapshot_disalin_bukan_dibagi_pakai(self):
        """Satu dict yang sama dipakai ulang tiap baris membuat suntingan
        pada satu baris mengubah seluruhnya."""
        from lpb_utils import baris_lpb_dari_aset
        s = {"penyedia": "PT X"}
        baris = baris_lpb_dari_aset(
            [{"asset_code": "3050102001"}, {"asset_code": "3050102001"}],
            sumber=s)
        baris[0]["sumber"]["penyedia"] = "DIUBAH"
        assert baris[1]["sumber"]["penyedia"] == "PT X"
        assert s["penyedia"] == "PT X"
