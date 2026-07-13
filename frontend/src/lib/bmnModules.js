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
      "✅ Stock opname: selisih → penyesuaian otomatis + kertas kerja & BAOF PDF + pengingat semesteran",
      "✅ Impor/ekspor master + Kartu Barang PDF (riwayat + saldo berjalan)",
      "✅ Transaksi massal per dokumen (satu bukti, banyak barang)",
      "✅ Filter Lokasi/Gudang di daftar master + laporan posisi per gudang",
      "✅ Pindah gudang per barang ber-jurnal (lokasi asal → tujuan tercatat, stok & FIFO tak berubah)",
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
    ringkas: "Hub arsip, LBKP, Posisi BMN di Neraca, rekonsiliasi XLSX, CaLBMN pra-isi, dan LKB sudah bisa dibuka.",
    deskripsi:
      "Pelaporan BMN berkala: Laporan Barang Kuasa Pengguna (LBKP) semesteran & tahunan, "
      + "laporan kondisi barang, serta dukungan rekonsiliasi dengan SIMAK/SAKTI. Saat ini "
      + "13+ laporan inventarisasi sudah berjalan di modul Inventarisasi Aset; modul ini "
      + "akan menyatukannya menjadi arsip laporan lintas kegiatan & lintas periode.",
    dasarHukum: [PENATAUSAHAAN_DASAR_HUKUM],
    fitur: [
      "✅ Posisi BMN di Neraca (per golongan, intra/ekstra + persediaan FIFO)",
      "✅ LBKP semesteran/tahunan per golongan (saldo awal–mutasi–akhir) + rekonsiliasi XLSX",
      "✅ CaLBMN pra-isi bab I–V per periode (struktur PMK 181; bahan penyusunan — final via SAKTI)",
      "✅ LKB — Laporan Kondisi Barang (rincian per NUP + ringkasan B/RR/RB per golongan, format LKBT-PKPB1)",
      "✅ Periode pelaporan ber-kunci (Semester I/II/Tahunan; terkunci = LBKP & CaLBMN berpenanda FINAL; buka kembali wajib beralasan)",
      "✅ Tenggat penyampaian konfigurabel per periode (surat DJKN/K/L) dengan pengingat sisa hari / lewat tenggat",
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
    status: "sebagian",
    fase: 4,
    ringkas: "Kandidat RKBMN pemeliharaan (saringan kelayakan PMK 153/2021 + riwayat biaya) sudah bisa dibuka.",
    deskripsi:
      "Perencanaan Kebutuhan BMN (RKBMN): usulan kebutuhan pengadaan dan pemeliharaan dari "
      + "unit, ditimbang terhadap Standar Barang & Standar Kebutuhan (SBSK) serta data "
      + "eksisting hasil inventarisasi.",
    dasarHukum: [
      "PMK No. 153/PMK.06/2021 — RKBMN",
      "PMK 138 Tahun 2024 — SBSK",
    ],
    fitur: [
      "✅ Kandidat RKBMN pemeliharaan: saringan kelayakan (Baik/RR vs rusak berat/idle) + riwayat biaya per aset",
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
    status: "sebagian",
    fase: 4,
    ringkas: "Register usulan RKBMN → telaah → DIPA → realisasi + sanding per akun & triwulan + kalender tenggat.",
    deskripsi:
      "Tindak lanjut RKBMN ke dalam penganggaran (titik 'Integrasi' siklus resmi, "
      + "PMK 62/2023 + PMK 153/2021). Tahap awal: register usulan berstatus — nilai "
      + "tercatat per tahap (usulan → disetujui telaah → DIPA → realisasi) dengan "
      + "tautan aset/NUP; kanal resmi tetap SIMAN V2 (RKBMN) dan SAKTI (RKA/DIPA).",
    dasarHukum: [
      "PMK No. 153/PMK.06/2021 — RKBMN (keterkaitan penganggaran)",
      "PMK 62 Tahun 2023 jo. 107/2024 & 41/2026 — perencanaan & pelaksanaan anggaran",
    ],
    fitur: [
      "✅ Register usulan berstatus: diusulkan → disetujui telaah → masuk DIPA → terealisasi",
      "✅ Nilai per tahap + serapan (realisasi/DIPA) + akun BAS 53x/523 + tautan aset",
      "✅ Sanding rencana vs realisasi per akun BAS (usulan/disetujui/DIPA/realisasi + serapan)",
      "✅ Sanding realisasi per triwulan per tahun anggaran (kumulatif + serapan kumulatif)",
      "✅ Ekspor CSV register usulan (nilai per tahap, akun BAS, status)",
      "✅ Kalender penganggaran konfigurabel: tahapan ber-tenggat + pengingat lewat/≤30 hari",
    ],
    integrasi: ["Menjembatani RKBMN (Perencanaan) dengan realisasi (Pengadaan); usulan dapat ditautkan ke aset"],
  },
  {
    id: "pengadaan",
    nama: "Pengadaan",
    urutan: 3,
    status: "sebagian",
    fase: 4,
    ringkas: "Register perolehan per BAST/kontrak + checklist dokumen + tautan aset.",
    deskripsi:
      "Pencatatan perolehan BMN baru (pembelian, hibah masuk, transfer masuk, "
      + "pembangunan — Perpres 16/2018 jo. 46/2025, pustaka §10). Tahap awal: register "
      + "perolehan per dokumen BAST/kontrak dengan checklist kelengkapan dokumen sumber "
      + "(penangkal temuan BPK \"BAST tercecer\"), tautan barang ke aset master, dan "
      + "penanda ekstrakomptabel di bawah ambang PMK 181/2016; pencatatan resmi tetap "
      + "di SAKTI.",
    dasarHukum: ["Perpres 16/2018 jo. Perpres 46/2025 — Pengadaan Barang/Jasa Pemerintah"],
    fitur: [
      "✅ Register perolehan per dokumen (jenis 101/102/103/105, penyedia, kontrak, BAST, daftar barang)",
      "✅ Checklist dokumen sumber per jenis (kontrak/BAPHP/BAST/kuitansi/SP2D; hibah: naskah + MPHL-BJS)",
      "✅ Tautan barang → aset master + penanda ekstrakomptabel PMK 181",
      "✅ Lampiran berkas per perolehan: scan kontrak/BAPHP/BAST/kuitansi/SP2D (PDF/gambar)",
      "✅ Ekspor CSV register perolehan (nilai, dokumen kurang, lampiran)",
      "✅ Tautan paket perolehan → usulan Penganggaran (snapshot uraian/DIPA/tahun; jembatan #117 ↔ #115)",
      "Auto-daftar draft aset baru dari perolehan (menyusul)",
    ],
    integrasi: ["Menjadi pintu masuk data master aset & batch persediaan baru; tersambung register penganggaran (#115)"],
  },
  {
    id: "penggunaan",
    nama: "Penggunaan",
    urutan: 4,
    status: "sebagian",
    fase: 3,
    ringkas: "Rekap pemegang, BMN idle, register SK PSP, dan tiket proses 4 rezim PMK 40/2024 sudah bisa dibuka.",
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
      "✅ Rekap aset per pemegang lintas kegiatan + kelengkapan BAST/NIP",
      "✅ Daftar Barang yang Digunakan per pemegang (PDF lampiran BAST, tanda tangan pemegang + KPB)",
      "✅ Daftar pantau BMN idle (PMK 120/2024): kandidat otomatis + tiket klarifikasi → usul serah → diserahkan + ekspor CSV register tiket",
      "✅ Register SK penetapan penggunaan multi-aset (PSP/alih status/sementara/pihak lain/bersama) + cakupan aset ter-PSP + ekspor CSV",
      "✅ Arsip scan SK penetapan + dokumen pendukung per register (PDF/gambar)",
      "✅ Tiket proses 4 rezim PMK 40/2024 (alih status/sementara/pihak lain/bersama) ber-pipeline + pengingat perpanjangan ≤90 hari + ekspor CSV",
      "✅ BAST penetapan status penggunaan PDF siap tanda tangan per SK (kop surat + tabel aset)",
      "✅ Alur pengajuan PSP berstatus: draf usulan → diajukan → ditetapkan (SK wajib) / ditolak / dikembalikan",
    ],
    integrasi: ["Field pengguna, NIP, jabatan, dan BAST dari modul inventarisasi menjadi data awal"],
  },
  {
    id: "pemanfaatan",
    nama: "Pemanfaatan",
    urutan: 5,
    status: "sebagian",
    fase: 5,
    ringkas: "Register perjanjian 6 bentuk (jaga dokumen persetujuan/NTPN + jatuh tempo ≤60 hari) sudah bisa dibuka.",
    deskripsi:
      "Pemanfaatan BMN oleh pihak lain sesuai PMK No. 115/PMK.06/2020: Sewa, Pinjam Pakai, "
      + "Kerjasama Pemanfaatan (KSP), Bangun Guna Serah (BGS), Bangun Serah Guna (BSG), "
      + "Kerjasama Penyediaan Infrastruktur (KSPI), dan Kerjasama Terbatas Untuk Pembiayaan "
      + "Infrastruktur (KETUPI) — dengan jadwal jatuh tempo dan pemantauan PNBP. Perjanjian "
      + "KSP/BGS/BSG dapat lahir dari fasilitas penyiapan & pelaksanaan transaksi "
      + "(PMK 18 Tahun 2024; khusus IKN: PMK 139/PMK.08/2022) — pendampingan, bukan bentuk baru.",
    dasarHukum: [
      "PMK No. 115/PMK.06/2020 — Pemanfaatan BMN",
      "PMK 18 Tahun 2024 — Fasilitas Penyiapan & Pelaksanaan Transaksi Pemanfaatan BMN",
      "PMK 139/PMK.08/2022 — Fasilitas transaksi pemanfaatan/pemindahtanganan BMN dalam rangka IKN",
    ],
    fitur: [
      "✅ Registrasi perjanjian per bentuk: Sewa / Pinjam Pakai / KSP / BGS / BSG / KSPI / KETUPI",
      "✅ Penjaga dokumen (persetujuan Pengelola + perjanjian; sewa: NTPN) & status jatuh tempo ≤60 hari",
      "✅ Kontribusi tahunan ber-NTPN per tahun + pengingat tunggakan otomatis",
      "✅ Ekspor CSV register perjanjian (status + rekap kontribusi + jumlah lampiran)",
      "✅ Arsip scan dokumen per perjanjian (persetujuan/perjanjian/bukti setor — PDF/gambar)",
      "✅ Lampiran wasdal per perjanjian (laporan monitoring/BA peninjauan lapangan — arsip terpisah)",
      "✅ Atribut fasilitas transaksi (PMK 18/2024 / PMK 139/2022 IKN) pada perjanjian KSP/BGS-BSG",
    ],
    integrasi: ["Status pemanfaatan tampil di detail aset & laporan"],
  },
  {
    id: "penilaian",
    nama: "Penilaian",
    urutan: 6,
    status: "sebagian",
    fase: 5,
    ringkas: "Posisi penyusutan semesteran (PMK 65/2017) + register koreksi nilai/revaluasi per aset sudah bisa dibuka.",
    deskripsi:
      "Penilaian BMN untuk penyusunan neraca dan rencana pemindahtanganan/pemanfaatan: "
      + "nilai wajar, Revaluasi BMN, dan perhitungan penyusutan per golongan.",
    dasarHukum: [
      "PMK 99 Tahun 2024 — Penilaian oleh Penilai Pemerintah di Kemenkeu",
      "Perpres 75/2017 + PMK 118/PMK.06/2017 jo. 57/2018 jo. 107/2019 — Revaluasi BMN",
      "PMK 65/PMK.06/2017 — Penyusutan BMN",
    ],
    fitur: [
      "✅ Register koreksi nilai & hasil penilaian per aset (revaluasi/LHIP/BA, checklist tercatat di SAKTI) + ekspor CSV",
      "✅ Penyusutan garis lurus semesteran per golongan (PMK 65/2017; masa manfaat KMK 295/2019 jo. 266/2023) + daftar telaah",
      "✅ Referensi masa manfaat dapat dikelola (seed lengkap lampiran KMK)",
      "✅ Riwayat nilai per aset (read-only): perolehan → koreksi/revaluasi → nilai terkini",
    ],
    integrasi: ["Nilai perolehan dari master aset; hasil menyuplai pembukuan & pelaporan"],
  },
  {
    id: "pengamanan",
    nama: "Pengamanan",
    urutan: 7,
    status: "sebagian",
    fase: 3,
    ringkas: "Dasbor, register BMN bermasalah, arsip dokumen, checklist, dan polis asuransi sudah bisa dibuka.",
    deskripsi:
      "Pengamanan BMN pada tiga lapis (PP 27/2014 Ps. 42): Fisik (penjagaan, patok, "
      + "pagar), Administrasi (kelengkapan dokumen & pencatatan), dan Hukum (sertifikat, "
      + "BPKB, dokumen kepemilikan) — ditambah Asuransi BMN untuk aset strategis.",
    dasarHukum: [
      "PP 27/2014 jo. PP 28/2020 Ps. 42-43 — kewajiban pengamanan & penyimpanan bukti kepemilikan",
      "PMK 43 Tahun 2025 — Pengasuransian BMN (mencabut PMK 97/2019)",
    ],
    fitur: [
      "✅ Dasbor kelengkapan data aset (foto/register/lokasi/pengguna/BAST) + daftar pantau sengketa",
      "✅ Register BMN bermasalah berstatus: identifikasi → mediasi → blokir → litigasi → selesai (bahan laporan wasdal) + ekspor CSV",
      "✅ Arsip dokumen kepemilikan per aset: sertipikat/BPKB/STNK/IMB-PBG + lokasi penyimpanan (Ps. 43) + scan + pengingat kedaluwarsa + ekspor CSV",
      "✅ Status sertipikasi tanah per dokumen sertipikat (belum/proses/K1-K4/SHP terbit)",
      "✅ Checklist pengamanan per aset per jenis (butir fisik/administrasi/hukum + skor + tanggal cek) + ekspor CSV",
      "✅ Register polis Asuransi BMN: nomor/penanggung/kategori objek/nilai/premi + pengingat masa berlaku (PMK 43/2025) + ekspor CSV",
    ],
    integrasi: ["Data sengketa & kelengkapan dokumen dari inventarisasi menjadi daftar pantau"],
  },
  {
    id: "pemeliharaan",
    nama: "Pemeliharaan",
    urutan: 8,
    status: "sebagian",
    fase: 3,
    ringkas: "Catatan riwayat & biaya pemeliharaan per aset (bahan DHPB) sudah bisa dibuka.",
    deskripsi:
      "Pemeliharaan BMN agar selalu dalam kondisi siap pakai (PP 27/2014 Ps. 46-47): "
      + "riwayat per kejadian (ringan/sedang/berat), rekap biaya per tahun anggaran "
      + "sebagai bahan Daftar Hasil Pemeliharaan Barang (DHPB), dan jadwal berkala — "
      + "menyuplai balik RKBMN pemeliharaan pada tahap perencanaan.",
    dasarHukum: [DASAR_HUKUM_UMUM[1]],
    fitur: [
      "✅ Riwayat & biaya pemeliharaan per kejadian per aset (kondisi sebelum/sesudah)",
      "✅ Rekap biaya per tahun anggaran + per jenis + aset terboros",
      "✅ Kondisi aset ter-update dari hasil pemeliharaan",
      "✅ Penanda telaah kapitalisasi (ambang PMK 181/2016)",
      "✅ DHPB semesteran/tahunan PDF (laporan KPB → Pengguna Barang)",
      "✅ Jadwal berkala per aset (jatuh tempo + status terlambat/segera) + ekspor CSV",
      "✅ Ekspor CSV riwayat (biaya, kondisi, telaah kapitalisasi, bukti)",
    ],
    integrasi: ["Riwayat biaya menjadi dasar usulan RKBMN pemeliharaan (Perencanaan)"],
  },
  {
    id: "pemindahtanganan",
    nama: "Pemindahtanganan",
    urutan: 9,
    status: "sebagian",
    fase: 6,
    ringkas: "Register usulan 4 bentuk berstatus (dokumen wajib per tahap, tenggat lelang 6 bulan) sudah bisa dibuka.",
    deskripsi:
      "Pemindahtanganan BMN sesuai diagram resmi: Penjualan (lelang), Hibah, Tukar Menukar, "
      + "dan Penyertaan Modal — dari usulan, persetujuan, risalah, hingga BAST keluar.",
    dasarHukum: [
      "PMK 111/PMK.06/2016 jo. PMK 165/PMK.06/2021 — Pemindahtanganan BMN",
      "UU 1/2004 Ps. 45–46 + PP 27/2014 jo. PP 28/2020 Ps. 55–58 — ambang persetujuan",
    ],
    fitur: [
      "✅ Register usulan multi-aset berstatus: diusulkan → disetujui → dilaksanakan → selesai (SK Penghapusan)",
      "✅ Dokumen wajib per tahap (persetujuan; risalah/BAST/naskah/PP + NTPN utk penjualan; SK) + peringatan tenggat lelang 6 bulan",
      "✅ Arsip scan risalah lelang / naskah hibah / BAST / bukti setor per usulan (PDF/gambar)",
      "✅ Ekspor CSV register usulan (bentuk + status + dokumen per tahap + ringkas aset)",
      "✅ Saran jenjang persetujuan (indikatif) dari jenis BMN + nilai wajar: Pengelola/Presiden/DPR (UU 1/2004 & PP 27/2014)",
      "Aset otomatis keluar dari daftar aktif setelah selesai",
    ],
    integrasi: ["Berbagi alur persetujuan & dokumen dengan pemusnahan/penghapusan"],
  },
  {
    id: "pemusnahan",
    nama: "Pemusnahan",
    urutan: 10,
    status: "sebagian",
    fase: 6,
    ringkas: "Register BA Pemusnahan (persetujuan wajib, aset rusak berat) sudah bisa dibuka.",
    deskripsi:
      "Pemusnahan BMN yang tidak dapat digunakan/dimanfaatkan/dipindahtangankan: usulan "
      + "(kandidat otomatis dari aset rusak berat hasil inventarisasi), persetujuan, dan "
      + "berita acara pemusnahan.",
    dasarHukum: ["PMK 83/PMK.06/2016 — Pemusnahan & Penghapusan BMN"],
    fitur: [
      "✅ Register BA Pemusnahan multi-aset (nomor persetujuan wajib; cara dibakar/dihancurkan/dll; objek dibatasi Rusak Berat)",
      "✅ PDF Berita Acara siap tanda tangan (kop surat, tabel aset + nilai, blok pelaksana/saksi/KPB)",
      "✅ Tindak lanjut otomatis: usulan penghapusan per aset BA (satu klik, aset ber-usulan aktif dilewati)",
      "✅ Lampiran bukti per BA: foto pelaksanaan + scan BA bertanda tangan (PDF/gambar)",
      "✅ Ekspor CSV register BA (cara, nilai perolehan, lampiran)",
      "Kandidat pemusnahan otomatis dari kondisi Rusak Berat + tindak lanjut inventarisasi",
    ],
    integrasi: ["Kondisi & tindak lanjut dari modul inventarisasi menjadi pintu masuk"],
  },
  {
    id: "penghapusan",
    nama: "Penghapusan",
    urutan: 11,
    status: "sebagian",
    fase: 6,
    ringkas: "Kandidat usul hapus + tiket usulan berstatus (usul → proses → SK, PMK 83/2016) sudah bisa dibuka.",
    deskripsi:
      "Penghapusan BMN dari daftar barang berdasarkan SK penghapusan — menindaklanjuti "
      + "pemindahtanganan, pemusnahan, atau sebab lain (hilang, force majeure). Aset "
      + "berklasifikasi 'Tidak Ditemukan' hasil inventarisasi menjadi kandidat usulan.",
    dasarHukum: ["PMK 83/PMK.06/2016 — Pemusnahan & Penghapusan BMN"],
    fitur: [
      "✅ Kandidat per jalur: Tidak Ditemukan → penelusuran+TGR; Rusak Berat → pemusnahan/pemindahtanganan",
      "✅ Tiket usulan berstatus: diusulkan → diproses → SK terbit/ditolak (nomor & tanggal SK terarsip)",
      "✅ Lampiran per usulan: scan SK penghapusan + dokumen pendukung (PDF/gambar)",
      "✅ Ekspor CSV register usulan (jalur + status + SK + jumlah lampiran)",
      "✅ Jejak Aset Terhapus: arsip read-only dari log audit (kode/NUP/nama/nilai/oleh/waktu) — aset yang dihapus permanen tetap tertelusur",
    ],
    integrasi: ["Klasifikasi tidak ditemukan + uraian + kronologis dari inventarisasi = berkas usulan siap pakai"],
  },
  {
    id: "wasdal",
    nama: "Pembinaan, Pengawasan & Pengendalian",
    urutan: 12,
    status: "sebagian",
    fase: 6,
    ringkas: "Dasbor pemantauan 5 objek wasdal KPB + register penertiban 15 hari kerja.",
    deskripsi:
      "Wasdal melingkupi seluruh siklus (PMK 207/PMK.06/2021). Tahap awal: dasbor "
      + "pemantauan tingkat KPB — mesin aturan membaca register yang sudah ada dan "
      + "mengelompokkan temuan per lima objek pemantauan (penggunaan, pemanfaatan, "
      + "pemindahtanganan & penghapusan, penatausahaan, pengamanan & pemeliharaan) "
      + "sebagai bahan pra-isi laporan wasdal; kanal resmi tetap Modul Wasdal SIMAN v2.",
    dasarHukum: ["PMK 207/PMK.06/2021 — Wasdal BMN"],
    fitur: [
      "✅ Dasbor pemantauan per 5 objek wasdal (temuan otomatis dari register)",
      "✅ Aturan: BAST kosong, perjanjian berakhir/dokumen kurang, usulan berlarut, kandidat belum diusulkan, data belum lengkap, sengketa, rusak tanpa pemeliharaan",
      "✅ Laporan Hasil Pemantauan PDF pra-isi (rekap 5 objek + rincian temuan + tanda tangan) — kanal resmi tetap SIMAN v2",
      "✅ Register penertiban ber-tenggat 15 hari kerja (sumber pemantauan/permintaan Pengelola/APIP-BPK, peringatan lewat tenggat, tindak lanjut tercatat) + ekspor CSV",
      "✅ Pemantauan insidentil 10+5 hari kerja (pemicu masyarakat/media/audit, alur berjalan → BA terbit → dilaporkan) + PDF BA siap tanda tangan + ekspor CSV",
      "✅ Arsip lampiran per tiket insidentil (scan BA bertanda tangan + foto temuan)",
      "Generator laporan formulir resmi Lampiran PMK 207 (menyusul)",
      "Portofolio aset & analisis SBSK (menyusul)",
    ],
    integrasi: ["Membaca register pemanfaatan, penghapusan, pemindahtanganan, pemeliharaan, dan data aset tanpa input ganda"],
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
