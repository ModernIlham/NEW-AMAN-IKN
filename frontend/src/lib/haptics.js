// Efek getar (Web Vibration API) — umpan balik taktil ringan tanpa perlu melihat
// layar (berguna saat menjepret di lapangan). Best-effort: desktop & iOS Safari
// MENGABAIKAN navigator.vibrate tanpa error, jadi aman dipanggil di mana pun.
// Bisa dimatikan pengguna via localStorage `aman_haptics` = "off".
//
// Pola sengaja BERBEDA per kejadian agar tiap aksi terasa beda. Bagian pemetaan
// pola dipisah (resolveHapticPattern) tanpa dependensi DOM → mudah diuji unit.

// Pola getar dalam milidetik (nyala, jeda, nyala, …).
export const HAPTIC_PATTERNS = {
  gpsLock: [18, 40, 70], // GPS SANGAT akurat (≤4 m) — pola menaik "tada"
  save: [45],            // simpan — satu getar mantap
  navNext: [14],         // pindah ke aset BERIKUTNYA — tik pendek tunggal
  navPrev: [14, 34, 14], // pindah ke aset SEBELUMNYA — tik ganda (arah terasa beda)
  shutter: [8],          // ambil foto — tik sangat ringan
  error: [60, 45, 60],   // gagal/blokir/konflik — getar tegas berulang
  success: [25, 30, 25], // sukses umum (mis. scan QR berhasil)
};

// Murni: nama → pola. Nama tak dikenal jatuh ke 'shutter' (tik paling ringan)
// agar pemanggilan tetap aman & tak pernah undefined.
export function resolveHapticPattern(name) {
  return HAPTIC_PATTERNS[name] || HAPTIC_PATTERNS.shutter;
}

// Preferensi pengguna (default AKTIF). Dibungkus try/catch untuk lingkungan
// tanpa localStorage (SSR/uji).
export function hapticsEnabled() {
  try {
    return typeof localStorage === "undefined" || localStorage.getItem("aman_haptics") !== "off";
  } catch {
    return true;
  }
}

// Picu getar untuk sebuah kejadian bernama. Mengembalikan false bila tak
// didukung / dimatikan (tanpa melempar) sehingga aman sebagai efek samping.
export function haptic(name) {
  try {
    if (typeof navigator === "undefined" || typeof navigator.vibrate !== "function") return false;
    if (!hapticsEnabled()) return false;
    return navigator.vibrate(resolveHapticPattern(name));
  } catch {
    return false;
  }
}
