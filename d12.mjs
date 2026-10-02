import { chromium } from 'playwright-core';
const b=await chromium.launch({channel:'chrome'});
const p=await (await b.newContext({viewport:{width:1400,height:1200},serviceWorkers:'block',locale:'pl-PL'})).newPage();
await p.goto('https://3dfile.link/zamow',{waitUntil:'networkidle',timeout:90000});
await p.evaluate(()=>pickFulfillment('ship'));
await p.waitForFunction(()=>document.querySelectorAll('#paczkomatList .pczrow').length>0,null,{timeout:60000});
await p.waitForTimeout(1200);
console.log(await p.evaluate(()=>{
  // czy regula .pczrow istnieje w CSSOM?
  let found=[];
  for(const sheet of document.styleSheets){
    let rules; try{rules=sheet.cssRules;}catch(e){continue;}
    for(const r of rules||[]){
      if(r.selectorText && /pczrow|pczsel|pczcode|pczsub/.test(r.selectorText))
        found.push(r.cssText.slice(0,160));
    }
  }
  const row=document.querySelector('#paczkomatList .pczrow');
  return JSON.stringify({
    regulyZnalezione:found,
    czyDisplayBlock:getComputedStyle(row).display,
    czyBorderWidth:getComputedStyle(row).borderTopWidth,
    czyFontSize:getComputedStyle(row).fontSize,
    czyMarginBottom:getComputedStyle(row).marginBottom,
    czyBackground:row.style.cssText || '(brak inline)',
    atrybuty:Array.from(row.attributes).map(a=>a.name+'='+a.value.slice(0,40))
  },null,1);
}));
await b.close();
