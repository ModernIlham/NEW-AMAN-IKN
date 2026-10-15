/* Public compiled assets only. Never cache authenticated API/media or IDB data. */
const LIGHTBOX_PRECACHE_URLS = /* AMAN_LIGHTBOX_PRECACHE */ [];
const RELEASE = /* AMAN_RELEASE_MANIFEST */ null;
const META_CACHE = 'inventory-release-meta-v1';
const META_KEY = '/__aman_release_meta__';
const CACHE_PREFIX = 'inventory-release-';
const GRACE_MS = 24 * 60 * 60 * 1000;
const MAX_RELEASES = 4;
const MAX_BYTES = 64 * 1024 * 1024;
const MAX_PINS = 128;
const LEGACY_CACHES = ['inventory-static-v4', 'inventory-runtime-v4'];
const SHELL = ['/', '/index.html', '/manifest.json'];
const release = RELEASE || { id: 'development', main: '', assets: LIGHTBOX_PRECACHE_URLS, critical: LIGHTBOX_PRECACHE_URLS };
const ownCache = CACHE_PREFIX + release.id;
let writes = Promise.resolve();
function serial(task) {
  const locked = () => {
    if (!self.navigator?.locks?.request) return notify('AMAN_CACHE_UPDATE_BLOCKED', { reason: 'cache_lock_unavailable' }).then(() => { throw new Error('cache_lock_unavailable'); });
    return self.navigator.locks.request('aman-public-release-cache-v1', { mode: 'exclusive' }, task);
  };
  const result = writes.then(locked, locked);
  writes = result.catch(() => {});
  return result;
}
async function readMeta() {
  const response = await (await caches.open(META_CACHE)).match(META_KEY);
  if (response) {
    try { const m = await response.json(); if (m?.releases && m?.pins) return m; } catch { /* recover metadata without deleting assets */ }
  }
  return { releases: {}, pins: {}, current: null, recovered: true };
}
async function saveMeta(meta) {
  await (await caches.open(META_CACHE)).put(META_KEY, new Response(JSON.stringify(meta), { headers: { 'Content-Type': 'application/json' } }));
}
async function clientsNow() { return self.clients.matchAll({ type: 'window', includeUncontrolled: true }); }
async function notify(type, detail = {}) {
  const clients = await clientsNow();
  for (const client of clients) client.postMessage({ type, ...detail });
}
async function cacheBytes(name) {
  const cache = await caches.open(name);
  let bytes = 0;
  for (const key of await cache.keys()) { const r = await cache.match(key); if (r) bytes += (await r.arrayBuffer()).byteLength; }
  return bytes;
}
async function importLegacy(meta) {
  if (meta.legacyImported) return;
  const existing = await caches.keys();
  const names = LEGACY_CACHES.filter(name => existing.includes(name));
  if (names.length) meta.releases.legacy = { id: 'legacy', cacheNames: names, createdAt: Date.now(), bytes: (await Promise.all(names.map(cacheBytes))).reduce((a, b) => a + b, 0), files: [], main: '' };
  meta.legacyImported = true;
}
function protectedCacheNames(meta) {
  return new Set([meta.current, ...Object.values(meta.pins).map(pin => pin.releaseId)].filter(Boolean).map(id => CACHE_PREFIX + id));
}
async function reconcileOrphans(meta) {
  const known = new Set(Object.values(meta.releases).flatMap(record => record.cacheNames));
  const protectedNames = protectedCacheNames(meta);
  const orphaned = (await caches.keys()).filter(name => /^inventory-release-[a-f0-9]{16}$/.test(name) && !known.has(name));
  for (const name of orphaned) {
    if (meta.recovered || protectedNames.has(name)) {
      // Metadata recovery cannot prove an old tab has stopped using this cache.
      // Adopt it into the one-time migration grace instead of deleting it.
      const legacy = meta.releases.legacy || { id: 'legacy', cacheNames: [], createdAt: Date.now(), bytes: 0, files: [], main: '' };
      legacy.cacheNames.push(name); legacy.bytes += await cacheBytes(name);
      meta.releases.legacy = legacy;
    } else if (name !== ownCache) {
      // An activated managed release always has a committed metadata record.
      // A valid manifest without this record identifies an interrupted install.
      await caches.delete(name);
    }
  }
  delete meta.recovered;
}
async function prune(meta, candidate = null, enforce = false) {
  const live = await clientsNow();
  const ids = new Set(live.map(c => c.id));
  for (const id of Object.keys(meta.pins)) if (!ids.has(id)) delete meta.pins[id];
  await reconcileOrphans(meta);
  const ordered = Object.values(meta.releases).sort((a, b) => b.createdAt - a.createdAt || a.id.localeCompare(b.id));
  const protectedIds = new Set([candidate, meta.current, ...Object.values(meta.pins).map(p => p.releaseId)].filter(Boolean));
  if (meta.releases.legacy?.cacheNames.some(name => protectedCacheNames(meta).has(name))) protectedIds.add('legacy');
  // Unupgraded tabs cannot report a release. Retain their potential caches until
  // they close; installation refuses a full protected budget instead of eviction.
  if (live.some(c => !meta.pins[c.id])) for (const r of ordered) protectedIds.add(r.id);
  const predecessor = ordered.find(r => r.id !== candidate && r.id !== meta.current);
  if (predecessor && Date.now() - predecessor.createdAt < GRACE_MS) protectedIds.add(predecessor.id);
  for (const r of ordered) if (Date.now() - r.createdAt < GRACE_MS) protectedIds.add(r.id);
  for (const r of [...ordered].reverse()) {
    if (protectedIds.has(r.id)) continue;
    for (const name of r.cacheNames) await caches.delete(name);
    delete meta.releases[r.id];
  }
  // Existing v4 contents have a one-time migration grace outside the new
  // budget. Their firstSeen is persisted even if a later install fails.
  const remaining = Object.values(meta.releases).filter(r => r.id !== 'legacy');
  const bytes = remaining.reduce((sum, r) => sum + r.bytes, 0);
  if (enforce && (remaining.length > MAX_RELEASES || bytes > MAX_BYTES || live.length > MAX_PINS)) throw new Error('cache_budget_protected');
  return { releases: remaining.length, bytes, maxReleases: MAX_RELEASES, maxBytes: MAX_BYTES };
}
function validAsset(path, response) {
  const mime = (response.headers.get('content-type') || '').split(';')[0].trim().toLowerCase();
  if (/\.js$/.test(path)) return /^(?:text|application)\/(?:x-)?(?:java|ecma)script$/.test(mime);
  if (/\.css$/.test(path)) return mime === 'text/css';
  if (path === '/manifest.json') return mime === 'application/json' || mime === 'application/manifest+json';
  return response.ok;
}
async function validShell(response) {
  if (!response.ok || (response.headers.get('content-type') || '').split(';')[0].trim().toLowerCase() !== 'text/html') return false;
  return !release.main || (await response.clone().text()).includes(release.main);
}
self.addEventListener('install', event => {
  event.waitUntil(serial(async () => {
    let preserveCandidate = (await caches.keys()).includes(ownCache);
    try {
      const meta = await readMeta(); await importLegacy(meta); await reconcileOrphans(meta);
      preserveCandidate = protectedCacheNames(meta).has(ownCache) || Object.values(meta.releases).some(record => record.cacheNames.includes(ownCache));
      await saveMeta(meta);
      const cache = await caches.open(ownCache);
      const urls = [...new Set([...SHELL, ...release.critical])];
      for (const url of urls) {
        const response = await fetch(new Request(url, { cache: 'reload', credentials: 'same-origin', integrity: release.integrity?.[url] || '' }));
        if (!response.ok || !validAsset(url, response) || ((url === '/' || url === '/index.html') && !await validShell(response))) throw new Error('release_precache_incomplete:' + url);
        await cache.put(url, response);
      }
      const previous = meta.releases[release.id];
      meta.releases[release.id] = { ...release, cacheNames: [ownCache], files: release.assets, createdAt: previous?.createdAt || Date.now(), bytes: await cacheBytes(ownCache) };
      await prune(meta, release.id, true); await saveMeta(meta);
      await self.skipWaiting();
    } catch (error) {
      if (!preserveCandidate) await caches.delete(ownCache);
      try { await notify('AMAN_CACHE_UPDATE_BLOCKED', { reason: error.message }); } catch { /* retain incumbent worker */ }
      throw error;
    }
  }));
});
self.addEventListener('activate', event => {
  event.waitUntil(serial(async () => {
    const meta = await readMeta(); meta.current = release.id;
    await prune(meta); await saveMeta(meta); await self.clients.claim();
    await notify('AMAN_CACHE_RELEASE', { releaseId: release.id });
  }));
});
function lifetime(event, task) { event.waitUntil(task.catch(() => {})); }
async function findCached(path, meta) {
  const records = Object.values(meta.releases).sort((a, b) => (b.id === release.id) - (a.id === release.id));
  for (const record of records) for (const name of record.cacheNames) {
    const response = await caches.match(path, { cacheName: name });
    if (response) return response;
  }
  return null;
}
async function storePublic(path, response, shell = false) {
  return serial(async () => {
    const meta = await readMeta();
    const record = shell ? meta.releases[release.id] : Object.values(meta.releases).find(r => r.files?.includes(path));
    if (!record) return;
    const cache = await caches.open(record.cacheNames[0]);
    const previous = await cache.match(path);
    const oldSize = previous ? (await previous.clone().arrayBuffer()).byteLength : 0;
    const size = (await response.clone().arrayBuffer()).byteLength;
    const total = Object.values(meta.releases).filter(r => r.id !== 'legacy').reduce((sum, r) => sum + r.bytes, 0);
    if (total - oldSize + size > MAX_BYTES) return; // a successful network response must still reach the page
    // Reserve bytes before the cache mutation. A crash can overcount, never
    // leave unaccounted cached bodies. A quota failure preserves the old entry.
    const reservedDelta = Math.max(0, size - oldSize);
    record.bytes += reservedDelta; await saveMeta(meta);
    try { await cache.put(path, response); }
    catch (error) {
      record.bytes -= reservedDelta;
      try { await saveMeta(meta); } catch { /* conservative reservation is safe */ }
      throw error;
    }
    if (size < oldSize) { record.bytes += size - oldSize; await saveMeta(meta); }
  });
}
self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/api') || url.pathname.startsWith('/ws')) return;
  if (request.mode === 'navigate') {
    event.respondWith((async () => {
      try {
        const response = await fetch(request);
        if (await validShell(response)) lifetime(event, storePublic('/index.html', response.clone(), true));
        return response;
      } catch (error) {
        const own = await caches.open(ownCache);
        const cached = await own.match('/index.html') || await own.match('/');
        if (cached) return cached;
        throw error;
      }
    })()); return;
  }
  // Only webpack-produced immutable assets, without arbitrary query-key growth.
  if (!url.pathname.startsWith('/static/')) return;
  event.respondWith((async () => {
    const meta = await readMeta();
    const cached = await findCached(url.pathname, meta);
    if (cached) return cached;
    const record = Object.values(meta.releases).find(r => r.files?.includes(url.pathname));
    const response = await fetch(record?.integrity?.[url.pathname] ? new Request(request, { integrity: record.integrity[url.pathname] }) : request);
    if (response.ok && validAsset(url.pathname, response) && record) lifetime(event, storePublic(url.pathname, response.clone()));
    return response;
  })());
});
self.addEventListener('message', event => {
  const data = event.data || {};
  if (data.type !== 'AMAN_PIN_RELEASE' && data.type !== 'CLEAR_CACHE' && data.type !== 'AMAN_CACHE_STATUS') return;
  event.waitUntil(serial(async () => {
    const meta = await readMeta();
    if (data.type === 'AMAN_PIN_RELEASE' && event.source?.id) {
      const record = Object.values(meta.releases).find(r => r.main === data.main);
      if (record && (meta.pins[event.source.id] || Object.keys(meta.pins).length < MAX_PINS)) meta.pins[event.source.id] = { releaseId: record.id };
    }
    const status = await prune(meta); await saveMeta(meta);
    event.ports?.[0]?.postMessage({ success: true, ...status, releaseId: release.id });
  }));
});
