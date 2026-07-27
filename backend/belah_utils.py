"""BELAH POLIGON DENGAN GARIS — helper MURNI (Fase 16).

Alat "potong" bawaan geoman hanya bisa MENGURANGI: Anda menggambar poligon, dan
irisannya dibuang dari bentuk asal. Itu tepat untuk melubangi, tetapi bukan yang
dibutuhkan penataan denah — memecah satu kawasan menjadi dua kawasan bersebelahan
yang keduanya TETAP ADA. Menggambar ulang dua poligon dari nol berarti batas
bersamanya tak pernah benar-benar berimpit: selalu tersisa celah atau tumpang
tindih beberapa meter yang lalu ditangkap validasi topologi.

Membelah dengan satu garis menyelesaikannya dari sumbernya — kedua bagian
berbagi PERSIS deret verteks yang sama di sisi potongnya.

Modul ini MURNI (tanpa I/O, tanpa DB) supaya bisa diuji tanpa infrastruktur.
"""
from typing import Optional

# Plafon verteks garis pembelah. Garis pembelah adalah goresan manusia (2–50
# titik); ribuan titik hampir pasti jejak GPS yang salah tempel, dan membelah
# dengannya membuat shapely bekerja sangat lama tanpa hasil yang berguna.
MAKS_TITIK_GARIS = 2000
# Bagian yang luasnya di bawah ini (m²) dianggap serpihan akibat garis yang
# menyerempet sudut — bukan wilayah yang dimaksud operator.
MIN_LUAS_BAGIAN_M2 = 1.0
# Toleransi kekekalan luas: jumlah luas bagian harus ≈ luas asal.
TOLERANSI_LUAS = 0.02


def _shapely():
    """Impor DITUNDA — sama seperti topologi_utils: shapely berat dan tak semua
    jalur repo membutuhkannya."""
    import shapely.geometry as sg
    import shapely.ops as so
    return sg, so


def jumlah_titik_garis(garis) -> int:
    if not isinstance(garis, dict):
        return 0
    koor = garis.get("coordinates") or []
    if garis.get("type") == "LineString":
        return len(koor)
    if garis.get("type") == "MultiLineString":
        return sum(len(c or []) for c in koor)
    return 0


def validasi_garis(garis) -> Optional[str]:
    """Pesan galat bila garis tak layak dipakai membelah, atau None."""
    if not isinstance(garis, dict):
        return "Garis pembelah tidak sah"
    if garis.get("type") not in ("LineString", "MultiLineString"):
        return ("Garis pembelah harus berupa GARIS — gambar dengan alat garis, "
                "bukan poligon atau titik")
    n = jumlah_titik_garis(garis)
    if n < 2:
        return "Garis pembelah butuh minimal dua titik"
    if n > MAKS_TITIK_GARIS:
        return (f"Garis pembelah punya {n} titik (maks {MAKS_TITIK_GARIS}) — "
                "gambar garis sederhana yang memotong wilayah")
    return None


def belah_poligon(geometry: dict, garis: dict) -> dict:
    """Belah poligon dengan garis → {"bagian": [geojson...], "galat": str}.

    `bagian` kosong bila gagal; `galat` selalu berisi kalimat yang bisa
    ditindaklanjuti operator, bukan pesan pustaka.
    """
    galat = validasi_garis(garis)
    if galat:
        return {"bagian": [], "galat": galat}
    if not isinstance(geometry, dict) or geometry.get("type") not in (
            "Polygon", "MultiPolygon"):
        return {"bagian": [], "galat": "Bentuk yang dibelah harus poligon"}

    try:
        sg, so = _shapely()
    except ImportError:
        return {"bagian": [], "galat": "Pustaka geometri tak tersedia di server"}

    try:
        poli = sg.shape(geometry)
        ln = sg.shape(garis)
    except Exception:
        return {"bagian": [], "galat": "Geometri tak dapat dibaca"}

    if not poli.is_valid:
        # Membelah bentuk yang topologinya sudah rusak menghasilkan pecahan yang
        # lebih rusak lagi. Perbaiki dulu lewat alat yang memang untuk itu.
        return {"bagian": [], "galat": ("Bentuk asal bertopologi rusak — "
                                        "perbaiki dulu sebelum dibelah")}

    try:
        hasil = so.split(poli, ln)
    except Exception:
        return {"bagian": [], "galat": "Pembelahan gagal — coba garis yang lebih sederhana"}

    bagian = [g for g in getattr(hasil, "geoms", [hasil])
              if g.geom_type in ("Polygon", "MultiPolygon") and not g.is_empty]
    # Serpihan mikro dibuang: garis yang menyerempet sudut menyisakan pecahan
    # beberapa sentimeter persegi yang tak pernah dimaksudkan siapa pun.
    bagian = [g for g in bagian if _luas_kasar(g) >= MIN_LUAS_BAGIAN_M2]

    if len(bagian) < 2:
        # Inilah kegagalan yang PALING SERING terjadi di lapangan, dan pesan
        # pustaka ("split failed") sama sekali tak menolong. shapely hanya
        # membelah bila garis MELINTAS PENUH: kedua ujungnya wajib berada di
        # LUAR poligon. Garis yang berhenti persis di dalam tak memisahkan apa
        # pun, dan bagi mata operator itu tampak seperti alatnya rusak.
        return {"bagian": [], "galat": (
            "Garis tidak membelah wilayah — kedua ujung garis harus keluar "
            "melewati batas, bukan berhenti di dalamnya. Tarik garis melintas "
            "penuh dari sisi satu ke sisi seberang.")}

    # Kekekalan luas: shapely tak menjamin apa pun bila geometri masukan aneh.
    # Bagian yang jumlahnya tak sepadan dengan asal berarti ada yang hilang —
    # lebih baik menolak daripada diam-diam memangkas wilayah.
    luas_asal = _luas_kasar(poli)
    luas_bagian = sum(_luas_kasar(g) for g in bagian)
    if luas_asal > 0 and abs(luas_bagian - luas_asal) / luas_asal > TOLERANSI_LUAS:
        return {"bagian": [], "galat": (
            "Hasil pembelahan tak sepadan dengan luas asal — dibatalkan agar "
            "tak ada wilayah yang hilang diam-diam")}

    # Terbesar dulu: bagian terbesar mewarisi identitas node asal, sisanya jadi
    # node baru. Urutan ini yang membuat "belah" terasa seperti memotong, bukan
    # seperti mengganti node dengan dua node asing.
    bagian.sort(key=_luas_kasar, reverse=True)
    return {"bagian": [sg.mapping(g) for g in bagian], "galat": ""}


def _luas_kasar(g) -> float:
    """Luas dalam m² PERKIRAAN dari geometri shapely berkoordinat derajat.

    Dipakai HANYA untuk mengurutkan & menyaring serpihan, jadi proyeksi
    setara-persegi lokal sudah memadai — sama seperti spasial_utils.luas_kasar_m2.
    """
    import math
    try:
        c = g.centroid
        m_lat = math.pi * 6371008.8 / 180.0
        m_lon = m_lat * math.cos(math.radians(c.y))
        return abs(g.area) * m_lat * m_lon
    except Exception:
        return 0.0


def nama_bagian(nama_asal: str, urutan: int) -> str:
    """Nama untuk pecahan ke-N. Bagian pertama MEMPERTAHANKAN nama asal supaya
    riwayat, tautan aset, dan kebiasaan operator tak putus."""
    dasar = str(nama_asal or "Wilayah").strip()[:100]
    return dasar if urutan <= 1 else f"{dasar} ({urutan})"
