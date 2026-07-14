import { useEffect } from "react";
import { hasUnsyncedWork } from "../lib/unloadGuard";

// Muat ulang / tutup halaman yang RAMAH tapi AMAN untuk data offline.
//
// Perilaku:
//  - TIDAK ada antrian yang perlu disinkron → tak memasang apa pun: muat ulang
//    berjalan biasa (pembaruan aplikasi lancar, tanpa dialog & tanpa repot
//    hapus cache).
//  - ADA antrian & ONLINE → JANGAN tahan dgn dialog konfirmasi. Otomatis
//    pancing sinkron (best-effort) lalu biarkan reload berjalan. Antrian juga
//    persist di IndexedDB + auto-flush saat load berikutnya (useOptimisticQueue),
//    jadi tak ada satu data pun yang tertinggal — semua dialihkan ke server.
//  - ADA antrian & OFFLINE → tahan dgn konfirmasi bawaan peramban: data belum
//    bisa dikirim, cegah pengguna menutup aplikasi menyangka semua sudah beres.
export function useUnsyncedGuard({ pendingCount, actionCount, isOnline = true, onFlush } = {}) {
  const active = hasUnsyncedWork({ pendingCount, actionCount });
  useEffect(() => {
    if (!active) return undefined; // tak ada yang perlu disinkron → reload biasa
    const kickFlush = () => { try { onFlush?.(); } catch { /* best-effort */ } };

    // Saat halaman disembunyikan/ditutup (paling andal di HP): pancing sinkron
    // sekali lagi agar data terkirim ke server sebelum halaman pergi.
    const onHide = () => { if (isOnline) kickFlush(); };

    const onBeforeUnload = (e) => {
      if (isOnline) {
        // Online → otomatis sinkron, TANPA menahan reload dgn dialog.
        kickFlush();
        return undefined;
      }
      // Offline → tahan: keduanya (preventDefault + returnValue non-kosong)
      // wajib di-set agar dialog konfirmasi muncul (Chrome/Firefox/Safari).
      e.preventDefault();
      e.returnValue = "Masih ada data yang belum tersinkron (Anda sedang offline). Yakin keluar?";
      return e.returnValue;
    };

    window.addEventListener("pagehide", onHide);
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => {
      window.removeEventListener("pagehide", onHide);
      window.removeEventListener("beforeunload", onBeforeUnload);
    };
  }, [active, isOnline, onFlush]);
}
