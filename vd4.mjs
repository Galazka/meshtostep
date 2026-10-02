import { chromium } from 'playwright-core';
const b=await chromium.launch({channel:'chrome'});
const p=await (await b.newContext({viewport:{width:1400,height:1200},serviceWorkers:'block',locale:'pl-PL'})).newPage();
p.on('pageerror',e=>console.log('PAGEERROR',e.message.slice(0,250)));
p.on('console',m=>{if(m.type()==='error')console.log('CONSOLE',m.text().slice(0,250));});
await p.goto('https://3dfile.link/zamow',{waitUntil:'networkidle',timeout:90000});
await p.setInputFiles('input[type=file]','C:/Users/galaz/Desktop/MeshToStep/frontend/_t1.stl');
await p.waitForTimeout(13000);
console.log(await p.evaluate(()=>{
  const l3=window.__local3d;
  const r={local3dExists:!!l3, local3dKeys:l3?Object.keys(l3):'-',
           proExists:!!window.__viewerPro};
  if(l3){
    // czy local3d trzyma wlasnego viewera?
    try{
      if(l3.viewer) r.l3viewerKeys=Object.keys(l3.viewer);
      if(l3.pro) r.l3proKeys=Object.keys(l3.pro);
      // sprawdz renderBytes
      r.hasRenderBytes=typeof l3.renderBytes;
    }catch(e){ r.err=e.message; }
  }
  // ile canvasow jest w previewBox
  r.canvases=document.querySelectorAll('#previewBox canvas').length;
  // canvas z viewerPro vs z local3d
  const pro=document.getElementById('previewBox').__pro;
  r.proCanvasParent=pro&&pro.renderer?pro.renderer.domElement.parentElement.tagName+'#'+pro.renderer.domElement.parentElement.id:'brak';
  return JSON.stringify(r,null,1);
}));
await b.close();
