import { chromium } from 'playwright-core';
import { writeFileSync, mkdirSync } from 'fs';
mkdirSync('shots',{recursive:true});
const b=await chromium.launch({channel:'chrome'});
const p=await (await b.newContext({viewport:{width:1400,height:1000},serviceWorkers:'block',locale:'pl-PL'})).newPage();
const errs=[]; p.on('pageerror',e=>errs.push(e.message.slice(0,80)));
await p.goto('https://3dfile.link/zamow',{waitUntil:'networkidle',timeout:90000});
await p.waitForTimeout(2500);
// wstrzyknij model i wymierz siatke vs mesh
console.log(await p.evaluate(async ()=>{
  const box=document.getElementById('previewBox');
  if(!box.__pro) return JSON.stringify({blad:'brak box.__pro'});
  const ab=await fetch('/logo.png').then(r=>r.arrayBuffer()); // nie stl, ale sprawdzimy siatke
  const v=box.__pro;
  return JSON.stringify({maApi:Object.keys(v||{})});
}));
// uzyj prawdziwego stl
await p.evaluate(()=>{ window.__STLTEST = true; });
console.log('--- laduje demo stl ---');
await p.evaluate(async ()=>{
  const r=await fetch('/_demo.stl'); 
  if(r.ok){ const ab=await r.arrayBuffer(); window.__local3d.renderBytes('demo.stl', ab, 'previewBox'); }
});
await p.waitForTimeout(2500);
console.log(await p.evaluate(()=>{
  const box=document.getElementById('previewBox');
  const v=box.__pro;
  const T=window.THREE;
  return JSON.stringify({maScene: !!(v&&v.scene)});
}));
await b.close();
