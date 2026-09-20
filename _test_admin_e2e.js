
// Simulate browser environment for admin_print.js
const { JSDOM } = require('jsdom');
const fs = require('fs');
const path = require('path');

async function main() {
  // Read admin.html
  const html = fs.readFileSync(path.resolve('frontend', 'admin.html'), 'utf-8');
  const dom = new JSDOM(html, {
    url: 'https://3dfile.link/admin',
    runScripts: 'outside-only',
    resources: 'usable',
  });
  const w = dom.window;
  const d = w.document;
  
  // Set up the globals admin_print.js expects
  w.localStorage.setItem('mt_token', fs.readFileSync('/tmp/admin_token.txt', 'utf-8').trim());
  
  // Now read and evaluate admin_print.js
  const printJs = fs.readFileSync(path.resolve('frontend', 'asset', 'admin_print.js'), 'utf-8');
  try {
    w.eval(printJs);
  } catch (e) {
    console.log('EVAL ERROR:', e.message);
    console.log(e.stack);
    return;
  }
  
  // Now call switchPrintTab('orders')
  console.log('=== Calling switchPrintTab("orders") ===');
  try {
    await w.switchPrintTab('orders');
  } catch(e) {
    console.log('switchPrintTab error:', e.message);
  }
  
  // Wait for the 50ms + fetch
  await w.setTimeout(() => {}, 200);
  
  // Check adminOrders content
  await w.setTimeout(() => {}, 100);
  
  const ao = d.getElementById('adminOrders');
  if (ao) {
    const html = ao.innerHTML;
    console.log('adminOrders innerHTML length:', html.length);
    console.log('First 300 chars:', html.substring(0, 300));
    console.log('Contains "Ładowanie":', html.includes('Ładowanie'));
    console.log('Contains "tr" (table row):', (html.match(/<tr[^>]*>/g) || []).length);
    console.log('Contains "Błąd":', html.includes('Błąd'));
  } else {
    console.log('adminOrders element NOT FOUND');
  }
  
  // Check all print tab containers
  ['tab-orders', 'tab-pstats', 'tab-pricing', 'tab-codes', 'tab-gallery', 'tab-reviews', 'tab-materials'].forEach(id => {
    const el = d.getElementById(id);
    if (el) {
      console.log(id, 'classes:', el.className, 'display:', el.style.display);
    }
  });
}

main().catch(e => console.error('MAIN ERROR:', e.message, e.stack));
