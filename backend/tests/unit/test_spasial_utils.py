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


# ═══════════════════════════════════════════════════════════════════════════
# HIERARKI (Fase 2)
# ═══════════════════════════════════════════════════════════════════════════

def test_kawasan_lebih_luas_daripada_zona():
    """KOREKSI INTI hasil riset: UU 26/2007 + PP 21/2021 menetapkan zona sebagai
    'kawasan dengan fungsi tertentu' — jadi zona SEJENIS kawasan, bukan induknya.
    Kawasan karena itu berada di ATAS, bukan di bawah zona seperti dugaan awal."""
    assert su.ordinal_level("KAWASAN") < su.ordinal_level("WP")
    assert su.parent_level_sah("KAWASAN", "WP") is True
    assert su.parent_level_sah("WP", "KAWASAN") is False


def test_urutan_registry_menaik_dan_ruangan_paling_kecil():
    ordinals = [b[0] for b in su.LEVEL_SPASIAL]
    assert ordinals == sorted(ordinals), "registry harus terurut besar->kecil"
    assert len(set(ordinals)) == len(ordinals), "ordinal wajib unik"
    # RUANGAN lebih kecil (lebih dalam) daripada GEDUNG dan LANTAI
    assert su.ordinal_level("GEDUNG") < su.ordinal_level("LANTAI") < su.ordinal_level("RUANGAN")


def test_ruangan_satu_satunya_level_wajib():
    """Ruangan = jangkar KIR & DBR (PMK 181/2016)."""
    wajib = [lv["kode_baku"] for lv in su.daftar_level() if lv["wajib"]]
    assert wajib == ["RUANGAN"]


def test_preset_penamaan_hanya_mengganti_label_bukan_data():
    akrab = {lv["kode_baku"]: lv["label"] for lv in su.daftar_level("ikn_akrab")}
    baku = {lv["kode_baku"]: lv["label"] for lv in su.daftar_level("rdtr_baku")}
    # Kosakata pemilik dipertahankan di preset akrab...
    assert akrab["WP"] == "Zona (WP)"
    assert akrab["SWP"] == "Distrik (Sub-WP)"
    # ...sementara kode baku tetap benar untuk dokumen resmi.
    assert baku["WP"] == "Wilayah Perencanaan"
    assert baku["SWP"] == "Sub Wilayah Perencanaan"
    assert set(akrab) == set(baku), "kode_baku identik di kedua preset"


def test_ordinal_berjarak_agar_level_baru_bisa_disisipkan():
    """Jarak 10 antar tingkat utama supaya penyisipan tak butuh migrasi."""
    assert su.ordinal_level("KAWASAN") == 20 and su.ordinal_level("WP") == 30
    assert su.ordinal_level("SUBBLOK") == 55  # sisipan di antara 50 dan 60


def test_lantai_bukan_containment_melainkan_sumbu_z():
    """Basement lazim MELEBIHI footprint gedung; memaksa containment ketat
    membuat tiap basement dilaporkan melanggar."""
    assert su.level_dari_kode("LANTAI")["containment"] == "sumbu_z"
    assert su.level_dari_kode("GEDUNG")["containment"] == "ketat"
    assert su.level_dari_kode("PERSIL")["containment"] == "longgar"


def test_level_tak_dikenal_ditolak():
    assert su.level_dari_kode("ENTAHAPA") is None
    assert su.ordinal_level("") is None
    assert su.parent_level_sah("ENTAHAPA", "RUANGAN") is False


def test_tingkat_boleh_dilompati():
    """Satker daerah lazim hanya Tapak->Gedung->Lantai->Ruangan tanpa Blok/Persil.
    Memaksa rantai lengkap akan melahirkan node kosong palsu."""
    assert su.parent_level_sah("TAPAK", "RUANGAN") is True
    assert su.parent_level_sah("KAWASAN", "GEDUNG") is True


# ── pohon ───────────────────────────────────────────────────────────────────

_POHON = {"ruang": "lantai", "lantai": "gedung", "gedung": "tapak"}


