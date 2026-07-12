"""Logika murni PEMANFAATAN (Fase 5 tahap awal: register perjanjian).

PMK 115/PMK.06/2020 (pustaka §6): enam bentuk pemanfaatan; satker =
pengusul & penatausaha (uang disetor mitra langsung ke Kas Negara).
Register mencegah dua temuan auditor tersering secara struktural:
status "aktif" hanya sah bila nomor persetujuan Pengelola + perjanjian
terisi (sewa: + NTPN bukti setor).

Fungsi murni tanpa Mongo/IO agar teruji unit.
"""
from datetime import date

# key → (label, jangka maksimal tahun, dapat diperpanjang)
BENTUK_PEMANFAATAN = {
    "sewa": ("Sewa", 5, True),
    "pinjam_pakai": ("Pinjam Pakai (Pemda/Pemdes)", 5, True),
    "ksp": ("Kerja Sama Pemanfaatan (KSP)", 30, True),
    "bgs_bsg": ("Bangun Guna Serah / Bangun Serah Guna", 30, False),
    "kspi": ("Kerja Sama Penyediaan Infrastruktur (KSPI)", 50, True),
    "ketupi": ("KETUPI", 50, True),
}

AMBANG_JATUH_TEMPO_HARI = 60  # syarat perpanjangan ≥2 bulan sebelum berakhir


def _tgl(v):
    try:
        return date.fromisoformat(str(v or "").strip()[:10])
    except (ValueError, TypeError):
        return None


def validate_pemanfaatan(data: dict) -> list:
    """Validasi payload register perjanjian → daftar pesan kesalahan."""
    errors = []
    bentuk = data.get("bentuk")
    if bentuk not in BENTUK_PEMANFAATAN:
        valid = ", ".join(BENTUK_PEMANFAATAN)
        errors.append(f"Bentuk tidak dikenal (pilihan: {valid})")
    if not str(data.get("mitra") or "").strip():
        errors.append("Nama mitra wajib diisi")
    mulai, berakhir = _tgl(data.get("mulai")), _tgl(data.get("berakhir"))
    if not mulai or not berakhir:
        errors.append("Tanggal mulai & berakhir wajib (format YYYY-MM-DD)")
    elif berakhir <= mulai:
        errors.append("Tanggal berakhir harus setelah mulai")
    elif bentuk in BENTUK_PEMANFAATAN:
        maks = BENTUK_PEMANFAATAN[bentuk][1]
        if (berakhir - mulai).days > maks * 366:
            errors.append(f"Jangka waktu melebihi maksimal {maks} tahun untuk "
                          f"{BENTUK_PEMANFAATAN[bentuk][0]} (PMK 115/2020)")
    try:
        if float(data.get("nilai") or 0) < 0:
            errors.append("Nilai tidak boleh negatif")
    except (TypeError, ValueError):
        errors.append("Nilai harus angka")
    return errors


def dokumen_kurang(p: dict) -> list:
    """Kekurangan dokumen yang menghalangi status aktif (temuan auditor).

    Wajib semua bentuk: persetujuan Pengelola + perjanjian; sewa juga
    wajib NTPN (bukti setor PNBP oleh penyewa).
    """
    kurang = []
    if not str(p.get("nomor_persetujuan") or "").strip():
        kurang.append("Nomor persetujuan Pengelola Barang belum terisi")
    if not str(p.get("nomor_perjanjian") or "").strip():
        kurang.append("Nomor perjanjian belum terisi")
    if p.get("bentuk") == "sewa" and not str(p.get("ntpn") or "").strip():
        kurang.append("NTPN bukti setor PNBP sewa belum terisi")
    return kurang


