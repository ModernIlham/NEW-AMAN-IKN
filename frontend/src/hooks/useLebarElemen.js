import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Ukur lebar KONTEN sebuah elemen dan ikuti perubahannya.
 *
 * Dipakai toolbar yang harus tetap satu baris: breakpoint Tailwind membaca
 * viewport, sedangkan toolbar bisa berada di dalam panel sempit pada layar
 * lebar (lihat `lib/labelRingkas`). Yang menentukan muat/tidak adalah lebar
 * kontainer — jadi lebar itulah yang diukur.
 *
 * @returns {[(el: HTMLElement|null) => void, number]} `[ref, lebar]`.
 *   `lebar` = 0 selama belum terukur (termasuk saat elemen `display:none`);
 *   pemanggil memperlakukan 0 sebagai "pakai bentuk paling ringkas".
 */
export default function useLebarElemen() {
  const [lebar, setLebar] = useState(0);
  const pengamatRef = useRef(null);

  const ref = useCallback((el) => {
    // Callback ref dipanggil dengan null saat elemen dilepas / diganti —
    // pengamat lama WAJIB diputus di sini, kalau tidak ia terus memanggil
    // setState pada komponen yang sudah tak ada.
    if (pengamatRef.current) {
      pengamatRef.current.disconnect();
      pengamatRef.current = null;
    }
    if (!el) return;

    if (typeof ResizeObserver === "undefined") {
      // Peramban tanpa ResizeObserver (dan jsdom pada uji unit): ukur sekali,
      // tanpa mengikuti perubahan. Bila hasilnya 0 pun, jangan biarkan nilai
      // itu lolos — 0 berarti "ringkas total", dan di lingkungan ini label
      // tak akan pernah muncul kembali. Anggap ruangnya luas.
      const w = el.getBoundingClientRect().width;
      setLebar(w > 0 ? w : Number.MAX_SAFE_INTEGER);
      return;
    }

    const pengamat = new ResizeObserver((entri) => {
      const w = entri[0]?.contentRect?.width ?? 0;
      // Abaikan riak sub-piksel: tanpa ini setiap gerakan kecil memicu render
      // ulang toolbar, dan pembulatan bisa membuat label kedip-kedip di ambang.
      setLebar((sebelum) => (Math.abs(sebelum - w) < 1 ? sebelum : w));
    });
    pengamat.observe(el);
    pengamatRef.current = pengamat;
    setLebar(el.getBoundingClientRect().width);
  }, []);

  useEffect(
    () => () => {
      if (pengamatRef.current) {
        pengamatRef.current.disconnect();
        pengamatRef.current = null;
      }
    },
    [],
  );

  return [ref, lebar];
}
