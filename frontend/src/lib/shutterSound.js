// Bunyi rana kamera — klik singkat yang DISINTESIS via Web Audio API (tanpa aset
// eksternal, jadi tetap berbunyi offline). Umpan balik audio saat foto benar-benar
// terambil di lapangan; melengkapi getar (lihat lib/haptics.js). Best-effort:
// TIDAK PERNAH melempar dan menjadi no-op bila Web Audio tak tersedia. Bisa
// dimatikan pengguna via localStorage `aman_shutter_sound` = "off".
//
// Pola sengaja dipisah seperti haptics: preferensi (shutterSoundEnabled) MURNI
// tanpa dependensi Web Audio → mudah diuji unit. Pemutaran audio TIDAK diuji
// (jsdom tak punya Web Audio).

// Preferensi pengguna (default AKTIF). Dibungkus try/catch untuk lingkungan
// tanpa localStorage (SSR/uji). Mengikuti pola hapticsEnabled().
export function shutterSoundEnabled() {
  try {
    return typeof localStorage === "undefined" || localStorage.getItem("aman_shutter_sound") !== "off";
  } catch {
    return true;
  }
}

// AudioContext BERSAMA (singleton) — dipakai ulang antar jepretan. Sengaja TIDAK
// membuat context baru tiap panggilan: (1) di ponsel context baru lahir dalam
// keadaan "suspended" dan HANYA bisa dibunyikan bila di-resume di dalam gestur
// pengguna; (2) browser membatasi jumlah AudioContext (~6) sehingga membuat &
// menutup berulang saat memotret cepat bisa gagal senyap. Dibuat malas (lazy)
// pada panggilan pertama (yang selalu terjadi di dalam tap tombol rana).
let _ctx = null;
function _getCtx() {
  const AudioCtx = typeof window !== "undefined" && (window.AudioContext || window.webkitAudioContext);
  if (!AudioCtx) return null;
  if (!_ctx) {
    try { _ctx = new AudioCtx(); } catch { return null; }
  }
  return _ctx;
}

// Putar bunyi klik rana SEKALI. Best-effort: no-op bila dimatikan atau Web Audio
// tak didukung; SEMUA dibungkus try/catch agar tak pernah melempar (aman sebagai
// efek samping di jalur pengambilan foto).
export function playShutterSound() {
  try {
    if (!shutterSoundEnabled()) return;
    const ctx = _getCtx();
    if (!ctx) return;
    // WAJIB resume di dalam gestur — context ponsel yang "suspended" (baru dibuat
    // atau ditidurkan browser setelah jeda) tak berbunyi tanpa resume(). Inilah
    // sebab utama "tak ada suara sama sekali" saat memotret. Best-effort/async.
    if (ctx.state === "suspended") { try { ctx.resume(); } catch { /* diam */ } }
    const now = ctx.currentTime;

    // Dua transien pendek & tajam → terasa seperti "cek-lik" rana (cermin
    // naik lalu turun). Tiap transien: gelombang square yang cepat naik lalu
    // meluruh (~30-45 ms) → bunyi klik, bukan nada.
    const click = (t, freq, dur, peak) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "square";
      osc.frequency.setValueAtTime(freq, t);
      gain.gain.setValueAtTime(0.0001, t);
      gain.gain.exponentialRampToValueAtTime(peak, t + 0.004);
      gain.gain.exponentialRampToValueAtTime(0.0001, t + dur);
      osc.connect(gain).connect(ctx.destination);
      osc.start(t);
      osc.stop(t + dur + 0.01);
    };
    click(now, 1900, 0.03, 0.42);          // transien pertama (tajam, tinggi)
    click(now + 0.04, 1250, 0.045, 0.34);  // transien kedua (lebih rendah)
    // Context TIDAK ditutup — dipakai ulang untuk jepretan berikutnya.
  } catch {
    // Best-effort: kegagalan audio tak boleh mengganggu pengambilan foto.
  }
}
