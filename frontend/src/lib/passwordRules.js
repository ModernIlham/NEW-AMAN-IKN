/**
 * Syarat kata sandi — SATU sumber kebenaran untuk seluruh layar yang menyetel
 * kata sandi (daftar akun, reset via OTP, ganti kata sandi).
 *
 * Sebelum berkas ini ada, aturannya diketik ulang di tiap layar: form Daftar
 * memblokir huruf besar/kecil/angka sementara alur reset OTP hanya meminta 8
 * karakter — akun yang sama bisa berakhir dengan kata sandi yang TAK AKAN
 * diterima saat mendaftar. Backend menegakkan aturan yang sama di
 * `auth_utils.periksa_kekuatan_password`.
 */

export const SYARAT_PASSWORD = [
  { label: "Min. 8 karakter", uji: (p) => p.length >= 8, wajib: true },
  { label: "Huruf besar (A-Z)", uji: (p) => /[A-Z]/.test(p), wajib: true },
  { label: "Huruf kecil (a-z)", uji: (p) => /[a-z]/.test(p), wajib: true },
  { label: "Angka (0-9)", uji: (p) => /\d/.test(p), wajib: true },
  // Karakter khusus DIANJURKAN, bukan syarat lulus — menaikkannya jadi wajib
  // akan menolak kata sandi lama yang sudah dipakai pengguna aktif.
  { label: "Karakter khusus (!@#$)", uji: (p) => /[^A-Za-z0-9]/.test(p), wajib: false },
];

/** Daftar status tiap syarat: [{label, ok, wajib}]. MURNI. */
export function statusSyaratPassword(password) {
  const p = String(password || "");
  return SYARAT_PASSWORD.map((s) => ({ label: s.label, wajib: s.wajib, ok: s.uji(p) }));
}

/**
 * Pesan galat pertama yang menghalangi, atau "" bila kata sandi memenuhi
 * SEMUA syarat wajib. Dipakai sebagai gerbang sebelum kirim ke server.
 */
export function galatPassword(password) {
  const p = String(password || "");
  if (p.length < 8) return "Password minimal 8 karakter";
  const kurang = SYARAT_PASSWORD.filter((s) => s.wajib && !s.uji(p));
  if (kurang.length) {
    return "Password harus mengandung huruf besar, huruf kecil, dan angka";
  }
  return "";
}

/** Skor 0-5 untuk bilah kekuatan (termasuk syarat anjuran). MURNI. */
export function skorPassword(password) {
  return statusSyaratPassword(password).filter((s) => s.ok).length;
}
