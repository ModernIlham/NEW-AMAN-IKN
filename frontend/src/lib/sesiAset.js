// PENANDA GERBONG — foto harus pulang ke aset yang memang difoto.
//
// Mode Kamera Penuh membiarkan surveyor memotret aset demi aset tanpa pernah
// meninggalkan kamera. Karena form-nya SATU dan hanya berganti isi, foto yang
// jepretannya bersamaan dengan perpindahan aset bisa mendarat di aset yang
// keliru. Yang membuatnya berbahaya: foto itu sudah berstempel watermark berisi
// kode & NUP aset SEBELUMNYA, jadi begitu tersimpan, bukti visual dan data
// induknya bercerita berbeda — dan tidak ada satu pun pesan galat yang muncul.
//
// Ada dua jendela nyata tempat ini terjadi:
//
//   1. Saat simpan berjalan. handleSubmit menunggu kompresi foto (bisa
//      berdetik-detik di HP low-end dengan 6 foto). Foto yang diambil di
//      jendela itu masuk ke state SETELAH payload dibekukan.
//   2. Saat thumbnail dibuat. Jalur edit menunggu generateThumbnailFromDataUrl
//      sebelum menaruh foto ke daftar.
//
// Solusinya bukan menambal salah satu jendela, melainkan membuat foto MEMBAWA
// identitas aset yang dituju sejak rana ditekan, lalu memeriksanya lagi tepat
// sebelum foto benar-benar disimpan.

/**
 * Penanda aset yang sedang di depan kamera.
 *
 * `savedCount` ikut karena dalam alur "simpan lalu siapkan aset baru" id-nya
 * TIDAK berubah — keduanya sama-sama aset baru tanpa id. Tanpa penghitung ini,
 * dua aset berturut-turut punya penanda identik dan foto tetap bisa tertukar.
 */
export function buatSesiAset(assetId, savedCount) {
  return `${assetId || "baru"}#${Number(savedCount) || 0}`;
}

/**
 * Foto ini milik gerbong lain?
 *
 * `sesiJepret` undefined berarti pemanggil lama yang belum menyertakan penanda
 * (mis. unggah dari galeri, yang memang tak lewat kamera beruntun) — foto
 * seperti itu DITERIMA. Menolaknya akan mematikan jalur unggah biasa demi
 * masalah yang tak ada di sana.
 */
export function fotoNyasar(sesiJepret, sesiSekarang) {
  if (sesiJepret === undefined || sesiJepret === null) return false;
  return sesiJepret !== sesiSekarang;
}
