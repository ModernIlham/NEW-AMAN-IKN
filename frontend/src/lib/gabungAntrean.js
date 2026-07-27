// KAPAN DUA SIMPANAN ATAS ASET YANG SAMA BOLEH DIGABUNG.
//
// Aturan ini hidup di `useOptimisticQueue` sejak PR #642/#643, dan audit
// adversarial menemukan bahwa SELURUHNYA tak tersentuh uji apa pun: berkas
// yang bernama `useOptimisticQueue.test.js` bahkan tak mengimpor hook-nya.
// Repo ini tak memasang @testing-library, jadi hook-nya memang tak bisa
// dirender — tetapi KEPUTUSANNYA bisa dipisahkan dan diuji, persis seperti
// gabungPatch/pemilikAntrean/sekaliJalan sebelumnya.
//
// Dua tempat memanggilnya, dan bedanya HALUS tetapi menentukan:
//
//   enqueue    → simpanan baru datang. Yang lama boleh digabung HANYA bila ia
//                belum terbang. Kalau sedang terbang, server mungkin sudah
//                menerapkannya; menggabung isinya ke simpanan kedua berarti
//                `photo_ops.add` diterapkan DUA KALI — foto kembar.
//
//   kegagalan  → simpanan baru GAGAL. Di sini yang lama justru TERBUKTI belum
//                diterapkan (ia ada di daftar gagal), sehingga penggabungan
//                aman dan WAJIB: keduanya berebut satu kunci `statusKey`, dan
//                tanpa digabung yang belakangan menghapus muatan yang pertama
//                beserta fotonya, tanpa satu pesan pun.
import { bolehGabung } from "./gabungPatch";

/**
 * Simpanan tertunda yang boleh digabung saat simpanan BARU di-enqueue,
 * atau null.
 *
 * @param {Object} failedItems   peta statusKey → simpanan gagal
 * @param {string} statusKey
 * @param {Object} calon         {isEdit, usePatch, editId} simpanan baru
 * @param {boolean} sedangTerbang simpanan atas aset ini sedang dikirim?
 */
export function tertundaUntukEnqueue(failedItems, statusKey, calon, sedangTerbang) {
  if (sedangTerbang) return null;
  const tertunda = (failedItems || {})[statusKey];
  return tertunda && bolehGabung(tertunda, calon) ? tertunda : null;
}

/**
 * Rekaman gagal SEBELUMNYA yang muatannya harus diserap saat simpanan ini
 * ikut gagal, atau null.
 *
 * `antreanId` yang SAMA berarti ini percobaan ulang simpanan yang itu-itu juga;
 * menggabungnya dengan dirinya sendiri akan menambahkan `photo_ops.add` dua
 * kali ke muatan yang sama.
 */
export function tertundaUntukKegagalan(sebelumnya, item) {
  if (!sebelumnya || !item) return null;
  if (sebelumnya.antreanId === item.antreanId) return null;
  return bolehGabung(sebelumnya, item) ? sebelumnya : null;
}
