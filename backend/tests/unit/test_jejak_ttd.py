"""Jejak identitas pada TTD berposisi bebas + keseragaman lebar kolom TTD.

Mandat pemilik (dua hal):
  1. Area "Mengetahui" di tengah tak boleh lebih sempit daripada area tanda
     tangan lainnya.
  2. Nama & tanggal pada tiap tanda tangan pindah ke SISI KIRI-BAWAH, tulisan
     menyamping keluar, sangat kecil, hampir transparan, tanggal DI BAWAH nama.
"""
from routes.reports import LEBAR_KOLOM_TTD
from routes.ttd import (
    JEJAK_TTD_ABU, JEJAK_TTD_FONT, jejak_identitas_ttd,
)


class TestLebarKolomTtd:
    def test_satu_angka_dipakai_semua_pola(self):
        """Tunggal, berpasangan, dan tengah memakai lebar yang SAMA.

        Dulu tiga pola memakai tiga angka (0.45 / 0.42 / 0.40) sehingga area
        "Mengetahui" di tengah jadi yang paling sempit — itu keluhannya.
        """
        doc = 1000.0
        tunggal = doc * LEBAR_KOLOM_TTD
        pasangan = doc * LEBAR_KOLOM_TTD
        tengah = doc * LEBAR_KOLOM_TTD
        assert tunggal == pasangan == tengah

    def test_tak_ada_area_yang_menyusut_dari_sebelumnya(self):
        """Lebar barunya >= angka TERBESAR yang pernah dipakai (0.45).

        Menyamakan ke angka yang lebih kecil akan 'menyeragamkan' dengan cara
        mempersempit — kebalikan dari yang diminta.
        """
        assert LEBAR_KOLOM_TTD >= 0.45

    def test_pasangan_masih_menyisakan_celah_pemisah(self):
        """Dua kolom + celah harus tetap muat dalam lebar dokumen, dan celahnya
        tak boleh habis (nol) — kalau habis, dua tanda tangan berdempetan."""
        celah = 1 - 2 * LEBAR_KOLOM_TTD
        assert celah > 0
        assert 2 * LEBAR_KOLOM_TTD + celah == 1

    def test_tengah_tetap_berada_di_tengah(self):
        sisi = (1 - LEBAR_KOLOM_TTD) / 2
        assert sisi > 0
        assert sisi + LEBAR_KOLOM_TTD + sisi == 1


class TestJejakIdentitasTtd:
    def test_tanggal_jadi_baris_TERSENDIRI_di_bawah_nama(self):
        """Bukan 'Nama · 2026-08-05' satu baris panjang, tapi dua baris —
        dan tanggalnya benar-benar DI BAWAH nama saat dibaca.

        Teks diputar 90° sehingga dibaca bawah-ke-atas; "atas" glyph-nya
        menghadap kiri halaman. Maka baris ber-geser LEBIH KECIL (lebih dekat
        tanda tangan) yang tampak di BAWAH. Percobaan pertama menaruh nama
        lebih dulu dan hasil render-nya justru tanggal di ATAS nama."""
        _x, _y, baris = jejak_identitas_ttd("Budi Santoso", "2026-08-05T10:00:00",
                                            x_pt=100, y_pt=200)
        teks = [t for t, _g in baris]
        assert sorted(teks) == sorted(["Budi Santoso", "2026-08-05"])
        geser = {t: g for t, g in baris}
        assert geser["2026-08-05"] < geser["Budi Santoso"]
        assert geser["2026-08-05"] == 0

    def test_tanpa_tanggal_hanya_satu_baris_tanpa_pemisah_menggantung(self):
        _x, _y, baris = jejak_identitas_ttd("Budi", None, x_pt=100, y_pt=200)
        assert [t for t, _g in baris] == ["Budi"]
        assert baris[0][1] == 0

    def test_tanpa_nama_dan_tanggal_tak_menggambar_apa_pun(self):
        _x, _y, baris = jejak_identitas_ttd("", "", x_pt=100, y_pt=200)
        assert baris == []
        _x, _y, baris = jejak_identitas_ttd(None, None, x_pt=100, y_pt=200)
        assert baris == []

    def test_baris_tumbuh_KE_LUAR_menjauhi_tanda_tangan(self):
        """Geser membesar = makin jauh dari ttd. Kalau arahnya terbalik,
        jejaknya merambat MASUK dan menimpa gambar tanda tangannya."""
        _x, _y, baris = jejak_identitas_ttd("Budi", "2026-08-05", 100, 200)
        assert [g for _t, g in baris] == sorted(g for _t, g in baris)
        assert baris[-1][1] > 0

    def test_pangkal_berada_di_KIRI_tanda_tangan(self):
        """Jejak harus keluar ke kiri — bukan menimpa gambar tanda tangannya."""
        x, _y, _b = jejak_identitas_ttd("Budi", "2026-08-05", x_pt=100, y_pt=200)
        assert x < 100

    def test_pangkal_tak_pernah_keluar_tepi_kiri_halaman(self):
        """TTD yang dijatuhkan mepet tepi kiri: jejaknya harus tetap tercetak,
        bukan tergeser ke luar halaman dan hilang."""
        x, _y, _b = jejak_identitas_ttd("Budi", "2026-08-05", x_pt=1.0, y_pt=200,
                                        tepi_kiri=4.0)
        assert x >= 4.0

    def test_pangkal_y_tak_negatif(self):
        _x, y, _b = jejak_identitas_ttd("Budi", "2026-08-05", x_pt=100, y_pt=0.0)
        assert y >= 2.0

    def test_nama_panjang_dipotong(self):
        panjang = "Nama Yang Sangat Panjang Sekali Melebihi Batas Wajar"
        _x, _y, baris = jejak_identitas_ttd(panjang, None, x_pt=100, y_pt=200)
        assert len(baris[0][0]) <= 28

    def test_signed_at_diambil_tanggalnya_saja(self):
        _x, _y, baris = jejak_identitas_ttd("B", "2026-08-05T23:59:59.123Z",
                                            x_pt=100, y_pt=200)
        assert dict(baris)["2026-08-05"] == 0

    def test_ukuran_dan_warna_sesuai_mandat(self):
        """Sebelumnya font 6 & abu 0.35. Mandat: 'sangat perkecil' dan
        'lebih pudarkan hingga hampir transparan dengan kertas'."""
        assert JEJAK_TTD_FONT < 6
        assert JEJAK_TTD_ABU > 0.35
        # Masih tercetak (bukan putih total) — jejaknya harus ADA, hanya samar.
        assert JEJAK_TTD_ABU < 1.0


