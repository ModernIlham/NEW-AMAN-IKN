import fs from "fs";
import path from "path";
import vm from "vm";
const template = fs.readFileSync(path.resolve(__dirname, "../../../public/service-worker.js"), "utf8");
class Reply {
  constructor(body = "", options = {}) { this.body = String(body); this.status = options.status || 200; this.ok = this.status >= 200 && this.status < 300; const values = options.headers || {}; this.headerValues = values; this.headers = { get: key => values[key] || null }; }
  clone() { return new Reply(this.body, { status: this.status, headers: this.headerValues }); }
  async text() { return this.body; }
  async json() { return JSON.parse(this.body); }
  async arrayBuffer() { const bytes = Buffer.from(this.body); return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength); }
}
class PublicRequest { constructor(url, options = {}) { this.url = new URL(typeof url === "string" ? url : url.url, "https://aman.test").href; this.method = "GET"; Object.assign(this, options); } }
const keyOf = input => new PublicRequest(input).url;
function env() {
  const stores = new Map(), network = new Map(), clients = new Map();
  let clock = 1000000000000, offline = false, failPut = null, beforePut = null, lock = Promise.resolve();
  const locks = { request: (_name, _options, task) => { const result = lock.then(task, task); lock = result.catch(() => {}); return result; } };
  const cacheFor = name => {
    if (!stores.has(name)) stores.set(name, new Map());
    const rows = stores.get(name);
    return { match: async key => rows.get(keyOf(key))?.clone(), keys: async () => [...rows.keys()].map(key => new PublicRequest(key)),
      put: async (key, response) => { if (beforePut) await beforePut(name, keyOf(key), response); if (failPut?.(name, keyOf(key))) throw new Error("QuotaExceededError"); rows.set(keyOf(key), response.clone()); }, delete: async key => rows.delete(keyOf(key)) };
  };
  const caches = { open: async name => cacheFor(name), keys: async () => [...stores.keys()], delete: jest.fn(async name => stores.delete(name)), match: async (key, { cacheName } = {}) => cacheName ? stores.get(cacheName)?.get(keyOf(key))?.clone() : [...stores.values()].map(rows => rows.get(keyOf(key))).find(Boolean)?.clone() };
  const fetch = jest.fn(async request => { if (offline) throw new Error("offline"); return (network.get(keyOf(request)) || new Reply("404", { status: 404 })).clone(); });
  const serve = release => { network.set(keyOf("/"), new Reply(`<script src="${release.main}"></script>`, { headers: { "content-type": "text/html" } })); network.set(keyOf("/index.html"), network.get(keyOf("/"))); network.set(keyOf("/manifest.json"), new Reply("{}", { headers: { "content-type": "application/json" } })); for (const file of release.assets) network.set(keyOf(file), new Reply(file, { headers: { "content-type": "application/javascript" } })); };
  const worker = (release, withLocks = true) => {
    const handlers = {};
    const self = { navigator: { locks: withLocks ? locks : null }, location: { origin: "https://aman.test" }, addEventListener: (type, handler) => { handlers[type] = handler; }, skipWaiting: jest.fn(async () => {}), clients: { matchAll: async () => [...clients.values()], claim: jest.fn(async () => {}) } };
    vm.runInNewContext(template.replace("/* AMAN_LIGHTBOX_PRECACHE */ []", "[]").replace("/* AMAN_RELEASE_MANIFEST */ null", JSON.stringify(release)), { self, caches, fetch, URL, Request: PublicRequest, Response: Reply, console, Date: { now: () => clock } });
    const emit = (type, options = {}) => {
      const waits = []; let response;
      handlers[type]({ ...options, waitUntil: p => waits.push(p), respondWith: p => { response = p; } });
      return { get response() { return response; }, async done() { let count = 0; do { count = waits.length; await Promise.all(waits); } while (waits.length !== count); } };
    };
    return { self, emit, async install() { await emit("install").done(); }, async activate() { await emit("activate").done(); }, async request(file, mode) { const e = emit("fetch", { request: new PublicRequest(file, { mode }) }); const response = await e.response; await e.done(); return response; }, async pin(id, main) { await emit("message", { source: { id }, data: { type: "AMAN_PIN_RELEASE", main } }).done(); }, async clean() { await emit("message", { data: { type: "CLEAR_CACHE" } }).done(); } };
  };
  const metadata = () => JSON.parse(stores.get("inventory-release-meta-v1").get(keyOf("/__aman_release_meta__")).body);
  return { stores, network, caches, fetch, clients, serve, worker, metadata, offline: value => { offline = value; }, fail: fn => { failPut = fn; }, beforePut: fn => { beforePut = fn; }, advance: ms => { clock += ms; } };
}
const release = id => ({ id, main: `/static/js/main.${id}.js`, assets: [`/static/js/main.${id}.js`, `/static/js/editor.${id}.js`, `/static/js/lightbox.${id}.js`, `/static/js/lazy.${id}.js`], critical: [`/static/js/main.${id}.js`, `/static/js/editor.${id}.js`, `/static/js/lightbox.${id}.js`] });
async function start(e, r) { e.serve(r); const w = e.worker(r); await w.install(); await w.activate(); return w; }
test("install memverifikasi shell, editor, dan lightbox sebelum aktivasi; gagal chunk mempertahankan rilis lama", async () => {
  const e = env(), a = release("aaa"), old = await start(e, a);
  expect(old.self.skipWaiting).toHaveBeenCalledTimes(1);
  const b = release("bbb"); e.serve(b); e.network.delete(keyOf(b.critical[1])); const next = e.worker(b);
  await expect(next.install()).rejects.toThrow("release_precache_incomplete");
  expect(next.self.skipWaiting).not.toHaveBeenCalled(); expect(e.stores.has("inventory-release-aaa")).toBe(true); expect(e.stores.has("inventory-release-bbb")).toBe(false);
});
test("dua tab dua rilis: kode belum dibuka tetap tersedia offline dan HTML fallback konsisten", async () => {
  const e = env(), a = release("aaa"), old = await start(e, a);
  e.clients.set("old", { id: "old", postMessage: jest.fn() }); await old.pin("old", a.main);
  const b = release("bbb"), next = await start(e, b);
  e.clients.set("new", { id: "new", postMessage: jest.fn() }); await next.pin("new", b.main);
  e.offline(true);
  expect(await (await next.request(a.critical[1])).text()).toBe(a.critical[1]);
  expect(await (await next.request(a.critical[2])).text()).toBe(a.critical[2]);
  expect(await (await next.request("/inventory", "navigate")).text()).toContain(b.main);
  expect(Object.values(e.metadata().pins).map(p => p.releaseId).sort()).toEqual(["aaa", "bbb"]);
});
test("hash immutable cache-first tidak revalidate; API/media dan origin lain dilewati", async () => {
  const e = env(), a = release("aaa"), w = await start(e, a); const n = e.fetch.mock.calls.length;
  await w.request(a.main); await w.request(a.main + "?ignored=1"); expect(e.fetch).toHaveBeenCalledTimes(n);
  for (const url of ["/api/assets/a/photos/0.jpg", "/ws/events", "https://other.test/static/js/main.aaa.js"]) expect(w.emit("fetch", { request: new PublicRequest(url) }).response).toBeUndefined();
});
test("HTML rilis baru tidak merusak fallback offline rilis worker yang masih berjalan", async () => {
  const e = env(), a = release("aaa"), w = await start(e, a), b = release("bbb"); e.serve(b);
  expect(await (await w.request("/", "navigate")).text()).toContain(b.main);
  e.offline(true); expect(await (await w.request("/", "navigate")).text()).toContain(a.main);
});
test("quota cache write dan metadata write tidak menggagalkan respons jaringan atau menambah entry liar", async () => {
  const e = env(), a = release("aaa"), w = await start(e, a), file = a.assets[3];
  e.fail(name => name === "inventory-release-aaa"); expect(await (await w.request(file)).text()).toBe(file); expect(e.stores.get("inventory-release-aaa").has(keyOf(file))).toBe(false);
  e.fail(name => name === "inventory-release-meta-v1"); expect(await (await w.request(file)).text()).toBe(file); expect(e.stores.get("inventory-release-aaa").has(keyOf(file))).toBe(false);
});
test("cache akhir bounded sesudah grace dan tab lama tutup; clear tidak menghapus rilis terpin atau cache aplikasi lain", async () => {
  const e = env(), a = release("aaa"), w = await start(e, a); e.stores.set("other-app", new Map());
  e.clients.set("old", { id: "old", postMessage: jest.fn() }); await w.pin("old", a.main);
  const b = release("bbb"), next = await start(e, b); e.advance(2 * 86400000); await next.clean();
  expect(e.stores.has("inventory-release-aaa")).toBe(true);
  e.clients.delete("old"); await next.clean(); expect(e.stores.has("inventory-release-aaa")).toBe(false); expect(e.stores.has("inventory-release-bbb")).toBe(true); expect(e.stores.has("other-app")).toBe(true);
});
test("anggaran rilis yang seluruhnya dilindungi menolak install berikutnya tanpa menghapus rilis aktif", async () => {
  const e = env(); for (const id of ["aaa", "bbb", "ccc", "ddd"]) { await start(e, release(id)); e.advance(1000); }
  const fifth = release("eee"); e.serve(fifth); const next = e.worker(fifth); await expect(next.install()).rejects.toThrow("cache_budget_protected");
  expect([...e.stores.keys()].filter(name => /^inventory-release-(?!meta)/.test(name))).toHaveLength(4); expect(e.metadata().current).toBe("ddd");
});
test("install yang melihat HTML dari deploy berbeda ditolak agar cold start tidak mengacu chunk salah", async () => {
  const e = env(), a = release("aaa"); e.serve(a); e.network.set(keyOf("/index.html"), new Reply("<script src='/static/js/main.bbb.js'></script>"));
  await expect(e.worker(a).install()).rejects.toThrow("release_precache_incomplete:/index.html");
});

