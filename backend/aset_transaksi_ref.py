"""Referensi KODE TRANSAKSI MUTASI ASET TETAP selaras SIMAK/SAKTI — LOGIKA MURNI.

Daftar lengkap 99 kode transaksi mutasi BMN aset tetap sebagaimana daftar
resmi aplikasi (mandat pemilik, 2026-08-09): 53 kode MUTASI BERTAMBAH dan
46 kode MUTASI BERKURANG. Registry ini SATU-SATUNYA sumber kebenaran
kode ↔ uraian ↔ arah untuk aset tetap — layar Referensi Kode Mutasi,
pencatatan mutasi_bmn, dan laporan membacanya dari sini (kembaran
`persediaan_transaksi_ref.py` untuk sisi persediaan).

Arah:
  bertambah → menambah kuantitas/nilai daftar aset (perolehan, reklas
              masuk, pengembangan, koreksi tambah, pembatalan pencatatan
              keluar, dsb.)
  berkurang → mengurangi kuantitas/nilai daftar aset (penghapusan,
              transfer/hibah keluar, reklas keluar, penyusutan, koreksi
              kurang, pencatatan hilang/usang, dsb.)

Kelompok dipakai untuk mengelompokkan layar referensi & laporan mutasi;
prefiks kode SIMAK sendiri sudah bermakna (1xx perolehan/reklas definitif,
2xx perubahan nilai, 3xx pengurangan, 4xx penggunaan/henti guna,
5xx KDP, 6xx barang bersejarah, 7xx barang pihak ketiga, 8xx BPYBDS,
9xx pencatatan khusus/penyusutan/ATR, Qxx koreksi penyusutan).
"""

