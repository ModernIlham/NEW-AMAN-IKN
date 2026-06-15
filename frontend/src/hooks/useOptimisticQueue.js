import { useState, useRef, useCallback, useEffect } from "react";
import axios from "axios";
import { getApiError } from "../lib/utils";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const axiosLargeUpload = axios.create({ timeout: 120000, maxContentLength: 50 * 1024 * 1024, maxBodyLength: 50 * 1024 * 1024 });

/**
 * Pull the current user from localStorage so we can stamp every mutation
 * request with `X-Audit-User` + `X-Audit-User-Id`. This axios instance is
 * separate from `axios.defaults`, so it does NOT inherit the global
 * request interceptor that DashboardPage registers — without these headers
 * the backend recorded "unknown" in audit logs and WebSocket notifications,
 * which is what the user reported seeing even while logged in.
 */
function getAuditHeaders() {
  try {
    const raw = localStorage.getItem("user");
    if (!raw) return {};
    const u = JSON.parse(raw);
    const name = u?.name || u?.username || "";
    const id = u?.id || "";
    const headers = {};
    if (name) headers["X-Audit-User"] = name;
    if (id) headers["X-Audit-User-Id"] = id;
    return headers;
  } catch {
    return {};
  }
}

const MAX_CONCURRENT = 3;

