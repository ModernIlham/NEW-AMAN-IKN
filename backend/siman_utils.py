"""Logika murni SINKRONISASI SIMAN V2 — impor XLSX "Master Aset".

SIMAN V2 adalah sumber data VALID (pencatatan resmi); AMAN alat bantu
lapangan. Karena SIMAN belum menyediakan API untuk satker, sinkronisasi
berjalan lewat IMPOR MANUAL hasil ekspor SIMAN V2 (sheet "Master Aset",
±78 kolom): tiap baris dicocokkan ke aset AMAN, perbedaan field kunci
dicatat sebagai `selisih` pada subdoc `siman` aset — ditandai di halaman
aset agar bisa disinkronkan kembali (nilai SIMAN yang menang).

Pencocokan (paling stabil dulu):
  1. `Kode Register` SIMAN ↔ field `kode_register` aset (ID internal SIMAN,
     tahan terhadap reklasifikasi kode barang).
  2. Kode Barang + NUP (dinormalisasi digit).

Fungsi murni tanpa Mongo/IO agar teruji unit. Jebakan yang ditangani:
tanggal placeholder SIMAN `9999-12-31` (= tidak ada) — JANGAN strptime
(OverflowError); angka Excel bergaya float ("1.0"); "Belum berlokasi" /
"Tidak Ada Inputan" = belum diisi di SIMAN (bukan selisih).
"""
import re

from pembukuan_utils import parse_harga

# ── Peta kolom SIMAN → kunci internal (header di-normalisasi lowercase) ──
KOLOM_SIMAN = {
    "kode barang": "kode_barang",
    "nup": "nup",
    "nama barang": "nama_barang",
    "merk": "merk",
    "tipe": "tipe",
    "kondisi": "kondisi",
    "status bmn": "status_bmn",
    "nilai perolehan": "nilai_perolehan",
    "nilai perolehan pertama": "nilai_perolehan_pertama",
    "nilai penyusutan": "nilai_penyusutan",
    "nilai buku": "nilai_buku",
    "tanggal perolehan": "tanggal_perolehan",
    "tanggal pengapusan": "tanggal_penghapusan",   # ejaan asli file SIMAN
    "tanggal penghapusan": "tanggal_penghapusan",
    "nama pengguna": "nama_pengguna",
    "lokasi ruang": "lokasi_ruang",
    "kode register": "kode_register",
    "status penggunaan": "status_penggunaan",
    "no psp": "no_psp",
    "tanggal psp": "tanggal_psp",
    "intra / extra": "intra_ekstra",
    "intra/extra": "intra_ekstra",
    "umur aset": "umur_aset",
    "kode satker": "kode_satker",
    "nama satker": "nama_satker",
    "status bmn idle": "status_idle",
    "henti guna": "henti_guna",
}

# Nilai SIMAN yang berarti "belum diisi" — jangan dianggap selisih.
_KOSONG_SIMAN = {"", "-", "belum berlokasi", "tidak ada inputan"}

# ── Field yang DIBANDINGKAN (AMAN ↔ SIMAN); jenis menentukan normalisasi ──
# Hanya field yang SIMAN memang otoritatif & AMAN punya padanannya.
PERBANDINGAN = (
    # (field_aman, kunci_siman, label, jenis)
    ("asset_code", "kode_barang", "Kode Barang", "kode"),
    ("category", "nama_barang", "Nama Barang (uraian kode)", "teks"),
    ("brand", "merk", "Merk", "teks"),
    ("model", "tipe", "Tipe", "teks"),
    ("condition", "kondisi", "Kondisi", "teks"),
    ("purchase_price", "nilai_perolehan", "Nilai Perolehan", "angka"),
    ("purchase_date", "tanggal_perolehan", "Tanggal Perolehan", "tanggal"),
    ("user", "nama_pengguna", "Nama Pengguna", "teks"),
    # kode_register: bila AMAN masih kosong, ID register SIMAN DIADOPSI
    # otomatis saat impor (identitas milik SIMAN — bukan selisih); hanya
    # ditandai selisih bila AMAN terisi nilai yang BERBEDA.
    ("kode_register", "kode_register", "Kode Register", "register"),
)
FIELD_TERAPKAN = frozenset(f for f, _, _, _ in PERBANDINGAN)

# Referensi SIMAN yang DISIMPAN di subdoc (tampil di halaman aset) tanpa
# dibandingkan — AMAN tidak mencatat nilai ini sendiri (penyusutan dihitung
# modul Penilaian; PSP dicatat modul Penggunaan).
KUNCI_REFERENSI = (
    "nilai_penyusutan", "nilai_buku", "umur_aset", "status_penggunaan",
    "no_psp", "tanggal_psp", "intra_ekstra", "status_bmn", "lokasi_ruang",
)


