"""Laporan Barang Pengguna (LBP) — LOGIKA MURNI (W8).

Format mengikuti dokumen resmi "LBP Otorita Ibu Kota Nusantara Tahun 2025
Audited" yang dipelajari mendalam (1.032 paragraf + 61 tabel):

  SAMPUL → KATA PENGANTAR → DAFTAR ISI → I. OVERVIEW (gambaran umum, dasar
  hukum, ruang lingkup, kebijakan umum, kebijakan akuntansi signifikan,
  nilai BMN) → II. LAPORAN BARANG PENGGUNA (posisi neraca, persediaan,
  intra/ekstra/gabungan per golongan, KDP, ATB, penyusutan) → III. CATATAN
  ATAS LAPORAN BMN (ringkasan mutasi per golongan: saldo awal + tambah −
  kurang = akhir, dipecah Gabungan/Intra/Ekstra; posisi per akun neraca;
  akumulasi penyusutan per akun; perbandingan Laporan Barang vs Laporan
  Keuangan; informasi BMN lainnya; tindak lanjut pemeriksaan) → LAMPIRAN →
  ttd Kuasa Pengguna Barang.

Angka dirakit dari mesin laporan yang SUDAH ada (pembukuan_utils
build_dbkp_rows/build_lbkp_rows/posisi_neraca, penilaian_utils
rekap_penyusutan, akun_bas_utils, persediaan) — file ini hanya menyusun
BENTUK: baris tabel, narasi baku, dan terbilang. Semua fungsi murni.
"""
from akun_bas_utils import AKUN_NERACA_DEFAULT
from pelaporan_utils import terbilang_id

# Nama akun akumulasi penyusutan per golongan aset tetap (BAS 137xxx) +
# akumulasi ATB (169xxx) — dipakai tabel akumulasi & perbandingan LB-LK.
AKUN_AKUMULASI = {
    "3": ("137111", "Akumulasi Penyusutan Peralatan dan Mesin"),
    "4": ("137211", "Akumulasi Penyusutan Gedung dan Bangunan"),
    "5": ("137311", "Akumulasi Penyusutan Jalan, Irigasi dan Jaringan"),
    "6": ("137411", "Akumulasi Penyusutan Aset Tetap Lainnya"),
    "8": ("169315", "Akumulasi Amortisasi Aset Tak Berwujud"),
}

# Dasar hukum baku LBP (umum lintas satker — bukan yang spesifik OIKN).
DASAR_HUKUM_LBP = [
    "Undang-Undang Nomor 17 Tahun 2003 tentang Keuangan Negara",
    "Undang-Undang Nomor 1 Tahun 2004 tentang Perbendaharaan Negara",
    "Peraturan Pemerintah Nomor 71 Tahun 2010 tentang Standar Akuntansi "
    "Pemerintahan",
    "Peraturan Pemerintah Nomor 27 Tahun 2014 tentang Pengelolaan Barang "
    "Milik Negara/Daerah sebagaimana diubah dengan PP Nomor 28 Tahun 2020",
    "PMK Nomor 214/PMK.05/2013 tentang Bagan Akun Standar",
    "PMK Nomor 181/PMK.06/2016 tentang Penatausahaan Barang Milik Negara",
    "PMK Nomor 65/PMK.06/2017 tentang Penyusutan Barang Milik Negara "
    "Berupa Aset Tetap Pada Entitas Pemerintah Pusat",
    "PMK Nomor 118/PMK.06/2018 tentang Tata Cara Rekonsiliasi Barang "
    "Milik Negara Dalam Rangka Penyusunan Laporan Keuangan Pemerintah "
    "Pusat",
    "PMK Nomor 207/PMK.06/2021 tentang Tata Cara Pelaksanaan Pengawasan "
    "dan Pengendalian Barang Milik Negara",
    "PMK Nomor 40 Tahun 2024 tentang Tata Cara Penggunaan Barang Milik "
    "Negara",
    "KMK Nomor 29/PMK.6/2010 tentang Penggolongan dan Kodefikasi Barang "
    "Milik Negara beserta perubahannya",
    "KMK Nomor 295/KMK.06/2019 tentang Tabel Masa Manfaat Dalam Rangka "
    "Penyusutan Barang Milik Negara berupa Aset Tetap",
]

