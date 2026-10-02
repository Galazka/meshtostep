import { chromium } from 'playwright-core';
const b=await chromium.launch({channel:'chrome'});
const p=await (await b.newContext({viewport:{width:1400,height:1200},serviceWorkers:'block',locale:'pl-PL'})).newPage();
p.on('console',m=>console.log('LOG:',m.text().slice(0,200)));
await p.goto('https://3dfile.link/zamow',{waitUntil:'networkidle',timeout:90000});
await p.setInputFiles('input[type=file]','C:/Users/galaz/Desktop/MeshToStep/frontend/_t1.stl');
await p.waitForTimeout(13000);
console.log(await p.evaluate(()=>{
  const v=window.__viewerPro;
  const r={globalViewerPro:!!v, boxPro:!!document.getElementById('previewBox').__pro,
           previewHex:previewHex(), setColorType:typeof (v&&v.setColor)};
  // czy to ten sam obiekt co viewer w previewBox?
  r.sameObject = (v===document.getElementById('previewBox').__pro);
  // jaki material ma mesh?
  const pro=document.getElementById('previewBox').__pro;
  try{
    let mesh=null;
    pro.group.traverse(o=>{ if(o.isMesh && !mesh) mesh=o; });
    r.meshFound=!!mesh;
    if(mesh){ r.meshColorHex='#'+mesh.material.color.getHexString();
              r.matType=mesh.material.type;
              r.rough=mesh.material.roughness; r.metal=mesh.material.metalness; }
  }catch(e){ r.meshErr=e.message; }
  return JSON.stringify(r,null,1);
}));
console.log('\n--- setColor bezposrednio ---');
console.log(await p.evaluate(()=>{
  const v=window.__viewerPro;
  try{ v.setColor('#ff0000'); }catch(e){ return 'ERR '+e.message; }
  let mesh=null;
  v.group.traverse(o=>{ if(o.isMesh&&!mesh) mesh=o; });
  return mesh? 'po setColor mesh.color = #'+mesh.material.color.getHexString() : 'brak mesh';
}));
await b.close();
