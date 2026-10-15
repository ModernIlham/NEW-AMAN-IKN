// Semua operasi dibatasi ID yang terlihat. Seleksi di halaman/filter lain
// dipertahankan sampai pengguna memilih tindakan "Hapus seleksi".
export function statusSeleksiHalaman(selectedIds, visibleIds) {
  const ids = new Set(visibleIds);
  let count = 0;
  ids.forEach(id => { if (selectedIds?.has(id)) count += 1; });
  return {
    count,
    total: ids.size,
    all: ids.size > 0 && count === ids.size,
    partial: count > 0 && count < ids.size,
  };
}

export function toggleSeleksiHalaman(selectedIds, visibleIds) {
  const ids = new Set(visibleIds);
  const { all } = statusSeleksiHalaman(selectedIds, ids);
  const next = new Set(selectedIds);
  ids.forEach(id => { if (all) next.delete(id); else next.add(id); });
  return next;
}
