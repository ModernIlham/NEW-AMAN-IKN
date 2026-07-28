"""Uji optimalisasi geometri peta — logika MURNI, tanpa DB.

Yang dijaga di sini bukan "apakah hasilnya lebih kecil", melainkan **apakah
hasilnya masih peta yang sama**. Poligon denah adalah dasar perhitungan luas
ruangan SBSK dan deteksi lokasi otomatis; penyederhanaan yang menggeser garis
terlalu jauh menghasilkan angka luas yang salah — diam-diam, tanpa galat.
"""
import math

import spasial_optimize as so


def _lingkaran(lat0=-0.95, lon0=116.7, r_deg=0.004, n=1000):
    """Poligon rapat ber-n verteks — mirip hasil impor SHP/KML asli."""
    ring = [[lon0 + r_deg * math.cos(t * 2 * math.pi / n),
             lat0 + r_deg * math.sin(t * 2 * math.pi / n)] for t in range(n)]
    ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


def _kotak(lat0=-0.95, lon0=116.7, d=0.0005):
    return {"type": "Polygon", "coordinates": [[
        [lon0, lat0], [lon0 + d, lat0], [lon0 + d, lat0 + d],
        [lon0, lat0 + d], [lon0, lat0]]]}


# ── Cacah verteks ──────────────────────────────────────────────────────────

def test_cacah_titik_semua_bentuk():
    assert so._titik_geom({"type": "Point", "coordinates": [1, 2]}) == 1
    assert so._titik_geom(
        {"type": "LineString", "coordinates": [[0, 0], [1, 1], [2, 2]]}) == 3
    assert so._titik_geom(_kotak()) == 5
    multi = {"type": "MultiPolygon",
             "coordinates": [_kotak()["coordinates"], _kotak()["coordinates"]]}
    assert so._titik_geom(multi) == 10


def test_cacah_titik_bentuk_rusak_tak_meledak():
    for buruk in (None, {}, {"type": "Polygon"}, {"coordinates": None},
                  {"type": "Polygon", "coordinates": []}, "bukan dict"):
        assert so._titik_geom(buruk) == 0


# ── Presisi koordinat ──────────────────────────────────────────────────────

def test_presisi_memangkas_desimal_tanpa_merusak_struktur():
    g = {"type": "Polygon", "coordinates": [[
        [116.712345678901, -0.951234567890], [116.8, -0.9],
        [116.7, -0.8], [116.712345678901, -0.951234567890]]]}
    h = so.presisi_koordinat(g, 6)
    assert h["coordinates"][0][0] == [116.712346, -0.951235]
    assert len(h["coordinates"][0]) == 4
    assert h["type"] == "Polygon"


def test_presisi_tak_mengubah_masukan():
    """Masukan tak boleh termutasi — pemanggil masih memegang yang ASLI."""
    g = _kotak()
    salinan = str(g)
    so.presisi_koordinat(g, 4)
    assert str(g) == salinan


def test_presisi_dijepit_ke_rentang_wajar():
    g = _kotak()
    # Nilai ekstrem tak boleh melahirkan koordinat bulat (peta lenyap) atau
    # 30 desimal (payload membengkak tanpa informasi).
    assert so.presisi_koordinat(g, 0)["coordinates"][0][0][0] == round(116.7, so.PRESISI_MIN)
    assert so.presisi_koordinat(g, 99) is not None


# ── Skala acuan ────────────────────────────────────────────────────────────

def test_diagonal_bbox_dalam_meter_masuk_akal():
    # Kotak 0.0005° di khatulistiwa ≈ 55 m per sisi → diagonal ≈ 78 m.
    d = so.diagonal_bbox_m(_kotak())
    assert 70 < d < 90, d


def test_diagonal_geometri_rusak_nol():
    assert so.diagonal_bbox_m(None) == 0.0
    assert so.diagonal_bbox_m({"type": "Polygon", "coordinates": []}) == 0.0


# ── INTI: sweet spot ───────────────────────────────────────────────────────

def test_optimasi_menghemat_banyak_tanpa_melanggar_anggaran():
    g = _lingkaran()
    h = so.optimalkan(g)
    m = h["metrik"]
    assert h["geometry"] is not None
    assert m["titik_hasil"] < m["titik_asli"] / 2, "hematnya tak berarti"
    # INI yang menentukan: bentuknya masih sama.
    assert m["geser_m"] <= so.MAKS_GESER_M
    assert m["delta_luas_persen"] <= so.MAKS_DELTA_LUAS


def test_anggaran_ketat_menghasilkan_penyederhanaan_lebih_sedikit():
    """Anggaran BUKAN hiasan: mengetatkannya harus mengurangi penghematan.

    Tanpa uji ini, `optimalkan` boleh saja mengabaikan parameternya dan tetap
    lulus semua uji lain.
    """
    g = _lingkaran()
    longgar = so.optimalkan(g, maks_geser_m=5.0, maks_delta_luas=10.0)
    ketat = so.optimalkan(g, maks_geser_m=0.02, maks_delta_luas=0.01)
    assert longgar["metrik"]["titik_hasil"] < ketat["metrik"]["titik_hasil"], (
        "anggaran ketat menghasilkan penghematan yang sama — parameternya "
        "tidak benar-benar dipakai")


def test_poligon_sederhana_tak_disentuh():
    """Kotak 5 titik tak punya apa pun untuk dihemat, dan bisa RUSAK bila
    tetap disederhanakan."""
    h = so.optimalkan(_kotak())
    assert h["geometry"] is None
    assert "ambang" in h["metrik"]["alasan"]


