"""NUP versus kuantitas BAST — peringatan saat LPB dibuat.

Permintaan pemilik: *"pada saat LPB akan dibuat pastikan untuk dapat
mengingatkan tentang NUP dan pastikan sesuai dengan jumlahnya."*

BMN ber-jumlah N seharusnya menjadi N aset ber-NUP masing-masing. Jalur
pencatatan memecahnya HANYA bila jumlahnya bilangan bulat 2..50; di luar itu —
pecahan, atau lebih dari 50 — SELURUH baris menjadi satu NUP dan sisanya cuma
jadi catatan teks pada `notes` aset.

Selisih itu tak pernah menghasilkan galat: LPB tetap terbit, jurnal tetap
tertulis, dan yang membacanya berbulan kemudian melihat "1 unit" untuk 100 rim
yang benar-benar datang. Justru itu sebabnya ia harus diperingatkan di detik
pencatatan, saat masih bisa diperbaiki.
"""
import ast
import pathlib

from lpb_utils import BATAS_PECAH_NUP, peringatan_nup, unit_per_baris

AKAR = pathlib.Path(__file__).resolve().parents[2]


def _aset(kode, n):
    return [{"asset_code": kode, "NUP": str(i + 1)} for i in range(n)]


class TestUnitPerBaris:
    def test_satu_unit_tetap_satu(self):
        assert unit_per_baris(1) == 1

    def test_bulat_dalam_batas_dipecah(self):
        assert unit_per_baris(2) == 2
        assert unit_per_baris(BATAS_PECAH_NUP) == BATAS_PECAH_NUP

    def test_melebihi_batas_TIDAK_dipecah(self):
        assert unit_per_baris(BATAS_PECAH_NUP + 1) == 1
        assert unit_per_baris(1000) == 1

    def test_pecahan_TIDAK_dipecah(self):
        assert unit_per_baris(2.5) == 1

    def test_masukan_kotor_tak_meledak(self):
        for x in (None, "", "abc", 0, -3, float("nan")):
            assert unit_per_baris(x) == 1, x

    def test_aturannya_dipakai_jalur_pencatatan_bukan_disalin(self):
        """Peringatan dan pelaksanaannya harus memakai aturan yang SAMA.
        Selama aturannya disalin sebagai ekspresi inline, keduanya bisa
        perlahan berbeda — dan peringatannya jadi berbohong."""
        teks = (AKAR / "routes" / "pengadaan.py").read_text(encoding="utf-8")
        assert "unit_per_baris(jumlah)" in teks
        # Ambang 50 tak boleh lagi ditulis tangan sebagai perbandingan di
        # jalur itu — `assert ... or True` yang sempat saya tulis di sini
        # tidak menagih apa pun, jadi dibuang.
        assert "2 <= jumlah <= 50" not in teks
        pohon = ast.parse(teks)
        panggil = [n for n in ast.walk(pohon)
                   if isinstance(n, ast.Call)
                   and getattr(n.func, "id", "") == "unit_per_baris"]
        assert panggil, "jalur pencatatan tak memanggil unit_per_baris"


