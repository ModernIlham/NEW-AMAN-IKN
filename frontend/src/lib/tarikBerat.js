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
 * TIRAI BERTAHAP.
 *
 * Bilah ini bukan lagi saklar buka/tutup melainkan tirai tiga tahap, karena
 * itulah yang diminta lapangan: bilahnya TERSEMBUNYI, dan tiap lapis berikutnya
 * ditarik TURUN dengan usaha tersendiri.
 *
 *   0 TERSEMBUNYI — hanya pegangan setipis rambut di tepi atas
 *   1 CAP         — "Satker aktif: <nama>"
 *   2 DAFTAR      — daftar seluruh satker untuk dipilih
 *
 * Menarik ke BAWAH selalu maju satu tahap, ke ATAS selalu mundur satu tahap.
 * Satu tarikan = satu tahap, tak peduli sejauh apa ditarik: melompat dua lapis
 * sekaligus akan membuat daftar satker muncul karena satu sapuan panjang yang
 * tak disengaja, dan mengganti satker aktif itu memuat ulang seluruh aplikasi.
 */
export const TAHAP_TERSEMBUNYI = 0;
export const TAHAP_CAP = 1;
export const TAHAP_DAFTAR = 2;
export const TAHAP_MAKS = TAHAP_DAFTAR;

/** Arah tarikan ini sah untuk tahap sekarang? (bawah=maju, atas=mundur) */
export function arahSah(tahap, dy) {
  const t = Number(tahap) || 0;
  const d = Number(dy);
  if (!Number.isFinite(d) || d === 0) return false;
  return d > 0 ? t < TAHAP_MAKS : t > 0;
}

/**
 * Jarak mentah yang DIHITUNG untuk tahap ini — 0 bila arahnya buntu.
 *
 * Menarik turun saat daftar sudah terbuka, atau menarik naik saat sudah
 * tersembunyi, tidak menggerakkan apa pun: tak ada lagi yang bisa dituju.
 */
export function majuTahap(dy, tahap) {
  return arahSah(tahap, dy) ? Math.abs(Number(dy)) : 0;
}

/** Tahap setelah tarikan dilepas. Tetap bila usahanya belum cukup. */
export function tahapSetelahTarik(tahap, dy) {
  const t = Math.min(TAHAP_MAKS, Math.max(0, Number(tahap) || 0));
  if (!arahSah(t, dy) || !cukupUntukBuka(Math.abs(Number(dy)))) return t;
  return Number(dy) > 0 ? t + 1 : t - 1;
}

/**
 * Geser TERLIHAT bertanda: turun positif, naik negatif, dan teredam sama
 * beratnya di kedua arah.
 */
export function geserTahap(dy, tahap) {
  const teredam = redamTarik(majuTahap(dy, tahap));
  return Number(dy) < 0 ? -teredam : teredam;
}