# Upaya peningkatan kualitas LBP (butir baku dari format resmi).
UPAYA_PERBAIKAN_LBP = [
    "Meningkatkan kualitas pengelolaan dan keandalan penyajian aset "
    "dengan melakukan penertiban aset yang meliputi utilisasi, "
    "optimalisasi, dan legalitas aset yang dikuasai;",
    "Memanfaatkan aplikasi penatausahaan BMN untuk memantau validitas "
    "data laporan barang;",
    "Melakukan telaah Laporan Barang Pengguna secara berkala;",
    "Menindaklanjuti hasil temuan pemeriksaan dengan rencana aksi sesuai "
    "rekomendasi Laporan Hasil Pemeriksaan (LHP); dan",
    "Mengoptimalkan peran Aparat Pengawas Intern Pemerintah (APIP) dalam "
    "menjaga keandalan penyajian laporan.",
]


def fmt_rp(n) -> str:
    """Angka → '1.234.567' (kurung utk negatif, '0' utk nol/None)."""
    try:
        v = float(n or 0)
    except (TypeError, ValueError):
        v = 0.0
    neg = v < 0
    s = f"{abs(v):,.0f}".replace(",", ".")
    return f"({s})" if neg else s


def rupiah_terbilang(n) -> str:
    """'Rp1.234,00 (seribu dua ratus tiga puluh empat rupiah)'."""
    try:
        v = int(round(float(n or 0)))
    except (TypeError, ValueError):
        v = 0
    if v < 0:
        return f"minus Rp{fmt_rp(-v)},00 ({terbilang_id(-v)} rupiah)"
    return f"Rp{fmt_rp(v)},00 ({terbilang_id(v)} rupiah)"


def label_periode_lbp(tahun, semester=None) -> str:
    """'Tahun 2026' / 'Semester I Tahun 2026' — judul periode LBP."""
    t = int(tahun)
    if semester in (1, "1"):
        return f"Semester I Tahun {t}"
    if semester in (2, "2"):
        return f"Semester II Tahun {t}"
    return f"Tahun {t}"


def tanggal_akhir_periode(tahun, semester=None) -> str:
    """ISO tanggal posisi laporan: 30 Juni (S1) / 31 Desember (S2/tahunan)."""
    t = int(tahun)
    return f"{t}-06-30" if semester in (1, "1") else f"{t}-12-31"


def baris_posisi_per_akun(dbkp_rows, persediaan_per_akun=None,
                          peta_akun=None) -> dict:
    """Susun tabel "BMN per Akun Neraca" (pola Tabel 52 dokumen contoh).

    - dbkp_rows: baris build_dbkp_rows (per golongan, nilai_intra dst.).
    - persediaan_per_akun: list {akun, uraian, nilai} (117xxx).
    - peta_akun: {golongan: {akun, uraian}} override master akun_bas;
      default AKUN_NERACA_DEFAULT.

    Kembalian {"aset_lancar": [(akun, uraian, nilai)], "aset_tetap": [...],
    "aset_lainnya": [...], "subtotal": {...}, "total": float} — hanya nilai
    INTRAKOMPTABEL (bruto, sesuai penyajian neraca sebelum penyusutan).
    MURNI."""
    peta = dict(peta_akun or {})

    def akun_gol(g):
        info = peta.get(str(g)) or AKUN_NERACA_DEFAULT.get(str(g)) or {}
        return str(info.get("akun") or ""), str(info.get("uraian") or "")

    lancar = [(str(p.get("akun") or ""), str(p.get("uraian") or ""),
               float(p.get("nilai") or 0))
              for p in (persediaan_per_akun or []) if float(p.get("nilai") or 0)]
    tetap, lainnya = [], []
    for r in dbkp_rows or []:
        g = str(r.get("golongan") or "")
        nilai = float(r.get("nilai_intra") or 0)
        if g in ("2", "3", "4", "5", "6", "7"):
            akun, uraian = akun_gol(g)
            tetap.append((akun, str(r.get("uraian") or uraian), nilai))
        elif g == "8":
            akun, uraian = akun_gol(g)
            lainnya.append((akun, str(r.get("uraian") or uraian), nilai))
    sub = {
        "aset_lancar": sum(x[2] for x in lancar),
        "aset_tetap": sum(x[2] for x in tetap),
        "aset_lainnya": sum(x[2] for x in lainnya),
    }
    return {"aset_lancar": lancar, "aset_tetap": tetap,
            "aset_lainnya": lainnya, "subtotal": sub,
            "total": sum(sub.values())}


