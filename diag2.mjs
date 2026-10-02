import { chromium } from 'playwright-core';
const b = await chromium.launch({ channel: 'chrome' });
const p = await (await b.newContext({ serviceWorkers: 'block', locale: 'pl-PL' })).newPage();
await p.goto('https://3dfile.link/zamow', { waitUntil: 'networkidle', timeout: 90000 });
await p.evaluate(() => { const s = document.getElementById('fShipping'); s.value = 'standard'; toggleShipUI(); });
await p.waitForFunction(() => document.querySelectorAll('#paczkomatList .pczrow').length > 0, null, { timeout: 60000 });
await p.waitForTimeout(3500);
console.log(await p.evaluate(() => {
  const el = document.getElementById('pczMap');
  const r = el.getBoundingClientRect();
  return JSON.stringify({
    pczMapClass: el.className,
    childCount: el.children.length,
    firstChildClass: el.children[0] ? el.className + ' >> ' + el.children[0].className : 'brak',
    rect: { w: Math.round(r.width), h: Math.round(r.height) },
    display: getComputedStyle(el).display,
    visibility: getComputedStyle(el).visibility,
    opacity: getComputedStyle(el).opacity,
    leafletContainerInDom: !!document.querySelector('.leaflet-container'),
    markerCount: document.querySelectorAll('.leaflet-marker-icon').length,
    tileCount: document.querySelectorAll('img.leaflet-tile').length,
    tileLoaded: document.querySelectorAll('img.leaflet-tile-loaded').length,
  }, null, 1);
}));
await b.close();
