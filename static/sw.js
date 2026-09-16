const CACHE_NAME = 'adb-v1';
const STATIC_ASSETS = [
  '/static/css/app.css',
  '/static/js/app.js',
  '/static/manifest.json',
];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then(c => c.addAll(STATIC_ASSETS)));
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (url.pathname.startsWith('/api/') || event.request.method !== 'GET') return;

  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(event.request).then(hit => hit || fetch(event.request))
    );
    return;
  }
});
