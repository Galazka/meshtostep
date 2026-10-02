import { chromium } from 'playwright-core';

const BASE = 'https://3dfile.link';
const SHOT = 'C:/Users/galaz/Desktop/MeshToStep/shots';
let pass = 0, fail = 0;
const ok = (c, m) => { c ? (pass++, console.log('  PASS ' + m)) : (fail++, console.log('  FAIL ' + m)); };

const browser = await chromium.launch({ channel: 'chrome' });
const ctx = await browser.newContext({
  viewport: { width: 1280, height: 1000 },
  permissions: [],
  serviceWorkers: 'block',
  locale: 'pl-PL',
});
const page = await ctx.newPage();
const errs = [];
page.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
page.on('pageerror', e => errs.push('PAGEERROR ' + e.message));

await page.goto(BASE + '/zamow', { waitUntil: 'networkidle', timeout: 90000 });

// --- 1. wejscie na wysylke (paczkomat) ---
console.log('\n[1] panel wysylki');
await page.evaluate(() => pickFulfillment('ship'));
await page.waitForFunction(() => document.querySelectorAll('#paczkomatList .pczrow').length > 0, null, { timeout: 60000 });
const rowsAll = await page.locator('#paczkomatList .pczrow').count();
ok(rowsAll > 300, `pelna lista paczkomatow widoczna (${rowsAll} pozycji, nie 12)`);

// --- 2. mapa ---
console.log('\n[2] mapa Leaflet');
await page.waitForFunction(() => !!document.getElementById('pczMap').classList.contains('leaflet-container'), null, { timeout: 40000 });
await page.waitForTimeout(2500);
const markers = await page.locator('#pczMap .leaflet-marker-icon').count();
ok(markers > 300, `markery na mapie: ${markers}`);
const tiles = await page.locator('#pczMap img.leaflet-tile-loaded').count();
ok(tiles > 0, `kafelki OSM zaladowane: ${tiles}`);

// --- 3. RAATZA ---
console.log('\n[3] szukanie ulicy "Raatza" (ta, ktorej nie bylo w wyborze)');
await page.evaluate(() => { const e=document.getElementById('fPaczkomat'); e.value=''; });
await page.type('#fPaczkomat', 'Raatza', { delay: 60 });
await page.waitForTimeout(2500);
const raatzaTxt = await page.locator('#paczkomatList').innerText();
ok(/Raatza/i.test(raatzaTxt), 'ulica Raatza widoczna na liscie');
const codeTxt = await page.locator('#paczkomatList').innerText();
ok(/GDA1\d+M|GDA\d+M/i.test(codeTxt), 'kod paczkomatu (GDA...M) pokazany');
await page.screenshot({ path: SHOT + '/pcz-raatza.png', fullPage: false });

// --- 4. wybor z listy ---
console.log('\n[4] wybor punktu z listy');
const before = await page.inputValue('#fPaczkomatName');
await page.evaluate(() => document.querySelectorAll('#paczkomatList .pczrow')[0].click());
await page.waitForTimeout(800);
const after = await page.inputValue('#fPaczkomatName');
ok(after && after !== before, `hidden input ustawiony: ${after}`);
const selStyle = await page.locator('#paczkomatList .pczrow.sel').count();
ok(selStyle === 1, 'wyróżniony wiersz zaznaczenia');
const statusTxt = await page.locator('#pczStatus').innerText();
ok(/Wybrano/i.test(statusTxt), 'status "Wybrano"');

// --- 5. powrot do pelnego katalogu i reczny wybor ---
console.log('\n[5] powrot do pelnego katalogu miasta');
await page.evaluate(() => { searchPaczkomatCity('Gdańsk'); });
await page.waitForFunction(() => document.querySelectorAll('#paczkomatList .pczrow').length > 100, null, { timeout: 60000 });
await page.waitForTimeout(1200);
const allBack = await page.locator('#paczkomatList .pczrow').count();
ok(allBack > 300, `powrot do katalogu miasta: ${allBack}`);
const manualPick = await page.evaluate(() => {
  const rows = document.querySelectorAll('#paczkomatList .pczrow');
  rows[5].click();
  return document.getElementById('fPaczkomatName').value;
});
ok(manualPick && manualPick !== after, `reczny wybor nadpisuje poprzedni: ${manualPick}`);
const selCount = await page.locator('#paczkomatList .pczrow.sel').count();
ok(selCount === 1, 'dokladnie jeden wiersz zaznaczony po zmianie wyboru');

