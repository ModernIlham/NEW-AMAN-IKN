"""Logika murni PENGANGGARAN (PMK 62/2023 + PMK 153/2021 — pustaka §9).

Register usulan penganggaran tingkat satker: jejak usulan dari kertas
kerja RKBMN menuju anggaran — diusulkan → disetujui telaah (RKBMN Hasil
Penelaahan) → masuk DIPA → terealisasi; ditolak = terminal. Status diisi
operator berdasar dokumen resmi (SIMAN V2/SAKTI adalah kanal resmi; AMAN
mencatat jejak per usulan/aset, bukan memutus).

Fungsi murni tanpa Mongo/IO agar teruji unit.
"""
from pembukuan_utils import parse_harga

# Jenis usulan → (label, kelompok akun BAS tujuan)
JENIS_ANGGARAN = {
    "pengadaan": ("Pengadaan (belanja modal)", "53x"),
    "pemeliharaan": ("Pemeliharaan", "523"),
}

# Akun BAS ringkas per jenis (pustaka §9.2) — pilihan, bukan validasi keras
AKUN_BAS = {
    "531": "Belanja Modal Tanah",
    "532": "Belanja Modal Peralatan dan Mesin",
    "533": "Belanja Modal Gedung dan Bangunan",
    "534": "Belanja Modal Jalan, Irigasi, dan Jaringan",
    "536": "Belanja Modal Lainnya",
    "523": "Belanja Pemeliharaan",
}

STATUS_ANGGARAN = {
    "diusulkan": "Diusulkan (RKBMN)",
    "disetujui_telaah": "Disetujui Hasil Penelaahan",
    "masuk_dipa": "Masuk DIPA",
    "terealisasi": "Terealisasi",
    "ditolak": "Ditolak",
}

TRANSISI_ANGGARAN = {
    "diusulkan": {"disetujui_telaah", "ditolak"},
    "disetujui_telaah": {"masuk_dipa"},
    "masuk_dipa": {"terealisasi"},
    "terealisasi": set(),
    "ditolak": set(),
}


def validate_usulan_anggaran(data: dict) -> list:
    """Validasi usulan baru → daftar pesan kesalahan (kosong = sah)."""
    errors = []
    if data.get("jenis") not in JENIS_ANGGARAN:
        pilihan = ", ".join(JENIS_ANGGARAN)
        errors.append(f"Jenis tidak dikenal (pilihan: {pilihan})")
    if not str(data.get("uraian") or "").strip():
        errors.append("Uraian usulan wajib diisi")
    tahun = str(data.get("tahun_anggaran") or "").strip()
    if not (tahun.isdigit() and 2000 <= int(tahun) <= 2100):
        errors.append("Tahun anggaran sasaran wajib 4 digit yang wajar")
    if parse_harga(data.get("nilai_usulan")) <= 0:
        errors.append("Nilai usulan harus lebih dari 0")
    akun = str(data.get("akun") or "").strip()
    if akun and akun not in AKUN_BAS:
        pilihan = ", ".join(AKUN_BAS)
        errors.append(f"Akun tidak dikenal (pilihan: {pilihan})")
    if akun and data.get("jenis") in JENIS_ANGGARAN:
        modal = akun.startswith("53")
        if modal != (data["jenis"] == "pengadaan"):
            errors.append("Akun tidak sesuai jenis (pengadaan → 53x; "
                          "pemeliharaan → 523)")
    return errors


def validate_transisi_anggaran(u: dict, ke: str, data: dict) -> list:
    """Validasi pindah status + dokumen/nilai wajib per tahap."""
    errors = []
    dari = u.get("status")
    if ke not in STATUS_ANGGARAN:
        errors.append("Status tujuan tidak dikenal")
        return errors
    if ke not in TRANSISI_ANGGARAN.get(dari, set()):
        errors.append(f"Transisi {dari} → {ke} tidak sah")
        return errors
    if ke == "disetujui_telaah":
        if parse_harga(data.get("nilai_disetujui")) <= 0:
            errors.append("Nilai disetujui hasil penelaahan wajib diisi")
    if ke == "masuk_dipa":
        if not str(data.get("nomor_dipa") or "").strip():
            errors.append("Nomor DIPA (petikan) wajib diisi")
        if parse_harga(data.get("nilai_dipa")) <= 0:
            errors.append("Nilai pada DIPA wajib diisi")
    if ke == "terealisasi":
        if parse_harga(data.get("nilai_realisasi")) <= 0:
            errors.append("Nilai realisasi wajib diisi")
    return errors


