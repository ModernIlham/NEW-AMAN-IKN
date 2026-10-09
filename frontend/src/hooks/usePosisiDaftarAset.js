import { useCallback, useLayoutEffect, useRef } from "react";

// Satu halaman memiliki dua pemilik gulir: main (panel/filter) dan daftar
// virtual di dalamnya. Rekam tepat sebelum commit, bukan saat request dimulai,
// agar gulir pengguna selama menunggu jaringan tetap dihormati.
export function usePosisiDaftarAset(mainRef, daftarRef) {
  const perekam = useRef(new Map());
  const utama = useRef(null);
  const daftarkan = useCallback((key, rekam) => {
    perekam.current.set(key, rekam);
    return () => { if (perekam.current.get(key) === rekam) perekam.current.delete(key); };
  }, []);
  const rekamPosisi = useCallback((termasukDaftar = false) => {
    const main = mainRef.current, daftar = daftarRef.current;
    if (main && daftar) utama.current = {
      main, daftar, offset: daftar.getBoundingClientRect().top,
    };
    if (termasukDaftar) perekam.current.forEach(rekam => rekam());
  }, [mainRef, daftarRef]);
  useLayoutEffect(() => {
    const posisi = utama.current;
    utama.current = null;
    if (!posisi || posisi.main !== mainRef.current || posisi.daftar !== daftarRef.current) return;
    // Hilangnya panel inline di atas daftar tidak boleh menggulir daftar jauh
    // dari posisi semula. Browser sendiri menjepit nilai di batas halaman.
    posisi.main.scrollTop = Math.max(0, posisi.main.scrollTop + posisi.daftar.getBoundingClientRect().top - posisi.offset);
  });
  return { daftarkan, rekamPosisi };
}

export function indeksJangkar(idsLama, index, assets) {
  const posisi = new Map(assets.map((a, i) => [a.id, i]));
  // Jika aset keluar dari filter, pilih tetangga terdekat yang masih ada.
  for (let jarak = 0; jarak < idsLama.length; jarak++) {
    for (const i of jarak ? [index + jarak, index - jarak] : [index]) {
      if (posisi.has(idsLama[i])) return posisi.get(idsLama[i]);
    }
  }
  return Math.max(0, Math.min(index, assets.length - 1));
}

export function useJangkarDaftarAset({ daftarkan, nama, assets, virtualizer, columns = 1 }) {
  const posisi = useRef(null);
  useLayoutEffect(() => {
    if (!daftarkan) return undefined;
    return daftarkan(nama, () => {
      const el = virtualizer.scrollElement;
      if (!el || !el.clientHeight || !assets.length) return;
      const item = virtualizer.getVirtualItems().find(row => row.end > el.scrollTop);
      if (!item) return;
      posisi.current = {
        ids: assets.map(a => a.id), index: item.index * columns,
        offset: Math.max(0, el.scrollTop - item.start), assets,
      };
    });
  }, [daftarkan, nama, assets, virtualizer, columns]);
  useLayoutEffect(() => {
    const lama = posisi.current;
    if (!lama || lama.assets === assets) return;
    posisi.current = null;
    if (!assets.length) return;
    const index = Math.floor(indeksJangkar(lama.ids, lama.index, assets) / columns);
    const offset = virtualizer.getOffsetForIndex(index, "start");
    if (offset) virtualizer.scrollToOffset(offset[0] + lama.offset, { behavior: "auto" });
  }, [assets, virtualizer, columns]);
}
