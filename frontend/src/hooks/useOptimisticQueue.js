import { useState, useRef, useCallback, useEffect, useMemo } from "react";
import axios from "axios";
import { openDB } from "idb";
import { toast } from "sonner";
import { getApiError } from "../lib/utils";
import { checkReachable, REACHABILITY_RETRY_MS } from "../lib/connectivity";
import { summarizeSyncStatuses } from "../lib/syncStatus";
import { resolveBaseVersion } from "../lib/occ";
import { terapkanHeaderSatker, getSatkerAktif } from "../lib/satkerAktif";
import { gabungPatch } from "../lib/gabungPatch";
import { tertundaUntukEnqueue, tertundaUntukKegagalan } from "../lib/gabungAntrean";
import { idPenggunaAktif, bolehReplay } from "../lib/pemilikAntrean";

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
  const { tempId, payload, isEdit, editId, usePatch, baseVersion, idempotencyKey, hadConflict, locked, queuedAt, nama_kegiatan, satkerAktif, antreanId, pemilik } = item;
  return {
    statusKey,
    // Stempel PEMILIK (temuan audit G3): IndexedDB hidup per-origin, bukan
    // per-akun. Tanpa stempel ini, rehidrasi di perangkat dinas bersama
    // memutar ulang simpanan akun LAIN memakai token & identitas audit akun
    // yang sedang login. Lihat lib/pemilikAntrean.js.
    pemilik: pemilik ?? idPenggunaAktif(),
    // Identitas SATU simpanan (beda dari statusKey, yang dipakai bersama oleh
    // semua simpanan atas aset yang sama). Dipakai memastikan sebuah simpanan
    // hanya menghapus rekamannya SENDIRI — lihat processNext.
    antreanId: antreanId ?? null,
    tempId,
    payload,
    isEdit: !!isEdit,
    editId: editId ?? null,
    usePatch: !!usePatch,
    baseVersion: baseVersion ?? null,
    idempotencyKey: idempotencyKey ?? null,
    nama_kegiatan: nama_kegiatan || "",
    // Satker aktif SAAT di-enqueue — direplay apa adanya agar simpanan tak
    // salah dikirim ke satker lain yang aktif saat sinkron (temuan tinjauan).
    satkerAktif: satkerAktif ?? "",
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

async function removePersistedItem(statusKey, antreanId) {
  try {
    const db = await getQueueDB();
    // Kunci rekaman adalah statusKey, yang dipakai BERSAMA oleh semua simpanan
    // atas aset yang sama. Menghapus tanpa memeriksa pemiliknya berarti sebuah
    // simpanan yang berhasil bisa membuang rekaman simpanan LAIN atas aset itu
    // yang baru saja gagal — muatannya lenyap dari perangkat, dan chip-nya
    // terlanjur berubah "saved" sehingga tak ada yang tahu.
    if (antreanId != null) {
      const ada = await db.get(QUEUE_STORE, statusKey);
      if (ada && ada.antreanId != null && ada.antreanId !== antreanId) return;
    }
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
  // statusKey yang baru saja di-"Abaikan" — penyelesaian in-flight-nya diabaikan
  const dismissedRef = useRef(new Set());
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

    // Replay dengan satker SAAT enqueue (bukan yang aktif kini) — lihat interceptor.
    const _sa = item.satkerAktif ?? "";
    try {
      let result;
      if (item.isEdit && item.editId) {
        if (item.usePatch) {
          result = await axiosLargeUpload.patch(`${API}/assets/${item.editId}`, item.payload, { headers, saOverride: _sa });
        } else {
          result = await axiosLargeUpload.put(`${API}/assets/${item.editId}`, item.payload, { headers, saOverride: _sa });
        }
      } else {
        result = await axiosLargeUpload.post(`${API}/assets`, item.payload, { headers, saOverride: _sa });
      }

      if (dismissedRef.current.has(statusKey)) {
        // Pengguna sudah membuang baris ini saat permintaan terbang — jangan
        // hidupkan lagi status/registrasinya. removePersistedItem tetap aman
        // (ber-antreanId).
        removePersistedItem(statusKey, item.antreanId);
        item.resolve?.(result);
        return;
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
      // Hanya buang rekaman milik SIMPANAN INI. Bila sementara itu sudah ada
      // simpanan lain atas aset yang sama yang mendaftar (mis. yang tadi gagal
      // lalu didaftarkan ulang), rekamannya harus tetap hidup agar bisa
      // di-replay — bukan ikut terhapus oleh keberhasilan kita.
      if (failedItemsRef.current[statusKey]?.antreanId === item.antreanId) {
        delete failedItemsRef.current[statusKey];
      }
      removePersistedItem(statusKey, item.antreanId); // confirmed by server

      item.resolve?.(result);
    } catch (err) {
      if (dismissedRef.current.has(statusKey)) {
        // Baris sudah dibuang pengguna saat permintaan terbang — kegagalan ini
        // tak boleh mendaftarkan ulang item (failedItemsRef/persist) ataupun
        // menghidupkan chip-nya. Janji ditutup dan selesai.
        item.reject?.(err);
        return;
      }
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
          const r = await axiosLargeUpload.get(`${API}/assets/next-nup?${params}`, { headers: getAuditHeaders(), saOverride: item.satkerAktif ?? "" });
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

      const _baseErr = getApiError(err, err.code === "ECONNABORTED" ? "Koneksi timeout" : "Gagal menyimpan");
      // Identitas aset agar mudah dicari di antara puluhan ribu aset & banyak
      // kegiatan (Kode Aset · NUP · Kegiatan). nama_kegiatan di-stamp ke payload
      // saat enqueue (DashboardPage) karena hook tak tahu nama kegiatan.
      const _p = item.payload || {};
      const _ident = [
        _p.asset_code && `Kode ${_p.asset_code}`,
        _p.NUP && `NUP ${_p.NUP}`,
        item.nama_kegiatan && `Keg. ${item.nama_kegiatan}`,
      ].filter(Boolean).join(" · ");
      const errorMsg = _ident ? `[${_ident}] ${_baseErr}` : _baseErr;
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
      // SIMPANAN PERTAMA YANG JUGA GAGAL TAK BOLEH TERTIMPA (temuan audit
      // adversarial). Saat simpanan lama masih TERBANG, enqueue sengaja
      // MELEWATI penggabungan — kalau yang lama ternyata sampai ke server,
      // menggabungnya berarti `photo_ops.add` diterapkan dua kali (foto kembar).
      // Tetapi begitu yang lama akhirnya GAGAL juga, ia terbukti TIDAK pernah
      // diterapkan, dan kini dua rekaman berebut satu kunci `statusKey`:
      // yang belakangan menghapus muatan yang pertama beserta fotonya, senyap.
      // Di titik ini penggabungan justru aman DAN wajib — keduanya dihitung
      // terhadap keadaan server yang sama dan sama-sama belum diterapkan.
      // Aturannya dipisah ke lib/gabungAntrean.js agar bisa diuji (hook ini
      // tak dapat dirender — repo tak memasang @testing-library).
      const sebelumnya = tertundaUntukKegagalan(
        failedItemsRef.current[statusKey], item);
      const itemSimpan = { ...item, locked: isLocked };
      if (sebelumnya) {
        itemSimpan.payload = gabungPatch(sebelumnya.payload, item.payload);
        // Patokan versi ikut yang TERTUNDA lebih dulu — patch gabungan ini
        // dihitung terhadap keadaan server itu, bukan yang lebih baru.
        if (sebelumnya.baseVersion != null) itemSimpan.baseVersion = sebelumnya.baseVersion;
        // Kunci idempotensi lama menempel pada muatan yang kini sudah berubah;
        // dipakai ulang, server bisa memutar balik respons untuk isi yang keliru.
        itemSimpan.idempotencyKey = null;
      }
      const stored = toPlainItem(itemSimpan, statusKey);
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

  const enqueue = useCallback(({ tempId, payload, isEdit, editId, usePatch, baseVersion, idempotencyKey, nama_kegiatan, satkerAktif }) => {
    const statusKey = isEdit ? editId : tempId;

    // PEMBATALAN HANYA BERLAKU UNTUK SIMPANAN YANG SEDANG TERBANG SAAT ITU.
    // `dismissedRef` menahan kunci selama 5 menit agar penyelesaian permintaan
    // yang tak bisa ditarik dari jaringan tak menghidupkan kembali baris yang
    // sudah dibuang. Tetapi simpanan BARU atas aset yang sama adalah kehendak
    // pengguna yang baru — tanpa pembersihan ini, mengedit ulang aset itu dalam
    // 5 menit setelah membatalkan membuat jalur sukses/gagal keluar lebih awal:
    // baris tak pernah diperbarui, chip tak pernah bersih, dan pengguna mengira
    // simpanannya hilang (temuan audit adversarial atas perbaikan G3 sendiri).
    dismissedRef.current.delete(statusKey);

    // SATU ASET BISA PUNYA LEBIH DARI SATU SIMPANAN TERTUNDA — dan dulu yang
    // kedua MENIMPA yang pertama. statusKey untuk EDIT adalah editId, yang
    // memang sengaja berulang, sedangkan failedItemsRef dan IndexedDB
    // (keyPath: "statusKey") sama-sama peta berkunci: menulis dua kali ke kunci
    // yang sama berarti yang pertama lenyap tanpa satu pesan pun.
    //
    // Akibat nyatanya: surveyor luring menambah FOTO (patch berisi photo_ops)
    // → gagal kirim → lalu menggeser pin aset itu di peta (patch ramping berisi
    // koordinat saja). Saat sinyal pulih hanya patch koordinat yang terkirim;
    // fotonya tak pernah sampai, chip tetap berakhir "saved", dan byte fotonya
    // sudah tak ada di perangkat karena snapshot luring memang membuang foto.
    //
    // Menggabung keduanya SAH justru karena yang pertama BELUM diterapkan:
    // kedua patch dihitung terhadap keadaan server yang sama.
    //
    // TAPI HANYA BILA YANG LAMA BELUM TERBANG. Kalau simpanan pertama sedang
    // dikirim, ia akan diterapkan server sebentar lagi; menggabung isinya ke
    // simpanan kedua berarti perubahan yang sama diterapkan DUA KALI — untuk
    // `photo_ops.add` artinya foto kembar. Saat sedang terbang, biarkan
    // keduanya berjalan sendiri-sendiri: processNext memang sudah menderetkan
    // simpanan atas aset yang sama (inFlightEditsRef), jadi urutannya terjaga.
    const sedangTerbang = !!(isEdit && editId && inFlightEditsRef.current.has(editId));
    const calon = { isEdit, usePatch, editId };
    const tertunda = tertundaUntukEnqueue(failedItemsRef.current, statusKey,
                                          calon, sedangTerbang);
    let payloadEfektif = payload;
    let baseVersionEfektif = baseVersion;
    if (tertunda) {
      payloadEfektif = gabungPatch(tertunda.payload, payload);
      // Patokan versi tetap milik simpanan TERTUNDA: patch gabungan ini
      // dihitung terhadap keadaan server yang itu, bukan yang lebih baru.
      if (tertunda.baseVersion != null) baseVersionEfektif = tertunda.baseVersion;
      // Kunci idempotensi lama menempel pada muatan yang kini sudah berubah —
      // dipakai ulang, server bisa memutar balik respons untuk isi yang keliru.
      idempotencyKey = null;
      // Item lama yang MASIH mengantre (belum sempat terbang) kini sudah
      // terwakili sepenuhnya oleh patch gabungan. Kalau dibiarkan, ia terkirim
      // lebih dulu dengan muatan usang lalu menaikkan versi server sehingga
      // patch gabungan justru ditolak 409 oleh perubahan kita sendiri.
      const sisa = [];
      for (const it of queueRef.current) {
        if (it.isEdit && it.editId === editId) {
          it.resolve?.(null); // janji lamanya ditutup, bukan digantung
          continue;
        }
        sisa.push(it);
      }
      queueRef.current = sisa;
      setQueueLength(queueRef.current.length);
    }

    // One idempotency key per logical save — REUSED on network-failure retry so
    // the server dedupes. Conflict retries pass none, so a fresh key is minted
    // (the stale key sits reserved server-side without a stored response).
    const item = {
      tempId, payload: payloadEfektif, isEdit, editId, usePatch,
      baseVersion: baseVersionEfektif,
      idempotencyKey: idempotencyKey || genIdempotencyKey(),
      // Nama kegiatan HANYA untuk pesan gagal (identitas aset) — TIDAK dikirim
      // ke server (yang dikirim hanya item.payload).
      nama_kegiatan: nama_kegiatan || "",
      // Bekukan satker aktif SAAT enqueue (super-admin act-as). Retry membawa
      // nilai tersimpan agar tak ter-recapture ke satker yang aktif kini.
      satkerAktif: satkerAktif !== undefined ? satkerAktif : getSatkerAktif(),
      queuedAt: new Date().toISOString(),
      antreanId: genIdempotencyKey(),
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
    // "Abaikan" harus benar-benar MEMBATALKAN (temuan audit G3). Dulu item
    // yang masih MENGANTRE tetap di queueRef dan terkirim pada flush
    // berikutnya — aset yang pengguna buang tetap tercipta di server.
    const sisa = [];
    for (const it of queueRef.current) {
      const kunci = it.isEdit ? it.editId : it.tempId;
      if (kunci === id) { it.resolve?.(null); continue; }
      sisa.push(it);
    }
    queueRef.current = sisa;
    setQueueLength(queueRef.current.length);
    // Permintaan yang SEDANG TERBANG tak bisa ditarik kembali dari jaringan —
    // tandai supaya penyelesaiannya nanti tak menghidupkan status/baris yang
    // sudah dibuang. (Server mungkin tetap menulis; refresh berikutnya yang
    // menampilkan kebenaran — itu batas jujur pembatalan sisi klien.)
    dismissedRef.current.add(id);
    setTimeout(() => dismissedRef.current.delete(id), 5 * 60 * 1000);
    // Tanpa antreanId: pembuangan oleh PENGGUNA memang disengaja atas baris itu,
    // jadi rekaman siapa pun di kunci itu ikut dibuang.
    removePersistedItem(id); // user explicitly discarded the change
    clearStatus(id);
    if (item?.isEdit && item?.editId) {
      onItemSaved?.(item.editId);
      // Induk juga diberi tahu untuk EDIT (temuan audit G3): nilai optimistis
      // yang dibatalkan masih menempel di baris daftar & snapshot luring —
      // induk memulihkannya dari kebenaran server (lihat DashboardPage).
      onItemDismissed?.(id, item);
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
      // Hanya rekaman MILIK AKUN INI yang di-replay (temuan audit G3):
      // IndexedDB per-origin, dan perangkat dinas dipakai bergantian —
      // tanpa saringan ini simpanan akun lain dikirim memakai token &
      // identitas audit akun yang sedang login. Rekaman era lama tanpa
      // stempel tetap lolos (lihat lib/pemilikAntrean.js).
      const idAktif = idPenggunaAktif();
      const toRegister = items.filter(rec =>
        rec?.statusKey && rec?.payload && bolehReplay(rec, idAktif)
        && !failedItemsRef.current[rec.statusKey] && !statusesRef.current[rec.statusKey]
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
