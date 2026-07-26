"""Uji impor_geo_utils — fixture dibangun DI DALAM uji (KML string, SHP via
pyshp Writer in-memory, KMZ via zipfile) sehingga tak ada file biner di repo."""
import io
import json
import zipfile

import pytest

import impor_geo_utils as ig
import spasial_utils as su
import topologi_utils as tu

pytest.importorskip("shapefile")
pytest.importorskip("utm")


# ── fixture pembangun ───────────────────────────────────────────────────────

KML_DUA_FITUR = b"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document>
 <Placemark><name>Gedung A</name>
  <ExtendedData><Data name="kode"><value>GA-01</value></Data></ExtendedData>
  <Polygon><outerBoundaryIs><LinearRing><coordinates>
   116.70,-1.40,0 116.71,-1.40,0 116.71,-1.39,0 116.70,-1.39,0
  </coordinates></LinearRing></outerBoundaryIs>
  <innerBoundaryIs><LinearRing><coordinates>
   116.703,-1.397 116.707,-1.397 116.707,-1.393 116.703,-1.393 116.703,-1.397
  </coordinates></LinearRing></innerBoundaryIs></Polygon>
 </Placemark>
 <Placemark><name>Titik Saja</name>
  <Point><coordinates>116.75,-1.35,0</coordinates></Point>
 </Placemark>
 <Placemark><name>Gedung B</name>
  <Polygon><outerBoundaryIs><LinearRing><coordinates>
   116.80,-1.40 116.81,-1.40 116.81,-1.39 116.80,-1.40
  </coordinates></LinearRing></outerBoundaryIs></Polygon>
 </Placemark>
