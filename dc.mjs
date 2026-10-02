import { chromium } from 'playwright-core';
const b=await chromium.launch({channel:'chrome'});
const p=await (await b.newContext({viewport:{width:1400,height:1200},serviceWorkers:'block',locale:'pl-PL'})).newPage();
p.on('pageerror',e=>console.log('PAGEERROR',e.message.slice(0,150)));
await p.goto('https://3dfile.link/zamow',{waitUntil:'networkidle',timeout:90000});
await p.setInputFiles('input[type=file]','C:/Users/galaz/Desktop/MeshToStep/frontend/_t1.stl');
await p.waitForTimeout(12000);
const dump=async(l)=>{
  try{
    const r=await p.evaluate(()=>{
      const it=CART[0];
      return JSON.stringify({
        multi:it&&it._multi?it._multi.slice():'brak',
        colors:it?it.colors:'-', color:it?it.color:'-',
        hex:typeof previewHex==='function'?previewHex():'brak fn',
        multiLen:it&&it._multi?it._multi.length:'-'
      });
    });
    console.log(l,r);
  }catch(e){ console.log(l,'ERR',e.message.slice(0,120)); }
};
await dump('start       :');
await p.evaluate(()=>pickColor('white')); await p.waitForTimeout(900); await dump('po bialy    :');
await p.evaluate(()=>pickColor('blue'));  await p.waitForTimeout(900); await dump('po niebieski:');
await p.evaluate(()=>pickColor('black')); await p.waitForTimeout(900); await dump('po czarny   :');
await b.close();
