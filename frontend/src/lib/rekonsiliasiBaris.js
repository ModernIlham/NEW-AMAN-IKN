// Versi server monotonik; waktu kedatangan respons bukan ukuran kesegaran.
export function versiBaris(row) {
  const v = row?.version;
  if (typeof v !== "number" && typeof v !== "string") return null;
  if (v === "") return null;
  const n = Number(v);
  return Number.isSafeInteger(n) && n >= 1 ? n : null;
}

export function editTertunda(items, id) {
  // Konflik sengaja menampilkan pemenang dari server agar bisa ditinjau.
  // Muatan konflik tetap berada di antrean, tidak dihapus oleh rekonsiliasi.
  return items.find(it => it.isEdit && it.editId === id && !it.hadConflict);
}

export function gabungVersiBaris(lama, baru) {
  if (!lama) return baru;
  const vLama = versiBaris(lama), vBaru = versiBaris(baru);
  if (vLama != null && vBaru != null && vBaru < vLama) return lama;
  const hasil = { ...lama, ...baru };
  if (vBaru == null && vLama != null) hasil.version = lama.version;
  return hasil;
}

export function rekonsiliasiBaris(lama, baru, items = []) {
  const tertunda = editTertunda(items, baru.id);
  if (!tertunda) return gabungVersiBaris(lama, baru);
  // Jangan menaikkan versi dasar edit ke versi rekan: itu melewati OCC.
  if (lama) return lama;
  // Baris dimuat kembali setelah berganti halaman/reload saat masih luring.
  return { ...baru, ...tertunda.payload, id: baru.id,
    version: tertunda.baseVersion ?? baru.version,
    thumbnail: tertunda.payload?.photo || baru.thumbnail };
}

export function rekonsiliasiDaftar(lama, baru, items = []) {
  const indeks = new Map(lama.map(row => [row.id, row]));
  // Keanggotaan dan urutan tetap milik respons yang sudah tersaring di server.
  return baru.map(row => rekonsiliasiBaris(indeks.get(row.id), row, items));
}

export function perbaruiBaris(lama, baru, items = []) {
  return lama.map(row => row.id === baru.id ? rekonsiliasiBaris(row, baru, items) : row);
}