def baris_akumulasi_per_akun(rekap_susut) -> dict:
    """Tabel akumulasi penyusutan per akun (pola Tabel 53).

    rekap_susut: hasil rekap_penyusutan (per_golongan berisi akumulasi).
    Kembalian {"baris": [(akun, uraian, nilai)], "total": float}. MURNI."""
    baris = []
    for r in (rekap_susut or {}).get("per_golongan", []) or []:
        g = str(r.get("golongan") or "")
        akum = float(r.get("akumulasi") or 0)
        if not akum or g not in AKUN_AKUMULASI:
            continue
        akun, uraian = AKUN_AKUMULASI[g]
        baris.append((akun, uraian, akum))
    return {"baris": baris, "total": sum(x[2] for x in baris)}


def baris_perbandingan_lb_lk(posisi_akun, akumulasi) -> dict:
    """Tabel Perbandingan Laporan Barang vs Laporan Keuangan (Tabel 54).

    AMAN satu basis data — nilai LK diisi sama dengan LB (selisih 0)
    dengan catatan rekonsiliasi internal; struktur tabel tetap lengkap
    agar siap diedit bila LK berbeda. Kembalian {"seksi": [(judul,
    [(akun, uraian, lb, lk, selisih)])], "total": (lb, lk, selisih)}.
    MURNI."""
    seksi = []
    total = 0.0

    def rows(pairs):
        return [(a, u, n, n, 0.0) for a, u, n in pairs]

    p = posisi_akun or {}
    if p.get("aset_lancar"):
        seksi.append(("ASET LANCAR", rows(p["aset_lancar"])))
    tetap = rows(p.get("aset_tetap") or [])
    # Akumulasi penyusutan tampil negatif di seksi aset tetap (137xxx)
    for akun, uraian, nilai in (akumulasi or {}).get("baris", []):
        if akun.startswith("137"):
            tetap.append((akun, uraian, -nilai, -nilai, 0.0))
    if tetap:
        seksi.append(("ASET TETAP", tetap))
    lainnya = rows(p.get("aset_lainnya") or [])
    for akun, uraian, nilai in (akumulasi or {}).get("baris", []):
        if not akun.startswith("137"):
            lainnya.append((akun, uraian, -nilai, -nilai, 0.0))
    if lainnya:
        seksi.append(("ASET LAINNYA", lainnya))
    total = sum(r[2] for _, rws in seksi for r in rws)
    return {"seksi": seksi, "total": (total, total, 0.0)}