test("fallback HTML200 pada chunk kritis ditolak sebelum aktivasi", async () => {
  const e = env(), a = release("aaa"); e.serve(a); e.network.set(keyOf(a.critical[1]), new Reply("<html>SPA fallback</html>", { headers: { "content-type": "text/html" } }));
  const w = e.worker(a); await expect(w.install()).rejects.toThrow("release_precache_incomplete"); expect(w.self.skipWaiting).not.toHaveBeenCalled();
});

test("old active cache write dan install baru memakai lock global sehingga metadata tidak hilang", async () => {
  const e = env(), a = release("aaa"), old = await start(e, a);
  let releaseSave, entered; const gate = new Promise(resolve => { releaseSave = resolve; }); const writing = new Promise(resolve => { entered = resolve; }); let paused = false;
  e.beforePut(async name => { if (name === "inventory-release-meta-v1" && !paused) { paused = true; entered(); await gate; } });
  const oldWrite = old.request(a.assets[3]); await writing;
  const b = release("bbb"); e.serve(b); const next = e.worker(b); const install = next.install(); await Promise.resolve();
  expect(e.metadata().current).toBe("aaa"); releaseSave(); await Promise.all([oldWrite, install]); await next.activate();
  expect(Object.keys(e.metadata().releases).sort()).toEqual(["aaa", "bbb"]); expect(e.metadata().current).toBe("bbb");
  e.offline(true); expect(await (await next.request(b.main)).text()).toBe(b.main);
});
test("browser tanpa Web Locks menolak aktivasi baru dengan petunjuk, menjaga cache yang ada", async () => {
  const e = env(), a = release("aaa"); e.serve(a); e.clients.set("tab", { id: "tab", postMessage: jest.fn() }); const w = e.worker(a, false);
  await expect(w.install()).rejects.toThrow("cache_lock_unavailable"); expect(w.self.skipWaiting).not.toHaveBeenCalled();
  expect(e.clients.get("tab").postMessage).toHaveBeenCalledWith(expect.objectContaining({ type: "AMAN_CACHE_UPDATE_BLOCKED", reason: "cache_lock_unavailable" }));
});

