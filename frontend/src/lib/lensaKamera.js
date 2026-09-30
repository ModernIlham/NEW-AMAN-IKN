// ID kamera hanya disimpan di browser ini, tidak dikirim ke API akun/aset.
const KUNCI = "aman_lensa_makro_perangkat_v1";

export function bacaPilihanLensa() {
  try { return localStorage.getItem(KUNCI) || ""; } catch { return ""; }
}
export function simpanPilihanLensa(id) {
  try { if (id) localStorage.setItem(KUNCI, id); else localStorage.removeItem(KUNCI); } catch { /* penyimpanan opsional */ }
}
export function daftarLensa(devices) {
  const unik = new Map();
  for (const d of devices || []) {
    if (d.kind !== "videoinput" || !d.deviceId || unik.has(d.deviceId)) continue;
    unik.set(d.deviceId, { id: d.deviceId, label: d.label?.trim() || `Kamera ${unik.size + 1}` });
  }
  return [...unik.values()];
}
export function cariLensaMakro(daftar, pilihan) {
  const tersimpan = daftar.find(d => d.id === pilihan);
  if (tersimpan) return tersimpan;
  // Urutan kamera, zoom, fokus manual atau label ultra-wide BUKAN bukti makro.
  const kandidat = daftar.filter(d => /\b(?:macro|makro)\b/i.test(d.label));
  return kandidat.length === 1 ? kandidat[0] : null;
}
export function idLensa(track) {
  try { return track?.getSettings?.().deviceId || ""; } catch { return ""; }
}
export async function bukaLensa({ deviceId, facing, resolusi }, media = navigator.mediaDevices) {
  const stream = await media.getUserMedia({ audio: false, video: {
    ...(deviceId ? { deviceId: { exact: deviceId } } : { facingMode: facing }),
    width: { ideal: resolusi }, height: { ideal: Math.round(resolusi * 3 / 4) },
  } });
  const track = stream.getVideoTracks()[0];
  if (!track || track.readyState !== "live" || (deviceId && idLensa(track) !== deviceId)) {
    stream.getTracks().forEach(t => t.stop());
    const err = new Error("Browser tidak mengonfirmasi kamera yang dipilih.");
    err.name = "LensaTidakSesuai";
    throw err;
  }
  return stream;
}
