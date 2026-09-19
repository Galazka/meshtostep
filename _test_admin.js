// Test admin_print.js w jsdom z prawdziwym fetchem do produkcji
const { JSDOM } = require('jsdom');
const fs = require('fs');

(async () => {
  // login → token
  const lr = await fetch('https://3dfile.link/api/auth/login', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: 'admin@meshtostep.pl', password: 'MeshToStep2026!' })
  });
  const { token } = await lr.json();
  console.log('token len:', token.length);

  const html = '<html><body><div id="adminOrders" class="print-panel"></div><div id="adminStats"></div><div id="adminPricing"></div><div id="adminCodes"></div><div id="adminGallery"></div><div id="adminReviews"></div><div id="adminReports"></div></body></html>';
  const dom = new JSDOM(html, { url: 'https://3dfile.link/admin', runScripts: 'outside-only' });
  const { window } = dom;

  // localStorage token
  window.localStorage.setItem('mt_token', token);
  // fetch: przekieruj relative → prod
  const gfetch = global.fetch;
  window.fetch = (url, opts) => {
    const u = url.startsWith('http') ? url : 'https://3dfile.link' + url;
    return gfetch(u, opts);
  };
  window.confirm = () => true;
  window.console.error = (...a) => console.log('[console.error]', ...a);

  // wczytaj admin_print.js w kontekście okna
  const code = fs.readFileSync('frontend/asset/admin_print.js', 'utf8');
  try {
    dom.runVMScript ? null : null;
    const vm = require('vm');
    const ctx = dom.getInternalVMContext();
    vm.runInContext(code, ctx);
    console.log('SKRYPT ZAŁADOWANY');
  } catch (e) {
    console.log('BŁĄD ŁADOWANIA SKRYPTU:', e.message);
    process.exit(1);
  }

  // klik symulacja
  try {
    window.switchPrintTab('orders');
    console.log('switchPrintTab OK, title:', window.document.title);
  } catch (e) { console.log('switchPrintTab ERR:', e.message); }

  await new Promise(r => setTimeout(r, 5000));
  const c = window.document.getElementById('adminOrders');
  console.log('--- adminOrders innerHTML len:', c.innerHTML.length);
  console.log('--- preview:', c.innerHTML.slice(0, 300).replace(/\n/g, ' '));
  process.exit(0);
})().catch(e => { console.log('FATAL:', e.message); process.exit(1); });
