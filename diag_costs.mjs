import fs from 'fs';
const BASE = 'https://3dfile.link';
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36';
const V = JSON.parse(fs.readFileSync(process.env.ADMTEST_VARS, 'utf8'));
const r = await fetch(BASE + '/api/auth/login?t=' + Date.now(), {
  method: 'POST', headers: { 'User-Agent': UA, 'Content-Type': 'application/json' },
  body: JSON.stringify({ email: V.admin_email, password: V.admin_password }) });
const b = await r.json();
const tok = b.token || (b.data && b.data.token);
const o = await (await fetch(BASE + '/api/orders?t=' + Date.now() + '&page=1&sort=newest',
  { headers: { 'User-Agent': UA, Authorization: 'Bearer ' + tok } })).json();
const list = o.orders || [];
console.log('zamowien:', list.length);
const keys = ['filament_cost','electricity_cost','color_premium','product_cost','production_cost',
              'shipping_cost','total_cost','margin_pln','profit','subtotal','total',
              'shipping_cost_pln','packing_fee','discount','margin'];
const first = list.find(x => x.items && x.items.length) || list[0];
console.log('\n--- zamowienie #' + first.id + ' ---');
for (const k of keys) if (first[k] !== undefined) console.log('  ' + k.padEnd(22), first[k]);
console.log('\n--- wszystkie klucze numeryczne ---');
for (const [k,v] of Object.entries(first)) {
  if (typeof v === 'number') console.log('  ' + k.padEnd(24), v);
}
console.log('\n--- items ---');
(first.items||[]).forEach((it,i)=>{
  console.log('  #' + i, JSON.stringify({qty:it.quantity, price:it.unit_price, amount:it.total,
    filament_cost:it.filament_cost, electricity_cost:it.electricity_cost,
    color_premium:it.color_premium, margin_pln:it.margin_pln, profit:it.profit,
    material:it.material, color:it.color}).slice(0,300));
});