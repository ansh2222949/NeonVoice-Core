/* NeonAI: Frontend logic (UI, chat, settings). */

// NeonAI — Service Worker (PWA Offline Shell)
const CACHE_NAME = 'neonai-v5';
const SHELL_ASSETS = [
    '/',
    '/static/styles.css',
    '/static/app.js',
    '/static/manifest.json'
];

// Install: Cache shell
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            return cache.addAll(SHELL_ASSETS).catch(() => {
                // Silently skip if any asset fails (server might not be ready)
                console.log('[SW] Some assets failed to cache, skipping.');
            });
        })
    );
    self.skipWaiting();
});

// Activate: Clean old caches
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
        )
    );
    self.clients.claim();
});

// Fetch: Network-first strategy (always try server first, fallback to cache)
self.addEventListener('fetch', event => {
    // Skip non-GET requests (POST /chat, /voice, etc.)
    if (event.request.method !== 'GET') return;

    // Skip API and auth routes
    const url = new URL(event.request.url);
    if (url.pathname.startsWith('/auth/') ||
        url.pathname.startsWith('/chat') ||
        url.pathname.startsWith('/voice') ||
        url.pathname.startsWith('/reset')) {
        return;
    }

    event.respondWith(
        fetch(event.request)
            .then(response => {
                // Clone and cache successful responses
                if (response.status === 200) {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
                }
                return response;
            })
            .catch(() => {
                // Offline: try cache
                return caches.match(event.request);
            })
    );
});
