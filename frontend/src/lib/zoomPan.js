// Zoom & geser (pan) MURNI untuk penampil foto layar penuh — tanpa tombol.
// Interaksi: gulir roda tetikus (desktop) & cubit dua jari (HP) untuk
// perbesar/perkecil; seret untuk menggeser saat sudah diperbesar.
//
// Semua fungsi di sini MURNI (tanpa DOM/IO) agar mudah diuji unit; komponen
// (`PhotoLightbox.FullscreenPhoto`) hanya menyambungkan event ke fungsi ini.

export const SKALA_MIN = 1;
export const SKALA_MAKS = 5;

export const jepit = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

/** Batasi skala ke rentang [min, max]; nilai tak hingga → min. */
export function jepitSkala(s, min = SKALA_MIN, max = SKALA_MAKS) {
  return Number.isFinite(s) ? jepit(s, min, max) : min;
}

/**
 * Skala berikutnya dari gulir roda tetikus.
 * deltaY < 0 (gulir ke atas) → perbesar; deltaY > 0 → perkecil.
 * Memakai eksponensial agar langkah zoom terasa mulus & simetris.
 */
export function skalaGulir(scale, deltaY, { min = SKALA_MIN, max = SKALA_MAKS, faktor = 0.0016 } = {}) {
  const s = scale * Math.exp(-deltaY * faktor);
  return jepitSkala(s, min, max);
}

/** Skala dari cubit: skalaAwal × (jarakKini / jarakAwal). */
export function skalaCubit(scaleAwal, jarakAwal, jarakKini, { min = SKALA_MIN, max = SKALA_MAKS } = {}) {
  if (!(jarakAwal > 0)) return jepitSkala(scaleAwal, min, max);
  return jepitSkala(scaleAwal * (jarakKini / jarakAwal), min, max);
}

/** Jarak Euclidean antara dua titik sentuh. */
export function jarak(ax, ay, bx, by) {
  return Math.hypot(ax - bx, ay - by);
}

/** Titik tengah dua titik (fokus cubit). */
export function titikTengah(ax, ay, bx, by) {
  return { x: (ax + bx) / 2, y: (ay + by) / 2 };
}

/**
 * Geseran (tx,ty) baru agar titik fokus tetap "menempel" di tempat yang sama
 * pada layar saat skala berubah scale → sBaru. fokusX/fokusY = posisi fokus
 * RELATIF terhadap pusat viewport (px). Rumus: elemen dipusatkan di viewport,
 * konten di bawah fokus = (fokus − geser)/scale harus sama setelah zoom.
 */
export function zoomKeTitik(scale, tx, ty, sBaru, fokusX, fokusY) {
  if (!(scale > 0)) return { tx, ty };
  const k = sBaru / scale;
  return { tx: fokusX - k * (fokusX - tx), ty: fokusY - k * (fokusY - ty) };
}

/**
 * Batasi geseran agar foto tak bisa didorong hilang dari layar. Saat skala 1
 * hanya boleh bergoyang sedikit (margin); makin diperbesar makin bebas.
 */
export function jepitGeser(tx, ty, scale, vw, vh, margin = 40) {
  const maksX = Math.max(0, (scale - 1) * vw / 2) + margin;
  const maksY = Math.max(0, (scale - 1) * vh / 2) + margin;
  return { tx: jepit(tx, -maksX, maksX), ty: jepit(ty, -maksY, maksY) };
}