def norm_kode(v) -> str:
    """Kode barang → digit saja ('3030203001'; '3.03.02.03.001' pun sama)."""
    return re.sub(r"\D", "", str(v or ""))


def norm_nup(v) -> str:
    """NUP → angka tanpa nol depan/artefak float Excel ('001'/'1.0' → '1')."""
    s = str(v or "").strip()
    if s.endswith(".0"):
        s = s[:-2]
    s = s.lstrip("0")
    return s or ("0" if str(v or "").strip() else "")


def norm_teks(v) -> str:
    """Teks untuk perbandingan: rapikan spasi (tanpa mengubah huruf)."""
    return re.sub(r"\s+", " ", str(v if v is not None else "")).strip()


def norm_tanggal(v) -> str:
    """Tanggal → 'YYYY-MM-DD'; placeholder 9999-12-31 (& datetime-nya) = ''.

    Jangan pakai strptime — nilai 9999 memicu OverflowError di sebagian
    platform (jebakan yang sudah pernah menggigit di modul impor).
    """
    s = str(v if v is not None else "").strip()[:10]
    if not s or s.startswith("9999"):
        return ""
    return s


def _kosong_siman(v) -> bool:
    return norm_teks(v).lower() in _KOSONG_SIMAN


def kunci_aset(kode, nup) -> str:
    """Kunci pencocokan kode+NUP; '' bila salah satunya kosong."""
    k, n = norm_kode(kode), norm_nup(nup)
    return f"{k}|{n}" if k and n else ""


def petakan_header(header_row):
    """Baris header XLSX → ({kunci_internal: index_kolom}, kunci_wajib_hilang).

    Wajib minimal: kode barang + NUP (kunci pencocokan fallback).
    """
    peta = {}
    for i, cell in enumerate(header_row or []):
        h = norm_teks(cell).lower()
        kunci = KOLOM_SIMAN.get(h)
        if kunci and kunci not in peta:
            peta[kunci] = i
    hilang = [k for k in ("kode_barang", "nup") if k not in peta]
    return peta, hilang


def deteksi_header(rows, maks_baris=25):
    """Cari baris header di antara `rows` (iterable of tuple) → (idx, peta)|None.

    Ekspor SIMAN kadang menaruh judul/kop di baris awal sebelum header tabel;
    scan maksimal `maks_baris` baris pertama dan ambil baris pertama yang
    memuat kolom wajib (kode barang + NUP).
    """
    for i, row in enumerate(rows):
        if i >= maks_baris:
            break
        peta, hilang = petakan_header(row)
        if not hilang:
            return i, peta
    return None


def norm_kode_satker(v) -> str:
    """Kode satker utk perbandingan: alfanumerik kapital saja
    ('126.01.1600691778.000-KP' == '126011600691778000KP')."""
    return re.sub(r"[^0-9A-Za-z]", "", str(v or "")).upper()


def validasi_satker(kode_file_set, kode_terdaftar_set):
    """Bandingkan kode satker pada FILE dengan kode satker TERDAFTAR di AMAN.

    Kembalikan {"cocok": bool, "kode_file": [...], "kode_terdaftar": [...]}.
    Bila salah satu sisi kosong (file tanpa kolom satker / AMAN belum diisi)
    dianggap cocok — validasi hanya bermakna saat keduanya terisi.
    """
    file_norm = {norm_kode_satker(k) for k in (kode_file_set or set())} - {""}
    daftar_norm = {norm_kode_satker(k) for k in (kode_terdaftar_set or set())} - {""}
    cocok = (not file_norm or not daftar_norm
             or bool(file_norm & daftar_norm))
    return {
        "cocok": cocok,
        "kode_file": sorted(file_norm)[:5],
        "kode_terdaftar": sorted(daftar_norm)[:5],
    }


def ringkas_baris_belum_tercatat(b):
    """Baris SIMAN tanpa padanan aset AMAN → dict ringkas utk register/CSV/draft."""
    return {
        "kode_barang": b.get("kode_barang", ""),
        "nup": b.get("nup", ""),
        "nama_barang": b.get("nama_barang", ""),
        "merk": b.get("merk", ""),
        "tipe": b.get("tipe", ""),
        "kondisi": b.get("kondisi", ""),
        "nilai_perolehan": b.get("nilai_perolehan", 0),
        "tanggal_perolehan": b.get("tanggal_perolehan", ""),
        "kode_register": b.get("kode_register", ""),
    }


