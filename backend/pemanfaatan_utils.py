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


# ---------------------------------------------------------------------------
# Fasilitas penyiapan & pelaksanaan transaksi pemanfaatan (riset #190).
# PMK 18 Tahun 2024 (umum, domain DJPPR) / PMK 139/PMK.08/2022 (khusus IKN):
# BUKAN bentuk pemanfaatan ke-7 — hanya pendampingan Menteri Keuangan untuk
# menyiapkan & mengeksekusi transaksi; skema yang didampingi sampai
# transaksi hanyalah KSP dan BGS/BSG. Register merekamnya sebagai atribut
# pendamping opsional pada perjanjian, bukan bentuk tersendiri.
# ---------------------------------------------------------------------------
DASAR_FASILITAS = {
    "tanpa_fasilitas": "Tanpa fasilitas",
    "pmk_18_2024": "Fasilitas transaksi PMK 18/2024",
    "pmk_139_2022": "Fasilitas transaksi PMK 139/PMK.08/2022 (IKN)",
}

# Skema yang dapat lahir dari fasilitas (Kajian Rekomendasi Transaksi)
BENTUK_DAPAT_FASILITAS = {"ksp", "bgs_bsg"}


def validate_fasilitas(data: dict) -> list:
    """Validasi atribut fasilitas transaksi pada payload perjanjian."""
    errors = []
    dasar = str(data.get("dasar_fasilitas") or "tanpa_fasilitas").strip()
    if dasar not in DASAR_FASILITAS:
        pilihan = ", ".join(DASAR_FASILITAS)
        errors.append(f"Dasar fasilitas tidak dikenal (pilihan: {pilihan})")
        return errors
    if dasar == "tanpa_fasilitas":
        return errors
    if data.get("bentuk") not in BENTUK_DAPAT_FASILITAS:
        errors.append("Fasilitas transaksi hanya untuk bentuk KSP atau "
                      "BGS/BSG (PMK 18/2024)")
    if not str(data.get("nomor_penetapan_fasilitas") or "").strip():
        errors.append("Nomor penetapan fasilitas wajib diisi bila perjanjian "
                      "lahir dari fasilitas transaksi")
    return errors


# ---------------------------------------------------------------------------
# Usulan pemanfaatan berstatus + perpanjangan (ASET-MANFAAT).
# Register perjanjian di atas hanya merekam perjanjian JADI — proses
# pengajuan ke Pengelola Barang (usulan KPB → persetujuan → tanda tangan
# perjanjian) dan perpanjangan tidak pernah terekam, padahal PMK 115/2020
# menaruh keputusan di Pengelola dan BGS/BSG tegas TIDAK dapat
# diperpanjang. Tiket usulan menutup dua lubang itu.
# ---------------------------------------------------------------------------
JENIS_USULAN_PEMANFAATAN = {
    "baru": "Pemanfaatan baru",
    "perpanjangan": "Perpanjangan perjanjian",
}

STATUS_USULAN_PEMANFAATAN = {
    "draf": "Draf",
    "diajukan": "Diajukan ke Pengelola Barang",
    "disetujui": "Disetujui Pengelola",
    "ditolak": "Ditolak",
    "perjanjian": "Perjanjian Ditandatangani",
    "dibatalkan": "Dibatalkan",
}

# diajukan boleh MUNDUR ke draf (koreksi salah klik — pola register TGR);
# ditolak/perjanjian/dibatalkan terminal.
TRANSISI_USULAN_PEMANFAATAN = {
    "draf": {"diajukan", "dibatalkan"},
    "diajukan": {"disetujui", "ditolak", "draf"},
    "disetujui": {"perjanjian", "dibatalkan"},
    "ditolak": set(),
    "perjanjian": set(),
    "dibatalkan": set(),
}

STATUS_USULAN_TERMINAL = {"ditolak", "perjanjian", "dibatalkan"}

# status tujuan → (field nomor, field tanggal, label dokumen wajib)
DOK_USULAN_PEMANFAATAN = {
    "diajukan": ("nomor_usulan", "tanggal_usulan",
                 "Nomor surat usulan ke Pengelola Barang"),
    "disetujui": ("nomor_persetujuan", "tanggal_persetujuan",
                  "Nomor surat persetujuan Pengelola Barang"),
    "perjanjian": ("nomor_perjanjian", "tanggal_perjanjian",
                   "Nomor perjanjian"),
}


def validate_usulan_perpanjangan(data: dict, induk: dict, today_iso: str) -> list:
    """Validasi usulan perpanjangan atas perjanjian induk (PMK 115/2020):
    bentuk harus dapat diperpanjang (BGS/BSG tidak), induk belum berakhir,
    pinjam pakai wajib diajukan ≥60 hari (2 bulan) sebelum berakhir,
    berakhir baru setelah berakhir lama dan jangka tambahan ≤ maksimal."""
    errors = []
    if not induk:
        return ["Perjanjian induk tidak ditemukan"]
    bentuk = induk.get("bentuk")
    info = BENTUK_PEMANFAATAN.get(bentuk)
    if not info:
        return [f"Bentuk perjanjian induk tidak dikenal: {bentuk}"]
    if not info[2]:
        errors.append(f"{info[0]} tidak dapat diperpanjang (PMK 115/2020) — "
                      "ajukan pemanfaatan baru")
    lama = _tgl(induk.get("berakhir"))
    baru = _tgl(data.get("berakhir"))
    hari_ini = _tgl(today_iso)
    if not lama:
        errors.append("Tanggal berakhir perjanjian induk tidak valid")
    elif hari_ini and lama < hari_ini:
        errors.append("Perjanjian sudah berakhir — tidak dapat diperpanjang, "
                      "ajukan pemanfaatan baru")
    elif (bentuk == "pinjam_pakai" and hari_ini
          and (lama - hari_ini).days < AMBANG_JATUH_TEMPO_HARI):
        errors.append("Usulan perpanjangan Pinjam Pakai wajib diajukan "
                      "minimal 60 hari (2 bulan) sebelum perjanjian berakhir")
    if not baru:
        errors.append("Tanggal berakhir baru wajib (format YYYY-MM-DD)")
    elif lama and baru <= lama:
        errors.append("Tanggal berakhir baru harus setelah tanggal berakhir "
                      "perjanjian induk")
    elif lama and (baru - lama).days > info[1] * 366:
        errors.append(f"Jangka perpanjangan melebihi maksimal {info[1]} tahun "
                      f"untuk {info[0]} (PMK 115/2020)")
    try:
        if float(data.get("nilai") or 0) < 0:
            errors.append("Nilai tidak boleh negatif")
    except (TypeError, ValueError):
        errors.append("Nilai harus angka")
    return errors


def validate_transisi_usulan_pemanfaatan(dari: str, ke: str,
                                         payload: dict) -> list:
    """Daftar galat transisi usulan — dokumen wajib per tahap."""
    p = payload or {}
    if ke not in STATUS_USULAN_PEMANFAATAN:
        return [f"Status tujuan tidak dikenal: {ke}"]
    if ke not in TRANSISI_USULAN_PEMANFAATAN.get(dari, set()):
        return [f"Transisi {STATUS_USULAN_PEMANFAATAN.get(dari, dari)} → "
                f"{STATUS_USULAN_PEMANFAATAN.get(ke, ke)} tidak diizinkan"]
    dok = DOK_USULAN_PEMANFAATAN.get(ke)
    if dok and not str(p.get("nomor_dokumen") or "").strip():
        return [f"{dok[2]} wajib diisi"]
    return []


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
