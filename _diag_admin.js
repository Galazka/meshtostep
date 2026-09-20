// Diagnostic: reproduce admin print-tab render in jsdom with stubbed fetch
const { JSDOM } = require('jsdom');
const fs = require('fs');
const path = 'C:/Users/galaz/Desktop/MeshToStep/frontend/';

let html = fs.readFileSync(path + 'admin.html', 'utf8');
let apr = fs.readFileSync(path + 'asset/admin_print.js', 'utf8');

const dom = new JSDOM(html, { runScripts: 'outside-only', url: 'https://3dfile.link/admin', pretendToBeVisual: true });
const { window } = dom;
const { document } = window;

// localStorage
const store = { mt_token: 'FAKETOKEN' };
window.localStorage = {
  getItem: (k) => store[k] ?? null,
  setItem: (k, v) => { store[k] = String(v); },
  removeItem: (k) => { delete store[k]; }
};

// stubbed fetch returning realistic data
const orders = {
  ok: true, total: 1, orders: [{
    id: 20, created_at: '2026-09-20T12:00:00Z', customer_name: 'Test Tomek',
    customer_email: 't@t.pl', customer_phone: '600000000', customer_city: 'Gdansk', customer_country: 'PL',
    status: 'nowy', items: [{ model_name: 'box.stl', material: 'PLA', color: 'czarny', quantity: 1, job_uuid: 'abc123' }]
  }]
};
const pricing = { ok: true, rows: [{key:'margin_percent', value:'68'},{key:'material:PLA', value:'79'}] };
const codes = { ok: true, codes: [] };
const gallery = { ok: true, items: [] };
const reviews = { ok: true, reviews: [] };
const reports = { ok: true, orders: [] };
const stats = { ok: true, total: 1, revenue: 100 };

window.fetch = (url, opts) => {
  console.log('  [FETCH]', url);
  let data = { ok: true };
  if (url.includes('/api/orders')) data = orders;
  else if (url.includes('/api/admin/pricing')) data = pricing;
  else if (url.includes('/api/admin/discount_codes')) data = codes;
  else if (url.includes('/api/admin/gallery')) data = gallery;
  else if (url.includes('/api/admin/reviews')) data = reviews;
  else if (url.includes('/api/admin/reports')) data = reports;
  else if (url.includes('/api/admin/orders/stats')) data = stats;
  return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(data) });
};

let errors = [];
window.addEventListener('error', (e) => { errors.push(String(e.error && e.error.stack || e.message)); });

try {
  // evaluate admin_print.js
  window.eval(apr);
  console.log('admin_print.js evaluated OK');
  console.log('window.switchPrintTab:', typeof window.switchPrintTab);
  console.log('window.loadAdminOrders?? -> inside IIFE; switchPrintTab calls internal loadAdminOrders');
  console.log('window.getStoredToken:', typeof window.getStoredToken);

  // simulate click on Zamówienia tab
  document.querySelectorAll('.tab-content').forEach(e => e.classList.remove('active'));
  const tabbtn = document.querySelector('.print-tab-btn[data-tab="orders"]');
  window.switchPrintTab('orders');
  console.log('after switchPrintTab, tab-orders active:', document.getElementById('tab-orders').classList.contains('active'));
  console.log('adminOrders inline display:', document.getElementById('adminOrders').style.display);
  console.log('adminOrders innerHTML after switch:', JSON.stringify(document.getElementById('adminOrders').innerHTML));
  // wait for the 50ms setTimeout + fetch
  setTimeout(() => {
    console.log('--- after 300ms ---');
    console.log('adminOrders innerHTML:', JSON.stringify(document.getElementById('adminOrders').innerHTML).slice(0, 500));
    console.log('errors:', errors);
    process.exit(0);
  }, 300);
} catch (e) {
  console.log('EVAL/EXEC ERROR:', e.stack);
  process.exit(1);
}
