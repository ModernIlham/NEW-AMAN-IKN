"""Hierarki digit Segmen Akun BAS — LOGIKA MURNI (teruji unit).

Struktur kode akun 6 digit mengikuti Bagan Akun Standar (PMK 214/PMK.05/2013;
kodefikasi KEP-211/PB/2018 jo. pemutakhirannya a.l. KEP-291/PB/2022):
digit 1 = AKUN (segmen besar: 1 Aset … 8 Non-Anggaran), 2 digit pertama =
KELOMPOK AKUN (mis. 52 Belanja Barang dan Jasa), 3 digit pertama = JENIS AKUN
(mis. 521 Belanja Barang), digit 4–6 = rincian/objek. Label kelompok di bawah
diverifikasi silang terhadap isi referensi resmi SAKTI/SPAN yang menjadi seed
master (`data/referensi_akun_bas.json`).
"""

# kelompok akun (2 digit pertama) → nama kelompok
KELOMPOK_LABEL = {
    # 1 — Aset
    "11": "Aset Lancar",
    "12": "Investasi Jangka Panjang",
    "13": "Aset Tetap",
    "14": "Dana Cadangan",
    "15": "Piutang Jangka Panjang",
    "16": "Aset Lainnya",
    "19": "Aset Lainnya Khusus BUN",
    # 2 — Kewajiban
    "21": "Kewajiban Jangka Pendek",
    "22": "Kewajiban Jangka Panjang",
    "23": "Kewajiban Dicadangkan (Komitmen Belanja)",
    "29": "Kewajiban Akrual Khusus (SPAN)",
    # 3 — Ekuitas
    "31": "Ekuitas Dana Lancar & Transaksi Antar Entitas",
    "32": "Ekuitas Dana Investasi",
    "39": "Ekuitas (Akrual & Konsolidasi)",
    # 4 — Pendapatan
    "41": "Pendapatan Perpajakan",
    "42": "Pendapatan Negara Bukan Pajak (PNBP)",
    "43": "Pendapatan Hibah",
    "49": "Pendapatan Lainnya & Akun Penyesuaian",
    # 5 — Belanja
    "51": "Belanja Pegawai",
    "52": "Belanja Barang dan Jasa",
    "53": "Belanja Modal",
    "54": "Belanja Pembayaran Kewajiban Utang",
    "55": "Belanja Subsidi",
    "56": "Belanja Hibah",
    "57": "Belanja Bantuan Sosial",
    "58": "Belanja Lain-lain",
    "59": "Beban Non-Kas (Penyusutan/Amortisasi/Penyisihan/Ekstrakomptabel)",
    # 6 — Transfer
    "61": "Transfer Dana Bagi Hasil (DBH)",
    "62": "Transfer Dana Alokasi Umum (DAU)",
    "63": "Transfer Dana Alokasi Khusus (DAK)",
    "64": "Transfer Otonomi Khusus, Keistimewaan & Insentif",
    "65": "Transfer Dana Insentif, TPG & Dana Desa",
    "66": "Transfer Dana Desa & Keistimewaan",
    "67": "Transfer Hibah kepada Daerah",
    "69": "Akun Penyesuaian Transfer",
    # 7 — Pembiayaan
    "71": "Penerimaan Pembiayaan",
    "72": "Pengeluaran Pembiayaan",
    "79": "Akun Penyesuaian Pembiayaan",
    # 8 — Non-Anggaran
    "81": "Penerimaan Non-Anggaran (PFK, Kiriman Uang, UP)",
    "82": "Pengeluaran Non-Anggaran",
    "83": "Output Kinerja",
}


def label_kelompok(kode) -> str:
    """Nama kelompok akun untuk sebuah kode (dipangkas ke 2 digit pertama);
    kelompok tak dikenal → label generik agar UI/CSV tidak pernah kosong."""
    p = str(kode or "").strip()[:2]
    return KELOMPOK_LABEL.get(p, f"Kelompok {p}" if p else "")


def baris_csv_referensi(items, label_segmen) -> list:
    """Baris CSV master referensi akun + kolom hierarki digit (header dulu).

    `items` = dokumen master (kode, nama, sumber, uraian_bmn, kapitalisasi,
    kategori_neraca); `label_segmen` = peta digit-1 → nama segmen. MURNI.
    """
    rows = [["Kode", "Nama Akun", "Akun (digit 1)", "Segmen",
             "Kelompok (2 digit)", "Nama Kelompok", "Jenis (3 digit)",
             "Sumber", "Uraian BMN", "Kapitalisasi", "Kategori Neraca"]]
    for a in items or []:
        kode = str(a.get("kode") or "")
        rows.append([
            kode, a.get("nama") or "", kode[:1],
            (label_segmen or {}).get(kode[:1], ""),
            kode[:2], label_kelompok(kode), kode[:3],
            a.get("sumber") or "", a.get("uraian_bmn") or "",
            a.get("kapitalisasi") or "", a.get("kategori_neraca") or "",
        ])
    return rows
