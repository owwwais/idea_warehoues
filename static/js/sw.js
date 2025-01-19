const CACHE_NAME = 'ideas-warehouse-v1';
const ASSETS_TO_CACHE = [
  '/',
  '/static/css/style.css',
  '/static/js/main.js',
  '/static/images/hero-illustration.svg',
  '/static/avatars/default.png',
  '/offline.html',
  '/static/manifest.json',
  '/static/icons/icon-192x192.png',
  '/static/icons/icon-512x512.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(ASSETS_TO_CACHE))
  );
});

self.addEventListener('fetch', (event) => {
  event.respondWith(
    fetch(event.request)
      .catch(() => {
        return caches.match(event.request)
          .then((response) => {
            if (response) {
              return response;
            }
            if (event.request.mode === 'navigate') {
              return caches.match('/offline.html');
            }
            return new Response('', {
              status: 408,
              statusText: 'Request timed out.'
            });
          });
      })
  );
}); 