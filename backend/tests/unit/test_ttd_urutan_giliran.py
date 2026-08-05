"""Alur BERURUTAN: giliran maju ke `urutan`, bukan ke posisi array.

Mandat pemilik: "cek alur urutan tanda tangan ... cukup hanya berurutan".
Yang paralel sudah teruji dan tak disentuh.
"""
from routes.ttd import _nomor_urut


def _pilih_berikutnya(signers):
    """Cerminan logika produksi: kandidat 'menunggu' dengan `urutan` terkecil."""
    return min((s for s in signers if s.get("status") == "menunggu"),
               key=_nomor_urut, default=None)


class TestNomorUrut:
    def test_membaca_urutan(self):
        assert _nomor_urut({"urutan": 2}) == 2.0

    def test_tanpa_urutan_jatuh_ke_belakang_antrean(self):
        """Data lama/hasil restore tanpa `urutan` tak boleh menyerobot."""
        assert _nomor_urut({}) == float("inf")
        assert _nomor_urut({"urutan": None}) == float("inf")

    def test_urutan_rusak_tak_melempar(self):
        assert _nomor_urut({"urutan": "bukan angka"}) == float("inf")


class TestGiliranBerikutnya:
    def test_array_searah_urutan_memilih_yang_pertama(self):
        s = [{"urutan": 1, "status": "ditandatangani"},
             {"urutan": 2, "status": "menunggu"},
             {"urutan": 3, "status": "menunggu"}]
        assert _pilih_berikutnya(s)["urutan"] == 2

    def test_array_TERSUSUN_ULANG_tetap_memilih_urutan_terkecil(self):
        """Inti perbaikannya. Dulu pemilihnya memakai posisi array, jadi
        susunan yang tak lagi searah `urutan` (restore, perbaikan manual,
        fitur ubah-urutan kelak) mengaktifkan ORANG YANG SALAH — tanpa galat,
        tanpa jejak."""
        s = [{"urutan": 3, "status": "menunggu"},
             {"urutan": 1, "status": "ditandatangani"},
             {"urutan": 2, "status": "menunggu"}]
        assert _pilih_berikutnya(s)["urutan"] == 2

    def test_semua_sudah_meneken_tak_ada_giliran_berikutnya(self):
        s = [{"urutan": 1, "status": "ditandatangani"},
             {"urutan": 2, "status": "ditandatangani"}]
        assert _pilih_berikutnya(s) is None

    def test_yang_aktif_tak_ikut_dipilih_ulang(self):
        """Hanya berstatus 'menunggu' yang jadi kandidat; yang sudah 'aktif'
        tak boleh diaktifkan lagi (dan tak menggeser giliran)."""
        s = [{"urutan": 1, "status": "aktif"},
             {"urutan": 2, "status": "menunggu"}]
        assert _pilih_berikutnya(s)["urutan"] == 2

    def test_campuran_ber_urutan_dan_tanpa_urutan(self):
        s = [{"status": "menunggu"},                 # tanpa urutan → +inf
             {"urutan": 5, "status": "menunggu"}]
        assert _pilih_berikutnya(s)["urutan"] == 5

    def test_hanya_tersisa_yang_tanpa_urutan_tetap_terpilih(self):
        """Jangan sampai dokumen menggantung selamanya hanya karena field
        `urutan` hilang pada satu-satunya orang yang tersisa."""
        s = [{"urutan": 1, "status": "ditandatangani"},
             {"status": "menunggu", "nama": "Tanpa Urutan"}]
        assert _pilih_berikutnya(s)["nama"] == "Tanpa Urutan"
