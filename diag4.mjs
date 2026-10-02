import { chromium } from 'playwright-core';
const b = await chromium.launch({ channel: 'chrome' });
const ctx = await b.newContext({
  serviceWorkers: 'block', locale: 'pl-PL',
  geolocation: { latitude: 54.3520, longitude: 18.6466 },
  permissions: [],
});
const p = await ctx.newPage();
p.on('pageerror', e => console.log('PAGEERROR', e.message));
p.on('console', m => { if (m.type()==='error') console.log('CONSOLE', m.text().slice(0,120)); });
await p.goto('https://3dfile.link/zamow', { waitUntil: 'networkidle', timeout: 90000 });
await p.evaluate(() => pickFulfillment('ship'));
await p.waitForFunction(() => document.querySelectorAll('#paczkomatList .pczrow').length > 0, null, { timeout: 60000 });
await p.waitForTimeout(1500);
const geo = await p.evaluate(() => new Promise(res => {
  navigator.geolocation.getCurrentPosition(
    pos => res('OK ' + pos.coords.latitude + ',' + pos.coords.longitude),
    err => res('ERR ' + err.code + ' ' + err.message), { enableHighAccuracy: true, timeout: 9000 });
}));
console.log('geolocation bezposrednio:', geo);
await p.click('text=Wybierz najbliższy automatycznie');
await p.waitForTimeout(7000);
console.log('status :', await p.locator('#pczStatus').innerText());
console.log('name   :', JSON.stringify(await p.inputValue('#fPaczkomatName')));
console.log('items  :', await p.evaluate(() => PCZ_ITEMS.length));
console.log('btn txt:', await p.evaluate(() => Array.from(document.querySelectorAll('button')).filter(b=>/najbli/i.test(b.textContent)).map(b=>b.textContent.trim()+' vis='+(b.offsetParent!==null))));
await b.close();
