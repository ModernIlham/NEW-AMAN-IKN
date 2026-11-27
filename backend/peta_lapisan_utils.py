"""Validasi murni LAPISAN EKSISTING peta (tanpa DB).

Dua jenis lapisan menggambarkan kondisi lapangan terbaru di atas peta dasar OSM:

- ``citra``  — foto udara (GeoTIFF drone/ortofoto). Peramban admin membaca
  berkasnya, memproyeksikan ulang ke WGS84/Web Mercator, dan memotongnya jadi
  ubin XYZ; server hanya MENYIMPAN ubin dan menyajikannya. Server 2 vCPU tanpa
  GDAL (docs/ARSITEKTUR-SPASIAL-IOT.md §0 #9) — memotong citra besar di server
  akan memakan CPU yang sama dengan yang melayani seluruh pengguna.
- ``gambar`` — titik, garis, dan area yang digambar langsung di peta, lengkap
  dengan gaya (warna, tebal, opasitas) dan label.

Batas-batas di modul ini menjaga dua hal: peta tetap ringan di HP lapangan
(jumlah fitur/verteks dibatasi, ubin hanya di dalam batas citra) dan tak ada
masukan yang bisa menyisip markup ke peramban pengguna lain (warna hanya
#rrggbb, teks label dipangkas dan dirender sebagai teks, bukan HTML).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import re
import uuid
from datetime import date
from typing import Any

JENIS = ("citra", "gambar")
ZOOM_MIN = 0
ZOOM_MAKS = 22
PANJANG_NAMA_MAKS = 120
PANJANG_TEKS_MAKS = 300

FORMAT_UBIN = {"webp": "image/webp", "png": "image/png", "jpg": "image/jpeg"}
UBIN_MAKS_PER_LAPISAN = 60_000
UKURAN_UBIN_MAKS = 600 * 1024           # satu ubin 256×256 wajarnya < 100 KB

FITUR_MAKS = 2_000
VERTEKS_MAKS_PER_FITUR = 5_000
VERTEKS_MAKS_PER_LAPISAN = 100_000
JSON_GAMBAR_MAKS = 2 * 1024 * 1024

POSISI_LABEL = {
    "titik": ("atas", "kanan", "bawah", "kiri"),
    "garis": ("ikut", "tengah"),
    "area": ("tengah",),
}
_WARNA = re.compile(r"^#[0-9a-fA-F]{6}$")
_ID_FITUR = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
_ID_LAPISAN = re.compile(r"^[0-9a-f-]{36}$")


# ── Pembantu dasar ──────────────────────────────────────────────────────────

def _teks(v: Any, maks: int) -> str:
    return str(v or "").strip()[:maks]


def _angka(v: Any) -> float | None:
    if isinstance(v, bool) or v is None or v == "":
        return None
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) else None


def _bulat(v: Any) -> int | None:
    n = _angka(v)
    return int(n) if n is not None and n == int(n) else None


def _rentang(v: Any, bawah: float, atas: float, bawaan: float) -> float:
    n = _angka(v)
    if n is None:
        return bawaan
    return min(atas, max(bawah, n))


def _warna(v: Any, bawaan: str) -> str:
    s = str(v or "").strip()
    return s.lower() if _WARNA.match(s) else bawaan


def id_lapisan_sah(v: str) -> bool:
    return bool(_ID_LAPISAN.match(str(v or "")))


def _tanggal(v: Any) -> tuple[str, str | None]:
    s = _teks(v, 10)
    if not s:
        return "", "Tanggal rekam wajib diisi"
    try:
        date.fromisoformat(s)
    except (ValueError, OverflowError):
        return s, "Tanggal rekam harus berformat TTTT-BB-HH"
    return s, None


# ── Geometri ubin XYZ (skema Google/OSM, Web Mercator) ─────────────────────

def ubin_x(lon: float, z: int) -> int:
    n = 2 ** z
    return min(n - 1, max(0, int(math.floor((lon + 180.0) / 360.0 * n))))


def ubin_y(lat: float, z: int) -> int:
    n = 2 ** z
    lat = max(-85.0511, min(85.0511, lat))
    r = math.radians(lat)
    y = (1 - math.log(math.tan(r) + 1 / math.cos(r)) / math.pi) / 2 * n
    return min(n - 1, max(0, int(math.floor(y))))


def rentang_ubin(batas: dict, z: int) -> tuple[int, int, int, int]:
    """(x_min, x_maks, y_min, y_maks) ubin yang menyentuh batas pada zoom z."""
    return (ubin_x(batas["barat"], z), ubin_x(batas["timur"], z),
            ubin_y(batas["utara"], z), ubin_y(batas["selatan"], z))


def jumlah_ubin(batas: dict, zmin: int, zmaks: int) -> int:
    total = 0
    for z in range(zmin, zmaks + 1):
        x0, x1, y0, y1 = rentang_ubin(batas, z)
        total += (x1 - x0 + 1) * (y1 - y0 + 1)
    return total


def ubin_dalam_batas(batas: dict, z: int, x: int, y: int) -> bool:
    x0, x1, y0, y1 = rentang_ubin(batas, z)
    return x0 <= x <= x1 and y0 <= y <= y1


def nama_berkas_ubin(nama: str) -> tuple[int, int, int, str] | None:
    """'15-27006-16471.webp' → (15, 27006, 16471, 'webp'); None bila tak sah."""
    m = re.fullmatch(r"(\d{1,2})-(\d{1,8})-(\d{1,8})\.(webp|png|jpg)", str(nama or ""))
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4)


def isi_cocok_format(data: bytes, fmt: str) -> bool:
    """Cek tanda tangan berkas — jangan percaya nama/jenis yang dikirim klien."""
    if fmt == "png":
        return data[:8] == b"\x89PNG\r\n\x1a\n"
    if fmt == "jpg":
        return data[:3] == b"\xff\xd8\xff"
    if fmt == "webp":
        return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return False


# ── Token ubin (tanpa kueri DB per ubin) ────────────────────────────────────
#
# Ubin dimuat lewat <img> yang tak bisa membawa header Authorization. Token ini
# dibagikan dalam daftar lapisan (butuh login) dan diverifikasi dengan HMAC saja
# — tanpa kueri DB — karena satu layar peta meminta belasan ubin sekaligus.
# Berganti tiap hari UTC (URL ubin stabil sepanjang hari → cache peramban
# tetap berlaku) dan diterima hingga sehari sesudahnya.

def token_ubin(rahasia: str, hari: int) -> str:
    sig = hmac.new(rahasia.encode(), f"ubin:{hari}".encode(), hashlib.sha256).hexdigest()[:32]
    return f"{hari}.{sig}"


def token_ubin_sah(rahasia: str, token: str, hari_ini: int) -> bool:
    try:
        hari_s, _ = str(token or "").split(".", 1)
        hari = int(hari_s)
    except ValueError:
        return False
    if hari not in (hari_ini, hari_ini - 1):
        return False
    return hmac.compare_digest(token_ubin(rahasia, hari), str(token))


# ── Lapisan CITRA ───────────────────────────────────────────────────────────

def normalisasi_batas(mentah: Any) -> tuple[dict, list[str]]:
    b = mentah if isinstance(mentah, dict) else {}
    batas = {k: _angka(b.get(k)) for k in ("barat", "selatan", "timur", "utara")}
    if any(v is None for v in batas.values()):
        return batas, ["Batas wilayah citra tidak terbaca"]
    galat = []
    if not (-180 <= batas["barat"] < batas["timur"] <= 180):
        galat.append("Batas bujur citra tidak wajar")
    if not (-85 <= batas["selatan"] < batas["utara"] <= 85):
        galat.append("Batas lintang citra tidak wajar")
    return batas, galat


def normalisasi_citra_baru(data: dict) -> tuple[dict, list[str]]:
    """Registri citra yang akan diunggah ubinnya."""
    galat: list[str] = []
    nama = _teks(data.get("nama"), PANJANG_NAMA_MAKS)
    if not nama:
        galat.append("Nama citra wajib diisi")
    tanggal, g = _tanggal(data.get("tanggal_rekam"))
    if g:
        galat.append(g)
    batas, g2 = normalisasi_batas(data.get("batas"))
    galat += g2
    zmin, zmaks = _bulat(data.get("zoom_min")), _bulat(data.get("zoom_maks"))
    if zmin is None or zmaks is None or not (ZOOM_MIN <= zmin <= zmaks <= ZOOM_MAKS):
        galat.append("Rentang zoom citra tidak wajar")
    fmt = str(data.get("format") or "").lower()
    if fmt not in FORMAT_UBIN:
        galat.append("Format ubin tidak dikenal")
    if not galat and jumlah_ubin(batas, zmin, zmaks) > UBIN_MAKS_PER_LAPISAN:
        galat.append(f"Citra terlalu besar: lebih dari {UBIN_MAKS_PER_LAPISAN:,} ubin".replace(",", "."))
    dok = {
        "jenis": "citra",
        "nama": nama,
        "sumber": _teks(data.get("sumber"), PANJANG_NAMA_MAKS),
        "tanggal_rekam": tanggal,
        "batas": batas,
        "zoom_min": zmin,
        "zoom_maks": zmaks,
        "format": fmt,
        "opasitas": round(_rentang(data.get("opasitas"), 0.1, 1, 1.0), 2),
        "crs_asal": _teks(data.get("crs_asal"), 40),
        "status": "memproses",
        "aktif": False,
    }
    return dok, galat


def normalisasi_citra_ubah(data: dict) -> tuple[dict, list[str]]:
    """Bidang citra yang boleh diubah sesudah diunggah (geometri tetap)."""
    galat: list[str] = []
    nama = _teks(data.get("nama"), PANJANG_NAMA_MAKS)
    if not nama:
        galat.append("Nama citra wajib diisi")
    tanggal, g = _tanggal(data.get("tanggal_rekam"))
    if g:
        galat.append(g)
    return {
        "nama": nama,
        "sumber": _teks(data.get("sumber"), PANJANG_NAMA_MAKS),
        "tanggal_rekam": tanggal,
        "opasitas": round(_rentang(data.get("opasitas"), 0.1, 1, 1.0), 2),
        "aktif": bool(data.get("aktif", True)),
    }, galat


# ── Lapisan GAMBAR ──────────────────────────────────────────────────────────

GAYA_BAWAAN = {
    "warna": "#2563eb", "tebal": 3.0, "opasitas": 1.0,
    "isi_warna": "#2563eb", "isi_opasitas": 0.25, "putus": False, "ukuran": 7.0,
}
LABEL_BAWAAN = {
    "teks": "", "warna": "#111827", "ukuran": 13.0, "tebal": True, "halo": "#ffffff",
}


def _koordinat(p: Any) -> list[float] | None:
    if not isinstance(p, (list, tuple)) or len(p) < 2:
        return None
    lon, lat = _angka(p[0]), _angka(p[1])
    if lon is None or lat is None or not (-180 <= lon <= 180 and -85 <= lat <= 85):
        return None
    return [round(lon, 7), round(lat, 7)]


def _geometri(geom: Any) -> tuple[str | None, dict | None, int, str | None]:
    """→ (tipe, geometri GeoJSON bersih, jumlah verteks, galat)."""
    if not isinstance(geom, dict):
        return None, None, 0, "geometri kosong"
    t = geom.get("type")
    c = geom.get("coordinates")
    if t == "Point":
        p = _koordinat(c)
        if not p:
            return None, None, 0, "koordinat titik tidak sah"
        return "titik", {"type": "Point", "coordinates": p}, 1, None
    if t == "LineString":
        pts = [_koordinat(p) for p in (c or [])] if isinstance(c, list) else []
        if len(pts) < 2 or any(p is None for p in pts):
            return None, None, 0, "garis butuh minimal 2 titik sah"
        if len(pts) > VERTEKS_MAKS_PER_FITUR:
            return None, None, 0, f"garis melebihi {VERTEKS_MAKS_PER_FITUR} titik"
        return "garis", {"type": "LineString", "coordinates": pts}, len(pts), None
    if t == "Polygon":
        if not isinstance(c, list) or not c:
            return None, None, 0, "area kosong"
        cincin, total = [], 0
        for ring in c[:20]:
            pts = [_koordinat(p) for p in (ring or [])] if isinstance(ring, list) else []
            if any(p is None for p in pts):
                return None, None, 0, "koordinat area tidak sah"
            if pts and pts[0] != pts[-1]:
                pts.append(list(pts[0]))
            if len(pts) < 4:
                return None, None, 0, "area butuh minimal 3 titik"
            total += len(pts)
            cincin.append(pts)
        if total > VERTEKS_MAKS_PER_FITUR:
            return None, None, 0, f"area melebihi {VERTEKS_MAKS_PER_FITUR} titik"
        return "area", {"type": "Polygon", "coordinates": cincin}, total, None
    return None, None, 0, f"jenis geometri {t!r} tidak didukung"


def normalisasi_fitur(f: Any, urut: int) -> tuple[dict | None, int, str | None]:
    if not isinstance(f, dict):
        return None, 0, f"fitur #{urut}: format tidak sah"
    tipe, geom, n, g = _geometri(f.get("geometri") or f.get("geometry"))
    if g:
        return None, 0, f"fitur #{urut}: {g}"
    fid = str(f.get("id") or "")
    if not _ID_FITUR.match(fid):
        fid = uuid.uuid4().hex[:12]
    gm = f.get("gaya") if isinstance(f.get("gaya"), dict) else {}
    warna = _warna(gm.get("warna"), GAYA_BAWAAN["warna"])
    gaya = {
        "warna": warna,
        "tebal": round(_rentang(gm.get("tebal"), 0.5, 20, GAYA_BAWAAN["tebal"]), 1),
        "opasitas": round(_rentang(gm.get("opasitas"), 0, 1, GAYA_BAWAAN["opasitas"]), 2),
        "isi_warna": _warna(gm.get("isi_warna"), warna),
        "isi_opasitas": round(_rentang(gm.get("isi_opasitas"), 0, 1, GAYA_BAWAAN["isi_opasitas"]), 2),
        "putus": bool(gm.get("putus", False)),
        "ukuran": round(_rentang(gm.get("ukuran"), 2, 30, GAYA_BAWAAN["ukuran"]), 1),
    }
    lm = f.get("label") if isinstance(f.get("label"), dict) else {}
    posisi_sah = POSISI_LABEL[tipe]
    posisi = lm.get("posisi") if lm.get("posisi") in posisi_sah else posisi_sah[0]
    halo = str(lm.get("halo") or "").strip()
    label = {
        "teks": _teks(lm.get("teks"), PANJANG_NAMA_MAKS),
        "warna": _warna(lm.get("warna"), LABEL_BAWAAN["warna"]),
        "ukuran": round(_rentang(lm.get("ukuran"), 8, 40, LABEL_BAWAAN["ukuran"]), 1),
        "tebal": bool(lm.get("tebal", LABEL_BAWAAN["tebal"])),
        "halo": halo.lower() if _WARNA.match(halo) else "",
        "posisi": posisi,
    }
    return {"id": fid, "tipe": tipe, "geometri": geom, "gaya": gaya, "label": label}, n, None


def normalisasi_gambar(data: dict) -> tuple[dict, list[str]]:
    galat: list[str] = []
    nama = _teks(data.get("nama"), PANJANG_NAMA_MAKS)
    if not nama:
        galat.append("Nama lapisan wajib diisi")
    mentah = data.get("fitur") or []
    if not isinstance(mentah, list):
        mentah = []
    if len(mentah) > FITUR_MAKS:
        galat.append(f"Maksimal {FITUR_MAKS} objek per lapisan")
        mentah = mentah[:FITUR_MAKS]
    fitur, total, ids = [], 0, set()
    for i, f in enumerate(mentah, 1):
        bersih, n, g = normalisasi_fitur(f, i)
        if g:
            galat.append(g)
            continue
        while bersih["id"] in ids:
            bersih["id"] = uuid.uuid4().hex[:12]
        ids.add(bersih["id"])
        total += n
        fitur.append(bersih)
    if total > VERTEKS_MAKS_PER_LAPISAN:
        galat.append(f"Lapisan melebihi {VERTEKS_MAKS_PER_LAPISAN:,} titik sudut".replace(",", "."))
    zl = _bulat(data.get("label_zoom_min"))
    dok = {
        "jenis": "gambar",
        "nama": nama,
        "fitur": fitur,
        "label_zoom_min": zl if zl is not None and ZOOM_MIN <= zl <= ZOOM_MAKS else 15,
        "aktif": bool(data.get("aktif", True)),
    }
    if len(json.dumps(fitur, separators=(",", ":"))) > JSON_GAMBAR_MAKS:
        galat.append("Lapisan gambar terlalu besar (maksimal 2 MB)")
    return dok, galat


def bentuk_publik(dok: dict) -> dict:
    """Bidang yang dibutuhkan peta — tanpa jejak penulis/satker."""
    kunci = ["id", "jenis", "nama", "aktif", "urutan", "version"]
    if dok.get("jenis") == "gambar":
        kunci += ["fitur", "label_zoom_min"]
    else:
        kunci += ["sumber", "tanggal_rekam", "batas", "zoom_min", "zoom_maks", "format",
                  "opasitas", "status", "jumlah_ubin", "ukuran_byte"]
    return {k: dok.get(k) for k in kunci}
