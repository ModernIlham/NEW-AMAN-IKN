"""Aturan tautan baris pengadaan → master persediaan terdaftar (MURNI).

Yang dijaga di sini adalah keputusan-keputusan yang membuat stok mendarat di
kartu yang BENAR: baris mana yang perlu tautan, tautan mana yang sah, kode
mana yang dipakai sesudahnya, dan baris mana yang masih akan ditebak sistem.
"""
from persediaan_pengadaan import (
    butuh_taut_persediaan, kode_setelah_taut, peringatan_persediaan,
    validate_taut_persediaan,
)

MASTER = {"id": "psd-1", "kode_barang": "1010301001000007",
          "nama_barang": "Kertas HVS A4", "satuan": "Rim"}


class TestButuhTaut:
    def test_golongan_satu_butuh_dipilihkan_masternya(self):
        assert butuh_taut_persediaan("1010301001") is True
        assert butuh_taut_persediaan("1010301001000007") is True

    def test_golongan_lain_tidak(self):
        for kode in ("3050102001", "4010101001", "7010101001", "8010101001"):
            assert butuh_taut_persediaan(kode) is False

    def test_kode_kosong_bukan_persediaan(self):
        """Baris tanpa kode belum bisa dicatat ke mana pun — jangan menebak."""
        assert butuh_taut_persediaan("") is False
        assert butuh_taut_persediaan(None) is False
        assert butuh_taut_persediaan("   ") is False


class TestValidateTaut:
    def test_kode_16_digit_yang_sama_persis_sah(self):
        assert validate_taut_persediaan("1010301001000007", MASTER) == []

    def test_kode_10_digit_yang_jadi_AWALAN_master_sah(self):
        """Kasus normalnya: operator mengetik kodefikasi, lalu memilih barang."""
        assert validate_taut_persediaan("1010301001", MASTER) == []

    def test_kode_10_digit_kodefikasi_LAIN_ditolak(self):
        errs = validate_taut_persediaan("1010302002", MASTER)
        assert len(errs) == 1
        assert "tidak cocok" in errs[0]
        assert "1010301001000007" in errs[0], "pesan tak menyebut kode terdaftarnya"

    def test_kode_16_digit_BERBEDA_pada_kodefikasi_sama_ditolak(self):
        """Enam digit terakhir justru yang membedakan HVS A4 dari HVS F4."""
        errs = validate_taut_persediaan("1010301001000008", MASTER)
        assert errs and "tidak cocok" in errs[0]

    def test_master_tak_ditemukan_ditolak_dengan_alasan_satker(self):
        errs = validate_taut_persediaan("1010301001", None)
        assert len(errs) == 1
        assert "satker" in errs[0].lower()

    def test_kode_aset_tetap_ditolak_dan_diarahkan_ke_jalur_aset(self):
        errs = validate_taut_persediaan("3050102001", MASTER)
        assert len(errs) == 1
        assert "golongan 1" in errs[0]

    def test_master_tanpa_kode_barang_ditolak(self):
        errs = validate_taut_persediaan("1010301001", {"id": "x"})
        assert errs and "kode barang" in errs[0]

    def test_kode_kosong_ditolak_lebih_dulu(self):
        """Tanpa penjaga ini, '' menjadi awalan SEMUA kode dan cocok apa pun."""
        assert validate_taut_persediaan("", MASTER) != []

    def test_spasi_pinggir_tak_menggagalkan_tautan(self):
        assert validate_taut_persediaan("  1010301001000007  ", MASTER) == []


class TestKodeSetelahTaut:
    def test_baris_mengadopsi_kode_16_digit_master(self):
        assert kode_setelah_taut(MASTER) == "1010301001000007"

    def test_master_kosong_menghasilkan_kode_kosong_bukan_galat(self):
        assert kode_setelah_taut(None) == ""
        assert kode_setelah_taut({}) == ""


class TestPeringatanPersediaan:
    def test_baris_persediaan_tanpa_tautan_diperingatkan(self):
        w = peringatan_persediaan([{"kode": "1010301001", "uraian": "HVS A4"}])
        assert len(w) == 1
        assert w[0]["index"] == 0
        assert w[0]["sebab"] == "kode_pendek"
        assert "HVS A4" in w[0]["pesan"]

    def test_kode_16_digit_tanpa_tautan_tetap_diperingatkan(self):
        """16 digit pun masih DITEBAK: yang menautkan adalah pilihan, bukan
        panjang kode — master 16 digit ber-kode sama bisa lebih dari satu
        bila NUP-nya berbeda."""
        w = peringatan_persediaan([{"kode": "1010301001000007", "uraian": "HVS"}])
        assert len(w) == 1
        assert w[0]["sebab"] == "belum_tertaut"
        assert "digit penuhnya" not in w[0]["pesan"], (
            "kalimat tambahan soal 6 digit nomor urut ikut tercetak untuk "
            "kode yang sudah 16 digit")

    def test_baris_tertaut_TIDAK_diperingatkan(self):
        assert peringatan_persediaan([
            {"kode": "1010301001000007", "uraian": "HVS", "psd_master_id": "psd-1"},
        ]) == []

    def test_baris_yang_sudah_di_kartu_stok_dilewati(self):
        assert peringatan_persediaan([
            {"kode": "1010301001", "uraian": "HVS", "psd_item_id": "psd-1"},
        ]) == []

    def test_baris_yang_sudah_jadi_aset_dilewati(self):
        assert peringatan_persediaan([
            {"kode": "1010301001", "uraian": "HVS", "asset_id": "aset-1"},
        ]) == []

    def test_baris_aset_tetap_tak_pernah_masuk_daftar(self):
        assert peringatan_persediaan([
            {"kode": "3050102001", "uraian": "Printer"},
        ]) == []

    def test_index_menunjuk_posisi_ASLI_bukan_urutan_hasil(self):
        """Panel di layar menyebut 'Baris n' dari index ini — kalau index
        dihitung dari hasil yang tersaring, operator diarahkan ke baris yang
        salah begitu ada baris aset di depannya."""
        w = peringatan_persediaan([
            {"kode": "3050102001", "uraian": "Printer"},
            {"kode": "1010301001", "uraian": "HVS"},
        ])
        assert [x["index"] for x in w] == [1]

    def test_baris_tanpa_uraian_tetap_terbaca(self):
        w = peringatan_persediaan([{"kode": "1010301001"}])
        assert w[0]["uraian"] == "(tanpa uraian)"

    def test_daftar_kosong_dan_isi_cacat_tak_melempar(self):
        assert peringatan_persediaan([]) == []
        assert peringatan_persediaan(None) == []
        assert peringatan_persediaan(["bukan dict", None]) == []


def test_pesan_menyebut_akibatnya_bukan_sekadar_larangan():
    """Peringatan yang tak menyebut akibat akan diabaikan operator."""
    w = peringatan_persediaan([{"kode": "1010301001", "uraian": "HVS"}])
    assert "dua kartu" in w[0]["pesan"]
