import { useEffect, useRef } from "react";
import { usePenjagaPermintaan } from "./usePenjagaPermintaan";

/** Debounce read dengan tiket yang diinvalidasi saat query/scope berubah. */
export function usePencarianBaca({ lingkup, kunci, aktif = true, delay = 300,
  jalankan, padaMulai, padaHasil, padaGagal, padaSelesai, padaKosong }) {
  const lingkupPermintaan = JSON.stringify([lingkup, kunci, aktif]);
  const penjaga = usePenjagaPermintaan(lingkupPermintaan);
  const handlers = useRef(null);
  handlers.current = { jalankan, padaMulai, padaHasil, padaGagal, padaSelesai, padaKosong };
  useEffect(() => {
    if (!aktif) { handlers.current.padaKosong?.(); return undefined; }
    const tiket = penjaga.mulaiBaca("pencarian", lingkupPermintaan);
    if (!tiket) return undefined;
    const timer = setTimeout(async () => {
      const cb = handlers.current;
      cb.padaMulai?.();
      try {
        const hasil = await cb.jalankan(tiket.signal);
        if (penjaga.berlaku(tiket)) cb.padaHasil?.(hasil);
      } catch (error) {
        if (penjaga.berlaku(tiket)) cb.padaGagal?.(error);
      } finally {
        if (penjaga.selesai(tiket)) cb.padaSelesai?.();
      }
    }, delay);
    return () => { clearTimeout(timer); penjaga.batalkan("pencarian"); };
  }, [aktif, delay, lingkupPermintaan, penjaga]);
}
