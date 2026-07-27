"""Uji belah poligon dengan garis (Fase 16).

Kegagalan yang paling sering terjadi di lapangan BUKAN geometri rumit,
melainkan garis yang berhenti di dalam poligon — dan pesan pustaka untuk kasus
itu tak menolong siapa pun. Uji di sini memastikan kasusnya terdeteksi dan
dijelaskan, bukan sekadar "berhasil membelah kotak".
"""
import belah_utils as bu

# Kotak ±0.002° di sekitar IKN.
KOTAK = {"type": "Polygon", "coordinates": [[
    [116.700, -1.402], [116.704, -1.402], [116.704, -1.398],
    [116.700, -1.398], [116.700, -1.402]]]}


def _garis(koor):
    return {"type": "LineString", "coordinates": koor}


# ── Pembelahan yang benar ───────────────────────────────────────────────────

def test_garis_melintas_penuh_menghasilkan_dua_bagian():
    r = bu.belah_poligon(KOTAK, _garis([[116.699, -1.400], [116.705, -1.400]]))
    assert r["galat"] == ""
    assert len(r["bagian"]) == 2
    assert all(b["type"] in ("Polygon", "MultiPolygon") for b in r["bagian"])


def test_bagian_terbesar_didahulukan():
    """Bagian terbesar mewarisi identitas node asal — urutan ini yang membuat
    'belah' terasa memotong, bukan mengganti node dengan dua node asing."""
    # Potong dekat tepi bawah → bagian atas jauh lebih besar.
    r = bu.belah_poligon(KOTAK, _garis([[116.699, -1.4015], [116.705, -1.4015]]))
    assert r["galat"] == ""
    luas = [bu._luas_kasar(__import__("shapely.geometry", fromlist=["shape"])
                           .shape(b)) for b in r["bagian"]]
    assert luas[0] > luas[1]


def test_luas_kedua_bagian_setara_luas_asal():
    """Kalau jumlahnya tak sepadan, ada wilayah yang hilang diam-diam."""
    from shapely.geometry import shape
    r = bu.belah_poligon(KOTAK, _garis([[116.699, -1.400], [116.705, -1.400]]))
    asal = bu._luas_kasar(shape(KOTAK))
    total = sum(bu._luas_kasar(shape(b)) for b in r["bagian"])
    assert abs(total - asal) / asal < 0.01


def test_garis_diagonal_juga_membelah():
    r = bu.belah_poligon(KOTAK, _garis([[116.699, -1.403], [116.705, -1.397]]))
    assert r["galat"] == "" and len(r["bagian"]) == 2


def test_garis_berbelok_membelah_mengikuti_bentuknya():
    """Batas nyata jarang lurus — garis patah harus tetap bekerja."""
    r = bu.belah_poligon(KOTAK, _garis([
        [116.699, -1.4005], [116.702, -1.4005], [116.702, -1.399],
        [116.705, -1.399]]))
    assert r["galat"] == "" and len(r["bagian"]) == 2


# ── KEGAGALAN LAPANGAN YANG PALING SERING ───────────────────────────────────

def test_garis_berhenti_di_dalam_ditolak_dengan_penjelasan():
    """shapely hanya membelah bila garis MELINTAS PENUH. Garis yang berhenti di
    dalam tak memisahkan apa pun — dan bagi mata operator itu tampak persis
    seperti alatnya rusak. Pesannya wajib memberi tahu apa yang harus dilakukan."""
    r = bu.belah_poligon(KOTAK, _garis([[116.701, -1.400], [116.703, -1.400]]))
    assert r["bagian"] == []
    assert "keluar melewati batas" in r["galat"]


def test_garis_seluruhnya_di_luar_tidak_membelah():
    r = bu.belah_poligon(KOTAK, _garis([[116.710, -1.400], [116.715, -1.400]]))
    assert r["bagian"] == [] and r["galat"]


def test_garis_menyerempet_sudut_tidak_melahirkan_serpihan():
    """Garis yang lewat persis di sudut bisa menyisakan pecahan beberapa cm²
    yang tak pernah dimaksudkan siapa pun."""
    r = bu.belah_poligon(KOTAK, _garis([[116.6999, -1.4021], [116.7001, -1.4019]]))
    assert r["bagian"] == []          # serpihan disaring → gagal, bukan 2 bagian


# ── Validasi masukan ────────────────────────────────────────────────────────

def test_poligon_dipakai_sebagai_garis_ditolak():
    r = bu.belah_poligon(KOTAK, KOTAK)
    assert "harus berupa GARIS" in r["galat"]


def test_garis_satu_titik_ditolak():
    assert "dua titik" in bu.validasi_garis(_garis([[116.7, -1.4]]))


def test_garis_terlalu_banyak_titik_ditolak():
    besar = _garis([[116.70 + i * 1e-6, -1.40] for i in range(bu.MAKS_TITIK_GARIS + 5)])
    assert "maks" in bu.validasi_garis(besar)


def test_bentuk_asal_bukan_poligon_ditolak():
    titik = {"type": "Point", "coordinates": [116.7, -1.4]}
    r = bu.belah_poligon(titik, _garis([[116.6, -1.4], [116.8, -1.4]]))
    assert "harus poligon" in r["galat"]


def test_topologi_rusak_ditolak_sebelum_dibelah():
    """Membelah bentuk yang sudah rusak menghasilkan pecahan lebih rusak lagi."""
    dasi = {"type": "Polygon", "coordinates": [[
        [116.700, -1.402], [116.704, -1.398], [116.704, -1.402],
        [116.700, -1.398], [116.700, -1.402]]]}
    r = bu.belah_poligon(dasi, _garis([[116.699, -1.400], [116.705, -1.400]]))
    assert "topologi rusak" in r["galat"]


def test_masukan_kosong_tak_meledak():
    assert bu.belah_poligon(None, None)["galat"]
    assert bu.belah_poligon({}, {})["galat"]


# ── Penamaan pecahan ────────────────────────────────────────────────────────

def test_bagian_pertama_mempertahankan_nama_asal():
    """Riwayat, tautan aset, dan kebiasaan operator tak boleh putus."""
    assert bu.nama_bagian("Kawasan Inti", 1) == "Kawasan Inti"
    assert bu.nama_bagian("Kawasan Inti", 2) == "Kawasan Inti (2)"
    assert bu.nama_bagian("", 1) == "Wilayah"
