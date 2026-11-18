// Kesiapan offline kegiatan inventarisasi (temuan F7, tinjauan mutu Nov 2026).
//
// Dulu snapshot offline HANYA disiapkan saat petugas menekan ikon kecil
// "Mode Inventarisasi" — dan pilihan itu hilang setiap halaman dimuat ulang.
// Petugas yang lupa lalu kehilangan sinyal di lapangan mendapati daftar
// kosong bertuliskan "Belum ada aset — Tambah aset pertama", padahal
// kegiatannya berisi ratusan aset.
//
// Modul ini murni (tanpa React) supaya keputusan & penyimpanannya teruji.

// Selaras aturan tata letak proyek: ≤1023px = HP/tablet (lihat index.css).
const LEBAR_PERANGKAT_LAPANGAN = 1023;

/**
 * Perlukah snapshot offline disiapkan OTOMATIS saat kegiatan dibuka?
 *
 * Ya untuk perangkat lapangan (layar sentuh kasar atau lebar ≤1023px) —
 * di sanalah sinyal hilang. Snapshot berisi metadata tanpa foto (±135 KB
 * terkompresi per 600 aset) dan sinkron berikutnya hanya delta.
 * TIDAK bila pengguna menyalakan mode hemat data (Save-Data): ia tetap bisa
 * menyiapkannya sendiri lewat Mode Inventarisasi. Desktop kantor tetap manual.
 */
export function perluSiapOfflineOtomatis(lingkungan = globalThis) {
  try {
    const nav = lingkungan?.navigator;
    if (nav?.connection?.saveData) return false;
    const mm = typeof lingkungan?.matchMedia === "function" ? lingkungan.matchMedia : null;
    if (mm && mm("(pointer: coarse)")?.matches) return true;
    const lebar = Number(lingkungan?.innerWidth);
    return Number.isFinite(lebar) && lebar > 0 && lebar <= LEBAR_PERANGKAT_LAPANGAN;
  } catch {
    return false;
  }
}

const AWALAN = "aman_mode_inventarisasi:";

/** Kunci per PENGGUNA + KEGIATAN: perangkat bersama tak saling mewarisi. */
export function kunciModeInventarisasi(userId, activityId) {
  if (!userId || !activityId) return null;
  return `${AWALAN}${userId}|${activityId}`;
}

/** Pilihan Mode Inventarisasi yang tersimpan (bawaan: mati). */
export function bacaModeInventarisasi(userId, activityId, simpanan = globalThis.localStorage) {
  const kunci = kunciModeInventarisasi(userId, activityId);
  if (!kunci) return false;
  try {
    return simpanan?.getItem(kunci) === "1";
  } catch {
    return false;   // mode privat / penyimpanan diblokir → perilaku lama
  }
}

/** Simpan pilihan; "mati" menghapus kunci agar penyimpanan tidak menumpuk. */
export function simpanModeInventarisasi(userId, activityId, aktif, simpanan = globalThis.localStorage) {
  const kunci = kunciModeInventarisasi(userId, activityId);
  if (!kunci) return;
  try {
    if (aktif) simpanan?.setItem(kunci, "1");
    else simpanan?.removeItem(kunci);
  } catch {
    /* penyimpanan penuh/diblokir — pilihan hanya berlaku untuk sesi ini */
  }
}
