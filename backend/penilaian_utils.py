"""Logika murni PENILAIAN (Fase 5 tahap awal: penyusutan aset tetap).

PMK 65/PMK.06/2017 (pustaka §5): metode tunggal GARIS LURUS tanpa nilai
residu, dihitung per unit, dibukukan tiap AKHIR SEMESTER (30 Jun/31 Des)
dengan konvensi semester penuh. Masa manfaat per KELOMPOK kodefikasi
(prefix 5 digit) mengikuti KMK 295/KM.6/2019 jo. KMK 266/KM.6/2023.

Prinsip kejujuran data: kelompok yang belum punya masa manfaat terdaftar
TIDAK ditebak — asetnya masuk daftar "perlu referensi"; aset Rusak Berat
masuk daftar telaah henti-susut (PMK 65: henti susut saat telah diusulkan
penghapusan). Fungsi murni tanpa Mongo/IO agar teruji unit.
"""
from datetime import date

from pembukuan_utils import golongan_of, parse_harga

# Kelompok (5 digit) → masa manfaat TAHUN (pustaka §5; butir verifikasi
# #11: entri "lazim" wajib divalidasi ke lampiran KMK sebelum seed penuh).
MASA_MANFAAT_DEFAULT = {
    "30201": 7,   # Alat Angkutan Darat Bermotor (terverifikasi)
    "30501": 5,   # Alat Kantor (terverifikasi)
    "30502": 5,   # Alat Rumah Tangga (terverifikasi)
    "31001": 4,   # Komputer Unit (lazim)
    "31002": 4,   # Peralatan Komputer (lazim)
    "30601": 5,   # Alat Studio (lazim)
    "30602": 5,   # Alat Komunikasi (lazim)
}

GOLONGAN_TANPA_SUSUT = {
    "1": "Persediaan — bukan objek penyusutan aset tetap",
    "2": "Tanah tidak disusutkan (PMK 65/2017)",
    "6": "Aset Tetap Lainnya tidak disusutkan (pengecualian alat musik modern menyusul)",
    "7": "Konstruksi Dalam Pengerjaan tidak disusutkan",
    "8": "Aset Lainnya/Tak Berwujud — amortisasi terpisah (menyusul)",
}


def validate_masa_manfaat(kode, tahun) -> list:
    """Validasi entri referensi masa manfaat → daftar pesan kesalahan.

    Kunci = KELOMPOK kodefikasi (5 digit, golongan 3-5 yang disusutkan);
    tahun 1-60 (rentang wajar tabel KMK: 2-50).
    """
    errors = []
    k = str(kode or "").strip()
    if len(k) != 5 or not k.isdigit():
        errors.append("Kode kelompok harus 5 digit angka (mis. 30201)")
    elif k[0] not in ("3", "4", "5"):
        errors.append("Golongan di luar objek penyusutan (hanya 3/4/5)")
    try:
        t = int(tahun)
    except (TypeError, ValueError):
        t = 0
    if not 1 <= t <= 60:
        errors.append("Masa manfaat harus 1-60 tahun")
    return errors


def semester_index(tanggal_iso):
    """Indeks semester absolut (tahun×2 + 0/1); None bila tanggal tak valid."""
    try:
        t = date.fromisoformat(str(tanggal_iso or "").strip()[:10])
    except (ValueError, TypeError):
        return None
    return t.year * 2 + (0 if t.month <= 6 else 1)


def status_susut(asset, peta=None):
    """('susut'|'henti'|'tanpa_referensi'|'tidak', alasan, masa_tahun|None)."""
    peta = MASA_MANFAAT_DEFAULT if peta is None else peta
    kode = str(asset.get("asset_code") or "").strip()
    gol = golongan_of(kode)
    if gol in GOLONGAN_TANPA_SUSUT:
        return "tidak", GOLONGAN_TANPA_SUSUT[gol], None
    if str(asset.get("condition") or "").strip() == "Rusak Berat":
        return ("henti",
                "Rusak Berat — telaah usulan penghapusan (henti susut saat telah diusulkan, PMK 65/2017)",
                None)
    masa = peta.get(kode[:5])
    if not masa:
        return ("tanpa_referensi",
                f"Kelompok {kode[:5] or '?'} belum punya masa manfaat terdaftar — lengkapi referensi KMK",
                None)
    if semester_index(asset.get("purchase_date")) is None:
        return ("tanpa_referensi",
                "Tanggal perolehan tidak tercatat — lengkapi data aset",
                None)
    return "susut", "", masa


