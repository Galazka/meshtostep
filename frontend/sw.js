/* 3dfile.link Service Worker v22
   Strategy (lekcja: stale-while-revalidate na .js serwował STARY niebieski viewer):
   - HTML (navigations): NETWORK-FIRST, cache tylko jako fallback offline
   - KOD (/js/, /asset/, /css/, *.js|*.mjs|*.css): NETWORK-FIRST — nigdy nie oddaj starego kodu
   - /vendor/ (three.js, wersjonowane pliki) + obrazy/fonty: STALE-WHILE-REVALIDATE
   - /api/, /s/, /u/, /e/, /admin: bypass
   - bump CACHE → activate kasuje stare cache u każdego klienta
*/
const CACHE = '3dfile-v23';
const PRECACHE = ['/manifest.json'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(PRECACHE).catch(() => {})));
  self.skipWaiting();
});

self.addEventListener('activate', e => e.waitUntil(
  caches.keys()
    .then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim())
));

function putInCache(req, resp) {
  if (resp && resp.ok && resp.type !== 'opaque') {
    const cl = resp.clone();
    caches.open(CACHE).then(c => c.put(req, cl)).catch(() => {});
  }
  return resp;
}

const OFFLINE_HTML = '<meta charset="utf-8"><body style="font-family:sans-serif;background:#0B1730;color:#fff;display:grid;place-items:center;min-height:90vh"><div style="text-align:center"><h1 style="font-size:22px">Jesteś offline</h1><p style="color:#8FA3C8">Połącz z internetem i odśwież stronę.</p></div></body>';

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
  const p = url.pathname;
  const isHTML = req.mode === 'navigate' ||
                 (req.headers.get('accept') || '').includes('text/html');
  const isCode = p.startsWith('/js/') || p.startsWith('/asset/') || p.startsWith('/css/') ||
                 /\.(js|mjs|css)(\?|$)/.test(p);
  const isVendor = p.startsWith('/vendor/');
  const isMedia = /\.(png|jpe?g|svg|webp|gif|ico|woff2?|ttf)(\?|$)/.test(p);

  // HTML + KOD: zawsze sieć (świeżość po deployu), cache tylko jako ratunek offline
  if (isHTML || isCode) {
    e.respondWith(
      fetch(req).then(resp => putInCache(req, resp)).catch(() =>
        caches.match(req).then(c => c || (isHTML
          ? new Response(OFFLINE_HTML, { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8', 'Retry-After': '5' } })
          : new Response('', { status: 503, statusText: 'Offline', headers: { 'Retry-After': '5' } })))
      )
    );
    return;
  }

  // /vendor/ + obrazy/fonty: szybko z cache, odświeżanie w tle
  if (isVendor || isMedia) {
    e.respondWith(
      caches.match(req).then(cached => {
        const network = fetch(req).then(resp => putInCache(req, resp)).catch(() => cached);
        return cached || network;
      })
    );
    return;
  }

  e.respondWith(
    fetch(req).then(resp => resp).catch(() => caches.match(req).then(c => c || new Response('', { status: 503, statusText: 'Offline', headers: { 'Retry-After': '5' } })))
  );
});
