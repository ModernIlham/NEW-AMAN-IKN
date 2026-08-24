"""Aturan kelengkapan pembubuhan tanda tangan elektronik (MURNI).

Laporan pemilik: *"ketika salah satu penanda tangan menandatangani hanya 1
lembar yang ia tanda tangani dan sudah memencet tombol bubuhkan, sehingga
lembaran yang ada tanda tangan dia lagi di lembar sebelum atau selanjutnya
tidak ditandatangani."*
"""
from ttd_kelengkapan import (
    MAKS_TTD_PER_ORANG, jumlah_pembubuhan, kurang_pembubuhan,
    normalisasi_jumlah_ttd, pesan_kurang,
)

POS = {"halaman": 1, "x": 0.5, "y": 0.7, "lebar": 0.3}


class TestNormalisasi:
    def test_angka_wajar_dipakai_apa_adanya(self):
        assert normalisasi_jumlah_ttd(1) == 1
        assert normalisasi_jumlah_ttd(3) == 3
        assert normalisasi_jumlah_ttd("3") == 3

    def test_kosong_jatuh_ke_satu(self):
        """Permintaan LAMA tak punya field ini; ia harus tetap berjalan
        persis seperti dulu, bukan mendadak ditolak."""
        for v in (None, "", "abc", [], {}, float("nan")):
            assert normalisasi_jumlah_ttd(v) == 1, v

    def test_nol_dan_negatif_jatuh_ke_satu(self):
        # 0 berarti "tak perlu meneken sama sekali" — itu bukan penanda
        # tangan, dan menerimanya membuat kiriman kosong lolos.
        assert normalisasi_jumlah_ttd(0) == 1
        assert normalisasi_jumlah_ttd(-5) == 1

    def test_dibatasi_agar_tak_ada_yang_mustahil_dipenuhi(self):
        assert normalisasi_jumlah_ttd(9999) == MAKS_TTD_PER_ORANG

    def test_pecahan_dipotong_bukan_dibulatkan_naik(self):
        # 2,9 tempat tak ada artinya; menuntut 3 akan menahan orang atas
        # angka yang tak pernah dideklarasikan siapa pun.
        assert normalisasi_jumlah_ttd(2.9) == 2


class TestJumlahPembubuhan:
    def test_posisi_utama_terhitung_satu(self):
        assert jumlah_pembubuhan(POS, []) == 1

    def test_posisi_lain_ikut_terhitung(self):
        assert jumlah_pembubuhan(POS, [POS, POS]) == 3

    def test_tanpa_posisi_utama_tak_terhitung(self):
        # `_posisi_bersih` mengembalikan None untuk kiriman cacat; kalau ia
        # tetap terhitung, kiriman rusak akan lolos sebagai "lengkap".
        assert jumlah_pembubuhan(None, [POS]) == 1
        assert jumlah_pembubuhan(None, []) == 0

    def test_posisi_lain_cacat_tak_melempar(self):
        assert jumlah_pembubuhan(POS, None) == 1
        assert jumlah_pembubuhan(POS, "bukan daftar") == 1


class TestKurangPembubuhan:
    def test_lengkap_tak_kurang(self):
        assert kurang_pembubuhan(3, POS, [POS, POS]) == 0

    def test_kurang_dihitung_tepat(self):
        assert kurang_pembubuhan(3, POS, []) == 2
        assert kurang_pembubuhan(3, POS, [POS]) == 1

    def test_LEBIH_dari_wajib_TIDAK_ditolak(self):
        """Membubuhkan lebih banyak adalah tindakan sengaja dan tetap terlihat
        di dokumen. Menolaknya hanya mengembalikan masalah yang sama dari arah
        sebaliknya — orang dipaksa mengulang karena melakukan hal yang benar."""
        assert kurang_pembubuhan(2, POS, [POS, POS, POS]) == 0

    def test_permintaan_lama_satu_pembubuhan_tetap_lolos(self):
        assert kurang_pembubuhan(None, POS, []) == 0


class TestPesanKurang:
    def test_lengkap_tak_berpesan(self):
        assert pesan_kurang(2, POS, [POS]) == ""

    def test_menyebut_angka_yang_BENAR(self):
        p = pesan_kurang(3, POS, [])
        assert "3 tanda tangan" in p
        assert "baru 1" in p
        assert "2 lagi" in p

    def test_menyebut_NAMA_TOMBOL_yang_harus_ditekan(self):
        # Penolakan yang hanya berkata "kurang" membuat orang menekan tombol
        # yang sama berulang kali.
        assert "Tanda tangan lagi" in pesan_kurang(2, POS, [])

    def test_menerangkan_kenapa_tak_bisa_diperbaiki_nanti(self):
        """Tanpa ini, orang akan mengira bisa membubuhkan sisanya belakangan
        — dan itulah persis kekeliruan yang melahirkan masalahnya."""
        p = pesan_kurang(2, POS, [])
        assert "tertutup" in p and "tak bisa ditambahkan" in p

    def test_kiriman_KOSONG_juga_ditolak(self):
        assert pesan_kurang(1, None, []) != ""
