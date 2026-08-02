"""Referensi KODE TRANSAKSI PERSEDIAAN selaras SAKTI — LOGIKA MURNI.

Daftar lengkap 45 kode transaksi Modul Persediaan SAKTI (M = masuk,
K = keluar, P = opname, H = penghapusan definitif) sebagaimana daftar
transaksi resmi aplikasi (mandat pemilik, 2026-08; selaras pustaka §3.2).
Registry ini SATU-SATUNYA sumber kebenaran kode ↔ uraian ↔ arah — dropdown
transaksi, Daftar Transaksi, ekspor CSV, dan laporan membacanya dari sini.

PENTING — sejarah ketidakselarasan: kode "warisan aplikasi" lama memakai
M06/M07/M99/K06/K07 untuk makna yang BERBEDA dari SAKTI (mis. M06 dulu
"Reklasifikasi Masuk", padahal SAKTI M06 = "Perolehan Lainnya"). Pemetaan
kunci internal → kode di sini sudah DIKOREKSI ke makna SAKTI; baris jurnal
lama yang telanjur menyimpan kode warisan diterjemahkan lewat
`kode_sakti_dari_jenis` (kunci `jenis`-nya stabil, kodenya diturunkan
ulang) — jangan pernah mempercayai field `kode_sakti` tersimpan begitu
saja untuk baris sebelum koreksi ini.

Arah:
  masuk / keluar  → menggeser KUANTITAS & nilai stok (jalur FIFO biasa)
  nilai           → hanya menggeser NILAI (kuantitas tetap) — M97/M98/K97/K98
  opname          → arah mengikuti selisih fisik vs buku (P01)
  hapus           → penghapusan DEFINITIF dari daftar usang/rusak/tak
                    dikuasai ber-SK (H01-H03); stok sudah keluar saat
                    K04/K05/K09 dicatat, jadi tak menggeser stok lagi
Kelompok dipakai untuk mengelompokkan dropdown & Daftar Transaksi.
"""

