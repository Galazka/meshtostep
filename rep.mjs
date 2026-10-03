import { chromium } from 'playwright-core';
import { mkdirSync } from 'fs';
mkdirSync('shots',{recursive:true});
const b=await chromium.launch({channel:'chrome'});
const p=await (await b.newContext({viewport:{width:1400,height:1150},serviceWorkers:'block',locale:'pl-PL'})).newPage();
const errs=[]; p.on('pageerror',e=>errs.push(e.message.slice(0,90)));
await p.goto('https://3dfile.link/zamow',{waitUntil:'networkidle',timeout:90000});
await p.waitForTimeout(2000);
console.log('render:', await p.evaluate(async()=>{
  const r=await fetch('/_kap.bin');
  const ab=await r.arrayBuffer();
  window.__local3d.renderBytes('kapajka3.stl', ab, 'previewBox');
  return 'ok '+r.status;
}));
await p.waitForTimeout(3200);
console.log('probe:', await p.evaluate(()=>JSON.stringify(window.__viewerPro.probe())));
const pv=await p.$('.preview-box');
await pv.screenshot({path:'shots/kap_full.png'});
await b.close();
