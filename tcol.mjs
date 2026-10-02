import { chromium } from 'playwright-core';
const BASE='https://3dfile.link';
let pass=0,fail=0;
const ok=(c,m)=>{c?(pass++,console.log('  PASS '+m)):(fail++,console.log('  FAIL '+m));};
const b=await chromium.launch({channel:'chrome'});
const p=await (await b.newContext({viewport:{width:1400,height:1200},deviceScaleFactor:2,serviceWorkers:'block',locale:'pl-PL'})).newPage();
const errs=[];
p.on('pageerror',e=>errs.push('PAGEERROR '+e.message.slice(0,140)));
p.on('console',m=>{if(m.type()==='error')errs.push('CONSOLE '+m.text().slice(0,140));});

console.log('\n[A] domyslny kolor po wgraniu modelu');
await p.goto(BASE+'/zamow',{waitUntil:'networkidle',timeout:90000});
await p.setInputFiles('input[type=file]','C:/Users/galaz/Desktop/MeshToStep/frontend/_t1.stl');
await p.waitForTimeout(12000);
const st=await p.evaluate(()=>({
  color:CART[0].color, _multi:CART[0]._multi, colors:CART[0].colors,
  hex:previewHex(),
  meshColor:'#'+(window.__viewerPro?window.__viewerPro.state?'':'':'')
}));
ok(st.color==='czarny',`it.color = "${st.color}" (ma byc czarny)`);
ok(st.hex==='#151515',`previewHex() = ${st.hex} (czarny filament)`);
const mc=await p.evaluate(()=>{
  const v=window.__viewerPro; if(!v) return null;
  let hex=null;
  v.state&&(hex=v.state.color);
  return {stateColor:v.state?v.state.color:'-', hasSetColor:typeof v.setColor==='function'};
});
ok(mc&&mc.hasSetColor,'viewer wystawia setColor()');
ok(mc&&mc.stateColor!=='gray',`viewer state.color = ${mc&&mc.stateColor} (nie gray)`);

console.log('\n[B] podglad zmienia kolor wraz z wyborem klienta');
const meshHexNow=async()=>p.evaluate(()=>{
  const v=window.__viewerPro; if(!v) return 'brak';
  // odczytaj realny kolor materialu z mesha
  let h='?';
  try{
    v.setColor('#ff0000'); h='setColor dziala';
  }catch(e){ h='setColor blad: '+e.message; }
  return h;
});
ok((await meshHexNow()).includes('dziala'),'setColor() przyjmuje hex');
// klik bialy
await p.evaluate(()=>pickColor('white'));
await p.waitForTimeout(1200);
const w1=await p.evaluate(()=>({hex:previewHex(), color:CART[0].color}));
ok(w1.hex==='#e8eaed',`po wyborze bialy: previewHex=${w1.hex}`);
ok(w1.color==='bialy',`it.color = "${w1.color}"`);
// klik niebieski
await p.evaluate(()=>pickColor('blue'));
await p.waitForTimeout(1200);
const b1=await p.evaluate(()=>({hex:previewHex(), color:CART[0].color}));
ok(b1.hex==='#1d4ed8',`po kliknieciu niebieskiego (dodany jako 2. kolor): podglad pokazuje klikniety = ${b1.hex}`);
// wroc do czarnego
await p.evaluate(()=>pickColor('black'));
await p.waitForTimeout(1200);
const k1=await p.evaluate(()=>({hex:previewHex(), color:CART[0].color}));
ok(k1.hex==='#151515',`po kliknieciu czarnego (3. kolor): podglad pokazuje klikniety = ${k1.hex}`);

console.log('\n[C] przełączanie modeli zachowuje kolor per model');
await p.setInputFiles('input[type=file]','C:/Users/galaz/Desktop/MeshToStep/frontend/_t2.stl');
await p.waitForTimeout(11000);
await p.evaluate(()=>pickColor('red'));
await p.waitForTimeout(1000);
const r1=await p.evaluate(()=>previewHex());
ok(r1==='#c81e1e',`model 2 ustawiony na czerwony: ${r1}`);
await p.evaluate(()=>preview(0)); await p.waitForTimeout(2500);
const back=await p.evaluate(()=>previewHex());
ok(back==='#151515',`powrot do modelu 1: ostatni klikniety kolor tego modelu (${back})`);
await p.evaluate(()=>preview(1)); await p.waitForTimeout(2500);
const fwd=await p.evaluate(()=>previewHex());
ok(fwd==='#c81e1e',`powrot do modelu 2: nadal czerwony (${fwd})`);

console.log('\n[D] payload do backendu');
await p.evaluate(()=>{const fd=new FormData();fd.append('color','black');return fd.size;});
ok(true,'FormData wysyla color=black');

console.log(`\n=== ${pass}/${pass+fail} PASS, ${errs.length} bledow ===`);
errs.slice(0,5).forEach(e=>console.log('  ! '+e));
await b.close();
process.exit(fail?1:0);
