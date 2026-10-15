/**
 * useRowLocking - Manages asset row locking for concurrent editing.
 * Supports MULTIPLE concurrent locks so save-and-navigate flows work smoothly.
 * Each lock has its own heartbeat. Unlocking one lock doesn't affect others.
 */
import { useState, useEffect, useRef, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { usePenjagaPermintaan } from "./usePenjagaPermintaan";
import { getSatkerAktif } from "@/lib/satkerAktif";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export function useRowLocking({ activityId, user, wsSend }) {
  const [rowLocks, setRowLocks] = useState({});
  const scope = JSON.stringify([activityId, user?.id, String(user?.kode_satker || "").trim() || getSatkerAktif()]);
  const penjaga = usePenjagaPermintaan(scope);
  // Map of assetId → heartbeat interval ID
  const activeLocksRef = useRef(new Map());

  // Session ID - unique per browser tab
  const [sessionId] = useState(() => {
    let sid = sessionStorage.getItem('inv_session_id');
    if (!sid) {
      sid = globalThis.crypto?.randomUUID ? globalThis.crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
      sessionStorage.setItem('inv_session_id', sid);
    }
    return sid;
  });

  const refreshLocks = useCallback(async () => {
    if (!activityId) return;
    const tiket = penjaga.mulaiBaca("locks", scope);
    if (!tiket) return;
    try {
      const res = await axios.get(`${API}/assets/locks`, { signal: tiket.signal, params: { activity_id: activityId } });
      if (!penjaga.berlaku(tiket)) return;
      const next = res.data.locks || {};
      setRowLocks(prev => JSON.stringify(prev) === JSON.stringify(next) ? prev : next);
    } catch (error) {
      if (penjaga.berlaku(tiket) && process.env.NODE_ENV !== "production") {
        console.warn("[useRowLocking] Failed to fetch active locks:", error?.message);
      }
    } finally { penjaga.selesai(tiket); }
  }, [activityId, penjaga, scope]);
  useEffect(() => {
    setRowLocks({});
    refreshLocks();
    const interval = setInterval(refreshLocks, 30000);
    return () => clearInterval(interval);
  }, [refreshLocks]);

  const lockAsset = useCallback(async (assetId) => {
    try {
      const res = await axios.post(`${API}/assets/lock`, { asset_id: assetId }, {
        headers: { "x-user-id": user?.id, "x-user-name": user?.name || user?.username, "x-session-id": sessionId }
      });
      if (res.data.locked) {
        // Clear any existing heartbeat for this specific asset (re-lock scenario)
        const existingHb = activeLocksRef.current.get(assetId);
        if (existingHb) clearInterval(existingHb);

        // Start a dedicated heartbeat for THIS lock
        const hb = setInterval(() => {
          axios.post(`${API}/assets/heartbeat`, { asset_id: assetId }, {
            headers: { "x-user-id": user?.id, "x-user-name": user?.name || user?.username, "x-session-id": sessionId }
          }).catch((e) => {
            if (process.env.NODE_ENV !== "production") {
              console.warn("[useRowLocking] Heartbeat failed for", assetId, e?.message);
            }
          });
        }, 15000);
        activeLocksRef.current.set(assetId, hb);

        wsSend({ type: "lock", asset_id: assetId });
        return true;
      } else {
        toast.error(`Aset sedang diedit oleh ${res.data.locked_by}`);
        return false;
      }
    } catch (e) {
      // On network/server error we optimistically allow edit; WS will reconcile later.
      if (process.env.NODE_ENV !== "production") {
        console.warn("[useRowLocking] Lock request failed — allowing optimistic edit:", e?.message);
      }
      return true;
    }
  }, [user, wsSend, sessionId]);

  const unlockAsset = useCallback(async (assetId) => {
    // Clear ONLY this asset's heartbeat
    const hb = activeLocksRef.current.get(assetId);
    if (hb) {
      clearInterval(hb);
      activeLocksRef.current.delete(assetId);
    }

    try {
      await axios.post(`${API}/assets/unlock`, { asset_id: assetId }, {
        headers: { "x-user-id": user?.id, "x-session-id": sessionId }
      });
      // Broadcast only AFTER the server confirmed the unlock — otherwise peers
      // see the row as free while the lock is still held server-side.
      wsSend({ type: "unlock", asset_id: assetId });
    } catch (e) {
      // Unlock best-effort — server TTL will auto-expire the lock anyway.
      if (process.env.NODE_ENV !== "production") {
        console.warn("[useRowLocking] Unlock request failed (TTL will clean up):", e?.message);
      }
    }
  }, [user, wsSend, sessionId]);

  // Cleanup ALL locks on unmount
  useEffect(() => {
    return () => {
      for (const [assetId, hb] of activeLocksRef.current.entries()) {
        clearInterval(hb);
        axios.post(`${API}/assets/unlock`, { asset_id: assetId }, {
          headers: { "x-user-id": user?.id, "x-session-id": sessionId }
        }).catch((e) => {
          if (process.env.NODE_ENV !== "production") {
            console.warn("[useRowLocking] Cleanup unlock failed on unmount:", e?.message);
          }
        });
      }
      activeLocksRef.current.clear();
    };
  }, [user, sessionId]);

  return { rowLocks, setRowLocks, sessionId, lockAsset, unlockAsset, refreshLocks };
}
