"""Satu indeks gagal tidak boleh membatalkan sisanya — temuan C31 & C4b.

Seluruh badan `create_indexes()` dulu berada di dalam SATU `try/except`, dan
`except`-nya hanya mencatat satu baris log. Satu `create_index` yang melempar
karenanya melompati SEMUA definisi setelahnya — 105 di antaranya berada setelah
titik rapuh terakhir.

Yang membuat ini sulit terlihat: **sistemnya tetap hidup**. Ia tetap menjawab,
tetap menyimpan, tetap mencetak laporan. Yang berubah hanyalah sebagian
kuerinya diam-diam menjadi pemindaian koleksi penuh — dan satu-satunya jejaknya
sebaris log saat boot yang tak pernah dibaca siapa pun.

Bahwa ini bukan hipotesis terlihat dari kompensasi di sekitarnya: ada blok yang
men-drop indeks era lama justru karena data produksi pernah melanggar keunikan.
`create_index` idempoten, jadi risikonya tidak menyala tiap boot — ia menyala
pada boot PERTAMA setelah indeks unik baru ditambahkan. Itu yang membuatnya
mendesak, karena C32 (Gelombang 2 berikutnya) memang mengusulkan indeks unik
baru.

Uji ini mengurung tiga hal: `_idx` tidak pernah melempar, kegagalan TERCATAT,
dan kegagalan itu SAMPAI ke `/api/health/deep` — sebab kegagalan yang tak
terlihat sama saja dengan kegagalan yang diabaikan.
"""
import asyncio
import inspect
import pathlib
import re

import pytest

import indexes as ix

BACKEND = pathlib.Path(__file__).resolve().parents[2]


