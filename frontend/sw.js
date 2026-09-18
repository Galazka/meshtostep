const CACHE = '3dfile-v17';
const ASSETS = ['/manifest.json', '/logo.png?v=2'];

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
  if (e.request.method !== 'GET') return;
  if (u.includes('chrome-extension://')) return;
  if (u.includes('/api/')) return;
  if (u.includes('/s/') || u.includes('/u/') || u.includes('/e/')) return;
  if (u.includes('/admin')) return;
  if (!u.startsWith(self.location.origin)) return;
  // JS/vendor: network-first (fresh after deploy), cache fallback.
  // IMPORTANT: on network error with no cache, return a REAL non-2xx status
  // (503) with empty body — NOT an empty 200 — because an empty body parsed as
  // an ES module throws "Invalid or unexpected token" and kills the whole
  // module chain (showModal/doAuth stay undefined -> broken UI/buttons).
  if (u.includes('/js/') || u.includes('/vendor/')) {
    e.respondWith(fetch(e.request).then(resp => {
      if (resp.ok) {
        const cl = resp.clone();
        caches.open(CACHE).then(c => c.put(e.request, cl)).catch(()=>{});
      }
      return resp;
    }).catch(() => caches.match(e.request).then(cached => {
      if (cached) return cached;
      return new Response('', {status: 503, statusText: 'Retry later', headers: {'Retry-After': '3'}});
    })));
    return;
  }
  e.respondWith(caches.match(e.request).then(cached => {
    if (cached) return cached;
    return fetch(e.request).then(resp => {
      if (resp.ok) {
        const ct = resp.headers.get('content-type') || '';
        if (!ct.includes('text/html')) {
          const cl = resp.clone();
          caches.open(CACHE).then(c => c.put(e.request, cl)).catch(()=>{});
        }
      }
      return resp;
    }).catch(() => new Response('', {status: 503, statusText: 'Retry later', headers: {'Retry-After': '3'}}));
  }));
});