def status_perjanjian(p: dict, today_iso: str) -> str:
    """'tidak_lengkap' | 'aktif' | 'jatuh_tempo' (≤60 hari) | 'berakhir'."""
    hari_ini = _tgl(today_iso)
    berakhir = _tgl(p.get("berakhir"))
    if berakhir and hari_ini and berakhir < hari_ini:
        return "berakhir"
    if dokumen_kurang(p):
        return "tidak_lengkap"
    if berakhir and hari_ini and (berakhir - hari_ini).days <= AMBANG_JATUH_TEMPO_HARI:
        return "jatuh_tempo"
    return "aktif"


LABEL_STATUS_PERJANJIAN = {
    "tidak_lengkap": "Dokumen Belum Lengkap",
    "aktif": "Aktif",
    "jatuh_tempo": "Jatuh Tempo ≤60 Hari",
    "berakhir": "Berakhir",
}


def tahun_tertunggak(p: dict, today_iso: str) -> list:
    """Tahun kontribusi tahunan yang belum tercatat pembayarannya.

    Berlaku hanya bila kontribusi_tahunan > 0 (KSP/BGS-BSG/KSPI/KETUPI —
    pustaka §6: kewajiban PNBP tahunan mitra). Kewajiban timbul tiap
    tahun kalender sejak tahun mulai s.d. min(tahun berjalan, tahun
    berakhir); tahun yang sudah tercatat pada daftar `kontribusi`
    dikecualikan.
    """
    try:
        if float(p.get("kontribusi_tahunan") or 0) <= 0:
            return []
    except (TypeError, ValueError):
        return []
    mulai = _tgl(p.get("mulai"))
    berakhir = _tgl(p.get("berakhir"))
    hari_ini = _tgl(today_iso)
    if not (mulai and hari_ini):
        return []
    akhir = min(hari_ini.year, berakhir.year if berakhir else hari_ini.year)
    terbayar = {str(k.get("tahun") or "").strip()
                for k in (p.get("kontribusi") or [])}
    return [t for t in range(mulai.year, akhir + 1) if str(t) not in terbayar]


def peringatan_kontribusi(p: dict, today_iso: str) -> list:
    """Peringatan tunggakan kontribusi tahunan (kosong bila tertib)."""
    tunggak = tahun_tertunggak(p, today_iso)
    if not tunggak:
        return []
    daftar = ", ".join(str(t) for t in tunggak)
    return [f"Kontribusi tahunan belum tercatat untuk tahun: {daftar}"]


def validate_kontribusi(data: dict, p: dict, today_iso: str) -> list:
    """Validasi pencatatan pembayaran kontribusi satu tahun."""
    errors = []
    tahun = str(data.get("tahun") or "").strip()
    if not (tahun.isdigit() and 2000 <= int(tahun) <= 2100):
        errors.append("Tahun kontribusi wajib 4 digit yang wajar")
    if not str(data.get("ntpn") or "").strip():
        errors.append("NTPN bukti setor PNBP wajib diisi")
    t = _tgl(data.get("tanggal"))
    hari_ini = _tgl(today_iso)
    if t and hari_ini and t > hari_ini:
        errors.append("Tanggal setor tidak boleh di masa depan")
    if tahun and any(str(k.get("tahun") or "").strip() == tahun
                     for k in (p.get("kontribusi") or [])):
        errors.append(f"Kontribusi tahun {tahun} sudah tercatat")
    return errors


def rekap_pemanfaatan(items, today_iso: str):
    """Ringkasan register: hitung per status & bentuk + total nilai."""
    per_status = {k: 0 for k in LABEL_STATUS_PERJANJIAN}
    per_bentuk = {k: 0 for k in BENTUK_PEMANFAATAN}
    total_nilai = 0.0
    for p in items or []:
        s = status_perjanjian(p, today_iso)
        per_status[s] = per_status.get(s, 0) + 1
        b = p.get("bentuk")
        if b in per_bentuk:
            per_bentuk[b] += 1
        try:
            total_nilai += float(p.get("nilai") or 0)
        except (TypeError, ValueError):
            pass
    return {"per_status": per_status, "per_bentuk": per_bentuk,
            "jumlah": len(items or []), "total_nilai": total_nilai}
