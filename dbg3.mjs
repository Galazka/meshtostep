import { chromium } from 'playwright-core';
const b = await chromium.launch({ channel: 'msedge', headless: true });
const ctx = await b.newContext({ viewport: { width: 1400, height: 950 }, serviceWorkers: 'block' });
const p = await ctx.newPage();
p.on('pageerror', e => console.log('PAGEERROR: ' + e.message));
await p.goto('https://3dfile.link/zamow', { waitUntil: 'networkidle', timeout: 60000 });
await p.waitForTimeout(700);
console.log('przed:', JSON.stringify(await p.evaluate(()=>({fn:typeof refreshSteps, d1:_stepDone(1), cart:(typeof CART!=='undefined'?CART.length:-1)}))));
await p.setInputFiles('#fileInput', 'C:/Users/galaz/Downloads/kapajka3.stl');
await p.waitForTimeout(3000);
console.log('po:', JSON.stringify(await p.evaluate(()=>{
  var out={};
  try{ out.d1=_stepDone(1); out.d2=_stepDone(2); }catch(e){ out.err=e.message; }
  try{ refreshSteps(); out.called=true; }catch(e){ out.callErr=e.message+' | '+e.stack.split('\n')[1]; }
  out.sum1=(document.getElementById('accs1')||{}).textContent;
  out.cls1=document.getElementById('acc1').className;
  return out;
})));
await b.close();
