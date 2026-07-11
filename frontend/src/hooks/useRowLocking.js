/**
 * useRowLocking - Manages asset row locking for concurrent editing.
 * Supports MULTIPLE concurrent locks so save-and-navigate flows work smoothly.
 * Each lock has its own heartbeat. Unlocking one lock doesn't affect others.
 */
import { useState, useEffect, useRef, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export function useRowLocking({ activityId, user, wsSend }) {
  const [rowLocks, setRowLocks] = useState({});
  // Map of assetId → heartbeat interval ID
  const activeLocksRef = useRef(new Map());

  // Session ID - unique per browser tab
  const sessionId = useRef(() => {
    let sid = sessionStorage.getItem('inv_session_id');
    if (!sid) {
      sid = crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
      sessionStorage.setItem('inv_session_id', sid);
    }
    return sid;
  }).current();

  // Fetch all active locks periodically — scoped to current activity for efficiency
  useEffect(() => {
    if (!activityId) return;
    const fetchLocks = async () => {
      try {
        const res = await axios.get(`${API}/assets/locks`, { params: { activity_id: activityId } });
        const next = res.data.locks || {};
        // Identitas stabil: umumnya hasil poll = {} yang sama — objek baru tiap
        // 30 detik memicu render ulang seluruh halaman + semua baris tanpa perlu.
        setRowLocks(prev => (JSON.stringify(prev) === JSON.stringify(next) ? prev : next));
      } catch (e) {
        // Non-fatal: lock state polling — WS will catch up on next real-time event.
        if (process.env.NODE_ENV !== "production") {
          console.warn("[useRowLocking] Failed to fetch active locks:", e?.message);
        }
      }
    };
    fetchLocks();
    // Poll every 30s (WebSocket covers real-time lock events; this is a safety net)
    const interval = setInterval(fetchLocks, 30000);
    return () => clearInterval(interval);
  }, [activityId]);

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

  return { rowLocks, setRowLocks, sessionId, lockAsset, unlockAsset };
}
