// Optimistic Concurrency (OCC) — helper murni tanpa dependensi, mudah diuji.
//
// resolveBaseVersion menentukan angka versi untuk header If-Match saat sebuah
// simpanan antrian dikirim. Masalah yang diperbaiki: edit BERANTAI atas aset
// yang sama dalam satu sesi. Simpanan pertama menaikkan versi server (mis. 5→6)
// dan kita catat 6 di `lastSavedVersion`; namun simpanan kedua masih membawa
// `baseVersion` = 5 (versi saat form dimuat) → If-Match 5 → server (6) menolak
// 409 → toast "diubah pengguna lain" MUNCUL TERUS walau hanya satu pengguna.
//
// Solusi: pakai versi TERTINGGI yang kita ketahui (versi monotonik naik). Kita
// hanya pernah MENAIKKAN base ke versi hasil simpanan kita sendiri yang sudah
// dikonfirmasi server — TAK PERNAH menurunkannya. Maka edit orang lain yang
// benar-benar lebih baru (versi lebih tinggi dari yang pernah kita simpan) tetap
// memicu 409 yang sah (bukan ditutupi).
export function resolveBaseVersion(itemBaseVersion, lastSavedVersion) {
  const b = Number.isFinite(itemBaseVersion) ? itemBaseVersion : null;
  const l = Number.isFinite(lastSavedVersion) ? lastSavedVersion : null;
  if (b == null) return l;
  if (l == null) return b;
  return Math.max(b, l);
}

export default resolveBaseVersion;