# kode → (uraian resmi, arah, kelompok)
KODE_TRANSAKSI_PERSEDIAAN = {
    # ── Masuk: perolehan ──
    "M01": ("Saldo Awal", "masuk", "perolehan"),
    "M02": ("Pembelian", "masuk", "perolehan"),
    "M03": ("Transfer Masuk", "masuk", "perolehan"),
    "M04": ("Hibah (Masuk)", "masuk", "perolehan"),
    "M05": ("Rampasan", "masuk", "perolehan"),
    "M06": ("Perolehan Lainnya", "masuk", "perolehan"),
    "M12": ("Hibah Masuk BLU", "masuk", "perolehan"),
    "M13": ("Transfer Masuk Online", "masuk", "perolehan"),
    "M14": ("Transfer Masuk Likuidasi UAKPB", "masuk", "perolehan"),
    "M15": ("Persediaan Dalam Proses Masuk", "masuk", "perolehan"),
    # ── Masuk: internal/organisasi ──
    "M07": ("Internal Transfer Masuk", "masuk", "internal"),
    "M08": ("Non Aktif UAPKPB Masuk", "masuk", "internal"),
    # ── Masuk: reklasifikasi ──
    "M10": ("Reklasifikasi Masuk", "masuk", "reklasifikasi"),
    "M11": ("Reklasifikasi Dari Aset", "masuk", "reklasifikasi"),
    # ── Masuk: koreksi ──
    "M09": ("Koreksi Hasil Migrasi", "masuk", "koreksi"),
    "M90": ("Koreksi Penyesuaian Tambah", "masuk", "koreksi"),
    "M95": ("Koreksi Transfer Keluar Online", "masuk", "koreksi"),
    "M96": ("Koreksi Tambah: FIFO ke HST", "masuk", "koreksi"),
    "M99": ("Koreksi Kuantitas Tambah", "masuk", "koreksi"),
    # ── Masuk: koreksi NILAI (kuantitas tetap) ──
    "M97": ("Koreksi Nilai Tambah (Opsik)", "nilai", "koreksi_nilai"),
    "M98": ("Koreksi Nilai Tambah", "nilai", "koreksi_nilai"),
    # ── Masuk: pembatalan tak dikuasai ──
    "M94": ("Batal Catat Persediaan Tak Dikuasai", "masuk", "tidak_dikuasai"),
    # ── Keluar: penyaluran/pemakaian ──
    "K01": ("Habis Pakai", "keluar", "penyaluran"),
    "K02": ("Transfer Keluar", "keluar", "penyaluran"),
    "K03": ("Hibah Keluar", "keluar", "penyaluran"),
    "K06": ("Keluar Lainnya", "keluar", "penyaluran"),
    "K13": ("Transfer Keluar Online", "keluar", "penyaluran"),
    "K14": ("Transfer Keluar Likuidasi UAKPB", "keluar", "penyaluran"),
    "K15": ("Persediaan Dalam Proses Keluar", "keluar", "penyaluran"),
    # ── Keluar: internal/organisasi ──
    "K07": ("Internal Transfer Keluar", "keluar", "internal"),
    "K08": ("Non Aktif UAPKPB Keluar", "keluar", "internal"),
    # ── Keluar: kondisi (masuk daftar usang/rusak — bahan CaLK) ──
    "K04": ("Usang", "keluar", "kondisi"),
    "K05": ("Rusak", "keluar", "kondisi"),
    # ── Keluar: reklasifikasi ──
    "K10": ("Reklasifikasi Keluar", "keluar", "reklasifikasi"),
    "K11": ("Reklasifikasi Aset", "keluar", "reklasifikasi"),
    # ── Keluar: koreksi ──
    "K90": ("Koreksi Penyesuaian Kurang", "keluar", "koreksi"),
    "K96": ("Koreksi Kurang: FIFO ke HST", "keluar", "koreksi"),
    "K99": ("Koreksi Kuantitas Kurang", "keluar", "koreksi"),
    # ── Keluar: koreksi NILAI (kuantitas tetap) ──
    "K97": ("Koreksi Nilai Kurang (Opsik)", "nilai", "koreksi_nilai"),
    "K98": ("Koreksi Nilai Kurang", "nilai", "koreksi_nilai"),
    # ── Keluar: pencatatan tak dikuasai ──
    "K09": ("Catat Persediaan Tak Dikuasai", "keluar", "tidak_dikuasai"),
    # ── Opname ──
    "P01": ("Hasil Opname Fisik", "opname", "opname"),
    # ── Penghapusan definitif ber-SK (dari daftar, bukan dari stok) ──
    "H01": ("Hapus Usang", "hapus", "hapus"),
    "H02": ("Hapus Rusak", "hapus", "hapus"),
    "H03": ("Hapus Persediaan Tak Dikuasai", "hapus", "tidak_dikuasai"),
}

LABEL_KELOMPOK = {
    "perolehan": "Perolehan",
    "penyaluran": "Penyaluran & Pemakaian",
    "internal": "Internal / Antar-UAPKPB",
    "reklasifikasi": "Reklasifikasi",
    "koreksi": "Koreksi Kuantitas",
    "koreksi_nilai": "Koreksi Nilai (kuantitas tetap)",
    "kondisi": "Kondisi (Usang/Rusak)",
    "tidak_dikuasai": "Persediaan Tidak Dikuasai",
    "opname": "Opname Fisik",
    "hapus": "Penghapusan Definitif (ber-SK)",
}

