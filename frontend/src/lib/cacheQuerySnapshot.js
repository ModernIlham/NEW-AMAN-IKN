import { filterSnapshotRows, sortSnapshotRows } from "./querySnapshotAset";
import { FIELD_CARI_ASET } from "./pencarianLokal";
import { hitungStatistikBaris } from "./statistikAset";

function canonical(value) {
  if (Array.isArray(value)) return [...new Set(value)].sort();
  if (value && typeof value === "object") return Object.fromEntries(Object.keys(value).sort().map(k => [k, canonical(value[k])]));
  return value;
}
export function kunciQuerySnapshot({ scope, meta, query, pendingRevision }) {
  return JSON.stringify([scope, meta.userId, meta.revision || 0, meta.lastSync, meta.disegarkanPada, meta.count,
    canonical(query), pendingRevision]);
}
export function buatCacheQuerySnapshot({ maxEntries = 4, maxBytes = 16 * 1024 * 1024, maxBaseBytes = 24 * 1024 * 1024 } = {}) {
  const entries = new Map();
  let bytes = 0, hits = 0, misses = 0, base = null;
  return {
    get(key) {
      const entry = entries.get(key);
      if (!entry) { misses++; return null; }
      hits++; entries.delete(key); entries.set(key, entry); return entry.value;
    },
    put(key, value) {
      const size = 256 + value.ids.reduce((sum, id) => sum + String(id).length * 2 + 32, 0);
      if (entries.has(key)) { bytes -= entries.get(key).size; entries.delete(key); }
      if (size > maxBytes) return false;
      entries.set(key, { value, size }); bytes += size;
      while (entries.size > maxEntries || bytes > maxBytes) {
        const first = entries.keys().next().value;
        bytes -= entries.get(first).size; entries.delete(first);
      }
      return true;
    },
    getBase(key) { return base?.key === key ? base.rows : null; },
    putBase(key, rows, size) { if (size <= maxBaseBytes) base = { key, rows, size }; },
    clear() { entries.clear(); bytes = 0; base = null; },
    metrics: () => ({ entries: entries.size, bytes, hits, misses, maxEntries, maxBytes,
      baseRows: base?.rows.length || 0, baseBytes: base?.size || 0, maxBaseBytes }),
  };
}
const SORT_FIELD = { newest: "created_at", oldest: "created_at", name_asc: "asset_name", name_desc: "asset_name",
  code_nup_asc: "asset_code", code_nup_desc: "asset_code",
  price_asc: "purchase_price", price_desc: "purchase_price", category_asc: "category", category_desc: "category",
  location_asc: "location", eselon1_asc: "eselon1", condition_asc: "condition", status_asc: "status" };
const QUERY_FIELDS = new Set([...FIELD_CARI_ASET, "id", "purchase_price", "purchase_date", "created_at", "inventory_status", "stiker_status", "pengguna_nip"]);
function queryRow(row) {
  const out = {};
  let bytes = 32;
  for (const field of QUERY_FIELDS) {
    const value = row[field];
    if (value === undefined || value === null || value === "") continue;
    out[field] = value;
    bytes += 16 + (typeof value === "string" ? value.length * 2 : 8);
  }
  return { row: out, bytes };
}
function assertActive(signal) {
  if (signal?.aborted) throw Object.assign(new Error("Read snapshot dibatalkan"), { name: "AbortError" });
}

/** Scan IDB dibatasi satu batch; cache hanya ID berurutan + statistik, tanpa
 * thumbnail/foto. Source rows(ids) mengembalikan hanya batch yang diminta. */
export async function queryHalamanSnapshot({ source, cache, scope, meta, query, page = 1, size = 50,
  pendingRevision = "", signal, batchSize = 128, clock = () => performance.now() }) {
  assertActive(signal);
  const key = kunciQuerySnapshot({ scope, meta, query, pendingRevision });
  let index = cache.get(key);
  const timing = { idbMs: 0, queryMs: 0, cacheHit: !!index, baseCacheHit: false, idbScanned: 0, scanned: 0 };
  if (!index) {
    let start = clock();
    const baseKey = JSON.stringify([scope, meta.userId, meta.revision || 0, meta.lastSync, meta.disegarkanPada, meta.count]);
    const baseline = cache.getBase(baseKey);
    timing.baseCacheHit = !!baseline;
    const keys = baseline ? null : await source.keys();
    timing.idbMs += clock() - start;
    const candidates = [];
    let baseRows = baseline ? null : [], baseBytes = 0;
    const stats = { totalAssets: 0, totalValue: 0, activeCount: 0, maintenanceCount: 0 };
    const field = SORT_FIELD[query.sort] || "created_at";
    const count = baseline ? baseline.length : keys.length;
    for (let i = 0; i < count; i += batchSize) {
      if (baseline && i > 0 && i % (batchSize * 8) === 0) await new Promise(resolve => setTimeout(resolve, 0));
      assertActive(signal); start = clock();
      let rows;
      if (baseline) rows = baseline.slice(i, i + batchSize);
      else {
        const loaded = (await source.rows(keys.slice(i, i + batchSize))).filter(Boolean);
        timing.idbMs += clock() - start;
        const projectionStart = clock();
        timing.idbScanned += loaded.length;
        const thin = loaded.map(queryRow);
        rows = thin.map(r => r.row);
        if (baseRows) {
          baseBytes += thin.reduce((sum, r) => sum + r.bytes, 0);
          if (baseBytes <= cache.metrics().maxBaseBytes) baseRows.push(...rows);
          else baseRows = null;
        }
        timing.queryMs += clock() - projectionStart;
      }
      timing.scanned += rows.length;
      assertActive(signal); start = clock();
      const filtered = filterSnapshotRows(rows, query);
      const partial = hitungStatistikBaris(filtered);
      for (const k of Object.keys(stats)) stats[k] += partial[k];
      for (const row of filtered) candidates.push({ id: row.id, [field]: row[field],
        ...(["code_nup_asc", "code_nup_desc"].includes(query.sort) ? { NUP: row.NUP } : {}) });
      timing.queryMs += clock() - start;
    }
    if (baseRows) cache.putBase(baseKey, baseRows, baseBytes);
    assertActive(signal); start = clock();
    const ordered = sortSnapshotRows(candidates, SORT_FIELD[query.sort] ? query.sort : "newest");
    index = { ids: ordered.map(r => r.id), stats: { ...stats, totalValue: stats.totalValue.toLocaleString("id-ID") } };
    timing.queryMs += clock() - start;
    cache.put(key, index);
  }
  const total = index.ids.length, totalPages = Math.max(1, Math.ceil(total / size));
  const currentPage = Math.max(1, Math.min(page, totalPages));
  assertActive(signal);
  const pageIds = index.ids.slice((currentPage - 1) * size, currentPage * size);
  const start = clock();
  const rows = await source.rows(pageIds);
  timing.idbMs += clock() - start;
  assertActive(signal);
  const byId = new Map(rows.filter(Boolean).map(row => [row.id, row]));
  return { items: pageIds.map(id => byId.get(id)).filter(Boolean), total, totalPages, currentPage, stats: index.stats, timing };
}

const pendingObjects = new WeakMap();
let nextPendingRevision = 0;
export function revisiAntreanSnapshot(items = []) {
  return items.map(item => {
    const payload = item.payload;
    if (payload && !pendingObjects.has(payload)) pendingObjects.set(payload, ++nextPendingRevision);
    return [item.statusKey || item.editId || item.tempId, item.queuedAt, !!item.isEdit,
      payload ? pendingObjects.get(payload) : 0].join(":");
  }).sort().join("|");
}
