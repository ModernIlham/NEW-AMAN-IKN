import { useState, useRef, useCallback, useEffect, useMemo } from "react";
import axios from "axios";
import { toast } from "sonner";
import { getApiError } from "../lib/utils";
import { checkReachable, REACHABILITY_RETRY_MS } from "../lib/connectivity";
import { summarizeSyncStatuses } from "../lib/syncStatus";
import { terapkanHeaderSatker, getSatkerAktif } from "../lib/satkerAktif";
import { idPenggunaAktif } from "../lib/pemilikAntrean";
import { keputusanGagalTulisAntrean } from "../lib/idbErrors";
import {
  operationId, appendOperation, readOperations, claimOperation, renewOperation,
  acknowledgeOperation, failOperation, retryOperations, cancelOperations, renumberOperation, hasMediaMutation,
} from "../lib/saveOutbox";

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
  // "Satker Aktif" saat REPLAY (temuan tinjauan): simpanan offline yang dibuat
  // saat super-admin ber-act-as satker A HARUS di-replay sebagai A — bukan
  // satker yang kebetulan aktif saat antrean flush (bisa berubah antara enqueue
  // dan sinkron → 403 "milik satker lain"). `config.saOverride` membawa satker
  // saat di-enqueue (bisa "" = Semua Satker); bila ada, pakai persis itu.
  if (config.saOverride !== undefined) {
    config.headers = config.headers || {};
    if (config.saOverride) config.headers["X-Satker-Aktif"] = config.saOverride;
    else delete config.headers["X-Satker-Aktif"];
  } else {
    config = terapkanHeaderSatker(config);
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
function downloadPending(items) {
  const url = URL.createObjectURL(new Blob([JSON.stringify({ schema: "aman-outbox-backup-v1", items })], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url; link.download = "aman-simpanan-tertunda.json";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function useOptimisticQueue(options) {
  const callbacks = useRef(options);
  callbacks.current = options;
  const [syncStatuses, setSyncStatuses] = useState({});
  const [queueLength, setQueueLength] = useState(0);
  const pendingRef = useRef([]);
  const volatile = useRef(new Map());
  const bodies = useRef(new Map());
  const completions = useRef(new Map());
  const active = useRef(new Map());
  const worker = useRef(operationId());
  const mounted = useRef(false);
  const refreshing = useRef(Promise.resolve());
  const pumping = useRef(false);
  const needsRefresh = useRef(false);
  const pumpRef = useRef(null);
  const owner = idPenggunaAktif();
  const reportedQuota = useRef(false);

  const storageError = useCallback(error => {
    if (!reportedQuota.current && keputusanGagalTulisAntrean(error) === "beri_tahu_pengguna") {
      reportedQuota.current = true;
      callbacks.current.onKuotaPenuh?.();
    }
    toast.error("Penyimpanan lokal gagal. Jangan tutup halaman; periksa ruang penyimpanan lalu coba lagi.",
      { id: "antrean-storage-error", duration: Infinity });
  }, []);

  const refresh = useCallback(() => {
    const task = async () => {
      if (!mounted.current || !owner || owner !== idPenggunaAktif()) return;
      const previous = new Map(pendingRef.current.map(item => [item.antreanId, item]));
      const { states, items } = await readOperations(owner, bodies.current);
      if (!mounted.current || owner !== idPenggunaAktif()) return;
      const saved = [];
      const dismissedKeys = new Set();
      const next = {};
      pendingRef.current = [...items, ...[...volatile.current.values()].filter(item => item.pemilik === owner)];
      for (const item of pendingRef.current) {
        const state = item.state || {};
        const status = { ready: "queued", sending: "saving", failed: "failed", conflict: "conflict", locked: "failed" }[state.status] || "failed";
        const current = next[item.statusKey];
        // The oldest blocking operation determines the row's action.
        if (!current) next[item.statusKey] = { status, error: state.error || null, ts: Date.now(),
          ...(["locked", "rejected"].includes(state.status) ? { locked: true } : {}) };
      }
      for (const state of states) {
        if (state.status === "cancelled" && previous.has(state.antreanId)) {
          const item = previous.get(state.antreanId);
          completions.current.get(state.antreanId)?.resolve(null);
          completions.current.delete(state.antreanId);
          if (!dismissedKeys.has(item.statusKey) && !pendingRef.current.some(it => it.statusKey === item.statusKey)) {
            dismissedKeys.add(item.statusKey);
            callbacks.current.onItemDismissed?.(item.statusKey, item);
            if (item.isEdit) callbacks.current.onItemSaved?.(item.editId);
          }
        }
        if (state.status !== "ack" || !previous.has(state.antreanId)) continue;
        const item = previous.get(state.antreanId);
        saved.push([item, state.result]);
        needsRefresh.current = true;
        if (!next[item.statusKey]) next[item.statusKey] = { status: "saved", ts: Date.now() };
      }
      setSyncStatuses(next);
      setQueueLength(pendingRef.current.filter(item => item.state?.status === "ready").length);
      const newlySeen = items.filter(item => !previous.has(item.antreanId));
      if (newlySeen.length) callbacks.current.onRehydrate?.(newlySeen);
      for (const [item, data] of saved) {
        if (item.isEdit && !pendingRef.current.some(it => it.statusKey === item.statusKey)) callbacks.current.onItemSaved?.(item.editId);
        callbacks.current.onRowSynced?.(item.statusKey, data, item.isEdit);
        completions.current.get(item.antreanId)?.resolve({ data });
        completions.current.delete(item.antreanId);
      }
    };
    refreshing.current = refreshing.current.catch(() => {}).then(task);
    return refreshing.current;
  }, [owner]);

  const processTicket = useCallback(async ticket => {
    const controller = new AbortController();
    let heartbeatBusy = false;
    const heartbeat = setInterval(async () => {
      if (heartbeatBusy) return;
      heartbeatBusy = true;
      try { if (!await renewOperation(ticket)) controller.abort(); }
      catch { controller.abort(); }
      finally { heartbeatBusy = false; }
    }, 15000);
    controller.signal.addEventListener("abort", () => clearInterval(heartbeat), { once: true });
    active.current.set(ticket.antreanId, controller);
    try {
      if (!mounted.current || idPenggunaAktif() !== ticket.pemilik) return;
      const headers = { "Idempotency-Key": ticket.idempotencyKey, ...getAuditHeaders() };
      if (ticket.isEdit && ticket.baseVersion != null) headers["If-Match"] = String(ticket.baseVersion);
      const config = { headers, signal: controller.signal, saOverride: ticket.satkerAktif || "" };
      const result = ticket.isEdit
        ? await axiosLargeUpload[ticket.usePatch ? "patch" : "put"](`${API}/assets/${ticket.editId}`, ticket.payload, config)
        : await axiosLargeUpload.post(`${API}/assets`, ticket.payload, config);
      if (!result?.data?.id) throw new Error("Respons simpan tidak lengkap. Antrean tetap tersimpan untuk dicoba kembali.");
      // Ack and dependent scalar version advance are ONE local transaction.
      if (await acknowledgeOperation(ticket, result?.data)) await refresh();
    } catch (error) {
      const httpStatus = error?.response?.status;
      const detail = error?.response?.data?.detail;
      if (!ticket.isEdit && httpStatus === 400 && typeof detail === "string" && /NUP/.test(detail)
          && /sudah digunakan/i.test(detail) && /dummy/i.test(ticket.payload?.category || "") && (ticket.nupRetries || 0) < 3) {
        try {
          const params = new URLSearchParams({ activity_id: ticket.payload.activity_id || "", asset_code: ticket.payload.asset_code || "" });
          const next = await axiosLargeUpload.get(`${API}/assets/next-nup?${params}`, {
            headers: getAuditHeaders(), saOverride: ticket.satkerAktif || "", signal: controller.signal });
          if (next.data?.next_nup && String(next.data.next_nup) !== String(ticket.payload.NUP)
              && await renumberOperation(ticket, next.data.next_nup)) {
            await refresh();
            return;
          }
        } catch { /* retain original body if renumbering cannot be committed */ }
      }
      // 409 also means an idempotency key is still processing. That is an
      // uncertain outcome: preserve the key/body and retry, never rebase it.
      const status = httpStatus === 409 ? (detail?.current_version != null ? "conflict" : "failed") : httpStatus === 423 ? "locked"
        : httpStatus >= 400 && httpStatus < 500 && ![408, 429].includes(httpStatus) ? "rejected" : "failed";
      const message = error?.response?.status === 401 ? "Sesi berakhir. Masuk kembali, lalu pilih Coba lagi pada aset ini. Simpanan tetap tersimpan."
        : getApiError(error, "Belum tersinkron. Perubahan tetap tersimpan di perangkat.");
      const retryHeader = error?.response?.headers?.["retry-after"];
      const retryAfter = retryHeader == null ? 0 : Number.isFinite(Number(retryHeader))
        ? Date.now() + Number(retryHeader) * 1000 : Date.parse(retryHeader);
      if (await failOperation(ticket, status, message, retryAfter)) {
        if (mounted.current && idPenggunaAktif() === ticket.pemilik) {
          if (status === "conflict") callbacks.current.onConflict?.(ticket.editId, error.response?.data?.detail || {});
          if (ticket.isEdit) callbacks.current.onItemFailed?.(ticket.editId);
        }
        completions.current.get(ticket.antreanId)?.reject(error);
        completions.current.delete(ticket.antreanId);
        await refresh();
      }
    } finally {
      clearInterval(heartbeat);
      active.current.delete(ticket.antreanId);
      if (mounted.current) pumpRef.current?.();
    }
  }, [refresh]);

  const pump = useCallback(async () => {
    if (pumping.current || !mounted.current || !owner || owner !== idPenggunaAktif() || !navigator.onLine) return;
    pumping.current = true;
    try {
      while (mounted.current && active.current.size < MAX_CONCURRENT) {
        const ticket = await claimOperation(owner, worker.current);
        if (!ticket) break;
        // processTicket registers itself synchronously before its first await.
        processTicket(ticket).catch(storageError);
      }
      await refresh();
    } catch (error) { storageError(error); }
    finally { pumping.current = false; }
  }, [owner, processTicket, refresh, storageError]);
  pumpRef.current = pump;

  const enqueue = useCallback(input => {
    const record = { ...input, statusKey: input.isEdit ? input.editId : input.tempId,
      pemilik: owner, satkerAktif: input.satkerAktif ?? getSatkerAktif(),
      antreanId: operationId(), idempotencyKey: input.idempotencyKey || operationId(), queuedAt: new Date().toISOString() };
    let resolve, reject;
    const completion = new Promise((ok, fail) => { resolve = ok; reject = fail; });
    completion.catch(() => {}); // callers may only await the local receipt
    completions.current.set(record.antreanId, { resolve, reject });
    volatile.current.set(record.antreanId, record);
    pendingRef.current = [...pendingRef.current, record];
    completion.persisted = (async () => {
      try {
        if (!owner) throw new Error("Masuk kembali sebelum menyimpan");
        await appendOperation(record, worker.current);
        volatile.current.delete(record.antreanId);
      } catch (error) {
        record.localFailed = true;
        storageError(error);
        reject(error);
        throw error;
      }
      refresh().then(pump).catch(storageError);
    })();
    completion.persisted.catch(() => {});
    // The caller still owns the form/draft when this receipt fails. Release
    // only this uncommitted attempt before resubmitting, never a durable op.
    completion.discardUncommitted = () => {
      if (!record.localFailed) return;
      volatile.current.delete(record.antreanId);
      pendingRef.current = pendingRef.current.filter(item => item.antreanId !== record.antreanId);
      completions.current.delete(record.antreanId);
      if (!pendingRef.current.some(item => item.statusKey === record.statusKey)) {
        setSyncStatuses(previous => { const next = { ...previous }; delete next[record.statusKey]; return next; });
      }
      if (!record.isEdit) callbacks.current.onItemDismissed?.(record.statusKey, record);
    };
    return completion;
  }, [owner, refresh, pump, storageError]);

  const retry = useCallback(statusKey => {
    const blocked = pendingRef.current.find(item => item.statusKey === statusKey && item.state?.status === "conflict"
      && hasMediaMutation(item.payload));
    if (blocked) {
      toast.error("Unduh cadangan terlebih dahulu. Tinjau versi terbaru, abaikan simpanan yang bentrok, lalu tambahkan ulang foto atau dokumen yang diperlukan.",
        { duration: Infinity, action: { label: "Unduh cadangan", onClick: () => downloadPending(
          pendingRef.current.filter(item => item.statusKey === statusKey)) } });
      return;
    }
    retryOperations(owner, { statusKey, version: callbacks.current.getLatestVersion?.(statusKey) })
      .then(refresh).then(pump).catch(storageError);
  }, [owner, refresh, pump, storageError]);
  const dismiss = useCallback(statusKey => {
    const removed = pendingRef.current.filter(item => item.statusKey === statusKey);
    const localOnly = removed.length && removed.every(item => item.localFailed);
    if (!removed.length) return;
    if (!localOnly && !window.confirm("Hapus simpanan tertunda beserta fotonya? Tindakan ini tidak dapat dibatalkan.")) return;
    for (const item of removed) {
      volatile.current.delete(item.antreanId);
      active.current.get(item.antreanId)?.abort();
      completions.current.get(item.antreanId)?.resolve(null);
      completions.current.delete(item.antreanId);
    }
    if (localOnly) {
      pendingRef.current = pendingRef.current.filter(item => item.statusKey !== statusKey);
      const item = removed[0];
      if (item?.isEdit) callbacks.current.onItemSaved?.(item.editId);
      if (item) callbacks.current.onItemDismissed?.(statusKey, item);
      return;
    }
    cancelOperations(owner, statusKey).then(refresh).then(() => {
      needsRefresh.current = true;
      pump();
    }).catch(storageError);
  }, [owner, refresh, pump, storageError]);
  const flushPending = useCallback((auto = false) => {
    // Global flush (also used by unload protection) must never resolve a
    // conflict implicitly. Only the explicit per-row retry may rebase scalars.
    const work = auto ? Promise.resolve() : retryOperations(owner, { auto: true });
    work.then(refresh).then(pump).catch(storageError);
  }, [owner, refresh, pump, storageError]);

  useEffect(() => {
    mounted.current = true;
    const activeRequests = active.current;
    let busy = false, cancelled = false;
    const tick = async () => {
      if (busy || cancelled || !owner || owner !== idPenggunaAktif()) return;
      busy = true;
      try {
        await refresh();
        if (!cancelled && pendingRef.current.length && await checkReachable()) await pump();
      } catch (error) { storageError(error); }
      finally { busy = false; }
    };
    tick();
    const timer = setInterval(tick, REACHABILITY_RETRY_MS);
    const channel = typeof BroadcastChannel !== "undefined" ? new BroadcastChannel("aman-outbox-v2") : null;
    if (channel) channel.onmessage = tick;
    const online = () => { tick(); };
    window.addEventListener("online", online);
    window.addEventListener("focus", online);
    const blocked = () => toast.error("Pembaruan penyimpanan menunggu tab AMAN lama. Simpan draf di tab tersebut lalu tutup tab lama; halaman ini akan melanjutkan otomatis.",
      { id: "antrean-upgrade", duration: Infinity });
    window.addEventListener("aman:outbox-upgrade-blocked", blocked);
    return () => {
      cancelled = true;
      mounted.current = false;
      clearInterval(timer);
      channel?.close();
      window.removeEventListener("online", online);
      window.removeEventListener("focus", online);
      window.removeEventListener("aman:outbox-upgrade-blocked", blocked);
      // Leave the persisted lease to expire. Aborting a request does not prove
      // the server did not commit it; a new tab retries the exact same key.
      for (const controller of activeRequests.values()) controller.abort();
    };
  }, [owner, refresh, pump, storageError]);

  const consumeRefreshFlag = useCallback(() => { const needed = needsRefresh.current; needsRefresh.current = false; return needed; }, []);
  const getPendingItems = useCallback(() => pendingRef.current, []);
  const summary = useMemo(() => summarizeSyncStatuses(syncStatuses), [syncStatuses]);
  return { syncStatuses, queueLength, enqueue, retry, dismiss, flushPending, consumeRefreshFlag,
    getPendingItems, isIdle: !Object.values(syncStatuses).some(s => ["queued", "saving"].includes(s.status)), ...summary };
}
