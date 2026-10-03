// Test accordion /zamow na produkcji (playwright-core z repo, SW zablokowany).
import { chromium } from 'playwright-core';

const errs = [];
const browser = await chromium.launch({ channel: 'msedge', headless: true });
const ctx = await browser.newContext({
  viewport: { width: 1400, height: 950 },
  serviceWorkers: 'block',
  locale: 'pl-PL',
});
const page = await ctx.newPage();
page.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
page.on('pageerror', e => errs.push('PAGEERROR ' + e.message));

await page.goto('https://3dfile.link/zamow', { waitUntil: 'networkidle', timeout: 60000 });
await page.waitForTimeout(1200);

const R = [];

// 1. Struktura accordion
const accCount = await page.locator('section.acc').count();
R.push(['4 sekcje accordion', accCount === 4, `${accCount}`]);

// 2. Domyslnie otwarty jest dokladnie jeden krok (krok 1)
const openCount = await page.locator('section.acc.open').count();
R.push(['jeden krok otwarty na starcie', openCount === 1, `${openCount}`]);

// 3. Naglowki widoczne ze summary
const summaries = await page.locator('.acc-s').allTextContents();
R.push(['podsumowania w naglowkach', summaries.length === 4, JSON.stringify(summaries)]);

// 4. Krok 1 otwarty, reszta zwinieta
const isOpen1 = await page.locator('#acc1').evaluate(e => e.classList.contains('open'));
const body1vis = await page.locator('#accb1').isVisible();
const body2vis = await page.locator('#accb2').isVisible();
R.push(['krok 1 otwarty, krok 2 zwiniety', isOpen1 && body1vis && !body2vis, `acc1open=${isOpen1} b1=${body1vis} b2=${body2vis}`]);

// 5. Klik na naglowek kroku 2 przełącza
await page.click('#acc2 .acc-h');
await page.waitForTimeout(450);
const b2 = await page.locator('#accb2').isVisible();
const b1 = await page.locator('#accb1').isVisible();
R.push(['klik kroku 2 otwiera go (dowolnie, nie tylko nastepny)', b2, `b2=${b2} b1=${b1}`]);

// 6. aria-expanded sie aktualizuje
const aria = await page.locator('#acc2 .acc-h').getAttribute('aria-expanded');
R.push(['aria-expanded na kroku 2 = true', aria === 'true', `${aria}`]);

// 7. Ponowne klikniecie zwija
await page.click('#acc2 .acc-h');
await page.waitForTimeout(350);
const b2closed = !(await page.locator('#accb2').isVisible());
R.push(['drugi klik zwija krok 2', b2closed, `${b2closed}`]);

// 8. Zadna sekcja nie jest pusta/nieopisana
const titles = await page.locator('.acc-t').allTextContents();
R.push(['4 tytuly krokow', titles.length === 4 && titles.every(t => t.trim().length > 2), JSON.stringify(titles)]);

// 9. Notatki krokow sa widoczne po otwarciu
// krok 1 by juz otwarty po tescie 4 — nie klikaj go, bo go zwinasz.
if (!(await page.locator('#accb1').isVisible())) { await page.click('#acc1 .acc-h'); await page.waitForTimeout(350); }
const note = await page.locator('#accb1 .acc-stepnote').first().isVisible();
R.push(['notatka kroku widoczna po otwarciu', note, `${note}`]);

// 10. Brak poziomego scrolla
const ov = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
R.push(['brak poziomego scrolla', ov <= 0, `${ov}px`]);

// 11. Funkcje JS istnieja w globals
const fns = await page.evaluate(() => ({
  toggle: typeof window.toggleStep, open: typeof window.openStep,
  refresh: typeof window.refreshSteps, done: typeof window._stepDone,
}));
R.push(['funkcje accordion w global', Object.values(fns).every(t => t === 'function'), JSON.stringify(fns)]);

// 12. Brak bledow JS
R.push(['zero bledow konsoli', errs.length === 0, errs.slice(0, 3).join(' | ')]);

// 13. Sekcja "Modele" nadal ma dropzone
const dz = await page.locator('#accb1 .dropzone').count();
R.push(['dropzone w kroku 1', dz === 1, `${dz}`]);

// 14. Materiały są w kroku 2
const mats = await page.locator('#accb2 .mat').count();
R.push(['kafelki materialow w kroku 2', mats > 0, `${mats} kafelkow`]);

await page.screenshot({ path: 'shots_acc_closed.png', fullPage: false });
await page.click('#acc1 .acc-h'); await page.waitForTimeout(300);
await page.click('#acc3 .acc-h'); await page.waitForTimeout(500);
await page.screenshot({ path: 'shots_acc_open.png', fullPage: false });

console.log('');
let pass = 0;
for (const [name, ok, info] of R) {
  console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${name}${info ? '   [' + info + ']' : ''}`);
  if (ok) pass++;
}
console.log(`\n${pass}/${R.length} PASS`);
console.log(`błędy konsoli: ${errs.length}`);
errs.slice(0, 5).forEach(e => console.log('   ! ' + e.slice(0, 160)));

await browser.close();
process.exit(pass === R.length && errs.length === 0 ? 0 : 1);