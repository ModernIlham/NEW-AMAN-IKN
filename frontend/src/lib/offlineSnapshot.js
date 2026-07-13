/**
 * Offline read-cache (snapshot) for the asset list — inventory mode.
 *
 * The write path already survives offline via useOptimisticQueue (IndexedDB
 * save queue + auto-flush on reconnect). This module adds the READ path: a
 * per-activity snapshot of the *list projection* (NO photos, NO full
 * document_checklist — verified server-side by GET /assets/offline-snapshot
 * which projects with the same LIST_PROJECTION as GET /assets) so the
 * dashboard list still loads with zero connectivity.
 *
 * Security policy:
 * - Snapshot is scoped by userId + activityId (meta store); a login by a
 *   DIFFERENT user must call ensureSnapshotOwner() → clearAllSnapshots().
 * - TTL 7 days: an older snapshot is never served (treated as absent).
 * - Manual logout clears everything (clearAllSnapshots from App.js);
 *   auto-401/idle logout does NOT — field data protection.
 */
import { openDB } from "idb";
import axios from "axios";
import { isQuotaExceeded } from "./idbErrors";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const DB_NAME = "aman_offline_snapshot";
// v2: proyeksi list menambah field berlebih/sengketa — snapshot lama tidak
// memilikinya dan sync delta tak akan mengisi ulang baris yang tak berubah,
// jadi upgrade mengosongkan cache agar sync berikutnya full resync.
const DB_VERSION = 2;
const ASSET_STORE = "assets"; // keyed by asset id, indexed by activity_id
const META_STORE = "meta";    // keyed by activityId → {activityId, userId, lastSync, count}

const PAGE_LIMIT = 1000;
// Refuse to serve a snapshot older than this — stale field data is worse
// than an explicit "reconnect to resync" message.
export const SNAPSHOT_TTL_MS = 7 * 24 * 60 * 60 * 1000; // 7 hari

// Fields we allow into the snapshot store — mirrors the backend
// LIST_PROJECTION. Anything else (full photos, document_checklist, photo
// blobs from optimistic payloads) is stripped before writing.
const SNAPSHOT_FIELDS = [
  "id", "asset_code", "NUP", "asset_name", "category", "brand", "model",
  "kode_register", "serial_number", "purchase_date", "purchase_price",
  "location", "eselon1", "eselon2", "user", "condition", "status",
  "pengguna_melekat_ke", "pengguna_jabatan", "pengguna_nip", "operasional_jenis", "nomor_bast",
  "bast_file_id", "bast_filename",
  "nomor_spm", "perolehan_dari_nama", "nomor_kontrak", "nomor_bukti_perolehan",
  "supplier", "notes", "thumbnail", "thumbnail_index", "gallery_thumbnail",
  "created_at", "updated_at", "activity_id", "version",
  "stiker_status", "stiker_ukuran", "stiker_photo_index",
  "inventory_status", "klasifikasi_tidak_ditemukan", "sub_klasifikasi",
  "uraian_tidak_ditemukan", "tindak_lanjut",
  "koordinat_latitude", "koordinat_longitude", "kronologis",
  "keterangan_berlebih", "asal_usul_berlebih",
  "nomor_perkara", "pihak_bersengketa", "keterangan_sengketa",
  "photo_count", "doc_total", "doc_checked", "doc_summary",
];

function getDB() {
  return openDB(DB_NAME, DB_VERSION, {
    upgrade(db, oldVersion, _newVersion, tx) {
      if (!db.objectStoreNames.contains(ASSET_STORE)) {
        const store = db.createObjectStore(ASSET_STORE, { keyPath: "id" });
        store.createIndex("by-activity", "activity_id", { unique: false });
      }
      if (!db.objectStoreNames.contains(META_STORE)) {
        db.createObjectStore(META_STORE, { keyPath: "activityId" });
      }
      if (oldVersion > 0 && oldVersion < 2) {
        tx.objectStore(ASSET_STORE).clear();
        tx.objectStore(META_STORE).clear();
      }
    },
  });
}

// Ask the browser to protect our IndexedDB from storage-pressure eviction.
// Request at most once per session — repeated calls can re-prompt on some
// browsers.
let persistRequested = false;
async function requestPersistentStorage() {
  if (persistRequested) return;
  persistRequested = true;
  try {
    if (navigator.storage?.persist) await navigator.storage.persist();
  } catch {
    // Best-effort — snapshot still works, just evictable under pressure.
  }
}