def baris_mutasi_golongan(per_kelas) -> list:
    """Susun tabel mutasi CaLBMN per golongan (pola Tabel 19 dst. dokumen):
    per golongan satu blok berisi baris [uraian, Gabungan(unit, rp),
    Intra(unit, rp), Ekstra(unit, rp)] untuk Saldo Awal / Mutasi Tambah /
    Mutasi Kurang / Saldo Akhir.

    per_kelas: {"intra": (rows,total), "ekstra": (...), "gabungan": (...)}
    dari build_lbkp_rows. Kembalian list blok {"golongan", "uraian",
    "baris": [(label, gab_u, gab_n, in_u, in_n, ek_u, ek_n)]}. MURNI."""
    def peta(rows):
        return {str(r.get("golongan")): r for r in (rows or [])}

    kelas = per_kelas or {}
    gab = peta((kelas.get("gabungan") or ([], {}))[0])
    intra = peta((kelas.get("intra") or ([], {}))[0])
    ekstra = peta((kelas.get("ekstra") or ([], {}))[0])
    hasil = []
    for g in sorted(set(gab) | set(intra) | set(ekstra)):
        rg, ri, re_ = gab.get(g, {}), intra.get(g, {}), ekstra.get(g, {})
        if not any(float(rg.get(k) or 0) for k in (
                "jumlah_awal", "nilai_awal", "jumlah_tambah", "nilai_tambah",
                "jumlah_kurang", "nilai_kurang", "jumlah_akhir",
                "nilai_akhir")):
            continue

        def ambil(row, kol):
            return float(row.get(kol) or 0)

        baris = []
        for label, ku, kn in (
                ("Saldo Awal", "jumlah_awal", "nilai_awal"),
                ("Mutasi Tambah", "jumlah_tambah", "nilai_tambah"),
                ("Mutasi Kurang", "jumlah_kurang", "nilai_kurang"),
                ("Saldo Akhir", "jumlah_akhir", "nilai_akhir")):
            baris.append((label,
                          ambil(rg, ku), ambil(rg, kn),
                          ambil(ri, ku), ambil(ri, kn),
                          ambil(re_, ku), ambil(re_, kn)))
        hasil.append({"golongan": g,
                      "uraian": str(rg.get("uraian") or ri.get("uraian")
                                    or ekstra.get(g, {}).get("uraian") or g),
                      "baris": baris})
    return hasil


def struktur_daftar_isi() -> list:
    """Outline daftar isi LBP (level, judul) — cermin struktur dokumen."""
    return [
        (1, "KATA PENGANTAR"),
        (1, "DAFTAR ISI"),
        (1, "I. OVERVIEW LAPORAN BARANG PENGGUNA"),
        (2, "1.1 Gambaran Umum"),
        (2, "1.2 Dasar Hukum"),
        (2, "1.3 Ruang Lingkup Laporan"),
        (2, "1.4 Kebijakan Umum Penatausahaan BMN"),
        (2, "1.5 Kebijakan Akuntansi yang Signifikan"),
        (2, "1.6 Nilai Barang Milik Negara"),
        (1, "II. LAPORAN BARANG PENGGUNA"),
        (2, "a. Laporan Posisi BMN di Neraca"),
        (2, "b. Laporan Persediaan"),
        (2, "c. Laporan BMN Intrakomptabel"),
        (2, "d. Laporan BMN Ekstrakomptabel"),
        (2, "e. Laporan BMN Gabungan"),
        (2, "f. Laporan Konstruksi Dalam Pengerjaan"),
        (2, "g. Laporan Aset Tak Berwujud"),
        (2, "h. Laporan Penyusutan"),
        (1, "III. CATATAN ATAS LAPORAN BARANG MILIK NEGARA"),
        (2, "3.1 Pendahuluan"),
        (2, "3.2 Ringkasan Mutasi BMN per Golongan"),
        (2, "3.3 BMN per Akun Neraca"),
        (2, "3.4 Perbandingan Laporan Barang dan Laporan Keuangan"),
        (2, "3.5 Informasi BMN Lainnya"),
        (1, "PENUTUP"),
    ]


# ── Kelengkapan penuh mengikuti contoh LBP resmi (W8 lanjutan) ──────────────

