// Akurasi asli perangkat, bukan angka pembulatan tampilan. Fix lama tidak
// boleh dianggap sebagai lokasi jepretan baru meskipun koordinatnya presisi.
export function gpsPemegangLayak(fix, now = Date.now()) {
  if (!fix || !Number.isFinite(fix.accuracy) || fix.accuracy < 0 || fix.accuracy > 8) return false;
  if (!Number.isFinite(fix.timestamp) || fix.timestamp <= 0 || fix.timestamp > now || now - fix.timestamp > 60000) return false;
  return fix.lat !== null && fix.lat !== "" && fix.lng !== null && fix.lng !== ""
    && Number.isFinite(Number(fix.lat)) && Math.abs(Number(fix.lat)) <= 90
    && Number.isFinite(Number(fix.lng)) && Math.abs(Number(fix.lng)) <= 180;
}