// Keep only list-projection fields (never photos / full checklist).
function toSnapshotRow(row) {
  const clean = {};
  for (const f of SNAPSHOT_FIELDS) {
    if (row[f] !== undefined) clean[f] = row[f];
  }
  return clean;
}

function isExpired(meta) {
  if (!meta?.lastSync) return true;
  const age = Date.now() - new Date(meta.lastSync).getTime();
  return !Number.isFinite(age) || age > SNAPSHOT_TTL_MS;
}

/** Raw meta record for an activity ({activityId, userId, lastSync, count}) or null. */
export async function snapshotMeta(activityId) {
  if (!activityId) return null;
  try {
    return (await (await getDB()).get(META_STORE, activityId)) || null;
  } catch {
    return null;
  }
}

/** True when a snapshot exists but is past its 7-day TTL. */
export function isSnapshotExpired(meta) {
  return !!meta && isExpired(meta);
}

/**
 * Sync the snapshot for one activity. Delta when possible (since=lastSync),
 * full otherwise. onProgress({loaded, total, pct}) fires per page.
 * Returns {count, lastSync}.
 */
export async function syncSnapshot(activityId, userId, onProgress, { forceFull = false } = {}) {
  if (!activityId || !userId) throw new Error("activityId dan userId wajib diisi");
  await requestPersistentStorage();

  const db = await getDB();
  const meta = await db.get(META_STORE, activityId);
  // Delta only when the snapshot belongs to this user and is still fresh —
  // otherwise resync from scratch (also the different-user defense in depth;
  // the primary guard is ensureSnapshotOwner on login).
  const canDelta = !forceFull && !!meta && meta.userId === userId && !isExpired(meta);
  const since = canDelta ? meta.lastSync : "";
  const fullSync = !since;

  let lastSyncCursor = null; // server_time of the FIRST page = next delta cursor
  const fetchedIds = fullSync ? new Set() : null;
  let skip = 0;
  let total = 0;
  let loaded = 0;
  // Kuota IndexedDB terlampaui di tengah sync (perangkat nyaris penuh): berhenti
  // menulis dengan anggun, layani cache sebagian yang sudah ada — jangan crash.
  let quotaHit = false;

  for (;;) {
    const params = new URLSearchParams({ activity_id: activityId, skip: String(skip), limit: String(PAGE_LIMIT) });
    if (since) params.append("since", since);
    const r = await axios.get(`${API}/assets/offline-snapshot?${params.toString()}`);
    const { items = [], deleted_ids: deletedIds = [], requires_full_refresh: needsFull } = r.data || {};
    total = r.data?.total ?? total;
    if (lastSyncCursor === null) lastSyncCursor = r.data?.server_time || new Date().toISOString();

    // A bulk delete happened since our cursor — tombstones don't carry ids
    // for it, so restart as a full sync (reconciles all deletes).
    if (needsFull && !fullSync) {
      return syncSnapshot(activityId, userId, onProgress, { forceFull: true });
    }

    // Apply tombstones (first delta page only carries them)
    if (deletedIds.length) {
      const tx = db.transaction(ASSET_STORE, "readwrite");
      for (const id of deletedIds) tx.store.delete(id);
      await tx.done;
    }

    if (items.length) {
      const staged = [];
      for (const item of items) {
        const row = toSnapshotRow(item);
        if (row.id && row.activity_id === activityId) staged.push(row);
      }
      try {
        const tx = db.transaction(ASSET_STORE, "readwrite");
        for (const row of staged) tx.store.put(row);
        await tx.done;
        for (const row of staged) fetchedIds?.add(row.id);
        loaded += items.length;
      } catch (e) {
        // Kuota penuh → hentikan sync dengan anggun (cache sebalumnya tetap
        // dilayani). Error lain (mis. store hilang) dilempar ke pemanggil.
        if (!isQuotaExceeded(e)) throw e;
        quotaHit = true;
        break;
      }
    }

    onProgress?.({ loaded, total, pct: total > 0 ? Math.min(100, Math.round((loaded / total) * 100)) : 100 });

    if (items.length < PAGE_LIMIT) break;
    skip += PAGE_LIMIT;
  }

  // Full sync: reconcile deletes — drop rows of this activity the server no
  // longer returned (no tombstone log needed for this path). DILEWATI saat
  // quotaHit: kita berhenti lebih awal, jadi banyak id sah belum masuk
  // fetchedIds — mereka bukan "stale", menghapusnya justru mengecilkan cache.
  if (fullSync && fetchedIds && !quotaHit) {
    const existing = await db.getAllKeysFromIndex(ASSET_STORE, "by-activity", activityId);
    const stale = existing.filter((id) => !fetchedIds.has(id));
    if (stale.length) {
      const tx = db.transaction(ASSET_STORE, "readwrite");
      for (const id of stale) tx.store.delete(id);
      await tx.done;
    }
  }

  const count = (await db.getAllKeysFromIndex(ASSET_STORE, "by-activity", activityId)).length;
  const newMeta = { activityId, userId, lastSync: lastSyncCursor, count };
  try {
    await db.put(META_STORE, newMeta);
  } catch (e) {
    // Meta ~beberapa byte; bila ini pun kena kuota, catat tanpa crash. Snapshot
    // parsial tanpa meta baru akan dilayani berdasarkan meta lama (delta) atau
    // dianggap absen (full) — tetap konsisten, tak rusak.
    if (!isQuotaExceeded(e)) throw e;
    quotaHit = true;
  }
  return { count, lastSync: lastSyncCursor, partial: quotaHit };
}

