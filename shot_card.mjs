import fs from 'fs';
import { chromium } from 'playwright-core';
const BASE = 'https://3dfile.link';
const V = JSON.parse(fs.readFileSync(process.env.ADMTEST_VARS, 'utf8'));
const b = await chromium.launch({ headless: true });
const c = await b.newContext({ serviceWorkers: 'block', viewport: { width: 1500, height: 1000 } });
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

// rozwin WSZYSTKIE sekcje w pierwszej karcie + dopisz brakujace pola
await p.evaluate(() => {
  const card = document.querySelector('.oc-card');
  card.querySelectorAll('details.oc-sec').forEach(d => { d.open = true; });
  card.scrollIntoView();
});
await p.waitForTimeout(600);
const card = p.locator('.oc-card').first();
await card.screenshot({ path: 'card-full.png' });

// podglad 3D
await p.evaluate(() => {
  const btn = document.querySelector('.oc-card [data-preview]');
  if (btn) btn.click();
});
await p.waitForTimeout(4500);
await p.screenshot({ path: 'preview-modal.png' });
console.log('ok: card-full.png preview-modal.png');
await b.close();