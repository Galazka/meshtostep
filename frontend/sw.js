/* 3dfile.link Service Worker v19
   Strategy:
   - HTML (navigations): NETWORK-FIRST (świeże strony po każdym deployu), cache fallback offline
   - CSS/JS/img/assety: STALE-WHILE-REVALIDATE (szybko z cache, odświeżanie w tle)
   - /api/, /s/, /u/, /e/, /admin: bypass (nigdy nie przechwytujemy)
   - 503 tylko gdy naprawdę offline i nic w cache
*/
const CACHE = '3dfile-v19';
const PRECACHE = ['/manifest.json', '/logo.png?v=83'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(PRECACHE).catch(() => {})));
  self.skipWaiting();
});

self.addEventListener('activate', e => e.waitUntil(
  caches.keys()
    .then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim())
));

self.addEventListener('fetch', e => {
  const req = e.request;
  const u = req.url;
  if (req.method !== 'GET') return;
  if (u.includes('chrome-extension://')) return;
  if (u.includes('/api/')) return;
  if (u.includes('/s/') || u.includes('/u/') || u.includes('/e/')) return;
  if (u.includes('/admin')) return;
  if (!u.startsWith(self.location.origin)) return;

  const url = new URL(u);
  const isHTML = req.mode === 'navigate' ||
                 (req.headers.get('accept') || '').includes('text/html');
  const isAsset = /\.(css|js|mjs|png|jpg|jpeg|svg|webp|woff2?|ico|json)(\?|$)/.test(url.pathname + url.search) ||
                  url.pathname.startsWith('/asset/') || url.pathname.startsWith('/js/') ||
                  url.pathname.startsWith('/vendor/') || url.pathname.startsWith('/css/');

  // HTML: NETWORK-FIRST (świeżość po deploach)
  if (isHTML) {
    e.respondWith(
      fetch(req).then(resp => {
        if (resp && resp.ok) {
          const cl = resp.clone();
          caches.open(CACHE).then(c => c.put(req, cl)).catch(() => {});
        }
        return resp;
      }).catch(() =>
        caches.match(req).then(c => c || new Response(
          '<meta charset="utf-8"><body style="font-family:sans-serif;background:#0B1730;color:#fff;display:grid;place-items:center;min-height:90vh"><div style="text-align:center"><h1 style="font-size:22px">Jesteś offline</h1><p style="color:#8FA3C8">Połącz z internetem i odśwież stronę.</p></div></body>',
          { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8', 'Retry-After': '5' } }
        ))
      )
    );
    return;
  }

  // ASSETY: STALE-WHILE-REVALIDATE
  if (isAsset) {
    e.respondWith(
      caches.match(req).then(cached => {
        const network = fetch(req).then(resp => {
          if (resp && resp.ok) {
            const cl = resp.clone();
            caches.open(CACHE).then(c => c.put(req, cl)).catch(() => {});
          }
          return resp;
        }).catch(() => cached);
        return cached || network;
      })
    );
    return;
  }

  // reszta same-origin: network z cache fallback
  e.respondWith(
    fetch(req).then(resp => resp).catch(() => caches.match(req).then(c => c || new Response('', { status: 503, statusText: 'Offline', headers: { 'Retry-After': '5' } })))
  );
});
