// CACHE FIX GPS TERAKHIR — dan kenapa ia butuh gerbang akurasi.
//
// Form aset memakai fix terakhir agar kolom koordinat langsung terisi saat
// surveyor membuka aset berikutnya, alih-alih menatap kolom kosong sambil
// menunggu GPS mengunci. Niatnya baik dan memang terasa cepat.
//
// Masalahnya, nilai itu berasal dari ASET LAIN. Selama ia sekadar tebakan awal
// yang akan segera ditimpa fix baru, tak apa. Yang berbahaya adalah dua hal:
//
//  1. **Tanpa gerbang akurasi.** Fix ±800 m (dalam gedung, A-GPS belum
//     mengunci) dulu ikut tersimpan dan diterapkan seolah setara fix ±5 m.
//     Rana kamera menolak memotret di atas ±8 m, tetapi jalur ini melewati
//     pemeriksaan itu sama sekali — sehingga justru titik terburuklah yang
//     bisa lolos ke basis data.
//  2. **Fix segar boleh gagal.** Bila permintaan fix baru tak pernah selesai,
//     nilai pinjaman itu TETAP di kolom dan ikut tersimpan saat aset disimpan.
//     Aset B akhirnya tercatat di titik aset A — kadang gedung yang berbeda.
//
// Karena itu akurasi ikut disimpan dan diperiksa saat dibaca. Fix yang tak
// menyertakan akurasi diperlakukan sebagai TIDAK LAYAK: lebih baik kolom
// kosong yang jujur daripada titik yang tampak sah padahal entah dari mana.

const KUNCI = "aman_last_gps";

/** Akurasi terlebar yang masih boleh dipinjam untuk aset lain (meter). */
export const MAKS_AKURASI_PINJAM_M = 30;
/** Umur maksimal fix pinjaman. Lebih tua dari ini, surveyor sudah pindah tempat. */
export const MAKS_USIA_PINJAM_MS = 5 * 60 * 1000;

export function simpanGpsTerakhir(lat, lng, accuracy) {
  if (lat == null || lng == null) return;
  try {
    localStorage.setItem(KUNCI, JSON.stringify({
      lat, lng,
      // null bila perangkat tak melaporkannya — dibaca sebagai "tak layak pinjam".
      akurasi: Number.isFinite(accuracy) ? Math.round(accuracy) : null,
      ts: Date.now(),
    }));
  } catch { /* localStorage penuh / mode privat — bukan alasan menggagalkan GPS */ }
}

/**
 * Fix terakhir yang LAYAK dipinjam untuk aset lain, atau null.
 *
 * Mengembalikan null jauh lebih sering daripada versi lama — dan itu memang
 * tujuannya. Kolom koordinat yang kosong akan diisi fix sungguhan beberapa
 * detik kemudian; koordinat yang salah tidak akan pernah memperbaiki dirinya.
 */
export function ambilGpsTerakhir(sekarang = Date.now()) {
  let c = null;
  try { c = JSON.parse(localStorage.getItem(KUNCI) || "null"); } catch { return null; }
  if (!c || c.lat == null || c.lng == null) return null;
  if (!Number.isFinite(c.akurasi)) return null;              // tak diketahui → tolak
  if (c.akurasi > MAKS_AKURASI_PINJAM_M) return null;        // terlalu lebar
  if (!Number.isFinite(c.ts) || sekarang - c.ts > MAKS_USIA_PINJAM_MS) return null;
  return { lat: c.lat, lng: c.lng, akurasi: c.akurasi, ts: c.ts };
}
