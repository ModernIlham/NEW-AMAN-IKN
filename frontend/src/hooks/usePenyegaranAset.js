import { useCallback, useLayoutEffect, useRef } from "react";
import { HASIL_USANG } from "./usePenjagaPermintaan";

/**
 * Callback muat ulang stabil untuk toolbar, timer WS, dan penutupan form.
 * Bukan hanya parameter yang harus terbaru: doFetch/doFetchStats membawa
 * closure kegiatan, filter lanjutan, antrean, dan jalur snapshot luring.
 * Simpan versi dari render yang sudah di-commit sebelum efek pemuatan berjalan.
 */
export function usePenyegaranAset(konteks) {
  const terbaru = useRef(konteks);
  const pemilik = useRef(0);
  const tampil = useRef(false);
  const terpasang = useRef(false);
  useLayoutEffect(() => { terbaru.current = konteks; });
  useLayoutEffect(() => {
    const urutan = pemilik;
    terpasang.current = true;
    // Lingkup berubah: callback lama tidak berhak menutup skeleton baru.
    if (tampil.current) {
      tampil.current = false;
      terbaru.current.setPageLoading(false);
    }
    return () => { terpasang.current = false; urutan.current++; };
  }, [konteks.lingkupPermintaan]);

  return useCallback((page, { showLoading = false, preserveMobile = false, hanyaDaftar = false } = {}) => {
    if (!terpasang.current) return Promise.resolve([HASIL_USANG, HASIL_USANG]);
    const p = terbaru.current;
    const tiket = ++pemilik.current;
    const pg = page !== undefined ? page : p.currentPage;
    if (showLoading) { tampil.current = true; p.setPageLoading(true); }
    // Refresh latar yang menyusul mewarisi skeleton yang masih tampil,
    // sehingga finally permintaan lama tidak mematikannya terlalu cepat.
    const work = Promise.all([
      // Refresh latar boleh mempertahankan jendela infinite-scroll HP.
      p.doFetch(pg, p.pageSize, p.debouncedSearch, p.filterCategory, p.sortBy, false, preserveMobile),
      hanyaDaftar ? undefined : p.doFetchStats(p.debouncedSearch),
    ]);
    // Kembalikan rantai finally agar kegagalan tetap sampai ke pemanggil,
    // tanpa menciptakan promise turunan yang ditolak tanpa penanganan.
    return work.then(hasil => (
      terpasang.current && tiket === pemilik.current ? hasil : [HASIL_USANG, HASIL_USANG]
    )).finally(() => {
      if (!terpasang.current || tiket !== pemilik.current) return;
      if (tampil.current) { tampil.current = false; p.setPageLoading(false); }
      p.setLoading?.(false);
    });
  }, []);
}
