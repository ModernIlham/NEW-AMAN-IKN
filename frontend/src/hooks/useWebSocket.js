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

      // If 3 quick failures, WebSocket is not supported here - stop trying
      if (failCountRef.current >= 3) {
        console.info("WebSocket not available in this environment. Real-time sync disabled.");
        return;
      }

      doCleanup();

      const url = `${WS_BASE}/ws/${activityId}?user_id=${encodeURIComponent(userId)}&user_name=${encodeURIComponent(userName || "Unknown")}`;

      try {
        const ws = new WebSocket(url);
        wsRef.current = ws;

        ws.onopen = () => {
          if (!mountedRef.current) { ws.close(); return; }
          openTimeRef.current = Date.now();
          setConnected(true);

          if (pingTimer.current) clearInterval(pingTimer.current);
          pingTimer.current = setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify({ type: "ping" }));
            }
          }, 25000);
        };

        ws.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data);
            const { onAssetChange: oac, onLocksUpdate: olu, userId: uid } = cbRefs.current;

            switch (msg.type) {
              case "online_users":
                setOnlineUsers(msg.users || []);
                break;
              case "asset_created":
                if (msg.user_id && msg.user_id === uid) break;
                toast.info(`${msg.user_name} menambahkan aset: ${msg.asset?.asset_code}`, { duration: 3000 });
                oac?.();
                break;
              case "asset_updated":
                if (msg.user_id && msg.user_id === uid) break;
                toast.info(`${msg.user_name} memperbarui aset: ${msg.asset?.asset_code}`, { duration: 3000 });
                oac?.();
                break;
              case "asset_deleted":
                if (msg.user_id && msg.user_id === uid) break;
                toast.info(`${msg.user_name} menghapus aset: ${msg.asset?.asset_code}`, { duration: 3000 });
                oac?.();
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

        ws.onclose = () => {
          if (!mountedRef.current) return;
          setConnected(false);
          if (pingTimer.current) { clearInterval(pingTimer.current); pingTimer.current = null; }

          const lived = Date.now() - (openTimeRef.current || 0);
          if (lived < STABLE_MS) {
            // Connection died too fast - environment doesn't support WS
            failCountRef.current++;
            if (failCountRef.current >= 3) {
              console.info("WebSocket not supported. Disabling.");
              return;
            }
            // Quick backoff then retry
            const delay = 3000 * Math.pow(2, failCountRef.current);
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
      }
    }

    tryConnect();

    return () => {
      mountedRef.current = false;
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
