import { useState, useRef, useCallback, useEffect, useMemo } from "react";
import axios from "axios";
import { openDB } from "idb";
import { toast } from "sonner";
import { getApiError } from "../lib/utils";
import { checkReachable, REACHABILITY_RETRY_MS } from "../lib/connectivity";
import { summarizeSyncStatuses } from "../lib/syncStatus";
import { resolveBaseVersion } from "../lib/occ";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const axiosLargeUpload = axios.create({ timeout: 120000, maxContentLength: 50 * 1024 * 1024, maxBodyLength: 50 * 1024 * 1024 });

// This instance is created outside React, so it does NOT run the global
// request interceptor registered in App.js — it must attach the JWT bearer
// token itself, or every queued save hits the backend without an
// Authorization header and 401s ("Invalid authorization header"). Read the
// token at request time (not module-load) so it stays fresh after re-login.
axiosLargeUpload.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token && !config.headers?.Authorization) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

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

// --- Persistent save queue (IndexedDB) ---
// Every queued/failed save is written through to IndexedDB so a crash, page
// reload, or 401-logout → re-login doesn't lose the user's work. Items are
// removed only when the server confirms the save or the user dismisses them.
const QUEUE_DB_NAME = "aman_save_queue";
const QUEUE_STORE = "items";

function getQueueDB() {
  return openDB(QUEUE_DB_NAME, 1, {
    upgrade(db) {
      if (!db.objectStoreNames.contains(QUEUE_STORE)) {
        db.createObjectStore(QUEUE_STORE, { keyPath: "statusKey" });
      }
    },
  });
}

// Strip non-serializable fields (resolve/reject) before storing/persisting
function toPlainItem(item, statusKey) {
  const { tempId, payload, isEdit, editId, usePatch, baseVersion, idempotencyKey, hadConflict, locked, queuedAt } = item;
  return {
    statusKey,
    tempId,
    payload,
    isEdit: !!isEdit,
    editId: editId ?? null,
    usePatch: !!usePatch,
    baseVersion: baseVersion ?? null,
    idempotencyKey: idempotencyKey ?? null,
    hadConflict: !!hadConflict,
    // 423 Locked (kegiatan disahkan): retry otomatis tidak akan pernah
    // berhasil — auto-flush melewati item ini; hanya retry/dismiss manual.
    locked: !!locked,
    queuedAt: queuedAt || new Date().toISOString(),
  };
}

async function persistQueueItem(item, statusKey) {
  try {
    const db = await getQueueDB();
    await db.put(QUEUE_STORE, toPlainItem(item, statusKey));
  } catch (e) {
    // Best-effort: the in-memory queue keeps working without persistence.
    if (process.env.NODE_ENV !== "production") {
      console.warn("[useOptimisticQueue] Failed to persist queue item:", e?.message);
    }
  }
}

async function removePersistedItem(statusKey) {
  try {
    const db = await getQueueDB();
    await db.delete(QUEUE_STORE, statusKey);
  } catch {
    // ignore — TTL-less store, an orphan is re-deduped by idempotency key
  }
}

async function loadPersistedItems() {
  try {
    const db = await getQueueDB();
    return await db.getAll(QUEUE_STORE);
  } catch {
    return [];
  }
}

