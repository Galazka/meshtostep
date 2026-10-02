import { chromium } from 'playwright-core';
const BASE='https://3dfile.link';
let pass=0,fail=0;
const ok=(c,m)=>{c?(pass++,console.log('  PASS '+m)):(fail++,console.log('  FAIL '+m));};
const b=await chromium.launch({channel:'chrome'});
const ctx=await b.newContext({viewport:{width:1400,height:1200},deviceScaleFactor:2,serviceWorkers:'block',locale:'pl-PL'});
const p=await ctx.newPage();
const errs=[];
p.on('pageerror',e=>errs.push('PAGEERROR '+e.message.slice(0,140)));
p.on('console',m=>{if(m.type()==='error')errs.push('CONSOLE '+m.text().slice(0,140));});

console.log('\n[A] podglad 3D — kolejne pliki');
await p.goto(BASE+'/zamow',{waitUntil:'networkidle',timeout:90000});
await p.setInputFiles('input[type=file]','C:/Users/galaz/Desktop/MeshToStep/frontend/_demo.stl');
await p.waitForTimeout(11000);
const c1=await p.evaluate(()=>document.querySelectorAll('#previewBox canvas').length);
ok(c1===1,`po 1 pliku: canvas=${c1}`);
await p.setInputFiles('input[type=file]','C:/Users/galaz/Downloads/222222222222222.stl');
await p.waitForTimeout(11000);
const c2=await p.evaluate(()=>document.querySelectorAll('#previewBox canvas').length);
ok(c2===1,`po 2 pliku: canvas=${c2} (wczesniej 0 = pusty podglad)`);
await p.setInputFiles('input[type=file]','C:/Users/galaz/Desktop/MeshToStep/frontend/_demo.stl');
await p.waitForTimeout(11000);
const c3=await p.evaluate(()=>document.querySelectorAll('#previewBox canvas').length);
ok(c3===1,`po 3 pliku: canvas=${c3}`);
const render3=await p.evaluate(()=>{
  const c=document.querySelector('#previewBox canvas');
  if(!c) return -1;
  const g=document.createElement('canvas'); g.width=90;g.height=90;
  const cx=g.getContext('2d'); cx.drawImage(c,0,0,90,90);
  const d=cx.getImageData(0,0,90,90).data; const s=new Set();
  for(let i=0;i<d.length;i+=4) s.add(d[i]+','+d[i+1]+','+d[i+2]);
  return s.size;
});
ok(render3>50,`render ma tresc: ${render3} unikalnych kolorow`);
// przełączanie modeli z listy
await p.evaluate(()=>preview(0)); await p.waitForTimeout(4000);
const s0=await p.evaluate(()=>{const c=document.querySelector('#previewBox canvas');return c?(c.isConnected?'connected':'detached'):'brak';});
ok(s0==='connected',`preview(0): canvas ${s0}`);
await p.evaluate(()=>preview(1)); await p.waitForTimeout(4000);
const s1=await p.evaluate(()=>{const c=document.querySelector('#previewBox canvas');return c?(c.isConnected?'connected':'detached'):'brak';});
ok(s1==='connected',`preview(1): canvas ${s1}`);
await p.locator('#previewBox').screenshot({path:'shots/fix-multi.png'});

console.log('\n[B] zaznaczenie paczkomatu');
await p.evaluate(()=>pickFulfillment('ship'));
await p.waitForFunction(()=>document.querySelectorAll('#paczkomatList .pczrow').length>0,null,{timeout:60000});
await p.waitForTimeout(1500);
ok(await p.evaluate(()=>document.querySelectorAll('#paczkomatList .pczrow.sel').length)===0,'na starcie nic nie zaznaczone');
await p.evaluate(()=>document.querySelectorAll('#paczkomatList .pczrow')[3].click());
await p.waitForTimeout(900);
const sel=await p.evaluate(()=>{
  const row=document.querySelector('#paczkomatList .pczrow.sel');
  if(!row) return null;
  const cs=getComputedStyle(row);
  const plain=getComputedStyle(document.querySelector('#paczkomatList .pczrow:not(.sel)'));
  return {tlo:cs.backgroundColor, zwykłeTlo:plain.backgroundColor, ramka:cs.borderColor,
          badge:!!row.querySelector('.pczsel'), badgeTekst:row.querySelector('.pczsel')?.textContent,
          cien:cs.boxShadow, paddingLeft:cs.paddingLeft};
});
ok(!!sel,'wiersz zaznaczony');
if(sel){
  ok(sel.tlo!==sel.zwykłeTlo,`tlo roznia sie od zwyklego: ${sel.tlo} vs ${sel.zwykłeTlo}`);
  ok(sel.badge&&/wybrany/i.test(sel.badgeTekst||''),`badge "wybrany" widoczny`);
  ok(sel.cien!=='none','cien/obwodka wzmocniona');
  ok(parseInt(sel.paddingLeft)>parseInt(sel.tlo)&&sel.paddingLeft!=='0px',`miejsce na znacznik: ${sel.paddingLeft}`);
}
const nSel=await p.evaluate(()=>document.querySelectorAll('#paczkomatList .pczrow.sel').length);
ok(nSel===1,`dokladnie jeden zaznaczony (${nSel})`);
await p.locator('#paczkomatList').screenshot({path:'shots/fix-sel.png'});
// po zmianie wyboru zaznaczenie przeskakuje
await p.evaluate(()=>document.querySelectorAll('#paczkomatList .pczrow')[7].click());
await p.waitForTimeout(800);
const moved=await p.evaluate(()=>{
  const rows=document.querySelectorAll('#paczkomatList .pczrow');
  return {selIdx:Array.from(rows).findIndex(r=>r.classList.contains('sel')),
          name:document.getElementById('fPaczkomatName').value};
});
ok(moved.selIdx===7,`zaznaczenie przeskoczlo na indeks ${moved.selIdx}`);

// dark mode
console.log('\n[C] dark mode');
await p.evaluate(()=>document.documentElement.setAttribute('data-theme','dark'));
await p.waitForTimeout(600);
const dark=await p.evaluate(()=>{
  const row=document.querySelector('#paczkomatList .pczrow.sel');
  const cs=getComputedStyle(row);
  return {tlo:cs.backgroundColor, badge:!!row.querySelector('.pczsel')};
});
ok(dark.tlo!=='rgba(0, 0, 0, 0)',`dark: tlo zaznaczonego = ${dark.tlo}`);
ok(dark.badge,'dark: badge widoczny');
await p.locator('#paczkomatList').screenshot({path:'shots/fix-sel-dark.png'});

console.log(`\n=== ${pass}/${pass+fail} PASS, ${errs.length} bledow konsoli ===`);
errs.slice(0,6).forEach(e=>console.log('  ! '+e));
await b.close();
process.exit(fail?1:0);
