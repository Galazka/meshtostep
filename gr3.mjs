import { chromium } from 'playwright-core';
const b=await chromium.launch({channel:'chrome'});
const p=await (await b.newContext({viewport:{width:1400,height:1000},serviceWorkers:'block',locale:'pl-PL'})).newPage();
const errs=[]; p.on('pageerror',e=>errs.push(e.message.slice(0,90)));
p.on('console',m=>{if(m.type()==='error')errs.push('C:'+m.text().slice(0,90))});
await p.goto('https://3dfile.link/zamow',{waitUntil:'networkidle',timeout:90000});
await p.waitForTimeout(2000);
console.log(await p.evaluate(async ()=>{
  const r=await fetch('/_demo.stl');
  if(!r.ok) return JSON.stringify({fetch:r.status});
  const ab=await r.arrayBuffer();
  try{ window.__local3d.renderBytes('demo.stl', ab, 'previewBox'); }
  catch(e){ return JSON.stringify({wyjatek:e.message}); }
  return JSON.stringify({ok:true, maViewer:!!window.__viewerPro, isLoaded:window.__viewerPro&&window.__viewerPro.isLoaded()});
}));
await p.waitForTimeout(3000);
console.log(await p.evaluate(()=>JSON.stringify({probe:window.__viewerPro.probe()})));
console.log('bledy:', errs.length?errs.slice(0,3).join(' | '):'brak');
await b.close();
