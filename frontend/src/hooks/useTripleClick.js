import { useRef, useCallback } from "react";

/**
 * Halaman tersembunyi (InfoPage) tidak boleh terbuka karena logo tersentuh
 * tak sengaja — kini butuh 3 KLIK beruntun pada logo (jeda antar-klik maks
 * `windowMs`; lewat dari itu hitungan diulang dari nol).
 *
 * Aktivasi keyboard (Enter/Spasi) dihitung sama dengan klik.
 */
export function useTripleClick(callback, { clicks = 3, windowMs = 1500 } = {}) {
  const countRef = useRef(0);
  const timerRef = useRef(null);
  return useCallback(() => {
    countRef.current += 1;
    if (timerRef.current) clearTimeout(timerRef.current);
    if (countRef.current >= clicks) {
      countRef.current = 0;
      callback?.();
      return;
    }
    timerRef.current = setTimeout(() => { countRef.current = 0; }, windowMs);
  }, [callback, clicks, windowMs]);
}

export default useTripleClick;