def sanding_per_akun(items) -> list:
    """Sanding rencana vs realisasi per akun BAS (pustaka §9).

    Baris per akun (usulan tanpa akun digabung ke "lainnya"), terurut
    kode akun; serapan = realisasi / DIPA per akun. Meniru pola sanding
    pagu-realisasi satker, pada granularitas usulan yang tidak dimiliki
    SAKTI.
    """
    grup = {}
    for u in items or []:
        akun = str(u.get("akun") or "").strip() or "lainnya"
        g = grup.setdefault(akun, {"akun": akun,
                                   "label": AKUN_BAS.get(akun, "Tanpa akun"),
                                   "jumlah": 0, "usulan": 0.0,
                                   "disetujui": 0.0, "dipa": 0.0,
                                   "realisasi": 0.0, "realisasi_bast": 0.0})
        g["jumlah"] += 1
        g["usulan"] += parse_harga(u.get("nilai_usulan"))
        g["disetujui"] += parse_harga(u.get("nilai_disetujui"))
        g["dipa"] += parse_harga(u.get("nilai_dipa"))
        g["realisasi"] += parse_harga(u.get("nilai_realisasi"))
        # Realisasi NYATA dari Pengadaan bertaut (BAST) — cek-silang terhadap
        # realisasi manual; serapan_persen tetap berbasis nilai_realisasi
        # (benar secara akuntansi), selisih hanya penanda rekonsiliasi.
        g["realisasi_bast"] += parse_harga(u.get("realisasi_pengadaan"))
    rows = sorted(grup.values(), key=lambda g: g["akun"])
    for g in rows:
        g["serapan_persen"] = round(
            g["realisasi"] / g["dipa"] * 100, 1) if g["dipa"] else 0.0
        g["selisih_bast"] = round(g["realisasi"] - g["realisasi_bast"], 2)
    return rows


# Selisih realisasi manual vs BAST di bawah ini dianggap pembulatan.
TOLERANSI_REKONSILIASI = 1.0


def rekap_rekonsiliasi(items, toleransi: float = TOLERANSI_REKONSILIASI) -> dict:
    """Cek-silang realisasi manual (nilai_realisasi) vs realisasi nyata
    Pengadaan bertaut (realisasi_pengadaan) → {jumlah_perlu_rekonsiliasi,
    total_selisih}. Hanya usulan yang PUNYA perolehan bertaut yang dinilai
    (realisasi_pengadaan > 0); usulan tanpa tautan bukan objek rekonsiliasi."""
    jumlah, total = 0, 0.0
    for u in items or []:
        bast = parse_harga(u.get("realisasi_pengadaan"))
        if bast <= 0:
            continue
        selisih = parse_harga(u.get("nilai_realisasi")) - bast
        if abs(selisih) > toleransi:
            jumlah += 1
            total += selisih
    return {"jumlah_perlu_rekonsiliasi": jumlah,
            "total_selisih": round(total, 2)}


NAMA_TRIWULAN = {1: "TW I", 2: "TW II", 3: "TW III", 4: "TW IV"}


def _tanggal_status(u: dict, status: str):
    """Tanggal ISO (YYYY-MM-DD) entri riwayat TERAKHIR berstatus tsb."""
    tanggal = None
    for r in u.get("riwayat") or []:
        if r.get("status") == status and r.get("tanggal"):
            tanggal = str(r["tanggal"])[:10]
    return tanggal


