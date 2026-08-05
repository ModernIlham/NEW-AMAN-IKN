"""Sisa kuota Tinify lebih baik dipakai daripada hangus — tanpa membengkakkan disk.

Permintaan pemilik:

  • Sepanjang bulan: cicil sedikit demi sedikit di jam sepi (perilaku lama,
    bantalan kuota `KUOTA_SISA_MIN` dijaga) supaya akhir bulan tak kerja keras.
  • H-1 pergantian bulan: habiskan sisa kuota — besok ia hangus.
  • Bila semua foto sudah WebP: pakai sisa kuota untuk MENGONVERSI ULANG,
    berhenti per gambar saat hematnya < 1%.
  • Bila SEMUA sudah di bawah 1%: tak melakukan apa-apa sampai ada aset baru.
  • Jangan sampai gambar rusak atau disk membengkak.

Yang terakhir itu menutup lubang LAMA yang tak dilaporkan: `_proses_satu`
dulu menukar blob tanpa membandingkan ukuran sama sekali — sebuah JPEG bisa
digantikan WebP yang JUSTRU lebih besar, sehingga penyimpanan bertambah
padahal tujuannya menyusut. (Fase thumbnail sudah punya penjaga ini; fase
foto asli belum.)
"""
import os
from datetime import datetime, timedelta, timezone

from webp_converter import (AMBANG_HEMAT_ULANG, KUOTA_SISA_MIN, SUMBER, WIB,
                            ambang_kuota_sisa, hari_terakhir_bulan,
                            hemat_persen, layak_ganti)


def _wib(y, m, d, jam=10):
    return datetime(y, m, d, jam, tzinfo=WIB)


class TestHariTerakhirBulan:
    def test_akhir_bulan_31_hari(self):
        assert hari_terakhir_bulan(_wib(2026, 1, 31))
        assert not hari_terakhir_bulan(_wib(2026, 1, 30))

    def test_akhir_bulan_30_hari(self):
        assert hari_terakhir_bulan(_wib(2026, 4, 30))
        assert not hari_terakhir_bulan(_wib(2026, 4, 29))

    def test_februari_biasa(self):
        assert hari_terakhir_bulan(_wib(2026, 2, 28))

    def test_februari_kabisat(self):
        """Tabel jumlah hari yang di-hardcode akan salah di sini; memakai
        'besok bulannya berbeda' otomatis benar."""
        assert hari_terakhir_bulan(_wib(2024, 2, 29))
        assert not hari_terakhir_bulan(_wib(2024, 2, 28))

    def test_pergantian_tahun(self):
        assert hari_terakhir_bulan(_wib(2026, 12, 31))

    def test_none_aman(self):
        assert hari_terakhir_bulan(None) is False


class TestAmbangKuota:
    def test_hari_terakhir_melepas_bantalan(self):
        """Inti permintaan: sisa kuota dipakai habis, bukan dibiarkan hangus."""
        assert ambang_kuota_sisa(_wib(2026, 1, 31)) == 0

    def test_hari_biasa_menjaga_bantalan(self):
        """Cicilan: bantalan dijaga supaya unggahan user yang butuh Tinify tak
        kehabisan di tengah bulan."""
        assert ambang_kuota_sisa(_wib(2026, 1, 15)) == KUOTA_SISA_MIN
        assert KUOTA_SISA_MIN > 0, "bantalan 0 sepanjang bulan = tak ada cicilan"

    def test_ambang_normal_bisa_dioper(self):
        assert ambang_kuota_sisa(_wib(2026, 1, 15), 10) == 10
        assert ambang_kuota_sisa(_wib(2026, 1, 31), 10) == 0


class TestHematPersen:
    def test_hitungan_dasar(self):
        assert hemat_persen(1000, 900) == 10.0
        assert hemat_persen(1000, 500) == 50.0

    def test_membesar_bernilai_negatif(self):
        assert hemat_persen(1000, 1200) < 0

    def test_sumber_nol_tak_meledak(self):
        assert hemat_persen(0, 100) == 0.0
        assert hemat_persen(None, 100) == 0.0
        assert hemat_persen("x", 100) == 0.0