def test_geometri_rusak_ditolak_bukan_meledak():
    for buruk in (None, {}, {"type": "Polygon", "coordinates": []}):
        h = so.optimalkan(buruk)
        assert h["geometry"] is None
        assert h["metrik"]["alasan"]


def test_ruangan_kecil_tak_dilenyapkan():
    """Toleransi diturunkan dari UKURAN OBJEK, bukan angka tetap.

    Angka tetap yang aman bagi kawasan 50 km akan melenyapkan ruangan 10 m.
    Uji ini memakai ruangan ~11 m ber-verteks rapat.
    """
    g = _lingkaran(r_deg=0.00005, n=200)      # radius ≈ 5,5 m
    h = so.optimalkan(g)
    hasil = h["geometry"] or g
    assert so._titik_geom(hasil) >= 4, "ruangan menjadi bukan-poligon"
    assert h["metrik"]["geser_m"] <= so.MAKS_GESER_M


def test_kawasan_besar_juga_tertangani():
    g = _lingkaran(r_deg=0.25, n=2000)        # radius ≈ 27 km
    h = so.optimalkan(g)
    assert h["geometry"] is not None
    assert h["metrik"]["hemat_persen"] > 50


def test_metrik_dilaporkan_dari_geometri_yang_BENAR_BENAR_disimpan():
    """Angka penyimpangan diukur ULANG setelah pembulatan presisi.

    Pembulatan terjadi SETELAH penyederhanaan dan dapat menggeser garis lagi.
    Melaporkan angka pra-pembulatan berarti menjanjikan ketelitian yang tak
    dimiliki geometri yang tersimpan.
    """
    g = _lingkaran()
    h = so.optimalkan(g, desimal=4)           # sengaja kasar
    dev = so.ukur_penyimpangan(g, h["geometry"])
    assert abs(dev["geser_m"] - h["metrik"]["geser_m"]) < 1e-6


def test_hemat_persen_konsisten_dengan_cacah_titik():
    h = so.optimalkan(_lingkaran())
    m = h["metrik"]
    harapan = round(100.0 * (m["titik_asli"] - m["titik_hasil"]) / m["titik_asli"], 1)
    assert m["hemat_persen"] == harapan


# ── Penyimpangan ───────────────────────────────────────────────────────────

def test_penyimpangan_nol_untuk_geometri_identik():
    g = _lingkaran(n=50)
    d = so.ukur_penyimpangan(g, g)
    assert d["geser_m"] == 0.0
    assert d["delta_luas_persen"] == 0.0


def test_penyimpangan_menangkap_pergeseran_yang_luasnya_tetap():
    """Selisih LUAS saja tak cukup — dua sisi bisa bergeser berlawanan.

    Inilah sebabnya jarak Hausdorff yang dipakai, bukan delta luas.
    """
    a = {"type": "Polygon", "coordinates": [[
        [116.700, -0.950], [116.701, -0.950], [116.701, -0.949],
        [116.700, -0.949], [116.700, -0.950]]]}
    b = {"type": "Polygon", "coordinates": [[
        [116.7005, -0.950], [116.7015, -0.950], [116.7015, -0.949],
        [116.7005, -0.949], [116.7005, -0.950]]]}   # digeser, luas SAMA
    d = so.ukur_penyimpangan(a, b)
    assert d["delta_luas_persen"] < 0.001, "luasnya memang tak berubah"
    assert d["geser_m"] > 40, "pergeseran 55 m tak terdeteksi"


def test_penyimpangan_geometri_tak_terbaca_mengembalikan_none():
    d = so.ukur_penyimpangan({"type": "Aneh"}, _kotak())
    assert d["geser_m"] is None and d["delta_luas_persen"] is None


# ── Pemilihan geometri untuk ditampilkan ───────────────────────────────────

def test_web_menampilkan_versi_optimize_secara_bawaan():
    doc = {"geometry": _lingkaran(n=100), "geometry_opt": _kotak()}
    assert so.pilih_geometri_tampil(doc) == _kotak()


def test_saklar_lihat_asli_mengembalikan_yang_asli():
    asli = _lingkaran(n=100)
    doc = {"geometry": asli, "geometry_opt": _kotak()}
    assert so.pilih_geometri_tampil(doc, pakai_asli=True) == asli


def test_node_belum_dioptimalkan_tetap_tampil():
    """Peta TIDAK BOLEH kehilangan bentuknya hanya karena optimasi belum
    dijalankan — itu regresi diam yang paling mudah terlewat."""
    asli = _kotak()
    assert so.pilih_geometri_tampil({"geometry": asli}) == asli
    assert so.pilih_geometri_tampil({"geometry": asli, "geometry_opt": None}) == asli
    assert so.pilih_geometri_tampil({}) is None


def test_ringkas_optimasi_untuk_layar():
    r = so.ringkas_optimasi({
        "geometry_opt": _kotak(),
        "optimasi": {"titik_asli": 1000, "titik_hasil": 120,
                     "hemat_persen": 88.0, "geser_m": 0.12,
                     "delta_luas_persen": 0.03, "pada": "2026-07-28T00:00:00"}})
    assert r["dioptimalkan"] is True
    assert r["titik_asli"] == 1000 and r["titik_hasil"] == 120
    assert r["hemat_persen"] == 88.0


def test_ringkas_optimasi_node_polos():
    r = so.ringkas_optimasi({"geometry": _kotak()})
    assert r["dioptimalkan"] is False
    assert r["titik_asli"] == 0 and r["hemat_persen"] == 0.0
