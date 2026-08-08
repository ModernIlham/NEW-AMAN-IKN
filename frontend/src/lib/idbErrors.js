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

/**
 * Keputusan saat MENULIS antrean simpan (kerja yang belum terkirim) gagal.
 *
 * Beda kelas dari gagal menulis cache BACA, dan perbedaan itulah intinya:
 * cache baca selalu bisa ditarik ulang dari server, sedangkan muatan antrean
 * — termasuk fotonya, 900 KB per lembar sampai 6 lembar — hanya ada di
 * perangkat ini. Bila penulisannya gagal karena KUOTA, antrean cuma hidup di
 * memori: chip barisnya tetap menampilkan "queued" seperti biasa, lalu begitu
 * tab ditutup atau di-swap keluar oleh Android, seluruhnya lenyap tanpa satu
 * pesan pun. Pengguna baru sadar berhari-hari kemudian, di kantor.
 *
 * Galat lain (store hilang, DB diblokir versi lama, mode privat) tidak punya
 * obat yang bisa dikerjakan pengguna di lapangan, jadi tetap dicatat diam
 * agar tidak menambah kebisingan di tengah pekerjaan.
 *
 * @returns {"beri_tahu_pengguna"|"catat_diam"}
 */
export function keputusanGagalTulisAntrean(err) {
  return isQuotaExceeded(err) ? "beri_tahu_pengguna" : "catat_diam";
}
