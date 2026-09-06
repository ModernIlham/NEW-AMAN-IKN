/**
 * "Aset ini sudah punya titik koordinat?" — SATU sumber kebenaran.
 *
 * Pertanyaan ini dijawab di dua tempat yang tak boleh berselisih: peta aset
 * (menentukan baris mana yang dapat dipasang pin) dan penanda di baris/kartu
 * daftar aset (menentukan pin mana yang bercentang). Kalau keduanya punya
 * pendapat sendiri, akan ada aset yang barisnya berkata "sudah berkoordinat"
 * tetapi tak pernah muncul di peta — dan tak ada galat apa pun yang
 * memberitahu.
 *
 * MURNI: tanpa React, tanpa jaringan.
 */

/**
 * Koordinat aset tersimpan sebagai STRING — parse toleran (koma desimal).
 *
 * Ambang |n| <= 180 dipertahankan APA ADANYA dari peta. Untuk lintang
 * seharusnya 90, dan nilai 150 memang akan diterima di sini padahal mustahil;
 * memperketatnya akan membuat penanda daftar dan peta berbeda pendapat, yang
 * justru masalah yang modul ini ada untuk mencegahnya. Pengetatan itu urusan
 * perbaikan tersendiri — di kedua tempat sekaligus.
 *
 * → angka, atau null bila tak terbaca.
 */
export function parseKoordinat(v) {
  if (v === null || v === undefined) return null;
  const n = parseFloat(String(v).trim().replace(",", "."));
  return Number.isFinite(n) && Math.abs(n) <= 180 ? n : null;
}

/**
 * Aset punya titik koordinat yang bisa dipetakan?
 *
 * KEDUANYA wajib. Lintang tanpa bujur bukan titik — ia tak bisa dipetakan,
 * dan menandainya "sudah berkoordinat" akan menyuruh petugas melewati aset
 * yang justru masih perlu diambil titiknya.
 */
export function punyaKoordinat(aset) {
  const a = aset || {};
  return parseKoordinat(a.koordinat_latitude) !== null
    && parseKoordinat(a.koordinat_longitude) !== null;
}

/** Teks koordinat untuk tooltip; "" bila belum ada. */
export function labelKoordinat(aset) {
  if (!punyaKoordinat(aset)) return "";
  const a = aset || {};
  return `${parseKoordinat(a.koordinat_latitude)}, ${parseKoordinat(a.koordinat_longitude)}`;
}

/**
 * Aset sudah menempati sebuah node denah?
 *
 * DUA BENTUK data dijawab fungsi yang sama, dan itu disengaja. Daftar aset
 * menerima ringkasan `di_denah` (dihitung server di LIST_PROJECTION), sedangkan
 * layar detail menerima subdoc `lokasi_spasial` utuh. Kalau masing-masing
 * layar memeriksa bentuknya sendiri, akan ada aset yang di daftar tampak sudah
 * di denah tetapi di detailnya tidak — persis jenis perselisihan yang modul
 * ini ada untuk mencegahnya.
 *
 * `node_id` yang menentukan, bukan sekadar adanya subdoc: penempatan yang
 * dilepas menyisakan subdoc dengan node_id kosong.
 */
export function diDenah(aset) {
  const a = aset || {};
  if (typeof a.di_denah === "boolean") return a.di_denah;
  return String((a.lokasi_spasial || {}).node_id || "").trim() !== "";
}

/** Nama node denah untuk tooltip; "" bila belum ditempatkan. */
export function labelDenah(aset) {
  if (!diDenah(aset)) return "";
  const a = aset || {};
  const spasial = a.lokasi_spasial || {};
  // Jalur lengkap lebih berguna daripada nama node saja — "Ruang 201" ada di
  // banyak gedung. Nama node dipakai bila jalurnya belum tercatat.
  return String(a.denah_jalur || spasial.jalur_nama
    || a.denah_nama || spasial.node_nama || "").trim();
}

/**
 * Teks baris lokasi pada kartu/baris daftar — "" bila tak ada yang perlu
 * ditampilkan.
 *
 * Keempat tampilan (galeri, kartu HP, tabel ringkas, tabel lebar) dulu
 * menyusun teks ini sendiri-sendiri sebagai `location || "Berkoordinat"`.
 * Begitu penanda denah masuk, tiap tampilan harus ingat menambahkan cabang
 * ketiganya — dan yang lupa akan MENYEMBUNYIKAN barisnya justru pada aset yang
 * sudah di denah tetapi belum berkoordinat dan belum bernama lokasi, yakni
 * aset yang penandanya paling perlu dilihat.
 */
export function labelBarisLokasi(aset) {
  const a = aset || {};
  const nama = String(a.location || "").trim();
  if (nama) return nama;
  if (punyaKoordinat(a)) return "Berkoordinat";
  if (diDenah(a)) return labelDenah(a) || "Di denah";
  return "";
}
