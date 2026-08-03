/**
 * Kelas baku KEPALA HALAMAN — satu bentuk untuk semua halaman modul.
 *
 * Masalah yang ditutup (terukur di 360 px dengan CSS produksi): baris kepala
 * dulu ditulis `flex items-center gap-3` dengan blok judul `min-w-0 flex-1`.
 * Aturan tap-target 44 px global (index.css) membuat setiap tombol aksi
 * memakai ≥44 px, sedangkan blok judul—karena `min-w-0` + `flex-1`—boleh
 * menyusut sampai NOL. Akibatnya di HP judul halamanlah yang mengalah:
 * Pengadaan tersisa 32 px, Referensi Akun 57 px, Pemanfaatan/Pemindahtanganan/
 * Pemusnahan/Penganggaran 84 px — praktis tak terbaca, padahal itu satu-satunya
 * penanda "saya sedang di halaman apa".
 *
 * Perbaikannya dua bagian dan HARUS berpasangan:
 *   1. `flex-wrap` + `gap-y-2` pada baris → tombol yang tak muat TURUN ke baris
 *      kedua, bukan mendesak tetangganya;
 *   2. LANTAI lebar pada blok judul (`min-w-[9rem]`, bukan `min-w-0`) → judul
 *      berhenti menyusut, sehingga poin (1) benar-benar terpicu.
 * Hanya `flex-wrap` saja TIDAK cukup: selama judul masih boleh menyusut ke 0,
 * baris tak pernah "penuh" dan tak pernah membungkus. Uji di kelasKepala.test.js
 * mengunci keduanya.
 *
 * Setelah dipakai, judul terukur 164–244 px di 360 px (dari 32–136 px), dengan
 * ongkos tinggi kepala +52 px HANYA pada halaman yang aksinya memang banyak.
 */

/** Lantai lebar blok judul — penyeimbang `flex-wrap` di baris kepala. */
export const LANTAI_JUDUL = "min-w-[9rem]";

/** Bilah kepala: menempel di atas, kaca buram, garis bawah. */
export const KEPALA_HALAMAN =
  "bg-card/95 backdrop-blur-sm border-b border-border px-3 sm:px-6 py-2.5 " +
  "sticky top-0 z-40";

/** Baris isi kepala (dipadukan dengan `max-w-*` milik halaman). */
export const BARIS_KEPALA = "flex flex-wrap items-center gap-2 sm:gap-3 gap-y-2";

/** Blok judul+keterangan. */
export const BLOK_JUDUL = `flex-1 ${LANTAI_JUDUL}`;

/** Judul halaman. */
export const JUDUL_KEPALA =
  "text-sm sm:text-base font-bold text-foreground leading-tight truncate";

/** Keterangan satu baris di bawah judul. */
export const SUBJUDUL_KEPALA =
  "text-[11px] sm:text-xs text-muted-foreground truncate";

/** Tombol kembali / aksi ikon-saja di kepala. */
export const TOMBOL_KEPALA =
  "h-9 w-9 rounded-lg border border-border text-foreground/80 flex " +
  "items-center justify-center hover:bg-muted flex-shrink-0";

/** Kotak ikon modul (warna latar tetap milik halaman). */
export const IKON_KEPALA =
  "w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0";
