/**
 * Kegiatan inventarisasi terakhir yang dibuka — disimpan di localStorage agar
 * reload (dan reload LURING) langsung kembali ke dashboard kegiatan itu.
 *
 * Tiga kunci: `currentActivityId`, `currentActivity` (salinan objek dari
 * server), dan `currentActivityOwner` (id akun pemilik salinan).
 *
 * Kenapa ada pemilik: logout otomatis/sesi habis SENGAJA menyisakan kegiatan
 * terakhir (lihat `forceLogout` di App.js) supaya pengguna yang sama kembali
 * ke tempatnya. Tanpa pemilik, akun LAIN di peramban yang sama akan sekejap
 * melihat kegiatan milik orang lain sebelum server menolak.
 */
const KUNCI_ID = "currentActivityId";
const KUNCI_OBJEK = "currentActivity";
const KUNCI_PEMILIK = "currentActivityOwner";

function salinanCocok(id) {
  const cached = JSON.parse(localStorage.getItem(KUNCI_OBJEK) || "null");
  return id && cached?.id === id ? cached : null;
}

/**
 * Salinan untuk tampil SEKETIKA saat dashboard dimuat — hanya bila pemiliknya
 * akun ini. Salinan era lama (tanpa pemilik) tidak dipakai di sini: jalurnya
 * kembali ke perilaku lama (menunggu server), aman walau tak lebih cepat.
 */
export function bacaKegiatanTersimpan(userId) {
  try {
    const id = localStorage.getItem(KUNCI_ID);
    if (!userId || localStorage.getItem(KUNCI_PEMILIK) !== String(userId)) return null;
    return salinanCocok(id);
  } catch { return null; }
}

/**
 * Cadangan saat server tak menjawab pasti (luring, 5xx, 429, 401). Salinan
 * era lama tanpa pemilik tetap diterima — reload luring pengguna lapangan tak
 * boleh rusak tepat sesudah rilis ini — tetapi salinan milik AKUN LAIN tidak.
 */
export function cadanganKegiatanLuring(storedId, userId) {
  try {
    const pemilik = localStorage.getItem(KUNCI_PEMILIK);
    if (pemilik && pemilik !== String(userId || "")) return null;
    return salinanCocok(storedId);
  } catch { return null; }
}

export function simpanKegiatanTersimpan(activity, userId) {
  try {
    localStorage.setItem(KUNCI_ID, activity.id);
    localStorage.setItem(KUNCI_OBJEK, JSON.stringify(activity));
    if (userId) localStorage.setItem(KUNCI_PEMILIK, String(userId));
    else localStorage.removeItem(KUNCI_PEMILIK);
  } catch { /* penyimpanan penuh/diblokir — tetap jalan tanpa cache */ }
}

export function hapusKegiatanTersimpan() {
  try {
    localStorage.removeItem(KUNCI_ID);
    localStorage.removeItem(KUNCI_OBJEK);
    localStorage.removeItem(KUNCI_PEMILIK);
  } catch { /* abaikan */ }
}
