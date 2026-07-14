// "Salin dari aset sebelumnya" — logika CERDAS penyalinan koordinat GPS dari
// aset terakhir yang disimpan (localStorage `aman_last_asset_ctx`).
//
// Koordinat aset sebelumnya adalah titik awal yang WAJAR untuk aset berikutnya
// (di lapangan aset yang diinventarisasi beruntun biasanya berdekatan). Tapi
// penyalinannya dibuat "smart":
//   (a) JANGAN timpa koordinat yang sudah ada (GPS segar/manual di form ini);
//   (b) hanya salin bila konteks MASIH BARU — aset yang disimpan lama lalu
//       kemungkinan berada di lokasi jauh, menyalin koordinatnya justru salah;
//   (c) koordinat salinan bersifat SEMENTARA: GPS kamera yang akurat akan
//       menggantikannya begitu dapat fix (lihat AssetForm.handleCameraGpsFix).
//
// Fungsi MURNI (tanpa DOM/IO) agar mudah diuji unit.

const ada = (v) => v != null && String(v).trim() !== "";

/**
 * Boleh menyalin koordinat dari `ctx` ke form saat ini?
 * @param {object|null} ctx  - konteks aset sebelumnya {koordinat_latitude, koordinat_longitude, ts, ...}
 * @param {*} curLat         - koordinat_latitude form saat ini (string/null)
 * @param {*} curLng         - koordinat_longitude form saat ini
 * @param {number} now       - Date.now() (disuntik agar deterministik saat uji)
 * @param {number} [maxAgeMs] - ambang kesegaran konteks (default 30 menit)
 * @returns {boolean}
 */
export function bolehSalinKoordinat(ctx, curLat, curLng, now, maxAgeMs = 30 * 60 * 1000) {
  if (!ctx || !ada(ctx.koordinat_latitude) || !ada(ctx.koordinat_longitude)) return false;
  if (ada(curLat) || ada(curLng)) return false;                 // (a) jangan timpa
  if (typeof ctx.ts !== "number" || !Number.isFinite(ctx.ts)) return false;
  const usia = now - ctx.ts;
  return usia >= 0 && usia <= maxAgeMs;                          // (b) masih baru
}