def test_rantai_induk_terjauh_ke_terdekat():
    assert su.rantai_induk("ruang", _POHON) == ["tapak", "gedung", "lantai"]
    assert su.rantai_induk("tapak", _POHON) == []          # akar


def test_jalur_dibungkus_pemisah_di_kedua_ujung():
    """Pembungkus membuat prefix ',A,' tak salah cocok dengan node 'A2'."""
    hasil = su.turunkan_pohon("ruang", "lantai", _POHON)
    assert hasil["jalur"] == ",tapak,gedung,lantai,ruang,"
    assert hasil["jalur"].startswith(",") and hasil["jalur"].endswith(",")
    assert hasil["kedalaman"] == 3
    # Uji anti-salah-cocok yang jadi alasan pembungkus itu ada:
    assert ",A," not in su.bangun_jalur([], "A2")


def test_pindah_ke_akar_mengosongkan_ancestors():
    hasil = su.turunkan_pohon("gedung", None, _POHON)
    assert hasil["ancestors"] == []
    assert hasil["jalur"] == ",gedung,"
    assert hasil["kedalaman"] == 0


def test_siklus_terdeteksi_sebelum_merusak_pohon():
    """Kasus nyata: operator menyeret Gedung ke bawah Ruangan di dalamnya."""
    assert su.ada_siklus("gedung", "ruang", _POHON) is True   # keturunan sendiri
    assert su.ada_siklus("gedung", "gedung", _POHON) is True  # diri sendiri
    assert su.ada_siklus("gedung", "tapak", _POHON) is False  # sah
    assert su.ada_siklus("gedung", None, _POHON) is False     # jadi akar


def test_pohon_rusak_tak_membuat_menggantung():
    """Data bersiklus (mis. dari restore rusak) harus berhenti, bukan berputar."""
    rusak = {"a": "b", "b": "c", "c": "a"}
    hasil = su.rantai_induk("a", rusak)
    assert len(hasil) < 64 and len(hasil) > 0


# ── ordinal lantai (IMDF) ───────────────────────────────────────────────────

def test_basement_negatif_dan_dasar_nol():
    assert su.tebak_ordinal_lantai("B1") == -1
    assert su.tebak_ordinal_lantai("B3") == -3
    assert su.tebak_ordinal_lantai("Basement 2") == -2
    for dasar in ("G", "GF", "LD", "Lantai Dasar", "Ground"):
        assert su.tebak_ordinal_lantai(dasar) == 0, dasar


def test_konvensi_indonesia_lantai_1_adalah_dasar():
    """'Lantai 1' di Indonesia LAZIM berarti lantai dasar — beda dari konvensi
    Inggris. Itu sebabnya ordinal dipisah dari label."""
    assert su.tebak_ordinal_lantai("Lantai 1") == 0
    assert su.tebak_ordinal_lantai("Lt 5") == 4
    assert su.tebak_ordinal_lantai("2") == 1


def test_label_ambigu_tidak_ditebak():
    """Mezanin & rooftop tingginya RELATIF terhadap gedung — menebaknya justru
    menaruh lantai di urutan yang salah tanpa ada yang sadar."""
    for ambigu in ("Mezanin", "M", "Rooftop", "Atap", "", None, "xyz"):
        assert su.tebak_ordinal_lantai(ambigu) is None, ambigu


def test_ordinal_rapat_menutup_celah_tanpa_menggeser_urutan():
    """Setelah lantai dihapus atau saat gedung melompati lantai 4/13, posisi
    relatif tetap tetapi tak boleh ada lubang di tengah."""
    assert su.ordinal_rapat([-2, -1, 0, 2, 5]) == [-2, -1, 0, 1, 2]
    assert su.ordinal_rapat([0, 1, 2]) == [0, 1, 2]        # sudah rapat
    assert su.ordinal_rapat([]) == []
    assert su.ordinal_rapat([3, 3, 4]) == [0, 1]           # duplikat diciutkan
