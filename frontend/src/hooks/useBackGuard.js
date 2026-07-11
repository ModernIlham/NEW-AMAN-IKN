import { useEffect, useRef } from "react";

/**
 * Penjaga tombol Back/Undo browser (termasuk gesture geser di HP) agar navigasi
 * TETAP di dalam aplikasi, tidak berpindah ke halaman/situs lain.
 *
 * Cara kerja: satu entri "sentinel" ditanam ke riwayat browser. Saat Back
 * ditekan, sentinel itu yang dikonsumsi (bukan URL sebelumnya), lalu handler
 * TERATAS dijalankan untuk melakukan navigasi INTERNAL (menutup overlay teratas
 * atau kembali ke daftar kegiatan), dan sentinel ditanam ulang — sehingga Back
 * tidak pernah keluar dari aplikasi. Karena setiap Back mengonsumsi satu entri
 * lalu pushState memangkas entri maju, jumlah entri riwayat tetap terbatas.
 *
 * Semua overlay/halaman memakai hook yang SAMA. Hanya SATU listener popstate
 * global yang dipasang, dengan tumpukan handler (LIFO): handler yang paling
 * akhir didaftarkan (overlay paling atas) yang menang — mencegah dua guard
 * menutup dua hal sekaligus.
 */
const handlerStack = [];
let installed = false;

function seedSentinel() {
  try {
    window.history.pushState({ __amanBackGuard: true }, "");
  } catch {
    /* beberapa konteks (mis. sandbox) melarang pushState — abaikan saja */
  }
}

function handlePopState() {
  // Tanam ulang sentinel LEBIH DULU supaya Back tidak pernah keluar aplikasi,
  // apa pun yang terjadi di handler.
  seedSentinel();
  const top = handlerStack[handlerStack.length - 1];
  if (top) {
    try { top(); } catch { /* handler tak boleh melumpuhkan penjaga */ }
  }
}

function ensureInstalled() {
  if (installed || typeof window === "undefined") return;
  installed = true;
  seedSentinel();
  window.addEventListener("popstate", handlePopState);
}

/**
 * @param {() => void} onBack - dipanggil saat Back ditekan (navigasi internal).
 * @param {boolean} [active=true] - daftarkan hanya saat overlay/halaman aktif.
 */
export function useBackGuard(onBack, active = true) {
  const ref = useRef(onBack);
  useEffect(() => { ref.current = onBack; });

  useEffect(() => {
    if (!active) return undefined;
    ensureInstalled();
    // Bungkus lewat ref agar handler selalu memakai closure terbaru tanpa perlu
    // mendaftar ulang tiap render.
    const entry = () => ref.current?.();
    handlerStack.push(entry);
    return () => {
      const i = handlerStack.lastIndexOf(entry);
      if (i >= 0) handlerStack.splice(i, 1);
    };
  }, [active]);
}

export default useBackGuard;
