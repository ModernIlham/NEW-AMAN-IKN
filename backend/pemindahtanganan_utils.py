"""Logika murni PEMINDAHTANGANAN (Fase 6 tahap awal: register usulan).

PMK 111/PMK.06/2016 jo. 165/PMK.06/2021 (pustaka §7): empat bentuk —
Penjualan (prinsip lelang; tanpa lelang hanya kasus khusus), Tukar
Menukar, Hibah, PMPP. Register per USULAN multi-aset berstatus; dokumen
wajib per tahap mengunci transisi (mencegah temuan: pemindahtanganan
tanpa persetujuan, hasil tidak disetor, tak ditindaklanjuti penghapusan).

Fungsi murni tanpa Mongo/IO agar teruji unit.
"""
from datetime import date

from pembukuan_utils import parse_harga

BENTUK_PEMINDAHTANGANAN = {
    "penjualan_lelang": "Penjualan (lelang KPKNL)",
    "penjualan_langsung": "Penjualan tanpa lelang (kasus khusus)",
    "tukar_menukar": "Tukar Menukar",
    "hibah": "Hibah",
    "pmpp": "Penyertaan Modal Pemerintah Pusat",
}

# Label dokumen pelaksanaan per bentuk (syarat status "dilaksanakan")
DOKUMEN_PELAKSANAAN = {
    "penjualan_lelang": "Risalah Lelang",
    "penjualan_langsung": "Perjanjian Jual Beli/BAST",
    "tukar_menukar": "Perjanjian Tukar Menukar + BAST",
    "hibah": "Naskah Hibah + BAST",
    "pmpp": "Peraturan Pemerintah PMPP + BAST",
}

STATUS_USULAN_PT = {
    "diusulkan": "Diusulkan",
    "disetujui": "Disetujui",
    "dilaksanakan": "Dilaksanakan",
    "selesai": "Selesai (SK Penghapusan terbit)",
    "ditolak": "Ditolak/Batal",
}

TRANSISI_PT = {
    "diusulkan": {"disetujui", "ditolak"},
    "disetujui": {"dilaksanakan", "ditolak"},
    "dilaksanakan": {"selesai"},
    "selesai": set(),
    "ditolak": set(),
}

TENGGAT_LELANG_HARI = 183  # permohonan lelang ≤6 bulan sejak persetujuan


def _tgl(v):
    try:
        return date.fromisoformat(str(v or "").strip()[:10])
    except (ValueError, TypeError):
        return None


def validate_usulan_pt(data: dict) -> list:
    """Validasi usulan baru → daftar pesan kesalahan."""
    errors = []
    if data.get("bentuk") not in BENTUK_PEMINDAHTANGANAN:
        valid = ", ".join(BENTUK_PEMINDAHTANGANAN)
        errors.append(f"Bentuk tidak dikenal (pilihan: {valid})")
    if not str(data.get("pihak") or "").strip():
        errors.append("Pihak penerima/pembeli/mitra wajib diisi")
    if not data.get("asset_ids"):
        errors.append("Minimal satu aset dalam usulan")
    return errors


def validate_transisi_pt(u: dict, ke: str, data: dict) -> list:
    """Validasi transisi status + dokumen wajib per tahap.

    disetujui  → wajib nomor persetujuan (+ instansi pemberi).
    dilaksanakan → wajib nomor dokumen pelaksanaan sesuai bentuk;
                   bentuk penjualan juga wajib NTPN setor PNBP.
    selesai    → wajib nomor SK Penghapusan (tindak lanjut PMK 83/2016).
    """
    errors = []
    dari = u.get("status")
    if ke not in STATUS_USULAN_PT:
        valid = ", ".join(STATUS_USULAN_PT)
        errors.append(f"Status tidak dikenal (pilihan: {valid})")
        return errors
    if ke not in TRANSISI_PT.get(dari, set()):
        errors.append(
            f"Transisi {STATUS_USULAN_PT.get(dari, dari)} → {STATUS_USULAN_PT[ke]} tidak sah")
        return errors
    if ke == "disetujui" and not str(data.get("nomor_persetujuan") or "").strip():
        errors.append("Nomor surat persetujuan wajib diisi")
    if ke == "dilaksanakan":
        label = DOKUMEN_PELAKSANAAN.get(u.get("bentuk"), "dokumen pelaksanaan")
        if not str(data.get("nomor_dokumen") or "").strip():
            errors.append(f"Nomor {label} wajib diisi")
        if u.get("bentuk", "").startswith("penjualan") and not str(data.get("ntpn") or "").strip():
            errors.append("NTPN bukti setor hasil penjualan ke Kas Negara wajib diisi")
    if ke == "selesai" and not str(data.get("nomor_sk_penghapusan") or "").strip():
        errors.append("Nomor SK Penghapusan wajib diisi (tindak lanjut PMK 83/2016)")
    return errors


def peringatan_pt(u: dict, today_iso: str) -> list:
    """Peringatan kepatuhan per usulan (tenggat lelang 6 bulan)."""
    warn = []
    hari_ini = _tgl(today_iso)
    if (u.get("status") == "disetujui"
            and u.get("bentuk") == "penjualan_lelang"):
        setuju = _tgl(u.get("tanggal_persetujuan"))
        if setuju and hari_ini:
            sisa = TENGGAT_LELANG_HARI - (hari_ini - setuju).days
            if sisa < 0:
                warn.append("Lewat 6 bulan sejak persetujuan tanpa pelaksanaan "
                            "lelang — wajib penilaian ulang (PMK 165/2021)")
            elif sisa <= 30:
                warn.append(f"Tenggat permohonan lelang tinggal ±{sisa} hari "
                            "(≤6 bulan sejak persetujuan)")
    return warn


def rekap_pt(items):
    """Ringkasan register: hitung per status/bentuk + nilai perolehan."""
    per_status = {k: 0 for k in STATUS_USULAN_PT}
    per_bentuk = {k: 0 for k in BENTUK_PEMINDAHTANGANAN}
    nilai = 0.0
    jumlah_aset = 0
    for u in items or []:
        s = u.get("status")
        if s in per_status:
            per_status[s] += 1
        b = u.get("bentuk")
        if b in per_bentuk:
            per_bentuk[b] += 1
        for a in u.get("aset") or []:
            jumlah_aset += 1
            nilai += parse_harga(a.get("harga"))
    return {"jumlah": len(items or []), "jumlah_aset": jumlah_aset,
            "per_status": per_status, "per_bentuk": per_bentuk, "nilai": nilai}
