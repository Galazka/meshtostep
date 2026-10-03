/* Wizualny test panelu admina: logowanie, render kart, rozwijanie sekcji,
   notatki, podglad 3D, brak overflow na mobile.
   Uzycie: ADMTEST_VARS=... node adminvisual.mjs  */
import fs from 'fs';
import { chromium } from 'playwright-core';

const BASE = 'https://3dfile.link';
let pass = 0, fail = 0;
const ok = (n, c, x) => c ? (pass++, console.log('PASS  ' + n))
                           : (fail++, console.log('FAIL  ' + n + (x ? '  -> ' + x : '')));

const V = JSON.parse(fs.readFileSync(process.env.ADMTEST_VARS, 'utf8'));
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ serviceWorkers: 'block', viewport: { width: 1440, height: 950 } });
const page = await ctx.newPage();

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36';
async function jfetch(url, opts = {}) {
  const r = await fetch(url, { ...opts,
    headers: { 'User-Agent': UA, 'Accept': 'application/json', ...(opts.headers || {}) } });
  const ct = r.headers.get('content-type') || '';
  return { status: r.status, body: ct.includes('json') ? await r.json().catch(() => null) : await r.text() };
}
let token = '';
const jsErrs = [];
page.on('pageerror', e => jsErrs.push(String(e.message).slice(0, 140)));
page.on('console', m => { if (m.type() === 'error') jsErrs.push('console: ' + m.text().slice(0, 140)); });

await page.goto(BASE + '/admin?t=' + Date.now(), { waitUntil: 'domcontentloaded' });

// zaloguj przez UI (jesli juz sesja, przejdzie)
const hasLogin = await page.locator('input[type=password]').count();
if (hasLogin) {
  await page.locator('input[type=email]').first().fill(V.admin_email);
  await page.locator('input[type=password]').first().fill(V.admin_password);
  await page.locator('button[type=submit], #loginBtn, button:has-text("Zaloguj")').first().click();
  await page.waitForTimeout(2500);
}
// token do weryfikacji notatek w API
const lg = await jfetch(BASE + '/api/auth/login?t=' + Date.now(), {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email: V.admin_email, password: V.admin_password }) });
token = (lg.body && (lg.body.token || (lg.body.data && lg.body.data.token))) || '';
ok('token admina do API', !!token);



// wejdz na zakladke zamowien
const clicked = await page.evaluate(() => {
  const t = document.querySelector('#tab-orders, [data-tab="orders"], a[href="#orders"]');
  if (t) { t.click(); return true; }
  if (typeof window.switchPrintTab === 'function') { window.switchPrintTab('orders'); return true; }
  return false;
});
await page.waitForTimeout(2500);
ok('zakladka zamowien', clicked);

const cards = await page.locator('.oc-card').count();
ok('karty zamowien wyrenderowane', cards > 0, 'n=' + cards);

// sesja: login ukryty + realne dane z API (karty = dane, nie szkielet)
const pwVisible = await page.locator('input[type=password]').first().isVisible().catch(() => false);
const realData = await page.evaluate(() => {
  const c = document.querySelector('.oc-card');
  return c ? {
    hasId: /#\d+/.test(c.textContent),
    hasMail: /@/.test(c.textContent),
    len: c.textContent.length
  } : null;
});
console.log('   [diag] login widoczny=' + pwVisible + ' dane=' + JSON.stringify(realData));
ok('sesja admina (login ukryty)', !pwVisible);
ok('karty maja realne dane klienta', !!realData && realData.hasId && realData.hasMail,
   JSON.stringify(realData));

