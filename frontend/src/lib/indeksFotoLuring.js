// INDEKS STRIP ≠ INDEKS FINAL — kecuali semua foto terlihat.
//
// Saat edit DARING, strip foto menampilkan SEMUA foto aset (yang lama dari
// server + yang baru), sehingga indeks strip = indeks susunan akhir. Invarian
// itu diam-diam patah di jalur LURING: foto lama server tidak dimuat
// (mediaLoaded false), strip hanya berisi foto BARU, padahal backend menyusun
// susunan akhir sebagai [semua foto lama (keep)] + [foto baru (add)].
//
// Akibatnya, surveyor luring yang mengetuk foto barunya sebagai SAMPUL atau
// FOTO STIKER menyimpan indeks strip 0 — yang di susunan akhir justru menunjuk
// FOTO LAMA PERTAMA. Tak ada galat: backend meng-clamp indeks sehingga selalu
// "sah", badge di layar tetap menempel pada foto yang diketuk, dan salah
// fotonya baru kelihatan setelah sinkron — sampul daftar dan foto stiker di
// laporan menampilkan barang yang berbeda dari yang dipilih.
//
// Perbaikannya menggeser indeks TEPAT saat pengguna mengetuk, bukan saat
// submit: dengan begitu formData.thumbnail_index / stiker_photo_index selalu
// berisi indeks FINAL, dan jalur submit maupun backend tak perlu tahu apa-apa.

/**
 * Indeks susunan-akhir untuk foto pada posisi `indeksStrip` di strip.
 *
 * @param {number} indeksStrip     posisi foto di strip yang terlihat
 * @param {boolean} mediaDimuat    true bila foto server SUDAH dimuat ke strip
 * @param {number} jumlahFotoServer cacah foto lama di server (yang tak terlihat)
 */
export function keIndeksFinal(indeksStrip, mediaDimuat, jumlahFotoServer) {
  const offset = mediaDimuat ? 0 : Math.max(0, Number(jumlahFotoServer) || 0);
  return indeksStrip + offset;
}

export default keIndeksFinal;