def hitung_penyusutan(harga, masa_tahun, perolehan_iso, per_iso):
    """Garis lurus semesteran tanpa residu (PMK 65/2017).

    Beban semester perolehan dibukukan penuh pada AKHIR semester itu —
    posisi per tanggal hanya memuat semester yang SUDAH BERAKHIR, sehingga
    terpakai = indeks_semester(per) − indeks_semester(perolehan), dipagari
    [0, masa manfaat dalam semester]. Nilai buku akhir = 0 (bukan Rp1).
    """
    h = parse_harga(harga)
    masa_sem = max(1, int(masa_tahun) * 2)
    i0 = semester_index(perolehan_iso)
    i1 = semester_index(per_iso)
    if i0 is None or i1 is None:
        terpakai = 0
    else:
        terpakai = max(0, min(masa_sem, i1 - i0))
    beban = h / masa_sem
    akumulasi = min(h, beban * terpakai)
    return {
        "beban_per_semester": beban,
        "semester_terpakai": terpakai,
        "masa_semester": masa_sem,
        "akumulasi": akumulasi,
        "nilai_buku": h - akumulasi,
        "habis": terpakai >= masa_sem,
    }


def rekap_penyusutan(assets, per_iso, peta=None, uraian_golongan=None):
    """Rekap posisi penyusutan per golongan + daftar telaah.

    Kembalikan {"per_golongan": [...], "total": {...},
    "henti": [...], "tanpa_referensi": [...], "tidak": {alasan: jumlah},
    "jumlah_habis": n} — semua dari data nyata; aset yang tak bisa
    dihitung TIDAK ikut angka penyusutan melainkan tampil di daftarnya.
    """
    uraian_golongan = uraian_golongan or {}
    per_gol = {}
    henti, tanpa_ref = [], []
    tidak = {}
    jumlah_habis = 0
    for a in assets or []:
        status, alasan, masa = status_susut(a, peta)
        ident = {"id": a.get("id"), "asset_code": a.get("asset_code"),
                 "NUP": a.get("NUP"), "asset_name": a.get("asset_name")}
        if status == "tidak":
            tidak[alasan] = tidak.get(alasan, 0) + 1
            continue
        if status == "henti":
            henti.append({**ident, "alasan": alasan,
                          "harga": parse_harga(a.get("purchase_price"))})
            continue
        if status == "tanpa_referensi":
            tanpa_ref.append({**ident, "alasan": alasan})
            continue
        d = hitung_penyusutan(a.get("purchase_price"), masa,
                              a.get("purchase_date"), per_iso)
        gol = golongan_of(a.get("asset_code")) or "?"
        g = per_gol.setdefault(gol, {
            "golongan": gol,
            "uraian": uraian_golongan.get(gol) or f"Golongan {gol}",
            "jumlah": 0, "nilai_perolehan": 0.0,
            "akumulasi": 0.0, "nilai_buku": 0.0,
        })
        g["jumlah"] += 1
        g["nilai_perolehan"] += parse_harga(a.get("purchase_price"))
        g["akumulasi"] += d["akumulasi"]
        g["nilai_buku"] += d["nilai_buku"]
        if d["habis"]:
            jumlah_habis += 1
    rows = [per_gol[g] for g in sorted(per_gol)]
    total = {
        "jumlah": sum(r["jumlah"] for r in rows),
        "nilai_perolehan": sum(r["nilai_perolehan"] for r in rows),
        "akumulasi": sum(r["akumulasi"] for r in rows),
        "nilai_buku": sum(r["nilai_buku"] for r in rows),
    }
    return {"per_golongan": rows, "total": total, "henti": henti,
            "tanpa_referensi": tanpa_ref, "tidak": tidak,
            "jumlah_habis": jumlah_habis}


# ---------------------------------------------------------------------------
# Register koreksi nilai & hasil penilaian per aset (riset #185; PMK 99
# Tahun 2024 mencabut PMK 173/2020 yang mencabut PMK 111/2017; revaluasi
# nasional: Perpres 75/2017 + PMK 118/2017 jo. 57/2018 jo. 107/2019).
# AMAN bukan penilai: nilai wajar sah hanya dari Laporan Penilaian
# Penilai Pemerintah DJKN/Penilai Publik; pencatatan resmi di SAKTI.
# ---------------------------------------------------------------------------

