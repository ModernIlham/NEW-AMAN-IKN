"""Rantai kompresi berjenjang — layanan mana yang MELAYANI permintaan berikutnya.

Laporan pemilik: indikator kuota menunjukkan **0/500** padahal Compresto masih
menyisakan 474. Rantainya sendiri sehat; yang keliru pemilihan layanannya —
indikator memakai `available` ("percobaan terakhir terbukti berhasil", catatan
di memori proses yang hangus tiap restart) untuk menjawab pertanyaan yang
berbeda: "siapa giliran berikutnya".

Berkas ini mengunci jawaban yang benar, dan menjaga rantai di `routes/media.py`
tetap sejalan dengan urutan yang dipakai layar.
"""
import os
import re

import pytest

from kompresi_rantai import URUTAN, layak_pakai, layanan_aktif, sisa_layanan

BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _entri(service, terpasang=True, limit=500, used=0, remaining=None, **lain):
    e = {"service": service, "terpasang": terpasang, "limit": limit, "used": used}
    if remaining is not None:
        e["remaining"] = remaining
    e.update(lain)
    return e


def _pillow(terpasang=True):
    return _entri("pillow", terpasang=terpasang, limit=-1, used=0, remaining=-1)


# ---------------------------------------------------------------------------
# Keadaan yang dilaporkan dari lapangan
# ---------------------------------------------------------------------------

class TestKeadaanLapangan:
    """Data persis seperti pada layar pemilik: Tinify habis, Compresto sisa 474."""

    _KUOTA = [
        _entri("tinify", limit=500, used=500, remaining=0, available=True),
        # `available` False karena catatan diagnostik hilang saat server restart
        _entri("compresto", limit=500, used=26, remaining=474, available=False),
        _entri("uploadcare", terpasang=False, limit=1000, used=0, remaining=1000,
               available=False),
        _pillow(),
    ]

    def test_beralih_ke_compresto_bukan_bertahan_di_tinify(self):
        assert layanan_aktif(self._KUOTA) == "compresto"

    def test_available_palsu_tidak_menggugurkan_giliran(self):
        """INTI CACATNYA. `available` menjawab 'sudah terbukti berhasil' —
        pertanyaan yang berbeda, dan jawabannya hilang tiap kali server
        restart. Memakainya di sini membuat layanan sehat tampak mati."""
        assert self._KUOTA[1]["available"] is False
        assert layak_pakai(self._KUOTA[1]) is True

    def test_kuota_habis_menggugurkan_giliran(self):
        assert layak_pakai(self._KUOTA[0]) is False

    def test_kunci_belum_dipasang_menggugurkan_giliran(self):
        assert layak_pakai(self._KUOTA[2]) is False


# ---------------------------------------------------------------------------
# Berjenjang sesuai permintaan: Tinify → Compresto → Uploadcare → Pillow
# ---------------------------------------------------------------------------

class TestBerjenjang:
    def test_semua_sehat_memakai_yang_pertama(self):
        assert layanan_aktif([
            _entri("tinify", remaining=500), _entri("compresto", remaining=500),
            _entri("uploadcare", limit=1000, remaining=1000), _pillow(),
        ]) == "tinify"

    def test_tinify_habis_turun_ke_compresto(self):
        assert layanan_aktif([
            _entri("tinify", used=500, remaining=0), _entri("compresto", remaining=500),
            _entri("uploadcare", limit=1000, remaining=1000), _pillow(),
        ]) == "compresto"

    def test_tinify_dan_compresto_habis_turun_ke_uploadcare(self):
        assert layanan_aktif([
            _entri("tinify", used=500, remaining=0),
            _entri("compresto", used=500, remaining=0),
            _entri("uploadcare", limit=1000, remaining=1000), _pillow(),
        ]) == "uploadcare"

    def test_semua_kuota_habis_jatuh_ke_pillow(self):
        """Permintaan pemilik: "…dan menggunakan pillow". Pillow tak berkuota,
        jadi tak pernah ada keadaan "tak bisa mengompres sama sekali"."""
        assert layanan_aktif([
            _entri("tinify", used=500, remaining=0),
            _entri("compresto", used=500, remaining=0),
            _entri("uploadcare", limit=1000, used=1000, remaining=0), _pillow(),
        ]) == "pillow"

    def test_layanan_tanpa_kunci_dilewati_walau_kuotanya_penuh(self):
        assert layanan_aktif([
            _entri("tinify", terpasang=False, remaining=500),
            _entri("compresto", terpasang=False, remaining=500),
            _entri("uploadcare", terpasang=False, limit=1000, remaining=1000),
            _pillow(),
        ]) == "pillow"

    def test_urutan_daftar_masukan_tidak_menentukan(self):
        """Endpoint boleh menyusun daftarnya sesuka hati; prioritas datang dari
        `URUTAN`. Tanpa ini, penyusunan ulang daftar diam-diam mengubah rantai."""
        terbalik = [
            _pillow(), _entri("uploadcare", limit=1000, remaining=1000),
            _entri("compresto", remaining=500), _entri("tinify", remaining=500),
        ]
        assert layanan_aktif(terbalik) == "tinify"

    def test_layanan_asing_tak_pernah_mendahului_rantai_baku(self):
        asing = _entri("layanan_baru", remaining=500)
        assert layanan_aktif([asing, _entri("tinify", remaining=500)]) == "tinify"

    def test_layanan_asing_tetap_boleh_dipakai_bila_rantai_baku_habis(self):
        """Dibuang begitu saja akan MENYEMBUNYIKAN layanan yang lupa
        didaftarkan; ia hanya tak boleh menyerobot antrean."""
        asing = _entri("layanan_baru", remaining=500)
        assert layanan_aktif([_entri("tinify", used=500, remaining=0), asing]) == "layanan_baru"


