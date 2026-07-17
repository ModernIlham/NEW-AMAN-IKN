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


def validate_tenggat(data: dict) -> list:
    """Validasi pengaturan tenggat periode (YYYY-MM-DD; kosong = hapus)."""
    from datetime import date

    tenggat = str(data.get("tenggat") or "").strip()
    if not tenggat:
        return []
    try:
        date.fromisoformat(tenggat[:10])
    except ValueError:
        return ["Tenggat tidak valid (YYYY-MM-DD)"]
    return []


def info_tenggat_periode(periode: dict, today_iso: str) -> dict:
    """Pengingat tenggat penyampaian periode TERBUKA → {tenggat, lewat,
    sisa_hari}. Periode terkunci/tanpa tenggat tidak diingatkan.

    Sisa dihitung hari kalender — tenggat penyampaian laporan ditetapkan
    sebagai tanggal (surat DJKN/K/L per periode), bukan hari kerja.
    """
    from datetime import date

    kosong = {"tenggat": None, "lewat": False, "sisa_hari": None}
    tenggat = str(periode.get("tenggat") or "").strip()[:10]
    if periode.get("status") != "terbuka" or not tenggat:
        return kosong
    try:
        batas = date.fromisoformat(tenggat)
        hari_ini = date.fromisoformat(str(today_iso)[:10])
    except ValueError:
        return kosong
    selisih = (batas - hari_ini).days
    return {"tenggat": tenggat, "lewat": selisih < 0,
            "sisa_hari": max(0, selisih)}


def penanda_final(periode) -> str:
    """Sufiks subjudul laporan bila periodenya terkunci; '' bila tidak."""
    if not periode or periode.get("status") != "terkunci":
        return ""
    tanggal = str(periode.get("tanggal_kunci") or "")[:10]
    return f" — FINAL (terkunci per {tanggal})" if tanggal else " — FINAL"


# ── Narasi tanggal Berita Acara (BAHI dkk.) — "Pada hari ini, Jumat, tanggal
# Tujuh Belas bulan Juli tahun Dua Ribu Dua Puluh Enam". MURNI (teruji unit).

HARI_ID = ("Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu")
BULAN_ID = ("Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
            "Agustus", "September", "Oktober", "November", "Desember")

_SATUAN_ID = ("nol", "satu", "dua", "tiga", "empat", "lima", "enam", "tujuh",
              "delapan", "sembilan", "sepuluh", "sebelas")


def terbilang_id(n) -> str:
    """Bilangan bulat 0..999999 → kata bahasa Indonesia (huruf kecil).

    Cukup untuk tanggal (1-31) dan tahun (4 digit). Nilai di luar rentang /
    bukan angka → ''.
    """
    try:
        n = int(n)
    except (TypeError, ValueError):
        return ""
    if n < 0 or n > 999999:
        return ""
    if n < 12:
        return _SATUAN_ID[n]
    if n < 20:
        return f"{_SATUAN_ID[n - 10]} belas"
    if n < 100:
        sisa = n % 10
        return f"{_SATUAN_ID[n // 10]} puluh" + (f" {_SATUAN_ID[sisa]}" if sisa else "")
    if n < 200:
        sisa = n % 100
        return "seratus" + (f" {terbilang_id(sisa)}" if sisa else "")
    if n < 1000:
        sisa = n % 100
        return f"{_SATUAN_ID[n // 100]} ratus" + (f" {terbilang_id(sisa)}" if sisa else "")
    if n < 2000:
        sisa = n % 1000
        return "seribu" + (f" {terbilang_id(sisa)}" if sisa else "")
    sisa = n % 1000
    return f"{terbilang_id(n // 1000)} ribu" + (f" {terbilang_id(sisa)}" if sisa else "")


def narasi_hari_tanggal(iso) -> dict:
    """Komponen narasi BA dari tanggal ISO 'YYYY-MM-DD[…]'.

    Kembalikan {hari, tanggal_terbilang, bulan, tahun_terbilang} ber-Kapital
    Tiap Kata (gaya naskah dinas), atau None bila tanggal tak valid.
    Tanpa strptime — tahan placeholder 9999-12-31 (dianggap tak valid).
    """
    from datetime import date
    s = str(iso or "").strip()[:10]
    try:
        d = date.fromisoformat(s)
    except ValueError:
        return None
    if d.year > 2200:  # placeholder SIMAN 9999-12-31 dkk.
        return None
    return {
        "hari": HARI_ID[d.weekday()],
        "tanggal_terbilang": terbilang_id(d.day).title(),
        "bulan": BULAN_ID[d.month - 1],
        "tahun_terbilang": terbilang_id(d.year).title(),
    }
