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
