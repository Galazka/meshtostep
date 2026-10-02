import { chromium } from 'playwright-core';
const b=await chromium.launch({channel:'chrome'});
const p=await (await b.newContext({viewport:{width:1400,height:1200},serviceWorkers:'block',locale:'pl-PL'})).newPage();
await p.goto('https://3dfile.link/zamow',{waitUntil:'networkidle',timeout:90000});
await p.evaluate(()=>pickFulfillment('ship'));
await p.waitForFunction(()=>document.querySelectorAll('#paczkomatList .pczrow').length>0,null,{timeout:60000});
await p.waitForTimeout(1500);
await p.evaluate(()=>document.querySelectorAll('#paczkomatList .pczrow')[3].click());
await p.waitForTimeout(1000);
console.log(await p.evaluate(()=>{
  const rows=document.querySelectorAll('#paczkomatList .pczrow');
  const sel=row=>{const cs=getComputedStyle(row);return{tlo:cs.backgroundColor,ramka:cs.borderColor,cien:cs.boxShadow,pl:cs.paddingLeft};};
  const s=document.querySelector('#paczkomatList .pczrow.sel');
  const n=document.querySelector('#paczkomatList .pczrow:not(.sel)');
  return JSON.stringify({
    liczbaWierszy:rows.length,
    selIstnieje:!!s,
    selHTML:s?s.outerHTML.slice(0,300):'-',
    selBadge: s?s.querySelector('.pczsel'):'BRAK',
    selStyle: s?sel(s):'-',
    plainStyle: n?sel(n):'-',
    darkModeAttr: document.documentElement.getAttribute('data-theme'),
    localTheme: localStorage.getItem('mt_theme')
  },null,1);
}));
await b.close();