# Kunci `jenis` internal (stabil — tersimpan di baris jurnal lama) → kode
# SAKTI yang BENAR. Lima kunci pertama bagian atas dikoreksi dari kode
# warisan yang salah makna (lihat docstring modul).
JENIS_KE_KODE = {
    # koreksi makna (kode warisan lama di komentar)
    "reklasifikasi_masuk": "M10",       # dulu M06
    "reklasifikasi_dari_aset": "M11",   # dulu M07
    "perolehan_lainnya": "M06",         # dulu M99
    "penghapusan_lainnya": "K06",       # label lama "Penghapusan Lainnya"
    "reklasifikasi_keluar": "K10",      # dulu K07
    # sudah selaras sejak awal
    "saldo_awal": "M01",
    "pembelian": "M02",
    "transfer_masuk": "M03",
    "hibah_masuk": "M04",
    "rampasan": "M05",
    "habis_pakai": "K01",
    "transfer_keluar": "K02",
    "hibah_keluar": "K03",
    "usang": "K04",
    "rusak": "K05",
    # jenis baru (mandat 45 kode)
    "internal_transfer_masuk": "M07",
    "non_aktif_uapkpb_masuk": "M08",
    "koreksi_hasil_migrasi": "M09",
    "hibah_masuk_blu": "M12",
    "transfer_masuk_online": "M13",
    "transfer_masuk_likuidasi": "M14",
    "dalam_proses_masuk": "M15",
    "koreksi_penyesuaian_tambah": "M90",
    "batal_catat_tak_dikuasai": "M94",
    "koreksi_transfer_keluar_online": "M95",
    "koreksi_tambah_fifo_hst": "M96",
    "koreksi_kuantitas_tambah": "M99",
    "internal_transfer_keluar": "K07",
    "non_aktif_uapkpb_keluar": "K08",
    "catat_tak_dikuasai": "K09",
    "reklasifikasi_ke_aset": "K11",
    "transfer_keluar_online": "K13",
    "transfer_keluar_likuidasi": "K14",
    "dalam_proses_keluar": "K15",
    "koreksi_penyesuaian_kurang": "K90",
    "koreksi_kurang_fifo_hst": "K96",
    "koreksi_kuantitas_kurang": "K99",
    "opname": "P01",
    "hapus_usang": "H01",
    "hapus_rusak": "H02",
    "hapus_tak_dikuasai": "H03",
}


def kode_sakti_dari_jenis(jenis, kode_tersimpan="") -> str:
    """Kode SAKTI yang benar untuk satu baris jurnal.

    Kunci `jenis` adalah identitas yang STABIL antar-versi; field
    `kode_sakti` tersimpan bisa berisi kode warisan bermakna lain
    (M06/M07/M99/K06/K07 lama) atau "OPN" (opname pra-P01) — maka kode
    selalu diturunkan ulang dari `jenis`. Baris tanpa jenis terdaftar
    (mis. `pindah_gudang` yang memang internal non-SAKTI) memakai kode
    tersimpannya apa adanya ("" bila kosong).
    """
    kode = JENIS_KE_KODE.get(str(jenis or "").strip())
    if kode:
        return kode
    tersimpan = str(kode_tersimpan or "").strip()
    return "" if tersimpan == "OPN" else tersimpan


def info_kode(kode) -> dict:
    """{kode, uraian, arah, kelompok, label_kelompok} — {} bila tak dikenal."""
    k = str(kode or "").strip().upper()
    ent = KODE_TRANSAKSI_PERSEDIAAN.get(k)
    if not ent:
        return {}
    uraian, arah, kelompok = ent
    return {"kode": k, "uraian": uraian, "arah": arah, "kelompok": kelompok,
            "label_kelompok": LABEL_KELOMPOK.get(kelompok, kelompok)}


def daftar_kode_transaksi() -> list:
    """Seluruh registry sebagai daftar terurut (M → K → P → H, lalu angka)
    untuk layar referensi Daftar Transaksi."""
    urutan_huruf = {"M": 0, "K": 1, "P": 2, "H": 3}
    kode_terurut = sorted(
        KODE_TRANSAKSI_PERSEDIAAN,
        key=lambda k: (urutan_huruf.get(k[0], 9), k[1:]))
    return [info_kode(k) for k in kode_terurut]
