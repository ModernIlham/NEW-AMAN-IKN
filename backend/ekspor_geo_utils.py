"""EKSPOR denah spasial → GeoJSON / KML / KMZ / Shapefile-zip + template gambar.

Cermin dari impor_geo_utils (Fase 5): apa pun yang modul ini hasilkan HARUS
bisa dibaca balik oleh parser impor tanpa kehilangan geometri maupun atribut —
uji round-trip di test_ekspor_geo_utils menegakkan kontrak itu memakai parser
impor sungguhan, bukan pembanding buatan.

Dua jebakan format yang ditangani eksplisit di sini:

1. ORIENTASI CINCIN SHAPEFILE. Spek ESRI menuntut cincin luar SEARAH jarum jam
   dan lubang berlawanan — kebalikan persis RFC 7946 yang dipakai GeoJSON kita.
   pyshp 3.1.4 menulis cincin APA ADANYA (terverifikasi empiris: input CCW/CW
   tersimpan CCW/CW), dan pembaca pyshp sendiri toleran sehingga kesalahan
   orientasi tak terlihat bila diuji lewat pyshp saja. ArcGIS/QGIS yang patuh
   spek akan menafsirkan lubang sebagai poligon lepas. Maka orientasi ditegakkan
   di sini: `_cincin_arah` membalik cincin berdasarkan luas bertanda shoelace.

2. ESCAPING XML KML. Nama node adalah teks bebas buatan pengguna ("Blok <A> &
   B"). Merangkai KML dengan f-string = XML rusak (atau injeksi elemen). Seluruh
   KML dibangun lewat ElementTree yang meng-escape otomatis.

Batas DBF yang relevan (shapefile): nama field maks 10 karakter, nilai teks
maks 254 byte — LOKASI (jalur nama moyang) dipotong sadar ke 254.
"""
import io
import json
import zipfile
import xml.etree.ElementTree as ET

KML_NS = "http://www.opengis.net/kml/2.2"

# Karakter kontrol C0 (selain \t \n \r) TIDAK SAH di XML 1.0 — ElementTree
# menserialisasinya tanpa protes sehingga satu nama node beracun membuat
# seluruh file KML tak terbaca (temuan tinjauan: parse balik gagal
# "not well-formed"). DBF juga menyimpannya mentah dan pembaca ber-semantik
# C-string terpotong di \x00. Disaring di semua teks keluaran.
_KONTROL_C0 = dict.fromkeys(i for i in range(32) if i not in (9, 10, 13))


def _bersih_teks(nilai) -> str:
    return str(nilai if nilai is not None else "").translate(_KONTROL_C0)

# WKT ESRI untuk WGS84 geografis — dikenali baca_crs_prj impor sebagai 'wgs84'
# dan oleh QGIS/ArcGIS sebagai EPSG:4326.
PRJ_WGS84 = ('GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",'
             'SPHEROID["WGS_1984",6378137.0,298.257223563]],'
             'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]')

# Kotak contoh kecil dekat KIPP IKN untuk file template — pengguna menghapusnya
# setelah paham polanya.
_CONTOH_KOTAK = [[116.705, -1.402], [116.707, -1.402], [116.707, -1.400],
                 [116.705, -1.400], [116.705, -1.402]]


# ── util geometri ───────────────────────────────────────────────────────────

def _luas_bertanda(cincin) -> float:
    """Shoelace; > 0 = berlawanan jarum jam (CCW), < 0 = searah (CW)."""
    s = 0.0
    for (x1, y1), (x2, y2) in zip(cincin, cincin[1:]):
        s += x1 * y2 - x2 * y1
    return s / 2.0


def _cincin_arah(cincin, searah_jarum_jam: bool):
    """Salinan cincin dengan arah putaran yang diminta (untuk shapefile)."""
    koor = [(float(p[0]), float(p[1])) for p in cincin]
    cw_sekarang = _luas_bertanda(koor) < 0
    return koor if cw_sekarang == searah_jarum_jam else list(reversed(koor))


def _poligon_list(geom) -> list:
    """[[cincin,...], ...] — Polygon dibungkus jadi satu anggota."""
    if geom["type"] == "Polygon":
        return [geom["coordinates"]]
    return list(geom["coordinates"])