test("migrasi v4 mencatat awal grace sekali meski install gagal; cache besar lama tidak mengunci budget baru", async () => {
  const e = env(), a = release("aaa"); e.stores.set("inventory-static-v4", new Map([[keyOf("/index.html"), new Reply("legacy")]])); e.serve(a); e.network.delete(keyOf(a.critical[1]));
  await expect(e.worker(a).install()).rejects.toThrow("release_precache_incomplete"); const firstSeen = e.metadata().releases.legacy.createdAt;
  e.advance(10000); await expect(e.worker(a).install()).rejects.toThrow("release_precache_incomplete"); expect(e.metadata().releases.legacy.createdAt).toBe(firstSeen);
  const metadata = e.metadata(); metadata.releases.legacy.bytes = 70 * 1024 * 1024;
  await (await e.caches.open("inventory-release-meta-v1")).put("/__aman_release_meta__", new Reply(JSON.stringify(metadata)));
  const w = await start(e, a); expect(w.self.skipWaiting).toHaveBeenCalled(); expect(e.stores.has("inventory-static-v4")).toBe(true);
  e.advance(2 * 86400000); await w.clean(); expect(e.stores.has("inventory-static-v4")).toBe(false); expect(e.stores.has("inventory-release-aaa")).toBe(true);
});

