// GABUNG DUA SIMPANAN YANG BELUM TERKIRIM ATAS ASET YANG SAMA.
//
// Antrean simpan mengunci tiap baris dengan `statusKey`; untuk EDIT kuncinya
// adalah `editId` — yang secara desain SAMA setiap kali aset itu disimpan.
// Kunci itu dipakai sebagai kunci PETA di tiga tempat (payload replay,
// IndexedDB `keyPath`, chip status), sehingga simpanan kedua atas aset yang
// sama dulu MENIMPA simpanan pertama yang belum sempat terkirim.
//
// Kenapa berbahaya, dan kenapa tak kelihatan:
//
//   Surveyor luring menambah FOTO ke aset A → gagal kirim (tak ada sinyal),
//   chip "belum tersinkron". Lalu ia menggeser pin aset A di peta, atau
//   membuka aset A lagi dan mengubah kondisinya. Simpanan kedua itu PATCH
//   ramping — hanya berisi field yang berubah, tanpa `photo_ops` — dan ia
//   menimpa rekaman simpanan pertama. Saat sinyal pulih, yang terkirim hanya
//   simpanan kedua. Fotonya tidak pernah sampai ke server, dan chip berakhir
//   "saved" seolah semuanya beres. Byte fotonya pun sudah tak ada di
//   perangkat: snapshot luring sengaja membuang foto sebelum menyimpan.
//
// Jalan keluarnya bukan menimpa dan bukan pula menolak simpanan kedua,
// melainkan MENGGABUNG keduanya. Ini sah justru karena simpanan pertama BELUM
// diterapkan ke server: kedua patch dihitung terhadap keadaan server yang
// sama, sehingga bisa dijadikan satu patch tanpa mengubah artinya.

/** Field yang tak boleh ikut digabung mentah-mentah (ditangani khusus). */
const KHUSUS = "photo_ops";

/**
 * Gabungkan `photo_ops` dua patch yang sama-sama belum diterapkan.
 *
 * Bentuknya `{ keep: [indeks foto server], add: [dataURL baru], thumbnail_index }`.
 *
 * - `keep` menunjuk POSISI foto di server. Karena tak satu pun patch sudah
 *   diterapkan, keadaan server belum bergeser — maka `keep` milik patch yang
 *   LEBIH BARU adalah kehendak terakhir pengguna atas foto-foto lama itu.
 * - `add` berisi foto BARU yang belum ada di server sama sekali. Keduanya
 *   harus selamat, jadi disatukan. Kalaupun pengguna kebetulan menambah foto
 *   yang sama dua kali, akibatnya foto kembar yang KELIHATAN dan bisa dihapus
 *   — jauh lebih baik daripada foto hilang yang tak kelihatan.
 */
export function gabungPhotoOps(lama, baru) {
  if (!lama) return baru;
  if (!baru) return lama;
  const tambah = [...(lama.add || []), ...(baru.add || [])];
  return {
    keep: Array.isArray(baru.keep) ? baru.keep : (lama.keep || []),
    add: tambah,
    // Sampul mengikuti kehendak terakhir; bila patch baru tak menyebutkannya,
    // pertahankan pilihan sebelumnya alih-alih diam-diam jatuh ke foto 0.
    thumbnail_index: baru.thumbnail_index != null ? baru.thumbnail_index : lama.thumbnail_index,
  };
}

/**
 * Gabungkan dua PAYLOAD patch menjadi satu. `baru` menang untuk field yang
 * sama — itu memang kehendak terakhir pengguna. Field yang HANYA ada di `lama`
 * ikut terbawa; di situlah foto yang tadinya hilang kini selamat.
 *
 * Hanya untuk dua patch yang sama-sama BELUM terkirim. Jangan dipakai
 * menggabung patch dengan sesuatu yang sudah diterapkan server.
 */
export function gabungPatch(lama, baru) {
  if (!lama || typeof lama !== "object") return baru;
  if (!baru || typeof baru !== "object") return lama;
  const hasil = { ...lama, ...baru };
  if (lama[KHUSUS] || baru[KHUSUS]) {
    hasil[KHUSUS] = gabungPhotoOps(lama[KHUSUS], baru[KHUSUS]);
  }
  return hasil;
}

/**
 * Bolehkah dua item antrean digabung?
 *
 * HANYA bila keduanya PATCH (usePatch) atas aset yang sama. Alasannya:
 *
 * - PUT/CREATE mengirim dokumen UTUH, jadi yang terakhir memang sudah memuat
 *   segalanya — menggabungnya tak menambah apa pun dan malah bisa
 *   menghidupkan kembali field yang sengaja dikosongkan pengguna.
 * - Menggabung CREATE dengan EDIT tak masuk akal: keduanya aset berbeda.
 */
export function bolehGabung(lama, baru) {
  if (!lama || !baru) return false;
  if (!lama.isEdit || !baru.isEdit) return false;
  if (!lama.usePatch || !baru.usePatch) return false;
  return String(lama.editId || "") === String(baru.editId || "");
}