JENIS_KOREKSI_NILAI = {
    "revaluasi": "Revaluasi / penilaian kembali",
    "koreksi_inventarisasi": "Koreksi hasil inventarisasi",
    "koreksi_temuan_putusan": "Koreksi temuan BPK/APIP/putusan",
    "koreksi_pencatatan": "Koreksi kesalahan pencatatan",
    "penilaian_tujuan_tertentu": "Penilaian tujuan tertentu (informasional)",
}

DOKUMEN_KOREKSI = {
    "lhip": "LHIP (Laporan Hasil Inventarisasi & Penilaian)",
    "laporan_penilaian": "Laporan Penilaian",
    "ba": "Berita Acara",
    "sk_koreksi": "SK Koreksi",
}

DAMPAK_MASA_MANFAAT = {
    "tetap": "Masa manfaat tetap",
    "masa_manfaat_baru": "Masa manfaat baru (akumulasi reset)",
}

STATUS_SAKTI_KOREKSI = {
    "belum_dicatat": "Belum tercatat di SAKTI",
    "tercatat_sakti": "Sudah divalidasi & di-approve di SAKTI",
}


def validate_koreksi_nilai(data: dict) -> list:
    """Validasi pencatatan koreksi nilai → daftar pesan kesalahan."""
    from datetime import date

    errors = []
    if data.get("jenis") not in JENIS_KOREKSI_NILAI:
        valid = ", ".join(JENIS_KOREKSI_NILAI)
        errors.append(f"Jenis koreksi tidak dikenal (pilihan: {valid})")
    if data.get("jenis_dokumen") not in DOKUMEN_KOREKSI:
        valid = ", ".join(DOKUMEN_KOREKSI)
        errors.append(f"Jenis dokumen tidak dikenal (pilihan: {valid})")
    if not str(data.get("nomor_dokumen") or "").strip():
        errors.append("Nomor dokumen wajib diisi")
    tanggal = str(data.get("tanggal_dokumen") or "").strip()[:10]
    try:
        date.fromisoformat(tanggal)
    except ValueError:
        errors.append("Tanggal dokumen harus berformat YYYY-MM-DD")
    for k, label in (("nilai_lama", "Nilai lama"), ("nilai_baru", "Nilai baru")):
        try:
            if float(data.get(k) or 0) < 0:
                errors.append(f"{label} tidak boleh negatif")
        except (TypeError, ValueError):
            errors.append(f"{label} harus angka")
    if data.get("dampak_masa_manfaat") not in DAMPAK_MASA_MANFAAT:
        valid = ", ".join(DAMPAK_MASA_MANFAAT)
        errors.append(f"Dampak masa manfaat tidak dikenal (pilihan: {valid})")
    if data.get("dampak_masa_manfaat") == "masa_manfaat_baru":
        try:
            if int(data.get("masa_manfaat_semester") or 0) <= 0:
                errors.append("Masa manfaat baru (semester) harus lebih dari 0")
        except (TypeError, ValueError):
            errors.append("Masa manfaat baru harus angka semester")
    return errors


def rekap_koreksi_nilai(items) -> dict:
    """Ringkasan register: per jenis, belum tercatat SAKTI, total selisih.

    Selisih hanya dihitung untuk jenis yang mengubah nilai buku —
    penilaian tujuan tertentu bersifat informasional.
    """
    per_jenis = {k: 0 for k in JENIS_KOREKSI_NILAI}
    belum_sakti = 0
    selisih_total = 0.0
    for k in items or []:
        j = k.get("jenis")
        if j in per_jenis:
            per_jenis[j] += 1
        if (k.get("status_sakti") == "belum_dicatat"
                and j != "penilaian_tujuan_tertentu"):
            belum_sakti += 1
        if j != "penilaian_tujuan_tertentu":
            try:
                selisih_total += (float(k.get("nilai_baru") or 0)
                                  - float(k.get("nilai_lama") or 0))
            except (TypeError, ValueError):
                pass
    return {"jumlah": len(items or []), "per_jenis": per_jenis,
            "belum_tercatat_sakti": belum_sakti,
            "selisih_total": selisih_total}
