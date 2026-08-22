"""Area tanda tangan sama tinggi di semua kolom.

Permintaan pemilik: *"benahi kolom tanda tangan agar mendapatkan area tanda
tangan yang sama."*

Blok tanda tangan sudah lama disusun sebagai tabel TIGA ZONA (kepala / tanda
tangan / nama) supaya baris nama dan NIP antar kolom selalu sejajar. Yang belum
seragam **zona tengahnya sendiri**: bila kolom itu membawa spesimen tanda
tangan digital, tingginya mengikuti RASIO gambarnya.

Akibatnya kolom bertanda tangan lebar-pendek punya area pena jauh lebih tipis
daripada kolom di sebelahnya yang tinggi — atau yang masih kosong dan memakai
celah penuh. Baris namanya tetap sejajar (tabel tiga zona menjaganya), jadi
cacat ini tak terlihat dari mana pun kecuali dari dokumen tercetak.

Perbaikannya: zona itu SELALU setinggi `celah_mm`, dan sisa ruang di bawah
gambar diisi.
"""
import pytest

from routes.reports import ukuran_zona_ttd

ZONA = 60.0
LEBAR_MAKS = 200.0


class TestUkuranZonaTtd:
    def test_gambar_lebar_pendek_menyisakan_ruang_untuk_diisi(self):
        """Inilah kasus yang membuat area pena tipis sendiri."""
        w, h, sisa = ukuran_zona_ttd(300, 100, LEBAR_MAKS, ZONA)
        assert (w, h) == (180.0, 60.0)
        assert h + sisa == ZONA

    def test_gambar_tinggi_dijepit_tingginya(self):
        w, h, sisa = ukuran_zona_ttd(100, 300, LEBAR_MAKS, ZONA)
        assert h == ZONA and sisa == 0.0
        assert w <= LEBAR_MAKS

    def test_gambar_kecil_TIDAK_diperbesar(self):
        """Spesimen beresolusi kecil yang dipaksa melar akan tercetak pecah
        pada dokumen resmi."""
        w, h, sisa = ukuran_zona_ttd(50, 20, LEBAR_MAKS, ZONA)
        assert (w, h) == (50.0, 20.0)
        assert sisa == ZONA - 20.0

    @pytest.mark.parametrize("lw,lh", [(300, 100), (100, 300), (50, 20),
                                       (120, 40), (40, 120), (0, 0)])
    def test_tinggi_gambar_DITAMBAH_sisa_selalu_setinggi_zona(self, lw, lh):
        """Satu invarian yang menjawab seluruh permintaannya: apa pun rasio
        spesimennya, zona itu setinggi yang sama."""
        _, h, sisa = ukuran_zona_ttd(lw, lh, LEBAR_MAKS, ZONA)
        assert h + sisa == pytest.approx(ZONA)

    def test_rasio_gambar_terjaga(self):
        w, h, _ = ukuran_zona_ttd(300, 100, LEBAR_MAKS, ZONA)
        assert w / h == pytest.approx(3.0)

    def test_ukuran_tak_masuk_akal_tak_meledak(self):
        assert ukuran_zona_ttd(0, 0, LEBAR_MAKS, ZONA) == (0.0, 0.0, ZONA)
        assert ukuran_zona_ttd(None, None, LEBAR_MAKS, ZONA) == (0.0, 0.0, ZONA)
        assert ukuran_zona_ttd(100, 100, LEBAR_MAKS, 0) == (0.0, 0.0, 0.0)

    def test_tak_pernah_melebihi_lebar_maksimal(self):
        for lw in (100, 500, 5000):
            w, _, _ = ukuran_zona_ttd(lw, 100, LEBAR_MAKS, ZONA)
            assert w <= LEBAR_MAKS + 1e-9, lw


class TestZonaTerpakaiDiBlokTandaTangan:
    def test_zona_ttd_memakai_helpernya_bukan_hitungan_sendiri(self):
        """Hitungan yang disalin ke dalam badan `_signature_block` akan luput
        dari uji di atas — dan zona yang tak seragam tak terlihat dari mana
        pun kecuali dari dokumen tercetak."""
        import inspect

        from routes.reports import _signature_block
        sumber = inspect.getsource(_signature_block)
        assert "ukuran_zona_ttd(" in sumber
        # Sisa ruang WAJIB diisi — tanpa ini helper-nya benar tapi zonanya
        # tetap menyusut mengikuti gambar.
        assert "Spacer(1, sisa)" in sumber
