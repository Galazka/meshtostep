import { chromium } from 'playwright-core';
const b=await chromium.launch({channel:'chrome'});
const p=await (await b.newContext({viewport:{width:1400,height:1200},serviceWorkers:'block',locale:'pl-PL'})).newPage();
await p.goto('https://3dfile.link/zamow',{waitUntil:'networkidle',timeout:90000});
await p.setInputFiles('input[type=file]','C:/Users/galaz/Desktop/MeshToStep/frontend/_t1.stl');
await p.waitForTimeout(13000);
console.log(await p.evaluate(()=>{
  const v=window.__viewerPro;
  const out=[];
  const walk=(o,depth)=>{
    if(depth>3) return;
    const d={t:o.type,name:o.name||'',vis:o.visible,
             mat:o.material?o.material.type:'-',
             col:o.material&&o.material.color?'#'+o.material.color.getHexString():'-',
             kids:(o.children||[]).length};
    out.push('  '.repeat(depth)+JSON.stringify(d));
    (o.children||[]).forEach(c=>walk(c,depth+1));
  };
  walk(v.group,0);
  return out.join('\n');
}));
console.log('\n--- stan po setColor(red) ---');
console.log(await p.evaluate(()=>{
  const v=window.__viewerPro; v.setColor('#ff0000');
  const out=[]; const walk=(o,d)=>{ if(d>3)return;
    if(o.material&&o.material.color) out.push(o.type+' '+(o.name||'-')+' #'+o.material.color.getHexString());
    (o.children||[]).forEach(c=>walk(c,d+1)); };
  walk(v.group,0); return out.join(' | ');
}));
await b.close();