# Uraian kode transaksi Buku Barang untuk tabel mutasi CaLBMN per akun
# (pola Tabel 17 dokumen contoh: Kode | Uraian | Kuantitas | Rupiah).
LABEL_TRANSAKSI_LBP = {
    "000": "Saldo Awal",
    "100": "Penambahan Saldo Awal",
    "101": "Pembelian",
    "102": "Transfer Masuk",
    "103": "Hibah (Masuk)",
    "105": "Penyelesaian Pembangunan Dengan KDP",
    "107": "Reklasifikasi Masuk",
    "112": "Perolehan Lainnya",
    "201": "Koreksi Perubahan Kuantitas",
    "204": "Koreksi Nilai (Revaluasi)",
    "209": "Koreksi Manual",
    "301": "Penghapusan",
    "302": "Transfer Keluar",
    "304": "Reklasifikasi Keluar",
    "305": "Koreksi Pencatatan",
}


def label_transaksi_lbp(kode) -> str:
    k = str(kode or "").strip()
    return LABEL_TRANSAKSI_LBP.get(k, f"Transaksi {k}" if k else "Transaksi")


def susun_mutasi_per_transaksi(jurnal, saldo_awal_qty=0,
                               saldo_awal_nilai=0.0) -> dict:
    """Susun tabel "Rincian Mutasi ... yang ditatausahakan" per kode
    transaksi (pola Tabel 17 dokumen contoh) untuk SATU golongan.

    - jurnal: baris mutasi_bmn periode berjalan {kode_transaksi, jumlah,
      nilai} (nilai transaksi KURANG boleh positif — dinegatifkan di sini
      berdasar kelompok kode 3xx/4xx).
    - saldo_awal_*: baris 000 dari LBKP (saldo awal periode).

    Kembalian {"baris": [(kode, uraian, qty, nilai)], "total": (qty,
    nilai)} — baris terurut: 000, lalu kode naik. MURNI."""
    agg = {}
    for j in jurnal or []:
        k = str(j.get("kode_transaksi") or "").strip() or "?"
        q = float(j.get("jumlah") or 0)
        n = float(j.get("nilai") or 0)
        if k[:1] in ("3", "4"):
            q, n = -abs(q), -abs(n)
        a = agg.setdefault(k, [0.0, 0.0])
        a[0] += q
        a[1] += n
    baris = [("000", LABEL_TRANSAKSI_LBP["000"],
              float(saldo_awal_qty or 0), float(saldo_awal_nilai or 0))]
    for k in sorted(agg):
        baris.append((k, label_transaksi_lbp(k), agg[k][0], agg[k][1]))
    total_q = sum(b[2] for b in baris)
    total_n = sum(b[3] for b in baris)
    return {"baris": baris, "total": (total_q, total_n)}