def _jalan(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


class _KoleksiPalsu:
    """Koleksi yang bisa disuruh gagal pada pemanggilan tertentu."""

    def __init__(self, nama, gagal_pada=()):
        self.name = nama
        self.gagal_pada = set(gagal_pada)
        self.dibuat = []
        self._n = 0

    async def create_index(self, *a, **kw):
        self._n += 1
        if self._n in self.gagal_pada:
            raise RuntimeError(f"E11000 duplicate key pada {self.name}")
        self.dibuat.append(kw.get("name") or (a[0] if a else "?"))


@pytest.fixture(autouse=True)
def bersihkan():
    ix._KEGAGALAN_INDEKS.clear()
    yield
    ix._KEGAGALAN_INDEKS.clear()


class TestIdxTidakPernahMelempar:
    def test_indeks_sukses_tercatat_dibuat(self):
        c = _KoleksiPalsu("assets")
        _jalan(ix._idx(c, "id", unique=True, name="unique_asset_id"))
        assert c.dibuat == ["unique_asset_id"]
        assert ix.kegagalan_indeks() == []

    def test_indeks_gagal_TIDAK_melempar(self):
        c = _KoleksiPalsu("assets", gagal_pada={1})
        _jalan(ix._idx(c, "id", unique=True, name="unique_asset_id"))  # tak boleh raise

    def test_kegagalan_dicatat_dengan_koleksi_nama_dan_alasan(self):
        c = _KoleksiPalsu("assets", gagal_pada={1})
        _jalan(ix._idx(c, "id", unique=True, name="unique_asset_id"))
        (g,) = ix.kegagalan_indeks()
        assert g["koleksi"] == "assets"
        assert g["indeks"] == "unique_asset_id"
        assert "duplicate key" in g["galat"]

    def test_indeks_SETELAH_yang_gagal_tetap_dibuat(self):
        """Inti C31: yang gagal satu, yang jalan tetap jalan."""
        c = _KoleksiPalsu("assets", gagal_pada={2})
        for n in ("a", "b", "c", "d"):
            _jalan(ix._idx(c, n, name=n))
        assert c.dibuat == ["a", "c", "d"]        # b gagal, sisanya LANJUT
        assert len(ix.kegagalan_indeks()) == 1

    def test_indeks_tanpa_name_tetap_bisa_dilaporkan(self):
        c = _KoleksiPalsu("kodefikasi", gagal_pada={1})
        _jalan(ix._idx(c, "kode"))
        assert ix.kegagalan_indeks()[0]["indeks"] == "kode"

    def test_daftar_kegagalan_dikembalikan_sebagai_SALINAN(self):
        # Pemanggil tak boleh bisa menghapus catatan kegagalan dengan
        # memutasi hasilnya — laporan yang bisa dibersihkan pembacanya
        # bukan laporan.
        c = _KoleksiPalsu("assets", gagal_pada={1})
        _jalan(ix._idx(c, "id", name="x"))
        salinan = ix.kegagalan_indeks()
        salinan.clear()
        assert len(ix.kegagalan_indeks()) == 1


class TestSumberIndeks:
    SRC = (BACKEND / "indexes.py").read_text(encoding="utf-8")

    def test_semua_indeks_level_fungsi_lewat_penjaga(self):
        """Satu titik panggil yang terlewat = satu rantai yang masih bisa putus."""
        telanjang = re.findall(r"^        await db\.[A-Za-z_0-9]+\.create_index\(",
                               self.SRC, re.M)
        assert telanjang == [], telanjang

    def test_jumlah_titik_panggil_berpenjaga_masuk_akal(self):
        assert len(re.findall(r"await _idx\(db\.", self.SRC)) > 150

    def test_yang_SUDAH_punya_try_except_sendiri_dibiarkan(self):
        # Sembilan panggilan berindentasi lebih dalam punya fallback sendiri
        # (mis. "kalau unik gagal, buat non-unik agar lookup tetap cepat").
        # Mengalihkannya ke _idx akan mematikan fallback itu — penjaga baru
        # tak boleh menghapus penjaga lama yang lebih pintar.
        dalam = re.findall(r"^ {12}await db\.[A-Za-z_0-9]+\.create_index\(",
                           self.SRC, re.M)
        assert len(dalam) >= 5, len(dalam)

    def test_daftar_dikosongkan_tiap_pembuatan(self):
        # backup.py membangun ulang indeks setelah restore; tanpa reset,
        # kegagalan lama menempel selamanya dan health check berbohong.
        src = inspect.getsource(ix.create_indexes)
        i_reset = src.index("_KEGAGALAN_INDEKS.clear()")
        i_try = src.index("try:")
        assert i_reset < i_try


class TestHealthDeep:
    SRC = (BACKEND / "server.py").read_text(encoding="utf-8")

    def test_melaporkan_kegagalan_indeks(self):
        assert "kegagalan_indeks" in self.SRC
        assert 'checks["indexes"]' in self.SRC

    def test_indeks_gagal_TIDAK_menjatuhkan_gerbang_deploy(self):
        """Sengaja: aplikasi masih melayani; 503 di sini melatih tim
        melewati gerbangnya."""
        i = self.SRC.index('checks["indexes"]')
        blok = self.SRC[i:self.SRC.index('checks["disk"]')]
        assert "ok = False" not in blok

    def test_disk_dilaporkan_dengan_ANGKA(self):
        # Ini satu-satunya cek yang bisa ditindaki pemilik tanpa menyentuh
        # kode — jadi ia harus menyebut berapa, bukan cuma "tidak sehat".
        assert 'checks["disk"]' in self.SRC
        for k in ("bebas_persen", "bebas_mb", "total_mb"):
            assert k in self.SRC, k

    def test_disk_penuh_MENJATUHKAN_status(self):
        # Beda dari indeks: disk penuh benar-benar mematikan layanan, dan
        # deploy di atas disk penuh akan gagal dengan cara yang membingungkan.
        i = self.SRC.index('checks["disk"]')
        blok = self.SRC[i:i + 900]
        assert "ok = False" in blok

    def test_ambangnya_disebut_eksplisit(self):
        assert "15.0" in self.SRC or "15%" in self.SRC

    def test_disk_PERINGATAN_tidak_menjatuhkan_status(self):
        """Koreksi atas versi pertama C4b.

        Disk 15% dulu menjatuhkan `ok` menjadi 503 — dan itu keliru bukan
        karena ambangnya salah, melainkan karena tak memperhitungkan SIAPA
        pembaca 503-nya. `scripts/deploy_vps.sh` memakai endpoint ini sebagai
        gerbang deploy; 503 memanggil `pulihkan`, yang `git reset --hard` ke
        commit sebelumnya. VPS berisi 86% — bukan penuh, aplikasi melayani
        normal — akan me-ROLLBACK setiap merge ke main, berulang selamanya,
        termasuk merge yang membawa perbaikannya sendiri.
        """
        i = self.SRC.index('checks["disk"]')
        blok = self.SRC[i:i + 900]
        assert "if disk_kritis:" in blok, blok
        # `disk_ok` (ambang peringatan 15%) TIDAK boleh menjatuhkan gerbang.
        assert "if not disk_ok:\n            ok = False" not in self.SRC

    def test_ambang_kritis_ABSOLUT_bukan_rasio(self):
        # Yang sebenarnya rusak juga absolut: `yarn build` dan `pip install`
        # butuh sekian ratus MB untuk selesai. Persentase salah di kedua ujung
        # — 3% dari 1 TB masih 30 GB (sehat), 15% dari 20 GB hanya 3 GB (mepet).
        assert "KRITIS_MB" in self.SRC
        assert "bebas_mb < KRITIS_MB" in self.SRC

    def test_dua_ambang_dilaporkan_terpisah(self):
        # Monitor tetap melihat peringatan 15%; gerbang deploy hanya melihat
        # yang kritis. Perlakuan yang sama dengan checks["indexes"].
        i = self.SRC.index('checks["disk"] = {')
        blok = self.SRC[i:i + 400]
        assert '"ok": disk_ok' in blok
        assert '"kritis": disk_kritis' in blok