class TestLayakGanti:
    def test_konversi_pertama_menolak_hasil_yang_membesar(self):
        """PENJAGA DISK. Tanpa ini foto digantikan blob yang lebih besar dan
        penyimpanan bertambah — persis yang pemilik minta dihindari."""
        assert not layak_ganti(1000, 1200, 0.0)
        assert not layak_ganti(1000, 1000, 0.0), "sama besar = tak ada gunanya"
        assert layak_ganti(1000, 999, 0.0)

    def test_konversi_ulang_menuntut_hemat_berarti(self):
        assert not layak_ganti(1000, 995, AMBANG_HEMAT_ULANG)   # 0,5% → tolak
        assert layak_ganti(1000, 989, AMBANG_HEMAT_ULANG)       # 1,1% → terima

    def test_ambang_ulang_satu_persen(self):
        assert AMBANG_HEMAT_ULANG == 1.0

    def test_hasil_kosong_ditolak(self):
        assert not layak_ganti(1000, 0, 0.0)
        assert not layak_ganti(1000, None, 0.0)


class TestSumberKonversiUlang:
    """Fase 3 hanya berjalan setelah fase 1–2 habis (urutan SUMBER = prioritas),
    dan menandai blob yang sudah mentok agar tak dicoba selamanya."""

    def _cari(self, nama):
        return next(s for s in SUMBER if s["nama"] == nama)

    def test_fase_ulang_ada_dan_di_urutan_terakhir(self):
        nama = [s["nama"] for s in SUMBER]
        assert "aset_ulang" in nama and "pegawai_ulang" in nama
        # Foto yang BELUM WebP harus selalu didahulukan.
        assert nama.index("aset") < nama.index("aset_ulang")
        assert nama.index("pegawai") < nama.index("pegawai_ulang")

    def test_fase_ulang_hanya_menyasar_webp(self):
        for n in ("aset_ulang", "pegawai_ulang"):
            q = self._cari(n)["query"]
            assert q["metadata.content_type"] == "image/webp", n

    def test_fase_pertama_tak_menyentuh_webp(self):
        """Kalau fase pertama ikut menyasar WebP, ia akan mengonversi ulang
        tanpa ambang 1% dan membakar kuota tanpa henti."""
        for n in ("aset", "pegawai", "pegawai_asli"):
            ct = self._cari(n)["query"]["metadata.content_type"]
            nilai = ct if isinstance(ct, str) else ct.get("$in", [])
            assert "image/webp" not in nilai, n

    def test_blob_mentok_disaring_dari_kandidat(self):
        """Tanpa penyaring ini konverter mengulang blob yang sama tiap putaran
        dan kuota habis tanpa hasil."""
        for n in ("aset_ulang", "pegawai_ulang"):
            q = self._cari(n)["query"]
            assert q["metadata.webp_ulang_selesai"] == {"$ne": True}, n

    def test_fase_ulang_memakai_ambang_dan_penanda(self):
        for n in ("aset_ulang", "pegawai_ulang"):
            s = self._cari(n)
            assert s["ambang_hemat"] == AMBANG_HEMAT_ULANG, n
            assert s["tanda_selesai"] == "webp_ulang_selesai", n

    def test_fase_pertama_tak_menandai_selesai_ulang(self):
        """Blob yang baru dikonversi pertama kali harus TETAP boleh dicoba
        ulang nanti; menandainya selesai akan mengunci mereka selamanya."""
        for n in ("aset", "pegawai", "pegawai_asli"):
            assert self._cari(n).get("tanda_selesai") in (None, "webp_skip"), n


class TestLoopTerpasang:
    _MOD = os.path.join(os.path.dirname(__file__), "..", "..", "webp_converter.py")

    def _src(self):
        with open(os.path.abspath(self._MOD), encoding="utf-8") as f:
            return f.read()

    def test_loop_memakai_ambang_dinamis(self):
        """Konstanta mati di loop = bantalan tak pernah dilepas, sisa kuota
        tetap hangus tiap bulan."""
        src = self._src()
        assert "ambang_kuota_sisa(datetime.now(WIB))" in src
        loop = src.split("async def _loop", 1)[1]
        assert "> KUOTA_SISA_MIN" not in loop

    def test_gerbang_disk_terpasang_sebelum_swap(self):
        src = self._src()
        proses = src.split("async def _proses_satu", 1)[1].split("\nasync def ", 1)[0]
        assert "layak_ganti(" in proses
        # Harus SEBELUM penyimpanan blob baru — kalau tidak, blob sampah
        # terlanjur ditulis ke disk tiap kali hematnya tipis.
        assert proses.index("layak_ganti(") < proses.index("_simpan_webp(")

    def test_idle_dan_lease_tetap_dihormati(self):
        """Cicilan hanya boleh jalan saat sepi — jangan sampai perubahan ini
        membuatnya bekerja di jam sibuk."""
        loop = self._src().split("async def _loop", 1)[1]
        assert "aplikasi_idle(IDLE_DETIK)" in loop
        assert "_pegang_lease()" in loop
