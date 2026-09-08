const CACHE = '3dhosty-v4';
const ASSETS = ['/', '/manifest.json', '/logo.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)).catch(()=>{}));
  self.skipWaiting();
});
self.addEventListener('activate', e => e.waitUntil(
  caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
  .then(() => self.clients.claim())
));
self.addEventListener('fetch', e => {
  const u = e.request.url;
  // Skip non-GET, cross-origin, API, chrome-extension, share/profile/embed pages
  if (e.request.method !== 'GET') return;
  if (u.includes('chrome-extension://')) return;
  if (u.includes('/api/')) return;
  if (u.includes('/s/') || u.includes('/u/') || u.includes('/e/')) return;
  if (u.includes('/admin')) return;
  if (!u.startsWith(self.location.origin)) return;
  e.respondWith(caches.match(e.request).then(cached => {
    if (cached) return cached;
    return fetch(e.request).then(resp => {
      if (resp.ok) {
        const cl = resp.clone();
        caches.open(CACHE).then(c => c.put(e.request, cl));
      }
      return resp;
    }).catch(() => cached);
  }));
});
