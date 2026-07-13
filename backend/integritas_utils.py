"""Logika murni integritas data lintas-modul (§5A Prinsip 1).

Register hilir (usulan penghapusan, pemeliharaan, pemindahtanganan, dll.)
menyimpan SNAPSHOT identitas aset (`asset_code`/`NUP`/`asset_name`) saat record
dibuat. Bila master aset kelak DIEDIT (mis. NUP dikoreksi), snapshot itu jadi
BASI → laporan/telusur silang bisa memakai identitas usang.

Modul ini hanya membandingkan dua dict (snapshot vs master terkini) — tanpa
Mongo/IO agar teruji unit. Pemanggil (endpoint read-only) yang mengambil data.
"""

# Field identitas yang di-snapshot di register hilir.
FIELD_IDENTITAS = ("asset_code", "NUP", "asset_name")


def _norm(v) -> str:
    """Normalisasi nilai identitas untuk pembanding: string ter-strip; None/""
    dianggap sama (abaikan beda None vs kosong vs spasi tepi)."""
    return str(v if v is not None else "").strip()


def identitas_drift(snapshot, master, fields=FIELD_IDENTITAS) -> dict:
    """Bandingkan snapshot identitas aset (di register hilir) dengan master aset
    TERKINI. Kembalikan dict ``{field: {"snapshot": s, "master": m}}`` HANYA
    untuk field yang BERBEDA (basi). Kosong ``{}`` = konsisten.

    Perbandingan memakai nilai ter-strip (None/""/spasi tepi setara) sehingga
    tak ada 'drift' palsu karena beda kosong. `snapshot`/`master` None/kosong →
    ``{}`` (tak ada pembanding — kasus 'master hilang' ditangani pemanggil).
    """
    if not snapshot or not master:
        return {}
    out = {}
    for f in fields:
        s = _norm(snapshot.get(f))
        m = _norm(master.get(f))
        if s != m:
            out[f] = {"snapshot": s, "master": m}
    return out
