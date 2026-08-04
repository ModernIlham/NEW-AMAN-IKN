/**
 * Penjaga "aksi yang butuh nama dulu" — dipakai Peta Kolaborasi.
 *
 * Tamu boleh menambah titik/komentar, tetapi harus mengisi namanya lebih dulu.
 * Polanya: aksi ditahan, dialog nama dibuka, lalu aksi dijalankan setelah nama
 * terisi.
 *
 * BUG YANG DIJAGA HELPER INI (pernah terjadi & merusak data):
 * dulu aksi ditahan sebagai closure React lalu dijalankan tepat setelah
 * `setNama(n)` pada tick yang SAMA. Karena setState tidak menyegarkan closure
 * lama, aksi itu masih membaca `nama` versi lama — yaitu string kosong. POST
 * terkirim `oleh: ""`, backend mengubahnya jadi "Tamu" dan MENYIMPANNYA, jadi
 * nama tamu tak pernah muncul dan refresh pun tak menyembuhkan.
 *
 * Karena itu helper ini MENYERAHKAN NAMA SEBAGAI ARGUMEN ke aksi. Aksi dilarang
 * membaca nama dari state — satu-satunya sumber adalah argumen yang diterimanya.
 */

/**
 * @returns {{jalankan: function, lanjutkan: function, batalkan: function,
 *            adaTertunda: function}}
 */
export function buatPenjagaNama() {
  let tertunda = null;

  return {
    /**
     * Jalankan `aksi(nama)` bila nama sudah ada / tak diperlukan.
     * Bila belum, tahan aksinya dan kembalikan true (pemanggil membuka dialog).
     */
    jalankan(aksi, { perluNama = true, nama = "" } = {}) {
      if (!perluNama || String(nama || "").trim()) {
        aksi(nama);
        return false;
      }
      tertunda = aksi;
      return true;
    },

    /** Lanjutkan aksi tertunda dengan nama BARU. true bila ada yang dijalankan. */
    lanjutkan(namaBaru) {
      const aksi = tertunda;
      tertunda = null;
      if (!aksi) return false;
      aksi(namaBaru);
      return true;
    },

    /** Buang aksi tertunda (dialog ditutup tanpa mengisi nama). */
    batalkan() {
      tertunda = null;
    },

    adaTertunda() {
      return !!tertunda;
    },
  };
}
