import { chromium } from 'playwright-core';
const b=await chromium.launch({channel:'chrome'});
const p=await (await b.newContext({viewport:{width:1400,height:1000},serviceWorkers:'block',locale:'pl-PL'})).newPage();
const errs=[]; p.on('pageerror',e=>errs.push(e.message.slice(0,90)));
await p.goto('https://3dfile.link/konto',{waitUntil:'networkidle',timeout:90000});
await p.waitForTimeout(2500);
console.log(await p.evaluate(()=>{
  const t=document.body.innerText;
  const walk=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
  let n,leak=0;
  while(n=walk.nextNode()){ if(n.nodeValue.includes('+orders.length+')||n.nodeValue.includes('var API =')){
    const r=document.createRange(); r.selectNodeContents(n); if(r.getBoundingClientRect().height>0) leak++; } }
  return JSON.stringify({widocznyKod:leak, h1:(document.querySelector('h1')||{}).textContent,
    pustyStan:document.body.innerText.includes('Nie masz jeszcze')},null,1);
}));
console.log('bledy JS:', errs.length?errs.join(' | '):'brak');
await b.close();
