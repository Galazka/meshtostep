import { chromium } from 'playwright-core';
const b=await chromium.launch({channel:'chrome'});
const p=await (await b.newContext({viewport:{width:1400,height:1200},serviceWorkers:'block',locale:'pl-PL'})).newPage();
p.on('pageerror',e=>console.log('PAGEERROR',e.message.slice(0,200)));
p.on('console',m=>{if(m.type()==='error')console.log('CONSOLE',m.text().slice(0,200));});
await p.goto('https://3dfile.link/zamow',{waitUntil:'networkidle',timeout:90000});
// sluchacz ZANIM cokolwiek
await p.evaluate(()=>{
  window.__ev=[];
  const box=document.getElementById('previewBox');
  new MutationObserver(muts=>{muts.forEach(m=>{if(m.type==='childList')
    window.__ev.push('+'+m.addedNodes.length+'/-'+m.removedNodes.length+' usunieto=['+
      Array.from(m.removedNodes).map(n=>n.tagName+(n.id?'#'+n.id:'')+(n.className?'.'+String(n.className).slice(0,18):'')).join(',')+']');
  })}).observe(box,{childList:true});
});
await p.setInputFiles('input[type=file]','C:/Users/galaz/Desktop/MeshToStep/frontend/_demo.stl');
await p.waitForTimeout(11000);
console.log('1 plik  canvas:',await p.evaluate(()=>document.querySelectorAll('#previewBox canvas').length));
await p.evaluate(()=>window.__ev=[]);
await p.setInputFiles('input[type=file]','C:/Users/galaz/Downloads/222222222222222.stl');
await p.waitForTimeout(12000);
console.log('2 plik  canvas:',await p.evaluate(()=>document.querySelectorAll('#previewBox canvas').length));
console.log('\nMUTACJE:');(await p.evaluate(()=>window.__ev)).forEach(e=>console.log('  '+e));
console.log('\n--- stan ---');
console.log(await p.evaluate(()=>{
  const box=document.getElementById('previewBox');
  const pro=box.__pro;
  const c=pro&&pro.renderer.domElement;
  return JSON.stringify({
    pro:!!pro,
    canvasJestWBox: c?box.contains(c):'brak canvas',
    canvasConnected: c?c.isConnected:'brak',
    canvasParent: c&&c.parentElement?c.parentElement.tagName+'#'+c.parentElement.id:'ORAZWYCHRONIONY',
    canvasRect: c?(r=>Math.round(r.width)+'x'+Math.round(r.height))(c.getBoundingClientRect()):'-',
    boxChildren:Array.from(box.children).map(e=>e.tagName+'#'+e.id),
    boxHTMLlen:box.innerHTML.length
  },null,1);
}));
await b.close();
