import { chromium } from 'playwright-core';
const b=await chromium.launch({channel:'chrome'});
const p=await (await b.newContext({viewport:{width:1400,height:1200},serviceWorkers:'block',locale:'pl-PL'})).newPage();
p.on('pageerror',e=>console.log('PAGEERROR',e.message.slice(0,250)));
p.on('console',m=>{const t=m.text(); if(!t.includes('Service Worker')) console.log('LOG:',t.slice(0,250));});
await p.goto('https://3dfile.link/zamow',{waitUntil:'networkidle',timeout:90000});
await p.setInputFiles('input[type=file]','C:/Users/galaz/Desktop/MeshToStep/frontend/_t1.stl');
await p.waitForTimeout(13000);
console.log('--- czy renderBytes w ogole laduje? wywolmy recznie i zlapmy wynik ---');
console.log(await p.evaluate(async()=>{
  const it=CART[0];
  const log=[];
  try{
    window.__local3d.renderBytes(it.model_name, it._bytes, 'previewBox');
    log.push('renderBytes bez wyjatku');
  }catch(e){ log.push('renderBytes THROW: '+e.message); }
  await new Promise(r=>setTimeout(r,4000));
  const pro=document.getElementById('previewBox').__pro;
  let meshes=0,cols=[];
  const seen=new Set();
  const scan=o=>{ if(!o||seen.has(o))return; seen.add(o);
    if(o.isMesh){meshes++; if(cols.length<3&&o.material&&o.material.color)cols.push('#'+o.material.color.getHexString());}
    (o.children||[]).forEach(scan); };
  if(pro&&pro.scene) scan(pro.scene);
  log.push('pro.scene meshe: '+meshes);
  log.push('kolory: '+cols.join(','));
  log.push('pro.isLoaded: '+(pro&&pro.isLoaded?pro.isLoaded():'-'));
  // renderBox meshe?
  const box=document.getElementById('previewBox');
  let n=0; const s2=new Set();
  const scan2=o=>{ if(!o||s2.has(o))return; s2.add(o);
    if(o.isMesh)n++; (o.children||[]).forEach(scan2); };
  return log.join(' | ');
}));
await b.close();
