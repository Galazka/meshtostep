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
await p.screenshot({ path: process.env.TMPDIR + '/zam_desk.png', fullPage: false });
await m.screenshot({ path: process.env.TMPDIR + '/zam_mob.png', fullPage: false });

console.log('BLEDY JS (' + errs.length + '):');
errs.slice(0, 8).forEach(e => console.log('  ' + e));
await b.close();