# kode → (uraian resmi, arah, kelompok)
KODE_MUTASI_ASET = {
    # ── Bertambah: perolehan definitif ──
    "100": ("Saldo Awal", "bertambah", "perolehan"),
    "101": ("Pembelian", "bertambah", "perolehan"),
    "102": ("Transfer Masuk", "bertambah", "perolehan"),
    "103": ("Hibah Masuk", "bertambah", "perolehan"),
    "104": ("Rampasan", "bertambah", "perolehan"),
    "105": ("Penyelesaian Pembangunan Dengan KDP", "bertambah", "perolehan"),
    "112": ("Perolehan Lainnya", "bertambah", "perolehan"),
    "113": ("Penyelesaian Pembangunan Langsung", "bertambah", "perolehan"),
    "135": ("Perolehan Migrasi SIMAK", "bertambah", "perolehan"),
    "192": ("Transfer Masuk (Henti Guna)", "bertambah", "henti_guna"),
    # ── Bertambah: pembatalan/pengembalian pencatatan ──
    "106": ("Pembatalan Penghapusan", "bertambah", "pembatalan"),
    "193": ("Batal Transfer Keluar", "bertambah", "pembatalan"),
    "902": ("Pembatalan Pencatatan Barang Hilang", "bertambah", "pembatalan"),
    "912": ("Pencatatan Pembatalan Barang Yang Mau Dihapuskan", "bertambah", "pembatalan"),
    "942": ("Pembatalan Pencatatan Barang Usang", "bertambah", "pembatalan"),
    # ── Bertambah: reklasifikasi masuk ──
    "107": ("Reklasifikasi Masuk", "bertambah", "reklasifikasi"),
    "115": ("Reklasifikasi Masuk dari Persediaan", "bertambah", "reklasifikasi"),
    "121": ("Reklasifikasi Masuk (IP)", "bertambah", "reklasifikasi"),
    "157": ("Reklasifikasi Dari Aset Kemitraan ke Aset Tetap", "bertambah", "reklasifikasi"),
    "177": ("Reklasifikasi Dari Aset Lainnya ke Aset Tetap", "bertambah", "reklasifikasi"),
    # ── Bertambah: likuidasi masuk ──
    "131": ("Likuidasi Masuk", "bertambah", "likuidasi"),
    "132": ("Likuidasi Masuk Henti Guna", "bertambah", "likuidasi"),
    "133": ("Likuidasi Masuk Usul Hapus", "bertambah", "likuidasi"),
    "134": ("Likuidasi Masuk Asset Kemitraan", "bertambah", "likuidasi"),
    # ── Bertambah: pengembangan & koreksi nilai ──
    "202": ("Pengembangan Nilai Aset (Langsung)", "bertambah", "pengembangan"),
    "208": ("Pengembangan Melalui KDP", "bertambah", "pengembangan"),
    "204": ("Koreksi Pencatatan Nilai Bertambah", "bertambah", "koreksi"),
    "232": ("KOREKSI TM (TAB)", "bertambah", "koreksi"),
    "240": ("KOREKSI RM (TAB)", "bertambah", "koreksi"),
    "305": ("Koreksi Pencatatan", "bertambah", "koreksi"),
    "933": ("Koreksi Masa Manfaat", "bertambah", "koreksi"),
    # ── Bertambah: penggunaan kembali & kemitraan ──
    "402": ("Penggunaan kembali BMN yang sudah dihentikan penggunaan aktif", "bertambah", "henti_guna"),
    "412": ("Perubahan Aset Kemitraan ke BMN", "bertambah", "kemitraan"),
    # ── Bertambah: KDP ──
    "501": ("Saldo Awal KDP", "bertambah", "kdp"),
    "502": ("Perolehan/Penambahan KDP", "bertambah", "kdp"),
    "503": ("Pengembangan KDP", "bertambah", "kdp"),
    "504": ("Koreksi Nilai KDP Bertambah", "bertambah", "kdp"),
    "506": ("Transfer Masuk KDP", "bertambah", "kdp"),
    "508": ("Hibah Masuk KDP", "bertambah", "kdp"),
    "510": ("Perolehan Lainnya KDP", "bertambah", "kdp"),
    "514": ("Reklasifikasi Masuk KDP", "bertambah", "kdp"),
    "596": ("Batal Transfer Keluar KDP", "bertambah", "kdp"),
    # ── Bertambah: barang bersejarah ──
    "602": ("Perolehan Barang Bersejarah", "bertambah", "bersejarah"),
    "609": ("Likuidasi Sejarah Masuk", "bertambah", "bersejarah"),
    # ── Bertambah: barang pihak ketiga ──
    "701": ("Perolehan Barang Pihak Ketiga", "bertambah", "pihak_ketiga"),
    "704": ("Likuidasi Masuk Pihak Ketiga", "bertambah", "pihak_ketiga"),
    # ── Bertambah: BPYBDS ──
    "801": ("Perolehan BPYBDS Dari Reklasifikasi BMN ke BPYBDS", "bertambah", "bpybds"),
    "803": ("Pencatatan Pembatalan BPYBDS", "bertambah", "bpybds"),
    # ── Bertambah: Aset Tetap Renovasi ──
    "951": ("Saldo Awal Aset Tetap Renovasi", "bertambah", "atr"),
    "952": ("Pembelian Aset Tetap Renovasi", "bertambah", "atr"),
    "953": ("Penyelesaian Langsung Aset Tetap Renovasi", "bertambah", "atr"),
    "954": ("Penyelesaian Dengan KDP Aset Tetap Renovasi", "bertambah", "atr"),
    "955": ("Perolehan Lainnya Aset Tetap Renovasi", "bertambah", "atr"),

    # ── Berkurang: reklasifikasi keluar ──
    "158": ("Reklasifikasi Dari Aset Tetap ke Aset Kemitraan", "berkurang", "reklasifikasi"),
    "169": ("Perolehan Reklasifikasi Dari Intra ke Ekstra", "berkurang", "reklasifikasi"),
    "188": ("Reklasifikasi Dari Aset Tetap ke Aset Lainnya", "berkurang", "reklasifikasi"),
    "304": ("Reklasifikasi Keluar", "berkurang", "reklasifikasi"),
    "315": ("Reklasifikasi Keluar ke Persediaan", "berkurang", "reklasifikasi"),
    "321": ("Reklasifikasi Keluar (IP)", "berkurang", "reklasifikasi"),
    # ── Berkurang: koreksi nilai ──
    "264": ("Koreksi Pencatatan Nilai Berkurang", "berkurang", "koreksi"),
    "267": ("Koreksi Nilai Revaluasi Berkurang", "berkurang", "koreksi"),
    # ── Berkurang: penghapusan & pemindahtanganan ──
    "301": ("Penghapusan", "berkurang", "penghapusan"),
    "302": ("Transfer Keluar", "berkurang", "penghapusan"),
    "303": ("Hibah Keluar", "berkurang", "penghapusan"),
    "307": ("Reklasifikasi BMN ke BPYBDS", "berkurang", "bpybds"),
    # ── Berkurang: usulan ke Pengelola ──
    "308": ("Usulan Barang Hilang ke Pengelola", "berkurang", "usulan"),
    "309": ("Usulan Barang Hibah DK/TP", "berkurang", "usulan"),
    # ── Berkurang: likuidasi keluar ──
    "311": ("Likuidasi Keluar", "berkurang", "likuidasi"),
    "312": ("Likuidasi Keluar Henti Guna", "berkurang", "likuidasi"),
    "314": ("Likuidasi Keluar Asset Kemitraan", "berkurang", "likuidasi"),
    # ── Berkurang: BMN yang dihentikan penggunaannya ──
    "391": ("Penghapusan (BMN Yang Dihentikan)", "berkurang", "henti_guna"),
    "392": ("Transfer Keluar (BMN Yang Dihentikan)", "berkurang", "henti_guna"),
    "393": ("Hibah Keluar (BMN Yang Dihentikan)", "berkurang", "henti_guna"),
    "394": ("Reklasifikasi Keluar (BMN Yang Dihentikan)", "berkurang", "henti_guna"),
    "396": ("Usulan Rusak Berat ke Pengelola (BMN yang dihentikan)", "berkurang", "henti_guna"),
    "397": ("Reklasifikasi BMN ke BPYBDS (BMN Yang Dihentikan)", "berkurang", "henti_guna"),
    "401": ("Penghentian Aset Dari Penggunaan", "berkurang", "henti_guna"),
    # ── Berkurang: kemitraan ──
    "411": ("Perubahan BMN ke Aset Kemitraan", "berkurang", "kemitraan"),
    # ── Berkurang: KDP ──
    "505": ("Penghapusan/Penghentian KDP", "berkurang", "kdp"),
    "507": ("Transfer Keluar KDP", "berkurang", "kdp"),
    "509": ("Hibah Keluar KDP", "berkurang", "kdp"),
    "513": ("Reklasifikasi Keluar KDP", "berkurang", "kdp"),
    "515": ("Likuidasi KDP Keluar", "berkurang", "kdp"),
    "564": ("Koreksi Nilai KDP Berkurang", "berkurang", "kdp"),
    # ── Berkurang: barang bersejarah ──
    "604": ("Penghapusan Barang Bersejarah", "berkurang", "bersejarah"),
    "608": ("Likuidasi Sejarah Keluar", "berkurang", "bersejarah"),
    # ── Berkurang: barang pihak ketiga ──
    "702": ("Penghapusan Barang Pihak Ketiga", "berkurang", "pihak_ketiga"),
    "703": ("Likuidasi Keluar Pihak Ketiga", "berkurang", "pihak_ketiga"),
    # ── Berkurang: BPYBDS ──
    "802": ("Penghapusan BPYBDS", "berkurang", "bpybds"),
    # ── Berkurang: pencatatan hilang/usul hapus/usang ──
    "901": ("Pencatatan Barang Hilang", "berkurang", "hilang_usang"),
    "911": ("Pencatatan Barang Yang Mau Dihapuskan", "berkurang", "hilang_usang"),
    "941": ("Pencatatan Barang Usang", "berkurang", "hilang_usang"),
    # ── Berkurang: internal ──
    "921": ("Internal Transfer Keluar", "berkurang", "internal"),
    # ── Berkurang: penyusutan & koreksinya ──
    "931": ("Penyusutan Aset Tetap", "berkurang", "penyusutan"),
    "Q13": ("Koreksi Penyusutan Semester 1 2013", "berkurang", "penyusutan"),
    "Q14": ("Koreksi Penyusutan Semester 1 2014", "berkurang", "penyusutan"),
    "Q23": ("Koreksi Penyusutan Semester 2 2013", "berkurang", "penyusutan"),
    "Q24": ("Koreksi Penyusutan Semester 2 2014", "berkurang", "penyusutan"),
    "Q34": ("Koreksi Penyusutan Minus", "berkurang", "penyusutan"),
}

