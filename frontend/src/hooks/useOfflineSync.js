import { useState, useEffect, useCallback, useRef } from "react";
import { openDB } from "idb";
import { toast } from "sonner";
import axios from "axios";
import { checkReachable, REACHABILITY_RETRY_MS } from "../lib/connectivity";

const DB_NAME = "inventory_offline";
const DB_VERSION = 1;
const STORE_NAME = "pending_changes";
const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

async function getDB() {
  return openDB(DB_NAME, DB_VERSION, {
    upgrade(db) {
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: "id", autoIncrement: true });
      }
    },
  });
}

export function useOfflineSync({ onSyncComplete }) {
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [pendingCount, setPendingCount] = useState(0);
  const [syncing, setSyncing] = useState(false);
  const syncingRef = useRef(false);

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

  // Count pending changes
  const refreshPendingCount = useCallback(async () => {
    try {
      const db = await getDB();
      const count = await db.count(STORE_NAME);
      setPendingCount(count);
    } catch { setPendingCount(0); }
  }, []);

  useEffect(() => { refreshPendingCount(); }, [refreshPendingCount]);

  // Queue an operation for later sync
  const queueOperation = useCallback(async (operation) => {
    try {
      const db = await getDB();
      await db.add(STORE_NAME, {
        ...operation,
        queued_at: new Date().toISOString(),
      });
      await refreshPendingCount();
      return true;
    } catch (err) {
      console.error("Failed to queue operation:", err);
      return false;
    }
  }, [refreshPendingCount]);

  // Process a single pending operation
  const processOperation = async (op) => {
    switch (op.type) {
      case "create":
        await axios.post(`${API}/assets`, op.data, { headers: op.headers || {} });
        break;
      case "update":
        await axios.put(`${API}/assets/${op.asset_id}`, op.data, { headers: op.headers || {} });
        break;
      case "delete":
        await axios.delete(`${API}/assets/${op.asset_id}`, { headers: op.headers || {} });
        break;
      default:
        break;
    }
  };

  // Sync all pending changes
  const syncPending = useCallback(async () => {
    if (syncingRef.current || !navigator.onLine) return;
    syncingRef.current = true;
    setSyncing(true);

    try {
      const db = await getDB();
      const allOps = await db.getAll(STORE_NAME);
      
      if (allOps.length === 0) {
        setSyncing(false);
        syncingRef.current = false;
        return;
      }

      let success = 0;
      let failed = 0;

      for (const op of allOps) {
        try {
          await processOperation(op);
          await db.delete(STORE_NAME, op.id);
          success++;
        } catch (err) {
          failed++;
          console.error("Sync failed for op:", op, err);
          // If conflict (409) or not found (404), remove from queue
          if (err.response?.status === 409 || err.response?.status === 404) {
            await db.delete(STORE_NAME, op.id);
          }
        }
      }

      await refreshPendingCount();
      
      if (success > 0) {
        toast.success(`${success} perubahan berhasil disinkronkan`);
        onSyncComplete?.();
      }
      if (failed > 0) {
        toast.error(`${failed} perubahan gagal disinkronkan`);
      }
    } catch (err) {
      console.error("Sync error:", err);
    } finally {
      setSyncing(false);
      syncingRef.current = false;
    }
  }, [refreshPendingCount, onSyncComplete]);

  // Auto-sync when coming back online
  useEffect(() => {
    if (isOnline && pendingCount > 0) {
      syncPending();
    }
  }, [isOnline]); // eslint-disable-line react-hooks/exhaustive-deps

  return {
    isOnline,
    pendingCount,
    syncing,
    queueOperation,
    syncPending,
  };
}
