/**
 * Registry modul Siklus Pengelolaan BMN — SATU sumber kebenaran untuk
 * "rumah modul" (ModuleHomePage) dan roadmap pengembangan bertahap.
 *
 * Siklus mengikuti PP 27/2014 jo. PP 28/2020: perencanaan → pengadaan →
 * penggunaan → pemanfaatan → pengamanan & pemeliharaan → penilaian →
 * pemindahtanganan → pemusnahan → penghapusan, dengan PENATAUSAHAAN
 * (pembukuan, inventarisasi, pelaporan) sebagai poros pencatatan dan
 * pembinaan-pengawasan-pengendalian melingkupi seluruh tahap.
 *
 * Posisi saat ini: Penatausahaan › Inventarisasi Aset (modul AKTIF).
 * Modul lain berstatus "segera" — kartunya sudah berdiri (rumah dibangun
 * dulu), konsep & rencana fiturnya tercatat di sini dan di
 * docs/MASTERPLAN-SIKLUS-BMN.md. Konsep persediaan diambil dari sistem
 * KERJA-BARENG (master FIFO, transaksi per dokumen sumber, gudang, opname).
 *
 * status: "aktif"    → modul berfungsi penuh (bisa dimasuki)
 *         "sebagian" → sebagian kemampuan sudah tersedia di modul lain
 *         "segera"   → coming soon; klik menampilkan konsep & rencana
 * fase:   urutan pengembangan (1 = sedang dimatangkan sekarang)
 */

// ── Sub-modul PENATAUSAHAAN (poros — tempat kita berada) ──────────────
export const PENATAUSAHAAN_SUBMODULES = [
  {
    id: "inventarisasi-aset",
    nama: "Inventarisasi Aset",
    status: "aktif",
    fase: 1,
    ringkas: "Pendataan fisik BMN per kegiatan — modul yang sedang Anda pakai.",
    deskripsi:
      "Inventarisasi fisik Barang Milik Negara sesuai SE-17/MK.1/2024: kegiatan ber-tiket, "
      + "mode lapangan offline-first, kamera + scan QR, peta aset GIS, klasifikasi "
      + "ditemukan/tidak ditemukan/berlebih/sengketa, 13+ laporan resmi, hingga pengesahan "
      + "berkekuatan dokumen dan kunci kegiatan.",
    fitur: [
      "Kegiatan inventarisasi ber-tiket (INV-{tahun}-{seq}) dengan tim & satker",
      "Mode lapangan: input sekali ketuk, kamera watermark, scan QR, GPS, offline penuh",
      "Peta aset interaktif + ekspor KML/KMZ/SHP",
      "13+ laporan resmi siap tanda tangan + pengesahan & kunci kegiatan",
    ],
    integrasi: [
      "Hasil klasifikasi (kondisi, tidak ditemukan) menjadi bahan modul Penghapusan & Perencanaan",
      "Data pengguna + BAST menjadi benih modul Penggunaan (aset pegawai)",
    ],
  },
  {
    id: "pembukuan",
    nama: "Pembukuan",
    status: "segera",
    fase: 2,
    ringkas: "Daftar Barang Kuasa Pengguna & Kartu Identitas Barang.",
    deskripsi:
      "Pencatatan BMN ke dalam daftar barang: Daftar Barang Kuasa Pengguna (DBKP) per "
      + "golongan, Kartu Identitas Barang (KIB) untuk tanah/bangunan/kendaraan, saldo awal-"
      + "mutasi-saldo akhir per periode. Setiap transaksi modul lain otomatis membukukan diri.",
    fitur: [
      "DBKP per golongan/bidang/kelompok mengikuti kodefikasi BMN",
      "KIB A-F (tanah, bangunan, kendaraan, dst.) dengan detail khusus per jenis",
      "Saldo awal → mutasi masuk/keluar → saldo akhir per semester",
      "Jurnal otomatis dari transaksi perolehan/penghapusan/transfer",
    ],
    integrasi: [
      "Master aset & hasil inventarisasi menjadi sumber saldo",
      "Referensi kodefikasi barang dipakai bersama seluruh modul",
    ],
  },
  {
    id: "inventarisasi-persediaan",
    nama: "Inventarisasi Persediaan",
    status: "segera",
    fase: 2,
    ringkas: "Stok barang habis pakai: FIFO, gudang, opname — konsep dari sistem KERJA-BARENG.",
    deskripsi:
      "Manajemen barang persediaan (aset lancar, kodefikasi berawalan '1'): master persediaan "
      + "dengan stok ber-batch FIFO (harga & kedaluwarsa per batch), transaksi masuk/keluar "
      + "terkelompok per dokumen sumber, gudang, dan stock opname berkala dengan penyesuaian "
      + "otomatis. Alur mengadopsi modul persediaan KERJA-BARENG yang sudah terbukti.",
    fitur: [
      "Master persediaan: kodefikasi 16 digit berawalan '1', NUP otomatis, satuan, foto",
      "Stok FIFO per batch — harga perolehan & tanggal kedaluwarsa melekat di batch",
      "Transaksi masuk/keluar (satuan & massal per dokumen: no. bukti, kontrak, PPK, penyedia) + bukti foto",
      "Gudang: distribusi, pengembalian, transfer antar gudang, ringkasan per gudang",
      "Stock opname: fisik vs sistem → selisih → penyesuaian otomatis + jurnal transaksi",
      "Peringatan batas kritis & kedaluwarsa + nota dinas otomatis (PDF)",
      "Laporan persediaan: posisi stok, mutasi per periode, rincian per barang",
    ],
    integrasi: [
      "Berbagi kodefikasi barang, satker, dan kop surat dengan modul aset",
      "Opname persediaan memakai pola kegiatan + mode lapangan yang sudah ada",
    ],
  },
  {
    id: "pelaporan",
    nama: "Pelaporan",
    status: "sebagian",
    fase: 2,
    ringkas: "Laporan barang semesteran/tahunan & rekonsiliasi — laporan inventarisasi sudah tersedia.",
    deskripsi:
      "Pelaporan BMN berkala: Laporan Barang Kuasa Pengguna (LBKP) semesteran & tahunan, "
      + "laporan kondisi barang, serta dukungan rekonsiliasi dengan SIMAK/SAKTI. Saat ini "
      + "13+ laporan inventarisasi sudah berjalan di modul Inventarisasi Aset; modul ini "
      + "akan menyatukannya menjadi arsip laporan lintas kegiatan & lintas periode.",
    fitur: [
      "LBKP semesteran/tahunan per golongan",
      "Arsip laporan lintas kegiatan dengan penomoran & riwayat",
      "Ekspor rekonsiliasi (format yang bisa disandingkan dengan SIMAK/SAKTI)",
    ],
    integrasi: [
      "Menarik data pembukuan + hasil inventarisasi aset & persediaan",
      "Kop surat & penanda tangan memakai pengaturan laporan yang sudah ada",
    ],
  },
];