/**
 * All snapshot rows for an activity, sorted created_at desc.
 * Returns null when no servable snapshot exists (absent OR past the 7-day
 * TTL — check isSnapshotExpired(await snapshotMeta(id)) to tell them apart).
 */
export async function getSnapshotAssets(activityId) {
  if (!activityId) return null;
  try {
    const db = await getDB();
    const meta = await db.get(META_STORE, activityId);
    if (!meta || isExpired(meta)) return null; // TTL: expired = absent
    const rows = await db.getAllFromIndex(ASSET_STORE, "by-activity", activityId);
    rows.sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")));
    return rows;
  } catch {
    return null;
  }
}

/**
 * Upsert one (optimistically edited) row so an offline reload shows the
 * change. No-ops unless a snapshot already exists for the activity, and
 * always strips non-projection fields (photos etc.) before writing.
 */
export async function upsertSnapshotAsset(activityId, row) {
  if (!activityId || !row?.id) return;
  try {
    const db = await getDB();
    const meta = await db.get(META_STORE, activityId);
    if (!meta) return; // no snapshot for this activity — nothing to keep fresh
    const clean = toSnapshotRow({ ...row, activity_id: activityId });
    await db.put(ASSET_STORE, clean);
  } catch {
    // Best-effort cache maintenance — the queue still holds the real change.
  }
}

/** Hapus SATU baris dari snapshot (setelah aset dihapus) agar reload offline
 *  tidak menampilkan aset yang sudah tidak ada. */
export async function removeSnapshotAsset(activityId, id) {
  if (!activityId || !id) return;
  try {
    const db = await getDB();
    const meta = await db.get(META_STORE, activityId);
    if (!meta) return;
    await db.delete(ASSET_STORE, id);
  } catch {
    // best-effort — TTL akan membereskan bila gagal
  }
}

/** Remove one activity's snapshot (rows + meta). */
export async function clearSnapshot(activityId) {
  if (!activityId) return;
  try {
    const db = await getDB();
    const keys = await db.getAllKeysFromIndex(ASSET_STORE, "by-activity", activityId);
    const tx = db.transaction([ASSET_STORE, META_STORE], "readwrite");
    for (const id of keys) tx.objectStore(ASSET_STORE).delete(id);
    tx.objectStore(META_STORE).delete(activityId);
    await tx.done;
  } catch {
    // ignore — worst case the TTL retires it
  }
}

/** Wipe every snapshot (all activities). Used on manual logout / user switch. */
export async function clearAllSnapshots() {
  try {
    const db = await getDB();
    const tx = db.transaction([ASSET_STORE, META_STORE], "readwrite");
    tx.objectStore(ASSET_STORE).clear();
    tx.objectStore(META_STORE).clear();
    await tx.done;
  } catch {
    // ignore
  }
}

/**
 * Login guard: if any stored snapshot belongs to a DIFFERENT user, wipe all
 * snapshots first — cached asset data must never leak across accounts on a
 * shared device. Same-user re-login keeps the cache (field data protection).
 */
export async function ensureSnapshotOwner(userId) {
  if (!userId) return;
  try {
    const db = await getDB();
    const metas = await db.getAll(META_STORE);
    if (metas.some((m) => m?.userId && m.userId !== userId)) {
      await clearAllSnapshots();
    }
  } catch {
    // ignore
  }
}
