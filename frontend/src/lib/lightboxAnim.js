// Parameter animasi geser kartu info lightbox — dihitung dari offset drag (px).
// SENGAJA murni & bebas DOM agar mudah diuji unit.
//
// Konvensi: dx > 0 = geser KANAN (menuju aset SEBELUMNYA), dx < 0 = geser KIRI
// (menuju aset BERIKUTNYA) — searah gestur jempol.
//
// Kartu tetangga (peek) mulai SAMAR (base) lalu opacity-nya bertambah mengikuti
// jauh-dekat geseran sampai `peak`; kartu depan sedikit mengecil (frontScale)
// agar terasa ada kedalaman/berlapis saat digeser.
export function peekAnim(dx, { threshold = 110, base = 0.3, peak = 0.95 } = {}) {
  const d = Number(dx) || 0;
  const p = Math.min(1, Math.abs(d) / (threshold || 1)); // 0..1 progress geser
  const grow = base + p * (peak - base);
  return {
    dragP: p,
    nextOpacity: d < 0 ? grow : base, // kartu KANAN = aset berikutnya (muncul saat geser kiri)
    prevOpacity: d > 0 ? grow : base, // kartu KIRI = aset sebelumnya (muncul saat geser kanan)
    frontScale: 1 - p * 0.03,         // kartu depan menyusut halus → efek kedalaman
  };
}
