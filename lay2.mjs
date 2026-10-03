import { chromium } from 'playwright-core';
const b=await chromium.launch({channel:'chrome'});
const p=await (await b.newContext({viewport:{width:1400,height:1100},serviceWorkers:'block'})).newPage();
await p.goto('https://3dfile.link/zamow',{waitUntil:'networkidle',timeout:90000});
await p.setInputFiles('input[type=file]','C:/Users/galaz/Desktop/MeshToStep/frontend/_demo.stl');
await p.waitForTimeout(9000);
console.log(await p.evaluate(()=>{
  const vw=document.documentElement.clientWidth, out=[];
  document.querySelectorAll('*').forEach(e=>{
    const b=e.getBoundingClientRect();
    if(b.right>vw+1 && b.width>0){
      // pokaż tylko najbardziej prawy element (liść/bez dzieci wystajacych)
      const kid=[...e.children].some(c=>c.getBoundingClientRect().right>vw+1);
      if(!kid) out.push({tag:e.tagName, cls:(e.className||'').toString().slice(0,44), id:e.id,
        right:Math.round(b.right), w:Math.round(b.width),
        txt:(e.textContent||'').trim().slice(0,28)});
    }
  });
  return out.slice(0,14).map(o=>JSON.stringify(o)).join('\n');
}));
await b.close();
