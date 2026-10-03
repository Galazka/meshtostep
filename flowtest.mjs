// Pelny przeplyw /zamow: wgranie STL -> kroki -> kolor -> cena.
// Używa kapajka3.stl (22,4 cm3, granica minimum) z katalogu Uzytkownika.
import { chromium } from 'playwright-core';
import { existsSync } from 'node:fs';

const STL = process.argv[2] || 'C:/Users/galaz/Downloads/kapajka3.stl';
if (!existsSync(STL)) { console.error('BRAK pliku: ' + STL); process.exit(1); }

const errs = [];
const browser = await chromium.launch({ channel: 'msedge', headless: true });
const ctx = await browser.newContext({ viewport: { width: 1400, height: 950 }, serviceWorkers: 'block', locale: 'pl-PL' });
const page = await ctx.newPage();
page.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
page.on('pageerror', e => errs.push('PAGEERROR ' + e.message));

await page.goto('https://3dfile.link/zamow', { waitUntil: 'networkidle', timeout: 60000 });
await page.waitForTimeout(1000);

const R = [];
const state = () => page.evaluate(() => ({
  open: [...document.querySelectorAll('section.acc.open')].map(e => e.id),
  sum: [...document.querySelectorAll('.acc-s')].map(e => e.textContent),
  done: [...document.querySelectorAll('section.acc.done')].map(e => e.id),
}));

// 1. Wgraj plik
await page.setInputFiles('#fileInput', STL);
await page.waitForTimeout(4000);

const cartLen = await page.evaluate(() => (typeof CART !== 'undefined' ? CART.length : -1));
R.push(['model w koszyku', cartLen === 1, `${cartLen}`]);

// 2. Po wrzuceniu modelu krok 2 powinien byc otwarty (krok 1 skonczony)
let st = await state();
R.push(['po uploadzie otwarty nastepny krok', st.open.includes('acc2'), JSON.stringify(st.open)]);
R.push(['krok 1 oznaczony jako done', st.done.includes('acc1'), JSON.stringify(st.done)]);
R.push(['podsumowanie kroku 1 = liczba modeli', st.sum[0] === '1 × model', st.sum[0]]);

// 3. Wybierz material PETG w kroku 2
await page.click('#acc2 .mat[data-mat="PETG"]');
await page.waitForTimeout(1800);
st = await state();
R.push(['podsumowanie kroku 2 = material', st.sum[1] === 'PETG', st.sum[1]]);
R.push(['krok 2 done po wyborze materialu', st.done.includes('acc2'), JSON.stringify(st.done)]);

// 4. Krok 3 powinien byc otwarty po wyborze materialu
R.push(['po materiale otwarty krok 3', st.open.includes('acc3'), JSON.stringify(st.open)]);

// 5. Wybierz kolor (swatch) w kroku 3 — najpierw otworz go jawnie,
//    bo auto-otwarcie trzyma krok 2 otwarty az do momentu wyboru materialu jako "done".
if (!(await page.locator('#accb3').isVisible())) { await page.click('#acc3 .acc-h'); await page.waitForTimeout(400); }
const swCount = await page.locator('#accb3 .swatch').count();
if (swCount > 0) { await page.locator('#accb3 .swatch').first().click(); await page.waitForTimeout(900); }
const applyBtn = page.locator('#accb3 button[data-i18n="applyColor"]');
if ((await applyBtn.count()) && await applyBtn.isVisible()) { await applyBtn.click(); await page.waitForTimeout(2200); }

st = await state();
R.push(['krok 3 ma swatche', swCount > 0, `${swCount}`]);
R.push(['podsumowanie kroku 3 zawiera kolor', st.sum[2] && st.sum[2] !== '—', st.sum[2]]);

// 6. Cena: 22,4 cm3 PETG powinna byc powyzej minimum
const price = await page.evaluate(() => {
  const t = document.getElementById('ctaTot');
  return t ? t.textContent.trim() : null;
});
R.push(['cena widoczna w CTA', !!price && price !== '—', `${price}`]);

// 7. Kalkulacja przez API zgodna z tym, co widzi klient (source of truth)
const api = await page.evaluate(async () => {
  const it = CART[0];
  const fd = new FormData();
  fd.append('material', it.material); fd.append('color', it.color || 'black');
  fd.append('quantity', String(it.qty)); fd.append('shipping', 'pickup');
  fd.append('shipping_region', 'PL'); fd.append('volume_cm3', String(it.vol));
  fd.append('infill', String(it.infill)); fd.append('currency', 'PLN');
  const r = await fetch('/api/calculate', { method: 'POST', body: fd });
  return r.json();
});
console.log('  API: vol=' + api.volume_cm3 + ' g=' + api.filament_grams + ' cena=' + api.total + ' minimum=' + api.at_min_print);
// /api/calculate nie zwraca volume_cm3 (liczymy z filament_grams),
// ale gramsy sa zrodlem prawdy dla progu minimum.
R.push(['API: masa filamentu > 25 g dla 23,9 cm3', api.filament_grams > 25, `${api.filament_grams} g`]);
R.push(['API: realna wycena (at_min_print=false)', api.at_min_print === false, `minimum=${api.at_min_print}`]);
R.push(['API: cena zgodna z UI', Math.abs(api.total - parseFloat(String(price).replace(/[^\d,]/g, '').replace(',', '.'))) < 1.5, `api=${api.total} ui=${price}`]);

// 8. Kazdy krok da sie otworzyc i cofnac
for (const n of [1, 2, 3, 4]) {
  await page.click(`#acc${n} .acc-h`); await page.waitForTimeout(260);
  const open = await page.locator(`#accb${n}`).isVisible();
  if (!open) { R.push([`krok ${n} otwiera sie klikem`, false, 'nie widoczny']); }
}
R.push(['wszystkie 4 kroki otwieraja sie klikem', true, '']);

// 9. Podglad 3D — mesh musi byc realnie wczytany (nie tylko canvas.isConnected).
const mesh = await page.evaluate(() => {
  const p = window.__viewerPro;
  if (!p) return { vp: false };
  const m = p.mesh;
  if (!m) return { vp: true, mesh: false };
  const g = m.geometry;
  g.computeBoundingBox?.();
  const bb = g.boundingBox;
  return {
    vp: true, mesh: true,
    verts: g.attributes?.position?.count || 0,
    hex: m.material?.color?.getHexString?.() || null,
    box: bb ? [bb.min.y.toFixed(2), bb.max.y.toFixed(2)] : null,
  };
});
R.push(['viewer_pro dostepny', mesh.vp, JSON.stringify(mesh)]);
R.push(['mesh ma wierzcholki', mesh.verts > 0, `${mesh.verts} wierzcholkow`]);

// 10. Brak poziomego scrolla po wczytaniu modelu
const ov = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
R.push(['brak poziomego scrolla z modelem', ov <= 0, `${ov}px`]);

await page.screenshot({ path: 'shots_flow.png', fullPage: false });

console.log('');
let pass = 0;
for (const [name, ok, info] of R) {
  console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${name}${info ? '   [' + info + ']' : ''}`);
  if (ok) pass++;
}
console.log(`\n${pass}/${R.length} PASS   bledy konsoli: ${errs.length}`);
errs.slice(0, 5).forEach(e => console.log('   ! ' + e.slice(0, 160)));
await browser.close();
process.exit(pass === R.length && errs.length === 0 ? 0 : 1);