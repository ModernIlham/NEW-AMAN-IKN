"""Hierarki digit Segmen Akun BAS — LOGIKA MURNI (teruji unit).

Struktur kode akun 6 digit mengikuti Bagan Akun Standar (PMK 214/PMK.05/2013;
kodefikasi KEP-211/PB/2018 jo. pemutakhirannya a.l. KEP-291/PB/2022):
digit 1 = AKUN (segmen besar: 1 Aset … 8 Non-Anggaran), 2 digit pertama =
KELOMPOK AKUN (mis. 52 Belanja Barang dan Jasa), 3 digit pertama = JENIS AKUN
(mis. 521 Belanja Barang), digit 4–6 = rincian/objek.

NAMA KELOMPOK di bawah diambil VERBATIM dari lampiran resmi KEP-211/PB/2018
(workbook "Kode Akun BAS", sheet Akun Kas & Akun Akrual, entri Level 2). Untuk
segmen anggaran (5 Belanja, 6 Transfer, 7 Pembiayaan, 8 Non-Anggaran) dipakai
nama ledger KAS (Belanja/Dana) agar konsisten dengan nama baris di master
(pandangan anggaran satker); kelompok yang hanya ada di ledger AKRUAL
(mis. 59 Beban Penyesuaian, 69 Beban Transfer Lain-lain) memakai nama akrual.
Dua kunci legacy (32, 67) tidak ada di KEP-211 tetapi masih muncul di seed
master lama — dipertahankan agar tabel tidak kehilangan header.
"""

# kelompok akun (2 digit pertama) → nama kelompok (resmi KEP-211/PB/2018)
KELOMPOK_LABEL = {
    # 1 — Aset
    "11": "Aset Lancar",
    "12": "Investasi Jangka Panjang",
    "13": "Aset Tetap",
    "14": "Dana Cadangan",
    "15": "Piutang Jangka Panjang",
    "16": "Aset Lainnya",
    "19": "Akun Setup",
    # 2 — Kewajiban
    "21": "Kewajiban Jangka Pendek",
    "22": "Kewajiban Jangka Panjang",
    "23": "Dicadangkan untuk Komitmen Belanja",
    "29": "Akun Setup",
    # 3 — Ekuitas
    "31": "Ekuitas",
    "32": "Ekuitas Dana Investasi",  # legacy (pra-akrual, tak ada di KEP-211)
    "39": "Ekuitas",
    # 4 — Pendapatan
    "41": "Pendapatan Perpajakan",
    "42": "Pendapatan Negara Bukan Pajak (PNBP)",
    "43": "Pendapatan Hibah",
    "49": "Pendapatan Penyesuaian",
    # 5 — Belanja (nama ledger Kas)
    "51": "Belanja Pegawai",
    "52": "Belanja Barang dan Jasa",
    "53": "Belanja Modal",
    "54": "Belanja Pembayaran Kewajiban Utang",
    "55": "Belanja Subsidi",
    "56": "Belanja Hibah",
    "57": "Belanja Bantuan Sosial",
    "58": "Belanja Lain-lain",
    "59": "Beban Penyesuaian",  # akrual: penyusutan/amortisasi/penyisihan
    # 6 — Transfer ke Daerah dan Dana Desa (nama ledger Kas)
    "61": "Dana Bagi Hasil (DBH)",
    "62": "Dana Alokasi Umum (DAU)",
    "63": "Dana Alokasi Khusus Fisik (DAK Fisik)",
    "64": "Dana Otonomi Khusus, Keistimewaan DIY & Insentif Daerah",
    "65": "Dana Alokasi Khusus Non Fisik (DAK Non Fisik)",
    "66": "Dana Desa",
    "67": "Hibah kepada Daerah",  # legacy (tak ada di KEP-211)
    "69": "Beban Transfer Lain-lain",  # akrual
    # 7 — Pembiayaan
    "71": "Penerimaan Pembiayaan",
    "72": "Pengeluaran Pembiayaan",
    "79": "Pengeluaran Pembiayaan Lain-lain",
    # 8 — Non-Anggaran
    "81": "Penerimaan Non Anggaran",
    "82": "Pengeluaran Non Anggaran",
    "83": "Output Kinerja",
}


# Label tiap LEVEL digit kode akun (struktur KEP-211/PB/2018: Level 1 =
# 1 digit … Level 6 = 6 digit; istilah fungsional level 1-3 mengikuti
# literatur BAS: akun/segmen → kelompok → jenis).
LEVEL_LABEL = {
    1: "Akun/Segmen — digit 1",
    2: "Kelompok Akun — 2 digit",
    3: "Jenis Akun — 3 digit",
    4: "Level 4 — 4 digit",
    5: "Level 5 — 5 digit",
    6: "Akun Rincian — 6 digit",
}


def jalur_digit(kode, hierarki, nama_sendiri="") -> list:
    """Jalur makna tiap pola digit sebuah kode akun 6 digit. MURNI.

    Kembalikan [{level, kode, label, uraian}] utk level 1..6 — uraian dari
    peta `hierarki` (kode ≤5 digit → nama resmi KEP-211); level 6 memakai
    `nama_sendiri` (nama akun master), fallback peta. Level tanpa nama resmi
    tetap muncul dengan uraian kosong agar strukturnya terlihat utuh."""
    k = str(kode or "").strip()
    peta = hierarki or {}
    out = []
    for n in range(1, min(len(k), 6) + 1):
        pref = k[:n]
        uraian = (str(nama_sendiri or "").strip() or peta.get(pref, "")) \
            if n == 6 else peta.get(pref, "")
        out.append({"level": n, "kode": pref,
                    "label": LEVEL_LABEL.get(n, f"Level {n}"),
                    "uraian": uraian})
    return out


def label_kelompok(kode) -> str:
    """Nama kelompok akun untuk sebuah kode (dipangkas ke 2 digit pertama);
    kelompok tak dikenal → label generik agar UI/CSV tidak pernah kosong."""
    p = str(kode or "").strip()[:2]
    return KELOMPOK_LABEL.get(p, f"Kelompok {p}" if p else "")


def baris_csv_referensi(items, label_segmen, hierarki=None) -> list:
    """Baris CSV master referensi akun + kolom hierarki digit (header dulu).

    `items` = dokumen master (kode, nama, sumber, uraian_bmn, kapitalisasi,
    kategori_neraca); `label_segmen` = peta digit-1 → nama segmen; `hierarki`
    (opsional) = peta prefiks ≤5 digit → nama resmi utk kolom Nama Jenis.
    MURNI."""
    h = hierarki or {}
    rows = [["Kode", "Nama Akun", "Akun (digit 1)", "Segmen",
             "Kelompok (2 digit)", "Nama Kelompok", "Jenis (3 digit)",
             "Nama Jenis", "Sumber", "Uraian BMN", "Kapitalisasi",
             "Kategori Neraca", "Penjelasan"]]
    for a in items or []:
        kode = str(a.get("kode") or "")
        penj = str(a.get("penjelasan") or "")
        if penj and a.get("penjelasan_warisan"):
            penj = f"[penjelasan kelompok induk] {penj}"
        rows.append([
            kode, a.get("nama") or "", kode[:1],
            (label_segmen or {}).get(kode[:1], ""),
            kode[:2], label_kelompok(kode), kode[:3], h.get(kode[:3], ""),
            a.get("sumber") or "", a.get("uraian_bmn") or "",
            a.get("kapitalisasi") or "", a.get("kategori_neraca") or "",
            penj,
        ])
    return rows