class TestUrutanRantai:
    def test_urutan_persis_sesuai_kesepakatan(self):
        # Diuji PERSIS: menyisipkan layanan di tengah menggeser prioritas
        # seluruh rantai tanpa ada yang menyadarinya.
        assert URUTAN == ("tinify", "compresto", "uploadcare", "pillow")

    def test_pillow_selalu_paling_akhir(self):
        assert URUTAN[-1] == "pillow"


# ---------------------------------------------------------------------------
# Tepian
# ---------------------------------------------------------------------------

class TestTepian:
    def test_daftar_kosong_tak_meledak(self):
        assert layanan_aktif([]) == ""
        assert layanan_aktif(None) == ""

    def test_entri_bukan_dict_diabaikan(self):
        assert layanan_aktif(["tinify", None, 7, _entri("compresto")]) == "compresto"

    def test_remaining_hilang_dihitung_dari_limit_dikurangi_used(self):
        assert sisa_layanan({"limit": 500, "used": 480}) == 20
        assert layak_pakai(_entri("tinify", limit=500, used=500)) is False
        assert layak_pakai(_entri("tinify", limit=500, used=499)) is True

    def test_nilai_kacau_tidak_meloloskan_layanan(self):
        assert layak_pakai(_entri("tinify", limit="banyak", remaining="entah")) is False

    def test_limit_negatif_berarti_tak_terbatas(self):
        assert sisa_layanan({"limit": -1}) == -1
        assert layak_pakai({"service": "pillow", "terpasang": True, "limit": -1}) is True

    def test_terpasang_hilang_dianggap_belum_dipasang(self):
        """Payload lama (tanpa `terpasang`) TIDAK boleh dianggap siap pakai —
        lebih baik indikator diam daripada menunjuk layanan yang salah."""
        assert layak_pakai({"service": "tinify", "limit": 500, "remaining": 500}) is False


# ---------------------------------------------------------------------------
# Anti-drift: rantai sungguhan & endpoint harus memakai daftar yang sama
# ---------------------------------------------------------------------------

class TestTerpasangDiRantaiSungguhan:
    @staticmethod
    def _src():
        with open(os.path.join(BACKEND, "routes", "media.py"), encoding="utf-8") as f:
            return f.read()

    def test_auto_compress_mengulang_URUTAN_bukan_daftar_sendiri(self):
        src = self._src()
        fn = src.split("async def auto_compress_image", 1)[1].split("\n# ===", 1)[0]
        assert "for method_name in URUTAN:" in fn
        # Daftar tertulis-tangan di dalam fungsi = dua sumber kebenaran lagi.
        assert '("tinify", compress_with_tinify)' not in fn

    def test_registry_fungsi_menutup_seluruh_rantai(self):
        """Setiap nama di URUTAN harus punya pelaksana — kecuali `pillow` yang
        memang bukan layanan jaringan. Nama yang tak tertutup akan dilewati
        DIAM-DIAM oleh loop rantai."""
        from routes.media import _FUNGSI_KOMPRESI
        assert set(_FUNGSI_KOMPRESI) | {"pillow"} == set(URUTAN)

    def test_pillow_bukan_bagian_registry_jaringan(self):
        from routes.media import _FUNGSI_KOMPRESI
        assert "pillow" not in _FUNGSI_KOMPRESI

    def test_endpoint_kuota_mengirim_layanan_aktif(self):
        src = self._src()
        fn = src.split("async def get_all_compression_quotas", 1)[1]
        assert '"aktif": layanan_aktif(quotas)' in fn

    @pytest.mark.parametrize("layanan", ["tinify", "compresto", "uploadcare", "pillow"])
    def test_endpoint_kuota_mengirim_terpasang_tiap_layanan(self, layanan):
        """Tanpa `terpasang`, layar kembali menebak-nebak dari `available`."""
        src = self._src()
        fn = src.split("async def get_all_compression_quotas", 1)[1]
        assert re.search(r'"terpasang"\s*:', fn)
        assert fn.count('"terpasang"') >= 4, layanan
