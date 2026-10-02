import { chromium } from 'playwright-core';
const b=await chromium.launch({channel:'chrome'});
const p=await (await b.newContext({viewport:{width:1400,height:1200},serviceWorkers:'block',locale:'pl-PL'})).newPage();
p.on('console',m=>console.log('LOG:',m.text().slice(0,400)));
await p.goto('https://3dfile.link/zamow',{waitUntil:'networkidle',timeout:90000});
await p.evaluate(()=>{
  window.__log=[];
  const orig=document.getElementById.bind(document);
  window.addEventListener('DOMNodeRemovedFromDocument',e=>{},true);
  const box=document.getElementById('previewBox');
  window.__log.push('box jest: '+!!box);
  // obserwuj czy sam box znika
  const mo=new MutationObserver(()=>{
    const b2=document.getElementById('previewBox');
    window.__log.push('previewBox w DOM: '+(!!b2)+' | innerHTML='+(b2?b2.innerHTML.length:'n/a')+' | canvas='+(b2?b2.querySelectorAll('canvas').length:0));
  });
  mo.observe(document.body,{childList:true,subtree:true});
});
await p.setInputFiles('input[type=file]','C:/Users/galaz/Desktop/MeshToStep/frontend/_demo.stl');
await p.waitForTimeout(11000);
console.log('1 plik canvas:',await p.evaluate(()=>document.querySelectorAll('#previewBox canvas').length));
await p.evaluate(()=>window.__log=[]);
await p.setInputFiles('input[type=file]','C:/Users/galaz/Downloads/222222222222222.stl');
await p.waitForTimeout(12000);
console.log('2 plik canvas:',await p.evaluate(()=>document.querySelectorAll('#previewBox canvas').length));
console.log('\nLOG DOM:');(await p.evaluate(()=>window.__log)).slice(-12).forEach(l=>console.log('  '+l));
await b.close();
