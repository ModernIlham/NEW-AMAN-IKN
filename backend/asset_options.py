"""Pilihan domain aset murni: tanpa DB, limiter, network, atau runtime aplikasi.

Re-export shared_utils dipertahankan untuk pemanggil lama. Generator sintetis
mengimpor modul ini langsung agar CLI tidak menginisialisasi layanan runtime.
"""

# --- Inventory Constants ---
VALID_INVENTORY_STATUSES = ["Belum Diinventarisasi", "Ditemukan", "Tidak Ditemukan", "Berlebih", "Sengketa"]
VALID_CONDITIONS = ["Baik", "Rusak Ringan", "Rusak Berat"]
VALID_STATUSES = ["Aktif", "Idle", "Maintenance", "Nonaktif"]
VALID_STIKER_STATUSES = ["Belum Terpasang", "Sudah Terpasang"]
VALID_STIKER_SIZES = ["Kecil", "Sedang", "Besar"]
VALID_KLASIFIKASI = ["Kesalahan Pencatatan", "Tidak Ditemukan Lainnya"]
# Sub-klasifikasi sebab BMN tidak ditemukan.
#
# Daftar di bawah adalah SATU sumber kebenaran, dan harus persis sama dengan
# `SUB_KLASIFIKASI_OPTIONS` di frontend `InventoryFieldSheet.jsx` — dijaga uji
# `tests/unit/test_sub_klasifikasi_selaras.py`.
#
# Kenapa dijaga: sebelumnya kedua sisi punya daftarnya sendiri dan IRISANNYA
# NOL. Akibatnya seluruh 10 nilai yang bisa dihasilkan UI aplikasi DITOLAK saat
# berkasnya diimpor ulang lewat Excel, sementara template Excel menawarkan
# nilai yang UI-nya tak pernah bisa hasilkan — bahkan baris contoh di template
# itu sendiri ("Pencatatan Ganda") ditolak validatornya sendiri.
VALID_SUB_KLASIFIKASI_PENCATATAN = [
    "Kesalahan Kodefikasi",
    "Pencatatan Ganda",
    "BMN Tercatat di Satker Lain",
    "Kegiatan Perencanaan/Pengembangan Dicatat Sebagai BMN Tersendiri",
    "BMN Objek Alih Status/Pemindahtanganan/Penghapusan",
    "Penggabungan BMN Satu Kesatuan Fungsi",
    "Kesalahan Pencatatan Pihak Ketiga",
    # Dua di bawah melengkapi pemetaan ke 11 klasifikasi resmi DJKN menjadi
    # 11/11 (lihat docs/SITASI-DOKUMEN-RESMI.md).
    "Kegiatan Renovasi Dicatat Sebagai BMN Tersendiri",
    "Kesalahan Kodefikasi/Klasifikasi (Bukan Objek Revaluasi)",
]
VALID_SUB_KLASIFIKASI_LAINNYA = [
    # Tiga pertama: BAGAIMANA pencarian gagal.
    "Tidak Ditemukan Fisiknya",
    "Tidak Dapat Ditelusuri",
    "Tertimpa Bangunan Lain/Beralih Fungsi",
    # Sisanya: SEBAB barangnya lenyap — termasuk keadaan kahar. Ditambahkan
    # atas keputusan pemilik agar kejadian tak terduga (kebakaran, bencana,
    # pencurian) punya kategorinya sendiri, bukan menumpuk di satu ember.
    #
    # Catatan jujur: dua kelompok ini memang DUA SUMBU yang berbeda — satu
    # menjawab "bagaimana kami gagal menemukannya", satu menjawab "kenapa ia
    # tidak ada". Meleburnya ke satu daftar adalah keputusan pemilik yang
    # diambil sadar; konsekuensinya operator memilih salah satu sudut pandang,
    # tidak keduanya sekaligus.
    "Hilang / Dicuri",
    "Kebakaran",
    "Bencana Alam",
    "Kerusuhan / Huru-hara",
    "Rusak Total / Hancur",
    "Sebab Lain (Diuraikan)",
]

# Nilai yang DITAWARKAN aplikasi hari ini (UI + dropdown template Excel).
SUB_KLASIFIKASI_DITAWARKAN = (VALID_SUB_KLASIFIKASI_PENCATATAN
                              + VALID_SUB_KLASIFIKASI_LAINNYA)

