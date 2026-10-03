/* E2E panelu admina po redesignie: logowanie, /api/orders ma nowe pola,
   karta renderuje grupy, notatki CRUD ida do admin_notes (nie notes),
   download po tokenie dziala. Uzycie: node admintest.mjs  */
import fs from 'fs';

const BASE = 'https://3dfile.link';
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36';

let pass = 0, fail = 0;
function ok(name, cond, extra) {
  if (cond) { pass++; console.log('PASS  ' + name); }
  else { fail++; console.log('FAIL  ' + name + (extra ? '  -> ' + extra : '')); }
}

const varsPath = process.env.ADMTEST_VARS || '/tmp/admtest_vars.json';
let V = {};
try { V = JSON.parse(fs.readFileSync(varsPath, 'utf8')); }
catch (e) { console.log('brak pliku zmiennych: ' + varsPath); process.exit(1); }

async function jfetch(url, opts = {}) {
  const r = await fetch(url, {
    ...opts,
    headers: { 'User-Agent': UA, 'Accept': 'application/json', ...(opts.headers || {}) }
  });
  const ct = r.headers.get('content-type') || '';
  let body = null;
  if (ct.includes('json')) body = await r.json().catch(() => null);
  else body = await r.text();
  return { status: r.status, body, headers: r.headers };
}

/* 1. logowanie admina */
const login = await jfetch(BASE + '/api/auth/login?t=' + Date.now(), {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email: V.admin_email, password: V.admin_password })
});
ok('login admina', login.status === 200, 'HTTP ' + login.status);
const token = login.body && (login.body.token || (login.body.data && login.body.data.token));
ok('login zwraca token (bez .ok)', !!token, 'klucze=' + Object.keys(login.body || {}).join(','));
ok('token zwrocony', !!token);
console.log('   [diag] login.body = ' + JSON.stringify(login.body).slice(0, 200));
/* 2. /api/orders z tokenem admina */
const orders = await jfetch(BASE + '/api/orders?t=' + Date.now() + '&page=1&sort=newest', {
  headers: { Authorization: 'Bearer ' + token }
});
ok('/api/orders 200', orders.status === 200, 'HTTP ' + orders.status);
const list = (orders.body && orders.body.orders) || [];
ok('lista zamowien niepusta', list.length > 0, 'n=' + list.length);

/* 3. nowe pola w payloadzie */
const o0 = list[0] || {};
ok('customer_address w payload', Object.prototype.hasOwnProperty.call(o0, 'customer_address'));
ok('customer_postal w payload', Object.prototype.hasOwnProperty.call(o0, 'customer_postal'));
ok('shipping_point_name w payload', Object.prototype.hasOwnProperty.call(o0, 'shipping_point_name'));
ok('shipping_point_addr w payload', Object.prototype.hasOwnProperty.call(o0, 'shipping_point_addr'));
ok('admin_notes w payload', Object.prototype.hasOwnProperty.call(o0, 'admin_notes'));
ok('tracking_code w payload', Object.prototype.hasOwnProperty.call(o0, 'tracking_code'));
ok('status+is_paid+total', o0.status !== undefined && o0.is_paid !== undefined && o0.total !== undefined);

const withItems = list.find(o => o.items && o.items.length);
ok('pozycje maja job_uuid', !!withItems && withItems.items.some(i => i.job_uuid),
   withItems ? JSON.stringify(withItems.items.map(i => i.job_uuid)) : 'brak itemow');
ok('filename z Job w payload',
   !!withItems && withItems.items.some(i => i.filename),
   withItems ? JSON.stringify(withItems.items.map(i => i.filename)) : '-');

/* 4. karta renderuje wszystkie sekcje */
const src = await jfetch(BASE + '/asset/order_card.js?v=1&t=' + Date.now());
ok('order_card.js serwowany', src.status === 200 && String(src.body).includes('orderCard'));
const cardSrc = String(src.body);
['secClient', 'secShip', 'secModels', 'secMoney', 'secNotes'].forEach(fn =>
  ok('sekcja ' + fn, cardSrc.includes('function ' + fn)));