def kebijakan_akuntansi_lbp(ambang=None) -> list:
    """Sub-bab Kebijakan Akuntansi yang Signifikan (lengkap mengikuti
    contoh). Kembalian list {judul, isi: [paragraf], daftar: [butir]}."""
    amb = ambang or {}
    amb3 = fmt_rp(amb.get("3") or 1_000_000)
    amb4 = fmt_rp(amb.get("4") or 25_000_000)
    return [
        {"judul": "Persediaan",
         "isi": ["Persediaan merupakan aset lancar dalam bentuk barang atau "
                 "perlengkapan yang dimaksudkan untuk mendukung kegiatan "
                 "operasional pemerintah, dan barang-barang yang dimaksudkan "
                 "untuk dijual dan/atau diserahkan dalam rangka pelayanan "
                 "kepada masyarakat. Persediaan dicatat di neraca "
                 "berdasarkan hasil perhitungan fisik pada tanggal neraca.",
                 "Penilaian persediaan menggunakan metode FIFO (First In "
                 "First Out): saldo persediaan dihitung berdasarkan harga "
                 "perolehan lapisan persediaan yang masuk lebih dahulu."],
         "daftar": ["Harga perolehan, apabila diperoleh dengan pembelian;",
                    "Harga pokok produksi, apabila diproduksi sendiri;",
                    "Nilai wajar/estimasi nilai penjualan, apabila "
                    "diperoleh dengan cara lainnya."]},
        {"judul": "Aset Tetap",
         "isi": ["Aset Tetap merupakan aset berwujud yang mempunyai masa "
                 "manfaat lebih dari 12 (dua belas) bulan untuk digunakan "
                 "dalam kegiatan pemerintah atau dimanfaatkan masyarakat "
                 "umum. Aset tetap dilaporkan di neraca berdasarkan harga "
                 "perolehan atau nilai wajar. Konstruksi Dalam Pengerjaan "
                 "(KDP) dipindahkan ke aset tetap bersangkutan saat aset "
                 "selesai dan siap digunakan."],
         "daftar": ["Tanah", "Peralatan dan Mesin", "Gedung dan Bangunan",
                    "Jalan, Irigasi dan Jaringan", "Aset Tetap Lainnya",
                    "Konstruksi Dalam Pengerjaan"]},
        {"judul": "Aset Lainnya",
         "isi": ["Aset Lainnya antara lain terdiri dari Aset Tak Berwujud "
                 "(aset non-keuangan teridentifikasi tanpa wujud fisik, "
                 "termasuk perangkat lunak, lisensi, dan hak kekayaan "
                 "intelektual) serta Aset Lain-lain (antara lain aset "
                 "tetap yang dihentikan dari penggunaan aktif "
                 "pemerintah)."],
         "daftar": []},
        {"judul": "Kebijakan Penyusutan BMN",
         "isi": ["Sesuai PSAP 07, aset tetap disajikan berdasarkan biaya "
                 "perolehan dikurangi akumulasi penyusutan. Penyusutan "
                 "dihitung dan dicatat setiap akhir semester tanpa nilai "
                 "residu menggunakan metode garis lurus selama masa "
                 "manfaat (PMK 65/PMK.06/2017; tabel masa manfaat KMK "
                 "295/KMK.06/2019).",
                 "Penyusutan tidak dilakukan terhadap: tanah; KDP; aset "
                 "tetap yang dinyatakan hilang dan telah diusulkan "
                 "penghapusannya; aset tetap rusak berat/usang yang telah "
                 "diusulkan penghapusannya; serta aset tetap renovasi yang "
                 "tidak menambah masa manfaat."],
         "daftar": ["Gedung dan Bangunan;", "Peralatan dan Mesin;",
                    "Jalan, Irigasi dan Jaringan;",
                    "Aset Tetap Lainnya (aset tetap renovasi dan alat "
                    "musik modern);",
                    "Aset Lainnya berupa aset tetap yang dihentikan dari "
                    "penggunaan operasional pemerintah."]},
        {"judul": "Amortisasi",
         "isi": ["Amortisasi aset tak berwujud merupakan alokasi harga "
                 "perolehan secara sistematis selama masa manfaatnya "
                 "(PMK 251/PMK.06/2015; masa manfaat KMK 620/KM.6/2015 jo. "
                 "KMK 81/KM.6/2018), dihitung setiap akhir semester dengan "
                 "metode garis lurus tanpa nilai residu."],
         "daftar": ["Perangkat Lunak (Software) Komputer;", "Lisensi;",
                    "Waralaba (Franchise);", "Hak Cipta (Copyright);",
                    "Hak Paten."]},
        {"judul": "Kebijakan Kapitalisasi BMN",
         "isi": ["Sesuai PMK 181/PMK.06/2016, BMN disajikan sebagai "
                 "intrakomptabel (memenuhi syarat kapitalisasi, disajikan "
                 "di neraca) dan ekstrakomptabel (tidak memenuhi syarat "
                 "kapitalisasi). Batas minimum kapitalisasi yang berlaku "
                 "pada satker ini:"],
         "daftar": [f"Peralatan dan mesin serta alat olahraga ≥ Rp{amb3};",
                    f"Gedung dan bangunan ≥ Rp{amb4};",
                    "Tanah, jalan/irigasi/jaringan, KDP, koleksi "
                    "perpustakaan, dan barang bercorak kesenian: tanpa "
                    "batas nilai minimum."]},
        {"judul": "Pencatatan Aset Rusak Berat dan Hilang",
         "isi": ["Aset tetap yang dinyatakan hilang berdasarkan dokumen "
                 "sumber yang sah dan telah diusulkan penghapusannya "
                 "direklasifikasi ke daftar barang hilang; aset rusak "
                 "berat/usang yang telah diusulkan penghapusannya "
                 "direklasifikasi ke daftar barang rusak berat — keduanya "
                 "tidak dicantumkan dalam laporan barang dan neraca "
                 "(PMK 65/PMK.06/2017)."],
         "daftar": []},
        {"judul": "Akuntansi Berbasis Akrual",
         "isi": ["Penyusunan laporan menerapkan basis akrual sesuai PP 71 "
                 "Tahun 2010: perolehan BMN diakui saat hak kepemilikan "
                 "berpindah meskipun pembayaran belum dilakukan; jurnal "
                 "persediaan dan penyusutan mempengaruhi beban pada "
                 "Laporan Operasional serta akun-akun Laporan Perubahan "
                 "Ekuitas."],
         "daftar": []},
    ]


