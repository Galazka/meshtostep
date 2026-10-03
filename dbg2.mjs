import { chromium } from 'playwright-core';
const b = await chromium.launch({ channel: 'msedge', headless: true });
const ctx = await b.newContext({ viewport: { width: 1400, height: 950 }, serviceWorkers: 'block' });
const p = await ctx.newPage();
p.on('pageerror', e => console.log('PAGEERROR: ' + e.message + '\n' + (e.stack||'').split('\n').slice(0,6).join('\n')));
p.on('console', m => { if (m.type()==='error') console.log('CONSOLE.ERR: ' + m.text().slice(0,200)); });
await p.goto('https://3dfile.link/zamow', { waitUntil: 'networkidle', timeout: 60000 });
await p.waitForTimeout(800);
await p.setInputFiles('#fileInput', 'C:/Users/galaz/Downloads/kapajka3.stl');
await p.waitForTimeout(3500);
const st = await p.evaluate(() => ({
  sum: [...document.querySelectorAll('.acc-s')].map(e=>e.textContent),
  cls: [...document.querySelectorAll('section.acc')].map(e=>e.id+':'+(e.classList.contains('done')?'DONE':(e.classList.contains('empty')?'empty':'-'))),
  it: (typeof CART!=='undefined'&&CART[0]) ? {mat:CART[0].material, matC:!!CART[0]._matChosen, col:CART[0].color, colC:!!CART[0]._colChosen, vol:CART[0].vol} : null,
}));
console.log(JSON.stringify(st,null,1));
await b.close();