test("cache kandidat tersisa setelah hardcrash dicatat atau dibersihkan tanpa melewati budget selamanya", async () => {
  const e = env(), a = release("1111111111111111"), old = await start(e, a);
  e.clients.set("old", { id: "old", postMessage: jest.fn() }); await old.pin("old", a.main);
  const orphan = "inventory-release-2222222222222222";
  e.stores.set(orphan, new Map([[keyOf("/partial.js"), new Reply("partial install before metadata")]]));
  const b = release("2222222222222222"); e.serve(b); e.network.delete(keyOf(b.critical[1]));
  await expect(e.worker(b).install()).rejects.toThrow("release_precache_incomplete");
  expect(e.stores.has(orphan)).toBe(false); expect(e.stores.has("inventory-release-1111111111111111")).toBe(true);
  e.stores.set("inventory-release-3333333333333333", new Map()); e.stores.set("other-app", new Map());
  await old.clean(); expect(e.stores.has("inventory-release-3333333333333333")).toBe(false); expect(e.stores.has("other-app")).toBe(true);
});
test("metadata hilang memulihkan cache incumbent tak dikenal ke grace dan baru menghapus setelah aman", async () => {
  const e = env(), incumbent = "inventory-release-1111111111111111";
  e.stores.set(incumbent, new Map([[keyOf("/old.js"), new Reply("old code")]]));
  e.clients.set("old", { id: "old", postMessage: jest.fn() });
  const b = release("2222222222222222"), next = await start(e, b);
  expect(e.stores.has(incumbent)).toBe(true); expect(e.metadata().releases.legacy.cacheNames).toContain(incumbent);
  const metadata = e.metadata(); metadata.pins.old = { releaseId: "1111111111111111" };
  await (await e.caches.open("inventory-release-meta-v1")).put("/__aman_release_meta__", new Reply(JSON.stringify(metadata)));
  e.advance(2 * 86400000); await next.clean(); expect(e.stores.has(incumbent)).toBe(true);
  e.clients.delete("old"); await next.clean(); expect(e.stores.has(incumbent)).toBe(false); expect(e.stores.has("inventory-release-2222222222222222")).toBe(true);
});

test("reservasi HTML lebih pendek tidak mengurangi byte sebelum body lama terganti", async () => {
  const e = env(), a = release("aaa"); e.serve(a);
  const short = `<script src="${a.main}"></script>`, long = short + "x".repeat(1000);
  for (const url of ["/", "/index.html"]) e.network.set(keyOf(url), new Reply(long, { headers: { "content-type": "text/html" } }));
  const w = e.worker(a); await w.install(); await w.activate(); const oldBytes = e.metadata().releases.aaa.bytes;
  let entered, releasePut; const writing = new Promise(r => { entered = r; }); const gate = new Promise(r => { releasePut = r; });
  e.beforePut(async (name, key) => { if (name === "inventory-release-aaa" && key === keyOf("/index.html")) { entered(); await gate; } });
  e.network.set(keyOf("/"), new Reply(short, { headers: { "content-type": "text/html" } })); const write = w.request("/", "navigate"); await writing;
  expect(e.metadata().releases.aaa.bytes).toBe(oldBytes); expect(e.stores.get("inventory-release-aaa").get(keyOf("/index.html")).body).toBe(long);
  releasePut(); await write; expect(e.metadata().releases.aaa.bytes).toBe(oldBytes - 1000);
});
