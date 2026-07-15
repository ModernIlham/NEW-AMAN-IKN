"""Logika murni PENILAIAN (Fase 5 tahap awal: penyusutan aset tetap).

PMK 65/PMK.06/2017 (pustaka §5): metode tunggal GARIS LURUS tanpa nilai
residu, dihitung per unit, dibukukan tiap AKHIR SEMESTER (30 Jun/31 Des)
dengan konvensi semester penuh. Masa manfaat per KELOMPOK kodefikasi
(prefix 5 digit) mengikuti KMK 295/KM.6/2019 jo. KMK 266/KM.6/2023.

Aset yang SUDAH direvaluasi final "terlahir kembali" (PMK 118/PMK.06/2017
jo. 57/2018 jo. 107/2019; Buletin Teknis SAP 18): nilai perolehan BARU =
nilai revaluasi, akumulasi penyusutan di-NOL-kan (eliminasi), masa manfaat
di-RESET PENUH dihitung ulang sejak tanggal revaluasi — metode/konvensi
lainnya (garis lurus, tanpa residu, semesteran) tidak berubah. Lihat
`dasar_penyusutan`.

Prinsip kejujuran data: kelompok yang belum punya masa manfaat terdaftar
TIDAK ditebak — asetnya masuk daftar "perlu referensi". Aset Rusak Berat
atau Hilang (Tidak Ditemukan) TIDAK otomatis berhenti disusutkan: selama
masih tercatat sebagai aset tetap ia tetap disusutkan; penyusutan baru
DIHENTIKAN (henti-susut) saat aset rusak berat/hilang itu TELAH DIUSULKAN
penghapusan/pemindahtanganan/pemusnahan — direklasifikasi keluar aset
tetap (PMK 65/2017, pustaka §5). Fungsi murni tanpa Mongo/IO agar teruji unit.
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


def status_susut(asset, peta=None, diusulkan=False):
    """('susut'|'henti'|'tanpa_referensi'|'tidak', alasan, masa_tahun|None).

    `diusulkan` = aset SUDAH punya usulan penghapusan aktif (belum ditolak).
    Kondisi Rusak Berat / status Hilang (Tidak Ditemukan) SAJA tidak
    menghentikan penyusutan — aset tetap disusutkan selama masih tercatat
    sebagai aset tetap. Henti-susut hanya berlaku saat aset rusak berat ATAU
    hilang itu TELAH DIUSULKAN penghapusan (reklas keluar aset tetap, PMK
    65/2017 — pustaka §5: "aset hilang / rusak berat yang telah diusulkan").
    """
    peta = MASA_MANFAAT_DEFAULT if peta is None else peta
    kode = str(asset.get("asset_code") or "").strip()
    gol = golongan_of(kode)
    if gol in GOLONGAN_TANPA_SUSUT:
        return "tidak", GOLONGAN_TANPA_SUSUT[gol], None
    rusak_berat = str(asset.get("condition") or "").strip() == "Rusak Berat"
    hilang = str(asset.get("inventory_status") or "").strip() == "Tidak Ditemukan"
    if diusulkan and (rusak_berat or hilang):
        dasar = "Rusak Berat" if rusak_berat else "Hilang (Tidak Ditemukan)"
        return ("henti",
                f"{dasar} & telah diusulkan penghapusan — penyusutan dihentikan (reklas keluar aset tetap, PMK 65/2017)",
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


def dasar_penyusutan(asset):
    """Basis & titik-mulai penyusutan satu aset → (harga, mulai_iso, sumber).

    Aset yang SUDAH direvaluasi final "terlahir kembali" (PMK 118/PMK.06/2017
    jo. 57/2018 jo. 107/2019; Buletin Teknis SAP 18): NILAI PEROLEHAN BARU =
    nilai revaluasi, akumulasi penyusutan di-NOL-kan (metode eliminasi), dan
    MASA MANFAAT di-RESET PENUH — penyusutan dihitung ULANG dari tanggal
    revaluasi dengan masa manfaat penuh kelompok. Metode garis lurus, tanpa
    residu, semesteran, konvensi semester penuh TIDAK berubah (pustaka §5).

    Basis revaluasi dipakai HANYA bila nilai wajar > 0 DAN tanggal revaluasi
    valid (kalau tidak → fallback ke nilai/tanggal perolehan historis).
    """
    nilai_rev = parse_harga(asset.get("nilai_wajar_terakhir"))
    tgl_rev = (asset.get("revaluasi") or {}).get("tanggal_dokumen")
    if nilai_rev > 0 and semester_index(tgl_rev) is not None:
        return nilai_rev, tgl_rev, "revaluasi"
    return parse_harga(asset.get("purchase_price")), asset.get("purchase_date"), "perolehan"


def rekap_penyusutan(assets, per_iso, peta=None, uraian_golongan=None,
                     diusulkan_ids=None):
    """Rekap posisi penyusutan per golongan + daftar telaah.

    `diusulkan_ids` = himpunan id aset yang punya usulan penghapusan aktif
    (belum ditolak) — aset rusak berat di dalamnya masuk henti-susut; yang
    di luar tetap disusutkan meski rusak berat (PMK 65/2017, pustaka §5).

    Aset yang sudah direvaluasi final disusutkan atas NILAI REVALUASI dengan
    masa manfaat di-reset penuh sejak tanggal revaluasi (lihat
    `dasar_penyusutan`); `jumlah_revaluasi` menghitung berapa yang demikian.

    Kembalikan {"per_golongan": [...], "total": {...},
    "henti": [...], "tanpa_referensi": [...], "tidak": {alasan: jumlah},
    "jumlah_habis": n, "jumlah_revaluasi": n} — semua dari data nyata; aset
    yang tak bisa dihitung TIDAK ikut angka penyusutan melainkan tampil di daftarnya.
    """
    uraian_golongan = uraian_golongan or {}
    diusulkan_ids = diusulkan_ids or set()
    per_gol = {}
    henti, tanpa_ref = [], []
    tidak = {}
    jumlah_habis = 0
    jumlah_revaluasi = 0
    for a in assets or []:
        status, alasan, masa = status_susut(
            a, peta, diusulkan=a.get("id") in diusulkan_ids)
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
        # Aset revaluasi: basis = nilai revaluasi, mulai = tanggal revaluasi,
        # masa manfaat penuh (reset) — mesin sama, cukup ganti basis & titik mulai.
        harga, mulai, sumber = dasar_penyusutan(a)
        if sumber == "revaluasi":
            jumlah_revaluasi += 1
        d = hitung_penyusutan(harga, masa, mulai, per_iso)
        gol = golongan_of(a.get("asset_code")) or "?"
        g = per_gol.setdefault(gol, {
            "golongan": gol,
            "uraian": uraian_golongan.get(gol) or f"Golongan {gol}",
            "jumlah": 0, "nilai_perolehan": 0.0,
            "akumulasi": 0.0, "nilai_buku": 0.0,
        })
        g["jumlah"] += 1
        g["nilai_perolehan"] += harga  # nilai perolehan BARU bila sudah direvaluasi
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
            "jumlah_habis": jumlah_habis, "jumlah_revaluasi": jumlah_revaluasi}


# ---------------------------------------------------------------------------
# Register koreksi nilai & hasil penilaian per aset (riset #184; PMK 99
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


# ---------------------------------------------------------------------------
# Riwayat nilai per aset (read-only, #203). Gabungkan nilai perolehan
# (master aset) dengan peristiwa koreksi/revaluasi (penilaian_koreksi #184)
# menjadi jejak kronologis. Nilai buku terkini = nilai_baru koreksi
# non-informasional terakhir; penilaian tujuan tertentu tidak mengubah buku.
# ---------------------------------------------------------------------------

def susun_riwayat_nilai(asset, koreksi_list) -> dict:
    """Jejak kronologis nilai satu aset → {peristiwa, nilai_terkini, ...}."""
    asset = asset or {}
    harga_awal = parse_harga(asset.get("purchase_price"))
    peristiwa = [{
        "tanggal": str(asset.get("purchase_date") or "").strip()[:10],
        "jenis": "perolehan",
        "label": "Perolehan",
        "nilai_lama": None,
        "nilai_baru": harga_awal,
        "selisih": None,
        "nomor_dokumen": "",
        "status_sakti": "",
        "informasional": False,
    }]
    # Urut koreksi menaik menurut tanggal dokumen (tak valid → di akhir "")
    for k in sorted(koreksi_list or [],
                    key=lambda x: str(x.get("tanggal_dokumen") or "")):
        jenis = k.get("jenis")
        informasional = (jenis == "penilaian_tujuan_tertentu")
        peristiwa.append({
            "tanggal": str(k.get("tanggal_dokumen") or "").strip()[:10],
            "jenis": jenis,
            "label": JENIS_KOREKSI_NILAI.get(jenis, jenis),
            "nilai_lama": parse_harga(k.get("nilai_lama")),
            "nilai_baru": parse_harga(k.get("nilai_baru")),
            "selisih": parse_harga(k.get("nilai_baru")) - parse_harga(k.get("nilai_lama")),
            "nomor_dokumen": str(k.get("nomor_dokumen") or "").strip(),
            "jenis_dokumen": k.get("jenis_dokumen"),
            "status_sakti": k.get("status_sakti") or "",
            "informasional": informasional,
        })
    # Nilai buku terkini: ikuti koreksi non-informasional terakhir
    nilai_terkini = harga_awal
    for p in peristiwa[1:]:
        if not p["informasional"]:
            nilai_terkini = p["nilai_baru"]
    return {
        "peristiwa": peristiwa,
        "nilai_perolehan": harga_awal,
        "nilai_terkini": nilai_terkini,
        "jumlah_koreksi": len(peristiwa) - 1,
    }


# Header CSV register koreksi nilai (dipakai endpoint ekspor & test).
HEADER_CSV_KOREKSI = [
    "kode_aset", "nup", "nama_aset", "jenis", "jenis_dokumen",
    "nomor_dokumen", "tanggal_dokumen", "nilai_lama", "nilai_baru",
    "selisih", "dampak_masa_manfaat", "masa_manfaat_semester",
    "penilai_pelaksana", "status_sakti", "catatan", "dibuat_oleh",
]


def baris_csv_koreksi(koreksi_list) -> list:
    """Susun baris CSV register koreksi nilai: [header, *data] — fungsi murni.

    Nilai rupiah dibulatkan ke bilangan bulat; kode jenis/dokumen/SAKTI
    diterjemahkan ke labelnya. Urutan mengikuti input (endpoint mengurut
    via Mongo). Tanpa Mongo/IO agar teruji unit (pola ekspor #158).
    """
    baris = [list(HEADER_CSV_KOREKSI)]
    for k in koreksi_list or []:
        # Bulatkan dulu agar kolom selisih konsisten dengan lama/baru di CSV.
        lama = int(round(parse_harga(k.get("nilai_lama"))))
        baru = int(round(parse_harga(k.get("nilai_baru"))))
        baris.append([
            k.get("asset_code") or "",
            k.get("NUP") or "",
            k.get("asset_name") or "",
            JENIS_KOREKSI_NILAI.get(k.get("jenis"), k.get("jenis") or ""),
            DOKUMEN_KOREKSI.get(k.get("jenis_dokumen"), k.get("jenis_dokumen") or ""),
            k.get("nomor_dokumen") or "",
            str(k.get("tanggal_dokumen") or "")[:10],
            lama,
            baru,
            baru - lama,
            DAMPAK_MASA_MANFAAT.get(k.get("dampak_masa_manfaat"),
                                    k.get("dampak_masa_manfaat") or ""),
            int(k.get("masa_manfaat_semester") or 0),
            k.get("penilai_pelaksana") or "",
            STATUS_SAKTI_KOREKSI.get(k.get("status_sakti"),
                                     k.get("status_sakti") or ""),
            k.get("catatan") or "",
            k.get("created_by") or "",
        ])
    return baris


def build_asset_revaluasi_projection(koreksi: dict, now_iso: str) -> dict:
    """Proyeksi master aset saat koreksi/REVALUASI nilai FINAL (tercatat SAKTI) —
    Prinsip 3 Bab 5 (transaksi = jurnal register `penilaian_koreksi`, master =
    proyeksi). Mengembalikan dict `$set` untuk `db.assets`: `nilai_wajar_terakhir`
    (nilai wajar terkini) + jejak `revaluasi.{...}`.

    SENGAJA TIDAK menimpa `purchase_price` (nilai perolehan historis tetap utuh
    untuk audit); laporan posisi/nilai yang ingin memakai nilai wajar cukup
    membaca `nilai_wajar_terakhir` bila ada (langkah lanjutan terpisah). Pemanggil
    menambah `$inc: {version: 1}` (bust cache/ETag + picu OCC 409 form usang).
    """
    nilai = float(koreksi.get("nilai_baru") or 0)
    return {
        "nilai_wajar_terakhir": nilai,
        "revaluasi": {
            "nilai_wajar": nilai,
            "nilai_lama": float(koreksi.get("nilai_lama") or 0),
            "jenis": str(koreksi.get("jenis") or ""),
            "nomor_dokumen": str(koreksi.get("nomor_dokumen") or "").strip(),
            "tanggal_dokumen": str(koreksi.get("tanggal_dokumen") or "").strip()[:10],
            "koreksi_id": str(koreksi.get("id") or ""),
            "diproyeksikan_pada": now_iso,
        },
    }
