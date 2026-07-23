"""Bank nilai realistis — konteks BMN OIKN/IKN.

Semua daftar di sini menjadi bahan baku generator supaya data sintetis
"terasa nyata": nama barang, kategori, merek, lokasi di Kawasan IKN
(Kalimantan Timur), satker, jabatan, dsb. Sengaja tanpa dependency eksternal
(mis. Faker) agar generator ringan dan bisa jalan di CI tanpa memasang paket
baru — cukup pustaka standar Python.

Angka/kode dibuat mengikuti pola nyata (kodefikasi BMN 6-digit per segmen,
NUP, satker 6/20 digit) tetapi nilainya fiktif — bukan data BMN sungguhan.
"""

# ── Barang per kategori (nama barang lazim di lingkungan kantor pemerintah) ──
# Dipakai untuk memilih nama aset yang konsisten dengan kategorinya.
BARANG_PER_KATEGORI = {
    "Peralatan dan Mesin": [
        "Laptop", "Komputer PC", "Monitor", "Printer", "Scanner",
        "Proyektor (LCD Projector)", "Mesin Fotokopi", "UPS", "Router",
        "Switch Jaringan", "Access Point", "CCTV", "Server Rack",
        "AC Split", "AC Standing", "Genset", "Dispenser", "Kulkas",
        "Televisi", "Mesin Absensi Sidik Jari", "Pemindai Barcode",
    ],
    "Tanah": [
        "Tanah Bangunan Kantor Pemerintah",
        "Tanah Kosong Yang Belum Digunakan",
        "Tanah Bangunan Rumah Negara Golongan I",
    ],
    "Gedung dan Bangunan": [
        "Bangunan Gedung Kantor Permanen",
        "Bangunan Gedung Pertemuan Permanen",
        "Rumah Negara Golongan II Tipe C Permanen",
        "Gudang Tertutup Permanen", "Pos Jaga Permanen",
    ],
    "Jalan, Irigasi dan Jaringan": [
        "Jalan Khusus Kompleks", "Jaringan Distribusi Air Bersih",
        "Instalasi Air Kotor", "Jaringan Listrik Tegangan Rendah",
    ],
    "Aset Tetap Lainnya": [
        "Meja Kerja Kayu", "Kursi Kerja", "Kursi Rapat", "Meja Rapat",
        "Lemari Arsip", "Filing Cabinet Besi", "Sofa", "Whiteboard",
        "Brankas", "Rak Besi", "Buku Perpustakaan Umum",
    ],
    "Alat Angkutan": [
        "Kendaraan Dinas Roda 4 (Minibus)",
        "Kendaraan Dinas Roda 2 (Sepeda Motor)",
        "Kendaraan Dinas Roda 4 (Double Cabin)",
        "Sepeda Listrik Operasional",
    ],
}

# Kategori yang benar-benar dipakai form aset (selaras opsi dropdown umum).
KATEGORI = tuple(BARANG_PER_KATEGORI.keys()) + ("Lainnya",)

# ── Merek per rumpun barang (dipakai kalau nama barang cocok) ──
MEREK_ELEKTRONIK = [
    "ASUS", "Lenovo", "HP", "Dell", "Acer", "Epson", "Canon", "Brother",
    "Cisco", "Mikrotik", "TP-Link", "Ubiquiti", "Hikvision", "Dahua",
    "Daikin", "Panasonic", "LG", "Sharp", "Samsung", "APC",
]
MEREK_KENDARAAN = ["Toyota", "Mitsubishi", "Honda", "Suzuki", "Isuzu", "Daihatsu"]
MEREK_MEBEL = ["Olympic", "Ligna", "Brother", "Chitose", "Indachi", "Uno", "Frontline"]

# ── Lokasi di Kawasan IKN & sekitarnya (Kalimantan Timur) ──
LOKASI = [
    "Kantor OIKN, Kawasan Inti Pusat Pemerintahan (KIPP), Sepaku",
    "Gedung Bendahara Umum Negara, KIPP IKN",
    "Kompleks Perkantoran Kementerian Koordinator, IKN",
    "Rumah Tapak Jabatan Menteri (RTJM), IKN",
    "Hunian Pekerja Konstruksi (HPK), Sepaku",
    "Kantor Kecamatan Sepaku, Penajam Paser Utara",
    "Gudang Logistik Titik Nol, Kalimantan Timur",
    "Embung MBH, Kawasan IKN",
    "Persemaian Mentawir, Penajam Paser Utara",
    "Bandara VVIP IKN, Kalimantan Timur",
    "Kantor Perwakilan Balikpapan, Kalimantan Timur",
    "Kantor Perwakilan Samarinda, Kalimantan Timur",
]

