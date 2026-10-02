import { chromium } from 'playwright-core';
const b=await chromium.launch({channel:'chrome'});
const p=await (await b.newContext({viewport:{width:1400,height:1200},serviceWorkers:'block',locale:'pl-PL'})).newPage();
p.on('pageerror',e=>console.log('PAGEERROR',e.message.slice(0,200)));
p.on('console',m=>{if(m.type()==='error')console.log('CONSOLE',m.text().slice(0,200));});
await p.goto('https://3dfile.link/zamow',{waitUntil:'networkidle',timeout:90000});
await p.setInputFiles('input[type=file]','C:/Users/galaz/Desktop/MeshToStep/frontend/_t1.stl');
await p.waitForTimeout(13000);
console.log(await p.evaluate(()=>{
  const pro=document.getElementById('previewBox').__pro;
  const v=window.__viewerPro;
  const r={proApiKeys:Object.keys(pro||{}), vKeys:Object.keys(v||{})};
  // scene?
  let meshCount=0, meshes=[];
  const scan=(o,d,seen)=>{ if(d>6||seen.has(o))return; seen.add(o);
    if(o.isMesh){meshCount++; if(meshes.length<3) meshes.push({name:o.name||'(brak)',
      col:o.material&&o.material.color?'#'+o.material.color.getHexString():'-',
      matType:o.material?o.material.type:'-'});}
    (o.children||[]).forEach(c=>scan(c,d+1,seen)); };
  const seen=new Set();
  if(v&&v.scene) scan(v.scene,0,seen);
  if(pro&&pro.scene) scan(pro.scene,0,seen);
  r.sceneExists = !!(v&&v.scene)||!!(pro&&pro.scene);
  r.sceneMeshCount=meshCount; r.meshes=meshes;
  r.groupKids = v&&v.group?v.group.children.length:'-';
  r.isLoaded = v&&v.isLoaded?v.isLoaded():'-';
  return JSON.stringify(r,null,1);
}));
await b.close();
