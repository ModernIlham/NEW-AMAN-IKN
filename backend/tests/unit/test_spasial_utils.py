"""Uji helper spasial murni — parsing koordinat & pembentukan GeoJSON.

Fokus pada jebakan yang GAGAL SENYAP (tanpa exception, tanpa log) sehingga
hanya bisa ditangkap oleh uji: urutan bujur/lintang terbalik, NaN yang lolos
perbandingan, dan Null Island.
"""
import spasial_utils as su


# ── parsing dasar ───────────────────────────────────────────────────────────

def test_parse_menerima_koma_desimal_indonesia():
    """Input lapangan & tempelan Excel Indonesia memakai koma desimal."""
    assert su.parse_lintang("-0,8241") == -0.8241
    assert su.parse_bujur("116,7013") == 116.7013
    # titik desimal tetap jalan
    assert su.parse_lintang("-0.8241") == -0.8241


def test_parse_menerima_angka_dan_spasi():
    assert su.parse_lintang(-0.82) == -0.82
    assert su.parse_bujur("  116.70  ") == 116.70


def test_parse_menolak_kosong_dan_sampah():
    for jelek in (None, "", "   ", "abc", "-", "1,2,3", [], {}):
        assert su.parse_lintang(jelek) is None


def test_parse_menolak_tak_berhingga():
    """NaN/inf WAJIB ditolak eksplisit: perbandingan NaN selalu False sehingga
    tanpa cek isfinite nilai itu bisa lolos lewat celah logika."""
    for jelek in ("nan", "NaN", "inf", "-inf", "Infinity", float("nan"), float("inf")):
        assert su.parse_lintang(jelek) is None, jelek
        assert su.parse_bujur(jelek) is None, jelek


def test_batas_rentang_lintang_vs_bujur_berbeda():
    """Lintang +-90, bujur +-180 — batas yang berbeda, bukan salah ketik."""
    assert su.parse_lintang("90") == 90.0
    assert su.parse_lintang("-90") == -90.0
    assert su.parse_lintang("90.001") is None
    assert su.parse_bujur("180") == 180.0
    assert su.parse_bujur("-180") == -180.0
    assert su.parse_bujur("180.001") is None
    # Bujur IKN (~116) SAH sebagai bujur tetapi TIDAK SAH sebagai lintang.
    assert su.parse_bujur("116.7") == 116.7
    assert su.parse_lintang("116.7") is None


# ── GeoJSON ─────────────────────────────────────────────────────────────────

def test_geojson_memakai_urutan_bujur_dulu():
    """RFC 7946: [bujur, lintang] — kebalikan cara manusia menyebut. Urutan
    terbalik menempatkan IKN di Samudra Hindia tanpa error apa pun."""
    titik = su.bangun_geo_point("-0.8241", "116.7013")
    assert titik == {"type": "Point", "coordinates": [116.7013, -0.8241]}
    # Pastikan bujur benar-benar di indeks 0 (nilai besar), lintang di indeks 1.
    assert titik["coordinates"][0] == 116.7013
    assert titik["coordinates"][1] == -0.8241


def test_null_island_ditolak():
    """(0,0) = penanda de-facto parsing gagal; tak ada BMN IKN di Teluk Guinea."""
    assert su.bangun_geo_point(0, 0) is None
    assert su.bangun_geo_point("0", "0") is None
    assert su.bangun_geo_point("0,0", "0,0") is None
    # Tetapi nol pada SATU sumbu saja tetap sah (garis khatulistiwa / meridian).
    assert su.bangun_geo_point(0, 116.7) is not None
    assert su.bangun_geo_point(-0.82, 0) is not None


def test_geojson_none_bila_salah_satu_tak_valid():
    assert su.bangun_geo_point(None, "116.7") is None
    assert su.bangun_geo_point("-0.82", None) is None
    assert su.bangun_geo_point("", "") is None
    assert su.bangun_geo_point("116.7", "116.7") is None  # lintang di luar batas


# ── deteksi tertukar ────────────────────────────────────────────────────────

def test_deteksi_koordinat_tertukar():
    """Untuk Indonesia, tertukar hampir selalu ketahuan sendiri: bujur nusantara
    (95..141) melanggar batas lintang +-90."""
    # Ditukar: lintang diisi 116.7 (bujur IKN), bujur diisi -0.82 (lintang IKN)
    assert su.koordinat_tertukar("116.7013", "-0.8241") is True
    # Urutan benar → bukan tertukar
    assert su.koordinat_tertukar("-0.8241", "116.7013") is False
    # Sampah bukan berarti tertukar
    assert su.koordinat_tertukar("abc", "116.7") is False
    assert su.koordinat_tertukar("999", "116.7") is False


