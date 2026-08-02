/**
 * Rekomendasi KELENGKAPAN DOKUMEN & PERALATAN per golongan/bidang BMN.
 *
 * Sebelum berkas ini ada, tiap aset baru selalu lahir dengan lima baris yang
 * sama — "Buku Manual, Charger/Adapter, Kabel USB, Kartu Garansi, CD Driver" —
 * daftar yang masuk akal untuk laptop dan **tidak masuk akal untuk apa pun
 * yang lain**. Sebidang tanah tak punya kabel USB; gedung tak punya CD driver.
 * Akibatnya angka "0/5" pada setiap aset menagih barang yang memang tak
 * mungkin ada, dan kelengkapan yang benar-benar wajib (sertifikat, IMB, BPKB)
 * justru tak pernah diminta.
 *
 * Kini daftarnya DITURUNKAN dari kode barang. Aset yang belum berkode mulai
 * dari 0/0 — jujur "belum ditentukan" — dan terisi begitu kodefikasinya dipilih.
 *
 * ── Dasar penyusunan ────────────────────────────────────────────────────────
 * Dokumen kepemilikan mengikuti pengamanan ADMINISTRATIF BMN: sertifikat hak
 * pakai untuk tanah, IMB untuk bangunan, serta BPKB/STNK untuk kendaraan —
 * tata cara penyimpanannya diatur PMK 218/PMK.06/2015 tentang Tata Cara
 * Penyimpanan Dokumen Kepemilikan Barang Milik Negara. Pembagian golongan
 * mengikuti penggolongan BMN yang sama dengan KIB A–F (A Tanah, B Peralatan
 * dan Mesin, C Gedung dan Bangunan, D Jalan/Irigasi/Jaringan, E Aset Tetap
 * Lainnya, F KDP). Perlengkapan fisik kendaraan (kunci cadangan, dongkrak,
 * kunci roda, ban cadangan, segitiga pengaman, buku manual) mengikuti daftar
 * periksa serah terima kendaraan yang lazim dipakai.
 *
 * INI REKOMENDASI, BUKAN KEWAJIBAN YANG DIKUNCI. Tiap baris tetap bisa
 * dihapus dan baris lain bisa ditambah — satker punya kebiasaan berbeda, dan
 * memaksakan daftar tetap hanya memindahkan masalah lama ke bentuk baru.
 */

// Berlaku untuk SEMUA golongan: bukti bahwa barangnya sah dimiliki dan sudah
// diserahterimakan. Dua ini yang paling sering ditagih pemeriksa.
const DASAR = [
  "Dokumen Perolehan (Faktur/Kuitansi/Kontrak)",
  "Berita Acara Serah Terima (BAST)",
];

/**
 * Kunci = prefix kode barang. Pencocokan memakai prefix TERPANJANG lebih dulu
 * (bidang 3 digit mengalahkan golongan 1 digit), sehingga "Alat Angkutan"
 * mendapat daftar kendaraannya sendiri alih-alih daftar umum Peralatan dan
 * Mesin.
 */