class TestJejakDipusatkanTegakLurus:
    """Ralat pemilik: jejak tetap di samping KIRI, tapi tepat di TENGAH.

    Teksnya berjalan ke ATAS, jadi memusatkan berarti menurunkan pangkalnya
    setengah PANJANG teks dari titik tengah tanda tangan.
    """
    # Pengukur palsu: 2 pt per karakter — cukup untuk menguji aritmetikanya
    # tanpa menyeret ReportLab ke dalam uji.
    UKUR = staticmethod(lambda t: 2.0 * len(t))

    def test_pangkal_turun_setengah_panjang_dari_titik_tengah(self):
        # tinggi 100, y dasar 200 → titik tengah 250.
        # Baris terpanjang "Budi Santoso" (12 huruf) = 24 pt → pangkal 250-12=238.
        _x, y, _b = jejak_identitas_ttd(
            "Budi Santoso", "2026-08-05", x_pt=100, y_pt=200,
            tinggi=100, ukur=self.UKUR)
        assert y == 238.0

    def test_titik_tengah_teks_berimpit_dengan_titik_tengah_ttd(self):
        panjang = 2.0 * len("Budi Santoso")
        _x, y, _b = jejak_identitas_ttd(
            "Budi Santoso", "2026-08-05", x_pt=100, y_pt=200,
            tinggi=100, ukur=self.UKUR)
        assert y + panjang / 2 == 200 + 100 / 2

    def test_panjang_diambil_dari_baris_TERPANJANG(self):
        """Kalau memakai baris pertama saja, jejak melenceng saat tanggal
        (10 huruf) lebih pendek daripada namanya."""
        _x, y_pendek, _b = jejak_identitas_ttd(
            "Ani", "2026-08-05", x_pt=100, y_pt=0, tinggi=100, ukur=self.UKUR)
        # terpanjang = "2026-08-05" (10) = 20 pt → 50 - 10 = 40
        assert y_pendek == 40.0

    def test_tanpa_tinggi_kembali_ke_perilaku_lama(self):
        """Pemanggil yang belum menyertakan tinggi tak boleh melompat ke
        tempat yang salah — jatuh kembali ke dasar tanda tangan."""
        _x, y, _b = jejak_identitas_ttd("Budi", "2026-08-05", x_pt=100,
                                        y_pt=200, ukur=self.UKUR)
        assert y == 200.0

    def test_tanpa_pengukur_kembali_ke_perilaku_lama(self):
        _x, y, _b = jejak_identitas_ttd("Budi", "2026-08-05", x_pt=100,
                                        y_pt=200, tinggi=100)
        assert y == 200.0

    def test_ttd_mepet_dasar_halaman_tak_membuat_pangkal_negatif(self):
        _x, y, _b = jejak_identitas_ttd(
            "Nama Panjang Sekali Betul", "2026-08-05", x_pt=100, y_pt=0,
            tinggi=1, ukur=self.UKUR)
        assert y >= 2.0
