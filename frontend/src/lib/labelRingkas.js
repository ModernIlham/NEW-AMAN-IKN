/**
 * Pelipatan label toolbar berdasarkan LEBAR KONTAINER — bukan lebar viewport.
 *
 * Kenapa bukan breakpoint Tailwind (`xl:inline`) seperti sebelumnya? Breakpoint
 * membaca lebar VIEWPORT. Toolbar yang sama bisa berada di dalam panel sempit:
 * halaman Kegiatan menyisakan ~880 px pada layar 1366 px, tetapi `xl` (≥1280)
 * tetap menyala sehingga SELURUH label lengkap ikut dirender. Hasilnya baris
 * meluber → muncul geser samping atau pecah ke baris kedua. Dua-duanya dilarang
 * pemilik: "jangan membuat row baris baru … usahakan dipersingkat dengan
 * memberikan iconnya saja seiring terhimpitnya tampilan layar."
 *
 * Fungsi di bawah ini memakai lebar kontainer yang SEBENARNYA (diukur
 * ResizeObserver, lihat `hooks/useLebarElemen`), lalu MELEPAS label satu per
 * satu — kontrolnya tetap ada, hanya berubah jadi ikon — sampai semuanya muat
 * dalam satu baris.
 */

/**
 * Perkiraan lebar satu huruf pada `text-xs` (12 px) di font UI repo.
 *
 * Diukur di peramban atas label-label nyata kedua toolbar: rata-ratanya
 * berkisar 5,6–7,6 px/huruf (huruf besar & kata pendek paling boros). Nilai di
 * bawah ini sengaja diambil dari UJUNG ATAS rentang itu, bukan reratanya —
 * menaksir TERLALU LEBAR hanya membuat label dilepas sedikit lebih awal
 * (tampak lebih ringkas, tidak ada yang rusak), sedangkan menaksir terlalu
 * sempit menyisakan baris meluber yang justru sedang diberantas.
 */
export const PX_PER_HURUF = 7.8;

/**
 * Selisih tetap antara bentuk berlabel dan bentuk ikon-saja: padding mendatar
 * yang bertambah (px-2 → px-3) plus jarak ikon→teks.
 */
export const PX_LABEL_EKSTRA = 12;

/**
 * Lebar satu kontrol dalam bentuk LENGKAP (ikon + label).
 *
 * Kontrol yang bukan tombol berlabel — mis. `Select` yang menyempit alih-alih
 * kehilangan teks — cukup menyebut `lebarPenuh` eksplisit; nilainya dipakai apa
 * adanya tanpa menghitung panjang label.
 *
 * @param {{lebarIkon: number, label?: string, lebarPenuh?: number}} item
 * @returns {number} px
 */
export function lebarItem(item) {
  if (Number.isFinite(item?.lebarPenuh)) return item.lebarPenuh;
  const ikon = Number.isFinite(item?.lebarIkon) ? item.lebarIkon : 0;
  const label = item?.label || "";
  return label ? ikon + label.length * PX_PER_HURUF + PX_LABEL_EKSTRA : ikon;
}

/**
 * Kunci kontrol yang labelnya HARUS dilepas agar seluruh baris muat.
 *
 * URUTAN `daftar` = urutan pelepasan: elemen pertama kehilangan labelnya lebih
 * dulu. Susun dari yang paling rela jadi ikon (label panjang, ikon sudah jelas
 * sendiri) ke yang paling perlu kata-katanya.
 *
 * @param {number} lebarTersedia Lebar kontainer (px) hasil pengukuran.
 * @param {{kunci: string, lebarIkon: number, label?: string, lebarPenuh?: number}[]} daftar
 * @param {{celah?: number, lebarTetap?: number}} [opsi]
 *   `celah` = jarak antar kontrol (gap-1.5 = 6 px). `lebarTetap` = ruang yang
 *   dipakai elemen yang tak pernah melipat (ikon judul, indikator kuota, dan
 *   lebar MINIMUM blok judul yang boleh menyusut).
 * @returns {Set<string>} kunci yang labelnya disembunyikan
 */
export function labelDilepas(lebarTersedia, daftar, opsi = {}) {
  const { celah = 6, lebarTetap = 0 } = opsi;
  const lepas = new Set();
  if (!Array.isArray(daftar) || daftar.length === 0) return lepas;

  // Lebar belum terukur (0/NaN — elemen masih `display:none`, atau render
  // pertama sebelum ResizeObserver menyala). Pilih bentuk paling RINGKAS:
  // salah ke arah ini paling banter menunda label satu frame, sedangkan
  // salah ke arah sebaliknya memampangkan baris meluber ber-scrollbar.
  if (!Number.isFinite(lebarTersedia) || lebarTersedia <= 0) {
    daftar.forEach((it) => lepas.add(it.kunci));
    return lepas;
  }

  const total = () =>
    lebarTetap +
    celah * daftar.length +
    daftar.reduce(
      (jml, it) => jml + (lepas.has(it.kunci) ? it.lebarIkon : lebarItem(it)),
      0,
    );

  for (const it of daftar) {
    if (total() <= lebarTersedia) break;
    lepas.add(it.kunci);
  }
  return lepas;
}
