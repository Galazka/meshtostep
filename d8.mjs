import { chromium } from 'playwright-core';
const b=await chromium.launch({channel:'chrome'});
const p=await (await b.newContext({viewport:{width:1400,height:1200},serviceWorkers:'block',locale:'pl-PL'})).newPage();
p.on('console',m=>console.log('LOG:',m.text().slice(0,400)));
await p.goto('https://3dfile.link/zamow',{waitUntil:'networkidle',timeout:90000});
await p.evaluate(()=>{
  const box=document.getElementById('previewBox');
  const origRemove=Element.prototype.remove;
  Element.prototype.remove=function(){
    if(this.tagName==='CANVAS'&&box.contains(this)) console.log('=== canvas.remove() ===\n'+new Error().stack);
    return origRemove.call(this);
  };
  const origRC=Node.prototype.replaceChild;
  Node.prototype.replaceChild=function(n,o){
    if(o&&o.tagName==='CANVAS') console.log('=== replaceChild(canvas) ===\n'+new Error().stack);
    return origRC.call(this,n,o);
  };
  const origTA=Element.prototype.removeAttribute;
  Element.prototype.removeAttribute=function(n){
    if(this.tagName==='CANVAS') console.log('=== canvas.removeAttribute('+n+') ===\n'+new Error().stack);
    return origTA.call(this,n);
  };
});
await p.setInputFiles('input[type=file]','C:/Users/galaz/Desktop/MeshToStep/frontend/_demo.stl');
await p.waitForTimeout(11000);
console.log('1 plik canvas:',await p.evaluate(()=>document.querySelectorAll('#previewBox canvas').length));
await p.setInputFiles('input[type=file]','C:/Users/galaz/Downloads/222222222222222.stl');
await p.waitForTimeout(12000);
console.log('2 plik canvas:',await p.evaluate(()=>document.querySelectorAll('#previewBox canvas').length));
await b.close();