// ── Tahap siklus BMN (di luar penatausahaan) ──────────────────────────
export const SIKLUS_MODULES = [
  {
    id: "perencanaan",
    nama: "Perencanaan & Penganggaran",
    urutan: 1,
    status: "segera",
    fase: 4,
    ringkas: "RKBMN: kebutuhan pengadaan & pemeliharaan berbasis data aset.",
    deskripsi:
      "Perencanaan Kebutuhan BMN (RKBMN): usulan kebutuhan pengadaan dan pemeliharaan "
      + "dari unit, ditimbang terhadap standar barang & standar kebutuhan (SBSK) serta "
      + "data eksisting hasil inventarisasi.",
    fitur: [
      "Usulan kebutuhan per unit + persetujuan berjenjang",
      "Sanding usulan vs data aset eksisting (jumlah, kondisi, umur)",
      "Rekap RKBMN pengadaan & pemeliharaan siap ajukan",
    ],
    integrasi: ["Data kondisi & jumlah aset dari Inventarisasi menjadi dasar analisis kebutuhan"],
  },
  {
    id: "pengadaan",
    nama: "Pengadaan",
    urutan: 2,
    status: "segera",
    fase: 4,
    ringkas: "Perolehan baru: kontrak, BAST, penerimaan → otomatis masuk daftar aset.",
    deskripsi:
      "Pencatatan perolehan BMN baru (pembelian, hibah masuk, transfer masuk): dokumen "
      + "sumber (kontrak, SPM/SP2D, BAST), penerimaan barang, dan pendaftaran otomatis "
      + "ke master aset/persediaan — pola dokumen sumber mengadopsi KERJA-BARENG.",
    fitur: [
      "Registrasi perolehan per dokumen sumber (kontrak, PPK, penyedia, nilai)",
      "Penerimaan barang → auto-daftar ke master aset (kode + NUP) / stok persediaan",
      "Lampiran dokumen & foto serah terima",
    ],
    integrasi: ["Menjadi pintu masuk data master aset & batch persediaan baru"],
  },
  {
    id: "penggunaan",
    nama: "Penggunaan",
    urutan: 3,
    status: "segera",
    fase: 3,
    ringkas: "Penetapan status penggunaan & aset di tangan pegawai (BAST).",
    deskripsi:
      "Penetapan Status Penggunaan (PSP), penggunaan sementara, BMN idle, dan penatausahaan "
      + "aset yang melekat ke pegawai/jabatan — melanjutkan data pengguna + BAST yang sudah "
      + "dicatat modul inventarisasi.",
    fitur: [
      "Pengajuan & SK Penetapan Status Penggunaan",
      "Daftar aset per pegawai/jabatan + BAST digital (benihnya sudah ada)",
      "Pemantauan BMN idle & penggunaan sementara",
    ],
    integrasi: ["Field pengguna, NIP, jabatan, dan BAST dari modul inventarisasi menjadi data awal"],
  },
  {
    id: "pemanfaatan",
    nama: "Pemanfaatan",
    urutan: 4,
    status: "segera",
    fase: 5,
    ringkas: "Sewa, pinjam pakai, KSP/BGS — jadwal & PNBP.",
    deskripsi:
      "Pemanfaatan BMN oleh pihak lain: sewa, pinjam pakai, kerja sama pemanfaatan (KSP), "
      + "bangun guna serah/bangun serah guna (BGS/BSG), dan KETUPI — dengan jadwal jatuh "
      + "tempo dan pemantauan PNBP.",
    fitur: [
      "Registrasi perjanjian pemanfaatan per aset + arsip dokumen",
      "Kalender jatuh tempo & pengingat perpanjangan",
      "Pencatatan PNBP per perjanjian",
    ],
    integrasi: ["Status pemanfaatan tampil di detail aset & laporan"],
  },
  {
    id: "pengamanan",
    nama: "Pengamanan & Pemeliharaan",
    urutan: 5,
    status: "segera",
    fase: 3,
    ringkas: "Dokumen kepemilikan, jadwal & riwayat pemeliharaan per aset.",
    deskripsi:
      "Pengamanan fisik, administrasi, dan hukum (sertifikat, BPKB, dokumen kepemilikan) "
      + "serta pemeliharaan: jadwal, riwayat, dan biaya pemeliharaan per aset.",
    fitur: [
      "Arsip dokumen kepemilikan per aset (sertifikat, BPKB, IMB)",
      "Jadwal pemeliharaan berkala + riwayat & biaya",
      "Pemantauan aset bermasalah (sengketa — datanya sudah dicatat inventarisasi)",
    ],
    integrasi: ["Data sengketa & kondisi dari inventarisasi menjadi daftar pantau"],
  },
  {
    id: "penilaian",
    nama: "Penilaian",
    urutan: 6,
    status: "segera",
    fase: 5,
    ringkas: "Nilai wajar, revaluasi, dan penyusutan.",
    deskripsi:
      "Penilaian BMN untuk penyusunan neraca dan rencana pemindahtanganan/pemanfaatan: "
      + "nilai wajar, revaluasi, dan perhitungan penyusutan per golongan.",
    fitur: [
      "Pencatatan hasil penilaian/revaluasi per aset",
      "Penyusutan otomatis per golongan (masa manfaat standar)",
      "Riwayat nilai: perolehan → revaluasi → buku",
    ],
    integrasi: ["Nilai perolehan dari master aset; hasil menyuplai pembukuan & pelaporan"],
  },
  {
    id: "pemindahtanganan",
    nama: "Pemindahtanganan",
    urutan: 7,
    status: "segera",
    fase: 6,
    ringkas: "Penjualan, tukar-menukar, hibah keluar, PMPP.",
    deskripsi:
      "Pemindahtanganan BMN: penjualan (lelang), tukar-menukar, hibah keluar, dan penyertaan "
      + "modal pemerintah pusat — dari usulan, persetujuan, risalah, hingga BAST keluar.",
    fitur: [
      "Alur usulan → persetujuan → pelaksanaan per jenis pemindahtanganan",
      "Arsip risalah lelang / naskah hibah / BAST keluar",
      "Aset otomatis keluar dari daftar aktif setelah selesai",
    ],
    integrasi: ["Berbagi alur persetujuan & dokumen dengan pemusnahan/penghapusan"],
  },
  {
    id: "pemusnahan",
    nama: "Pemusnahan",
    urutan: 8,
    status: "segera",
    fase: 6,
    ringkas: "Usulan & berita acara pemusnahan aset rusak berat.",
    deskripsi:
      "Pemusnahan BMN yang tidak dapat digunakan/dimanfaatkan/dipindahtangankan: usulan "
      + "(kandidat otomatis dari aset rusak berat hasil inventarisasi), persetujuan, dan "
      + "berita acara pemusnahan.",
    fitur: [
      "Kandidat pemusnahan otomatis dari kondisi Rusak Berat + tindak lanjut inventarisasi",
      "Alur usulan → persetujuan → BA pemusnahan (dengan foto bukti)",
    ],
    integrasi: ["Kondisi & tindak lanjut dari modul inventarisasi menjadi pintu masuk"],
  },
  {
    id: "penghapusan",
    nama: "Penghapusan",
    urutan: 9,
    status: "segera",
    fase: 6,
    ringkas: "SK penghapusan & arsip aset terhapus dari daftar barang.",
    deskripsi:
      "Penghapusan BMN dari daftar barang berdasarkan SK penghapusan — menindaklanjuti "
      + "pemindahtanganan, pemusnahan, atau sebab lain (hilang, force majeure). Aset "
      + "berklasifikasi 'Tidak Ditemukan' hasil inventarisasi menjadi kandidat usulan.",
    fitur: [
      "Kandidat penghapusan dari klasifikasi Tidak Ditemukan (sudah tercatat rapi per sub-klasifikasi)",
      "Registrasi SK penghapusan + lampiran",
      "Arsip aset terhapus (tetap bisa ditelusuri, keluar dari daftar aktif)",
    ],
    integrasi: ["Klasifikasi tidak ditemukan + uraian + kronologis dari inventarisasi = berkas usulan siap pakai"],
  },
  {
    id: "wasdal",
    nama: "Pengawasan & Pengendalian",
    urutan: 10,
    status: "segera",
    fase: 6,
    ringkas: "Pemantauan ketertiban pengelolaan & tindak lanjut audit.",
    deskripsi:
      "Pembinaan, pengawasan, dan pengendalian (wasdal): pemantauan ketertiban penatausahaan "
      + "seluruh modul, penelusuran audit trail, dan pengelolaan tindak lanjut temuan audit.",
    fitur: [
      "Dasbor ketertiban per satker/kegiatan (kelengkapan data, foto, dokumen)",
      "Register temuan audit + status tindak lanjut",
      "Penelusuran audit trail lintas modul (fondasinya sudah berjalan)",
    ],
    integrasi: ["Audit trail per field yang sudah ada menjadi sumber penelusuran"],
  },
];

// Ringkasan fase roadmap — dipakai dialog konsep & dokumentasi.
export const FASE_ROADMAP = {
  1: "Fase 1 — sekarang: pematangan Penatausahaan › Inventarisasi Aset",
  2: "Fase 2: Penatausahaan penuh — Pembukuan, Pelaporan, Inventarisasi Persediaan",
  3: "Fase 3: Penggunaan (aset pegawai/BAST) + Pengamanan & Pemeliharaan",
  4: "Fase 4: Perencanaan (RKBMN) + Pengadaan (pintu masuk data)",
  5: "Fase 5: Pemanfaatan + Penilaian",
  6: "Fase 6: Pemindahtanganan, Pemusnahan, Penghapusan + Wasdal penuh",
};

export const STATUS_LABELS = {
  aktif: "Aktif",
  sebagian: "Sebagian Aktif",
  segera: "Segera Hadir",
};
