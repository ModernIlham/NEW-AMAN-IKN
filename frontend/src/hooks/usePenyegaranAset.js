import { useCallback, useLayoutEffect, useRef } from "react";

/**
 * Callback muat ulang stabil untuk toolbar, timer WS, dan penutupan form.
 * Bukan hanya parameter yang harus terbaru: doFetch/doFetchStats membawa
 * closure kegiatan, filter lanjutan, antrean, dan jalur snapshot luring.
 * Simpan versi dari render yang sudah di-commit sebelum efek pemuatan berjalan.
 */
export function usePenyegaranAset(konteks) {
  const terbaru = useRef(konteks);
  useLayoutEffect(() => { terbaru.current = konteks; });

  return useCallback((page, { showLoading = false, preserveMobile = false } = {}) => {
    const p = terbaru.current;
    const pg = page !== undefined ? page : p.currentPage;
    const work = Promise.all([
      // Refresh latar boleh mempertahankan jendela infinite-scroll HP.
      p.doFetch(pg, p.pageSize, p.debouncedSearch, p.filterCategory, p.sortBy, false, preserveMobile),
      p.doFetchStats(p.debouncedSearch),
    ]);
    if (!showLoading) return work;
    p.setPageLoading(true);
    // Kembalikan rantai finally agar kegagalan tetap sampai ke pemanggil,
    // tanpa menciptakan promise turunan yang ditolak tanpa penanganan.
    return work.finally(() => p.setPageLoading(false));
  }, []);
}
