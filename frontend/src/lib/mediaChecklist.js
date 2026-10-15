// Posisi media pada respons server tidak mengikuti urutan rekomendasi/form.
// Metadata ini hanya untuk URL baca; sentinel tetap indeks foto/PDF per item.
export function indeksItemMedia(item, visualIndex) {
  return Number.isInteger(item?._serverItemIndex) && item._serverItemIndex >= 0
    ? item._serverItemIndex : visualIndex;
}

export function gabungMediaChecklist(current, serverItems) {
  const source = serverItems.map((item, index) => ({ item, index }));
  const byId = new Map(source.filter(entry => entry.item.id).map(entry => [entry.item.id, entry]));
  const used = new Set();
  return current.map(item => {
    const identified = item.id ? byId.get(item.id) : null;
    const entry = item.id
      ? (identified && !used.has(identified.index) ? identified : null)
      : source.find(candidate => !used.has(candidate.index) && candidate.item.name === item.name);
    if (!entry) return item;
    used.add(entry.index);
    const full = entry.item;
    return {
      ...item, ...(full.id ? { id: full.id } : {}), _serverItemIndex: entry.index,
      checked: full.checked != null ? full.checked : item.checked,
      notes: full.notes != null ? full.notes : item.notes,
      photos: Array.from({ length: Number(full.photo_count) || 0 }, (_, index) => `__existing__:${index}`),
      photo_thumbnails: full.photo_thumbnails || item.photo_thumbnails || [],
      documents: (full.documents || []).map((doc, index) => ({
        ...(doc.id ? { id: doc.id } : {}), name: doc.name || "document.pdf",
        data: `__existing__:${Number.isInteger(doc.idx) ? doc.idx : index}`,
      })),
    };
  });
}