def sanding_per_triwulan(items) -> list:
    """Sanding realisasi per triwulan per tahun anggaran (pustaka §9).

    Triwulan realisasi diambil dari tanggal entri riwayat "terealisasi";
    serapan kumulatif dibanding total nilai DIPA tahun anggaran tsb.
    Usulan terealisasi tanpa tanggal riwayat dihitung di `tanpa_triwulan`
    (tetap masuk total, tidak hilang). Tahun tanpa DIPA maupun realisasi
    tidak ditampilkan (belum ada yang disanding).
    """
    grup = {}
    for u in items or []:
        tahun = str(u.get("tahun_anggaran") or "").strip() or "?"
        g = grup.setdefault(tahun, {
            "tahun_anggaran": tahun, "dipa": 0.0, "realisasi": 0.0,
            "per_triwulan": {q: {"triwulan": q, "nama": NAMA_TRIWULAN[q],
                                 "jumlah": 0, "realisasi": 0.0}
                             for q in (1, 2, 3, 4)},
            "tanpa_triwulan": 0,
        })
        g["dipa"] += parse_harga(u.get("nilai_dipa"))
        if u.get("status") != "terealisasi":
            continue
        nilai = parse_harga(u.get("nilai_realisasi"))
        g["realisasi"] += nilai
        tanggal = _tanggal_status(u, "terealisasi")
        bulan = 0
        if tanggal and len(tanggal) >= 7 and tanggal[5:7].isdigit():
            bulan = int(tanggal[5:7])
        if 1 <= bulan <= 12:
            tw = g["per_triwulan"][(bulan - 1) // 3 + 1]
            tw["jumlah"] += 1
            tw["realisasi"] += nilai
        else:
            g["tanpa_triwulan"] += 1
    rows = [g for g in grup.values() if g["dipa"] or g["realisasi"]]
    rows.sort(key=lambda g: g["tahun_anggaran"])
    for g in rows:
        kumulatif = 0.0
        daftar = []
        for q in (1, 2, 3, 4):
            tw = g["per_triwulan"][q]
            kumulatif += tw["realisasi"]
            tw["kumulatif"] = kumulatif
            tw["serapan_kumulatif_persen"] = round(
                kumulatif / g["dipa"] * 100, 1) if g["dipa"] else 0.0
            daftar.append(tw)
        g["per_triwulan"] = daftar
        g["serapan_persen"] = round(
            g["realisasi"] / g["dipa"] * 100, 1) if g["dipa"] else 0.0
    return rows


def rekap_anggaran(items) -> dict:
    """Ringkasan register: per status/jenis + total nilai tiap tahap.

    serapan = realisasi / DIPA (hanya usulan yang sudah punya nilai DIPA).
    """
    per_status = {k: 0 for k in STATUS_ANGGARAN}
    per_jenis = {k: 0 for k in JENIS_ANGGARAN}
    nilai = {"usulan": 0.0, "disetujui": 0.0, "dipa": 0.0, "realisasi": 0.0}
    for u in items or []:
        s = u.get("status")
        if s in per_status:
            per_status[s] += 1
        j = u.get("jenis")
        if j in per_jenis:
            per_jenis[j] += 1
        nilai["usulan"] += parse_harga(u.get("nilai_usulan"))
        nilai["disetujui"] += parse_harga(u.get("nilai_disetujui"))
        nilai["dipa"] += parse_harga(u.get("nilai_dipa"))
        nilai["realisasi"] += parse_harga(u.get("nilai_realisasi"))
    serapan = (nilai["realisasi"] / nilai["dipa"] * 100) if nilai["dipa"] else 0.0
    return {"jumlah": len(items or []), "per_status": per_status,
            "per_jenis": per_jenis, "nilai": nilai,
            "serapan_persen": round(serapan, 1)}


# ---------------------------------------------------------------------------
# Kalender penganggaran (pustaka §9.4) — tahapan ber-tenggat KONFIGURABEL.
# Tenggat internal tiap K/L berbeda (surat edaran masing-masing), sehingga
# tanggal TIDAK di-hardcode dari regulasi; admin mengisinya sendiri.
# ---------------------------------------------------------------------------

def validate_tahapan_kalender(data: dict) -> list:
    """Validasi tahapan kalender penganggaran → daftar pesan kesalahan."""
    from datetime import date

    errors = []
    if not str(data.get("nama") or "").strip():
        errors.append("Nama tahapan wajib diisi")
    tahun = str(data.get("tahun_anggaran") or "").strip()
    if not (len(tahun) == 4 and tahun.isdigit()):
        errors.append("Tahun anggaran harus 4 digit angka")
    tanggal = str(data.get("tanggal") or "").strip()[:10]
    try:
        date.fromisoformat(tanggal)
    except ValueError:
        errors.append("Tanggal tenggat harus berformat YYYY-MM-DD")
    return errors


def info_tenggat_tahapan(tahapan: dict, today_iso: str) -> dict:
    """Pengingat satu tahapan → {tanggal, lewat, sisa_hari} (hari kalender)."""
    from datetime import date

    kosong = {"tanggal": None, "lewat": False, "sisa_hari": None}
    tanggal = str(tahapan.get("tanggal") or "").strip()[:10]
    try:
        batas = date.fromisoformat(tanggal)
        hari_ini = date.fromisoformat(str(today_iso)[:10])
    except ValueError:
        return kosong
    selisih = (batas - hari_ini).days
    return {"tanggal": tanggal, "lewat": selisih < 0,
            "sisa_hari": max(0, selisih)}


def rekap_kalender(items, today_iso: str) -> dict:
    """Ringkasan tahapan: total, lewat tenggat, dan mendatang ≤30 hari."""
    lewat = mendatang = 0
    for t in items or []:
        info = info_tenggat_tahapan(t, today_iso)
        if info["tanggal"] is None:
            continue
        if info["lewat"]:
            lewat += 1
        elif info["sisa_hari"] is not None and info["sisa_hari"] <= 30:
            mendatang += 1
    return {"jumlah": len(items or []), "lewat": lewat,
            "mendatang_30_hari": mendatang}
