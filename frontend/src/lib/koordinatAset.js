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