# Nilai LAMA yang dulu divalidasi impor & ditawarkan template. Tidak lagi
# ditawarkan, tetapi tetap DITERIMA: berkas Excel dan data yang sudah terlanjur
# memakainya tak boleh mendadak ditolak hanya karena daftarnya dirapikan.
# Longgar saat menerima, ketat saat menawarkan.
SUB_KLASIFIKASI_LAWAS = [
    "Salah Kode Barang/NUP",
    "Salah Pembukuan (SIMAK-BMN Error)",
    "Perubahan Kondisi Belum Dicatat",
    "Aset Sudah Dihibahkan/Dipindahtangankan",
    "Aset Sudah Dihapuskan",
    "Pencatatan Ganda (Double Counting)",
    "Pemecahan/Penggabungan Belum Dicatat",
    "Transfer Masuk/Keluar Belum Diproses",
    # "Hilang / Dicuri", "Bencana Alam", dan "Rusak Total / Hancur" DIPROMOSIKAN
    # kembali ke daftar yang ditawarkan (lihat VALID_SUB_KLASIFIKASI_LAINNYA),
    # jadi tak lagi tercantum di sini — keduanya wajib saling lepas.
    "Lainnya",
]

VALID_SUB_KLASIFIKASI_ALL = SUB_KLASIFIKASI_DITAWARKAN + SUB_KLASIFIKASI_LAWAS


# ── Temuan pencatatan lapangan ──────────────────────────────────────────────
# Klasifikasi yang BERDIRI SENDIRI, sengaja lepas dari `klasifikasi_tidak_
# ditemukan`. Alasannya sederhana dan datang dari lapangan: cacat pencatatan
# paling sering ditemukan pada barang yang JUSTRU KETEMU — kodenya tak sesuai
# fisik, stikernya tertempel di barang lain, namanya beda dengan barangnya.
#
# Sebelum ini tak ada tempat menandainya. Sub-klasifikasi hanya hidup ketika
# aset berstatus "Tidak Ditemukan", sehingga temuan pada aset yang ditemukan
# hanya bisa dititipkan ke kolom Catatan — tidak terhitung, tidak tersaring,
# dan hilang dari rekapitulasi.
#
# Penanda ini yang kelak menyuplai usul REKLASIFIKASI: kode barang yang salah
# baru bisa diusulkan diperbaiki kalau ada yang mencatatnya saat inventarisasi.
# Daftar ini memuat DUA macam kejadian, dan itu disengaja:
#
#   (a) CACAT CATATAN — catatan tak sesuai fisik (kode, stiker, nama, jumlah);
#   (b) HAMBATAN PEMERIKSAAN — barangnya tidak bisa diperiksa saat itu, tetapi
#       BUKAN berarti hilang (ruangan terkunci, sedang dipinjam, di bengkel).
#
# Meleburnya aman di sini, berbeda dengan `sub_klasifikasi`. Alasannya: penanda
# ini NETRAL — tidak ada satu pun naskah resmi yang berubah isinya karena nilai
# di field ini. Sub-klasifikasi menggerakkan Berita Acara, SPTJM, dan usul
# penghapusan; kalau dua sumbu dilebur di sana, dokumen bermeterai ikut salah
# bicara. Di sini paling jauh akibatnya adalah satu baris di rekapitulasi.
#
# Golongan (b) penting justru karena tanpanya operator terpaksa memilih antara
# dua-duanya salah: menandai "Ditemukan" padahal tak diperiksa, atau "Tidak
# Ditemukan" padahal barangnya jelas ada di tangan seseorang.
VALID_TEMUAN_PENCATATAN = [
    # (a) cacat catatan
    "Kodefikasi Tidak Sesuai Fisik",
    "Stiker Tertempel di Barang Lain",
    "Stiker Rusak/Tidak Terbaca",
    "NUP Ganda pada Fisik Berbeda",
    "Nama/Spesifikasi Tidak Sesuai Fisik",
    "Lokasi Tercatat Tidak Sesuai",
    "Fisik Ada, Jumlah Tidak Sesuai Catatan",
    # (b) hambatan pemeriksaan — barang belum tentu hilang
    "Tidak Dapat Diakses (Ruangan Terkunci)",
    "Sedang Dipinjam/Dibawa Pemegang",
    "Sedang Diperbaiki/Di Luar Kantor",
    "Temuan Lain (Diuraikan)",
]