class TestPeringatanNup:
    def test_jumlah_pas_tidak_memperingatkan_apa_pun(self):
        brg = [{"kode": "3050104001", "uraian": "Laptop", "jumlah": 3}]
        assert peringatan_nup(brg, _aset("3050104001", 3)) == []

    def test_satu_unit_tidak_memperingatkan(self):
        brg = [{"kode": "3050104001", "uraian": "Laptop", "jumlah": 1}]
        assert peringatan_nup(brg, _aset("3050104001", 1)) == []

    def test_melebihi_batas_diperingatkan_dengan_ANGKA_sebenarnya(self):
        brg = [{"kode": "1", "uraian": "Server", "jumlah": 100}]
        w = peringatan_nup([{**brg[0], "kode": "3050104001"}],
                           _aset("3050104001", 1))
        assert len(w) == 1 and w[0]["sebab"] == "melebihi_batas"
        assert "100 unit" in w[0]["pesan"]
        assert w[0]["nup_terbentuk"] == 1

    def test_pecahan_diperingatkan_dan_sebabnya_disebut(self):
        w = peringatan_nup(
            [{"kode": "3020101001", "uraian": "Mobil", "jumlah": 2.5}],
            _aset("3020101001", 1))
        assert w[0]["sebab"] == "pecahan"
        assert "pecahan" in w[0]["pesan"]

    def test_pemecahan_yang_gagal_di_tengah_diperingatkan(self):
        """Kegagalan sebagian tetap menerbitkan LPB — yang kurang tak pernah
        menyusul, dan tak ada galat yang menyebutkannya."""
        w = peringatan_nup(
            [{"kode": "3060101001", "uraian": "Kamera", "jumlah": 4}],
            _aset("3060101001", 2))
        assert w[0]["sebab"] == "nup_kurang"
        assert "2 dari 4" in w[0]["pesan"]

    def test_baris_PERSEDIAAN_bukan_urusan_NUP(self):
        """Golongan 1 masuk kartu stok, tak pernah ber-NUP. Memperingatkannya
        akan melatih operator mengabaikan peringatan ini."""
        assert peringatan_nup(
            [{"kode": "1010301001", "uraian": "Kertas", "jumlah": 50}], []) == []

    def test_baris_yang_sudah_TERTAUT_bukan_selisih(self):
        assert peringatan_nup(
            [{"kode": "3050104001", "uraian": "Laptop", "jumlah": 3,
              "asset_id": "a-1"}], []) == []

    def test_baris_tanpa_kode_dilewati(self):
        assert peringatan_nup(
            [{"kode": "", "uraian": "Jasa", "jumlah": 2}], []) == []

    def test_dua_baris_berkode_SAMA_dihitung_terpisah(self):
        """Satu BAST bisa memuat dua baris berkode sama. Menjumlahkannya jadi
        satu akan menyembunyikan baris kedua yang gagal."""
        brg = [{"kode": "3050104001", "uraian": "Laptop A", "jumlah": 2},
               {"kode": "3050104001", "uraian": "Laptop B", "jumlah": 3}]
        w = peringatan_nup(brg, _aset("3050104001", 2))
        assert len(w) == 1
        assert "Laptop B" in w[0]["pesan"] and "0 dari 3" in w[0]["pesan"]

    def test_daftar_kosong_aman(self):
        assert peringatan_nup([], []) == []
        assert peringatan_nup(None, None) == []

    def test_pesannya_menyebut_kode_dan_uraiannya(self):
        w = peringatan_nup(
            [{"kode": "3050104001", "uraian": "Server Rak", "jumlah": 80}],
            _aset("3050104001", 1))
        assert "Server Rak" in w[0]["pesan"] and "3050104001" in w[0]["pesan"]


# ── Porsi baris BAST yang diwakili satu draft ───────────────────────────────

class TestPorsiBaris:
    """Satu sumber untuk `jumlah_bast` LPB, nilai perolehan aset, dan nilai
    jurnal. Ketiganya dulu dihitung sendiri-sendiri dan berselisih."""

    def test_baris_yang_dipecah_per_unit_menghasilkan_satu(self):
        from lpb_utils import porsi_baris, unit_per_baris
        for j in (2, 5, 50):
            assert porsi_baris(j, unit_per_baris(j)) == 1.0, j

    def test_baris_di_luar_batas_diwakili_SELURUHNYA(self):
        from lpb_utils import porsi_baris, unit_per_baris
        assert porsi_baris(100, unit_per_baris(100)) == 100.0
        assert porsi_baris(51, unit_per_baris(51)) == 51.0

    def test_jumlah_pecahan_diwakili_apa_adanya(self):
        from lpb_utils import porsi_baris, unit_per_baris
        assert porsi_baris(2.5, unit_per_baris(2.5)) == 2.5

    def test_satu_unit_tetap_satu(self):
        from lpb_utils import porsi_baris, unit_per_baris
        assert porsi_baris(1, unit_per_baris(1)) == 1.0

    def test_nilai_cacat_tak_pernah_jadi_pengali_rupiah(self):
        """Satu baris cacat tak boleh meracuni seluruh Neraca."""
        from lpb_utils import porsi_baris
        for j in (0, -5, float("nan"), float("inf"), None, "x", [1]):
            assert porsi_baris(j, 1) == 1.0, j

    def test_n_unit_menang_atas_jumlah(self):
        """Bila barisnya SUDAH dipecah, tiap draft mewakili satu unit —
        berapa pun jumlah barisnya."""
        from lpb_utils import porsi_baris
        assert porsi_baris(5, 5) == 1.0
