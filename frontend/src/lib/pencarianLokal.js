/**
 * PENCARIAN LOKAL — cermin semantik pencarian server (backend/pencarian_utils.py
 * + FIELD_CARI_ASET di backend/routes/assets.py).
 *
 * Dipakai jalur BACA LURING (snapshot IndexedDB). Bila aturannya berbeda dari
 * server, satu kata kunci yang sama memberi hasil berbeda tergantung aplikasi
 * sedang daring atau luring — persis keluhan "kadang ketemu kadang tidak".
 *
 * Aturan (sama persis dengan server):
 * - Kata kunci dipecah per spasi; SETIAP kata wajib ada, boleh di field mana
 *   pun (bukan satu frasa utuh di satu field).
 * - Kata yang mengandung ≥ 2 angka juga dicocokkan sebagai DERET ANGKA tanpa
 *   memedulikan pemisah: "3100102001" cocok ke "3.10.01.02.001", "1.5" cocok
 *   ke "1,5".
 * - Nilai bertipe angka ikut dibandingkan (NUP/tahun yang tersimpan numerik).
 */

// Cermin FIELD_CARI_ASET (backend/routes/assets.py). NIP sengaja TIDAK ada.
export const FIELD_CARI_ASET = [
  "asset_code", "NUP", "asset_name", "serial_number", "location",
  "brand", "model", "category", "eselon1", "eselon2", "eselon3",
  "eselon4", "eselon5", "user",
  "pengguna_jabatan", "supplier", "perolehan_dari_nama",
  "condition", "status", "nomor_spm", "kode_register",
  "nomor_kontrak", "nomor_bast", "nomor_bukti_perolehan", "notes", "year",
];

// Cermin FIELD_KODE_ASET — dicocokkan juga sebagai deret angka bebas pemisah.
export const FIELD_KODE_ASET = [
  "asset_code", "NUP", "kode_register", "serial_number", "nomor_spm",
  "nomor_kontrak", "nomor_bast", "nomor_bukti_perolehan",
  "asset_name", "model", "location",
];

export const MIN_PANJANG = 2;   // cermin pencarian_utils.MIN_PANJANG
export const MAKS_KATA = 8;     // cermin pencarian_utils.MAKS_KATA

export function pecahKata(search) {
  const teks = String(search ?? "").trim();
  if (teks.length < MIN_PANJANG) return [];
  const kata = [];
  for (const k of teks.split(/\s+/)) {
    if (k && !kata.includes(k)) kata.push(k);
    if (kata.length >= MAKS_KATA) break;
  }
  return kata;
}

const digitSaja = (v) => String(v ?? "").replace(/\D/g, "");

/** True bila SATU kata ditemukan di salah satu field baris. */
function kataCocok(row, kata) {
  const k = kata.toLowerCase();
  for (const f of FIELD_CARI_ASET) {
    const nilai = row[f];
    if (nilai === null || nilai === undefined) continue;
    if (String(nilai).toLowerCase().includes(k)) return true;
  }
  // Deret angka bebas pemisah (kode diketik tanpa titik, desimal koma/titik).
  const d = digitSaja(kata);
  if (d.length >= 2 && d.length <= 24) {
    for (const f of FIELD_KODE_ASET) {
      const nilai = row[f];
      if (nilai === null || nilai === undefined) continue;
      if (digitSaja(nilai).includes(d)) return true;
    }
  }
  return false;
}

/** True bila SEMUA kata pada `search` ditemukan pada baris `row`. */
export function cocokAset(row, search) {
  const kata = pecahKata(search);
  if (!kata.length) return true;
  return kata.every((k) => kataCocok(row, k));
}
