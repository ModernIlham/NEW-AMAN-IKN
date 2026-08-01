"""Uji catatan diagnostik layanan kompresi gambar."""
import pytest

from kompresi_diagnostik import (
    STATUS_BELUM_DICOBA, STATUS_BERHASIL, STATUS_GAGAL, STATUS_TAK_DISETEL,
    ambil_status, catat_percobaan, reset_status, ringkas_layanan,
)


@pytest.fixture(autouse=True)
def bersih():
    reset_status()
    yield
    reset_status()


class TestCatatPercobaan:
    def test_percobaan_berhasil_tercatat(self):
        catat_percobaan("compresto", True, waktu="2026-08-01T10:00:00Z")
        rec = ambil_status("compresto")
        assert rec["status"] == STATUS_BERHASIL
        assert rec["waktu"] == "2026-08-01T10:00:00Z"

    def test_percobaan_gagal_menyimpan_alasan_dan_kode(self):
        catat_percobaan("compresto", False, alasan="Kunci API ditolak",
                        kode_http=401, waktu="2026-08-01T10:00:00Z")
        rec = ambil_status("compresto")
        assert rec["status"] == STATUS_GAGAL
        assert rec["kode_http"] == 401
        assert "ditolak" in rec["alasan"]

    def test_percobaan_terbaru_menimpa_yang_lama(self):
        catat_percobaan("compresto", False, alasan="gagal", kode_http=500)
        catat_percobaan("compresto", True)
        assert ambil_status("compresto")["status"] == STATUS_BERHASIL

    def test_alasan_panjang_dipangkas_agar_tak_membanjiri_respons(self):
        catat_percobaan("compresto", False, alasan="x" * 1000)
        assert len(ambil_status("compresto")["alasan"]) == 300

    def test_layanan_berbeda_tak_saling_mengganggu(self):
        catat_percobaan("compresto", False, alasan="gagal")
        catat_percobaan("uploadcare", True)
        assert ambil_status("compresto")["status"] == STATUS_GAGAL
        assert ambil_status("uploadcare")["status"] == STATUS_BERHASIL

    def test_belum_pernah_dicoba_mengembalikan_None(self):
        assert ambil_status("compresto") is None

    def test_ambil_status_mengembalikan_SALINAN(self):
        # Pemanggil tak boleh bisa merusak catatan internal.
        catat_percobaan("compresto", True)
        rec = ambil_status("compresto")
        rec["status"] = "dirusak"
        assert ambil_status("compresto")["status"] == STATUS_BERHASIL


class TestRingkasLayanan:
    def test_kunci_belum_dipasang(self):
        r = ringkas_layanan("compresto", kunci_terpasang=False,
                            kuota_terpakai=0, kuota_batas=500)
        assert r["status"] == STATUS_TAK_DISETEL
        assert r["tersedia"] is False
        assert ".env" in r["alasan"]

    def test_kunci_terpasang_tapi_belum_dicoba_TIDAK_diklaim_tersedia(self):
        # Inilah kebohongan lama: `available = bool(API_KEY)`. Kunci terisi
        # bukan bukti layanannya menjawab.
        r = ringkas_layanan("compresto", kunci_terpasang=True,
                            kuota_terpakai=0, kuota_batas=500)
        assert r["status"] == STATUS_BELUM_DICOBA
        assert r["tersedia"] is False

    def test_tersedia_hanya_setelah_percobaan_BERHASIL(self):
        catat_percobaan("compresto", True, waktu="2026-08-01T10:00:00Z")
        r = ringkas_layanan("compresto", True, 3, 500)
        assert r["tersedia"] is True
        assert r["status"] == STATUS_BERHASIL
        assert r["waktu_percobaan_terakhir"] == "2026-08-01T10:00:00Z"

    def test_gagal_membawa_sebab_sampai_ke_layar(self):
        catat_percobaan("compresto", False, alasan="Host tidak dapat dihubungi",
                        kode_http=None)
        r = ringkas_layanan("compresto", True, 0, 500)
        assert r["tersedia"] is False
        assert r["status"] == STATUS_GAGAL
        assert "Host" in r["alasan"]

    def test_hitungan_kuota_ikut_dilaporkan(self):
        r = ringkas_layanan("uploadcare", True, kuota_terpakai=120, kuota_batas=1000)
        assert r["used"] == 120 and r["limit"] == 1000 and r["remaining"] == 880

    def test_sisa_kuota_tak_pernah_negatif(self):
        r = ringkas_layanan("uploadcare", True, kuota_terpakai=1200, kuota_batas=1000)
        assert r["remaining"] == 0
