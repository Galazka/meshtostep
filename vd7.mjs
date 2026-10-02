import { chromium } from 'playwright-core';
const b=await chromium.launch({channel:'chrome'});
const p=await (await b.newContext({viewport:{width:1400,height:1200},deviceScaleFactor:2,serviceWorkers:'block',locale:'pl-PL'})).newPage();
p.on('pageerror',e=>console.log('PAGEERROR',e.message.slice(0,200)));
await p.goto('https://3dfile.link/zamow',{waitUntil:'networkidle',timeout:90000});
await p.setInputFiles('input[type=file]','C:/Users/galaz/Desktop/MeshToStep/frontend/_t1.stl');
await p.waitForTimeout(13000);
const probe=async()=>p.evaluate(()=>{
  const pro=document.getElementById('previewBox').__pro;
  if(!pro) return 'brak pro';
  let mesh=null; const seen=new Set();
  const scan=o=>{ if(!o||seen.has(o))return; seen.add(o);
    if(o.isMesh&&!mesh)mesh=o; (o.children||[]).forEach(scan); };
  scan(pro.scene);
  const c=pro.renderer.domElement;
  // render kolor mesha
  let col='brak'; if(mesh&&mesh.material.color) col='#'+mesh.material.color.getHexString();
  // policz jasne piksele w canvasie (model vs tlo)
  const g=document.createElement('canvas'); g.width=120;g.height=120;
  const cx=g.getContext('2d'); cx.drawImage(c,0,0,120,120);
  const d=cx.getImageData(0,0,120,120).data;
  let meshPix=0,sum=[0,0,0];
  for(let i=0;i<d.length;i+=4){
    if(Math.abs(d[i]-16)+Math.abs(d[i+1]-26)+Math.abs(d[i+2]-46)<50) continue;
    meshPix++; sum[0]+=d[i];sum[1]+=d[i+1];sum[2]+=d[i+2];
  }
  return JSON.stringify({isLoaded:pro.isLoaded(), meshFound:!!mesh, meshColor:col,
    meshPixels:meshPix, meshAvg: meshPix? sum.map(v=>Math.round(v/meshPix)) : null});
});
console.log('DOMYSLNY :', await probe());
for(const c of ['white','red','green','yellow']){
  await p.evaluate(cc=>{CART[0]._multi=[cc];CART[0].colors=1;CART[0].color=colPl([cc]);refreshCol();},c);
  await p.waitForTimeout(1800);
  console.log(c.padEnd(8)+':', await probe());
}
await b.close();