// Generate a short idempotency key for each save attempt
function genIdempotencyKey() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export function useOptimisticQueue({ onItemSaved, onItemFailed, onRowSynced, onConflict }) {
  const [syncStatuses, setSyncStatuses] = useState({});
  const [queueLength, setQueueLength] = useState(0);
  const queueRef = useRef([]);
  const activeCountRef = useRef(0);
  const failedItemsRef = useRef({});
  const failTimersRef = useRef({});
  // Track whether a full refresh is needed (accumulated after saves complete)
  const needsRefreshRef = useRef(false);

  const updateStatus = useCallback((id, status, error) => {
    setSyncStatuses(prev => ({ ...prev, [id]: { status, error: error || null, ts: Date.now() } }));
  }, []);

  const clearStatus = useCallback((id) => {
    setSyncStatuses(prev => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
  }, []);

  useEffect(() => {
    return () => {
      Object.values(failTimersRef.current).forEach(t => clearTimeout(t));
    };
  }, []);

  const processNext = useCallback(async () => {
    if (activeCountRef.current >= MAX_CONCURRENT) return;
    if (queueRef.current.length === 0) return;

    const item = queueRef.current.shift();
    setQueueLength(queueRef.current.length);

    const statusKey = item.isEdit ? item.editId : item.tempId;
    activeCountRef.current++;
    updateStatus(statusKey, "saving");

    // Build per-request headers for OCC + idempotency + audit stamping
    const headers = {
      "Idempotency-Key": item.idempotencyKey,
      ...getAuditHeaders(),
    };
    if (item.isEdit && item.baseVersion != null) {
      headers["If-Match"] = String(item.baseVersion);
    }

    try {
      let result;
      if (item.isEdit && item.editId) {
        if (item.usePatch) {
          result = await axiosLargeUpload.patch(`${API}/assets/${item.editId}`, item.payload, { headers });
        } else {
          result = await axiosLargeUpload.put(`${API}/assets/${item.editId}`, item.payload, { headers });
        }
      } else {
        result = await axiosLargeUpload.post(`${API}/assets`, item.payload, { headers });
      }

      updateStatus(statusKey, "saved");
      setTimeout(() => clearStatus(statusKey), 3000);

      // Unlock the saved row
      if (item.isEdit && item.editId) {
        onItemSaved?.(item.editId);
      }

      // Notify parent with server data for targeted row update (no full refresh!)
      const serverData = result?.data;
      if (serverData) {
        onRowSynced?.(statusKey, serverData, item.isEdit);
      }

      // Mark that a refresh is needed when editing session ends
      needsRefreshRef.current = true;

      if (failTimersRef.current[statusKey]) {
        clearTimeout(failTimersRef.current[statusKey]);
        delete failTimersRef.current[statusKey];
      }
      delete failedItemsRef.current[statusKey];

      item.resolve?.(result);
    } catch (err) {
      // --- Handle 409 Conflict (OCC) separately ---
      const isConflict = err?.response?.status === 409;
      if (isConflict && item.isEdit && item.editId) {
        const conflictDetail = err.response?.data?.detail || {};
        updateStatus(statusKey, "conflict", conflictDetail.message || "Data telah diubah oleh pengguna lain.");
        // Notify parent — they can refresh the row and optionally re-enqueue
        onConflict?.(item.editId, conflictDetail);
        // Unlock since save failed — let user re-acquire lock after refresh
        onItemFailed?.(item.editId);
        // Keep failed item for potential manual retry after user review
        failedItemsRef.current[statusKey] = item;
        if (failTimersRef.current[statusKey]) clearTimeout(failTimersRef.current[statusKey]);
        failTimersRef.current[statusKey] = setTimeout(() => {
          delete failTimersRef.current[statusKey];
        }, 120000);
        item.reject?.(err);
        return;
      }

      const errorMsg = getApiError(err, err.code === "ECONNABORTED" ? "Koneksi timeout" : "Gagal menyimpan");
      updateStatus(statusKey, "failed", errorMsg);

      if (item.isEdit && item.editId) {
        if (failTimersRef.current[statusKey]) clearTimeout(failTimersRef.current[statusKey]);
        failTimersRef.current[statusKey] = setTimeout(() => {
          onItemFailed?.(item.editId);
          delete failTimersRef.current[statusKey];
        }, 60000);
      }

      item.reject?.(err);
    } finally {
      activeCountRef.current--;
      processNext();
    }
  }, [updateStatus, clearStatus, onItemSaved, onItemFailed, onRowSynced, onConflict]);

  const enqueue = useCallback(({ tempId, payload, isEdit, editId, usePatch, baseVersion }) => {
    const statusKey = isEdit ? editId : tempId;
    // Generate one idempotency key per logical save — reused on retry so server dedupes
    const idempotencyKey = genIdempotencyKey();
    const item = { tempId, payload, isEdit, editId, usePatch, baseVersion, idempotencyKey };

    failedItemsRef.current[statusKey] = item;
    updateStatus(statusKey, "queued");

    return new Promise((resolve, reject) => {
      queueRef.current.push({ ...item, resolve, reject });
      setQueueLength(queueRef.current.length);
      processNext();
    });
  }, [processNext, updateStatus]);

  const retry = useCallback((id) => {
    const item = failedItemsRef.current[id];
    if (!item) return;
    if (failTimersRef.current[id]) {
      clearTimeout(failTimersRef.current[id]);
      delete failTimersRef.current[id];
    }
    delete failedItemsRef.current[id];
    // Reuse the same idempotency key for retry — server dedupes duplicate writes
    enqueue(item);
  }, [enqueue]);

  const dismiss = useCallback((id) => {
    if (failTimersRef.current[id]) {
      clearTimeout(failTimersRef.current[id]);
      delete failTimersRef.current[id];
    }
    const item = failedItemsRef.current[id];
    delete failedItemsRef.current[id];
    clearStatus(id);
    if (item?.isEdit && item?.editId) {
      onItemSaved?.(item.editId);
    }
    needsRefreshRef.current = true;
  }, [clearStatus, onItemSaved]);

  // Called by parent when editing session ends (form closed)
  // Returns true if a deferred refresh should happen
  const consumeRefreshFlag = useCallback(() => {
    const needed = needsRefreshRef.current;
    needsRefreshRef.current = false;
    return needed;
  }, []);

  // Check if queue is completely idle (nothing queued or active)
  const isIdle = activeCountRef.current === 0 && queueRef.current.length === 0;

  return {
    syncStatuses,
    enqueue,
    retry,
    dismiss,
    queueLength,
    consumeRefreshFlag,
    isIdle,
  };
}
