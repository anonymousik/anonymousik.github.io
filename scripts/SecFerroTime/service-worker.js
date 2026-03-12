// ============================================
// SECFERRO DIVISION - SERVICE WORKER v5.0
// PWA Offline Support + Cache Strategy
// Compatible with Quantum Time Terminal v5.0 FUSION 2025
// ============================================

const CACHE_NAME = 'secferro-v5.0.0';
const RUNTIME_CACHE = 'secferro-runtime-v5.0.0';

// Critical resources to cache on install
const CRITICAL_ASSETS = [
  '/',
  '/index.html',
  '/manifest.json',
  '/service-worker.js',
  'https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Orbitron:wght@400;700;900&display=swap'
];

// Font files to cache (CDN)
const FONT_CACHE_URLS = [
  /fonts\.googleapis\.com/,
  /fonts\.gstatic\.com/
];

// ============================================
// INSTALL EVENT - Cache Critical Assets
// ============================================
self.addEventListener('install', (event) => {
  console.log('[SW] Installing Service Worker v3.0.0...');
  
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('[SW] Caching critical assets...');
        return cache.addAll(CRITICAL_ASSETS);
      })
      .then(() => {
        console.log('[SW] ✅ Installation complete - Skip waiting');
        return self.skipWaiting();
      })
      .catch((error) => {
        console.error('[SW] ❌ Installation failed:', error);
      })
  );
});

// ============================================
// ACTIVATE EVENT - Clean Old Caches
// ============================================
self.addEventListener('activate', (event) => {
  console.log('[SW] Activating Service Worker v3.0.0...');
  
  event.waitUntil(
    caches.keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames.map((cacheName) => {
            if (cacheName !== CACHE_NAME && cacheName !== RUNTIME_CACHE) {
              console.log('[SW] 🗑️ Deleting old cache:', cacheName);
              return caches.delete(cacheName);
            }
          })
        );
      })
      .then(() => {
        console.log('[SW] ✅ Activation complete - Claiming clients');
        return self.clients.claim();
      })
  );
});

// ============================================
// FETCH EVENT - Network-First Strategy
// ============================================
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);
  
  // Skip non-GET requests
  if (request.method !== 'GET') {
    return;
  }
  
  // Skip chrome-extension and other protocols
  if (!url.protocol.startsWith('http')) {
    return;
  }
  
  // Strategy 1: Network-First for HTML (always fresh)
  if (request.headers.get('accept')?.includes('text/html')) {
    event.respondWith(
      networkFirst(request, CACHE_NAME)
    );
    return;
  }
  
  // Strategy 2: Cache-First for Fonts (performance)
  if (FONT_CACHE_URLS.some(pattern => pattern.test(url.href))) {
    event.respondWith(
      cacheFirst(request, RUNTIME_CACHE)
    );
    return;
  }
  
  // Strategy 3: Stale-While-Revalidate for other assets
  event.respondWith(
    staleWhileRevalidate(request, RUNTIME_CACHE)
  );
});

// ============================================
// CACHING STRATEGIES
// ============================================

/**
 * Network-First Strategy
 * Try network, fallback to cache
 * Best for: HTML, API calls
 */
async function networkFirst(request, cacheName) {
  try {
    const networkResponse = await fetch(request);
    
    // Cache successful responses
    if (networkResponse.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, networkResponse.clone());
    }
    
    return networkResponse;
  } catch (error) {
    console.log('[SW] 📡 Network failed, using cache:', request.url);
    const cachedResponse = await caches.match(request);
    
    if (cachedResponse) {
      return cachedResponse;
    }
    
    // Return offline page if available
    return caches.match('/offline.html') || new Response(
      '<!DOCTYPE html><html><head><title>Offline</title></head><body style="background:#000;color:#00ff41;font-family:monospace;padding:2rem;text-align:center;"><h1>🛡️ SecFerro Division</h1><p>You are currently offline</p><p>Connection will restore automatically</p></body></html>',
      { headers: { 'Content-Type': 'text/html' } }
    );
  }
}