# ── penerapan ke dokumen aset ───────────────────────────────────────────────

def test_geo_dari_aset_membaca_field_string_yang_ada():
    doc = {"koordinat_latitude": "-0,8241", "koordinat_longitude": "116,7013"}
    assert su.geo_dari_aset(doc)["coordinates"] == [116.7013, -0.8241]
    assert su.geo_dari_aset({}) is None
    assert su.geo_dari_aset(None) is None


def test_terapkan_geo_membuang_geo_basi():
    """Koordinat dikosongkan -> `geo` WAJIB ikut hilang. Bila dibiarkan, aset
    tetap muncul di kueri area pada posisi LAMANYA."""
    doc = {"koordinat_latitude": "-0.82", "koordinat_longitude": "116.7"}
    su.terapkan_geo(doc)
    assert "geo" in doc

    doc["koordinat_latitude"] = ""          # pengguna menghapus koordinat
    su.terapkan_geo(doc)
    assert "geo" not in doc


def test_terapkan_geo_idempoten():
    doc = {"koordinat_latitude": "-0.82", "koordinat_longitude": "116.7"}
    su.terapkan_geo(doc)
    pertama = dict(doc["geo"])
    su.terapkan_geo(doc)
    assert doc["geo"] == pertama


def test_operasi_geo_update_set_dan_unset():
    """Jalur update memakai OCC; helper hanya menyusun bagian $set/$unset."""
    ada = su.operasi_geo_update({"koordinat_latitude": "-0.82",
                                 "koordinat_longitude": "116.7"})
    assert ada["set"]["geo"]["coordinates"] == [116.7, -0.82]
    assert ada["unset"] == {}

    kosong = su.operasi_geo_update({"koordinat_latitude": "",
                                    "koordinat_longitude": ""})
    assert kosong["set"] == {}
    assert "geo" in kosong["unset"]


# ── kompatibilitas dengan parser lama yang digantikan ───────────────────────

def test_setara_dengan_parser_lama_pada_masukan_lazim():
    """Helper ini menggantikan `_geo_coord` (exports.py) dan `_parse_coord`
    (peta_kolaborasi.py). Perilaku pada masukan lazim harus tetap sama agar
    ekspor KML/SHP dan peta kolaborasi tidak berubah diam-diam."""
    for v, batas, harapan in [
        ("116.7013", 180.0, 116.7013),
        ("116,7013", 180.0, 116.7013),
        ("-0.8241", 90.0, -0.8241),
        ("", 180.0, None),
        (None, 180.0, None),
        ("abc", 180.0, None),
        ("181", 180.0, None),
        ("91", 90.0, None),
    ]:
        assert su.parse_koordinat(v, batas) == harapan, v


# ── penyisipan ke update parsial ────────────────────────────────────────────

def test_sisip_geo_diam_bila_update_tak_menyentuh_koordinat():
    """Update yang hanya mengubah kondisi barang TIDAK boleh menulis ulang geo."""
    perubahan = {"condition": "Rusak Ringan"}
    unset = su.sisip_geo_ke_update({"koordinat_latitude": "-0.82",
                                    "koordinat_longitude": "116.7"}, perubahan)
    assert unset == {}
    assert "geo" not in perubahan


def test_sisip_geo_menggabung_satu_sumbu_dengan_dokumen_lama():
    """Pengguna lazim memperbaiki SATU sumbu saja — sumbu lain harus tetap
    terpakai dari dokumen lama, bukan hilang."""
    lama = {"koordinat_latitude": "-0.82", "koordinat_longitude": "116.7"}
    perubahan = {"koordinat_longitude": "117,25"}   # hanya bujur diperbaiki
    unset = su.sisip_geo_ke_update(lama, perubahan)
    assert unset == {}
    assert perubahan["geo"]["coordinates"] == [117.25, -0.82]


def test_sisip_geo_unset_saat_koordinat_dikosongkan():
    lama = {"koordinat_latitude": "-0.82", "koordinat_longitude": "116.7"}
    perubahan = {"koordinat_latitude": ""}
    unset = su.sisip_geo_ke_update(lama, perubahan)
    assert unset == {"geo": ""}
    assert "geo" not in perubahan


def test_sisip_geo_menangani_dokumen_lama_kosong():
    perubahan = {"koordinat_latitude": "-0.82", "koordinat_longitude": "116.7"}
    unset = su.sisip_geo_ke_update({}, perubahan)
    assert unset == {}
    assert perubahan["geo"]["coordinates"] == [116.7, -0.82]
