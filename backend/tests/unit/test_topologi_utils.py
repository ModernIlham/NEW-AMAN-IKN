"""Uji topologi_utils — validasi shapely untuk kasus yang LOLOS cek struktural.

Semua fixture di sini lolos `spasial_utils.validasi_geometri` (struktur benar:
larik, tertutup, ≥3 titik berbeda) tetapi rusak secara topologi — persis kelas
bug yang Fase 3 dokumentasikan sebagai "belum diperiksa" dan Fase 4 tutup.
"""
import pytest

import spasial_utils as su
import topologi_utils as tu

pytest.importorskip("shapely")   # CI memasang requirements.txt → selalu ada


def poligon(*cincin):
    return {"type": "Polygon", "coordinates": [list(c) for c in cincin]}


# Kotak sederhana di sekitar IKN.
KOTAK = [[116.70, -1.40], [116.80, -1.40], [116.80, -1.30], [116.70, -1.30],
         [116.70, -1.40]]
# Bow-tie: urutan verteks menyilang — struktur SAH (tertutup, 5 titik, 4 unik).
BOWTIE = [[116.70, -1.40], [116.80, -1.30], [116.80, -1.40], [116.70, -1.30],
          [116.70, -1.40]]
LUBANG_DALAM = [[116.72, -1.38], [116.74, -1.38], [116.74, -1.36],
                [116.72, -1.36], [116.72, -1.38]]
LUBANG_LUAR = [[116.90, -1.38], [116.92, -1.38], [116.92, -1.36],
               [116.90, -1.36], [116.90, -1.38]]


def test_fixture_topologi_memang_lolos_cek_struktural():
    """Prasyarat seluruh file ini: kasus rusak-topologi HARUS lolos struktur —
    kalau tidak, uji di bawah tak membuktikan apa-apa."""
    assert su.validasi_geometri(poligon(BOWTIE)) is None
    assert su.validasi_geometri(poligon(KOTAK, LUBANG_LUAR)) is None


def test_poligon_sah_lolos():
    assert tu.validasi_topologi(poligon(KOTAK)) is None
    assert tu.validasi_topologi(poligon(KOTAK, LUBANG_DALAM)) is None


def test_bowtie_ditolak_dengan_pesan_indonesia():
    galat = tu.validasi_topologi(poligon(BOWTIE))
    assert galat and "menyilang" in galat


def test_lubang_di_luar_shell_ditolak():
    galat = tu.validasi_topologi(poligon(KOTAK, LUBANG_LUAR))
    assert galat and "LUAR" in galat


def test_multipolygon_bagian_bersarang_ditolak():
    dalam = [[116.72, -1.38], [116.74, -1.38], [116.74, -1.36],
             [116.72, -1.36], [116.72, -1.38]]
    galat = tu.validasi_topologi(
        {"type": "MultiPolygon", "coordinates": [[KOTAK], [dalam]]})
    assert galat is not None       # nested shells


def test_perbaiki_topologi_bowtie_menghasilkan_bentuk_sah():
    """make_valid atas bow-tie → MultiPolygon dua segitiga yang SAH — dan hasil
    usulan wajib lolos KEDUA validator, karena pratinjau yang akan ditolak saat
    disimpan itu menyesatkan."""
    usul = tu.perbaiki_topologi(poligon(BOWTIE))
    assert usul is not None
    assert su.validasi_geometri(usul) is None
    assert tu.validasi_topologi(usul) is None


def test_perbaiki_topologi_bentuk_sudah_sah_tetap_sah():
    usul = tu.perbaiki_topologi(poligon(KOTAK))
    assert usul is not None and tu.validasi_topologi(usul) is None


# ── containment ─────────────────────────────────────────────────────────────

INDUK = poligon(KOTAK)
ANAK_DI_DALAM = poligon([[116.72, -1.38], [116.75, -1.38], [116.75, -1.35],
                         [116.72, -1.35], [116.72, -1.38]])
ANAK_SETENGAH_KELUAR = poligon([[116.78, -1.38], [116.85, -1.38],
                                [116.85, -1.35], [116.78, -1.35],
                                [116.78, -1.38]])
ANAK_TERPISAH = poligon([[117.10, -1.38], [117.12, -1.38], [117.12, -1.36],
                         [117.10, -1.36], [117.10, -1.38]])


