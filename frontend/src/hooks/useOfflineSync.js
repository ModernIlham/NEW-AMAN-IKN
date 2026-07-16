import { useState, useEffect } from "react";
import { toast } from "sonner";
import { checkReachable, REACHABILITY_RETRY_MS } from "../lib/connectivity";

/**
 * Status online/offline aplikasi (dengan verifikasi backend benar-benar
 * terjangkau — bukan sekadar event 'online' browser).
 *
 * CATATAN: jalur antrean-sync lama di hook ini (queueOperation/syncPending
 * via IndexedDB) sudah DIHAPUS — tidak pernah dipanggil siapa pun dan
 * kebijakan konfliknya berbeda dari antrean simpan yang nyata,
 * useOptimisticQueue (If-Match + Idempotency-Key + retry). Satu-satunya
 * antrean tulis offline adalah useOptimisticQueue.
 */
export function useOfflineSync() {
  const [isOnline, setIsOnline] = useState(navigator.onLine);

  // Bersihkan sisa antrean IDB dari jalur sync lama (best-effort) agar op
  // usang tak pernah tereksekusi lagi oleh kode mana pun.
  useEffect(() => {
    try { indexedDB.deleteDatabase("inventory_offline"); } catch { /* abaikan */ }
  }, []);

  // Monitor online/offline status
  useEffect(() => {
    // Note: pending saves live in useOptimisticQueue (which auto-flushes on
    // 'online'), so this toast only reports connectivity — no sync claim here.
    // The 'online' event only means a network interface came up — verify the
    // backend actually answers before declaring online (captive portal, dead
    // Wi-Fi, server down). Unreachable → stay offline and retry after 10s.
    let cancelled = false;
    let retryTimer = null;

    const verifyOnline = async () => {
      const reachable = await checkReachable();
      if (cancelled) return;
      if (reachable) {
        setIsOnline(true);
        toast.success("Koneksi internet kembali pulih.");
      } else {
        retryTimer = setTimeout(verifyOnline, REACHABILITY_RETRY_MS);
      }
    };

    const handleOnline = () => {
      if (retryTimer) { clearTimeout(retryTimer); retryTimer = null; }
      verifyOnline();
    };
    const handleOffline = () => {
      if (retryTimer) { clearTimeout(retryTimer); retryTimer = null; }
      setIsOnline(false);
      toast.warning("Koneksi terputus. Mode offline aktif.");
    };
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      cancelled = true;
      if (retryTimer) clearTimeout(retryTimer);
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  return { isOnline };
}
