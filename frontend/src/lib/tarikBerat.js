/**
 * Fisika "tarik berat" — gerakan yang SENGAJA dibuat berat agar tak terbuka
 * karena tersenggol.
 *
 * KENAPA ADA. Bilah Satker Aktif tampil di hampir seluruh halaman. Ia menyatakan
 * SEBAGAI SATKER MANA seluruh aplikasi sedang bekerja, jadi membukanya adalah
 * tindakan yang harus disengaja — bukan sesuatu yang terjadi karena jari
 * menyerempet tepi atas layar atau kursor lewat begitu saja.
 *
 * Dua sifat yang membuatnya terasa berat, dan keduanya perlu:
 *
 * 1. REDAMAN — jarak yang TERLIHAT jauh lebih pendek daripada jarak yang
 *    DITARIK, dan makin jauh ditarik makin seret (asimtotik). Tarikan iseng
 *    hampir tak menggerakkan apa pun, jadi umpan baliknya sendiri sudah
 *    mengatakan "ini bukan sekadar sentuhan".
 * 2. AMBANG — perpindahan baru terjadi bila tarikan MENTAH melewati ambang.
 *    Yang dinilai adalah jarak mentah, bukan jarak teredam: yang harus
 *    diusahakan pengguna adalah gerakannya, bukan hasil animasinya.
 *
 * Modul ini murni angka supaya bisa diuji tanpa DOM — pola yang sama dipakai
 * `zoomPan`, `lightboxAnim`, dan `denahEditor` di repo ini.
 */

/** Jarak tarik MENTAH (px) yang wajib dilampaui agar bilah berpindah keadaan. */
export const AMBANG_TARIK = 72;

/** Jarak TERLIHAT maksimum (px), berapa pun jauhnya ditarik. */
export const MAKS_TAMPAK = 26;

/** Makin kecil, makin cepat mentok (makin seret terasanya). */
const SKALA = 60;

/**
 * Jarak mentah → jarak yang ditampilkan, teredam asimtotik ke MAKS_TAMPAK.
 *
 * Memakai x/(x+SKALA) alih-alih pemotongan linier: tak ada titik patah, dan
 * turunannya mengecil terus sehingga jari terasa melawan pegas yang mengeras.
 * Tarikan mundur (negatif) menghasilkan 0 — menarik ke arah yang salah tak
 * pernah menggerakkan apa pun.
 */
export function redamTarik(mentah) {
  const x = Number(mentah);
  if (!Number.isFinite(x) || x <= 0) return 0;
  return MAKS_TAMPAK * (x / (x + SKALA));
}

/** Sudah cukup jauh untuk benar-benar berpindah keadaan? */
export function cukupUntukBuka(mentah) {
  const x = Number(mentah);
  return Number.isFinite(x) && x >= AMBANG_TARIK;
}

/**
 * Kemajuan 0..1 menuju ambang — untuk indikator visual.
 *
 * Tanpa ini redaman berbalik jadi kejam: pengguna menarik jauh, layar nyaris
 * tak bergerak, dan ia menyimpulkan bilahnya rusak. Indikator memberi tahu
 * "tarikanmu terbaca, teruskan" tanpa membuat tarikannya jadi ringan.
 */
export function kemajuanTarik(mentah) {
  const x = Number(mentah);
  if (!Number.isFinite(x) || x <= 0) return 0;
  return Math.min(1, x / AMBANG_TARIK);
}

/**
 * Jarak mentah BERTANDA sesuai arah yang sah untuk keadaan sekarang.
 *
 * Saat tertutup, yang sah adalah menarik KE BAWAH (dy positif); saat terbuka,
 * KE ATAS. Mengembalikan angka positif = "maju ke arah yang benar sejauh ini".
 * Arah sebaliknya menghasilkan negatif dan — lewat redamTarik/cukupUntukBuka —
 * tak berefek apa pun.
 */
export function majuTarik(dy, terbuka) {
  const d = Number(dy);
  if (!Number.isFinite(d)) return 0;
  return terbuka ? -d : d;
}
