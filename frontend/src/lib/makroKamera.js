// Dukungan kontrol fokus, BUKAN detektor jarak objek/lensa makro khusus.
// Rentang focusDistance berbeda antar driver: cari ketajaman aktual, bukan
// menebak bahwa min/max selalu merupakan fokus paling dekat.
export function deteksiMakro(track) {
  try {
    if (!track?.applyConstraints || track.readyState !== "live") return { jenis: "none" };
    const c = track.getCapabilities?.() || {}, mode = c.focusMode || [];
    const s = track.getSettings?.() || {};
    if (!mode.includes(s.focusMode) || (s.focusMode === "manual" && !Number.isFinite(s.focusDistance))) return { jenis: "none" };
    const d = c.focusDistance;
    if (mode.includes("manual") && Number.isFinite(d?.min) && Number.isFinite(d?.max) && d.max > d.min) {
      return { jenis: "manual", min: d.min, max: d.max, step: Number(d.step) || 0 };
    }
    const otomatis = ["continuous", "single-shot"].find(m => mode.includes(m));
    return otomatis ? { jenis: "otomatis", mode: otomatis } : { jenis: "none" };
  } catch { return { jenis: "none" }; }
}

const FOKUS = ["focusMode", "focusDistance", "pointsOfInterest"];
export function bacaFokus(track) {
  const s = track.getSettings?.() || {};
  return Object.fromEntries(FOKUS.filter(k => s[k] !== undefined).map(k => [k, s[k]]));
}

export async function terapkanFokus(track, fokus) {
  const bersih = o => Object.fromEntries(Object.entries(o || {}).filter(([k]) => !FOKUS.includes(k) && k !== "advanced"));
  const lama = track.getConstraints?.() || {};
  const s = track.getSettings?.() || {};
  // Pertahankan zoom/senter aktual meski pemanggil sebelumnya hanya memakai
  // advanced. Jangan membuat properti yang tidak diekspos perangkat.
  const tetap = Object.fromEntries(["zoom", "torch"].filter(k => s[k] !== undefined).map(k => [k, s[k]]));
  await track.applyConstraints({ ...bersih(lama), advanced: [...(lama.advanced || []).map(bersih), { ...tetap, ...fokus }] });
}

export function skorKetajaman({ data, width, height }) {
  if (width < 3 || height < 3) return 0;
  const abu = i => data[i] * 0.299 + data[i + 1] * 0.587 + data[i + 2] * 0.114;
  let sum = 0, kuadrat = 0, n = 0;
  for (let y = 1; y < height - 1; y++) for (let x = 1; x < width - 1; x++) {
    const i = (y * width + x) * 4;
    const v = 4 * abu(i) - abu(i - 4) - abu(i + 4) - abu(i - width * 4) - abu(i + width * 4);
    sum += v; kuadrat += v * v; n++;
  }
  return Math.max(0, kuadrat / n - (sum / n) ** 2);
}

export function pembacaKetajaman(video) {
  const c = document.createElement("canvas"); c.width = 96; c.height = 96;
  const ctx = c.getContext("2d", { willReadFrequently: true });
  return () => {
    if (!ctx || !video || video.readyState < 2 || video.paused || !video.videoWidth) throw new Error("Bingkai kamera belum siap.");
    const sisi = Math.min(video.videoWidth, video.videoHeight) * 0.3;
    ctx.drawImage(video, (video.videoWidth - sisi) / 2, (video.videoHeight - sisi) / 2, sisi, sisi, 0, 0, 96, 96);
    return skorKetajaman(ctx.getImageData(0, 0, 96, 96));
  };
}

export async function cariFokusMakro(track, ukur, aktif, tunggu = ms => new Promise(r => setTimeout(r, ms))) {
  const cek = () => { if (!aktif() || track.readyState !== "live") throw new Error("Pencarian fokus dibatalkan."); };
  const cap = deteksiMakro(track);
  cek();
  if (cap.jenis === "none") throw new Error("Kontrol fokus tidak tersedia di browser/kamera ini.");
  if (cap.jenis === "otomatis") {
    await terapkanFokus(track, { focusMode: cap.mode, pointsOfInterest: [{ x: 0.5, y: 0.5 }] });
    cek();
    if (track.getSettings?.().focusMode !== cap.mode) throw new Error("Browser tidak mengonfirmasi perubahan fokus.");
    return "otomatis";
  }
  const jepit = n => Math.min(cap.max, Math.max(cap.min, n));
  const bulat = n => jepit(cap.step > 0 ? cap.min + Math.round((n - cap.min) / cap.step) * cap.step : n);
  const awal = bacaFokus(track).focusDistance;
  const kandidat = [...new Set([awal, ...[0, 0.05, 0.15, 0.35, 0.65, 1].map(n => bulat(cap.min + n * (cap.max - cap.min)))]
    .filter(n => Number.isFinite(n) && n >= cap.min && n <= cap.max))];
  let terbaik = null;
  for (const jarak of kandidat) {
    cek(); await terapkanFokus(track, { focusMode: "manual", focusDistance: jarak }); cek();
    const s = bacaFokus(track);
    if (s.focusMode !== "manual" || !Number.isFinite(s.focusDistance) || Math.abs(s.focusDistance - jarak) > Math.max(cap.step, 1e-4)) {
      throw new Error("Kamera mengabaikan pengaturan fokus manual.");
    }
    await tunggu(220); cek();
    const a = ukur(); await tunggu(90); cek();
    const skor = Math.min(a, ukur());
    if (Number.isFinite(skor) && (!terbaik || skor > terbaik.skor)) terbaik = { jarak, skor };
  }
  if (!terbaik || terbaik.skor < 4) throw new Error("Detail belum cukup. Tambah cahaya atau jauhkan kamera sedikit.");
  cek(); await terapkanFokus(track, { focusMode: "manual", focusDistance: terbaik.jarak }); cek();
  return "manual";
}
