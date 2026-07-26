"""Impor file geospasial (SHP-zip / KML / KMZ / GeoJSON) → fitur poligon WGS84.

Modul MURNI (tanpa Mongo/FastAPI) agar teruji unit; jalur request/job-nya ada di
routes/spasial.py. Semua keputusan di sini mengikuti riset Fase 0
(docs/ARSITEKTUR-SPASIAL-IOT.md §4.4 & §Impor) — tiga jebakan yang GAGAL SENYAP
dan mitigasinya:

1. `buffer(0)` DILARANG; perbaikan otomatis memakai `make_valid` DAN selalu
   membandingkan luas sebelum/sesudah — selisih > 1% berarti bentuk berubah
   berarti, jadi JANGAN diterapkan diam-diam (fitur dilewati + alasan).
2. Urutan koordinat: keluaran modul ini SELALU GeoJSON [bujur, lintang].
   KML/GeoJSON memang lon-first; SHP ber-CRS UTM dikonversi lewat paket `utm`
   yang mengembalikan (lat, lon) — dibalik DI SATU TEMPAT, di sini.
3. Encoding DBF: baca `.cpg` bila ada; tanpa itu coba UTF-8 lalu jatuh ke
   CP1252. Heuristik mojibake menandai nama yang rusak agar operator melihat
   pratinjau SEBELUM menyimpan, bukan sesudahnya.

XML KML diparse dengan stdlib `xml.etree` + penolakan dini `<!DOCTYPE`/`<!ENTITY`
(billion-laughs/XXE). KML/KMZ/GeoJSON selalu WGS84 menurut speknya; SHP membaca
CRS dari `.prj` — hanya WGS84 geografis dan UTM yang didukung, selain itu ditolak
dengan pesan yang menyebut proyeksinya (menebak CRS = denah di lokasi yang salah
tanpa satu pun galat).
"""
import io
import json
import math
import re
import zipfile
from typing import Optional

import spasial_utils as su
import topologi_utils as tu

# Plafon impor. File kecamatan penuh pun ribuan fitur; di atas ini pengalaman
# menggambar ulang lebih buruk daripada memecah filenya.
MAKS_FITUR_IMPOR = 2000
# Rasio perubahan luas maksimum yang boleh diterapkan otomatis oleh make_valid
# (jebakan #1 riset: buffer(0) memangkas separuh poligon TANPA galat — pagar
# ini memastikan make_valid pun tak pernah mengubah bentuk secara diam-diam).
MAKS_SELISIH_LUAS = 0.01

_POLA_MOJIBAKE = ("�", "Ã©", "Ã¡", "Ã­", "Ã³", "Ãº", "Ã±", "Â°", "â€")


def deteksi_mojibake(teks: str) -> bool:
    """True bila string tampak korban encoding ganda/salah (jebakan #3)."""
    t = str(teks or "")
    return any(p in t for p in _POLA_MOJIBAKE)


def deteksi_format(nama_file: str, data: bytes) -> Optional[str]:
    """"shp_zip" | "kml" | "kmz" | "geojson" | None (tak dikenal).

    Isi file yang menentukan, bukan hanya ekstensi: file .zip bisa berisi
    shapefile ATAU doc.kml (KMZ yang diganti nama).
    """
    nama = str(nama_file or "").lower()
    kepala = bytes(data[:4] or b"")
    if kepala[:2] == b"PK":                    # arsip zip
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                daftar = [n.lower() for n in z.namelist()]
        except zipfile.BadZipFile:
            return None
        if any(n.endswith(".shp") for n in daftar):
            return "shp_zip"
        if any(n.endswith(".kml") for n in daftar):
            return "kmz"
        return None
    if nama.endswith(".kml") or b"<kml" in data[:2048]:
        return "kml"
    if nama.endswith((".geojson", ".json")):
        return "geojson"
    potong = data.lstrip()[:1]
    if potong == b"{":
        return "geojson"
    return None


# ── KML / KMZ ───────────────────────────────────────────────────────────────

def _teks_koordinat_ke_cincin(teks: str):
    """"lon,lat[,alt] lon,lat…" (KML) → cincin [[lon,lat], …] atau None."""
    cincin = []
    for token in str(teks or "").split():
        bagian = token.split(",")
        if len(bagian) < 2:
            continue
        try:
            lon, lat = float(bagian[0]), float(bagian[1])
        except ValueError:
            continue
        cincin.append([lon, lat])
    return cincin or None


