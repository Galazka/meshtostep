import { chromium } from 'playwright-core';
const b=await chromium.launch({channel:'chrome'});
const p=await (await b.newContext({viewport:{width:1400,height:1000},serviceWorkers:'block',locale:'pl-PL'})).newPage();
await p.goto('https://3dfile.link/zamow',{waitUntil:'networkidle',timeout:90000});
await p.waitForTimeout(2000);
await p.evaluate(async ()=>{
  const r=await fetch('/_demo.stl');
  const ab=await r.arrayBuffer();
  window.__local3d.renderBytes('demo.stl', ab, 'previewBox');
});
await p.waitForTimeout(3000);
console.log(await p.evaluate(()=>JSON.stringify(window.__viewerPro.probe())));
await b.close();
