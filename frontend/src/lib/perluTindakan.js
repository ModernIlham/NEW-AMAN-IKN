// Daftar simpanan MACET untuk panel "Perlu Tindakan" (lencana oranye header).
//
// Murni tanpa dependensi (axios/idb/sonner) agar mudah diuji unit.
//
// Sumber kebenaran JUMLAH adalah `syncStatuses` — sama persis dengan yang
// dihitung `summarizeSyncStatuses().actionCount` — sehingga angka di lencana
// dan isi panel tidak pernah berbeda. Rinciannya (nama barang, pesan server,
// jenis penolakan) diperkaya dari item antrean pertama per `statusKey`
// (operasi tertua yang menahan baris itu; antrean memblokir penerusnya).

/** @typedef {"konflik"|"terkunci"|"ditolak"} JenisTindakan */

export const INFO_JENIS = {
  konflik: {
    judul: "Bentrok versi",
    sebab: "Aset ini diubah pengguna lain sebelum perubahan Anda terkirim.",
    saran: "Lihat aset untuk membandingkan isian terbaru. Pilih \"Kirim perubahan saya\" untuk menerapkan perubahan Anda di atas versi terbaru, atau \"Abaikan\" untuk memakai versi server.",
    labelUlang: "Kirim perubahan saya",
  },
  terkunci: {
    judul: "Kegiatan terkunci",
    sebab: "Kegiatan sudah dikunci/disahkan sehingga perubahan tidak diterima.",
    saran: "Minta admin membuka kunci kegiatan, lalu pilih \"Coba lagi\". Bila perubahan tidak lagi diperlukan, pilih \"Abaikan\".",
    labelUlang: "Coba lagi",
  },
  ditolak: {
    judul: "Ditolak server",
    sebab: "Server menolak simpanan ini.",
    saran: "Baca pesan di atas. Bila penyebabnya sudah diatasi (mis. sudah masuk kembali), pilih \"Coba lagi\". Bila isiannya tidak valid, pilih \"Abaikan\" lalu isi ulang lewat form.",
    labelUlang: "Coba lagi",
  },
};

/**
 * Jenis tindakan untuk satu entri syncStatuses; null bila bukan item macet.
 * Selaras dengan summarizeSyncStatuses: macet = "conflict" ATAU
 * "failed" + locked (423 terkunci / 4xx ditolak).
 */
export function jenisTindakan(status, item) {
  if (!status || !status.status) return null;
  if (status.status === "conflict") return "konflik";
  if (status.status === "failed" && status.locked) {
    return item?.state?.status === "locked" ? "terkunci" : "ditolak";
  }
  return null;
}

/**
 * @param {Object} p
 * @param {Object} p.syncStatuses  peta statusKey → {status, error, locked}
 * @param {Array}  p.items         item antrean (getPendingItems())
 * @param {string} p.activityId    kegiatan yang sedang dibuka
 * @param {(id:string)=>Object|undefined} [p.cariAset] baris aset yang sudah dimuat
 * @param {(payload:Object)=>boolean} [p.adaMedia] payload menyentuh foto/dokumen
 */
export function daftarPerluTindakan({ syncStatuses, items, activityId, cariAset, adaMedia } = {}) {
  const pertama = new Map();
  for (const item of items || []) {
    if (item?.statusKey && !pertama.has(item.statusKey)) pertama.set(item.statusKey, item);
  }
  const hasil = [];
  for (const [statusKey, status] of Object.entries(syncStatuses || {})) {
    const item = pertama.get(statusKey);
    const jenis = jenisTindakan(status, item);
    if (!jenis) continue;
    const isEdit = item ? !!item.isEdit : false;
    const assetId = isEdit ? (item.editId || statusKey) : statusKey;
    const aset = cariAset?.(assetId) || null;
    const payload = item?.payload || {};
    const kegiatanItem = payload.activity_id || aset?.activity_id || null;
    hasil.push({
      statusKey,
      jenis,
      isEdit,
      assetId,
      nama: aset?.asset_name || payload.asset_name || "",
      kode: aset?.asset_code || payload.asset_code || "",
      nup: aset?.NUP ?? payload.NUP ?? "",
      pesan: status.error || item?.state?.error || "",
      queuedAt: item?.queuedAt || null,
      namaKegiatan: item?.nama_kegiatan || "",
      // null = tak diketahui (edit parsial yang barisnya belum termuat)
      kegiatanLain: kegiatanItem && activityId ? kegiatanItem !== activityId : null,
      adaMedia: !!(adaMedia && item?.payload && adaMedia(item.payload)),
      // Aset BARU yang belum pernah tersimpan tak bisa dibuka di form edit.
      bisaDibuka: isEdit,
    });
  }
  // Kegiatan aktif dulu, lalu yang tertua (paling lama tertahan) di atas.
  return hasil.sort((a, b) => (a.kegiatanLain === true) - (b.kegiatanLain === true)
    || String(a.queuedAt || "").localeCompare(String(b.queuedAt || "")));
}

/** Label ringkas aset untuk judul kartu. */
export function labelAset(entri) {
  const nama = entri?.nama || (entri?.isEdit ? "Aset" : "Aset baru");
  const kode = [entri?.kode, entri?.nup !== "" && entri?.nup != null ? `NUP ${entri.nup}` : ""]
    .filter(Boolean).join(" · ");
  return { nama, kode };
}