// Generate a short idempotency key for each save attempt
function genIdempotencyKey() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export function useOptimisticQueue({ onItemSaved, onItemFailed, onRowSynced, onConflict, onItemDismissed, onRehydrate, getLatestVersion }) {
  const [syncStatuses, setSyncStatuses] = useState({});
  const [queueLength, setQueueLength] = useState(0);
  const queueRef = useRef([]);
  const activeCountRef = useRef(0);
  const failedItemsRef = useRef({});
  const failTimersRef = useRef({});
  // Track whether a full refresh is needed (accumulated after saves complete)
  const needsRefreshRef = useRef(false);
  // Synchronous mirror of syncStatuses so queue callbacks can read fresh state
  const statusesRef = useRef({});
  // editIds with a request in flight — same-asset saves are serialized behind them
  const inFlightEditsRef = useRef(new Set());
  // Last confirmed server version per editId (from a completed save's response)
  const lastSavedVersionsRef = useRef({});
  const flushGuardRef = useRef(false);
  const rehydratedRef = useRef(false);

  // Parent callbacks that may be recreated each render — read via refs
  const getLatestVersionRef = useRef(getLatestVersion);
  const onRehydrateRef = useRef(onRehydrate);
  useEffect(() => {
    getLatestVersionRef.current = getLatestVersion;
    onRehydrateRef.current = onRehydrate;
  });

  const updateStatus = useCallback((id, status, error, extra) => {
    // `extra` menempelkan penanda tambahan (mis. { locked: true } untuk 423)
    // agar summarizeSyncStatuses bisa membedakan gagal-jaringan (bisa di-flush)
    // dari gagal-terkunci (perlu tindakan manual). Selalu ditulis ulang penuh,
    // jadi penanda hanya ada saat status ini memang membawanya.
    statusesRef.current = { ...statusesRef.current, [id]: { status, error: error || null, ts: Date.now(), ...(extra || {}) } };
    setSyncStatuses(statusesRef.current);
  }, []);

  const clearStatus = useCallback((id) => {
    const next = { ...statusesRef.current };
    delete next[id];
    statusesRef.current = next;
    setSyncStatuses(next);
  }, []);

  useEffect(() => {
    return () => {
      Object.values(failTimersRef.current).forEach(t => clearTimeout(t));
    };
  }, []);

  const processNext = useCallback(async () => {
    if (activeCountRef.current >= MAX_CONCURRENT) return;
    if (queueRef.current.length === 0) return;

    // Serialize same-asset saves: skip items whose editId is already in flight
    // (a rapid double-save of one row would otherwise 409 against itself).
    let idx = -1;
    for (let i = 0; i < queueRef.current.length; i++) {
      const it = queueRef.current[i];
      if (it.isEdit && it.editId && inFlightEditsRef.current.has(it.editId)) {
        it.awaitingPrior = true; // dispatched later with the prior save's returned version
        continue;
      }
      idx = i;
      break;
    }
    if (idx === -1) return; // everything left is waiting behind an in-flight same-asset save

    const item = queueRef.current.splice(idx, 1)[0];
    setQueueLength(queueRef.current.length);

    const statusKey = item.isEdit ? item.editId : item.tempId;
    activeCountRef.current++;
    if (item.isEdit && item.editId) inFlightEditsRef.current.add(item.editId);
    updateStatus(statusKey, "saving");

    // Kirim If-Match dengan versi TERTINGGI yang kita ketahui agar tak self-409:
    // edit berantai atas aset yang sama (atau yang menunggu di belakang simpanan
    // lain) sudah menaikkan versi server; `baseVersion` item bisa jadi versi saat
    // form dimuat. resolveBaseVersion mengambil max(base, lastSaved) — tak pernah
    // menurunkan versi, jadi bentrok orang lain yang benar-benar baru tetap 409.
    if (item.isEdit && item.editId) {
      const resolved = resolveBaseVersion(item.baseVersion, lastSavedVersionsRef.current[item.editId]);
      if (resolved != null) item.baseVersion = resolved;
    }

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
      // Clear only if still 'saved' — a follow-up save of the same row may have
      // set a newer status (queued/saving/failed) that this timer must not wipe
      setTimeout(() => {
        if (statusesRef.current[statusKey]?.status === "saved") clearStatus(statusKey);
      }, 3000);

      // Unlock the saved row
      if (item.isEdit && item.editId) {
        onItemSaved?.(item.editId);
      }

      // Notify parent with server data for targeted row update (no full refresh!)
      const serverData = result?.data;
      if (serverData) {
        if (item.isEdit && item.editId && serverData.version != null) {
          lastSavedVersionsRef.current[item.editId] = serverData.version;
        }
        onRowSynced?.(statusKey, serverData, item.isEdit);
      }

      // Mark that a refresh is needed when editing session ends
      needsRefreshRef.current = true;

      if (failTimersRef.current[statusKey]) {
        clearTimeout(failTimersRef.current[statusKey]);
        delete failTimersRef.current[statusKey];
      }
      delete failedItemsRef.current[statusKey];
      removePersistedItem(statusKey); // confirmed by server — drop the persisted copy

      item.resolve?.(result);
    } catch (err) {
      // --- Handle 409 Conflict (OCC) separately ---
      const isConflict = err?.response?.status === 409;
      if (isConflict && item.isEdit && item.editId) {
        const conflictDetail = err.response?.data?.detail || {};
        updateStatus(statusKey, "conflict", conflictDetail.message || "Data telah diubah oleh pengguna lain.");
        // Clear after a moment (mirrors the saved branch) so the row becomes
        // clickable again — the user re-edits on the fresh server version
        // that onConflict merges into the local list.
        setTimeout(() => {
          if (statusesRef.current[statusKey]?.status === "conflict") clearStatus(statusKey);
        }, 4000);
        // Notify parent — they can refresh the row and optionally re-enqueue
        onConflict?.(item.editId, conflictDetail);
        // Unlock since save failed — let user re-acquire lock after refresh
        onItemFailed?.(item.editId);
        // Keep failed item for potential manual retry after user review.
        // `hadConflict` makes retry() refresh the base version + mint a new key.
        const stored = toPlainItem({ ...item, hadConflict: true }, statusKey);
        failedItemsRef.current[statusKey] = stored;
        persistQueueItem(stored, statusKey);
        if (failTimersRef.current[statusKey]) clearTimeout(failTimersRef.current[statusKey]);
        failTimersRef.current[statusKey] = setTimeout(() => {
          delete failTimersRef.current[statusKey];
        }, 120000);
        item.reject?.(err);
        return;
      }

      // --- Auto-renumber NUP untuk aset "dummy" yang bentrok (mis. dibuat
      // offline oleh perangkat lain) --- ambil NUP berikutnya dari server lalu
      // coba ulang otomatis (maks 3x). Hanya untuk CREATE kategori dummy yang
      // NUP-nya memang dinomori otomatis — tidak mengubah NUP yang diketik user.
      const detail = err?.response?.data?.detail;
      const isNupCollision = err?.response?.status === 400 && typeof detail === "string"
        && /NUP/.test(detail) && /sudah digunakan/i.test(detail);
      if (!item.isEdit && isNupCollision && /dummy/i.test(item.payload?.category || "") && (item.nupRetries || 0) < 3) {
        try {
          const params = new URLSearchParams({ activity_id: item.payload.activity_id || "" });
          if (item.payload.asset_code) params.set("asset_code", item.payload.asset_code);
          const r = await axiosLargeUpload.get(`${API}/assets/next-nup?${params}`, { headers: getAuditHeaders() });
          const nextNup = r?.data?.next_nup;
          if (nextNup && String(nextNup) !== String(item.payload.NUP)) {
            const newItem = {
              ...item,
              payload: { ...item.payload, NUP: String(nextNup) },
              idempotencyKey: genIdempotencyKey(),
              nupRetries: (item.nupRetries || 0) + 1,
            };
            // WRITE-THROUGH: samakan salinan persist + failedItemsRef dengan retry
            // yang benar-benar berjalan. Tanpa ini, IndexedDB tetap menyimpan
            // {key lama, NUP lama}; bila crash setelah retry sukses, rehydrate
            // me-replay NUP lama → aset KEMBAR. Sekarang yang di-replay adalah
            // item ber-NUP baru + key barunya (server bisa dedup lewat idempotensi).
            failedItemsRef.current[statusKey] = toPlainItem(newItem, statusKey);
            persistQueueItem(newItem, statusKey);
            updateStatus(statusKey, "queued");
            queueRef.current.push(newItem);
            setQueueLength(queueRef.current.length);
            toast.info(`NUP ${item.payload.NUP} sudah dipakai — dinomori ulang otomatis ke ${nextNup}`, { duration: 3500 });
            item.reject?.(err); // promise asli sudah tak ditunggu; item baru yang diproses
            return; // finally akan memicu processNext untuk item ber-NUP baru
          }
        } catch { /* gagal ambil NUP baru → jatuh ke penanganan gagal biasa */ }
      }

      const errorMsg = getApiError(err, err.code === "ECONNABORTED" ? "Koneksi timeout" : "Gagal menyimpan");
      // 423 Locked: kegiatan sudah disahkan — retry tidak akan pernah berhasil,
      // jadi tampilkan toast yang jelas (save berjalan di background sehingga
      // form sudah tertutup dan tidak bisa menampilkan errornya sendiri).
      const isLocked = err?.response?.status === 423;
      if (isLocked) {
        toast.error(errorMsg || "Kegiatan sudah disahkan dan terkunci", { duration: 6000 });
      }
      // 423 ditandai {locked} → dihitung sebagai "perlu tindakan" (bukan pending
      // sinkron) sehingga tombol Sinkronkan tidak menyala selamanya untuk
      // kegiatan terkunci yang flush-nya memang selalu dilewati (flushPending).
      updateStatus(statusKey, "failed", errorMsg, isLocked ? { locked: true } : undefined);

      // Re-register + persist so retry/rehydrate always have the payload (a
      // prior success of the same statusKey may have removed the entry).
      // `locked` mengikuti kegagalan TERAKHIR: item 423 tidak ikut auto-flush
      // (lihat flushPending) agar antrian offline tidak me-replay + toast
      // berulang setiap reconnect terhadap kegiatan yang sudah terkunci.
      const stored = toPlainItem({ ...item, locked: isLocked }, statusKey);
      failedItemsRef.current[statusKey] = stored;
      persistQueueItem(stored, statusKey);

      if (item.isEdit && item.editId) {
        if (failTimersRef.current[statusKey]) clearTimeout(failTimersRef.current[statusKey]);
        failTimersRef.current[statusKey] = setTimeout(() => {
          onItemFailed?.(item.editId);
          delete failTimersRef.current[statusKey];
        }, 60000);
      }

      item.reject?.(err);
    } finally {
      if (item.isEdit && item.editId) inFlightEditsRef.current.delete(item.editId);
      activeCountRef.current--;
      processNext();
    }
  }, [updateStatus, clearStatus, onItemSaved, onItemFailed, onRowSynced, onConflict]);

  const enqueue = useCallback(({ tempId, payload, isEdit, editId, usePatch, baseVersion, idempotencyKey }) => {
    const statusKey = isEdit ? editId : tempId;
    // One idempotency key per logical save — REUSED on network-failure retry so
    // the server dedupes. Conflict retries pass none, so a fresh key is minted
    // (the stale key sits reserved server-side without a stored response).
    const item = {
      tempId, payload, isEdit, editId, usePatch, baseVersion,
      idempotencyKey: idempotencyKey || genIdempotencyKey(),
      queuedAt: new Date().toISOString(),
    };

    failedItemsRef.current[statusKey] = toPlainItem(item, statusKey);
    persistQueueItem(item, statusKey); // write-through: survives reload/crash
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
    const next = { ...item };
    if (next.hadConflict || statusesRef.current[id]?.status === "conflict") {
      // Conflict retry: rebuild on the CURRENT local row version (onConflict
      // already merged the fresh server copy) and mint a NEW idempotency key.
      const latest = getLatestVersionRef.current?.(next.editId);
      if (latest != null) next.baseVersion = latest;
      next.idempotencyKey = null;
      next.hadConflict = false;
    }
    // Network-failure retries reuse the same idempotency key — server dedupes
    enqueue(next).catch(() => { /* failure re-registers the item via processNext */ });
  }, [enqueue]);

  const dismiss = useCallback((id) => {
    if (failTimersRef.current[id]) {
      clearTimeout(failTimersRef.current[id]);
      delete failTimersRef.current[id];
    }
    const item = failedItemsRef.current[id];
    delete failedItemsRef.current[id];
    removePersistedItem(id); // user explicitly discarded the change
    clearStatus(id);
    if (item?.isEdit && item?.editId) {
      onItemSaved?.(item.editId);
    } else if (item) {
      // Failed CREATE rows stay visible until dismissed — parent drops the temp row
      onItemDismissed?.(id, item);
    }
    needsRefreshRef.current = true;
  }, [clearStatus, onItemSaved, onItemDismissed]);

  // Retry everything failed + kick the queue — used on reconnect, after
  // rehydration, and by the header's manual sync button.
  // auto=true → dipanggil otomatis (reconnect / rehydrasi saat buka kegiatan);
  // auto=false → aksi eksplisit user (tombol Sinkronkan di header).
  const flushPending = useCallback((auto = false) => {
    if (flushGuardRef.current) return; // throttle rapid online/offline flaps
    flushGuardRef.current = true;
    setTimeout(() => { flushGuardRef.current = false; }, 3000);
    Object.keys(failedItemsRef.current).forEach((key) => {
      const rec = failedItemsRef.current[key];
      // 423 Locked (kegiatan disahkan): jangan retry — hasilnya pasti 423 lagi.
      // Item tetap tersimpan; user memutuskan retry/dismiss manual per-baris.
      if (rec?.locked) return;
      // OCC 409 (bentrok) saat AUTO (reconnect/rehidrasi): lewati — menimpa
      // perubahan orang lain secara pasif itu keliru. Tapi saat MANUAL (tombol
      // Sinkronkan, auto=false): retry — onConflict sudah memuat versi server
      // terbaru ke daftar, jadi retry membangun ulang di versi itu (last-write-
      // wins dengan data user) dan BERHASIL, bukan 409 lagi. Ini yang membuat
      // "sudah diklik sinkron tapi terus minta sinkron" akhirnya tuntas.
      if (auto && rec?.hadConflict) return;
      const st = statusesRef.current[key]?.status;
      if (st === "failed" || (!auto && rec?.hadConflict)) retry(key);
    });
    processNext(); // anything still queued in memory (in-flight guard: activeCountRef)
  }, [retry, processNext]);

  const flushRef = useRef(flushPending);
  useEffect(() => { flushRef.current = flushPending; });

  // Auto-flush when connectivity returns. The 'online' event only means a
  // network interface came up — verify the backend really answers first, or
  // every queued save would fail again immediately. Retry after 10s while
  // the browser says online but the server is unreachable.
  useEffect(() => {
    let cancelled = false;
    let retryTimer = null;

    const verifyAndFlush = async () => {
      const reachable = await checkReachable();
      if (cancelled) return;
      if (reachable) {
        flushRef.current?.(true); // auto (reconnect) — lewati item bentrok
      } else {
        retryTimer = setTimeout(verifyAndFlush, REACHABILITY_RETRY_MS);
      }
    };

    const handleOnline = () => {
      if (retryTimer) { clearTimeout(retryTimer); retryTimer = null; }
      verifyAndFlush();
    };
    window.addEventListener("online", handleOnline);
    return () => {
      cancelled = true;
      if (retryTimer) clearTimeout(retryTimer);
      window.removeEventListener("online", handleOnline);
    };
  }, []);

  // Rehydrate persisted items once on mount: register them as 'failed' so the
  // rows show the retry UI, hand them to the parent (pending CREATE rows must
  // reappear in the list), then auto-retry if we're online. This also covers
  // the 401-logout → re-login case (remount rehydrates).
  useEffect(() => {
    if (rehydratedRef.current) return;
    rehydratedRef.current = true;
    let cancelled = false;
    (async () => {
      const items = await loadPersistedItems();
      if (cancelled || items.length === 0) return;
      const toRegister = items.filter(rec =>
        rec?.statusKey && rec?.payload && !failedItemsRef.current[rec.statusKey] && !statusesRef.current[rec.statusKey]
      );
      if (toRegister.length === 0) return;
      toRegister.forEach((rec) => {
        failedItemsRef.current[rec.statusKey] = rec;
        if (rec.locked) {
          // 423 terkunci: perlu tindakan manual (retry/dismiss). {locked} agar
          // tidak dihitung sebagai pending sinkron.
          updateStatus(
            rec.statusKey, "failed",
            "Kegiatan sudah disahkan dan terkunci — perubahan tidak dapat disimpan",
            { locked: true }
          );
        } else if (rec.hadConflict) {
          // 409 konflik: kembalikan sebagai status "conflict" (perlu tindakan),
          // BUKAN "failed" generik. Dulu direhidrasi sebagai "failed" → keliru
          // dihitung pending → tanda sinkron MUNCUL LAGI tiap buka halaman
          // padahal flush auto memang melewati item bentrok.
          updateStatus(
            rec.statusKey, "conflict",
            "Versi berbeda dari server — tinjau lalu simpan ulang"
          );
        } else {
          updateStatus(
            rec.statusKey, "failed",
            "Belum tersinkron — perubahan tersimpan di perangkat ini"
          );
        }
      });
      onRehydrateRef.current?.(toRegister);
      if (navigator.onLine) flushRef.current?.(true); // auto (rehidrasi) — lewati item bentrok
    })();
    return () => { cancelled = true; };
  }, [updateStatus]);

  // Called by parent when editing session ends (form closed)
  // Returns true if a deferred refresh should happen
  const consumeRefreshFlag = useCallback(() => {
    const needed = needsRefreshRef.current;
    needsRefreshRef.current = false;
    return needed;
  }, []);

  // Snapshot of unsynced items (queued/saving/failed/conflict) — lets the
  // parent re-inject pending CREATE rows after a server refetch replaces the list.
  const getPendingItems = useCallback(() => Object.values(failedItemsRef.current), []);

  // Honest sync counters derived from real queue state (lihat
  // summarizeSyncStatuses): pendingCount = bisa di-flush; actionCount = macet
  // (konflik/terkunci) yang perlu tindakan manual per-baris.
  const { pendingCount, isSyncing, actionCount } = useMemo(
    () => summarizeSyncStatuses(syncStatuses),
    [syncStatuses]
  );

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
    pendingCount,
    isSyncing,
    actionCount,
    flushPending,
    getPendingItems,
  };
}