def struktur_daftar_isi_lengkap() -> list:
    """Outline daftar isi LBP LENGKAP (level, judul) — cermin contoh."""
    return [
        (1, "KATA PENGANTAR"),
        (1, "DAFTAR ISI"),
        (1, "SURAT PENGANTAR"),
        (1, "I. OVERVIEW LAPORAN BARANG PENGGUNA"),
        (2, "1.1 Gambaran Umum"),
        (2, "1.2 Dasar Hukum"),
        (2, "1.3 Ruang Lingkup Laporan"),
        (2, "1.4 Kebijakan Umum Penatausahaan BMN"),
        (2, "1.5 Kebijakan Akuntansi yang Signifikan"),
        (2, "1.6 Nilai Barang Milik Negara"),
        (1, "II. LAPORAN BARANG PENGGUNA"),
        (2, "a. Laporan Posisi BMN di Neraca"),
        (2, "b. Laporan Persediaan"),
        (2, "c. Laporan BMN Intrakomptabel"),
        (2, "d. Laporan BMN Ekstrakomptabel"),
        (2, "e. Laporan BMN Gabungan"),
        (2, "f. Laporan Konstruksi Dalam Pengerjaan"),
        (2, "g. Laporan Aset Tak Berwujud"),
        (2, "h. Laporan Barang Bersejarah"),
        (2, "i. Laporan Barang BPYDS"),
        (2, "j. Laporan Barang Hibah DK/TP"),
        (2, "k. Laporan Penyusutan dan Amortisasi"),
        (1, "III. CATATAN ATAS LAPORAN BARANG MILIK NEGARA"),
        (2, "3.1 Pendahuluan"),
        (2, "3.2 Ringkasan Mutasi BMN per Golongan"),
        (2, "3.3 BMN per Akun Neraca"),
        (2, "3.4 Perbandingan Laporan Barang dan Laporan Keuangan"),
        (2, "3.5 Informasi BMN Lainnya"),
        (2, "3.6 Tindak Lanjut Temuan Pemeriksaan"),
        (1, "LAMPIRAN"),
        (2, "a. Laporan PNBP dari Pengelolaan BMN"),
        (2, "b. Laporan Pelaksanaan Pengasuransian BMN"),
        (2, "c. Laporan BMN Berupa Rumah Negara"),
        (2, "d. Berita Acara Rekonsiliasi Internal"),
        (2, "e. Neraca Percobaan dan Laporan Neraca"),
        (2, "f. Data Transfer Masuk dan Transfer Keluar"),
        (2, "g. Rekapitulasi Transaksi Hibah"),
        (2, "h. Daftar BMN Hilang yang Diusulkan ke Pengelola"),
        (2, "i. Laporan Pengawasan dan Pengendalian"),
        (1, "PENUTUP"),
    ]