</Document></kml>"""

# WKT .prj ala ESRI untuk UTM zona 50 Selatan (wilayah IKN).
PRJ_UTM_50S = (b'PROJCS["WGS_1984_UTM_Zone_50S",GEOGCS["GCS_WGS_1984",'
               b'DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],'
               b'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],'
               b'PROJECTION["Transverse_Mercator"],'
               b'PARAMETER["False_Easting",500000.0],'
               b'PARAMETER["False_Northing",10000000.0],'
               b'PARAMETER["Central_Meridian",117.0],UNIT["Meter",1.0]]')
PRJ_WGS84 = (b'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",'
             b'SPHEROID["WGS_1984",6378137.0,298.257223563]],'
             b'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]')
PRJ_MERCATOR = (b'PROJCS["WGS_1984_Web_Mercator_Auxiliary_Sphere",'
                b'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",'
                b'SPHEROID["WGS_1984",6378137.0,298.257223563]]],'
                b'PROJECTION["Mercator_Auxiliary_Sphere"]]')


def _bangun_shp_zip(poligon_xy, nama_fitur, prj: bytes = None,
                    cpg: bytes = None, field="NAMA"):
    """Bangun zip shapefile in-memory dengan pyshp Writer."""
    import shapefile as pyshp
    shp, shx, dbf = io.BytesIO(), io.BytesIO(), io.BytesIO()
    w = pyshp.Writer(shp=shp, shx=shx, dbf=dbf, shapeType=pyshp.POLYGON,
                     encoding="utf-8")
    w.field(field, "C", size=80)
    for cincin, nama in zip(poligon_xy, nama_fitur):
        w.poly([cincin])
        w.record(nama)
    w.close()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("data.shp", shp.getvalue())
        z.writestr("data.shx", shx.getvalue())
        z.writestr("data.dbf", dbf.getvalue())
        if prj is not None:
            z.writestr("data.prj", prj)
        if cpg is not None:
            z.writestr("data.cpg", cpg)
    return buf.getvalue()


# Kotak WGS84 dekat IKN (searah jarum jam — konvensi cincin luar shapefile).
KOTAK_DERAJAT = [(116.70, -1.40), (116.70, -1.39), (116.71, -1.39),
                 (116.71, -1.40), (116.70, -1.40)]
# Kotak UTM zona 50S (meter) di sekitar area yang sama.
KOTAK_UTM = [(466000.0, 9845000.0), (466000.0, 9846000.0),
             (467000.0, 9846000.0), (467000.0, 9845000.0),
             (466000.0, 9845000.0)]


# ── deteksi format ──────────────────────────────────────────────────────────

def test_deteksi_format_dari_isi_bukan_ekstensi():
    shp_zip = _bangun_shp_zip([KOTAK_DERAJAT], ["A"], prj=PRJ_WGS84)
    assert ig.deteksi_format("berkas.zip", shp_zip) == "shp_zip"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("doc.kml", KML_DUA_FITUR)
    assert ig.deteksi_format("peta.zip", buf.getvalue()) == "kmz"   # zip ≠ selalu shp
    assert ig.deteksi_format("d.kml", KML_DUA_FITUR) == "kml"
    assert ig.deteksi_format("d.geojson", b'{"type":"FeatureCollection"}') == "geojson"
    assert ig.deteksi_format("tanpa-ekstensi", b'{"type":"Feature"}') == "geojson"
    assert ig.deteksi_format("x.txt", b"halo dunia") is None


# ── KML / KMZ ───────────────────────────────────────────────────────────────

def test_kml_poligon_lubang_dan_penutupan_cincin():
    fitur = ig.parse_kml(KML_DUA_FITUR)
    assert [f["nama"] for f in fitur] == ["Gedung A", "Gedung B"]   # titik dilewati
    a = fitur[0]
    assert a["atribut"]["kode"] == "GA-01"                # ExtendedData terbaca
    assert len(a["geometry"]["coordinates"]) == 2         # luar + lubang
    luar = a["geometry"]["coordinates"][0]
    assert luar[0] == luar[-1]                            # cincin KML tak tertutup → ditutup
    # hasil parse lolos validator struktur repo ini
    assert su.validasi_geometri(a["geometry"]) is None
    assert su.validasi_geometri(fitur[1]["geometry"]) is None


def test_kml_dengan_doctype_ditolak():
    jahat = b'<?xml version="1.0"?><!DOCTYPE kml [<!ENTITY x "y">]><kml></kml>'
    with pytest.raises(ValueError, match="DOCTYPE"):
        ig.parse_kml(jahat)


def test_kmz_membaca_kml_di_dalam_zip():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("files/ikon.png", b"\x89PNG")
        z.writestr("doc.kml", KML_DUA_FITUR)
    fitur = ig.parse_kmz(buf.getvalue())
    assert len(fitur) == 2
    with pytest.raises(ValueError, match="rusak|zip"):
        ig.parse_kmz(b"bukan zip sama sekali")


# ── GeoJSON ─────────────────────────────────────────────────────────────────

def test_geojson_featurecollection_dan_nama():
    dok = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"nama": "Blok C", "luas": 12},
         "geometry": {"type": "Polygon",
                      "coordinates": [[list(t) for t in KOTAK_DERAJAT]]}},
        {"type": "Feature", "properties": {},
         "geometry": {"type": "Point", "coordinates": [1, 2]}},
    ]}
    fitur = ig.parse_geojson(json.dumps(dok).encode())
    assert len(fitur) == 1 and fitur[0]["nama"] == "Blok C"
    assert fitur[0]["atribut"]["luas"] == "12"            # atribut → string
    with pytest.raises(ValueError):
        ig.parse_geojson(b"{bukan json")


# ── .prj / CRS ──────────────────────────────────────────────────────────────

def test_baca_crs_prj_varian():
    assert ig.baca_crs_prj(PRJ_WGS84.decode())["jenis"] == "wgs84"
    utm = ig.baca_crs_prj(PRJ_UTM_50S.decode())
    assert utm == {"jenis": "utm", "zona": 50, "utara": False}   # 10jt = selatan
    # gaya EPSG: "UTM zone 50S" eksplisit
    epsg = ig.baca_crs_prj('PROJCS["WGS 84 / UTM zone 50S",GEOGCS["WGS 84"]]')
    assert epsg["jenis"] == "utm" and epsg["zona"] == 50 and epsg["utara"] is False
    lain = ig.baca_crs_prj(PRJ_MERCATOR.decode())
    assert lain["jenis"] == "tak_didukung" and "Mercator" in lain["nama"]
    assert ig.baca_crs_prj("") is None


# ── SHP ─────────────────────────────────────────────────────────────────────

def test_shp_wgs84_terbaca_dengan_field():
    data = _bangun_shp_zip([KOTAK_DERAJAT], ["Kantor Pusat"], prj=PRJ_WGS84,
                           cpg=b"UTF-8")
    hasil = ig.parse_shp_zip(data)
    assert hasil["crs"]["jenis"] == "wgs84"
    assert hasil["fields"] == ["NAMA"]
    assert hasil["fitur"][0]["atribut"]["NAMA"] == "Kantor Pusat"
    assert su.validasi_geometri(hasil["fitur"][0]["geometry"]) is None
    assert hasil["peringatan"] == []                      # ada .cpg → tanpa keluhan


def test_shp_utm_dikonversi_ke_wgs84_lon_lat():
    """Jebakan #2 riset: keluaran WAJIB [bujur, lintang]. Kotak UTM 50S di
    dekat IKN harus mendarat di ~116–117°BT, ~-1,4°LS — bukan tertukar."""
    data = _bangun_shp_zip([KOTAK_UTM], ["Tapak UTM"], prj=PRJ_UTM_50S)
    hasil = ig.parse_shp_zip(data)
    assert hasil["crs"]["jenis"] == "utm"
    cincin = hasil["fitur"][0]["geometry"]["coordinates"][0]
    for lon, lat in cincin:
        assert 116.0 < lon < 118.0, f"bujur {lon} di luar wilayah IKN"
        assert -2.0 < lat < -0.5, f"lintang {lat} di luar wilayah IKN"
    assert su.validasi_geometri(hasil["fitur"][0]["geometry"]) is None


def test_shp_tanpa_prj_koordinat_derajat_diasumsikan_wgs84():
    data = _bangun_shp_zip([KOTAK_DERAJAT], ["A"])
    hasil = ig.parse_shp_zip(data)
    assert hasil["crs"]["jenis"] == "wgs84"
    assert any("DIASUMSIKAN" in p for p in hasil["peringatan"])


def test_shp_tanpa_prj_koordinat_meter_ditolak():
    """Menebak CRS untuk koordinat ratusan ribu = denah di lokasi salah tanpa
    galat. Tolak tegas."""
    data = _bangun_shp_zip([KOTAK_UTM], ["A"])
    with pytest.raises(ValueError, match="koordinat|tak dapat ditentukan"):
        ig.parse_shp_zip(data)


def test_shp_proyeksi_asing_ditolak_dengan_nama():
    data = _bangun_shp_zip([KOTAK_DERAJAT], ["A"], prj=PRJ_MERCATOR)
    with pytest.raises(ValueError, match="Mercator"):
        ig.parse_shp_zip(data)


def test_shp_tanpa_dbf_ditolak():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("x.shp", b"\x00" * 100)
    with pytest.raises(ValueError, match="dbf"):
        ig.parse_shp_zip(buf.getvalue())


# ── pintu seragam & pembersihan ─────────────────────────────────────────────

def test_parse_file_seragam_semua_format():
    shp = _bangun_shp_zip([KOTAK_DERAJAT], ["A"], prj=PRJ_WGS84)
    assert ig.parse_file("a.zip", shp)["format"] == "shp"
    assert ig.parse_file("a.kml", KML_DUA_FITUR)["format"] == "kml"
    with pytest.raises(ValueError, match="Format"):
        ig.parse_file("a.bin", b"\x00\x01\x02")


BOWTIE = {"type": "Polygon", "coordinates": [[
    [116.70, -1.40], [116.80, -1.30], [116.80, -1.40], [116.70, -1.30],
    [116.70, -1.40]]]}
KOTAK_SAH = {"type": "Polygon",
             "coordinates": [[list(t) for t in KOTAK_DERAJAT]]}


def test_bersihkan_fitur_sah_lolos_apa_adanya():
    g, alasan = ig.bersihkan_fitur(KOTAK_SAH)
    assert alasan is None and g is KOTAK_SAH


def test_bersihkan_fitur_bowtie_tanpa_perbaiki_dilewati():
    g, alasan = ig.bersihkan_fitur(BOWTIE, perbaiki=False)
    assert g is None and "topologi" in alasan


def test_bersihkan_fitur_bowtie_dengan_perbaiki_diperbaiki():
    """Luas shoelace bow-tie simetris = 0 (cuping saling meniadakan) — pagar
    luas TIDAK boleh menolak kasus perbaikan utama gara-gara angka asal yang
    tak bermakna. Hasil perbaikan wajib lolos kedua validator."""
    g, alasan = ig.bersihkan_fitur(BOWTIE, perbaiki=True)
    assert alasan is None and g is not None
    assert su.validasi_geometri(g) is None
    assert tu.validasi_topologi(g) is None


def test_bersihkan_fitur_struktur_rusak_dilewati():
    g, alasan = ig.bersihkan_fitur({"type": "Polygon", "coordinates": "x"})
    assert g is None and "struktur" in alasan


# ── mojibake ────────────────────────────────────────────────────────────────

def test_deteksi_mojibake():
    assert ig.deteksi_mojibake("Zona Inti Caf�") is True
    assert ig.deteksi_mojibake("CafÃ© Timur") is True
    assert ig.deteksi_mojibake("Café Timur") is False
    assert ig.deteksi_mojibake("") is False