def test_ketat_anak_di_dalam_lolos():
    assert tu.validasi_containment(ANAK_DI_DALAM, INDUK, "ketat") is None


def test_ketat_verteks_menempel_batas_tak_dianggap_keluar():
    """Digambar dengan snap ke garis induk: verteks TEPAT di batas. Toleransi
    ±0,5 m harus meloloskannya — selisih pembulatan float bukan pelanggaran."""
    nempel = poligon([[116.70, -1.40], [116.75, -1.40], [116.75, -1.35],
                      [116.70, -1.35], [116.70, -1.40]])
    assert tu.validasi_containment(nempel, INDUK, "ketat") is None


def test_ketat_setengah_keluar_beri_peringatan_berpersen():
    pesan = tu.validasi_containment(ANAK_SETENGAH_KELUAR, INDUK, "ketat")
    assert pesan and "LUAR" in pesan and "%" in pesan


def test_longgar_bersinggungan_lolos_terpisah_tidak():
    assert tu.validasi_containment(ANAK_SETENGAH_KELUAR, INDUK, "longgar") is None
    pesan = tu.validasi_containment(ANAK_TERPISAH, INDUK, "longgar")
    assert pesan and "bersinggungan" in pesan


@pytest.mark.parametrize("mode", ["sumbu_z", "akar", "", None])
def test_mode_tanpa_cek_dilewati(mode):
    assert tu.validasi_containment(ANAK_TERPISAH, INDUK, mode) is None


def test_induk_belum_digambar_bukan_pelanggaran():
    assert tu.validasi_containment(ANAK_DI_DALAM, None, "ketat") is None
    assert tu.validasi_containment(ANAK_DI_DALAM, {}, "ketat") is None


def test_mode_registry_tersambung_ke_level_spasial():
    """Kontrak dengan registry: mode containment tiap level HARUS salah satu
    yang dikenal modul ini — nilai baru yang tak dikenal jatuh ke "ketat"
    (lebih aman), tapi lebih baik ketahuan di sini daripada diam-diam."""
    dikenal = {"ketat", "longgar"} | {m for m in tu.MODE_TANPA_CEK if m}
    for baris in su.LEVEL_SPASIAL:
        assert baris[4] in dikenal, f"mode '{baris[4]}' pada {baris[1]} tak dikenal"


# ── plafon ukuran ───────────────────────────────────────────────────────────

def test_jumlah_titik_menghitung_semua_cincin():
    assert tu.jumlah_titik(poligon(KOTAK)) == 5
    assert tu.jumlah_titik(poligon(KOTAK, LUBANG_DALAM)) == 10
    assert tu.jumlah_titik({"type": "Point", "coordinates": [1, 2]}) == 1
    assert tu.jumlah_titik({"type": "Polygon", "coordinates": "x"}) == 0
    assert tu.jumlah_titik(None) == 0


def test_geometri_raksasa_ditolak_sebelum_shapely(monkeypatch):
    """Endpoint pratinjau bisa dipanggil bebas oleh user terautentikasi —
    MultiPolygon raksasa tak boleh jadi jalan membakar CPU VPS lewat GEOS."""
    monkeypatch.setattr(tu, "MAKS_TITIK_TOPOLOGI", 8)
    galat = tu.validasi_topologi(poligon(KOTAK, LUBANG_DALAM))   # 10 titik
    assert galat and "terlalu besar" in galat
    assert tu.validasi_topologi(poligon(KOTAK)) is None          # 5 titik → jalan


# ── degradasi anggun tanpa shapely ──────────────────────────────────────────

def test_tanpa_shapely_semua_cek_melewati_diri(monkeypatch):
    """Server TIDAK boleh mati karena libgeos absen — tanpa shapely seluruh
    fungsi mengembalikan None dan MongoDB kembali jadi jaring terakhir."""
    monkeypatch.setattr(tu, "_shapely", lambda: None)
    assert tu.topologi_aktif() is False
    assert tu.validasi_topologi(poligon(BOWTIE)) is None
    assert tu.perbaiki_topologi(poligon(BOWTIE)) is None
    assert tu.validasi_containment(ANAK_TERPISAH, INDUK, "ketat") is None