/**
 * Cache-First Strategy
 * Check cache first, then network
 * Best for: Fonts, images, static assets
 */
async function cacheFirst(request, cacheName) {
  const cachedResponse = await caches.match(request);
  
  if (cachedResponse) {
    console.log('[SW] ⚡ Serving from cache:', request.url);
    return cachedResponse;
  }
  
  try {
    const networkResponse = await fetch(request);
    
    if (networkResponse.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, networkResponse.clone());
    }
    
    return networkResponse;
  } catch (error) {
    console.error('[SW] ❌ Cache and network failed:', request.url);
    return new Response('Resource not available', { status: 503 });
  }
}

/**
 * Stale-While-Revalidate Strategy
 * Serve cache immediately, update in background
 * Best for: CSS, JS, non-critical resources
 */
async function staleWhileRevalidate(request, cacheName) {
  const cachedResponse = await caches.match(request);
  
  const fetchPromise = fetch(request)
    .then((networkResponse) => {
      if (networkResponse.ok) {
        const cache = caches.open(cacheName);
        cache.then(c => c.put(request, networkResponse.clone()));
      }
      return networkResponse;
    })
    .catch(() => {
      console.log('[SW] 📡 Background update failed for:', request.url);
    });
  
  // Return cached version immediately if available, or wait for fetch
  return cachedResponse || fetchPromise || new Response('', { status: 503 });
}

// ============================================
// MESSAGE EVENT - Cache Management
// ============================================
self.addEventListener('message', (event) => {
  if (event.data.type === 'SKIP_WAITING') {
    console.log('[SW] 🔄 Force update requested');
    self.skipWaiting();
  }
  
  if (event.data.type === 'CLEAR_CACHE') {
    console.log('[SW] 🗑️ Clearing all caches...');
    event.waitUntil(
      caches.keys().then((cacheNames) => {
        return Promise.all(
          cacheNames.map((cacheName) => caches.delete(cacheName))
        );
      })
    );
  }
  
  if (event.data.type === 'GET_VERSION') {
    event.ports[0].postMessage({
      version: CACHE_NAME,
      timestamp: new Date().toISOString()
    });
  }
});

// ============================================
// PUSH NOTIFICATION SUPPORT (Optional)
// ============================================
self.addEventListener('push', (event) => {
  const options = {
    body: event.data ? event.data.text() : 'SecFerro Division Update',
    icon: 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 192 192"%3E%3Crect fill="%23000" width="192" height="192"/%3E%3Cpath d="M96,30 L156,60 L156,120 Q156,150 96,165 Q36,150 36,120 L36,60 Z" fill="none" stroke="%2300ff41" stroke-width="4"/%3E%3C/svg%3E',
    badge: 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96"%3E%3Crect fill="%2300ff41" width="96" height="96"/%3E%3C/svg%3E',
    vibrate: [200, 100, 200],
    tag: 'secferro-notification',
    requireInteraction: false
  };
  
  event.waitUntil(
    self.registration.showNotification('SecFerro Division', options)
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(
    clients.openWindow('/')
  );
});

// ============================================
// BACKGROUND SYNC (Optional)
// ============================================
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-data') {
    console.log('[SW] 🔄 Background sync triggered');
    event.waitUntil(
      // Add your sync logic here
      Promise.resolve()
    );
  }
});

// ============================================
// ERROR HANDLING
// ============================================
self.addEventListener('error', (event) => {
  console.error('[SW] ❌ Service Worker Error:', event.error);
});

self.addEventListener('unhandledrejection', (event) => {
  console.error('[SW] ❌ Unhandled Promise Rejection:', event.reason);
});

console.log('[SW] 🛡️ SecFerro Service Worker v5.0.0 Loaded — Quantum Time Terminal FUSION 2025');