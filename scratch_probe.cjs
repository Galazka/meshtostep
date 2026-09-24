const { chromium } = require('playwright-core');

(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 2000 }, serviceWorkers: 'block' });
  const page = await ctx.newPage();
  const reqs = [];
  page.on('response', r => { if (r.url().includes('/api/')) reqs.push(r.status() + ' ' + r.url().replace('https://3dfile.link','')); });
  await page.goto('https://3dfile.link/#discover', { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(4000);
  const info = await page.evaluate(() => {
    const out = [];
    document.querySelectorAll('img').forEach((im, i) => {
      const r = im.getBoundingClientRect();
      if (r.width < 30 || r.top > 4000 || out.length > 12) return;
      out.push({ src: (im.getAttribute('src')||'').slice(0,70), nat: im.naturalWidth + 'x' + im.naturalHeight,
        complete: im.complete, w: Math.round(r.width), h: Math.round(r.height),
        cls: im.className, parentBg: getComputedStyle(im.parentElement).backgroundColor });
    });
    return { imgs: out, h2: [...document.querySelectorAll('h2,h3')].slice(0,6).map(e=>e.textContent.trim().slice(0,40)) };
  });
  await page.screenshot({ path: process.env.SHOT_DIR + '/discover_full.png', fullPage: false });
  // profil publiczny
  await page.goto('https://3dfile.link/u/warsztatgdansk/wieszak-na-sluchawki-pod-biurko', { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(3500);
  await page.screenshot({ path: process.env.SHOT_DIR + '/share_prod.png', fullPage: false });
  console.log(JSON.stringify({ info, apiReqs: reqs.filter((v,i,a)=>a.indexOf(v)===i) }, null, 1));
  await browser.close();
})().catch(e => { console.error('ERR', e.message); process.exit(1); });
