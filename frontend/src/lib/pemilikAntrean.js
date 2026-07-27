// ANTREAN LURING TERIKAT PEMILIKNYA.
//
// Rekaman antrean simpan hidup di IndexedDB per-ORIGIN, bukan per-akun. Di
// perangkat dinas yang dipakai bergantian, rehidrasi dulu memutar ulang
// simpanan tertunda MILIK AKUN LAIN — dikirim memakai token dan identitas
// audit akun yang sedang login. Jejak auditnya menyatakan si B mengubah aset
// yang sebenarnya dikerjakan si A, dan isolasi satker bisa menolaknya dengan
// 403 yang membingungkan (atau lebih buruk: menerimanya).
//
// Solusinya dua sentuhan: tiap rekaman distempel pemiliknya saat ditulis, dan
// rehidrasi hanya mengambil rekaman milik akun yang sedang login. Rekaman
// LAMA tanpa stempel tetap di-replay — kita tak bisa tahu pemiliknya, dan
// membuangnya berarti kehilangan pekerjaan orang; satu rilis kemudian semua
// rekaman baru sudah berstempel.

/** Identitas akun yang sedang login, atau "" bila tak diketahui. */
export function idPenggunaAktif() {
  try {
    const u = JSON.parse(localStorage.getItem("user") || "null");
    return String(u?.id || u?.username || "");
  } catch {
    return "";
  }
}

/**
 * Bolehkah rekaman ini di-replay oleh akun yang sedang login?
 *
 * - Rekaman berstempel milik akun LAIN → TIDAK (inilah cacatnya).
 * - Rekaman tanpa stempel (era lama)   → boleh, demi tak membuang pekerjaan.
 * - Identitas login tak diketahui      → boleh; menahannya hanya memindahkan
 *   masalah (rekaman menggantung selamanya) tanpa menutup risiko apa pun.
 */
export function bolehReplay(rekaman, idAktif) {
  const pemilik = String(rekaman?.pemilik || "");
  if (!pemilik) return true;
  if (!idAktif) return true;
  return pemilik === idAktif;
}