const stats = await page.evaluate(() => {
  const list = document.querySelector('.oc-list');
  const first = document.querySelector('.oc-card');
  const secs = first ? [...first.querySelectorAll('details.oc-sec')] : [];
  const titles = secs.map(d => (d.querySelectorAll('summary span')[1] || {}).textContent || '');
  return {
    listTag: list ? list.tagName : 'BRAK',
    firstTag: first ? first.tagName : 'BRAK',
    secs: titles,
    sectionsCount: secs.length,
    openCount: secs.filter(d => d.open).length,
    orderNo: first ? ((first.querySelector('div > span') || {}).textContent || '') : '',
    overflowInCard: first ? first.scrollWidth - first.clientWidth : 0,
    cellCount: first ? first.querySelectorAll('div').length : 0
  };
});
console.log('   [diag] ' + JSON.stringify(stats));
ok('karta to <article> (nie <tr> tabeli)', stats.firstTag === 'ARTICLE', stats.firstTag);
ok('lista .oc-list to <div>', stats.listTag === 'DIV', stats.listTag);
ok('5 sekcji w karcie', stats.sectionsCount === 5, 'n=' + stats.sectionsCount + ' ' + stats.secs.join('/'));
ok('tytuly sekcji kompletne', ['Klient','Dostawa','Modele','Koszty','Notatki'].every(t => stats.secs.includes(t)), stats.secs.join(','));
ok('numer zamowienia widoczny', /^#\d+$/.test(stats.orderNo.trim()), 'got=' + stats.orderNo);
ok('brak poziomego overflow w karcie', stats.overflowInCard <= 1, 'overflow=' + stats.overflowInCard);

const collapseFlow = await page.evaluate(() => {
  const secs = [...document.querySelectorAll('.oc-card details.oc-sec')];
  const closed = secs.filter(d => !d.open);
  const target = secs.find(d => !d.open);
  if (!target) return { noClosed: true, countClosed: 0 };
  const before = target.open;
  target.querySelector('summary').click();
  return { countClosed: closed.length, before, after: target.open,
           title: (target.querySelectorAll('summary span')[1] || {}).textContent };
});
console.log('   [diag] collapse: ' + JSON.stringify(collapseFlow));
ok('czesc sekcji zwinieta na starcie', collapseFlow.countClosed > 0, JSON.stringify(collapseFlow));
ok('sekcja rozwija sie po kliknieciu', collapseFlow.after === true, JSON.stringify(collapseFlow));

// notatki: edycja + zapis + wyczyszczenie (inline w sekcji, nie modal)
const noteFlow = await page.evaluate(async () => {
  const card = document.querySelector('.oc-card');
  if (!card) return { err: 'brak karty' };
  const ta = card.querySelector('textarea[id^="an_"]');
  if (!ta) return { err: 'brak textarea', ids: [...card.querySelectorAll('textarea')].map(t=>t.id) };
  const oid = ta.id.replace('an_', '');
  const sec = ta.closest('details.oc-sec');
  if (!sec.open) { sec.querySelector('summary').click(); await new Promise(r=>setTimeout(r,250)); }
  const marker = 'PW-test-' + Date.now();
  ta.value = marker;
  const save = card.querySelector('[data-notes-save]');
  if (!save) return { err: 'brak przycisku zapisu' };
  save.click();
  await new Promise(r => setTimeout(r, 1800));
  const persisted = ta.value;
  const hint = (card.querySelector('[data-notes-save]') || {}).parentElement;
  const hintTxt = hint ? hint.textContent.replace(/\s+/g,' ').trim() : '';
  return { oid, marker, persisted, hintTxt, err: null };
});
console.log('   [diag] notes: ' + JSON.stringify(noteFlow));
ok('textarea notatek w karcie', noteFlow.err === null, noteFlow.err || '');
ok('przycisk zapisu notatki', noteFlow.err === null);

const noteApi = await jfetch(BASE + '/api/orders?t=' + Date.now() + '&page=1&sort=newest',
  { headers: { Authorization: 'Bearer ' + token } });
const noteRow = ((noteApi.body && noteApi.body.orders) || []).find(o => o.id === Number(noteFlow.oid));
ok('notatka zapisana w API (admin_notes)',
   !!noteRow && noteFlow.marker && String(noteRow.admin_notes || '') === noteFlow.marker,
   noteRow ? 'admin_notes=' + JSON.stringify(noteRow.admin_notes) : 'brak w liscie');

// wyczyszczenie przez UI
// clear uzywa confirm() - trzeba zaakceptowac dialog
page.once('dialog', d => d.accept());
const clearFlow = await page.evaluate(async () => {
  const card = document.querySelector('.oc-card');
  const clr = card.querySelector('[data-notes-clear]');
  if (!clr) return { err: 'brak przycisku wyczysczenia' };
  clr.click();
  await new Promise(r => setTimeout(r, 2200));
  const ta = card.querySelector('textarea[id^="an_"]');
  return { val: ta ? ta.value : null, err: null };
});
console.log('   [diag] clear: ' + JSON.stringify(clearFlow));
ok('wyczyszczenie notatki przez UI', clearFlow.err === null && !clearFlow.val,
   JSON.stringify(clearFlow));

// podglad 3D przed pobraniem
const pv = await page.evaluate(async () => {
  const card = document.querySelector('.oc-card');
  const btn = card && card.querySelector('[data-preview]');
  if (!btn) return { err: 'brak przycisku podgladu', attrs: [...card.querySelectorAll('[data-fmt]')].length };
  btn.click();
  await new Promise(r => setTimeout(r, 4000));
  const modal = document.querySelector('#oc-preview-modal');
  return {
    err: null,
    display: modal ? getComputedStyle(modal).display : 'BRAK',
    hasCanvas: !!(modal && modal.querySelector('canvas')),
    title: modal ? (modal.querySelector('#oc-pv-title')||{}).textContent : '',
    bodyLen: modal ? (modal.querySelector('#oc-pv-body')||{childNodes:[]}).childNodes.length : 0
  };
});
console.log('   [diag] preview: ' + JSON.stringify(pv));
ok('modal podgladu otwiera sie', pv.display === 'flex', 'display=' + pv.display);
ok('viewer renderuje model (canvas)', pv.hasCanvas === true, 'canvas=' + pv.hasCanvas);

// ESC zamyka i czysci canvas
const closed = await page.evaluate(async () => {
  document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
  await new Promise(r => setTimeout(r, 500));
  const modal = document.querySelector('#oc-preview-modal');
  const body = modal && modal.querySelector('#oc-pv-body');
  return {
    display: modal ? getComputedStyle(modal).display : 'BRAK',
    leftovers: body ? body.childNodes.length : -1
  };
});
console.log('   [diag] po ESC: ' + JSON.stringify(closed));
ok('ESC zamyka preview', closed.display === 'none', 'display=' + closed.display);
ok('canvas posprzatany po zamknieciu', closed.leftovers === 0, 'leftovers=' + closed.leftovers);


// mobile: 390px bez overflow
const m = await ctx.newPage();
await m.goto(BASE + '/admin?t=' + Date.now(), { waitUntil: 'domcontentloaded' });
await m.setViewportSize({ width: 390, height: 844 });
await m.waitForTimeout(3000);
const mf = await m.evaluate(() => ({
  ov: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  vw: document.documentElement.clientWidth
}));
console.log('   [diag] mobile 390: ' + JSON.stringify(mf));
ok('brak poziomego overflow na mobile', mf.ov <= 0, 'overflow=' + mf.ov);
await m.screenshot({ path: 'admin-mobile.png', fullPage: false });
await page.screenshot({ path: 'admin-desktop.png', fullPage: false });
console.log('   [diag] screenshoty: admin-desktop.png admin-mobile.png');

// CSP violacje GTM/clarity to inny temat - liczymy tylko wlasne bledy
const csp = jsErrs.filter(e => /Content Security Policy/.test(e));
const own  = jsErrs.filter(e => !/Content Security Policy/.test(e));
console.log('   [diag] CSP (GTM/clarity, nie panel): ' + csp.length + ' | wlasne bledy: ' + own.length);
ok('brak wlasnych bledow JS', own.length === 0, own.slice(0, 3).join(' | '));
console.log('   [diag] CSP: ' + csp.slice(0,2).map(e => e.slice(0,150)).join(' || '));

await browser.close();
console.log('\n' + pass + ' PASS / ' + fail + ' FAIL');
process.exit(fail ? 1 : 0);