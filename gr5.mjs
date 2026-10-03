import { chromium } from 'playwright-core';
import { mkdirSync, writeFileSync } from 'fs';
mkdirSync('shots',{recursive:true});
const b=await chromium.launch({channel:'chrome'});
const p=await (await b.newContext({viewport:{width:1400,height:1100},serviceWorkers:'block',locale:'pl-PL'})).newPage();
await p.goto('https://3dfile.link/zamow',{waitUntil:'networkidle',timeout:90000});
await p.waitForTimeout(2000);
for(const [name,file] of [['kula','/_gridtest.bin'],['inny','/logo.png']]){
  await p.evaluate(async(f)=>{
    const r=await fetch(f); const ab=await r.arrayBuffer();
    window.__local3d.renderBytes(f, ab, 'previewBox');
  }, file);
  await p.waitForTimeout(2800);
  console.log(name, await p.evaluate(()=>JSON.stringify(window.__viewerPro.probe())));
  const el=await p.$('.preview-box');
  if(el) await el.screenshot({path:`shots/grid_${name}.png`});
}
await b.close();
