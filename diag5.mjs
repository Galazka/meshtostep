import { chromium } from 'playwright-core';
const b = await chromium.launch({ channel: 'chrome' });
const ctx = await b.newContext({ serviceWorkers: 'block', locale: 'pl-PL', permissions: [] });
const p = await ctx.newPage();
p.on('pageerror', e => console.log('PAGEERROR', e.message));
await p.goto('https://3dfile.link/zamow', { waitUntil: 'networkidle', timeout: 90000 });
await p.evaluate(() => pickFulfillment('ship'));
await p.waitForFunction(() => document.querySelectorAll('#paczkomatList .pczrow').length > 0, null, { timeout: 60000 });
await p.waitForTimeout(1000);
// obserwuj status w czasie
await p.evaluate(() => {
  window.__trace = [];
  const el = document.getElementById('pczStatus');
  new MutationObserver(() => window.__trace.push(el.innerHTML.slice(0, 60))).observe(el, { childList: true, characterData: true, subtree: true });
});
await p.evaluate(() => autoNearestPaczkomat());
await p.waitForTimeout(8000);
console.log('trace statusow:');
(await p.evaluate(() => window.__trace)).forEach((t, i) => console.log(`  ${i}: "${t}"`));
console.log('koncowy status:', JSON.stringify(await p.locator('#pczStatus').innerText()));
console.log('keepStatus parametr w kodzie:', await p.evaluate(() => searchPaczkomatCity.length));
await b.close();