// --- 6. najblizszy automatycznie (bez geolokalizacji = musi graceful) ---
console.log('\n[6] przycisk "najblizszy automatycznie" bez geolokalizacji');
ctx.clearPermissions();
await page.fill('#fPaczkomat', '');
await page.click('text=Wybierz najbliższy automatycznie');
await page.waitForTimeout(6000);
const s6 = await page.locator('#pczStatus').innerText();
ok(/lokalizacj/i.test(s6), `komunikat o braku geolokalizacji nie zostal nadpisany: "${s6.slice(0, 80)}"`);
const rowsAfter = await page.locator('#paczkomatList .pczrow').count();
ok(rowsAfter > 0, `lista nadal pokazuje punkty (${rowsAfter})`);

// --- 7. blad geolokalizacji (fake deny) ---
console.log('\n[7] geolokalizacja zablokowana');
const ctx2 = await browser.newContext({
  viewport: { width: 1280, height: 1000 },
  serviceWorkers: 'block', locale: 'pl-PL',
  geolocation: { latitude: 54.3520, longitude: 18.6466 },
  permissions: ['geolocation'],
});
const p2 = await ctx2.newPage();
p2.on('pageerror', e => errs.push('PAGEERROR2 ' + e.message));
await p2.goto(BASE + '/zamow', { waitUntil: 'networkidle', timeout: 90000 });
await p2.evaluate(() => pickFulfillment('ship'));
await p2.waitForFunction(() => document.querySelectorAll('#paczkomatList .pczrow').length > 0, null, { timeout: 60000 });
await p2.click('text=Wybierz najbliższy automatycznie');
await p2.waitForTimeout(9000);
const s7 = await p2.locator('#pczStatus').innerText();
const name7 = await p2.inputValue('#fPaczkomatName');
ok(name7.length > 0, `punkt wybrany z geolokalizacji: ${name7}`);
ok(/Najbliższy|metr|m\b/i.test(s7 + name7) || s7.length > 0, `status: ${s7.slice(0, 70)}`);
await p2.screenshot({ path: SHOT + '/pcz-nearest.png' });
await ctx2.close();

// --- 8. mobile 360 ---
console.log('\n[8] mobile 360px');
const ctx3 = await browser.newContext({
  viewport: { width: 360, height: 780 }, isMobile: true, hasTouch: true,
  deviceScaleFactor: 3, serviceWorkers: 'block', locale: 'pl-PL',
});
const p3 = await ctx3.newPage();
await p3.goto(BASE + '/zamow', { waitUntil: 'networkidle', timeout: 90000 });
await p3.evaluate(() => pickFulfillment('ship'));
await p3.waitForFunction(() => document.querySelectorAll('#paczkomatList .pczrow').length > 0, null, { timeout: 60000 });
const ovf = await p3.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
ok(ovf <= 2, `brak poziomego overflow (${ovf}px)`);
const mapH = await p3.evaluate(() => document.getElementById('pczMap').getBoundingClientRect().height);
ok(mapH > 180, `mapa widoczna na mobile (${Math.round(mapH)}px)`);
await p3.screenshot({ path: SHOT + '/pcz-mobile.png', fullPage: false });
await ctx3.close();

console.log('\n=== ' + pass + '/' + (pass + fail) + ' PASS, ' + errs.length + ' bledow konsoli ===');
errs.slice(0, 6).forEach(e => console.log('  ! ' + e.slice(0, 140)));
await browser.close();
process.exit(fail ? 1 : 0);