def parse_baris(row, peta_header):
    """Satu baris data XLSX → dict SIMAN ternormalisasi; None bila kosong.

    Baris tanpa kode barang ATAU tanpa NUP dilewati (bukan baris aset —
    umumnya baris kosong/pemisah di ekspor).
    """
    d = {}
    for kunci, idx in peta_header.items():
        d[kunci] = row[idx] if idx < len(row) else None
    kode = norm_kode(d.get("kode_barang"))
    nup = norm_nup(d.get("nup"))
    if not kode or not nup:
        return None
    out = {
        "kode_barang": kode,
        "nup": nup,
        "kode_register": norm_teks(d.get("kode_register")),
        "nama_barang": norm_teks(d.get("nama_barang")),
        "merk": norm_teks(d.get("merk")),
        "tipe": norm_teks(d.get("tipe")),
        "kondisi": norm_teks(d.get("kondisi")),
        "status_bmn": norm_teks(d.get("status_bmn")),
        "nama_pengguna": norm_teks(d.get("nama_pengguna")),
        "lokasi_ruang": norm_teks(d.get("lokasi_ruang")),
        "status_penggunaan": norm_teks(d.get("status_penggunaan")),
        "no_psp": norm_teks(d.get("no_psp")),
        "intra_ekstra": norm_teks(d.get("intra_ekstra")),
        "umur_aset": norm_teks(d.get("umur_aset")),
        "status_idle": norm_teks(d.get("status_idle")),
        "henti_guna": norm_teks(d.get("henti_guna")),
        "kode_satker": norm_teks(d.get("kode_satker")),
        "nama_satker": norm_teks(d.get("nama_satker")),
        "tanggal_perolehan": norm_tanggal(d.get("tanggal_perolehan")),
        "tanggal_penghapusan": norm_tanggal(d.get("tanggal_penghapusan")),
        "tanggal_psp": norm_tanggal(d.get("tanggal_psp")),
        "nilai_perolehan": parse_harga(d.get("nilai_perolehan")),
        "nilai_penyusutan": parse_harga(d.get("nilai_penyusutan")),
        "nilai_buku": parse_harga(d.get("nilai_buku")),
    }
    return out


def _nilai_aman_utk(field, aset):
    return aset.get(field)


def banding_aset(aset, siman):
    """Daftar selisih field kunci antara aset AMAN dan baris SIMAN.

    Nilai SIMAN yang kosong/placeholder TIDAK dianggap selisih (AMAN boleh
    lebih kaya); nilai SIMAN yang terisi dan berbeda = selisih (SIMAN valid).
    Kembalikan list {field, label, aman, siman} (nilai tampilan apa adanya).
    """
    out = []
    for field, kunci, label, jenis in PERBANDINGAN:
        nilai_siman = siman.get(kunci)
        nilai_aman = _nilai_aman_utk(field, aset)
        if jenis == "kode":
            s, a = norm_kode(nilai_siman), norm_kode(nilai_aman)
            beda = bool(s) and s != a
            tampil_siman = norm_kode(nilai_siman)
        elif jenis == "angka":
            if nilai_siman in (None, ""):
                continue
            s_val = float(nilai_siman)
            a_val = parse_harga(nilai_aman)
            beda = abs(s_val - a_val) > 0.5
            tampil_siman = int(s_val) if s_val == int(s_val) else s_val
        elif jenis == "tanggal":
            s = norm_tanggal(nilai_siman)
            a = norm_tanggal(nilai_aman)
            beda = bool(s) and s != a
            tampil_siman = s
        elif jenis == "register":
            s = norm_teks(nilai_siman)
            a = norm_teks(nilai_aman)
            beda = bool(s) and bool(a) and s != a  # kosong = adopsi, bukan selisih
            tampil_siman = s
        else:  # teks
            if _kosong_siman(nilai_siman):
                continue
            s = norm_teks(nilai_siman)
            a = norm_teks(nilai_aman)
            beda = s.casefold() != a.casefold()
            tampil_siman = s
        if beda:
            out.append({
                "field": field, "label": label,
                "aman": "" if nilai_aman is None else str(nilai_aman),
                "siman": str(tampil_siman),
            })
    return out


def referensi_siman(siman):
    """Cuplikan nilai referensi SIMAN untuk disimpan di subdoc aset."""
    return {k: siman.get(k) for k in KUNCI_REFERENSI}


def nilai_terapkan(selisih_item):
    """Nilai yang DITULIS ke field AMAN saat 'terapkan nilai SIMAN'."""
    return str(selisih_item.get("siman") if selisih_item.get("siman")
               is not None else "")


def ringkas_import(hasil_per_aset, baris_siman_tanpa_aset, aman_tanpa_siman):
    """Ringkasan hasil impor untuk register & respons endpoint. MURNI."""
    per_field = {}
    selisih = cocok = 0
    for r in hasil_per_aset:
        if r["selisih"]:
            selisih += 1
            for s in r["selisih"]:
                per_field[s["field"]] = per_field.get(s["field"], 0) + 1
        else:
            cocok += 1
    return {
        "aset_dicek": len(hasil_per_aset),
        "cocok": cocok,
        "selisih": selisih,
        "per_field": per_field,
        "siman_tanpa_aset": len(baris_siman_tanpa_aset),
        "aman_tanpa_siman": len(aman_tanpa_siman),
    }
