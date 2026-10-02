import { chromium } from 'playwright-core';
const b=await chromium.launch({channel:'chrome'});
const p=await (await b.newContext({viewport:{width:1400,height:1200},serviceWorkers:'block',locale:'pl-PL'})).newPage();
p.on('pageerror',e=>console.log('PAGEERROR',e.message.slice(0,250)));
await p.goto('https://3dfile.link/zamow',{waitUntil:'networkidle',timeout:90000});
await p.setInputFiles('input[type=file]','C:/Users/galaz/Desktop/MeshToStep/frontend/_t1.stl');
await p.waitForTimeout(13000);
console.log(await p.evaluate(async()=>{
  const out=[];
  // 1) czy bytes to ArrayBuffer?
  const it=CART[0];
  out.push('_bytes ctor: '+it._bytes.constructor.name+' len='+it._bytes.byteLength);
  out.push('to ArrayBuffer: '+(it._bytes instanceof ArrayBuffer));
  // 2) spróbujmy STLLoader recznie przez dynamic import
  try{
    const M=await import('/vendor/three/loaders/STLLoader.js');
    out.push('STLLoader module: '+Object.keys(M).join(','));
    const ab=(it._bytes instanceof ArrayBuffer)?it._bytes:it._bytes.buffer.slice(it._bytes.byteOffset,it._bytes.byteOffset+it._bytes.byteLength);
    out.push('ab len: '+ab.byteLength);
    const geo=new M.STLLoader().parse(ab);
    out.push('geo: '+(geo?'ok':'null')+' verts='+(geo&&geo.attributes?geo.attributes.position.count:'-'));
  }catch(e){ out.push('STLLoader THROW: '+e.message); }
  // 3) probuj setMesh recznie
  try{
    const pro=document.getElementById('previewBox').__pro;
    out.push('pro.setMesh: '+typeof pro.setMesh);
    out.push('pro.attachMesh: '+typeof pro.attachMesh);
  }catch(e){ out.push('err '+e.message); }
  return out.join('\n');
}));
await b.close();
