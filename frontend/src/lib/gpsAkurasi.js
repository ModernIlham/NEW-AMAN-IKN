// Pemilihan koordinat GPS PALING AKURAT dari beberapa fix (jepretan foto) dalam
// SATU aset. `accuracy` = radius ketidakpastian dalam meter; makin KECIL makin
// presisi. Saat kamera terbuka, watchPosition mengalirkan fix terus-menerus;
// AssetForm memakai helper ini untuk mengunci koordinat aset ke fix TERBAIK
// (bukan fix terakhir yang mungkin ber-jitter) selagi surveyor memotret.
//
// Fungsi MURNI (tanpa DOM/IO) agar mudah diuji unit. lat/lng boleh string
// ("-6.175110") — dibaca sebagai angka.

// Konversi ke angka dengan KETAT: null/undefined/""/"  " → NaN (bukan 0).
// Perlu karena Number("")===0 & Number(null)===0 akan lolos uji finite palsu.
function keAngka(v) {
  if (v == null) return NaN;
  if (typeof v === "string" && v.trim() === "") return NaN;
  const n = Number(v);
  return Number.isFinite(n) ? n : NaN;
}

// Koordinat terbaca sebagai angka hingga (lat & lng ada dan finite).
export function koordinatValid(fix) {
  return !!fix && !Number.isNaN(keAngka(fix.lat)) && !Number.isNaN(keAngka(fix.lng));
}

// Akurasi ada, terhingga, dan ≥ 0 (0 = sempurna). null/negatif → tak valid.
export function akurasiValid(fix) {
  if (!koordinatValid(fix)) return false;
  const a = keAngka(fix.accuracy);
  return !Number.isNaN(a) && a >= 0;
}

// Apakah `baru` LEBIH AKURAT dari `lama`? (accuracy lebih kecil = lebih presisi)
// - `baru` tanpa akurasi valid → tak pernah dianggap lebih akurat.
// - `lama` tanpa akurasi valid (mis. null) tapi `baru` valid → `baru` menang
//   (naik dari "tak diketahui" ke terukur).
export function lebihAkurat(baru, lama) {
  if (!akurasiValid(baru)) return false;
  if (!akurasiValid(lama)) return true;
  return Number(baru.accuracy) < Number(lama.accuracy);
}

// Dari daftar fix, kembalikan yang accuracy-nya TERKECIL (paling akurat), atau
// null bila tak ada satu pun yang akurasinya valid.
export function pilihKoordinatTerbaik(daftar) {
  if (!Array.isArray(daftar)) return null;
  let best = null;
  for (const f of daftar) if (lebihAkurat(f, best)) best = f;
  return akurasiValid(best) ? best : null;
}
