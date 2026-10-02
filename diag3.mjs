import { chromium } from 'playwright-core';
const b = await chromium.launch({ channel: 'chrome' });
const p = await (await b.newContext({ serviceWorkers: 'block', locale: 'pl-PL' })).newPage();
await p.goto('https://3dfile.link/zamow', { waitUntil: 'networkidle', timeout: 90000 });
await p.evaluate(() => { const s = document.getElementById('fShipping'); s.value = 'standard'; toggleShipUI(); });
await p.waitForFunction(() => document.querySelectorAll('#paczkomatList .pczrow').length > 0, null, { timeout: 60000 });
await p.waitForTimeout(2500);
console.log(await p.evaluate(() => {
  const out = [];
  let e = document.getElementById('pczMap');
  while (e && e !== document.documentElement) {
    const cs = getComputedStyle(e);
    const r = e.getBoundingClientRect();
    out.push(`${e.tagName}${e.id ? '#' + e.id : ''}${e.className ? '.' + String(e.className).split(' ').slice(0,2).join('.') : ''} | display=${cs.display} | inlineDisplay=${e.style.display || '-'} | w=${Math.round(r.width)} h=${Math.round(r.height)}`);
    e = e.parentElement;
  }
  return out.join('\n');
}));
await b.close();
