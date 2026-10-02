import { chromium } from 'playwright-core';
const b=await chromium.launch({channel:'chrome'});
const p=await (await b.newContext({viewport:{width:1400,height:1200},serviceWorkers:'block',locale:'pl-PL'})).newPage();
p.on('console',m=>console.log('LOG:',m.text().slice(0,300)));
p.on('pageerror',e=>console.log('PAGEERROR',e.message.slice(0,200)));
await p.goto('https://3dfile.link/zamow',{waitUntil:'networkidle',timeout:90000});
// przechwyc innerHTML=''
await p.evaluate(()=>{
  const box=document.getElementById('previewBox');
  const d=Object.getOwnPropertyDescriptor(Element.prototype,'innerHTML');
  Object.defineProperty(box,'innerHTML',{
    configurable:true,
    get(){return d.get.call(this);},
    set(v){
      if(String(v).trim()===''){
        console.log('=== innerHTML="" na previewBox ===\n'+new Error().stack);
      }
      d.set.call(this,v);
    }
  });
});
await p.setInputFiles('input[type=file]','C:/Users/galaz/Desktop/MeshToStep/frontend/_demo.stl');
await p.waitForTimeout(11000);
console.log('1 plik canvas:',await p.evaluate(()=>document.querySelectorAll('#previewBox canvas').length));
await p.setInputFiles('input[type=file]','C:/Users/galaz/Downloads/222222222222222.stl');
await p.waitForTimeout(12000);
console.log('2 plik canvas:',await p.evaluate(()=>document.querySelectorAll('#previewBox canvas').length));
await b.close();
