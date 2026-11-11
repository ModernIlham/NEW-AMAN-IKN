"""Gambar ikon kelompok orang untuk keluaran backend (PGW-09; rencana 3.8).

Satu-satunya pemakai naskah berikon adalah Laporan Eksekutif (K10). Gambar
dibaca dari `data/ikon_kelompok.json` — sumber yang sama dengan layar
(`frontend/src/lib/ikonKelompok.json`, salinan byte-identik).
"""
import json
from functools import lru_cache
from html import escape
from pathlib import Path

_BERKAS = Path(__file__).resolve().parent / "data" / "ikon_kelompok.json"


@lru_cache(maxsize=1)
def data_ikon() -> dict:
    return json.loads(_BERKAS.read_text(encoding="utf-8"))


def svg_ikon(kunci: str, ukuran: int = 8) -> str:
    """SVG sebaris untuk satu kunci ikon, dengan `<title>` teks alternatifnya.

    Kunci tak dikenal → "" (tanpa ikon). Warna dari `hex` — tetap terbedakan
    dicetak hitam-putih karena bentuknya berbeda."""
    d = data_ikon()["ikon"].get(kunci)
    if not d:
        return ""
    isi = "".join(
        "<{} {}/>".format(tag, " ".join(
            f'{k}="{escape(str(v), quote=True)}"' for k, v in attrs.items()))
        for tag, attrs in d["elemen"])
    alt = escape(d["alt"], quote=True)
    return (f'<svg class="ikon-kelompok" xmlns="http://www.w3.org/2000/svg" role="img" '
            f'aria-label="{alt}" width="{int(ukuran)}" height="{int(ukuran)}" '
            f'viewBox="0 0 24 24" fill="none" stroke="{escape(d["hex"], quote=True)}" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            f"<title>{alt}</title>{isi}</svg>")


def peta_svg(ukuran: int = 8) -> dict:
    """{kunci: svg} untuk seluruh kunci ikon."""
    return {k: svg_ikon(k, ukuran) for k in data_ikon()["urutan"]}


def legenda(ukuran: int = 8) -> list:
    """[{kunci, svg, alt}] berurutan — bahan baris keterangan ikon."""
    d = data_ikon()
    return [{"kunci": k, "svg": svg_ikon(k, ukuran), "alt": d["ikon"][k]["alt"]}
            for k in d["urutan"]]