def _teks_koordinat(cincin) -> str:
    """Cincin → teks koordinat KML "lon,lat lon,lat …" (str() = repr terpendek
    Python yang round-trip float secara eksak — bukan pembulatan %.f)."""
    return " ".join(f"{float(p[0])},{float(p[1])}" for p in cincin)


# ── GeoJSON ─────────────────────────────────────────────────────────────────

def _properti_node(n: dict) -> dict:
    """Atribut yang dibawa serta tiap fitur. Kunci 'nama'/'kode' disengaja —
    dropdown impor mem-prapilih field bernama itu (regex /nama|name|label/i),
    jadi hasil ekspor yang diimpor balik terpetakan otomatis."""
    lokasi = " / ".join(n.get("ancestors_nama") or [])
    return {"id": n.get("id") or "", "tipe": n.get("tipe") or "",
            "nama": n.get("nama") or "", "kode": n.get("kode") or "",
            "lokasi": lokasi, "status": n.get("status") or "",
            "lantai": n.get("lantai") or "",
            "luas_m2": (n.get("metrik") or {}).get("luas_m2")}


def ke_geojson(nodes: list) -> bytes:
    fitur = [{"type": "Feature", "geometry": n["geometry"],
              "properties": _properti_node(n)}
             for n in nodes if n.get("geometry")]
    fc = {"type": "FeatureCollection", "features": fitur}
    return json.dumps(fc, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


# ── KML / KMZ ───────────────────────────────────────────────────────────────

def _el(induk, tag, teks=None):
    e = ET.SubElement(induk, f"{{{KML_NS}}}{tag}")
    if teks is not None:
        e.text = _bersih_teks(teks)
    return e


def _tambah_geometri_kml(placemark, geom):
    """Polygon/MultiPolygon/Point → elemen geometri KML."""
    if geom["type"] == "Point":
        p = _el(placemark, "Point")
        _el(p, "coordinates", f"{float(geom['coordinates'][0])},{float(geom['coordinates'][1])}")
        return
    poligon = _poligon_list(geom)
    wadah = placemark if len(poligon) == 1 else _el(placemark, "MultiGeometry")
    for cincin_list in poligon:
        pg = _el(wadah, "Polygon")
        for i, cincin in enumerate(cincin_list):
            batas = _el(pg, "outerBoundaryIs" if i == 0 else "innerBoundaryIs")
            ring = _el(batas, "LinearRing")
            _el(ring, "coordinates", _teks_koordinat(cincin))


def _isi_extended(placemark, n: dict):
    ext = _el(placemark, "ExtendedData")
    props = _properti_node(n)
    for kunci in ("kode", "tipe", "lokasi", "status", "luas_m2"):
        nilai = props.get(kunci)
        if nilai in (None, ""):
            continue
        d = ET.SubElement(ext, f"{{{KML_NS}}}Data", name=kunci)
        _el(d, "value", nilai)


def ke_kml(nodes: list, label_level: dict = None) -> bytes:
    """KML ber-Folder BERSARANG mengikuti hierarki — di Google Earth pohon
    Kawasan → … → Ruangan tampil sebagai pohon folder, bukan daftar datar.

    Node bergeometri jadi Placemark; node ber-anak jadi Folder (Placemark-nya
    sendiri ikut di dalam folder itu). Akar = node yang induknya tak ikut
    diekspor (ekspor subtree memotong rantai moyang). Guard `dikunjungi`
    membuat siklus data terburuk sekalipun tak membuat rekursi abadi.
    """
    label_level = label_level or {}
    ada = {n["id"]: n for n in nodes if n.get("id")}
    anak = {}
    for n in nodes:
        pid = n.get("parent_id")
        if pid in ada and pid != n.get("id"):
            anak.setdefault(pid, []).append(n)
    for daftar in anak.values():
        daftar.sort(key=lambda x: (x.get("ordinal_level") or 0,
                                   x.get("kode") or "", x.get("nama") or ""))
    akar = sorted((n for n in nodes if n.get("parent_id") not in ada
                   or n.get("parent_id") == n.get("id")),
                  key=lambda x: (x.get("ordinal_level") or 0,
                                 x.get("kode") or "", x.get("nama") or ""))

    ET.register_namespace("", KML_NS)
    kml = ET.Element(f"{{{KML_NS}}}kml")
    dok = _el(kml, "Document")
    _el(dok, "name", "Denah AMAN IKN")

    dikunjungi = set()

    def tulis(n, wadah):
        if n["id"] in dikunjungi:
            return
        dikunjungi.add(n["id"])
        label = label_level.get(n.get("tipe")) or n.get("tipe") or ""
        judul = n.get("nama") or n.get("id")
        punya_anak = bool(anak.get(n["id"]))
        if punya_anak:
            folder = _el(wadah, "Folder")
            _el(folder, "name", judul)
            tempat_pm = folder
        else:
            tempat_pm = wadah
        if n.get("geometry"):
            pm = _el(tempat_pm, "Placemark")
            _el(pm, "name", judul)
            if label:
                _el(pm, "description", label)
            _isi_extended(pm, n)
            _tambah_geometri_kml(pm, n["geometry"])
        for a in anak.get(n["id"], []):
            tulis(a, folder if punya_anak else wadah)

    for n in akar:
        tulis(n, dok)
    return (b'<?xml version="1.0" encoding="UTF-8"?>\n'
            + ET.tostring(kml, encoding="unicode").encode("utf-8"))


def ke_kmz(kml_bytes: bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("doc.kml", kml_bytes)
    return buf.getvalue()


# ── Shapefile ───────────────────────────────────────────────────────────────

# (nama_field ≤10 char DBF, tipe, ukuran, desimal, kunci properti)
_FIELD_SHP = [("ID", "C", 40, 0, "id"), ("NAMA", "C", 120, 0, "nama"),
              ("KODE", "C", 40, 0, "kode"), ("TIPE", "C", 20, 0, "tipe"),
              ("LOKASI", "C", 254, 0, "lokasi"),
              ("STATUS", "C", 10, 0, "status"),
              ("LANTAI", "C", 20, 0, "lantai"),
              ("LUAS_M2", "N", 18, 2, "luas_m2")]


def _tulis_shp(z: "zipfile.ZipFile", nama_dasar: str, nodes: list,
               tipe_titik: bool) -> None:
    """Satu set .shp/.shx/.dbf/.prj/.cpg ke dalam zip. Shapefile hanya boleh
    SATU tipe shape per file — poligon dan titik dipisah oleh pemanggil."""
    import shapefile as pyshp
    shp, shx, dbf = io.BytesIO(), io.BytesIO(), io.BytesIO()
    w = pyshp.Writer(shp=shp, shx=shx, dbf=dbf, encoding="utf-8",
                     shapeType=pyshp.POINT if tipe_titik else pyshp.POLYGON)
    for nama_f, tipe_f, ukuran, desimal, _ in _FIELD_SHP:
        w.field(nama_f, tipe_f, size=ukuran, decimal=desimal)
    for n in nodes:
        geom = n["geometry"]
        if tipe_titik:
            w.point(float(geom["coordinates"][0]), float(geom["coordinates"][1]))
        else:
            # Spek ESRI: luar CW, lubang CCW — pyshp TIDAK membetulkannya.
            parts = []
            for cincin_list in _poligon_list(geom):
                for i, cincin in enumerate(cincin_list):
                    parts.append(_cincin_arah(cincin, searah_jarum_jam=(i == 0)))
            w.poly(parts)
        props = _properti_node(n)
        rekord = []
        for _, tipe_f, ukuran, _, kunci in _FIELD_SHP:
            nilai = props.get(kunci)
            if tipe_f == "N":
                # Data lama bisa membawa luas non-angka; satu node kotor tak
                # boleh menggagalkan seluruh ekspor (temuan tinjauan).
                try:
                    rekord.append(round(float(nilai or 0), 2))
                except (TypeError, ValueError):
                    rekord.append(0)
            else:
                rekord.append(_bersih_teks(nilai)[:ukuran])
        w.record(*rekord)
    w.close()
    z.writestr(f"{nama_dasar}.shp", shp.getvalue())
    z.writestr(f"{nama_dasar}.shx", shx.getvalue())
    z.writestr(f"{nama_dasar}.dbf", dbf.getvalue())
    z.writestr(f"{nama_dasar}.prj", PRJ_WGS84)
    z.writestr(f"{nama_dasar}.cpg", "UTF-8")


def ke_shp_zip(nodes: list) -> bytes:
    """Zip shapefile WGS84: `denah.*` (poligon) + `denah_titik.*` (bila ada
    node bergeometri Point). ValueError bila tak ada geometri sama sekali —
    zip kosong yang "berhasil diunduh" hanya menunda kebingungan pengguna."""
    poligon = [n for n in nodes
               if (n.get("geometry") or {}).get("type") in ("Polygon", "MultiPolygon")]
    titik = [n for n in nodes if (n.get("geometry") or {}).get("type") == "Point"]
    if not poligon and not titik:
        raise ValueError("Tidak ada node bergeometri untuk diekspor")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        if poligon:
            _tulis_shp(z, "denah", poligon, tipe_titik=False)
        if titik:
            _tulis_shp(z, "denah_titik", titik, tipe_titik=True)
        z.writestr("BACA_SAYA.txt", _README_SHP)
    return buf.getvalue()


_README_SHP = """Denah AMAN IKN — ekspor Shapefile (WGS84 / EPSG:4326)

Isi:
- denah.shp/.shx/.dbf/.prj/.cpg        : poligon denah
- denah_titik.* (bila ada)             : node bertipe titik

Kolom atribut: ID, NAMA, KODE, TIPE, LOKASI (jalur moyang), STATUS, LANTAI,
LUAS_M2. Encoding DBF: UTF-8 (lihat .cpg).

Alur bolak-balik dengan QGIS:
1. Buka .zip ini langsung di QGIS (drag & drop).
2. Sunting / tambah poligon; pastikan kolom NAMA terisi.
3. Ekspor ulang sebagai Shapefile (zip .shp+.dbf+.prj) atau GeoJSON.
4. Di aplikasi: Denah > Hierarki Spasial > Impor — hasil masuk sebagai draft.
"""


# ── Template gambar ─────────────────────────────────────────────────────────

def template_shp_zip() -> bytes:
    """Shapefile kosong ber-skema (1 fitur contoh) untuk digambar di QGIS.
    Kolomnya sama persis dengan hasil ekspor sehingga hasil gambar pengguna
    otomatis terpetakan oleh dropdown impor."""
    contoh = {"id": "contoh-1", "nama": "Contoh Gedung (hapus saya)",
              "kode": "CONTOH", "tipe": "GEDUNG", "status": "draft",
              "geometry": {"type": "Polygon", "coordinates": [_CONTOH_KOTAK]}}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        _tulis_shp(z, "template_denah", [contoh], tipe_titik=False)
        z.writestr("BACA_SAYA.txt", _README_TEMPLATE)
    return buf.getvalue()


_README_TEMPLATE = """Template denah AMAN IKN untuk QGIS (WGS84 / EPSG:4326)

1. Buka template_denah.shp di QGIS.
2. Aktifkan mode sunting, gambar poligon denah Anda (satu fitur = satu
   gedung/ruangan/blok). Hapus fitur "Contoh Gedung".
3. Isi kolom NAMA (wajib) dan KODE (opsional) tiap fitur.
4. Simpan, lalu zip kembali .shp+.shx+.dbf+.prj+.cpg.
5. Di aplikasi: Denah > Hierarki Spasial > Impor. Pilih tingkat & induknya —
   hasil masuk sebagai DRAFT untuk diperiksa dulu.
"""


def template_kml() -> bytes:
    """KML contoh untuk Google Earth: satu Placemark poligon bernama, dengan
    petunjuk alur di description dokumen."""
    ET.register_namespace("", KML_NS)
    kml = ET.Element(f"{{{KML_NS}}}kml")
    dok = _el(kml, "Document")
    _el(dok, "name", "Template denah AMAN IKN")
    _el(dok, "description",
        "Gambar poligon denah di Google Earth (Tambah > Poligon), beri NAMA "
        "pada tiap poligon, lalu simpan sebagai KML/KMZ dan impor lewat "
        "Denah > Hierarki Spasial > Impor. Hapus poligon contoh ini. "
        "Hasil impor masuk sebagai draft.")
    pm = _el(dok, "Placemark")
    _el(pm, "name", "Contoh Gedung (hapus saya)")
    ext = _el(pm, "ExtendedData")
    d = ET.SubElement(ext, f"{{{KML_NS}}}Data", name="kode")
    _el(d, "value", "CONTOH")
    pg = _el(pm, "Polygon")
    ob = _el(pg, "outerBoundaryIs")
    ring = _el(ob, "LinearRing")
    _el(ring, "coordinates", _teks_koordinat(_CONTOH_KOTAK))
    return (b'<?xml version="1.0" encoding="UTF-8"?>\n'
            + ET.tostring(kml, encoding="unicode").encode("utf-8"))
