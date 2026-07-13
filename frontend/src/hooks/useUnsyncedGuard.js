import { useEffect } from "react";
import { hasUnsyncedWork } from "../lib/unloadGuard";

// Cegah kehilangan/kerusakan data offline saat MUAT ULANG atau berpindah ke
// versi aplikasi yang lebih baru: selama masih ada antrian yang perlu
// disinkronkan, tahan penutupan/reload halaman dengan dialog konfirmasi bawaan
// peramban ("beforeunload"). Antrian sendiri sudah persist di IndexedDB +
// auto-flush saat online (useOptimisticQueue) — guard ini lapisan pengaman
// TERAKHIR agar pengguna tidak menutup aplikasi di tengah sinkron tanpa sadar,
// lalu mengira datanya hilang.
export function useUnsyncedGuard({ pendingCount, actionCount } = {}) {
  const active = hasUnsyncedWork({ pendingCount, actionCount });
  useEffect(() => {
    if (!active) return undefined;
    const handler = (e) => {
      // Peramban modern mengabaikan teks kustom & menampilkan pesan generik,
      // tetapi keduanya (preventDefault + returnValue non-kosong) tetap wajib
      // di-set agar dialog konfirmasi muncul (Chrome/Firefox/Safari).
      e.preventDefault();
      e.returnValue = "Masih ada data yang belum tersinkron. Yakin memuat ulang / keluar?";
      return e.returnValue;
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [active]);
}
