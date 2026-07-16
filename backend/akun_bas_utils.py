"""Referensi Akun Neraca (Bagan Akun Standar) per golongan BMN — LOGIKA MURNI.

Memetakan golongan kodefikasi BMN (digit 1) → akun neraca aset (BAS). Dasar
riset (Jul 2026) dari Neraca Percobaan Akrual tingkat satker + Laporan Posisi
BMN di Neraca berbagai K/L (sumber sekunder resmi); KODE AKUN 6-DIGIT SUB-
KELOMPOK bervariasi per jenis — nilai di sini adalah akun REPRESENTATIF per
golongan, wajib diverifikasi ke Lampiran BAS (KEP-211/PB/2018 dst.) & bisa
ditimpa admin (pola referensi masa manfaat).
"""

# golongan (1 digit) → {akun neraca representatif, uraian}
AKUN_NERACA_DEFAULT = {
    "1": {"akun": "117111", "uraian": "Persediaan (Barang Konsumsi — akun 117xxx per jenis)"},
    "2": {"akun": "131111", "uraian": "Tanah"},
    "3": {"akun": "132111", "uraian": "Peralatan dan Mesin"},
    "4": {"akun": "133111", "uraian": "Gedung dan Bangunan"},
    "5": {"akun": "134111", "uraian": "Jalan, Irigasi, dan Jaringan"},
    "6": {"akun": "135121", "uraian": "Aset Tetap Lainnya"},
    "7": {"akun": "136111", "uraian": "Konstruksi Dalam Pengerjaan (KDP)"},
    "8": {"akun": "162151", "uraian": "Aset Tak Berwujud (Software — ATB 162xxx per jenis)"},
}


def validate_akun_bas(golongan, akun):
    """Kembalikan daftar error (kosong bila valid). MURNI (teruji unit)."""
    errors = []
    g = str(golongan or "").strip()
    if g not in AKUN_NERACA_DEFAULT:
        errors.append("Golongan harus 1 digit (1–8)")
    a = str(akun or "").strip()
    if not a.isdigit() or not (3 <= len(a) <= 6):
        errors.append("Kode akun harus 3–6 digit angka (mis. 132111)")
    return errors


def akun_untuk_golongan(kode_barang, peta=None):
    """Akun neraca untuk sebuah kode barang (via golongan/digit pertama).

    `peta` = gabungan default + entri satker (override menang). Kembalikan
    {golongan, akun, uraian} atau None bila golongan tak dikenal. MURNI.
    """
    peta = AKUN_NERACA_DEFAULT if peta is None else peta
    g = str(kode_barang or "").strip()[:1]
    if g not in peta:
        return None
    rec = peta[g]
    return {"golongan": g, "akun": rec.get("akun", ""), "uraian": rec.get("uraian", "")}
