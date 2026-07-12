"""Logika murni PELAPORAN — periode pelaporan ber-kunci (pustaka §2.3).

Entitas Periode Pelaporan (Semester I / Semester II / Tahunan per tahun)
dengan status terbuka → terkunci. Periode terkunci menandai laporan
periode itu FINAL: PDF LBKP & CaLBMN diberi penanda "FINAL (terkunci
per {tanggal})". Kunci dapat dibuka kembali oleh admin dengan catatan
(riwayat tercatat) — data tidak pernah dihapus diam-diam.

Fungsi murni tanpa Mongo/IO agar teruji unit.
"""

STATUS_PERIODE = {"terbuka": "Terbuka", "terkunci": "Terkunci"}


def _terisi(v) -> bool:
    return bool(str(v or "").strip())


def label_periode_pelaporan(tahun, semester=None) -> str:
    """Label baku periode: 'Semester I 2026' / 'Semester II 2026' /
    'Tahunan 2026'."""
    if semester == 1:
        return f"Semester I {tahun}"
    if semester == 2:
        return f"Semester II {tahun}"
    return f"Tahunan {tahun}"


def kunci_unik_periode(tahun, semester=None) -> str:
    """Kunci identitas unik periode (untuk cegah duplikat)."""
    return f"{tahun}-S{semester}" if semester in (1, 2) else f"{tahun}-T"


def validate_periode(data: dict) -> list:
    """Validasi pembuatan periode baru → daftar pesan kesalahan."""
    errors = []
    tahun = data.get("tahun")
    if not (isinstance(tahun, int) and 2000 <= tahun <= 2100):
        errors.append("Tahun periode wajib 2000–2100")
    if data.get("semester") not in (None, 1, 2):
        errors.append("Semester harus 1, 2, atau kosong (tahunan)")
    return errors


def validate_kunci_periode(periode: dict) -> list:
    """Periode hanya bisa dikunci saat terbuka."""
    if periode.get("status") != "terbuka":
        return ["Periode sudah terkunci"]
    return []


def validate_buka_periode(periode: dict, data: dict) -> list:
    """Membuka kembali periode terkunci wajib beralasan (jejak audit)."""
    errors = []
    if periode.get("status") != "terkunci":
        errors.append("Periode tidak sedang terkunci")
    if not _terisi(data.get("alasan")):
        errors.append("Alasan membuka kunci wajib diisi")
    return errors


def rekap_periode(items) -> dict:
    """Ringkasan register periode: total + per status."""
    items = items or []
    return {"total": len(items),
            "terbuka": sum(1 for p in items if p.get("status") == "terbuka"),
            "terkunci": sum(1 for p in items if p.get("status") == "terkunci")}


def cari_periode(items, tahun, semester=None):
    """Temukan periode dengan identitas (tahun, semester) — None bila
    belum dibuat."""
    target = kunci_unik_periode(tahun, semester)
    for p in items or []:
        if kunci_unik_periode(p.get("tahun"), p.get("semester")) == target:
            return p
    return None


def penanda_final(periode) -> str:
    """Sufiks subjudul laporan bila periodenya terkunci; '' bila tidak."""
    if not periode or periode.get("status") != "terkunci":
        return ""
    tanggal = str(periode.get("tanggal_kunci") or "")[:10]
    return f" — FINAL (terkunci per {tanggal})" if tanggal else " — FINAL"