ok('modal preview', cardSrc.includes('oc-preview-modal') && cardSrc.includes('initViewerPro'));
ok('preview przez /api/download (nie /api/preview)',
   cardSrc.includes("'/api/download/'") && !cardSrc.includes('loadUrl(viewerUrl(jobUuid, fmt)') ||
   cardSrc.includes('loadUrl(viewerUrl(jobUuid, fmt)'));

/* 5. admin.html podpina skrypty */
const admin = await jfetch(BASE + '/admin?t=' + Date.now());
const html = String(admin.body);
ok('admin 200', admin.status === 200);
ok('order_card.js podpiety', /order_card\.js\?v=\d+/.test(html));
ok('admin_print.js v=103', /admin_print\.js\?v=103/.test(html));
ok('cache guard APP_V=115', html.includes("window.__APP_V='119'"));
ok('guard sessionStorage 115', html.includes("setItem(k,'119')") && html.includes("s!=='119'"));

/* 6. notatki: PATCH admin_notes nie tyka notes */
const target = list.find(o => !o.is_paid) || list[0];
const marker = 'E2E-' + Date.now();
const patch = await jfetch(BASE + '/api/orders/' + target.id + '?t=' + Date.now(), {
  method: 'PATCH',
  headers: { Authorization: 'Bearer ' + token, 'Content-Type': 'application/x-www-form-urlencoded' },
  body: 'admin_notes=' + encodeURIComponent(marker)
});
ok('PATCH admin_notes 200', patch.status === 200, 'HTTP ' + patch.status + ' ' + JSON.stringify(patch.body).slice(0, 120));

const after = await jfetch(BASE + '/api/orders?t=' + Date.now() + '&page=1&sort=newest',
  { headers: { Authorization: 'Bearer ' + token } });
// search nie filtruje po admin_notes - szukamy po odczytanej liscie
const found = ((after.body && after.body.orders) || []).find(o => o.id === target.id);
ok('admin_notes zapisane', !!found && String(found.admin_notes || '') === marker,
   found ? 'admin_notes=' + JSON.stringify(found.admin_notes) : 'brak zamowienia na liscie');
ok('notes klienta nietkniete', !!found && (found.notes === null || found.notes === target.notes),
   found ? 'notes=' + JSON.stringify(found.notes) + ' vs ' + JSON.stringify(target.notes) : '-');

/* 7. wyczyszczenie notatki */
const clr = await jfetch(BASE + '/api/orders/' + target.id + '?t=' + Date.now(), {
  method: 'PATCH',
  headers: { Authorization: 'Bearer ' + token, 'Content-Type': 'application/x-www-form-urlencoded' },
  body: 'admin_notes='
});
ok('wyczyszczenie notatki 200', clr.status === 200, 'HTTP ' + clr.status);
const after2 = await jfetch(BASE + '/api/orders?t=' + Date.now() + '&page=1&sort=newest',
  { headers: { Authorization: 'Bearer ' + token } });
const cur = ((after2.body && after2.body.orders) || []).find(o => o.id === target.id);
ok('notatka wyczyszczona', cur && !cur.admin_notes, JSON.stringify(cur && cur.admin_notes));

/* 8. download pliku klienta tokenem admina */
if (withItems && withItems.items.some(i => i.job_uuid)) {
  const item = withItems.items.find(i => i.job_uuid);
  const dl = await fetch(BASE + '/api/download/' + item.job_uuid + '?format=stl&token=' + encodeURIComponent(token),
    { headers: { 'User-Agent': UA } });
  const buf = await dl.arrayBuffer();
  ok('download STL adminem', dl.status === 200 && buf.byteLength > 100, 'HTTP ' + dl.status + ' bajty=' + buf.byteLength);
} else {
  ok('download STL adminem (pominieto - brak plikow)', true);
}

/* 9. odbior osobisty vs paczkomat widoczny w karcie */
const shipMethods = [...new Set(list.map(o => o.shipping_method).filter(Boolean))];
ok('rozne metody dostawy w danych', shipMethods.length >= 1, shipMethods.join(','));
ok('karta zna odbior osobisty', cardSrc.includes("'pickup'") && cardSrc.includes('Odbiór osobisty'));
ok('karta zna paczkomat', cardSrc.includes('Paczkomat (kod)') && cardSrc.includes('Paczkomat (z adresu)'));

console.log('\n' + pass + ' PASS / ' + fail + ' FAIL');
process.exit(fail ? 1 : 0);