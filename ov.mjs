import { chromium } from 'playwright-core';
const b=await chromium.launch({channel:'chrome'});
for(const W of [1400,1100,900]){
const p=await (await b.newContext({viewport:{width:W,height:1100},serviceWorkers:'block',locale:'pl-PL'})).newPage();
await p.goto('https://3dfile.link/zamow',{waitUntil:'networkidle',timeout:90000});
await p.waitForTimeout(1800);
console.log(W, await p.evaluate(()=>{
  const pv=document.querySelector('.preview-box');
  if(!pv) return 'brak .preview-box';
  const pr=pv.getBoundingClientRect();
  // elementy z lewej kolumny, ktore wchodza na preview-box
  const hits=[];
  document.querySelectorAll('.steps, .step, .card, .mcard, .drop, .mat, .mats, .mgrid, .prt-stat, p, h2, h3, b, span').forEach(e=>{
    const r=e.getBoundingClientRect();
    if(r.width===0||r.height===0) return;
    if(r.right>pr.left+1 && r.left<pr.right-1 && r.bottom>pr.top+1 && r.top<pr.bottom-1){
      const t=(e.textContent||'').trim().slice(0,22);
      if(t) hits.push({tag:e.tagName+'.'+(e.className||'').toString().slice(0,22), t, right:Math.round(r.right), z:getComputedStyle(e).zIndex, pos:getComputedStyle(e).position});
    }
  });
  return JSON.stringify({preview:{l:Math.round(pr.left),r:Math.round(pr.right),t:Math.round(pr.top)},
    scrollW:document.documentElement.scrollWidth, vw:innerWidth, naklady:hits.length, przyklady:hits.slice(0,6)});
}));
await p.close();
}
await b.close();