const REKOMENDASI = {
  // ── Golongan 2 — Tanah (KIB A) ────────────────────────────────────────────
  2: [
    ...DASAR,
    "Sertifikat Hak Pakai/Hak Pengelolaan",
    "Surat Ukur / Gambar Situasi",
    "Bukti Perolehan (Akta/Pelepasan Hak)",
    "SPPT PBB Terakhir",
  ],

  // ── Golongan 3 — Peralatan dan Mesin (KIB B) ──────────────────────────────
  3: [...DASAR, "Buku Manual/Petunjuk Penggunaan", "Kartu Garansi"],

  // Alat Angkutan — satu-satunya bidang dengan dokumen kepemilikan tersendiri
  // (BPKB/STNK) DAN perlengkapan fisik yang wajib ikut saat serah terima.
  302: [
    ...DASAR,
    "BPKB",
    "STNK",
    "Bukti Bayar Pajak Kendaraan Terakhir",
    "Buku Manual/Servis",
    "Kunci Cadangan",
    "Ban Cadangan",
    "Dongkrak & Kunci Roda",
    "Segitiga Pengaman",
  ],

  // Alat Kantor dan Rumah Tangga
  305: [...DASAR, "Buku Manual/Petunjuk Penggunaan", "Kartu Garansi", "Kabel Daya/Adaptor"],

  // Alat Studio, Komunikasi dan Pemancar
  306: [
    ...DASAR,
    "Buku Manual/Petunjuk Penggunaan",
    "Kartu Garansi",
    "Kabel Daya/Adaptor",
    "Izin Frekuensi (bila pemancar)",
  ],

  // Alat Kedokteran dan Kesehatan — kalibrasi adalah syarat laik pakai.
  307: [
    ...DASAR,
    "Buku Manual/Petunjuk Penggunaan",
    "Kartu Garansi",
    "Sertifikat Kalibrasi",
    "Izin Edar Alat Kesehatan",
  ],

  // Alat Laboratorium
  308: [...DASAR, "Buku Manual/Petunjuk Penggunaan", "Kartu Garansi", "Sertifikat Kalibrasi"],

  // Komputer
  310: [
    ...DASAR,
    "Buku Manual/Petunjuk Penggunaan",
    "Kartu Garansi",
    "Charger/Adaptor Daya",
    "Kabel Data/Power",
    "Media/Lisensi Perangkat Lunak",
  ],

  // ── Golongan 4 — Gedung dan Bangunan (KIB C) ──────────────────────────────
  4: [
    ...DASAR,
    "IMB / PBG",
    "Sertifikat Laik Fungsi (SLF)",
    "Gambar Terbangun (As-Built Drawing)",
    "Dokumen Kontrak Pembangunan",
    "Berita Acara Serah Terima Pekerjaan (PHO/FHO)",
    "SPPT PBB Terakhir",
  ],

  // ── Golongan 5 — Jalan, Irigasi, dan Jaringan (KIB D) ─────────────────────
  5: [
    ...DASAR,
    "Dokumen Kontrak Pekerjaan",
    "Gambar Terbangun (As-Built Drawing)",
    "Berita Acara Serah Terima Pekerjaan (PHO/FHO)",
    "Izin Pemanfaatan Ruang/Jalan",
  ],

  // ── Golongan 6 — Aset Tetap Lainnya (KIB E) ───────────────────────────────
  // Buku/perpustakaan, barang bercorak kesenian, hewan & tumbuhan.
  6: [...DASAR, "Katalog/Daftar Rincian", "Sertifikat Keaslian (bila barang seni)"],

  // ── Golongan 7 — Konstruksi Dalam Pengerjaan (KIB F) ──────────────────────
  // Belum jadi aset utuh: yang ada baru berkas pekerjaannya.
  7: [
    "Dokumen Kontrak Pekerjaan",
    "Laporan Kemajuan Pekerjaan",
    "Berita Acara Pembayaran Termin",
  ],

  // ── Golongan 8 — Aset Tak Berwujud ────────────────────────────────────────
  // Tak ada wujud fisik untuk diperiksa — seluruh buktinya berupa dokumen.
  8: [
    ...DASAR,
    "Sertifikat/Bukti Lisensi",
    "Perjanjian Lisensi/Pemeliharaan",
    "Dokumentasi Teknis / Kode Sumber",
    "Bukti Pendaftaran HKI (bila ada)",
  ],
};

/** Prefix diurut dari yang TERPANJANG supaya bidang mengalahkan golongan. */
const PREFIX_TERURUT = Object.keys(REKOMENDASI).sort((a, b) => b.length - a.length);

/**
 * Nama-nama kelengkapan yang disarankan untuk sebuah kode barang. MURNI.
 *
 * @param {string} kodeBarang Kode kodefikasi (1/3/5/7/10 digit). Boleh kosong.
 * @returns {string[]} Daftar nama; KOSONG bila kode belum diisi atau golongan
 *   tak dikenal — dan daftar kosong memang jawaban yang benar di situ, karena
 *   menebak kelengkapan barang yang belum diketahui jenisnya hanya melahirkan
 *   baris palsu yang harus dihapus satu per satu.
 */
export function rekomendasiKelengkapan(kodeBarang) {
  const kode = String(kodeBarang || "").replace(/\D/g, "");
  if (!kode) return [];
  const cocok = PREFIX_TERURUT.find((p) => kode.startsWith(p));
  return cocok ? [...REKOMENDASI[cocok]] : [];
}

/**
 * Bentuk baris checklist siap pakai dari daftar nama.
 *
 * Baris yang SUDAH ADA dipertahankan apa adanya — beserta centang, catatan,
 * foto, dan dokumennya. Tanpa ini, mengganti kategori aset akan menghapus
 * bukti yang sudah susah payah diunggah petugas lapangan.
 *
 * @param {string[]} nama Nama kelengkapan yang disarankan.
 * @param {Array} sebelumnya Baris checklist yang sudah ada (boleh kosong).
 * @returns {Array} Baris rekomendasi lebih dulu, lalu baris tambahan pengguna.
 */
export function bangunChecklist(nama, sebelumnya = []) {
  const lama = Array.isArray(sebelumnya) ? sebelumnya : [];
  const disarankan = Array.isArray(nama) ? nama : [];
  const baris = disarankan.map(
    (n) => lama.find((i) => i && i.name === n)
      || { name: n, checked: false, notes: "", photos: [], documents: [] },
  );
  // Baris buatan pengguna (di luar rekomendasi) tetap ikut, ditaruh di bawah.
  const set = new Set(disarankan);
  return [...baris, ...lama.filter((i) => i && !set.has(i.name))];
}

export { REKOMENDASI, DASAR };
