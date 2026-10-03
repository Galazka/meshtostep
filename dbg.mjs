import { chromium } from 'playwright-core';
const errs = [];
const b = await chromium.launch({ channel: 'msedge', headless: true });
const ctx = await b.newContext({ viewport: { width: 1400, height: 950 }, serviceWorkers: 'block' });
const p = await ctx.newPage();
p.on('console', m => console.log('  [console.' + m.type() + '] ' + m.text().slice(0, 150)));
p.on('pageerror', e => console.log('  [PAGEERROR] ' + e.message.slice(0, 200)));

await p.goto('https://3dfile.link/zamow', { waitUntil: 'networkidle', timeout: 60000 });
await p.waitForTimeout(800);

console.log('przed upload:');
console.log('  ' + JSON.stringify(await p.evaluate(() => ({
  open: [...document.querySelectorAll('section.acc.open')].map(e => e.id),
  lastDone: typeof _lastStepDone !== 'undefined' ? _lastStepDone : 'undef',
  done1: _stepDone ? _stepDone(1) : 'nofn',
}))));

await p.setInputFiles('#fileInput', 'C:/Users/galaz/Downloads/kapajka3.stl');
for (const t of [800, 1500, 2500, 4000]) {
  await p.waitForTimeout(t === 800 ? 800 : 1000);
  const st = await p.evaluate(() => ({
    open: [...document.querySelectorAll('section.acc.open')].map(e => e.id),
    cart: typeof CART !== 'undefined' ? CART.length : -1,
    lastDone: typeof _lastStepDone !== 'undefined' ? JSON.parse(JSON.stringify(_lastStepDone)) : 'undef',
    d1: _stepDone(1), d2: _stepDone(2),
    sum1: (document.getElementById('accs1') || {}).textContent,
  }));
  console.log(`po ${t}ms: ` + JSON.stringify(st));
}
console.log('bledy: ' + errs.length);
await b.close();