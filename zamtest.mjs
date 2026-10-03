import { chromium } from 'playwright-core';
import { readFileSync } from 'fs';

const exe = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const b = await chromium.launch({ executablePath: exe, headless: true });
const ctx = await b.newContext({ viewport: { width: 1280, height: 1000 }, serviceWorkers: 'block' });
const p = await ctx.newPage();
const errs = [];
p.on('pageerror', e => errs.push('PAGEERR ' + e.message));
p.on('console', m => { if (m.type() === 'error') errs.push('CONSOLE ' + m.text()); });

// desktop
await p.goto('https://3dfile.link/zamow?t=' + Date.now(), { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(3500);

const desk = await p.evaluate(() => {
  const btns = [...document.querySelectorAll('button, a.btn, .paybtn')]
    .filter(e => /zamów i zapłać|zapłać/i.test(e.textContent || '') && e.offsetParent !== null);
  const sb = document.getElementById('submitBtn');
  const cb = document.querySelector('#ctaBar button');
  return {
    wWidocznych: btns.length,
    submitBtn: sb ? { widoczny: sb.offsetParent !== null, tekst: sb.textContent.trim() } : null,
    ctaBar: cb ? { widoczny: cb.offsetParent !== null, tekst: cb.textContent.trim() } : null,
    poziomyScroll: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  };
});
console.log('DESKTOP 1280:', JSON.stringify(desk, null, 1));

// mobile
const m = await ctx.newPage();
await m.setViewportSize({ width: 390, height: 844 });
await m.goto('https://3dfile.link/zamow?t=' + Date.now(), { waitUntil: 'domcontentloaded' });
await m.waitForTimeout(3000);
const mob = await m.evaluate(() => {
  const sb = document.getElementById('submitBtn');
  const cb = document.querySelector('#ctaBar button');
  const widoczne = [...document.querySelectorAll('button, .paybtn')]
    .filter(e => /zamów i zapłać|zapłać/i.test(e.textContent || '') && e.offsetParent !== null);
  return {
    ileWidocznych: widoczne.length,
    submitBtnWidoczny: sb ? sb.offsetParent !== null : null,
    ctaBarWidoczny: cb ? cb.offsetParent !== null : null,
    poziomyScroll: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  };
});
console.log('MOBILE 390:', JSON.stringify(mob, null, 1));

// z jednym modelem w koszyku -> ile CTA widocznych
await p.setViewportSize({ width: 1280, height: 1000 });
await p.waitForTimeout(800);
const fi = p.locator('input[type=file]').first();
if (await fi.count()) {
  await fi.setInputFiles('C:/Users/galaz/Downloads/kapajka3.stl');
  await p.waitForTimeout(6000);
}
const poKoszyku = await p.evaluate(() => {
  const widoczne = [...document.querySelectorAll('button, .paybtn')]
    .filter(e => /zamów i zapłać|zapłać/i.test(e.textContent || '') && e.offsetParent !== null);
  return {
    ileWidocznych: widoczne.length,
    teksty: widoczne.map(e => e.textContent.trim().slice(0, 40)),
  };
});
console.log('PO KOSZYKU (desktop):', JSON.stringify(poKoszyku, null, 1));
await p.screenshot({ path: 'C:/Users/galaz/AppData/Local/hermes/cache/scratch/zam_full.png', fullPage: true });
await m.screenshot({ path: 'C:/Users/galaz/AppData/Local/hermes/cache/scratch/zam_mobfull.png', fullPage: true });

const przycisk = await p.evaluate(() => {
  const b = document.getElementById('submitBtn');
  const r = b ? b.getBoundingClientRect() : null;
  return { istnieje: !!b, tekst: b ? b.textContent.trim() : null, disabled: b ? b.disabled : null,
           wWidoku: r ? (r.top >= 0 && r.bottom <= innerHeight) : null, wysokosc: r ? Math.round(r.height) : null };
});
console.log('CTA w podsumowaniu:', JSON.stringify(przycisk));
// pozycja vs toolbar w podgladzie
// Czy JEST realnie tekst pod viewportem? Sprawdz elementy pod toolboxem
const podTB = await p.evaluate(() => {
  const tb = document.querySelector('.vptools, #vpTools, .vp-bar, .preview-box > div:first-child');
  // znajdz wszystkie elementy tekstowe ktore moga byc pod canvasem
  const box = document.querySelector('.preview-box');
  if (!box) return 'brak preview-box';
  const br = box.getBoundingClientRect();
  const canvas = box.querySelector('canvas');
  const cr = canvas ? canvas.getBoundingClientRect() : null;
  const wynik = { box: [Math.round(br.left), Math.round(br.top), Math.round(br.right), Math.round(br.bottom)] };
  if (cr) wynik.canvas = [Math.round(cr.left), Math.round(cr.top), Math.round(cr.right), Math.round(cr.bottom)];
  wynik.canvasPozaBox = cr ? (cr.right > br.right + 1 || cr.bottom > br.bottom + 1) : null;
  // elementy z overflow widoczne przy lewej krawedzi canvasa
  wynik.overflowX = box.scrollWidth - box.clientWidth;
  wynik.overflowY = box.scrollHeight - box.clientHeight;
  // czy canvas ma tlo (nieprzezroczyste) - jak tak, tekst pod nim nie widac
  wynik.canvasTlo = canvas ? getComputedStyle(canvas).backgroundColor : null;
  wynik.boxOverflow = getComputedStyle(box).overflow;
  // ile elementow z pozycja absolute wewnatrz box
  wynik.absolutes = [...box.querySelectorAll('*')].filter(e => getComputedStyle(e).position === 'absolute')
    .map(e => ({ cls: e.className, txt: (e.textContent||'').trim().slice(0,25) })).slice(0,12);
  return wynik;
});
console.log('PODGLAD / overflow:', JSON.stringify(podTB, null, 1));

const overlap = await p.evaluate(() => {
  const tb = document.querySelector('.vp-tools, .preview-box .tools, [class*=tool]');
  const sb = document.getElementById('submitBtn');
  if (!tb || !sb) return 'brak elementu';
  const a = tb.getBoundingClientRect(), b = sb.getBoundingClientRect();
  const ov = !(b.right < a.left || b.left > a.right || b.bottom < a.top || b.top > a.bottom);
  return { overlap: ov, tools: [Math.round(a.left), Math.round(a.top), Math.round(a.right), Math.round(a.bottom)],
           btn: [Math.round(b.left), Math.round(b.top), Math.round(b.right), Math.round(b.bottom)] };
});
console.log('Nakladanie toolbar vs CTA:', JSON.stringify(overlap));
// admin: viewer_pro tez tam uzywany
const adm = await ctx.newPage();
await adm.goto('https://3dfile.link/admin?t=' + Date.now(), { waitUntil: 'domcontentloaded' });
await adm.waitForTimeout(3000);
const admBox = await adm.evaluate(() => {
  const c = document.querySelector('canvas');
  if (!c) return 'brak canvasa';
  const host = c.parentElement;
  const cr = c.getBoundingClientRect(), hr = host.getBoundingClientRect();
  return { poza: cr.right > hr.right + 1 || cr.bottom > hr.bottom + 1 || cr.left < hr.left - 1,
           canvas: [Math.round(cr.left), Math.round(cr.right)], host: [Math.round(hr.left), Math.round(hr.right)] };
});
console.log('ADMIN viewer canvas:', JSON.stringify(admBox));

console.log('BLEDY JS (' + errs.length + '):');
errs.slice(0, 8).forEach(e => console.log('  ' + e));
await b.close();