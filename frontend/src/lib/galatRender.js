// Klasifikasi galat RENDER (dipakai batas galat React) — logika murni, tanpa
// DOM, supaya bisa diuji langsung. Komponennya ada di components/BatasGalat.jsx.

/**
 * Apakah galat ini kegagalan MENGUNDUH potongan kode (bukan bug render)?
 *
 * Diperiksa lewat beberapa penanda karena tiap peramban/bundler menamainya
 * berbeda: webpack melempar `ChunkLoadError` dengan pesan "Loading chunk N
 * failed", sedangkan modul ES asli (Safari/Firefox) memakai kalimat "error
 * loading dynamically imported module", "Failed to fetch dynamically imported
 * module", atau "Importing a module script failed".
 *
 * Pembedaan ini menentukan tombol pemulihan yang ditawarkan — lihat catatan di
 * BatasGalat: potongan yang gagal TAK BISA diulang di tempat.
 */
/**
 * Teks galat yang bisa dibaca. Sengaja TIDAK memakai `err.message || err`:
 * `new Error("")` punya message kosong, dan fallback itu menghasilkan string
 * "Error" — kata yang lalu bocor ke layar operator sebagai seolah-olah pesan.
 */
function teksGalat(err) {
  if (typeof err === "string") return err;
  if (err && typeof err.message === "string") return err.message;
  return err === null || err === undefined ? "" : String(err);
}

export function galatUnduhPotongan(err) {
  if (!err) return false;
  if (String(err.name || "") === "ChunkLoadError") return true;
  // "Loading chunk 3 failed" (JS) DAN "Loading CSS chunk 3 failed" (CSS) —
  // webpack menyisipkan jenis berkas di tengah kalimat untuk yang kedua.
  return /loading (?:\w+ )?chunk|chunkloaderror|dynamically imported module|importing a module script failed/i
    .test(teksGalat(err));
}

/** Pesan yang dibaca operator — sengaja menyebut penyebab yang paling mungkin. */
export function pesanGalatRender(err) {
  if (galatUnduhPotongan(err)) {
    return "Bagian aplikasi ini gagal diunduh. Biasanya karena sinyal terputus, "
         + "atau versi baru aplikasi baru saja dipasang sehingga berkas lama "
         + "tidak ada lagi di server.";
  }
  const pesan = teksGalat(err).trim();
  return pesan
    ? `Terjadi galat saat menampilkan halaman ini: ${pesan}`
    : "Terjadi galat saat menampilkan halaman ini.";
}
