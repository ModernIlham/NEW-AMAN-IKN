"""Uji ekspor denah (Fase 6) — kontraknya ROUND-TRIP: apa pun yang
ekspor_geo_utils hasilkan harus terbaca balik oleh parser impor Fase 5 tanpa
kehilangan geometri/atribut. Pembandingnya parser impor SUNGGUHAN, bukan
pembaca buatan uji — sehingga kedua sisi saling mengunci.
"""
import io
import zipfile

import pytest

import ekspor_geo_utils as eg
import impor_geo_utils as ig

pytest.importorskip("shapefile")


# ── fixture node ────────────────────────────────────────────────────────────

KAWASAN = {"id": "k1", "tipe": "KAWASAN", "nama": 'Kawasan <Inti> & "Pusat"',
           "kode": "KW-1", "parent_id": None, "ordinal_level": 20,
           "status": "aktif", "ancestors_nama": []}
# Poligon berlubang, DITULIS dalam orientasi RFC 7946 (luar CCW, lubang CW)
# sebagaimana tersimpan di MongoDB.
GEDUNG = {"id": "g1", "tipe": "GEDUNG", "nama": "Menara A", "kode": "GD-01",
          "parent_id": "k1", "ordinal_level": 80, "status": "aktif",
          "ancestors_nama": ['Kawasan <Inti> & "Pusat"'],
          "metrik": {"luas_m2": 1234.56},
          "geometry": {"type": "Polygon", "coordinates": [
              [[116.70, -1.40], [116.71, -1.40], [116.71, -1.39],
               [116.70, -1.39], [116.70, -1.40]],
              [[116.703, -1.397], [116.707, -1.397], [116.707, -1.393],
               [116.703, -1.393], [116.703, -1.397]],
          ]}}
MULTI = {"id": "m1", "tipe": "TAPAK", "nama": "Kampus Dua Tapak", "kode": "TP-9",
         "parent_id": "k1", "ordinal_level": 70, "status": "aktif",
         "ancestors_nama": [],
         "geometry": {"type": "MultiPolygon", "coordinates": [
             [[[116.72, -1.41], [116.73, -1.41], [116.73, -1.40], [116.72, -1.41]]],
             [[[116.74, -1.41], [116.75, -1.41], [116.75, -1.40], [116.74, -1.41]]],
         ]}}
TITIK = {"id": "t1", "tipe": "TITIK", "nama": "Pos Jaga", "kode": "",
         "parent_id": "g1", "ordinal_level": 110, "status": "draft",
         "ancestors_nama": [],
         "geometry": {"type": "Point", "coordinates": [116.705, -1.395]}}
SEMUA = [KAWASAN, GEDUNG, MULTI, TITIK]


def _luas_bertanda(cincin):
    return sum(x1 * y2 - x2 * y1
               for (x1, y1), (x2, y2) in zip(cincin, cincin[1:])) / 2


# ── GeoJSON ─────────────────────────────────────────────────────────────────

def test_geojson_round_trip_geometri_eksak():
    fitur = ig.parse_geojson(eg.ke_geojson(SEMUA))
    g = next(f for f in fitur if f["nama"] == "Menara A")
    assert g["geometry"] == GEDUNG["geometry"]        # eksak, bukan hampir
    assert g["atribut"]["kode"] == "GD-01"
    # Kunci 'nama' disengaja agar prapilih dropdown impor (regex nama|name|
    # label) memetakannya otomatis saat diimpor balik.
    assert "nama" in g["atribut"]


def test_geojson_tanpa_geometri_dilewati():
    fitur = ig.parse_geojson(eg.ke_geojson([KAWASAN, GEDUNG]))
    assert [f["nama"] for f in fitur] == ["Menara A"]


# ── KML / KMZ ───────────────────────────────────────────────────────────────

def test_kml_round_trip_lubang_multi_dan_escaping():
    """Nama ber-<XML> & kutip tak boleh merusak dokumen; lubang dan
    MultiPolygon harus selamat lewat parser impor."""
    fitur = ig.parse_kml(eg.ke_kml(SEMUA, {"GEDUNG": "Gedung"}))
    nama = {f["nama"] for f in fitur}
    assert "Menara A" in nama and "Kampus Dua Tapak" in nama
    g = next(f for f in fitur if f["nama"] == "Menara A")
    assert len(g["geometry"]["coordinates"]) == 2     # luar + lubang
    assert g["atribut"]["kode"] == "GD-01"
    m = next(f for f in fitur if f["nama"] == "Kampus Dua Tapak")
    assert m["geometry"]["type"] == "MultiPolygon"