# Kotak koordinat kasar Kawasan IKN (Sepaku, PPU) untuk titik yang realistis.
IKN_LAT_MIN, IKN_LAT_MAX = -1.05, -0.85     # sekitar -0.9..-1.0 LS
IKN_LNG_MIN, IKN_LNG_MAX = 116.55, 116.95   # sekitar 116.6..116.9 BT

# ── Eselon / unit organisasi (fiktif tapi berpola) ──
ESELON1 = [
    "Deputi Bidang Sarana dan Prasarana",
    "Deputi Bidang Pendanaan dan Investasi",
    "Deputi Bidang Lingkungan Hidup dan Sumber Daya Alam",
    "Deputi Bidang Sosial Budaya dan Pemberdayaan Masyarakat",
    "Sekretariat Otorita IKN",
    "Deputi Bidang Transformasi Hijau dan Digital",
]
ESELON2 = [
    "Direktorat Pengelolaan Barang Milik Negara",
    "Direktorat Umum dan Tata Usaha",
    "Direktorat Perencanaan dan Pembangunan",
    "Biro Perencanaan dan Keuangan",
    "Biro Umum dan Layanan Pengadaan",
    "Direktorat Sistem Informasi dan Teknologi",
]

# ── Nama orang Indonesia (untuk pengguna/pegawai/penanda tangan) ──
NAMA_DEPAN = [
    "Budi", "Siti", "Ahmad", "Dewi", "Rizki", "Putri", "Agus", "Rina",
    "Hendra", "Wulan", "Fajar", "Nur", "Andi", "Maya", "Bambang", "Ayu",
    "Dimas", "Ratna", "Eko", "Sari", "Yusuf", "Indah", "Rahmat", "Lestari",
    "Gunawan", "Fitri", "Hadi", "Nabila", "Irfan", "Yuni",
]
NAMA_BELAKANG = [
    "Santoso", "Wijaya", "Nugroho", "Hakim", "Pratama", "Kusuma", "Halim",
    "Saputra", "Maulana", "Ramadhan", "Hidayat", "Purnama", "Anggraini",
    "Setiawan", "Firdaus", "Utami", "Wibowo", "Handayani", "Suryadi",
    "Permana",
]
GELAR_DEPAN = ["", "", "", "Dr.", "Ir.", "Drs.", "H.", "Hj."]
GELAR_BELAKANG = ["", "", "", "S.T.", "S.E.", "S.H.", "S.Kom.", "M.M.",
                  "M.T.", "M.Si.", "A.Md.", "S.Sos."]

JABATAN = [
    "Kepala Sub Bagian Umum", "Analis Pengelolaan BMN", "Pengelola BMN",
    "Bendahara Pengeluaran", "Operator SIMAK-BMN", "Staf Tata Usaha",
    "Kepala Bagian Perencanaan", "Pranata Komputer", "Arsiparis",
    "Pengadministrasi Persuratan",
]

SUPPLIER = [
    "CV Mitra Sarana Nusantara", "PT Karya Teknik Mandiri",
    "CV Borneo Elektronik", "PT Sinar Kalimantan Sejahtera",
    "PT Digital Solusi Indonesia", "CV Andalan Furniture",
    "PT Nusantara Motor Prima", "CV Cahaya Timur Perkasa",
]

KONDISI_ASET = ("Baik", "Rusak Ringan", "Rusak Berat")

# Prefiks kode barang BMN (kodefikasi PMK) — 2 digit gol + segmen, fiktif tapi
# berpola "3.05.01.04.001" dst. Digunakan generator untuk membentuk asset_code.
KODE_GOLONGAN = {
    "Peralatan dan Mesin": "3",
    "Tanah": "1",
    "Gedung dan Bangunan": "4",
    "Jalan, Irigasi dan Jaringan": "5",
    "Aset Tetap Lainnya": "6",
    "Alat Angkutan": "3",
    "Lainnya": "3",
}

# Nama kegiatan inventarisasi realistis (untuk generator kegiatan).
NAMA_KEGIATAN = [
    "Inventarisasi BMN Semester {sem} T.A. {tahun}",
    "Opname Fisik Aset {eselon} Tahun {tahun}",
    "Rekonsiliasi Internal BMN Triwulan {tw} {tahun}",
    "Sensus BMN Kawasan IKN {tahun}",
    "Verifikasi Aset Hasil Serah Terima {tahun}",
]

# Satker fiktif berpola (untuk generator satker; kode 6 digit + lengkap 20 digit).
SATKER = [
    ("Otorita Ibu Kota Nusantara", "999001"),
    ("OIKN - Deputi Sarana Prasarana", "999002"),
    ("OIKN - Sekretariat", "999003"),
    ("OIKN - Perwakilan Balikpapan", "999004"),
]
