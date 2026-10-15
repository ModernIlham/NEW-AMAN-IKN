import { performance } from "perf_hooks";
import { buatCacheQuerySnapshot, queryHalamanSnapshot } from "../cacheQuerySnapshot";
import { filterSnapshotRows, sortSnapshotRows } from "../querySnapshotAset";
function fixture(count) {
  const data = new Map(Array.from({ length: count }, (_, i) => {
    const row = { id: `id-${String(i).padStart(7, "0")}`, asset_name: `Kursi ${i}`, activity_id: "a",
      purchase_price: `${100 + (i % 20)}.01`, created_at: `2026-10-${String(1 + i % 20).padStart(2,"0")}`, purchase_date: `2026-09-${String(1+i%20).padStart(2,"0")}`,
      status: i % 3 ? "Aktif" : "Maintenance", condition: i % 2 ? "Baik" : "Rusak Ringan", location: "Gedung Utama",
      thumbnail: "data:image/jpeg;base64," + "a".repeat(4096) };
    return [row.id, row];
  }));
  let maxBatch = 0;
  const source = { keys: jest.fn(async () => [...data.keys()]), rows: jest.fn(async ids => {
    maxBatch = Math.max(maxBatch, ids.length);
    // Model clone IDB: media tidak pernah diclone untuk seluruh 50k sekaligus.
    return ids.map(id => ({ ...data.get(id) }));
  }) };
  return { data, source, maxBatch: () => maxBatch };
}
const scope = { owner: "u", satker: "s", activity: "a" };
const meta = { userId: "u", revision: 1, count: 50000, lastSync: "2026-10-15" };

test.each([1000, 10000, 50000])("%i baris: halaman kedua tidak mengulang scan/filter/sort, cache tidak menyimpan media", async count => {
  const f = fixture(count), cache = buatCacheQuerySnapshot();
  const query = { search: "Kursi", category: [], filters: { condition: ["Baik", "Rusak Ringan"], priceMin: "110", dateFrom: "2026-09-03" }, sort: "price_desc" };
  const start = performance.now();
  const first = await queryHalamanSnapshot({ source: f.source, cache, scope, meta, query, clock: () => performance.now() });
  const firstMs = performance.now() - start;
  const baseline = sortSnapshotRows(filterSnapshotRows([...f.data.values()], query), query.sort).map(r => r.id);
  expect(first.items.map(r => r.id)).toEqual(baseline.slice(0, 50));
  const reads = f.source.rows.mock.calls.length;
  const secondStart = performance.now();
  const second = await queryHalamanSnapshot({ source: f.source, cache, scope, meta, query, page: 2, clock: () => performance.now() });
  const pageMs = performance.now() - secondStart;
  expect(second.items.map(r => r.id)).toEqual(baseline.slice(50, 100));
  expect(second.timing).toMatchObject({ cacheHit: true, scanned: 0, queryMs: 0 });
  expect(f.source.rows.mock.calls.length - reads).toBe(1);
  expect(f.source.keys).toHaveBeenCalledTimes(1); expect(f.maxBatch()).toBeLessThanOrEqual(128);
  expect(cache.metrics().bytes).toBeLessThan(16 * 1024 * 1024);
  if (process.env.AMAN_QA_BENCHMARK) console.log(JSON.stringify({ count, firstMs, pageMs, timing: first.timing, cache: cache.metrics() }));
});

test("revision snapshot/pending/scope/query invalidates and LRU bounds retained ID lists", async () => {
  const f = fixture(1000), cache = buatCacheQuerySnapshot({ maxEntries: 2, maxBytes: 100000 });
  const query = { filters: {}, sort: "newest" };
  const read = extra => queryHalamanSnapshot({ source: f.source, cache, scope, meta, query, ...extra });
  await read({}); await read({ pendingRevision: "new-queue" });
  await read({ meta: { ...meta, revision: 2 } });
  await read({ scope: { ...scope, owner: "other-user" } });
  expect(f.source.keys).toHaveBeenCalledTimes(3);
  expect(cache.metrics().entries).toBeLessThanOrEqual(2); expect(cache.metrics().bytes).toBeLessThanOrEqual(100000);
  await read({}); expect(f.source.keys).toHaveBeenCalledTimes(4);
});

test("abort saat scan menghentikan batch berikutnya tanpa memasukkan query setengah jadi ke cache", async () => {
  const f = fixture(1000), cache = buatCacheQuerySnapshot(), controller = new AbortController();
  const original = f.source.rows.getMockImplementation();
  f.source.rows.mockImplementation(async ids => { const rows = await original(ids); controller.abort(); return rows; });
  await expect(queryHalamanSnapshot({ source: f.source, cache, scope, meta, query: { filters: {} }, signal: controller.signal })).rejects.toMatchObject({ name: "AbortError" });
  expect(f.source.rows).toHaveBeenCalledTimes(1); expect(cache.metrics().entries).toBe(0);
});


test("query baru dan pending queue baru memakai metadata tanpa clone thumbnail seluruh snapshot", async () => {
  const f = fixture(1000), cache = buatCacheQuerySnapshot();
  const options = { source: f.source, cache, scope, meta, query: { filters: {}, sort: "price_asc" } };
  await queryHalamanSnapshot(options);
  const reads = f.source.rows.mock.calls.length;
  const next = await queryHalamanSnapshot({ ...options, query: { search: "Kursi 99", filters: {}, sort: "price_desc" }, pendingRevision: "draft-2" });
  expect(next.timing.baseCacheHit).toBe(true); expect(next.timing.idbScanned).toBe(0);
  expect(f.source.keys).toHaveBeenCalledTimes(1); expect(f.source.rows.mock.calls.length - reads).toBe(1);
  expect(cache.metrics().baseRows).toBe(1000); expect(cache.metrics().baseBytes).toBeLessThan(24*1024*1024);
});
