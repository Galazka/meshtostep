import { chromium } from 'playwright-core';
const b=await chromium.launch({channel:'chrome'});
const p=await (await b.newContext({viewport:{width:1400,height:1100},serviceWorkers:'block'})).newPage();
await p.goto('https://3dfile.link/zamow',{waitUntil:'networkidle',timeout:90000});
await p.setInputFiles('input[type=file]','C:/Users/galaz/Desktop/MeshToStep/frontend/_demo.stl');
await p.waitForTimeout(9000);
console.log(await p.evaluate(()=>{
  const c=document.querySelector('canvas'); const out=[];
  let e=c;
  while(e && e!==document.documentElement){
    const b=e.getBoundingClientRect(), s=getComputedStyle(e);
    out.push([e.tagName+'.'+(e.className||'').toString().split(' ')[0]+(e.id?'#'+e.id:''),
      'x='+Math.round(b.x),'w='+Math.round(b.width),'r='+Math.round(b.right),
      'pad='+s.paddingLeft+'/'+s.paddingRight,'box='+s.boxSizing,'ov='+s.overflowX].join(' '));
    e=e.parentElement;
  }
  return out.join('\n');
}));
await b.close();
