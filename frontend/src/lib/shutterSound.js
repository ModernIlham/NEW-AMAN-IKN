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

// Putar bunyi klik rana SEKALI. Best-effort: no-op bila dimatikan atau Web Audio
// tak didukung; SEMUA dibungkus try/catch agar tak pernah melempar (aman sebagai
// efek samping di jalur pengambilan foto). AudioContext dibuat baru per panggilan
// lalu ditutup setelah bunyi selesai agar tidak menumpuk context.
export function playShutterSound() {
  try {
    if (!shutterSoundEnabled()) return;
    const AudioCtx = typeof window !== "undefined" && (window.AudioContext || window.webkitAudioContext);
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
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
    click(now, 1900, 0.03, 0.32);          // transien pertama (tajam, tinggi)
    click(now + 0.04, 1250, 0.045, 0.26);  // transien kedua (lebih rendah)

    // Tutup context setelah bunyi selesai (~total ≤ 95 ms) agar di-GC.
    setTimeout(() => { try { ctx.close(); } catch { /* diam */ } }, 140);
  } catch {
    // Best-effort: kegagalan audio tak boleh mengganggu pengambilan foto.
  }
}
