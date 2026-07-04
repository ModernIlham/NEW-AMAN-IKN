// ============================================================================
// SERVICE WORKER v3 - OPTIMIZED
// Strategy: Stale-While-Revalidate for static assets
// Cache versioning with auto-cleanup
// ============================================================================

const CACHE_VERSION = 'v3';
const STATIC_CACHE = `inventory-static-${CACHE_VERSION}`;
const RUNTIME_CACHE = `inventory-runtime-${CACHE_VERSION}`;

// Pre-cache essential assets
const PRECACHE_URLS = [
  '/',
  '/manifest.json',
];

// ============================================================================
// INSTALL - Pre-cache critical resources
// ============================================================================
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then(cache => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting()) // Activate immediately
  );
});

// ============================================================================
// ACTIVATE - Clean up old caches
// ============================================================================
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames
          .filter(name => name !== STATIC_CACHE && name !== RUNTIME_CACHE)
          .map(name => {
            console.log(`[SW] Deleting old cache: ${name}`);
            return caches.delete(name);
          })
      );
    }).then(() => self.clients.claim()) // Take control of all pages
  );
});

// ============================================================================
// FETCH - Stale-While-Revalidate Strategy
// ============================================================================
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests
  if (request.method !== 'GET') return;

  // Skip API, WebSocket, and extension requests
  if (url.pathname.startsWith('/api') || 
      url.pathname.startsWith('/ws') || 
      url.protocol === 'ws:' || 
      url.protocol === 'wss:' ||
      url.protocol === 'chrome-extension:') {
    return;
  }

  // For navigation requests (HTML) - Network first, fallback to cache
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then(response => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(STATIC_CACHE).then(cache => cache.put(request, clone));
          }
          return response;
        })
        .catch(() => caches.match('/').then(r => r || caches.match(request)))
    );
    return;
  }

  // For static assets (JS, CSS, images, fonts) - Stale-While-Revalidate
  if (isStaticAsset(url.pathname)) {
    event.respondWith(
      caches.match(request).then(cachedResponse => {
        // Start fetching update in background
        const fetchPromise = fetch(request).then(networkResponse => {
          if (networkResponse.ok) {
            const clone = networkResponse.clone();
            caches.open(RUNTIME_CACHE).then(cache => cache.put(request, clone));
          }
          return networkResponse;
        }).catch(() => cachedResponse); // If network fails, rely on cache

        // Return cached immediately, or wait for network
        return cachedResponse || fetchPromise;
      })
    );
    return;
  }

  // For everything else - Network first
  event.respondWith(
    fetch(request).catch(() => caches.match(request))
  );
});

// ============================================================================
// HELPERS
// ============================================================================
function isStaticAsset(pathname) {
  return /\.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot|webp)(\?.*)?$/.test(pathname) ||
         pathname.startsWith('/static/');
}

// ============================================================================
// MESSAGE HANDLER - For manual cache clearing
// ============================================================================
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'CLEAR_CACHE') {
    caches.keys().then(names => {
      Promise.all(names.map(name => caches.delete(name)))
        .then(() => {
          console.log('[SW] All caches cleared');
          event.ports[0]?.postMessage({ success: true });
        });
    });
  }
});
