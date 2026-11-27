"""Validasi murni registri LAPISAN CITRA EKSISTING pada peta (tanpa DB).

Peta dasar OSM di kawasan yang sedang dibangun tertinggal dari kondisi lapangan.
Lapisan ini menumpangkan citra terbaru (drone/ortofoto) yang sudah dipotong jadi
ubin XYZ — DI LUAR server (mis. QGIS "Generate XYZ tiles"), lalu disajikan
sebagai berkas statis oleh nginx. Backend hanya menyimpan REGISTRI-nya: alamat
ubin, batas wilayah, rentang zoom, tanggal rekam, sumber.

Kenapa batas & zoom wajib: Leaflet hanya meminta ubin di dalam `bounds` dan
rentang zoom yang diberikan. Tanpa keduanya setiap geser peta di mana pun
memicu ratusan permintaan 404 — beban sia-sia di HP lapangan dan di server.

Kenapa alamat ubin dibatasi (jalur lokal "/…" atau https): alamat ini dimuat
oleh peramban SETIAP pengguna. Skema lain (javascript:, data:, http polos)
membuka celah konten campuran/penyisipan; alamat lintas-protokol "//host"
mengaburkan asal ubin.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

ZOOM_MIN = 0
ZOOM_MAKS = 22          # sama dengan maxZoom peta aset (AssetMapFullView)
PANJANG_NAMA_MAKS = 120
PANJANG_TEKS_MAKS = 500
PANJANG_URL_MAKS = 500

_PLACEHOLDER = re.compile(r"\{([a-z]+)\}")
_PLACEHOLDER_BOLEH = {"z", "x", "y", "s"}
_PLACEHOLDER_WAJIB = {"z", "x", "y"}


def _teks(v: Any, maks: int) -> str:
    return str(v or "").strip()[:maks]


def _angka(v: Any) -> float | None:
    if isinstance(v, bool) or v is None or v == "":
        return None
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    return n if n == n and n not in (float("inf"), float("-inf")) else None


def _bulat(v: Any) -> int | None:
    n = _angka(v)
    return int(n) if n is not None and n == int(n) else None


def validasi_url_template(url: str) -> list[str]:
    """Galat alamat ubin; [] bila sah."""
    if not url:
        return ["Alamat ubin wajib diisi"]
    if len(url) > PANJANG_URL_MAKS:
        return [f"Alamat ubin maksimal {PANJANG_URL_MAKS} karakter"]
    if any(c.isspace() for c in url) or any(c in url for c in "\"'<>\\"):
        return ["Alamat ubin tidak boleh berisi spasi, tanda kutip, < > atau \\"]
    lokal = url.startswith("/") and not url.startswith("//")
    if not (lokal or url.lower().startswith("https://")):
        return ["Alamat ubin harus berupa jalur di server ini (diawali \"/\") "
                "atau alamat https://"]
    nama = set(_PLACEHOLDER.findall(url))
    galat = []
    kurang = _PLACEHOLDER_WAJIB - nama
    if kurang:
        galat.append("Alamat ubin wajib memuat " + ", ".join(
            "{" + k + "}" for k in sorted(kurang)))
    asing = nama - _PLACEHOLDER_BOLEH
    if asing:
        galat.append("Penanda tidak dikenal di alamat ubin: " + ", ".join(
            "{" + k + "}" for k in sorted(asing)))
    return galat


def normalisasi_lapisan(data: dict) -> tuple[dict, list[str]]:
    """Bersihkan masukan → (dokumen, galat). Dokumen hanya sah bila galat kosong."""
    galat: list[str] = []
    nama = _teks(data.get("nama"), PANJANG_NAMA_MAKS)
    if not nama:
        galat.append("Nama lapisan wajib diisi")

    tanggal = _teks(data.get("tanggal_rekam"), 10)
    if not tanggal:
        galat.append("Tanggal rekam citra wajib diisi")
    else:
        try:
            date.fromisoformat(tanggal)
        except (ValueError, OverflowError):
            galat.append("Tanggal rekam harus berformat TTTT-BB-HH")

    url = _teks(data.get("url_template"), PANJANG_URL_MAKS + 1)
    galat += validasi_url_template(url)

    batas_mentah = data.get("batas") or {}
    if not isinstance(batas_mentah, dict):
        batas_mentah = {}
    batas = {k: _angka(batas_mentah.get(k)) for k in ("barat", "selatan", "timur", "utara")}
    if any(v is None for v in batas.values()):
        galat.append("Batas wilayah (barat, selatan, timur, utara) wajib berupa angka")
    else:
        if not (-180 <= batas["barat"] <= 180 and -180 <= batas["timur"] <= 180):
            galat.append("Bujur batas harus di antara -180 dan 180")
        if not (-85 <= batas["selatan"] <= 85 and -85 <= batas["utara"] <= 85):
            galat.append("Lintang batas harus di antara -85 dan 85")
        if batas["barat"] >= batas["timur"]:
            galat.append("Batas barat harus lebih kecil dari batas timur")
        if batas["selatan"] >= batas["utara"]:
            galat.append("Batas selatan harus lebih kecil dari batas utara")

    zmin, zmaks = _bulat(data.get("zoom_min")), _bulat(data.get("zoom_maks"))
    if zmin is None or zmaks is None:
        galat.append("Zoom minimum dan maksimum wajib berupa bilangan bulat")
    elif not (ZOOM_MIN <= zmin <= ZOOM_MAKS and ZOOM_MIN <= zmaks <= ZOOM_MAKS):
        galat.append(f"Zoom harus di antara {ZOOM_MIN} dan {ZOOM_MAKS}")
    elif zmin > zmaks:
        galat.append("Zoom minimum tidak boleh melebihi zoom maksimum")

    opasitas = _angka(data.get("opasitas"))
    if opasitas is None:
        opasitas = 0.85
    if not (0.1 <= opasitas <= 1):
        galat.append("Opasitas bawaan harus di antara 0,1 dan 1")

    dok = {
        "nama": nama,
        "sumber": _teks(data.get("sumber"), PANJANG_NAMA_MAKS),
        "tanggal_rekam": tanggal,
        "url_template": url,
        "batas": batas,
        "zoom_min": zmin,
        "zoom_maks": zmaks,
        "opasitas": round(opasitas, 2),
        "aktif": bool(data.get("aktif", True)),
        "keterangan": _teks(data.get("keterangan"), PANJANG_TEKS_MAKS),
    }
    return dok, galat


def bentuk_publik(dok: dict) -> dict:
    """Bidang yang dibutuhkan peta — tanpa jejak penulis/satker."""
    return {k: dok.get(k) for k in (
        "id", "nama", "sumber", "tanggal_rekam", "url_template", "batas",
        "zoom_min", "zoom_maks", "opasitas", "aktif", "keterangan", "version")}
