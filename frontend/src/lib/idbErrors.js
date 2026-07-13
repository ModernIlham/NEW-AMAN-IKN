// Klasifikasi error IndexedDB — SENGAJA dipisah tanpa dependensi berat (idb,
// axios) agar murni & mudah diuji unit (pola sama dengan syncStatus.js/occ.js).
//
// isQuotaExceeded: deteksi KUOTA penyimpanan terlampaui (perangkat nyaris
// penuh) lintas-peramban. Dipakai agar sync snapshot offline pada perangkat
// penuh degradasi anggun (layani cache sebagian) alih-alih crash / merusak cache.
export function isQuotaExceeded(err) {
  if (!err) return false;
  const e = err.target?.error || err;
  const name = e?.name || "";
  const code = e?.code;
  return (
    name === "QuotaExceededError" ||
    name === "NS_ERROR_DOM_QUOTA_REACHED" || // Firefox
    code === 22 ||                            // kode lawas (WebKit/Blink)
    code === 1014                             // kode lawas (Firefox)
  );
}
