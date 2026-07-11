import { useEffect, useRef, useState, useCallback } from "react";
import { toast } from "sonner";

const WS_BASE = process.env.REACT_APP_BACKEND_URL?.replace(/^http/, "ws") + "/api";

// Connection must survive this long to be considered "working"
const STABLE_MS = 4000;

export function useWebSocket({ activityId, userId, userName, onAssetChange, onLocksUpdate }) {
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);
  const pingTimer = useRef(null);
  const [onlineUsers, setOnlineUsers] = useState([]);
  const [connected, setConnected] = useState(false);
  const mountedRef = useRef(true);
  const failCountRef = useRef(0);
  const openTimeRef = useRef(0);
  const hasConnectedRef = useRef(false);
  const connectedRef = useRef(false);
  const lastEventRef = useRef(0);

  // Use refs for callbacks to avoid dependency issues
  const cbRefs = useRef({ onAssetChange, onLocksUpdate, userId });
  useEffect(() => {
    cbRefs.current = { onAssetChange, onLocksUpdate, userId };
  });

  const doCleanup = useCallback(() => {
    if (pingTimer.current) { clearInterval(pingTimer.current); pingTimer.current = null; }
    if (reconnectTimer.current) { clearTimeout(reconnectTimer.current); reconnectTimer.current = null; }
    if (wsRef.current) {
      const ws = wsRef.current;
      wsRef.current = null;
      ws.onclose = null;
      ws.onerror = null;
      ws.onmessage = null;
      ws.onopen = null;
      try { ws.close(); } catch {}
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    failCountRef.current = 0;

    if (!activityId || !userId) return;

    function tryConnect() {
      if (!mountedRef.current) return;

      // Only a truly unsupported environment (no WebSocket global) disables
      // real-time sync. Transient failures keep retrying with capped backoff.
      if (typeof WebSocket === "undefined") {
        console.info("WebSocket not available in this environment. Real-time sync disabled.");
        return;
      }

      doCleanup();

      // Identity is derived server-side from the JWT — user_id/user_name query
      // params are no longer sent (the backend would ignore them anyway).
      const token = localStorage.getItem("token") || "";
      const url = `${WS_BASE}/ws/${activityId}?token=${encodeURIComponent(token)}`;

      try {
        const ws = new WebSocket(url);
        wsRef.current = ws;

        ws.onopen = () => {
          if (!mountedRef.current) { ws.close(); return; }
          openTimeRef.current = Date.now();
          lastEventRef.current = Date.now();
          setConnected(true);
          connectedRef.current = true;

          // Catch-up on RE-connect (not first connect): events broadcast while
          // we were down are lost, so refetch once. Routed through the parent's
          // edit-guard + debounce (onWsAssetChange in DashboardPage).
          if (hasConnectedRef.current) {
            cbRefs.current.onAssetChange?.();
          }
          hasConnectedRef.current = true;

          if (pingTimer.current) clearInterval(pingTimer.current);
          pingTimer.current = setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify({ type: "ping" }));
            }
          }, 25000);
        };

        ws.onmessage = (event) => {
          lastEventRef.current = Date.now();
          try {
            const msg = JSON.parse(event.data);
            const { onAssetChange: oac, onLocksUpdate: olu, userId: uid } = cbRefs.current;

            switch (msg.type) {
              case "online_users":
                setOnlineUsers(msg.users || []);
                break;
              case "asset_created":
                // Bandingkan sebagai String: id bisa berbeda tipe (mis. number
                // vs string) sehingga === gagal menyaring event buatan sendiri,
                // memicu refetch yang berlomba → baris kembar saat simpan aset baru.
                if (msg.user_id && String(msg.user_id) === String(uid)) break;
                toast.info(`${msg.user_name} menambahkan aset: ${msg.asset?.asset_code}`, { duration: 3000 });
                oac?.();
                break;
              case "asset_updated":
                if (msg.user_id && String(msg.user_id) === String(uid)) break;
                toast.info(`${msg.user_name} memperbarui aset: ${msg.asset?.asset_code}`, { duration: 3000 });
                // Teruskan tipe + info aset agar pemanggil bisa mem-patch SATU
                // baris (bukan refetch seluruh daftar + statistik per event).
                oac?.("asset_updated", msg.asset);
                break;
              case "asset_deleted":
                if (msg.user_id && String(msg.user_id) === String(uid)) break;
                toast.info(`${msg.user_name} menghapus aset: ${msg.asset?.asset_code}`, { duration: 3000 });
                oac?.("asset_deleted", msg.asset);
                break;
              case "asset_locked":
                olu?.(prev => ({ ...prev, [msg.asset_id]: { user_name: msg.user_name, user_id: msg.user_id } }));
                break;
              case "asset_unlocked":
                olu?.(prev => { const n = { ...prev }; delete n[msg.asset_id]; return n; });
                break;
              case "pong":
                break;
              case "server_ping":
                // Respond to server-initiated heartbeat to keep connection live
                try { ws.send(JSON.stringify({ type: "pong" })); } catch { /* ignore */ }
                break;
              default:
                break;
            }
          } catch (e) {
            if (process.env.NODE_ENV !== "production") {
              console.warn("[ws] Failed to parse server message:", e?.message);
            }
          }
        };

        ws.onclose = (event) => {
          if (!mountedRef.current) return;
          setConnected(false);
          connectedRef.current = false;
          if (pingTimer.current) { clearInterval(pingTimer.current); pingTimer.current = null; }

          // 4401 = server rejected the token (missing/invalid/expired). Do NOT
          // reconnect-loop — a new token is needed first; the axios 401
          // interceptor handles logout on the next API call.
          if (event?.code === 4401) {
            console.info("WebSocket ditolak: token tidak valid/kedaluwarsa. Real-time sync dinonaktifkan sampai login ulang.");
            return;
          }

          const lived = Date.now() - (openTimeRef.current || 0);
          if (lived < STABLE_MS) {
            // Connection died quickly — keep retrying with exponential backoff
            // capped at 60s (never disable permanently; outages recover).
            failCountRef.current++;
            const delay = Math.min(3000 * Math.pow(2, failCountRef.current), 60000);
            reconnectTimer.current = setTimeout(tryConnect, delay);
          } else {
            // Was a stable connection - reset fail count and reconnect normally
            failCountRef.current = 0;
            reconnectTimer.current = setTimeout(tryConnect, 3000);
          }
        };

        ws.onerror = () => { /* onclose handles it */ };
      } catch {
        failCountRef.current++;
        const delay = Math.min(3000 * Math.pow(2, failCountRef.current), 60000);
        reconnectTimer.current = setTimeout(tryConnect, delay);
      }
    }

    tryConnect();

    // Tab becomes visible while disconnected (or stale: no server traffic for
    // >60s) → the user likely missed colleagues' changes; trigger the same
    // deferred refetch path used for WS events.
    const onVisibility = () => {
      if (document.visibilityState !== "visible") return;
      if (!connectedRef.current || Date.now() - lastEventRef.current > 60000) {
        lastEventRef.current = Date.now(); // don't refire on rapid tab flips
        cbRefs.current.onAssetChange?.();
      }
    };
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      mountedRef.current = false;
      document.removeEventListener("visibilitychange", onVisibility);
      doCleanup();
    };
  }, [activityId, userId, userName, doCleanup]);

  const sendMessage = useCallback((msg) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  return { onlineUsers, connected, sendMessage };
}
