// Efek getar — umpan balik taktil ringan tanpa perlu melihat layar (berguna saat
// menjepret di lapangan). Dua jalur, best-effort (tak pernah melempar):
//   1. Web Vibration API `navigator.vibrate` — Android (HP/tablet).
//   2. Fallback iOS 17.4+: menoggel kontrol <input type="checkbox" switch>
//      tersembunyi memicu haptic ringan Safari (satu-satunya cara web di iOS;
//      Apple memblokir Vibration API). Diam bila iOS lebih lama / tak didukung.
// Desktop tanpa motor getar mengabaikan keduanya tanpa error.
// Bisa dimatikan pengguna via localStorage `aman_haptics` = "off".
//
// Pola sengaja BERBEDA per kejadian agar tiap aksi terasa beda. Bagian pemetaan
// pola dipisah (resolveHapticPattern) tanpa dependensi DOM → mudah diuji unit.

// Pola getar dalam milidetik (nyala, jeda, nyala, …).
export const HAPTIC_PATTERNS = {
  gpsLock: [18, 40, 70],   // GPS SANGAT akurat (≤4 m) — pola menaik "tada"
  save: [45],              // simpan — satu getar mantap
  navNext: [14],           // pindah ke aset BERIKUTNYA — tik pendek tunggal
  navPrev: [14, 34, 14],   // pindah ke aset SEBELUMNYA — tik ganda (arah terasa beda)
  shutter: [45, 35, 45],   // ambil foto — DENYUT GANDA mantap ("cha-chunk") agar
                           // pasti terasa; pulsa tunggal pendek kerap tak terasa
                           // di sebagian motor getar Android.
  error: [60, 45, 60],     // gagal/blokir/konflik — getar tegas berulang
  success: [25, 30, 25],   // sukses umum (mis. scan QR berhasil)
};

// Murni: nama → pola. Nama tak dikenal jatuh ke 'shutter' agar pemanggilan tetap
// aman & tak pernah undefined.
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

// Jalur iOS: elemen switch tersembunyi (dibuat sekali, dipakai ulang). Meng-klik
// label menoggel switch → Safari iOS 17.4+ memberi haptic. Off-screen (bukan
// display:none) agar tetap dirender sehingga haptic ikut terpicu. Best-effort:
// bila atribut `switch` tak dikenal (iOS lama / browser lain) tak terjadi apa-apa.
let _iosSwitch = null;
function _iosHaptic() {
  try {
    if (typeof document === "undefined" || !document.body) return false;
    if (!_iosSwitch) {
      const label = document.createElement("label");
      label.setAttribute("aria-hidden", "true");
      label.style.cssText =
        "position:fixed;top:0;left:0;width:1px;height:1px;opacity:0;pointer-events:none;z-index:-1";
      const input = document.createElement("input");
      input.type = "checkbox";
      input.setAttribute("switch", ""); // atribut khas iOS 17.4+
      // opacity:0 tak mengeluarkan elemen dari urutan tab — beri tabindex=-1
      // agar kontrol tak-terlihat ini tak "menangkap" fokus keyboard (aturan
      // aria-hidden-focus). Jangan pakai `disabled` — switch nonaktif tak
      // toggle → haptic gagal.
      input.tabIndex = -1;
      label.appendChild(input);
      document.body.appendChild(label);
      _iosSwitch = label;
    }
    _iosSwitch.click(); // toggle switch → haptic (best-effort)
    return true;
  } catch {
    return false;
  }
}

// Picu getar untuk sebuah kejadian bernama. Mengembalikan false bila dimatikan /
// tak ada jalur yang berhasil (tanpa melempar) sehingga aman sebagai efek samping.
export function haptic(name) {
  try {
    if (!hapticsEnabled()) return false;
    // Android & sejenisnya: Web Vibration API.
    if (typeof navigator !== "undefined" && typeof navigator.vibrate === "function") {
      return navigator.vibrate(resolveHapticPattern(name));
    }
    // Tak ada Vibration API (mis. iOS Safari) → coba jalur haptic iOS 17.4+.
    return _iosHaptic();
  } catch {
    return false;
  }
}
