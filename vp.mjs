import { chromium } from 'playwright-core';
const b=await chromium.launch({channel:'chrome'});
const p=await (await b.newContext({viewport:{width:1400,height:1200},deviceScaleFactor:2,serviceWorkers:'block',locale:'pl-PL'})).newPage();
await p.goto('https://3dfile.link/zamow',{waitUntil:'networkidle',timeout:90000});
await p.setInputFiles('input[type=file]','C:/Users/galaz/Desktop/MeshToStep/frontend/_t1.stl');
await p.waitForTimeout(13000);
const meshAvg=async()=>p.evaluate(()=>{
  const c=document.querySelector('#previewBox canvas'); if(!c) return 'brak canvas';
  const g=document.createElement('canvas'); g.width=110;g.height=110;
  const cx=g.getContext('2d'); cx.drawImage(c,0,0,110,110);
  const d=cx.getImageData(0,0,110,110).data;
  const bg=[16,26,46];
  let n=0,sum=[0,0,0],mesh=0;
  for(let i=0;i<d.length;i+=4){
    if(Math.abs(d[i]-bg[0])+Math.abs(d[i+1]-bg[1])+Math.abs(d[i+2]-bg[2])<40) continue;
    mesh++; sum[0]+=d[i];sum[1]+=d[i+1];sum[2]+=d[i+2];
  }
  if(!mesh) return 'brak mesha';
  return 'pikseli='+mesh+' sredni=rgb('+sum.map(v=>Math.round(v/mesh)).join(',')+')';
});
console.log('DOMYSLNY (czarny) :', await meshAvg());
await p.locator('#previewBox').screenshot({path:'shots/col-black.png'});
for(const [c,nazwa] of [['white','bialy'],['red','czerwony'],['yellow','zolty']]){
  await p.evaluate(cc=>{CART[0]._multi=[cc];CART[0].colors=1;CART[0].color=colPl([cc]);refreshCol();},c);
  await p.waitForTimeout(1600);
  console.log(nazwa.padEnd(10)+':', await meshAvg());
  await p.locator('#previewBox').screenshot({path:'shots/col-'+c+'.png'});
}
await b.close();
