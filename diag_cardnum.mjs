import fs from 'fs';
import { chromium } from 'playwright-core';
const BASE = 'https://3dfile.link';
const V = JSON.parse(fs.readFileSync(process.env.ADMTEST_VARS, 'utf8'));
const b = await chromium.launch({ headless: true });
const c = await b.newContext({ serviceWorkers: 'block', viewport: { width: 1440, height: 950 } });
const p = await c.newPage();
await p.goto(BASE + '/admin?t=' + Date.now(), { waitUntil: 'domcontentloaded' });
if (await p.locator('input[type=password]').count()) {
  await p.locator('input[type=email]').first().fill(V.admin_email);
  await p.locator('input[type=password]').first().fill(V.admin_password);
  await p.locator('button[type=submit], #loginBtn').first().click();
  await p.waitForTimeout(2500);
}
await p.evaluate(() => { const t=document.querySelector('#tab-orders,[data-tab="orders"],a[href="#orders"]'); if(t) t.click(); else window.switchPrintTab && window.switchPrintTab('orders'); });
await p.waitForTimeout(2500);
const out = await p.evaluate(() => {
  const cards = [...document.querySelectorAll('.oc-card')];
  return cards.slice(0, 3).map(c => {
    const firstSpan = c.querySelector('div > span');
    return {
      idAttr: c.getAttribute('data-id'),
      headSpan: firstSpan ? firstSpan.textContent : 'BRAK',
      firstHash: (c.textContent.match(/#\d+/) || ['BRAK'])[0],
      textStart: c.textContent.replace(/\s+/g, ' ').slice(0, 260)
    };
  });
});
console.log(JSON.stringify(out, null, 2));
await b.close();