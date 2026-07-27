// SATU PENERBANGAN PER KUNCI (single-flight).
//
// Pola gagal yang ditutup helper ini: sebuah cache di-seed lewat pekerjaan
// asinkron, dan DUA pemanggil serentak sama-sama melihat cache masih kosong.
// Keduanya menjalankan seeding, dan yang selesai BELAKANGAN menimpa hasil
// pihak yang sudah lebih dulu maju. Untuk urutan NUP dummy, itu berarti dua
// aset lahir dengan NOMOR YANG SAMA — kembar yang baru ketahuan saat sinkron
// (atau lebih buruk: tidak ketahuan sama sekali).
//
// Prinsipnya: yang di-memo bukan HASILNYA, melainkan JANJINYA. Pemanggil kedua
// tidak memulai penerbangan baru — ia menumpang janji yang sedang terbang,
// sehingga seeding terjadi tepat satu kali per kunci.

/**
 * Jalankan `fn` sekali per `kunci`; pemanggil serentak menumpang janji yang
 * sama. Setelah selesai (sukses ATAU gagal) janji dilepas dari peta — kegagalan
 * tidak boleh menyandera kunci itu selamanya.
 *
 * @param {Object} peta   penyimpan janji per kunci (module-level milik pemanggil)
 * @param {string} kunci
 * @param {() => Promise<any>} fn
 */
export function sekaliJalan(peta, kunci, fn) {
  if (peta[kunci]) return peta[kunci];
  const janji = Promise.resolve()
    .then(fn)
    .finally(() => { delete peta[kunci]; });
  peta[kunci] = janji;
  return janji;
}

export default sekaliJalan;
