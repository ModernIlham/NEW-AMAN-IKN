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


def lingkaran(n, cx=116.75, cy=-1.35, r=0.01):
    """Poligon SAH ber-n verteks — murah bagi GEOS berapa pun besarnya."""
    import math
    cincin = [[cx + math.cos(2 * math.pi * i / n) * r,
               cy + math.sin(2 * math.pi * i / n) * r] for i in range(n)]
    return poligon(cincin + [cincin[0]])


def test_geometri_raksasa_ditolak_sebelum_shapely(monkeypatch):
    """Plafon verteks masih ada sebagai batas kewarasan MEMORI — bukan biaya."""
    monkeypatch.setattr(tu, "MAKS_TITIK_VALIDASI", 8)
    galat = tu.validasi_topologi(poligon(KOTAK, LUBANG_DALAM))   # 10 titik
    assert galat and galat.startswith(tu.AWALAN_TERLALU_BESAR)
    assert tu.validasi_topologi(poligon(KOTAK)) is None          # 5 titik → jalan


def test_pesan_tolak_tak_menyuruh_pakai_jalur_impor_file():
    """REGRESI LAPANGAN. Pesan lama berbunyi "sederhanakan bentuknya atau pakai
    jalur impor file" — dan justru muncul kepada operator yang SEDANG memakai
    jalur impor file (6 poligon BWP IKN: 1 jadi, 5 dilewati). Saran yang
    menyuruh melakukan hal yang sudah dilakukan adalah jalan buntu."""
    for pesan in (tu.SARAN_SEDERHANAKAN,
                  tu.validasi_topologi(lingkaran(6)) or "",
                  _tolak_karena_besar()):
        assert "jalur impor file" not in pesan


def _tolak_karena_besar():
    import unittest.mock as m
    with m.patch.object(tu, "MAKS_TITIK_VALIDASI", 3):
        return tu.validasi_topologi(poligon(KOTAK)) or ""


def test_poligon_sah_besar_LOLOS_bukan_ditolak():
    """INTI PERBAIKAN GIS-1. Poligon batas wilayah 50.000 verteks itu SAH dan
    `is_valid` menyelesaikannya dalam hitungan milidetik. Plafon lama 20.000
    menolaknya mentah-mentah — itulah sebab node draft dilewati saat impor.

    Uji ini mati bila seseorang menurunkan plafon kembali ke bawah 50.000.
    """
    besar = lingkaran(50_000)
    assert tu.jumlah_titik(besar) > tu.AMBANG_TENGGAT_VALIDASI   # lewat jalur tenggat
    assert tu.validasi_topologi(besar) is None


def test_poligon_sah_besar_dapat_diperbaiki_juga():
    """`make_valid` atas poligon sah 50.000 verteks = ~1 ms. Menolaknya karena
    cacah verteks berarti menolak perbaikan yang justru murah."""
    besar = lingkaran(50_000)
    assert tu.jumlah_titik(besar) > tu.AMBANG_TENGGAT_PERBAIKAN  # lewat jalur tenggat
    usul = tu.perbaiki_topologi(besar)
    assert usul is not None and tu.validasi_topologi(usul) is None


def test_tenggat_membunuh_kerja_yang_kebablasan(monkeypatch):
    """Pagar sesungguhnya adalah TENGGAT, bukan cacah verteks.

    Dibuktikan dengan kerja yang sengaja menggantung: tanpa pembunuhan proses,
    uji ini takkan pernah selesai. `perbaiki_topologi` harus menyerah (None)
    dan `validasi_topologi` harus melapor "terlalu rumit" — bukan membeku.
    """
    monkeypatch.setattr(tu, "AMBANG_TENGGAT_VALIDASI", 0)
    monkeypatch.setattr(tu, "AMBANG_TENGGAT_PERBAIKAN", 0)
    monkeypatch.setattr(tu, "BATAS_DETIK_VALIDASI", 1.0)
    monkeypatch.setattr(tu, "BATAS_DETIK_PERBAIKAN", 1.0)
    monkeypatch.setattr(tu, "_kerja_validasi", _menggantung)
    monkeypatch.setattr(tu, "_kerja_perbaikan", _menggantung)

    galat = tu.validasi_topologi(poligon(KOTAK))
    assert galat and galat.startswith(tu.AWALAN_TERLALU_RUMIT)
    assert tu.perbaiki_topologi(poligon(KOTAK)) is None


def _menggantung(_geom):
    import time
    time.sleep(3600)          # anak WAJIB dibunuh; kalau tidak, uji menggantung