def _lokal(tag: str) -> str:
    """Nama tag tanpa namespace — KML beredar dengan/tanpa ns, kadang gx:."""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _poligon_dari_elemen(el):
    """Elemen <Polygon> KML → koordinat GeoJSON [cincin_luar, lubang…]."""
    luar, lubang = None, []
    for anak in el.iter():
        nama = _lokal(anak.tag)
        if nama not in ("outerBoundaryIs", "innerBoundaryIs"):
            continue
        for koor in anak.iter():
            if _lokal(koor.tag) != "coordinates":
                continue
            cincin = _teks_koordinat_ke_cincin(koor.text)
            if not cincin:
                continue
            if cincin[0] != cincin[-1]:
                cincin.append(list(cincin[0]))     # KML tak selalu menutup cincin
            if nama == "outerBoundaryIs" and luar is None:
                luar = cincin
            elif nama == "innerBoundaryIs":
                lubang.append(cincin)
    return [luar] + lubang if luar else None


def parse_kml(data: bytes) -> list:
    """KML → [{"nama", "geometry", "atribut"}]. Hanya Placemark ber-poligon.

    `<!DOCTYPE`/`<!ENTITY` DITOLAK sebelum parser disentuh — KML sah dari
    Google Earth/QGIS tak pernah memakainya, dan hanya lewat situlah serangan
    entity-expansion masuk.
    """
    kepala = data[:4096]
    if b"<!DOCTYPE" in kepala or b"<!ENTITY" in kepala:
        raise ValueError("KML mengandung deklarasi DOCTYPE/ENTITY — ditolak "
                         "demi keamanan; ekspor ulang dari aplikasi peta Anda")
    import xml.etree.ElementTree as ET
    try:
        akar = ET.fromstring(data)
    except ET.ParseError as e:
        raise ValueError(f"KML tidak dapat dibaca: {e}")

    fitur = []
    for pm in akar.iter():
        if _lokal(pm.tag) != "Placemark":
            continue
        nama = ""
        atribut = {}
        poligon = []
        for anak in pm.iter():
            tag = _lokal(anak.tag)
            if tag == "name" and not nama:
                nama = str(anak.text or "").strip()
            elif tag == "SimpleData" and anak.get("name"):
                atribut[anak.get("name")] = str(anak.text or "").strip()
            elif tag == "Data" and anak.get("name"):
                for v in anak.iter():
                    if _lokal(v.tag) == "value":
                        atribut[anak.get("name")] = str(v.text or "").strip()
            elif tag == "Polygon":
                koor = _poligon_dari_elemen(anak)
                if koor:
                    poligon.append(koor)
        if not poligon:
            continue                        # Placemark titik/garis — bukan denah
        geometry = ({"type": "Polygon", "coordinates": poligon[0]}
                    if len(poligon) == 1 else
                    {"type": "MultiPolygon", "coordinates": poligon})
        fitur.append({"nama": nama, "geometry": geometry, "atribut": atribut})
    return fitur