def test_kml_folder_bersarang_mengikuti_hierarki():
    teks = eg.ke_kml(SEMUA, {}).decode("utf-8")
    # Kawasan ber-anak → Folder; namanya ter-escape, bukan XML mentah.
    assert "<Folder>" in teks
    assert "Kawasan &lt;Inti&gt; &amp; &quot;Pusat&quot;" in teks \
        or "Kawasan &lt;Inti&gt; &amp; \"Pusat\"" in teks
    assert "<Kawasan <Inti>" not in teks


def test_kml_siklus_data_tak_membuat_rekursi_abadi():
    a = {"id": "a", "parent_id": "b", "nama": "A", "ordinal_level": 20,
         "ancestors_nama": [], "status": "aktif", "tipe": "KAWASAN"}
    b = {"id": "b", "parent_id": "a", "nama": "B", "ordinal_level": 20,
         "ancestors_nama": [], "status": "aktif", "tipe": "KAWASAN"}
    assert eg.ke_kml([a, b], {})                      # selesai, tanpa hang


def test_kmz_terbaca_balik():
    assert len(ig.parse_kmz(eg.ke_kmz(eg.ke_kml(SEMUA, {})))) == 2


# ── Shapefile ───────────────────────────────────────────────────────────────

def test_shp_round_trip_lubang_multi_atribut():
    hasil = ig.parse_file("denah.zip", eg.ke_shp_zip(SEMUA))
    assert hasil["crs"] == {"jenis": "wgs84"}         # .prj dikenali, tanpa tebakan
    assert hasil["peringatan"] == []
    g = next(f for f in hasil["fitur"] if f["atribut"]["NAMA"] == "Menara A")
    assert len(g["geometry"]["coordinates"]) == 2     # lubang selamat
    assert g["atribut"]["KODE"] == "GD-01"
    assert g["atribut"]["LOKASI"].startswith("Kawasan")
    m = next(f for f in hasil["fitur"] if f["atribut"]["NAMA"] == "Kampus Dua Tapak")
    assert m["geometry"]["type"] == "MultiPolygon"


def test_shp_orientasi_cincin_esri_di_file_mentah():
    """Pembaca pyshp TOLERAN terhadap orientasi salah (terverifikasi empiris),
    jadi round-trip saja tak cukup — arah putaran diperiksa langsung dari file:
    luar wajib CW, lubang CCW (spek ESRI, kebalikan RFC 7946)."""
    import shapefile as pyshp
    z = zipfile.ZipFile(io.BytesIO(eg.ke_shp_zip([GEDUNG])))
    r = pyshp.Reader(shp=io.BytesIO(z.read("denah.shp")),
                     shx=io.BytesIO(z.read("denah.shx")),
                     dbf=io.BytesIO(z.read("denah.dbf")))
    sh = r.shape(0)
    idx = list(sh.parts) + [len(sh.points)]
    arah = ["CW" if _luas_bertanda(sh.points[a:b]) < 0 else "CCW"
            for a, b in zip(idx, idx[1:])]
    assert arah == ["CW", "CCW"]


def test_shp_titik_jadi_file_terpisah():
    z = zipfile.ZipFile(io.BytesIO(eg.ke_shp_zip(SEMUA)))
    nama = set(z.namelist())
    assert {"denah.shp", "denah.prj", "denah.cpg",
            "denah_titik.shp", "BACA_SAYA.txt"} <= nama


def test_shp_tanpa_geometri_menolak():
    with pytest.raises(ValueError, match="Tidak ada node bergeometri"):
        eg.ke_shp_zip([KAWASAN])


def test_shp_nama_unicode_utf8():
    n = dict(GEDUNG, nama="Gedung Café Nusantara — Blok β")
    hasil = ig.parse_file("d.zip", eg.ke_shp_zip([n]))
    assert hasil["fitur"][0]["atribut"]["NAMA"] == "Gedung Café Nusantara — Blok β"
    assert not ig.deteksi_mojibake(hasil["fitur"][0]["atribut"]["NAMA"])


# ── Template ────────────────────────────────────────────────────────────────

def test_template_shp_terbaca_dan_ber_crs():
    hasil = ig.parse_file("t.zip", eg.template_shp_zip())
    assert len(hasil["fitur"]) == 1
    assert hasil["crs"] == {"jenis": "wgs84"}
    assert "NAMA" in hasil["fields"]


def test_template_kml_terbaca():
    fitur = ig.parse_kml(eg.template_kml())
    assert len(fitur) == 1
    assert fitur[0]["atribut"]["kode"] == "CONTOH"