def test_anak_yang_kebablasan_benar_benar_DIBUNUH(monkeypatch):
    """Tenggat lewat saja tidak cukup — prosesnya harus MATI.

    Tanpa `proses.kill()`, `_jalankan_bertenggat` tetap melaporkan TENGGAT tepat
    waktu sementara anaknya terus membakar CPU di latar. Uji ini menangkap
    justru mutasi itu: ia memeriksa PID-nya sudah tak ada lagi.
    """
    import os
    import time as _t
    dilihat = {}
    nyata = tu.multiprocessing.get_context("fork")    # tangkap SEBELUM ditambal

    class Perekam(nyata.Process):
        def start(self):
            super().start()
            dilihat["pid"] = self.pid

    class KonteksPerekam:
        Pipe = staticmethod(nyata.Pipe)
        Process = Perekam

    monkeypatch.setattr(tu.multiprocessing, "get_context",
                        lambda _m: KonteksPerekam())
    status, _ = tu._jalankan_bertenggat(_menggantung, poligon(KOTAK), 0.5)
    assert status == tu.TENGGAT and "pid" in dilihat

    for _ in range(50):                    # beri kernel waktu menuai zombie
        try:
            os.kill(dilihat["pid"], 0)
        except OSError:
            break
        _t.sleep(0.1)
    else:
        raise AssertionError(
            f"proses {dilihat['pid']} MASIH HIDUP setelah tenggat lewat — "
            "kerja GEOS yang kebablasan tak pernah benar-benar dihentikan")


def test_bentuk_patologis_nyata_selesai_dalam_waktu_terbatas(monkeypatch):
    """Bukti dengan data ASLI, bukan tiruan.

    Bintang menyilang-diri 501 verteks terukur TIDAK selesai dalam 20 detik di
    `make_valid` (dan plafon lama 20.000 meloloskannya begitu saja). Dengan
    tenggat, panggilannya wajib kembali — menyerah — dalam hitungan detik.
    """
    import math
    import time as _t
    n = 501
    lompat = n // 2 if (n // 2) % 2 == 1 else n // 2 - 1
    titik = [[116.75 + math.cos(2 * math.pi * ((i * lompat) % n) / n) * 0.01,
              -1.35 + math.sin(2 * math.pi * ((i * lompat) % n) / n) * 0.01]
             for i in range(n)]
    bintang = poligon(titik + [titik[0]])

    assert su.validasi_geometri(bintang) is None            # struktur SAH
    assert tu.validasi_topologi(bintang) is not None        # topologi rusak
    assert tu.jumlah_titik(bintang) > tu.AMBANG_TENGGAT_PERBAIKAN

    monkeypatch.setattr(tu, "BATAS_DETIK_PERBAIKAN", 2.0)
    t0 = _t.perf_counter()
    hasil = tu.perbaiki_topologi(bintang)
    lama = _t.perf_counter() - t0
    assert hasil is None, "make_valid mustahil selesai untuk bentuk ini"
    assert lama < 15, f"perbaikan makan {lama:.1f} dtk — tenggat tidak menggigit"


def test_perlu_disederhanakan_membedakan_tolak_dari_cacat():
    """Kontrak dengan pemanggil (impor & pratinjau): "kami menolak memeriksa"
    harus bisa dibedakan dari "bentuknya salah". Kalau tidak, impor menempelkan
    "(perbaikan otomatis gagal)" pada penolakan ukuran — persis kalimat
    membingungkan yang dilaporkan dari lapangan."""
    assert tu.perlu_disederhanakan(f"{tu.AWALAN_TERLALU_BESAR} (99 titik)")
    assert tu.perlu_disederhanakan(f"{tu.AWALAN_TERLALU_RUMIT} — 9 detik")
    assert not tu.perlu_disederhanakan(tu.validasi_topologi(poligon(BOWTIE)))
    assert not tu.perlu_disederhanakan(None)
    assert not tu.perlu_disederhanakan("")


def test_tanpa_proses_terpisah_kembali_ke_plafon_konservatif(monkeypatch):
    """Platform tanpa fork tak boleh diam-diam kehilangan pagarnya: bila tenggat
    mustahil dipasang, plafon verteks lama kembali menjadi satu-satunya pagar —
    dan `make_valid` menolak, karena membeku jauh lebih buruk daripada menolak."""
    monkeypatch.setattr(tu, "_jalankan_bertenggat",
                        lambda *a, **k: (tu.TANPA_PROSES, None))
    besar = lingkaran(50_000)
    galat = tu.validasi_topologi(besar)
    assert galat and galat.startswith(tu.AWALAN_TERLALU_BESAR)
    assert tu.perbaiki_topologi(besar) is None


# ── degradasi anggun tanpa shapely ──────────────────────────────────────────

def test_tanpa_shapely_semua_cek_melewati_diri(monkeypatch):
    """Server TIDAK boleh mati karena libgeos absen — tanpa shapely seluruh
    fungsi mengembalikan None dan MongoDB kembali jadi jaring terakhir."""
    monkeypatch.setattr(tu, "_shapely", lambda: None)
    assert tu.topologi_aktif() is False
    assert tu.validasi_topologi(poligon(BOWTIE)) is None
    assert tu.perbaiki_topologi(poligon(BOWTIE)) is None
    assert tu.validasi_containment(ANAK_TERPISAH, INDUK, "ketat") is None
