/**
 * Registry modul Siklus Pengelolaan BMN — SATU sumber kebenaran untuk
 * "rumah modul" (ModuleHomePage) dan roadmap pengembangan bertahap.
 *
 * Mengikuti DIAGRAM RESMI Kemenkeu "Siklus Pengelolaan Barang Milik
 * Negara/Daerah" (UU 1/2004, PP 27/2014 jo. PP 28/2020) — 12 tahap searah
 * jarum jam: Perencanaan Kebutuhan → Penganggaran → Pengadaan → Penggunaan →
 * Pemanfaatan → Penilaian → Pengamanan → Pemeliharaan → PENATAUSAHAAN →
 * Pemindahtanganan → Pemusnahan → Penghapusan, dengan Pembinaan-Pengawasan-
 * Pengendalian (wasdal) melingkupi seluruh siklus. Setiap tahap membawa
 * PMK-nya sendiri (field `dasarHukum`).
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

// ── Asas pengelolaan BMN (legenda diagram resmi) ──────────────────────
export const ASAS_PENGELOLAAN = [
  "Fungsional",
  "Kepastian Hukum",
  "Transparansi & Keterbukaan",
  "Efisiensi",
  "Akuntabilitas",
  "Kepastian Nilai",
];

export const DASAR_HUKUM_UMUM = [
  "UU 1/2004 — Perbendaharaan Negara",
  "PP 27/2014 jo. PP 28/2020 — Pengelolaan BMN/D",
];

// ── Sub-modul PENATAUSAHAAN (poros — tempat kita berada) ──────────────
// Dasar hukum tahap: PMK No. 181/PMK.06/2016 (Penatausahaan BMN).
export const PENATAUSAHAAN_DASAR_HUKUM = "PMK No. 181/PMK.06/2016 — Penatausahaan BMN";

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
    dasarHukum: [PENATAUSAHAAN_DASAR_HUKUM, "SE-17/MK.1/2024 — Pelaksanaan Inventarisasi BMN"],
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
    dasarHukum: [PENATAUSAHAAN_DASAR_HUKUM],
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
    status: "sebagian",
    fase: 2,
    ringkas: "Berjalan: master, transaksi masuk/keluar FIFO, peringatan + nota dinas, laporan, opname + BAOF. Menyusul: gudang & impor massal.",
    deskripsi:
      "Manajemen barang persediaan (aset lancar, kodefikasi berawalan '1') — pencatatan "
      + "perpetual + penilaian FIFO per layer selaras SAKTI (PMK 234/2020). Inti modul "
      + "sudah berjalan (#77–#83): master ber-layer FIFO, transaksi masuk/keluar dengan "
      + "jurnal berjejak, peringatan kritis/kedaluwarsa + nota dinas, laporan posisi/"
      + "mutasi, dan stock opname dengan BAOF 3 penandatangan.",
    dasarHukum: [PENATAUSAHAAN_DASAR_HUKUM, "PMK 234/PMK.05/2020 — FIFO (kebijakan akuntansi)"],
    fitur: [
      "✅ Master persediaan: kode '1' 16 digit (nomor urut otomatis), NUP otomatis, batas kritis, kedaluwarsa",
      "✅ Transaksi masuk/keluar FIFO per layer + jurnal (jenis memetakan kode SAKTI M0x/K0x)",
      "✅ Peringatan habis/kritis/kedaluwarsa + Nota Dinas PDF otomatis",
      "✅ Laporan Posisi (per kelompok kodefikasi) & Mutasi periode (dari jurnal)",
      "✅ Stock opname: selisih → penyesuaian otomatis + kertas kerja & BAOF PDF",
      "Menyusul: gudang (distribusi/transfer), impor massal master, transaksi massal per dokumen",
    ],
    integrasi: [
      "Berbagi kodefikasi barang, satker, dan kop surat dengan modul aset",
      "Jurnal persediaan menjadi sumber laporan & rekonsiliasi (selaras SAKTI)",
    ],
  },
  {
    id: "pelaporan",
    nama: "Pelaporan",
    status: "sebagian",
    fase: 2,
    ringkas: "Hub arsip laporan lintas kegiatan + laporan persediaan sudah bisa dibuka — LBKP & rekonsiliasi menyusul.",
    deskripsi:
      "Pelaporan BMN berkala: Laporan Barang Kuasa Pengguna (LBKP) semesteran & tahunan, "
      + "laporan kondisi barang, serta dukungan rekonsiliasi dengan SIMAK/SAKTI. Saat ini "
      + "13+ laporan inventarisasi sudah berjalan di modul Inventarisasi Aset; modul ini "
      + "akan menyatukannya menjadi arsip laporan lintas kegiatan & lintas periode.",
    dasarHukum: [PENATAUSAHAAN_DASAR_HUKUM],
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

// ── Tahap siklus BMN (di luar penatausahaan) — urutan sesuai diagram ──
export const SIKLUS_MODULES = [
  {
    id: "perencanaan",
    nama: "Perencanaan Kebutuhan",
    urutan: 1,
    status: "segera",
    fase: 4,
    ringkas: "RKBMN & SBSK: kebutuhan pengadaan/pemeliharaan berbasis data aset.",
    deskripsi:
      "Perencanaan Kebutuhan BMN (RKBMN): usulan kebutuhan pengadaan dan pemeliharaan dari "
      + "unit, ditimbang terhadap Standar Barang & Standar Kebutuhan (SBSK) serta data "
      + "eksisting hasil inventarisasi.",
    dasarHukum: [
      "PMK No. 153/PMK.06/2021 — RKBMN",
      "PMK 138 Tahun 2024 — SBSK",
    ],
    fitur: [
      "Penyusunan RKBMN pengadaan & pemeliharaan per unit + persetujuan berjenjang",
      "Analisis SBSK: sanding usulan vs standar barang & kebutuhan",
      "Sanding usulan vs data aset eksisting (jumlah, kondisi, umur)",
    ],
    integrasi: ["Data kondisi & jumlah aset dari Inventarisasi menjadi dasar analisis kebutuhan"],
  },
  {
    id: "penganggaran",
    nama: "Penganggaran",
    urutan: 2,
    status: "segera",
    fase: 4,
    ringkas: "Menjembatani RKBMN ke anggaran (RKA) — integrasi perencanaan-penganggaran.",
    deskripsi:
      "Tindak lanjut RKBMN ke dalam penganggaran: pagu kebutuhan BMN per unit/tahun, "
      + "penandaan usulan yang lolos anggaran, dan pemantauan realisasi terhadap rencana — "
      + "titik 'Integrasi' pada siklus resmi Kemenkeu.",
    dasarHukum: ["PMK No. 153/PMK.06/2021 — RKBMN (keterkaitan penganggaran)"],
    fitur: [
      "Pagu kebutuhan BMN per unit & tahun anggaran",
      "Status usulan RKBMN: diusulkan → disetujui → dianggarkan → direalisasikan",
      "Sanding realisasi pengadaan vs rencana & anggaran",
    ],
    integrasi: ["Menjembatani RKBMN (Perencanaan) dengan realisasi (Pengadaan)"],
  },
  {
    id: "pengadaan",
    nama: "Pengadaan",
    urutan: 3,
    status: "segera",
    fase: 4,
    ringkas: "Perolehan baru: kontrak, BAST, penerimaan → otomatis masuk daftar aset.",
    deskripsi:
      "Pencatatan perolehan BMN baru (pembelian, hibah masuk, transfer masuk): dokumen "
      + "sumber (kontrak, SPM/SP2D, BAST), penerimaan barang, dan pendaftaran otomatis "
      + "ke master aset/persediaan — pola dokumen sumber mengadopsi KERJA-BARENG.",
    dasarHukum: ["Perpres 16/2018 jo. Perpres 46/2025 — Pengadaan Barang/Jasa Pemerintah"],
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
    urutan: 4,
    status: "sebagian",
    fase: 3,
    ringkas: "Rekap aset per pemegang (+kelengkapan BAST) sudah bisa dibuka — PSP/alih status/BMN idle menyusul.",
    deskripsi:
      "Penggunaan BMN sesuai PMK 40 Tahun 2024: Penetapan Status Penggunaan (PSP), Alih "
      + "Status Penggunaan, Penggunaan Sementara, Penggunaan BMN untuk dioperasikan Pihak "
      + "Lain, dan Penggunaan Bersama — plus pemantauan BMN idle (PMK 120 Tahun 2024) dan "
      + "penatausahaan aset di tangan pegawai (melanjutkan data pengguna + BAST inventarisasi).",
    dasarHukum: [
      "PMK 40 Tahun 2024 — Penggunaan BMN",
      "PMK 120 Tahun 2024 — BMN Idle",
    ],
    fitur: [
      "Pengajuan & SK Penetapan Status Penggunaan (PSP)",
      "Alih status, penggunaan sementara, dioperasikan pihak lain, penggunaan bersama",
      "Daftar aset per pegawai/jabatan + BAST digital (benihnya sudah ada)",
      "Pemantauan & tindak lanjut BMN idle",
    ],
    integrasi: ["Field pengguna, NIP, jabatan, dan BAST dari modul inventarisasi menjadi data awal"],
  },
  {
    id: "pemanfaatan",
    nama: "Pemanfaatan",
    urutan: 5,
    status: "segera",
    fase: 5,
    ringkas: "Sewa, Pinjam Pakai, KSP, BGS/BSG, KSPI, KETUPI — jadwal & PNBP.",
    deskripsi:
      "Pemanfaatan BMN oleh pihak lain sesuai PMK No. 115/PMK.06/2020: Sewa, Pinjam Pakai, "
      + "Kerjasama Pemanfaatan (KSP), Bangun Guna Serah (BGS), Bangun Serah Guna (BSG), "
      + "Kerjasama Penyediaan Infrastruktur (KSPI), dan Kerjasama Terbatas Untuk Pembiayaan "
      + "Infrastruktur (KETUPI) — termasuk Pemanfaatan dengan Fasilitas (PDF, PMK 18 Tahun "
      + "2024), dengan jadwal jatuh tempo dan pemantauan PNBP.",
    dasarHukum: [
      "PMK No. 115/PMK.06/2020 — Pemanfaatan BMN",
      "PMK 18 Tahun 2024 — Pemanfaatan dengan Fasilitas (PDF)",
    ],
    fitur: [
      "Registrasi perjanjian per bentuk: Sewa / Pinjam Pakai / KSP / BGS / BSG / KSPI / KETUPI / PDF",
      "Kalender jatuh tempo & pengingat perpanjangan",
      "Pencatatan PNBP per perjanjian",
      "Arsip dokumen perjanjian per aset",
    ],
    integrasi: ["Status pemanfaatan tampil di detail aset & laporan"],
  },
  {
    id: "penilaian",
    nama: "Penilaian",
    urutan: 6,
    status: "segera",
    fase: 5,
    ringkas: "Nilai wajar, revaluasi BMN, dan penyusutan.",
    deskripsi:
      "Penilaian BMN untuk penyusunan neraca dan rencana pemindahtanganan/pemanfaatan: "
      + "nilai wajar, Revaluasi BMN, dan perhitungan penyusutan per golongan.",
    dasarHukum: ["PMK 97/PMK.06/2019 — Revaluasi BMN"],
    fitur: [
      "Pencatatan hasil penilaian/revaluasi per aset",
      "Penyusutan otomatis per golongan (masa manfaat standar)",
      "Riwayat nilai: perolehan → revaluasi → buku",
    ],
    integrasi: ["Nilai perolehan dari master aset; hasil menyuplai pembukuan & pelaporan"],
  },
  {
    id: "pengamanan",
    nama: "Pengamanan",
    urutan: 7,
    status: "sebagian",
    fase: 3,
    ringkas: "Dasbor tertib administrasi (kelengkapan foto/register/lokasi/pengguna/BAST) + pantau sengketa sudah bisa dibuka.",
    deskripsi:
      "Pengamanan BMN pada tiga lapis sesuai diagram resmi: Fisik (penjagaan, stiker, "
      + "pagar), Administrasi (kelengkapan dokumen & pencatatan), dan Hukum (sertifikat, "
      + "BPKB, dokumen kepemilikan) — ditambah Asuransi BMN untuk aset strategis.",
    dasarHukum: ["PMK 97/PMK.06/2019 — Asuransi BMN (pengamanan aset tertentu)"],
    fitur: [
      "Arsip dokumen kepemilikan per aset (sertifikat, BPKB, IMB)",
      "Dasbor kelengkapan pengamanan fisik / administrasi / hukum",
      "Registrasi polis Asuransi BMN + masa berlaku",
      "Pemantauan aset bermasalah (sengketa — datanya sudah dicatat inventarisasi)",
    ],
    integrasi: ["Data sengketa & kelengkapan dokumen dari inventarisasi menjadi daftar pantau"],
  },
  {
    id: "pemeliharaan",
    nama: "Pemeliharaan",
    urutan: 8,
    status: "segera",
    fase: 3,
    ringkas: "Jadwal, riwayat, dan biaya pemeliharaan per aset.",
    deskripsi:
      "Pemeliharaan BMN agar selalu dalam kondisi siap pakai: jadwal pemeliharaan berkala, "
      + "riwayat perbaikan, dan biaya pemeliharaan per aset — menyuplai balik RKBMN "
      + "pemeliharaan pada tahap perencanaan.",
    dasarHukum: [DASAR_HUKUM_UMUM[1]],
    fitur: [
      "Jadwal pemeliharaan berkala per aset/kelompok",
      "Riwayat & biaya pemeliharaan (per kejadian, per tahun)",
      "Kondisi aset ter-update dari hasil pemeliharaan",
    ],
    integrasi: ["Riwayat biaya menjadi dasar usulan RKBMN pemeliharaan (Perencanaan)"],
  },
  {
    id: "pemindahtanganan",
    nama: "Pemindahtanganan",
    urutan: 9,
    status: "segera",
    fase: 6,
    ringkas: "Penjualan, Hibah, Tukar Menukar, Penyertaan Modal.",
    deskripsi:
      "Pemindahtanganan BMN sesuai diagram resmi: Penjualan (lelang), Hibah, Tukar Menukar, "
      + "dan Penyertaan Modal — dari usulan, persetujuan, risalah, hingga BAST keluar.",
    dasarHukum: [
      "PMK 111/PMK.06/2016 jo. PMK 165/PMK.06/2021 — Pemindahtanganan BMN",
    ],
    fitur: [
      "Alur usulan → persetujuan → pelaksanaan per jenis: Penjualan / Hibah / Tukar Menukar / Penyertaan Modal",
      "Arsip risalah lelang / naskah hibah / BAST keluar",
      "Aset otomatis keluar dari daftar aktif setelah selesai",
    ],
    integrasi: ["Berbagi alur persetujuan & dokumen dengan pemusnahan/penghapusan"],
  },
  {
    id: "pemusnahan",
    nama: "Pemusnahan",
    urutan: 10,
    status: "segera",
    fase: 6,
    ringkas: "Usulan & berita acara pemusnahan aset rusak berat.",
    deskripsi:
      "Pemusnahan BMN yang tidak dapat digunakan/dimanfaatkan/dipindahtangankan: usulan "
      + "(kandidat otomatis dari aset rusak berat hasil inventarisasi), persetujuan, dan "
      + "berita acara pemusnahan.",
    dasarHukum: ["PMK 83/PMK.06/2016 — Pemusnahan & Penghapusan BMN"],
    fitur: [
      "Kandidat pemusnahan otomatis dari kondisi Rusak Berat + tindak lanjut inventarisasi",
      "Alur usulan → persetujuan → BA pemusnahan (dengan foto bukti)",
    ],
    integrasi: ["Kondisi & tindak lanjut dari modul inventarisasi menjadi pintu masuk"],
  },
  {
    id: "penghapusan",
    nama: "Penghapusan",
    urutan: 11,
    status: "segera",
    fase: 6,
    ringkas: "SK penghapusan & arsip aset terhapus dari daftar barang.",
    deskripsi:
      "Penghapusan BMN dari daftar barang berdasarkan SK penghapusan — menindaklanjuti "
      + "pemindahtanganan, pemusnahan, atau sebab lain (hilang, force majeure). Aset "
      + "berklasifikasi 'Tidak Ditemukan' hasil inventarisasi menjadi kandidat usulan.",
    dasarHukum: ["PMK 83/PMK.06/2016 — Pemusnahan & Penghapusan BMN"],
    fitur: [
      "Kandidat penghapusan dari klasifikasi Tidak Ditemukan (sudah tercatat rapi per sub-klasifikasi)",
      "Registrasi SK penghapusan + lampiran",
      "Arsip aset terhapus (tetap bisa ditelusuri, keluar dari daftar aktif)",
    ],
    integrasi: ["Klasifikasi tidak ditemukan + uraian + kronologis dari inventarisasi = berkas usulan siap pakai"],
  },
  {
    id: "wasdal",
    nama: "Pembinaan, Pengawasan & Pengendalian",
    urutan: 12,
    status: "segera",
    fase: 6,
    ringkas: "Pemantauan, investigasi, portofolio aset, analisis SBSK, penertiban.",
    deskripsi:
      "Wasdal melingkupi seluruh siklus (PMK 207/PMK.06/2021) dengan lima kegiatan sesuai "
      + "diagram resmi: Pemantauan, Investigasi, Portofolio Aset, Analisis SBSK, dan "
      + "Penertiban — ditopang audit trail lintas modul yang sudah berjalan.",
    dasarHukum: ["PMK 207/PMK.06/2021 — Wasdal BMN"],
    fitur: [
      "Pemantauan ketertiban per satker/kegiatan (kelengkapan data, foto, dokumen)",
      "Register investigasi & temuan audit + status tindak lanjut (penertiban)",
      "Portofolio aset: komposisi, nilai, dan pemanfaatan lintas satker",
      "Analisis SBSK: sanding kepemilikan vs standar kebutuhan",
      "Penelusuran audit trail lintas modul (fondasinya sudah berjalan)",
    ],
    integrasi: ["Audit trail per field yang sudah ada menjadi sumber penelusuran"],
  },
];

// Ringkasan fase roadmap — dipakai dialog konsep & dokumentasi.
export const FASE_ROADMAP = {
  1: "Fase 1 — sekarang: pematangan Penatausahaan › Inventarisasi Aset",
  2: "Fase 2: Penatausahaan penuh — Pembukuan, Pelaporan, Inventarisasi Persediaan",
  3: "Fase 3: Penggunaan (PSP/aset pegawai/BMN idle) + Pengamanan + Pemeliharaan",
  4: "Fase 4: Perencanaan Kebutuhan (RKBMN/SBSK) + Penganggaran + Pengadaan",
  5: "Fase 5: Pemanfaatan + Penilaian",
  6: "Fase 6: Pemindahtanganan, Pemusnahan, Penghapusan + Wasdal penuh",
};

export const STATUS_LABELS = {
  aktif: "Aktif",
  sebagian: "Sebagian Aktif",
  segera: "Segera Hadir",
};