def parse_kmz(data: bytes) -> list:
    """KMZ = zip berisi .kml (lazim doc.kml). Ambil KML pertama."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            nama_kml = next((n for n in z.namelist()
                             if n.lower().endswith(".kml")), None)
            if not nama_kml:
                raise ValueError("KMZ tidak berisi file .kml")
            return parse_kml(z.read(nama_kml))
    except zipfile.BadZipFile:
        raise ValueError("File KMZ rusak (bukan arsip zip yang sah)")


# ── GeoJSON ─────────────────────────────────────────────────────────────────

def parse_geojson(data: bytes) -> list:
    try:
        dok = json.loads(data.decode("utf-8-sig"))
    except (ValueError, UnicodeDecodeError) as e:
        raise ValueError(f"GeoJSON tidak dapat dibaca: {e}")
    if isinstance(dok, dict) and dok.get("type") == "FeatureCollection":
        mentah = dok.get("features") or []
    elif isinstance(dok, dict) and dok.get("type") == "Feature":
        mentah = [dok]
    else:
        raise ValueError("GeoJSON harus FeatureCollection atau Feature")
    fitur = []
    for f in mentah:
        g = (f or {}).get("geometry") or {}
        if g.get("type") not in ("Polygon", "MultiPolygon"):
            continue
        props = {k: ("" if v is None else str(v))
                 for k, v in ((f or {}).get("properties") or {}).items()}
        nama = props.get("name") or props.get("nama") or props.get("Name") or ""
        fitur.append({"nama": nama, "geometry": g, "atribut": props})
    return fitur


# ── SHP (zip berisi .shp + .dbf, opsional .prj/.cpg) ────────────────────────

_RX_UTM = re.compile(r"UTM[\s_]*zone[\s_]*(\d{1,2})\s*,?\s*([NS])?", re.IGNORECASE)


def baca_crs_prj(teks_prj: str):
    """Isi .prj (WKT) → {"jenis": "wgs84"} | {"jenis":"utm","zona":50,"utara":False}
    | {"jenis":"tak_didukung","nama": "..."} | None (kosong).

    Hanya dua CRS yang didukung SENGAJA: WGS84 geografis dan UTM (semua zona
    Indonesia: 46–54). Mendukung "sebagian" proyeksi lain berarti menebak —
    dan tebakan CRS menaruh denah di lokasi salah tanpa satu pun galat.
    """
    t = str(teks_prj or "").strip()
    if not t:
        return None
    if "PROJCS" not in t.upper():
        # geografis murni; WGS84/WGS 1984 diterima
        if re.search(r"WGS[\s_]*(19)?84", t, re.IGNORECASE):
            return {"jenis": "wgs84"}
        return {"jenis": "tak_didukung", "nama": t[:80]}
    m = _RX_UTM.search(t)
    if m:
        zona = int(m.group(1))
        arah = (m.group(2) or "").upper()
        if not arah:
            # gaya ESRI: hemisfer tersirat di false northing (10 jt = selatan)
            arah = "S" if re.search(r'"false_northing"?\s*,?\s*10000000',
                                    t, re.IGNORECASE) else "N"
        if 1 <= zona <= 60:
            return {"jenis": "utm", "zona": zona, "utara": arah != "S"}
    m_nama = re.search(r'PROJCS\[\s*"([^"]+)"', t)
    return {"jenis": "tak_didukung",
            "nama": (m_nama.group(1) if m_nama else t[:80])}


def _konversi_titik_utm(x, y, zona, utara):
    import utm
    lat, lon = utm.to_latlon(x, y, zona, northern=utara, strict=False)
    return [float(lon), float(lat)]           # KEMBALI ke lon-first (jebakan #2)


def _konversi_geometri_utm(geom, zona, utara):
    def cincin(c):
        return [_konversi_titik_utm(t[0], t[1], zona, utara) for t in c]
    if geom["type"] == "Polygon":
        return {"type": "Polygon",
                "coordinates": [cincin(c) for c in geom["coordinates"]]}
    return {"type": "MultiPolygon",
            "coordinates": [[cincin(c) for c in pol]
                            for pol in geom["coordinates"]]}


def parse_shp_zip(data: bytes) -> dict:
    """Zip shapefile → {"fitur": [...], "fields": [...], "crs": {...},
    "peringatan": [...]}. Fitur non-poligon dilewati.

    `__geo_interface__` pyshp yang mengelompokkan cincin menjadi Polygon/
    MultiPolygon (termasuk lubang) — menulis ulang logika orientasi cincin
    sendiri adalah sumber bug klasik.
    """
    import shapefile as pyshp                  # pyshp — sudah di requirements
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise ValueError("File SHP harus berupa zip berisi .shp + .dbf")
    nama_shp = next((n for n in z.namelist() if n.lower().endswith(".shp")), None)
    if not nama_shp:
        raise ValueError("Zip tidak berisi file .shp")
    dasar = nama_shp[:-4]

    def _baca(eks):
        for n in z.namelist():
            if n.lower() == (dasar + eks).lower():
                return z.read(n)
        return None

    b_shp, b_dbf, b_shx = z.read(nama_shp), _baca(".dbf"), _baca(".shx")
    if b_dbf is None:
        raise ValueError("Zip tidak berisi file .dbf (tabel atribut)")

    peringatan = []
    # Encoding: .cpg adalah satu-satunya sumber tepercaya (jebakan #3).
    b_cpg = _baca(".cpg")
    encoding = (b_cpg.decode("ascii", "ignore").strip() if b_cpg else "") or "utf-8"
    try:
        r = pyshp.Reader(shp=io.BytesIO(b_shp), dbf=io.BytesIO(b_dbf),
                         shx=io.BytesIO(b_shx) if b_shx else None,
                         encoding=encoding)
        _ = [f[0] for f in r.fields[1:]]
    except (UnicodeDecodeError, LookupError):
        peringatan.append(f"Encoding '{encoding}' gagal — jatuh ke cp1252; "
                          "periksa nama-nama pada pratinjau")
        r = pyshp.Reader(shp=io.BytesIO(b_shp), dbf=io.BytesIO(b_dbf),
                         shx=io.BytesIO(b_shx) if b_shx else None,
                         encoding="cp1252")
    if not b_cpg:
        peringatan.append("Tanpa file .cpg — encoding atribut ditebak (UTF-8); "
                          "periksa nama-nama pada pratinjau")

    crs = baca_crs_prj((_baca(".prj") or b"").decode("utf-8", "ignore"))
    fields = [f[0] for f in r.fields[1:]]      # buang DeletionFlag

    fitur = []
    for sr in r.iterShapeRecords():
        try:
            geom = sr.shape.__geo_interface__
        except Exception:
            continue
        if not geom or geom.get("type") not in ("Polygon", "MultiPolygon"):
            continue
        atribut = {k: ("" if v is None else str(v))
                   for k, v in zip(fields, list(sr.record))}
        # __geo_interface__ memakai tuple; normalkan ke list agar JSON-able.
        geom = json.loads(json.dumps(geom))
        fitur.append({"nama": "", "geometry": geom, "atribut": atribut})

    # CRS: tanpa .prj → heuristik rentang; PROJCS asing → tolak tegas.
    if crs is None:
        semua_wajar = all(
            abs(t[0]) <= 180 and abs(t[1]) <= 90
            for f in fitur for t in su._semua_titik(f["geometry"]))
        if fitur and semua_wajar:
            crs = {"jenis": "wgs84"}
            peringatan.append("Tanpa file .prj — koordinat DIASUMSIKAN WGS84 "
                              "karena rentangnya masuk akal; verifikasi posisi "
                              "di pratinjau peta")
        else:
            raise ValueError("Tanpa .prj dan koordinat di luar rentang derajat "
                             "— sistem koordinat tak dapat ditentukan")
    if crs["jenis"] == "tak_didukung":
        raise ValueError(
            f"Proyeksi '{crs.get('nama')}' belum didukung — ekspor ulang dari "
            "GIS Anda sebagai WGS84 (EPSG:4326) atau UTM")
    if crs["jenis"] == "utm":
        fitur = [{**f, "geometry": _konversi_geometri_utm(
            f["geometry"], crs["zona"], crs["utara"])} for f in fitur]

    return {"fitur": fitur, "fields": fields, "crs": crs,
            "peringatan": peringatan}


# ── Pintu masuk seragam ─────────────────────────────────────────────────────

def parse_file(nama_file: str, data: bytes) -> dict:
    """Semua format → bentuk seragam {"fitur", "fields", "crs", "peringatan"}."""
    fmt = deteksi_format(nama_file, data)
    if fmt == "shp_zip":
        hasil = parse_shp_zip(data)
        hasil["format"] = "shp"
        return hasil
    if fmt in ("kml", "kmz"):
        fitur = parse_kml(data) if fmt == "kml" else parse_kmz(data)
        kunci = sorted({k for f in fitur for k in f["atribut"]})
        return {"format": fmt, "fitur": fitur, "fields": kunci,
                "crs": {"jenis": "wgs84"}, "peringatan": []}
    if fmt == "geojson":
        fitur = parse_geojson(data)
        kunci = sorted({k for f in fitur for k in f["atribut"]})
        return {"format": "geojson", "fitur": fitur, "fields": kunci,
                "crs": {"jenis": "wgs84"}, "peringatan": []}
    raise ValueError("Format tidak dikenali — dukung: zip Shapefile "
                     "(.shp+.dbf), .kml, .kmz, .geojson")


def bersihkan_fitur(geometry, perbaiki: bool = False):
    """(geometry_bersih, None) atau (None, alasan_dilewati).

    Urutan: struktur → topologi → (opsional) make_valid ber-PAGAR-LUAS.
    make_valid TIDAK pernah diterapkan bila mengubah luas > 1% (MAKS_SELISIH_LUAS)
    — perubahan sebesar itu berarti bentuknya memang beda, dan menyimpannya
    diam-diam adalah persis kegagalan-senyap yang riset Fase 0 larang.
    """
    galat = su.validasi_geometri(geometry)
    if galat:
        return None, f"struktur: {galat}"
    galat_topo = tu.validasi_topologi(geometry)
    if not galat_topo:
        return geometry, None
    if not perbaiki:
        return None, f"topologi: {galat_topo}"
    usul = tu.perbaiki_topologi(geometry)
    if usul is None:
        return None, f"topologi: {galat_topo} (perbaikan otomatis gagal)"
    if su.validasi_geometri(usul) or tu.validasi_topologi(usul):
        return None, f"topologi: {galat_topo} (hasil perbaikan tetap tak sah)"
    luas_awal = su.luas_kasar_m2(geometry)
    luas_baru = su.luas_kasar_m2(usul)
    # Pagar luas HANYA berlaku bila luas asal BERMAKNA. Shoelace pada poligon
    # menyilang-diri saling meniadakan — bow-tie simetris berluas "0" padahal
    # make_valid (benar) memberi luas kedua cupingnya. Terukur di repo ini:
    # 0,0 m² vs 61,8 juta m². Menerapkan pagar pada angka yang tak bermakna
    # akan menolak justru kasus perbaikan utama. Ambang "bermakna": luas asal
    # setidaknya 1% dari hasil — di bawah itu angka asal adalah artefak
    # peniadaan, bukan ukuran bentuk.
    if luas_awal > luas_baru * 0.01 and not math.isclose(
            luas_awal, luas_baru, rel_tol=MAKS_SELISIH_LUAS):
        selisih = abs(luas_baru - luas_awal) / luas_awal * 100.0
        return None, (f"topologi: {galat_topo} (perbaikan mengubah luas "
                      f"{selisih:.1f}% — melebihi 1%, tidak diterapkan otomatis)")
    return usul, None