# Kode WARISAN AMAN di luar daftar resmi 99 — dipertahankan supaya baris
# jurnal lama tetap terbaca dan penulis yang ada tidak berubah makna:
#   205 — "Koreksi Nilai Berkurang": dipakai luas sejak Gelombang 7 (edit
#         harga turun, revaluasi turun, terapan selisih SIMAN); padanan
#         resminya 264, tetapi baris tersimpan memakai 205 sehingga kode
#         ini tetap sah (jangan migrasi data historis diam-diam).
#   203 — "Perubahan Kondisi" (netral): tak pernah ditulis modul mana pun,
#         dipertahankan hanya agar kontrak validasi lama tidak menyempit.
KODE_WARISAN_AMAN = {
    "203": ("Perubahan Kondisi", "netral", "koreksi"),
    "205": ("Koreksi Nilai Berkurang", "berkurang", "koreksi"),
}


def semua_kode_bmn() -> dict:
    """Registry resmi 99 kode + warisan AMAN — dasar VALIDASI & pengayaan
    jurnal (layar referensi memakai daftar resmi saja + bagian warisan)."""
    return {**KODE_WARISAN_AMAN, **KODE_MUTASI_ASET}


LABEL_KELOMPOK_ASET = {
    "perolehan": "Perolehan",
    "pengembangan": "Pengembangan & Kapitalisasi",
    "reklasifikasi": "Reklasifikasi",
    "koreksi": "Koreksi Pencatatan & Nilai",
    "pembatalan": "Pembatalan Pencatatan",
    "likuidasi": "Likuidasi",
    "penghapusan": "Penghapusan & Pemindahtanganan",
    "usulan": "Usulan ke Pengelola",
    "henti_guna": "BMN Dihentikan dari Penggunaan",
    "kemitraan": "Aset Kemitraan",
    "kdp": "Konstruksi Dalam Pengerjaan (KDP)",
    "bersejarah": "Barang Bersejarah",
    "pihak_ketiga": "Barang Pihak Ketiga",
    "bpybds": "BPYBDS",
    "hilang_usang": "Barang Hilang / Usul Hapus / Usang",
    "internal": "Internal",
    "penyusutan": "Penyusutan & Koreksinya",
    "atr": "Aset Tetap Renovasi",
}


def info_kode_aset(kode) -> dict:
    """{kode, uraian, arah, kelompok, label_kelompok} — {} bila tak dikenal."""
    k = str(kode or "").strip().upper()
    ent = KODE_MUTASI_ASET.get(k)
    if not ent:
        return {}
    uraian, arah, kelompok = ent
    return {"kode": k, "uraian": uraian, "arah": arah, "kelompok": kelompok,
            "label_kelompok": LABEL_KELOMPOK_ASET.get(kelompok, kelompok)}


def daftar_kode_mutasi_aset() -> list:
    """Seluruh registry terurut: bertambah dulu lalu berkurang, di dalamnya
    urut kode (angka dulu, Qxx paling akhir) — untuk layar referensi."""
    def kunci(k):
        ent = KODE_MUTASI_ASET[k]
        urutan_arah = 0 if ent[1] == "bertambah" else 1
        return (urutan_arah, k[0].isalpha(), k)
    return [info_kode_aset(k) for k in sorted(KODE_MUTASI_ASET, key=kunci)]
