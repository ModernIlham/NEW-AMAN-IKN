import { useState, useEffect } from "react";
import { toast } from "sonner";
import { checkReachable, REACHABILITY_RETRY_MS } from "../lib/connectivity";

// Respons probe lama tidak boleh mengubah status setelah jaringan putus lagi.
export function useOfflineSync() {
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  useEffect(() => {
    let generation = 0;
    let retryTimer;
    let lastReachable = navigator.onLine;
    const verify = async session => {
      const reachable = await checkReachable();
      if (session !== generation) return;
      const online = reachable && navigator.onLine;
      setIsOnline(online);
      if (online && !lastReachable) toast.success("Koneksi internet kembali pulih.");
      lastReachable = online;
      if (navigator.onLine) retryTimer = setTimeout(() => verify(session), REACHABILITY_RETRY_MS);
    };
    const handleOnline = () => { clearTimeout(retryTimer); verify(++generation); };
    const handleOffline = () => {
      ++generation;
      clearTimeout(retryTimer);
      lastReachable = false;
      setIsOnline(false);
      toast.warning("Koneksi terputus. Mode offline aktif.");
    };
    handleOnline();
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      ++generation;
      clearTimeout(retryTimer);
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);
  return { isOnline };
}
