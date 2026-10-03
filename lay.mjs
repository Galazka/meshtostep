import { chromium } from 'playwright-core';
const b=await chromium.launch({channel:'chrome'});
for(const w of [1400, 1000, 768, 390]){
  const p=await (await b.newContext({viewport:{width:w,height:1100},serviceWorkers:'block',locale:'pl-PL'})).newPage();
  await p.goto('https://3dfile.link/zamow',{waitUntil:'networkidle',timeout:90000});
  await p.setInputFiles('input[type=file]','C:/Users/galaz/Desktop/MeshToStep/frontend/_demo.stl');
  await p.waitForTimeout(9000);
  const r=await p.evaluate(()=>{
    const g=(s)=>document.querySelector(s);
    const box=(e)=>{ if(!e) return null; const b=e.getBoundingClientRect(); return {x:Math.round(b.x),w:Math.round(b.width)}; };
    const grid=g('.ocols')||g('.layout')||g('main');
    return {
      scrollW: document.documentElement.scrollWidth, clientW: document.documentElement.clientWidth,
      gridClass: grid?grid.className:null,
      cols: getComputedStyle(grid||document.body).gridTemplateColumns,
      steps: box(g('.steps')||g('.left')),
      side: box(g('.side')||g('.sidebar')||g('.previewWrap')),
      overflowX: document.documentElement.scrollWidth > document.documentElement.clientWidth+1,
    };
  });
  console.log(w+'px:', JSON.stringify(r));
  await p.close();
}
await b.close();
