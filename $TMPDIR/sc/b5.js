
var CART=[]; var cur='PLN'; var RATES={PLN:1,USD:4.20,EUR:4.55}; var SYM={PLN:'zł',USD:'$',EUR:'€'};
var MATS={}; var CUR_ACTSYM=1; var selIdx=-1;

function toast(m,ok){var t=document.createElement('div');t.className='toast';t.style.opacity=1;t.textContent=m;var col=(ok===false||ok==='')?'#dc2626':(ok==='w'?'#d97706':'#059669');t.style.background=col;document.body.appendChild(t);setTimeout(function(){t.style.opacity=0;setTimeout(function(){t.remove()},300);},2600);}
var INFCFG={min:10,max:100,base:15,shell:0.35};
var CFG=null;
fetch('/api/pricing/public?t='+Date.now()).then(function(r){return r.json()}).then(function(d){
  if(d&&d.ok){
    CFG=d;
    var n1=document.getElementById('colPriceNote');
    if(n1) n1.innerHTML='1 wybrany kolor jest <b>zawsze w cenie produktu</b> (również kolor specjalny). Dopłata dotyczy tylko wydruku wielokolorowego (2+ kolory): <b>+'+((CFG.multicolor_first_extra_pln!=null)?CFG.multicolor_first_extra_pln:20)+' zł za 1. ekstra</b>, każdy kolejny +'+((CFG.multicolor_next_extra_pln!=null)?CFG.multicolor_next_extra_pln:10)+' zł.';
    // oznacz swatche z dopłatą (widoczne dopiero przy 2+ kolorach)
    var cs=d.color_surcharge||{};
    document.querySelectorAll('#colSwatches .swatch').forEach(function(b){
      var sur=(cs[b.dataset.color]||0);
      if(sur>0){ b.title='Kolor specjalny — dopłata '+sur.toFixed(0).replace('.',',')+' zł dotyczy TYLKO wydruków wielokolorowych (2+ kolory). Przy 1 kolorze jest w cenie.'; }
    });
  }
}).catch(function(){});
fetch('/api/config/infill?t='+Date.now()).then(function(r){return r.json()}).then(function(d){
  if(d&&d.ok){INFCFG={min:d.min,max:d.max,base:d.base,shell:d.shell};
    var rg=document.getElementById('infillRange'); if(rg){rg.min=d.min;rg.max=d.max;rg.value=d.base;}
    CART.forEach(function(it){if(!it.infill)it.infill=d.base;});
    syncInfillUI(); calc();
  }
}).catch(function(){});
function infFactor(f){var b=INFCFG.base/100,sr=INFCFG.shell;return (sr+(f/100)*(1-sr))/(sr+b*(1-sr));}
function setInfill(v){ if(selIdx<0){toast('Najpierw kliknij model w koszyku','');return;}
  v=Math.max(INFCFG.min,Math.min(INFCFG.max,parseInt(v)||INFCFG.base));
  CART[selIdx].infill=v; syncInfillUI(); reprice(selIdx); calc(); }
function syncInfillUI(){
  var rg=document.getElementById('infillRange'); if(!rg)return;
  var it=selIdx>=0?CART[selIdx]:null;
  rg.value=it?(it.infill||INFCFG.base):INFCFG.base;
  var vv=document.getElementById('infillVal'); if(vv)vv.textContent=(it?(it.infill||INFCFG.base):INFCFG.base)+'%';
  var inf=document.getElementById('infillInfo');
  if(inf){ var f=it?(it.infill||INFCFG.base):INFCFG.base;
    if(f>INFCFG.base){ inf.textContent='+'+Math.round((infFactor(f)-1)*100)+'% ceny — więcej materiału i czasu druku'; inf.style.color='#B45309'; }
    else if(f<INFCFG.base){ inf.textContent='−'+Math.round((1-infFactor(f))*100)+'% ceny — lżejszy wydruk'; inf.style.color='#15803d'; }
    else { inf.textContent='Wypełnienie bazowe '+INFCFG.base+'% — w cenie podstawowej'; inf.style.color='var(--muted)'; } }
}
function reprice(i){ var it=CART[i]; if(!it||!it.vol)return;
  var fd=new FormData();
  var _pl2en={czarny:'black',bialy:'white',szary:'gray',czerwony:'red',pomaranczowy:'orange',zolty:'yellow',zielony:'green',niebieski:'blue',fioletowy:'purple',rozowy:'pink',naturalny:'natural',srebrny:'silver',zloty:'gold',weglowy:'carbon',drewno:'wood',przezroczysty:'transparent'};
  var _firstCol=((it.color||'naturalny').split(' + ')[0]||'naturalny').toLowerCase().trim();
  fd.append('material',it.material||'PLA'); fd.append('color',_pl2en[_firstCol]||_firstCol);
  fd.append('quantity',String(it.qty||1)); fd.append('colors',String(it.colors||1));
  fd.append('shipping','pickup'); fd.append('shipping_region','PL');
  fd.append('volume_cm3',String(it.vol)); fd.append('estimated_hours','0');
  if(it.dims)fd.append('dims',String(it.dims));
  fd.append('infill',String(it.infill||INFCFG.base)); fd.append('currency','PLN');
  fetch('/api/calculate?t='+Date.now(),{method:'POST',body:fd}).then(function(r){return r.json()}).then(function(c){
    if(c&&c.ok){ it.price=c.product_subtotal_pln; it.mfee=c.multicolor_fee_pln||0; it.cprem=c.color_premium_pln||0;
      it.grams=c.filament_grams||0; it.hours=c.printing_hours||0; it.atMin=!!c.at_min_print; calc(); }
  }).catch(function(){});
}
function _colHex(c){
  var m={black:'#1e293b',white:'#f8fafc',gray:'#94a3b8',red:'#dc2626',orange:'#ea580c',yellow:'#eab308',green:'#16a34a',blue:'#2563eb',purple:'#7c3aed',pink:'#db2777',silver:'#cbd5e1',gold:'#facc15',carbon:'#0f172a',transparent:'linear-gradient(135deg,#e2e8f0,#f8fafc)'};
  return m[c]||'#cccccc';
}
function sym(){return SYM[cur];}
function cx(v){return Math.ceil(v*2)/2;}
function fmt(v){return v.toFixed(2).replace('.',',')+' '+sym();}

function loadMats(){
  fetch('/api/admin/materials?t='+Date.now()).then(function(r){return r.json();}).then(function(d){
    var box=document.getElementById('mats');
    if(d && d.materials){ Object.keys(d.materials).forEach(function(k){var p=d.materials[k];MATS[k]=k;var desc=(typeof p==='object'&&p.desc)?p.desc:'';var el=document.createElement('div');el.className='mat';el.dataset.mat=k;var p100=''; if(typeof p==='object'&&p.price_kg){ p100=' <b style="color:var(--accent);font-weight:700">'+((+p.price_kg/10).toFixed(1)).replace('.',',')+' zł/100 g · ~'+Math.round(100/(p.density||1.24))+' cm³/100 g</b>'; }
el.innerHTML='<b>'+k+'</b><span>'+desc+p100+'</span>';el.onclick=function(){selectMat(k);};box.appendChild(el);}); }
  });
}
function selectMat(k){ if(selIdx<0){toast('Najpierw kliknij model w koszyku','');return;} CART[selIdx].material=k; CART[selIdx]._matChosen=true; drawCart(); refreshMatSel(); reprice(selIdx); calc(); }
function refreshMatSel(){ var m=(selIdx>=0)?CART[selIdx].material:null; document.querySelectorAll('.mat').forEach(function(x){x.classList.toggle('sel',x.dataset.mat===m);}); document.getElementById('matFor').textContent=(selIdx>=0)?('#'+(selIdx+1)+' · '+(CART[selIdx].model_name||'Model')):'—'; }
  // Podglad 3D ma pokazywac ten sam kolor co zamowienie. Kolor ma wplyw
  // na postrzegana wage bryly, wiec czarne PLA wyglada inaczej niz biale.
  var PREVIEW_HEX={black:'#151515',white:'#e8eaed',gray:'#6b7584',red:'#c81e1e',orange:'#d9600a',
    yellow:'#e3b505',green:'#12873d',blue:'#1d4ed8',purple:'#6d28d9',pink:'#c2185b',
    silver:'#c3cad3',gold:'#d4a017',carbon:'#1f1f1f',transparent:'#dfe4ea'};
  var PL2CODE={czarny:'black',bialy:'white',szary:'gray',czerwony:'red',pomaranczowy:'orange',
    zolty:'yellow',zielony:'green',niebieski:'blue',fioletowy:'purple',rozowy:'pink',
    naturalny:'black',srebrny:'silver',zloty:'gold',grafitowy:'carbon',weglowy:'carbon',
    drewno:'carbon',przezroczysty:'transparent'};
  function previewHex(){ var it=(selIdx>=0)?CART[selIdx]:null; if(!it) return null;
    // Ostatnio klikniety kolor, nie pierwszy z listy — klient chce widziec
    // w podgladzie wlasnie ten kolor, ktory teraz wybiera.
    var first=(it._multi&&it._multi.length)?it._multi[it._multi.length-1]
              :String(it.color||'black').split(' ')[0].toLowerCase();
    first=String(first).toLowerCase();
    // it.color trzyma tekst PL ("czarny + bialy"), _multi trzyma kody — sprowadzamy oba do kodu
    return PREVIEW_HEX[first]||PREVIEW_HEX[PL2CODE[first]]||'#151515'; }
  function syncPreviewColor(){ var v=window.__viewerPro; if(!v||!v.setColor) return;
    var h=previewHex(); if(h) v.setColor(h); }
  function refreshCol(){ var cnt=document.getElementById('colCount'); if(cnt&&selIdx>=0){ cnt.value=String(CART[selIdx].colors||1); } document.querySelectorAll('.swatch').forEach(function(x){var sel=(selIdx>=0)?(CART[selIdx]._multi||[]).indexOf(x.dataset.color)>=0:false;x.classList.toggle('sel',sel);}); document.getElementById('colFor').textContent=(selIdx>=0)?('#'+(selIdx+1)+' · '+(CART[selIdx].model_name||'Model')):'—'; if(typeof renderMulti==='function')renderMulti(); syncPreviewColor(); }
  function applyColor(){ if(selIdx<0){toast('Kliknij model w koszyku','');return;} var cnt=document.getElementById('colCount'); var n=parseInt(cnt?cnt.value:'1'); var it=CART[selIdx]; it.colors=(n>1)?n:1;
    // _multi trzymy KODY kolorów (dataset.color), a it.color trzyma tekst PL.
    // Przy first load it.color bywa polskim napisem, więc odtwarzamy listę kodów
    // z pierwszego słowa, inaczej colPl() przestaje mapować i cena się rozjeżdża.
    if(!it._multi||!it._multi.length){
      var firstPl=String(it.color||'').split(' + ')[0].trim().toLowerCase();
      var firstCode=Object.keys(COL_PL).find(function(k){return COL_PL[k]===firstPl;})||firstPl||'black';
      it._multi=[firstCode]; it._colChosen=true;
    }
    while(it._multi.length>it.colors){ it._multi.pop(); }
    it.color=colPl(it._multi); it._colChosen=true;
    drawCart(); reprice(selIdx); calc(); refreshCol(); renderMulti(); toast('Kolory: '+it.colors+'x',true); }
  var COL_PL={};
  document.querySelectorAll('#colSwatches .swatch').forEach(function(b){
    var code=b.dataset.color; var txt=b.textContent||'';
    var pl=txt.replace(/\s*\(\+?\d+\)\s*$/,'').trim().toLowerCase();
    COL_PL[code]=pl||code;
  });
  // swatche bez polskiej etykiety w DOM — uzupelniamy, inaczej plakietka
  // pokazuje angielski kod (silver/gold) zamiast nazwy
  var _plFallback={natural:'naturalny',silver:'srebrny',gold:'złoty',carbon:'grafitowy',
    transparent:'przezroczysty'};
  for(var _k in _plFallback){ if(!COL_PL[_k]) COL_PL[_k]=_plFallback[_k]; }
  // Przyjmuje tablice kodow kolorow ALBO gotowy string PL ("czarny + bialy").
  // Bez tego zabezpieczenia wywolanie ze stringiem rzucalo "list.map is not
  // a function" i gaslo caly refreshSteps() — naglowki krokow zostawaly puste.
  function colPl(list){
    if(Array.isArray(list)) return list.map(function(c){return COL_PL[c]||c;}).join(' + ');
    return list||'';
  }
  // ── Plakietka koloru w podsumowaniu ──
  // tło = wybrany kolor, ramka = ten sam kolor przyciemniony, tekst czytelny
  // dla jasnych i ciemnych barw (luminacja), skrót PL na wierzchu.
  // Wartości dostrojone pod tekst na plakietce: gray/orange/green przyciemnione,
  // bo surowy odcień z białym tekstem dawał < 4.5:1 (WCAG AA). Środek kółka
  // zostaje w oryginalnym odcieniu swatcha, więc kolor dalej wygląda na swatch.
  var COL_HEX={black:'#151515',white:'#f8fafc',gray:'#6b7584',red:'#dc2626',orange:'#c94c0a',
    yellow:'#eab308',green:'#12873d',blue:'#2563eb',purple:'#7c3aed',pink:'#db2777',
    silver:'#cbd5e1',gold:'#facc15',carbon:'#0f172a',transparent:'#e2e8f0'};
  var COL_SWATCH={gray:'#94a3b8',orange:'#ea580c',green:'#16a34a'};
  function _lum(hex){ var c=hex.replace('#',''); if(c.length<6)c+=c;
    var r=parseInt(c.substr(0,2),16)/255,g=parseInt(c.substr(2,2),16)/255,b=parseInt(c.substr(4,2),16)/255;
    function f(v){ return v<=0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055,2.4); }
    return 0.2126*f(r)+0.7152*f(g)+0.0722*f(b); }
  function _darken(hex,amt){ var c=hex.replace('#',''); if(c.length<6)c+=c;
    var p=function(x){ x=Math.max(0,Math.min(255,Math.round(x*(1-amt)))); return ('0'+x.toString(16)).slice(-2); };
    return '#'+p(parseInt(c.substr(0,2),16))+p(parseInt(c.substr(2,2),16))+p(parseInt(c.substr(4,2),16)); }
  function colorBadge(code,label){
    var hex=COL_HEX[code]||'#cccccc';
    var light=_lum(hex)>0.45;                 // jasne tło -> ciemny tekst
    var txt=light?'#101828':'#ffffff';
    var bd=_darken(hex,light?0.30:0.18);      // ramka = ten sam kolor, nie szara
    var ring=code==='white'||code==='silver'||code==='transparent'?'box-shadow:inset 0 0 0 1px rgba(0,0,0,.18);':'';
    var dot=COL_SWATCH[code]||hex;
    return '<span class="cbadge" style="background:'+hex+';color:'+txt+';border-color:'+bd+';'+ring+'">'
         +'<i class="cdot" style="background:'+dot+';box-shadow:0 0 0 1.5px '+txt+'"></i>'
         +'<span class="ctxt">'+(label||COL_PL[code]||code)+'</span></span>';
  }
  // pozycja w koszyku: lista kodów _multi, a gdy pusta — kod z nazwy PL
  function itemColorCodes(it){
    if(it._multi&&it._multi.length) return it._multi.slice();
    var first=String(it.color||'').split(' + ')[0].trim().toLowerCase();
    var rev={}; for(var k in COL_PL){ rev[COL_PL[k]]=k; }
    return [rev[first]||first||'natural'];
  }
  function renderMulti(){
    var box=document.getElementById('multiInfo'); if(!box) return;
    if(selIdx<0){ box.innerHTML=''; return; }
    var it=CART[selIdx]; var n=it.colors||1; var list=it._multi||[];
    if(n<2){ box.innerHTML='<span style="font-size:12px;color:var(--muted)">Jeden kolor — kliknij swatch aby wybrać.</span> <span style="font-size:11px;color:#B45309">Uwaga: 1 bryła = 1 kolor — nie drukujemy dwóch kolorów na jednym elemencie. Model wielokolorowy = osobne elementy (osobne bryły), każdy w swoim kolorze.</span>'+((it._multi&&it._multi.length)?'':'<div style="font-size:11.5px;color:#b91c1c;margin-top:4px;font-weight:600">⚠ Wybierz kolor wydruku — 1 kolor jest w cenie produktu (nie płacisz za niego extra).</div>'); return; }
    box.innerHTML='<span style="font-size:12.5px">Wybrane kolory ('+list.length+'/'+n+'): <b>'+colPl(list)+'</b></span>'+
          '<span style="font-size:11px;color:var(--muted)"> — klikaj swatche aby dodać/odznaczyć. Ekstra kolor: +'+( (CFG&&CFG.multicolor_first_extra_pln)?CFG.multicolor_first_extra_pln:20 )+' zł, każdy kolejny +'+( (CFG&&CFG.multicolor_next_extra_pln)?CFG.multicolor_next_extra_pln:10 )+' zł.</span>';
  }
  function pickColor(c){
      if(selIdx<0){
        if(CART.length===1){ selIdx=0; } else { toast('Kliknij model w koszyku',''); return; }
      }
      var it=CART[selIdx];
            if(!it._multi||!it._multi.length){
              // PIERWSZY wybrany kolor jest w cenie (rule: 1 bryła = 1 kolor, backend
              // routes_order.py zeruje color_premium gdy colors<=1). Nie seedujemy
              // domyślnego koloru — inaczej pierwsze kliknięcie liczyłoby się jako
              // "drugi kolor" i klient płacił +20 zł za zmianę koloru.
              it._multi=[]; it._colChosen=true;
            }
            // it.colors bywa undefined (item z koszyka nie ustawia tego pola) —
            // wyprowadzamy je z faktycznej liczby wybranych kolorów, inaczej
            // porównanie `>=` nigdy nie przejdzie i dopłata się nie naliczy.
            if(it.colors==null||isNaN(it.colors)){ it.colors=Math.max(1,it._multi.length); }
            var i=it._multi.indexOf(c);
            if(i>=0){
              if(it._multi.length>1){
                it._multi.splice(i,1);
                if(it.colors>it._multi.length){ it.colors=Math.max(1,it._multi.length); var cc0=document.getElementById('colCount'); if(cc0) cc0.value=String(it.colors); }
                it.color=colPl(it._multi); it._colChosen=true;
                drawCart(); reprice(selIdx); calc(); refreshCol(); renderMulti(); toast('Odznaczono: '+colPl([c]),true);
                return;
              } else { toast('Przynajmniej 1 kolor zostaje',''); return; }
            }
            if(it._multi.length>=it.colors){
              // chcesz więcej kolorów niż ustawione → automatycznie podnieś liczbę (cena: +20 zł za 1. ekstra)
              it.colors=it._multi.length+1;
              var cc=document.getElementById('colCount'); if(cc) cc.value=String(it.colors);
              var extra=(it.colors===2)?((CFG&&CFG.multicolor_first_extra_pln)?CFG.multicolor_first_extra_pln:20):((CFG&&CFG.multicolor_next_extra_pln)?CFG.multicolor_next_extra_pln:10);
              toast('Ilość kolorów → '+it.colors+' (+'+extra+' zł)');
            }
      it._multi.push(c);
      it.color=colPl(it._multi); it._colChosen=true;
      drawCart(); reprice(selIdx); calc(); refreshCol(); renderMulti(); toast('Kolory: '+it.color,true);
  }
  /* ===================================================================
     FIRMA / NIP — WYGASZONE (nie usunięte).
     Powód: sprzedaż prowadzona jako działalność nierejestrowana (osoba
     fizyczna, brak NIP). Od 1.04.2026 faktury B2B wymagają NIP + KSeF.
     WŁĄCZENIE JEDNYM KLIKIEM: ustaw env FIRM_ORDERS_ENABLED=true na
     Railway (backend) — frontend czyta flagę z /api/config/features
     i sam pokaże przycisk "Firma" + pola NIP/nazwa/adres do faktury.
     Cała logika firmowa (NIP, nazwa, adres do faktury) zostaje w kodzie.
     =================================================================== */
  var FIRM_ORDERS_ENABLED = false;
  function _firmApply(){
    var b=document.getElementById('custTypeFirm');
    if(b) b.style.display = FIRM_ORDERS_ENABLED ? '' : 'none';
    var fr=document.getElementById('firmRow');
    if(fr && !FIRM_ORDERS_ENABLED) fr.style.display='none';
    var vn=document.getElementById('vatModeNote');
    if(vn) vn.style.display = FIRM_ORDERS_ENABLED ? '' : 'none';
  }
  (function _firmLoad(){
    try{
      fetch('/api/config/features?t='+Date.now()).then(function(r){return r.json();}).then(function(j){
        if(j && typeof j.firm_orders!=='undefined'){ FIRM_ORDERS_ENABLED=!!j.firm_orders; }
        _firmApply();
      }).catch(function(){ _firmApply(); });
    }catch(e){ _firmApply(); }
    if(document.readyState==='loading'){ document.addEventListener('DOMContentLoaded',_firmApply); } else { _firmApply(); }
  })();
  function setCustType(t){
    if(t==='firm' && !FIRM_ORDERS_ENABLED){ try{ toast('Zamówienia firmowe (faktura na NIP) będą dostępne wkrótce',''); }catch(e){} return; }
    var p=document.getElementById('custTypePerson'),f=document.getElementById('custTypeFirm'),fr=document.getElementById('firmRow');
    if(t==='firm'){
      f.style.border='2px solid var(--accent)';f.style.background='#eff6ff';f.style.color='var(--accent)';
      p.style.border='2px solid var(--border)';p.style.background='var(--bg)';p.style.color='var(--muted)';
      fr.style.display='block';
    } else {
      p.style.border='2px solid var(--accent)';p.style.background='#eff6ff';p.style.color='var(--accent)';
      f.style.border='2px solid var(--border)';f.style.background='var(--bg)';f.style.color='var(--muted)';
      fr.style.display='none';
    }
  }
  var FULFILL=''; var PK_SPEED='std'; var LAST_SHIP_TIER='standard';
  function pickFulfillment(mode){
    FULFILL=mode;
    document.getElementById('fulPickupBtn').classList.toggle('sel', mode==='pickup');
    document.getElementById('fulShipBtn').classList.toggle('sel', mode==='ship');
    document.getElementById('pickupBlock').style.display = mode==='pickup'?'block':'none';
    document.getElementById('shipFields').style.display = mode==='ship'?'block':'none';
    var fs=document.getElementById('fShipping');
    if(mode==='pickup'){ fs.value = PK_SPEED==='express'?'pickup_express':'pickup'; }
    else { fs.value = LAST_SHIP_TIER; toggleShipUI(); }
    calc();
  }
  function setPickupSpeed(v){
    PK_SPEED=v;
    document.getElementById('pkStdBtn').classList.toggle('sel', v==='std');
    document.getElementById('pkExpBtn').classList.toggle('sel', v==='express');
    var fs=document.getElementById('fShipping');
    fs.value = v==='express'?'pickup_express':'pickup';
    calc();
  }
  function toggleShipUI(){
      var sel=document.getElementById('fShipping');
      if(FULFILL==='pickup'){ sel.value = PK_SPEED==='express'?'pickup_express':'pickup'; return; }
      var ship=sel.value, row=document.getElementById('pickupRow'), csr=document.getElementById('companyShipRow');
      if(ship==='standard'||ship==='express'){ LAST_SHIP_TIER=ship; row.style.display='block'; csr.style.display='none'; if(!document.getElementById('fPaczkomat').value) searchPaczkomatCity('Gdańsk'); }
      else if(ship==='address'){ LAST_SHIP_TIER='address'; row.style.display='none'; csr.style.display='block'; }
      else { row.style.display='none'; csr.style.display='none'; }
    }
  var PCZ_ITEMS=[], PCZ_MAP=null, PCZ_MARKERS=[], PCZ_SEL=null, PCZ_CITY='', PCZ_ME=null;
  function pczStatus(msg){ var el=document.getElementById('pczStatus'); if(el) el.innerHTML=msg||''; }

  // Jedno pole dla miasta LUB ulicy. InPost wymaga diakrytyk w nazwie
  // miasta, wiec miasto idzie z nasza mapa; ulice filtrujemy sami po
  // stronie serwera, wiec polskie wejscie ("raatza", "Raatza") dziala.
  function searchPaczkomat(q){
    var box=document.getElementById('paczkomatList'); if(!box) return;
    q=(q||'').trim();
    if(q.length<2){ box.innerHTML=''; pczStatus(''); return; }
    var city=_cityFromQuery(q);
    pczStatus('Szukam…');
    fetch('/api/inpost/points?q='+encodeURIComponent(city)+'&street='+encodeURIComponent(q)+'&t='+Date.now())
      .then(function(r){return r.json();}).then(function(d){
        var items=(d&&d.items)||[];
        PCZ_CITY=(d&&d.city)||city;
        if(!items.length){
          // Ulica bez punktow nie moze konczyc sie pustym oknem — pokaz
          // caly katalog miasta i powiedz wprost, czego szukac.
          searchPaczkomatCity(PCZ_CITY);
          pczStatus('Brak paczkomatu na ulicy „'+esc(q)+'”. Poniżej wszystkie punkty w '+esc(PCZ_CITY)+' — kliknij mapę albo listę.');
          return;
        }
        PCZ_ITEMS=items; renderPaczkomaty();
        pczStatus('Znaleziono <b>'+items.length+'</b> punktów na tej ulicy — kliknij, aby wybrać.');
      }).catch(function(){
        box.innerHTML='<div style="color:var(--muted);font-size:13px">Nie udało się pobrać punktów.</div>'; pczStatus('');
      });
  }
  // miasto rozpoznajemy po znanych nazwach; "raatza" to ulica, wiec zostaje
  // miasto z ostatniego wyboru (domyslnie Gdansk)
  var _KNOWN_CITIES={gdansk:1,gdynia:1,sopot:1,krakow:1,wroclaw:1,poznan:1,warszawa:1,katowice:1,lodz:1,szczecin:1,bialystok:1,bydgoszcz:1,lublin:1,olsztyn:1,kielce:1,szczecin:1,czestochowa:1,elblag:1,koszalin:1,opole:1,plock:1,rzeszow:1,slupsk:1,sosnowiec:1,torun:1,zabrze:1,gliwice:1,bytom:1,pomorskie:1};
  function _cityFromQuery(q){
    var n=(q||'').toLowerCase().trim();
    if(_KNOWN_CITIES[n]) return q;
    var first=n.split(' ')[0];
    if(_KNOWN_CITIES[first]) return q;
    return PCZ_CITY||'Gdańsk';
  }
  function searchPaczkomatCity(city, keepStatus){
    PCZ_CITY=city||'Gdańsk';
    var box=document.getElementById('paczkomatList'); if(!box) return;
    if(!keepStatus) pczStatus('Szukam…');
    fetch('/api/inpost/points?q='+encodeURIComponent(PCZ_CITY)+'&t='+Date.now())
      .then(function(r){return r.json();}).then(function(d){
        PCZ_ITEMS=(d&&d.items)||[]; PCZ_CITY=(d&&d.city)||PCZ_CITY;
        renderPaczkomaty();
        if(!keepStatus) pczStatus(PCZ_ITEMS.length
          ? 'Znaleziono <b>'+PCZ_ITEMS.length+'</b> punktów w '+esc(PCZ_CITY)+'. Kliknij mapę albo listę, albo użyj „najbliższy automatycznie”.'
          : 'Brak punktów w tym mieście — spróbuj innego.');
      }).catch(function(){ pczStatus('Nie udało się pobrać punktów.'); });
  }
  function renderPaczkomaty(){
    var box=document.getElementById('paczkomatList'); if(!box) return;
    if(!PCZ_ITEMS.length){ box.innerHTML=''; drawPczMap(); return; }
    // grupuj po ulicy — dla klienta "Raatza" czyta sie lepiej niz kod GDA125M
    var groups={}, order=[];
    PCZ_ITEMS.forEach(function(p){ var k=p.street||'—'; if(!groups[k]){groups[k]=[];order.push(k);} groups[k].push(p); });
    var h='';
    order.sort().forEach(function(k){
      var g=groups[k];
      h+='<div class="pczgroup">'+esc(k)+(g.length>1?' ('+g.length+')':'')+'</div>';
      g.forEach(function(p){ h+=pczRow(p); });
    });
    box.innerHTML=h;
    box.querySelectorAll('button[data-pczbk]').forEach(function(b){
      b.onclick=function(){ selectPaczkomat(b.getAttribute('data-pczbk')); };
    });
    drawPczMap();
  }
  function pczRow(p){
    var h='<b>'+esc(String(p.street||''))+' '+esc(String(p.building_number||''))+'</b>'+
      ' <span class="pczcode">'+esc(String(p.name||''))+'</span>'+
      '<br><span class="pczsub">'+esc(String(p.post_code||''))+' '+esc(String(p.city||''))+
      (p.distance_m!=null?' · '+p.distance_m+' m':'')+'</span>';
    var sel=(p.name===PCZ_SEL)?'<span class="pczsel">wybrany</span>':'';
    return '<button type="button" class="pczrow'+(p.name===PCZ_SEL?' sel':'')+'" data-pczbk="'+esc(String(p.name||''))+'">'+h+sel+'</button>';
  }
  function selectPaczkomat(name){
    var p=null;
    PCZ_ITEMS.forEach(function(x){ if(x.name===name) p=x; });
    if(!p) return;
    PCZ_SEL=name;
    document.getElementById('fPaczkomatName').value=p.name;
    document.getElementById('fPaczkomatAddr').value=String(p.street||'')+' '+String(p.building_number||'')+', '+String(p.post_code||'')+' '+String(p.city||'');
    document.getElementById('fPaczkomatLat').value=(p.lat==null?'':p.lat);
    document.getElementById('fPaczkomatLon').value=(p.lon==null?'':p.lon);
    document.getElementById('fPaczkomat').value=p.street+' '+String(p.building_number||'')+' ('+p.name+')';
    pczStatus('Wybrano <b>'+esc(p.street)+' '+esc(String(p.building_number||''))+'</b> · '+esc(p.name));
    boxSelectedPcz();
    renderPaczkomaty();
    drawPczMap();
  }
  function boxSelectedPcz(){
    var box=document.getElementById('paczkomatList'); if(!box) return;
    box.querySelectorAll('button[data-pczbk]').forEach(function(b){
      b.classList.toggle('sel', b.getAttribute('data-pczbk')===PCZ_SEL);
    });
  }
  // "wybierz najblizszy automatycznie": pozycja z przegladarki, serwer
  // sortuje po prawdziwej odleglosci — to nie jest "pierwszy z listy".
  function autoNearestPaczkomat(){
    var city=PCZ_CITY||'Gdańsk';
    if(!navigator.geolocation){
      pczStatus('Ta przeglądarka nie udostępnia lokalizacji. Wybierz z listy albo kliknij mapę.');
      searchPaczkomatCity(city, true); return;
    }
    pczStatus('Szukam Twojej lokalizacji…');
    navigator.geolocation.getCurrentPosition(function(pos){
      var la=pos.coords.latitude, lo=pos.coords.longitude;
      fetch('/api/inpost/points?q='+encodeURIComponent(city)+'&lat='+la+'&lon='+lo+'&limit=1&t='+Date.now())
        .then(function(r){return r.json();}).then(function(d){
          var it=((d&&d.items)||[])[0];
          if(!it){
            pczStatus('Nie znalazłem punktów w pobliżu — sprawdź miasto.');
            searchPaczkomatCity(city, true); return;
          }
          PCZ_ITEMS=[it]; renderPaczkomaty(); selectPaczkomat(it.name);
          toast('Najbliższy punkt: '+it.street+' ('+(it.distance_m!=null?it.distance_m+' m':'?')+')', true);
        });
    }, function(){
      pczStatus('Nie udało się ustalić lokalizacji — wybierz z listy albo wpisz miasto. Dopuszcz dostęp do lokalizacji w przeglądarce, albo kliknij punkt na mapie.');
      searchPaczkomatCity(city, true);
    }, {enableHighAccuracy:true, timeout:9000});
  }
  function locateMePaczkomat(){
    if(!navigator.geolocation){ pczStatus('Ta przeglądarka nie udostępnia lokalizacji.'); return; }
    navigator.geolocation.getCurrentPosition(function(pos){
      PCZ_ME=[pos.coords.latitude,pos.coords.longitude];
      pczStatus('Twoja lokalizacja: '+PCZ_ME[0].toFixed(4)+', '+PCZ_ME[1].toFixed(4));
      autoNearestPaczkomat();
    }, function(){ pczStatus('Brak dostępu do lokalizacji.'); });
  }
  function drawPczMap(){
    var el=document.getElementById('pczMap');
    if(!el||typeof L==='undefined'||!window.L) return;
    var pts=PCZ_ITEMS.filter(function(p){return p.lat!=null&&p.lon!=null;});
    if(!pts.length){ el.style.display='none'; return; }
    el.style.display='block';
    if(!PCZ_MAP){
      PCZ_MAP=L.map(el,{scrollWheelZoom:false}).setView([54.3520,18.6466],12);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap'}).addTo(PCZ_MAP);
    }
    PCZ_MARKERS.forEach(function(m){ PCZ_MAP.removeLayer(m); });
    PCZ_MARKERS=[];
    pts.forEach(function(p){
      var sel=p.name===PCZ_SEL;
      var m=L.marker([p.lat,p.lon],{icon:L.divIcon({className:'',html:
        '<span style="display:block;width:'+(sel?18:13)+'px;height:'+(sel?18:13)+'px;border-radius:50%;background:'+(sel?'#2563eb':'#ffffff')+';border:2.5px solid #1d4ed8;box-shadow:0 1px 4px rgba(0,0,0,.35)"></span>'})});
      m.bindPopup('<b>'+esc(p.street)+' '+esc(String(p.building_number||''))+'</b><br>'+esc(p.post_code)+' '+esc(p.city)+'<br><span class="pczcode">'+esc(p.name)+'</span>');
      m.on('click',function(){ selectPaczkomat(p.name); });
      m.addTo(PCZ_MAP); PCZ_MARKERS.push(m);
    });
    if(PCZ_ME) L.circleMarker(PCZ_ME,{radius:7,color:'#16a34a',fillColor:'#16a34a',fillOpacity:.9}).addTo(PCZ_MAP).bindPopup('Ty');
    var all=pts.map(function(p){return [p.lat,p.lon];});
    if(PCZ_ME) all.push(PCZ_ME);
    PCZ_MAP.fitBounds(L.latLngBounds(all).pad(0.15));
  }
function drawCart(){
  var c=document.getElementById('cart');
  if(!CART.length){ c.innerHTML='<div class="cart-empty">Koszyk pusty — prześlij model powyżej (możesz dodać kilka).</div>'; return; }
  var h='';
    CART.forEach(function(it,i){
      var active = i===selIdx;
      var colHex = _colHex(it.color);
      h+='<div class="item" style="'+(active?'outline:2px solid '+MY_ACC()+';': '')+'cursor:pointer" onclick="preview('+i+')">'+
          '<div class="thumb '+(active?'active':'')+'" title="Podgląd 3D">🖼</div>'+
          '<div class="meta"><div class="nm">'+esc(it.model_name||('Model '+(i+1)))+'</div>'+
          '<div class="sub"><span style="display:inline-flex;align-items:center;gap:6px">'+(it.material||'PLA')+' · '+(it.infill||INFCFG.base)+'% wypełn. · '+it.qty+' szt · '+(it.vol?it.vol.toFixed(1):'?')+' cm³</span></div>'+
          '<div class="sub" style="display:flex;align-items:center;gap:6px"><span style="width:14px;height:14px;border-radius:50%;background:'+colHex+';border:1px solid rgba(0,0,0,.15);display:inline-block"></span><span>'+esc(it.color||'—')+'</span><span style="color:var(--muted)">'+(it.colors&&it.colors>1?(' · '+it.colors+' kol.'):'')+'</span></div></div>'+
          '<div style="display:flex;gap:8px;align-items:center"><div class="qty">'+
          '<button onclick="event.stopPropagation();chg('+i+',-1)">−</button><span>'+it.qty+'</span><button onclick="event.stopPropagation();chg('+i+',1)">+</button></div>'+
          '<button class="del" onclick="event.stopPropagation();del('+i+')">✕</button></div></div>';
    });
    c.innerHTML=h;
}
function MY_ACC(){return '#2563eb';}
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function chg(i,d){ CART[i].qty=Math.max(1,CART[i].qty+d); drawCart(); reprice(i); calc(); }
function del(i){ CART.splice(i,1); if(selIdx>=CART.length) selIdx=CART.length-1; if(selIdx===-1) selIdx=-1; drawCart(); refreshMatSel(); calc(); if(!CART.length) document.getElementById('previewBox').innerHTML='Wybierz model z listy, żeby zobaczyć go tutaj.'; }

document.getElementById('fileInput').addEventListener('change',function(){ var f=this.files[0]; if(!f)return; var fd=new FormData(); fd.append('file',f);
  var note=document.createElement('div'); document.getElementById('loading').style.display='flex';
  fetch('/api/estimate?t='+Date.now(),{method:'POST',body:fd}).then(function(r){return r.json();}).then(function(d){
    document.getElementById('loading').style.display='none';
    var vol=d.volume_cm3||0;
    var estPrice=(d.estimate && d.estimate.product_subtotal)?d.estimate.product_subtotal:0;
    var item={job_id:null,job_uuid:d.uuid||null,model_name:f.name,material:'PLA',color:'czarny',qty:1,infill:INFCFG.base,vol:vol,dims:d.dimensions||'',desc:'',price:estPrice,_bytes:null};
    // read local bytes for instant 3D preview (no server round-trip)
    f.arrayBuffer().then(function(buf){
      item._bytes=new Uint8Array(buf);
      try{ if(selIdx===CART.length-1 && typeof window.__local3d!=='undefined' && typeof local3dPreview==='function'){ local3dPreview(CART.length-1); } }catch(e){}
    }).catch(function(){});
    function local3dPreview(i){ if(window.__local3d&&CART[i]&&CART[i]._bytes){ window.__local3d.renderBytes(CART[i].model_name,CART[i]._bytes,'previewBox'); } }
    // always get a hostable job for 3D preview (public /e/{job_id})
    var fd3=new FormData(); fd3.append('mode','auto'); fd3.append('file',f);
    fetch('/api/convert?t='+Date.now(),{method:'POST',body:fd3}).then(function(r){return r.json();}).then(function(cv){ if(cv&&cv.job_id){ item.job_id=cv.job_id; if(selIdx===CART.length-1){ preview(CART.length-1); } } }).catch(function(){});
    var fd2=new FormData(); fd2.append('material','PLA'); fd2.append('color','black'); fd2.append('quantity','1'); fd2.append('shipping','pickup'); fd2.append('shipping_region','PL'); fd2.append('volume_cm3',String(vol)); fd2.append('estimated_hours','0'); if(d.dimensions)fd2.append('dims',String(d.dimensions)); fd2.append('infill',String(INFCFG.base)); fd2.append('currency','PLN');
    fetch('/api/calculate?t='+Date.now(),{method:'POST',body:fd2}).then(function(r){return r.json();}).then(function(c){if(c.ok){item.price=c.product_subtotal_pln; item.mfee=0; if(!item.desc) item.desc=''; calc();}}).catch(function(){});
    CART.push(item); selIdx=CART.length-1; drawCart(); refreshMatSel(); calc();
    if(item.vol) preview(selIdx); toast('Dodano: '+f.name,true);
  }).catch(function(){document.getElementById('loading').style.display='none';toast('Błąd przetwarzania pliku','');});
  this.value='';
});

// Przycisk "Zmien" w podsumowaniu: otworz krok, w ktorym da sie realnie zmienic
// wybor tego modelu, i przewin do niego. Osobna funkcja, bo preview() renderuje
// koszyk przy kazdej zmianie — scrollowalibysmy klienta w nieskonczonosc.
function gotoEditStep(i){
  var it=CART[i]; if(!it || typeof openStep!=='function') return;
  var n=it._matChosen?3:2;
  openStep(n);
  var t=document.getElementById('accb'+n);
  if(t) t.scrollIntoView({behavior:'smooth',block:'center'});
}

// ── START ACCORDION ────────────────────────────────────────────
// Krok 1 otwarty na wejsciu; kolejny otwiera sie sam po wypelnieniu poprzedniego.
function _accStart(){
  if(typeof refreshSteps==='function') refreshSteps();
  if(!document.querySelector('.acc.open')) openStep(1);
}
if(document.readyState==='loading'){ document.addEventListener('DOMContentLoaded',_accStart); }
else { _accStart(); }
// ── ACCORDION KROKÓW ────────────────────────────────────────────
// Jedna sekcja otwarta naraz. Pozycja w stepach jest zawsze jawna,
// wiec klient widzi gdzie jest i co juz zaznaczyl.
function _accEls(n){ return {sec:document.getElementById('acc'+n), body:document.getElementById('accb'+n), head:document.querySelector('#acc'+n+' .acc-h')}; }
function openStep(n){ for(var i=1;i<=4;i++){ if(i===n) continue; closeStep(i); } var e=_accEls(n); if(!e.sec) return; e.sec.classList.add('open'); if(e.head) e.head.setAttribute('aria-expanded','true'); }
function closeStep(n){ var e=_accEls(n); if(!e.sec) return; e.sec.classList.remove('open'); if(e.head) e.head.setAttribute('aria-expanded','false'); }
function stepIsOpen(n){ var e=_accEls(n); return !!(e.sec && e.sec.classList.contains('open')); }
function toggleStep(n){ stepIsOpen(n)?closeStep(n):openStep(n); }

// Nastepny krok = pierwszy z wybranych, ktory nie ma jeszcze pelnej odpowiedzi.
var _lastStepDone={};
function _stepDone(n){
  if(n===1) return CART.length>0;
  if(n===2){ if(selIdx<0) return false; var it=CART[selIdx]; return !!(it._matChosen && it.material); }
  if(n===3){ if(selIdx<0) return false; var it=CART[selIdx]; return !!(it._colChosen && (it._multi&&it._multi.length)); }
  if(n===4) return false;
  return false;
}
function _stepNext(){ for(var i=1;i<=4;i++){ if(!_stepDone(i)) return i; } return 4; }
function openNextStep(){ openStep(_stepNext()); }

// Podsumowanie wyboru w naglowku kazdego kroku.
function refreshSteps(){
  // Gdy wskazany krok wlasnie sie zrobil kompletny, otworz nastepny
  // (ale nie przy kazdym renderze — tylko przy zmianie stanu kompletnosci).
  var wasDone=_lastStepDone||{};
  var changed=false, sel0=selIdx>=0?CART[selIdx]:null;
  for(var i=1;i<=4;i++){
    var d=_stepDone(i);
    if(d && !wasDone[i]) changed=true;
    wasDone[i]=d;
  }
  _lastStepDone=wasDone;
  if(changed){
    var nx=_stepNext();
    if(nx) openStep(nx);
  }

  var sel=selIdx>=0?CART[selIdx]:null;
  var vals={};
  vals[1]=CART.length?(CART.length+' × model'):'—';
  vals[2]=sel&&sel.material?sel.material:'—';
  if(sel){
      var c=sel.colors||1;
      // it.color to string PL ("czarny + bialy"), a colPl() oczekuje tablicy kodow.
      // Uzywaj _multi (kody) jesli jest — inaczej colPl() rzuca TypeError
      // "list.map is not a function" i cale refreshSteps() pada, zostawiajac
      // wszystkie naglowki puste.
      var nm=(sel._multi&&sel._multi.length)?colPl(sel._multi):(sel.color||'—');
      if(c>1) nm=c+' kolory';
      vals[3]=(nm||'—')+(sel.infill?(' · '+sel.infill+'% wypełn.'):'');
    } else vals[3]='—';
  vals[4]='Dane i płatność';
  for(var i=1;i<=4;i++){
    var el=document.getElementById('accs'+i), sec=document.getElementById('acc'+i);
    if(!el||!sec) continue;
    el.textContent=vals[i];
    sec.classList.toggle('done', _stepDone(i));
    sec.classList.toggle('empty', !_stepDone(i));
  }
}

function calc(){
  if(typeof refreshSteps==='function') refreshSteps();
  var box=document.getElementById('sumBody'), empty=document.getElementById('sumEmpty');
  var btn=document.getElementById('submitBtn');
  // Przycisk "Zaplac" renderowany jest wewnatrz panelu podsumowania, wiec
  // przy pierwszym wywolaniu calc() (przed renderem) nie istnieje jeszcze.
  // Pobieramy go na nowo PO wstawieniu innerHTML, inaczej null.
  if(!CART.length){ box.style.display='none'; empty.style.display='block'; if(btn){btn.disabled=true;btn.textContent='Zaplac';} var cb0=document.getElementById('ctaTot'); if(cb0)cb0.textContent='\u2014'; return; }
  var rate=RATES[cur]||1;
  var productsPLN=0, colorExt=0, rowsHTML='';
  var COUPON_PLN=0; try{COUPON_PLN=(window.__COUPON&&window.__COUPON.pln)||0;}catch(e){}
  CART.forEach(function(it, idx){
    // it.price = produkt z /api/calculate ( JUŻ z dopłatami i infill ) — nie dodajemy nic
    var prn=(+it.price)||0;
    productsPLN += prn;
    colorExt += (+it.mfee)||0;
    var c=it.colors||1; var colTag=(c>1)?' · '+c+' kol.':'';
    var infTag=(it.infill&&it.infill!==INFCFG.base)?' · '+it.infill+'% wypełn.':'';
    var unit = it.qty>1 ? ' × '+it.qty+' szt' : '';
    rowsHTML+='<div class="summary-row sumitem" style="cursor:pointer" onclick="preview('+idx+');refreshCol()"><span style="font-weight:600">'+esc(it.model_name||('Model '+(idx+1)))+unit+'</span><span>'+fmt(prn/rate)+'</span></div>';
    var gl=''; if(it.grams){ gl=(+it.grams).toFixed(1).replace('.',',')+' g'; if(it.hours) gl+=' · ~'+(+it.hours).toFixed(1).replace('.',',')+' h'; }
    var meta=[];
    meta.push('<span class="chip">'+esc(it.material||'PLA')+'</span>');
    var cCodes=itemColorCodes(it);
    cCodes.forEach(function(c){ meta.push(colorBadge(c)); });
    if(it.colors>1) meta.push('<span class="chip chipmin">'+it.colors+' kolory</span>');
    if(it.vol) meta.push('<span class="chip">'+it.vol.toFixed(1).replace('.',',')+' cm³</span>');
    if(it.dims) meta.push('<span class="chip">'+esc(String(it.dims).replace(/\s*mm\s*$/i,''))+' mm</span>');
    if(gl) meta.push('<span class="chip">'+gl+'</span>');
    if(it.atMin) meta.push('<span class="chip chipmin">cena minimalna</span>');
    // Jednostkowa liczona Z pozycji (prn/q), nigdy przez mnozenie — it.price
    // z /api/calculate juz zawiera quantity. Pokazujemy "jedn x qty = razem"
    // tylko gdy mnozenie faktycznie odtwarza pozycje; min_print potrafi ja
    // przyciac, wowczas mnozenie by klamalo, wiec idzie "srednio ... / szt".
    var q=it.qty||1, mathTxt='';
    if(q>1){
      // cx() rounds UP to 0.50, which would print 9,90 as 10,00 and then
      // 10,00 x 5 = 50 against a 49,50 line. So the unit price keeps its real
      // 2 decimals, and the multiplication is shown only when it reconciles
      // exactly at those decimals — otherwise it would not add up on paper.
      var perR=Math.round((prn/q)/rate*100)/100;
      var recon=Math.abs(perR*q-prn/rate)<0.005;
      mathTxt = recon
        ? '<span class="summath">'+fmt(perR)+' × '+q+' szt = <b>'+fmt(prn/rate)+'</b></span>'
        : '<span class="summath">średnio '+fmt(perR)+' / szt</span>';
    }
    rowsHTML+='<div class="sumblock"><div class="summeta">'+meta.join('')+'</div>'+mathTxt+
      '<button class="sumedit" onclick="event.stopPropagation();preview('+idx+');refreshCol();gotoEditStep('+idx+')">Zmień</button></div>';
  });
  var shipBase=(CFG&&CFG.shipping_tiers)||{standard:{PL:16.49,EU:35,GLOBAL:55},express:{PL:33,EU:70,GLOBAL:110},pickup:{PL:0,EU:0,GLOBAL:0},pickup_express:{PL:19,EU:19,GLOBAL:19}};
  var PACK=(CFG&&CFG.packing_pln!=null)?+CFG.packing_pln:3;
  var MINP=(CFG&&CFG.min_print_pln!=null)?+CFG.min_print_pln:10;
  var SOMAX=(CFG&&CFG.small_order_max_product_pln!=null)?+CFG.small_order_max_product_pln:40;
  var SOFLAT=(CFG&&CFG.small_order_ship_flat_pln!=null)?+CFG.small_order_ship_flat_pln:9.9;
  var FREEMIN=(CFG&&CFG.free_shipping_min_pln!=null)?+CFG.free_shipping_min_pln:200;
  var PEFEE=(CFG&&CFG.pickup_express_fee_pln!=null)?+CFG.pickup_express_fee_pln:19;
  var reg=document.getElementById('fRegion').value, ship=document.getElementById('fShipping').value;
  var isPickup = ship==='pickup', isPkExp = ship==='pickup_express';
  var base=(shipBase[ship]||shipBase.standard)[reg]||0;
  var shippingPLN = isPickup ? 0 : isPkExp ? PEFEE : (base+PACK);
  var basePrint = Math.max(MINP, productsPLN); // minimum druku z cennika admina
    var adjPLN = basePrint;
    var smallOrder = shippingPLN>0 && !isPkExp && adjPLN<SOMAX;
    if(smallOrder) shippingPLN = Math.min(shippingPLN, SOFLAT);
    var freeShip = !isPickup && !isPkExp && adjPLN>=FREEMIN && shippingPLN>0;
    if(freeShip) shippingPLN=0;
  if(COUPON_PLN>adjPLN)COUPON_PLN=adjPLN;
    var totalPLN = adjPLN + shippingPLN - COUPON_PLN;
var discLine = COUPON_PLN>0 ? '<div class="summary-row"><span>Rabat '+(window.__COUPON.code||'')+'</span><span style="color:#15803d;font-weight:700">−'+fmt(cx(COUPON_PLN/rate))+'</span></div>' : '';
  // it.price from /api/calculate ALREADY includes multicolor_fee — never add it twice.
  // Show it as a breakdown line inside the total, not as a separate charge.
  var _rawAdj=adjPLN+shippingPLN-COUPON_PLN, _rounded=cx(_rawAdj/rate), _raw=Math.round(_rawAdj/rate*100)/100;
  var roundLine = (Math.abs(_rounded-_raw)>=0.005)
    ? '<div class="summary-row sumsub sumround"><span>okrąglenie do pełnej 0,50 zł</span><span>'+fmt(_rounded-_raw)+'</span></div>' : '';
  var colorLine = colorExt>0 ? '<div class="summary-row sumsub"><span>w tym dopłata za kolory</span><span>'+fmt(colorExt/rate)+'</span></div>' : '';
  var shipLabel = isPickup ? 'Odbiór osobisty (Gdańsk Osowa)' : isPkExp ? 'Ekspres przy odbiorze (≤2 dni)' : freeShip ? 'Wysyłka — GRATIS (≥'+FREEMIN+' zł)' : smallOrder ? 'Wysyłka + pakowanie — małe zamówienie (flat '+fmt(SOFLAT)+')' : 'Wysyłka + pakowanie';
  // cena ostateczna (bez dopłat po fakcie) — bez rozbicia netto/VAT
  var total=cx(totalPLN/rate);
  var brutto=total;
  var nModel=CART.length;
  var modelWord = nModel===1 ? '1 model' : (nModel>=2&&nModel<=4 ? nModel+' modele' : nModel+' modeli');
  box.innerHTML='<div class="sumhead">Co drukujemy</div>'+
    '<div class="sumlist">'+rowsHTML+'</div>'+
    '<div class="sumcalc">'+
      '<div class="summary-row sumsub2"><span>Wszystkie modele</span><span>'+fmt(basePrint/rate)+'</span></div>'+roundLine+
      '<div class="summary-row"><span>'+shipLabel+'</span><span>'+(shippingPLN===0?'gratis':fmt(shippingPLN/rate))+'</span></div>'+
      colorLine+discLine+
      '<div class="summary-row sumsum"><span>Razem</span><span>'+fmt(brutto)+'</span></div>'+
    '</div>'+
    '<button class="paybtn" id="submitBtn" onclick="submitOrder()">Zamów i zapłać '+fmt(brutto)+'</button>'+
    '<div class="sumnote">Cena ostateczna — rachunek dostaniesz e-mailem. Płatność: Stripe (karta lub BLIK).</div>';
  empty.style.display='none'; box.style.display='block';
  btn=document.getElementById('submitBtn');
  if(btn){ btn.disabled=false; btn.textContent='Zapłać '+fmt(brutto); }
  try{ var cb=document.getElementById('ctaTot'); if(cb)cb.textContent=fmt(brutto); }catch(e){}
  var vn=document.getElementById('vatNote'); if(vn) vn.textContent='Do zamówienia dołączamy rachunek. Nie doliczamy żadnych opłat później.';
  var fn=document.getElementById('fxNote'); if(fn) fn.textContent = cur==='PLN'?'Waluta: PLN':'Waluta: '+cur+' · kurs 1 '+cur+' = '+(1/rate).toFixed(4)+' PLN';
}

function applyCoupon(silent){
  var code=(document.getElementById('fCode').value||'').trim().toUpperCase();
  var btn=document.getElementById('codeBtn');
  var info=document.getElementById('couponInfo');
  if(!code){ window.__COUPON=null; if(info)info.textContent=''; calc(); return; }
  var sub=0; CART.forEach(function(it){sub+=(+it.price)||0;});
  var fd=new FormData(); fd.append('code',code); fd.append('amount',String(Math.max(sub,10)));
  fetch('/api/discount/validate?t='+Date.now(),{method:'POST',body:fd}).then(function(r){return r.json()}).then(function(d){
    if(d&&d.valid){ window.__COUPON={code:code,pln:d.discount_pln};
      if(btn){btn.textContent='✓ '+code;btn.style.background='#15803d';btn.style.color='#fff';btn.style.borderColor='#15803d';}
      if(info){info.innerHTML='<span style="color:#15803d;font-weight:700">OK — odjęte '+d.discount_pln.toFixed(2).replace('.',',')+' zł</span>';}
      if(!silent) toast('Kupon zastosowany',true);
    } else { window.__COUPON=null;
      if(btn){btn.textContent=(document.documentElement.lang==='en')?'Apply':'Zastosuj';btn.style.background='';btn.style.color='';btn.style.borderColor='';}
      if(info)info.innerHTML='<span style="color:#b91c1c">'+(d&&d.message?'Kod odrzucony: '+d.message:'Kod nieprawidłowy lub wygasły')+'</span>';
    }
    calc();
  }).catch(function(){ if(info)info.textContent='Sprawdź połączenie'; });
}
(function(){ var ci=document.getElementById('fCode'); if(ci){ var tmr=null; ci.addEventListener('input',function(){ clearTimeout(tmr); if(!ci.value.trim()){ window.__COUPON=null; var b=document.getElementById('codeBtn'); if(b){b.textContent='Zastosuj';b.style.background='';} var i2=document.getElementById('couponInfo'); if(i2)i2.textContent=''; calc(); return;} tmr=setTimeout(function(){ applyCoupon(true); },500); }); } })();

function preview(i){
  selIdx=i; drawCart(); refreshMatSel(); syncInfillUI(); if(typeof refreshCol==='function') refreshCol();
  // "Zmien" w podsumowaniu ma prowadzic do kroku, w ktorym da sie faktycznie
    // zmienic wybor dla tego modelu. Decyduje swiadomy wybor uzytkownika
    // (_matChosen), nie samo istnienie pola material — inaczej kazde renderowanie
    // koszyka otwieralo krok 3 i przewijalo do niego, omijajac krok 2.
    // scrollIntoView tylko przy jawnym wywolaniu (button "Zmien"), nie przy renderze.
    if(typeof openStep==='function'){
      var i1=CART[i];
      openStep(i1 && i1._matChosen ? 3 : 2);
    }
  var it=CART[i], box=document.getElementById('previewBox');
  if(it && it._bytes && typeof window.__local3d!=='undefined'){ try{ window.__local3d.renderBytes(it.model_name,it._bytes,'previewBox'); syncPreviewColor(); return; }catch(e){ if(e&&e.message)console.warn('renderBytes:',e.message); } }
  if(it.job_id){
    if(box.__pro){ box.__pro.loadBytes(it.model_name||'model.stl', it._bytes||new ArrayBuffer(0)); syncPreviewColor(); return; }
    box.innerHTML='<iframe class="preview-iframe" src="/e/'+it.job_id+'" frameborder="0" allowfullscreen></iframe>';
  } else {
    box.innerHTML='<div style="padding:22px;text-align:center">📦 <b>'+esc(it.model_name||'Model')+'</b><br><span style="color:var(--muted);font-size:13px">'+(it.vol?it.vol.toFixed(1)+' cm³': '')+(it.dims?' · '+it.dims:'')+'</span><br><span style="color:#2563eb;font-size:12px">'+esc(it.material||'PLA')+' · kolor '+esc(it.color||'czarny')+' · '+it.qty+' szt</span><br><br><span style="color:var(--muted);font-size:12px">Wgrywam podgląd 3D… (pozwól chwilę konwersji)</span></div>';
  }
}

function buildCur(){
  var box=document.getElementById('curBox'); box.innerHTML='';
  Object.keys(RATES).forEach(function(c){ var b=document.createElement('button'); b.className='cur-btn'+(c===cur?' active':''); b.textContent=c; b.onclick=function(){cur=c;document.getElementById('curBox').innerHTML='';buildCur();calc();}; box.appendChild(b); });
}

function submitOrder(){
  var nm=document.getElementById('fName').value.trim(), em=document.getElementById('fEmail').value.trim();
  if(!FULFILL){ toast('Najpierw wybierz: odbiór osobisty czy wysyłka',''); document.getElementById('fulfillStep').scrollIntoView({behavior:'smooth'}); return; }
  if(!nm||!em){ toast('Wpisz imię i nazwisko oraz email',''); return; }
  var ph=document.getElementById('fPhone').value.trim();
  if(!ph){ toast(FULFILL==='pickup'?'Do odbioru osobistego potrzebny jest numer telefonu (SMS o gotowości)':'Podaj numer telefonu — kurier/InPost wyśle kod',''); document.getElementById('fPhone').focus(); return; }
  if(!CART.length){ toast('Dodaj co najmniej jeden model',''); return; }
  for(var ci=0;ci<CART.length;ci++){ var _it=CART[ci];
    if(!_it._multi||!_it._multi.length){ toast('Wybierz kolor dla: '+(_it.model_name||'Model #'+(ci+1))+' — 1 kolor jest w cenie produktu',''); if(typeof preview==='function')preview(ci); if(typeof refreshCol==='function')refreshCol(); document.getElementById('colSwatches').scrollIntoView({behavior:'smooth',block:'center'}); return; } }
  if(FULFILL==='ship' && (!document.getElementById('fAddr').value.trim() || !document.getElementById('fCity').value.trim())){ toast('Podaj adres i miasto dostawy',''); document.getElementById('fAddr').focus(); return; }
  var shipSel=document.getElementById('fShipping').value;
    /* FIRMA OFF: pola NIP/nazwa nie są wysyłane do backendu dopóki FIRM_ORDERS_ENABLED=false */
    var nip=FIRM_ORDERS_ENABLED?((document.getElementById('fNip')||{}).value||''):'';
    var comp=FIRM_ORDERS_ENABLED?((document.getElementById('fCompany')||{}).value||''):'';
    var shipAddr=document.getElementById('fAddr').value.trim();
    if(shipSel==='address'){
      var dest=(document.getElementById('fCompanyShip')||{}).value.trim();
      if(dest){ shipAddr=(shipAddr?shipAddr+', ':'')+'DOSTAWA NA ADRES: '+dest; }
      else { shipAddr=(shipAddr?shipAddr+', ':'')+'DOSTAWA KURIEREM NA ADRES'; }
    } else {
      var pczk=(document.getElementById('fPaczkomatName')||{}).value||document.getElementById('fPaczkomat').value.trim();
      if(pczk){ shipAddr=(shipAddr?shipAddr+', ':'')+'Paczkomat: '+pczk; }
    }
    if(nip){ shipAddr=(shipAddr?shipAddr+', ':'')+'NIP: '+nip; if(comp) shipAddr+=', ' + comp; }
  if(FULFILL==='pickup'){ shipAddr='ODBIÓR OSOBISTY — Gdańsk, ul. Międzygwiezdna 31/2 (Osowa), 80-299'; }
  var _fa=FIRM_ORDERS_ENABLED?(((document.getElementById('fFirmAddr')||{}).value)||''):''; if(_fa.trim()) shipAddr=(shipAddr?shipAddr+' | ':'')+'FAKTURA: '+_fa.trim();
  var body={name:nm,email:em,phone:document.getElementById('fPhone').value.trim(),address:shipAddr,city:(FULFILL==='pickup'?'80-299 Gdańsk':document.getElementById('fCity').value.trim()),country:(FULFILL==='pickup'?'PL':document.getElementById('fRegion').value),shipping:document.getElementById('fShipping').value,shipping_region:document.getElementById('fRegion').value,discount_code:document.getElementById('fCode').value.trim(),notes:document.getElementById('fNotes').value.trim(),payment_method:'stripe',currency:cur,items:CART.map(function(it){return {job_uuid:it.job_uuid,job_id:it.job_id,model_name:it.model_name,material:it.material,color:it.color,colors:it.colors||1,quantity:it.qty,volume_cm3:it.vol,estimated_hours:0,dims:it.dims,infill:it.infill||INFCFG.base};})};
var btn=document.getElementById('submitBtn'); if(btn){btn.disabled=true; btn.textContent='Tworzę zamówienie…';}
  fetch('/api/orders/multi?t='+Date.now(),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
    .then(function(r){return r.json().then(function(d){return {ok:r.ok,d:d};});})
    .then(function(res){
      if(!(res.ok&&res.d.ok)){ toast((res.d&&res.d.detail)||'Błąd zamówienia',''); btn.disabled=false; btn.textContent='Zapłać'; return; }
      var orderId=res.d.order_id;
      if(typeof saveProfileShip==='function') saveProfileShip();
      btn.textContent='Przygotowuję płatność…';
      // CHECKOUT: Stripe (redirect) albo BLIK — thank-you dopiero po potwierdzonej płatności
      fetch('/api/orders/'+orderId+'/checkout?t='+Date.now(),{method:'POST'})
        .then(function(r){return r.json().then(function(d){return {ok:r.ok,d:d};});})
        .then(function(c){
          if(c.ok&&c.d&&c.d.checkout_url){
            window.location.href=c.d.checkout_url;  // Stripe hosted checkout
            return;
          }
          if(c.ok&&c.d&&c.d.blik_fallback){
            // BLIK / przelew — ekran z danymi do wpłaty
            try{ sessionStorage.setItem('blik_info',JSON.stringify({titled:c.d.titled,blik_code:c.d.blik_code,total:c.d.total})); }catch(e){}
            document.getElementById('blikOrder').textContent='#'+orderId;
            document.getElementById('blikTotal').textContent=(c.d.total!=null?(+c.d.total).toFixed(2)+' '+(c.d.currency||'PLN'):'—');
            document.getElementById('blikCode').textContent=c.d.blik_code||'—';
            document.getElementById('blikTitle').textContent=c.d.titled||('3dfile.link #'+orderId);
            document.getElementById('blikStatus').href='/platnosc?status=pending&order='+orderId;
            document.getElementById('pageOrder').style.display='none';
            document.getElementById('pageBlik').style.display='block';
            window.scrollTo(0,0);
            return;
          }
          // checkout padł — strona błędu płatności
          toast((c.d&&c.d.detail)||'Błąd przygotowania płatności','error');
          window.location.href='/platnosc?status=error&order='+orderId;
        })
        .catch(function(){
          toast('Błąd połączenia z płatnościami','error');
          window.location.href='/platnosc?status=error&order='+orderId;
        });
    })
    .catch(function(){toast('Błąd sieci','');btn.disabled=false;btn.textContent='Zapłać';});
}

buildCur(); loadMats(); drawCart(); calc(); autofillShipping();
loadJobFromUrl();
function loadJobFromUrl(){
  var m=location.search.match(/job=([^&]+)/); if(!m) return;
  var uuid=decodeURIComponent(m[1]); if(!uuid) return;
  fetch('/api/job/'+uuid+'/info?t='+Date.now()).then(function(r){return r.json();}).then(function(d){
    if(!(d&&d.ok)) return;
    var item={job_id:d.id,job_uuid:d.uuid,model_name:d.name||'Model',material:'PLA',color:'black',qty:1,infill:INFCFG.base,vol:+(d.volume_cm3||0),dims:d.dimensions||'',desc:'',price:(d.volume_cm3?0:0),_bytes:null,fromFile:d.id?true:false};
    CART.push(item); selIdx=CART.length-1; drawCart(); refreshMatSel(); calc();
    toast('Załadowano model: '+(d.name||'Model'),true);
    history.replaceState(null,'','/zamow');
  }).catch(function(){});
}



if(document.getElementById('fShipping').value!=='pickup') toggleShipUI();
function autofillShipping(){
  var t=localStorage.getItem('token')||localStorage.getItem('mt_token');
  if(!t) return;
  fetch('/api/auth/me',{headers:{'Authorization':'Bearer '+t}}).then(function(r){return r.ok?r.json():null;}).then(function(d){
    if(!d) return;
    if(d.ship_full_name){ var e=document.getElementById('fName'); if(e&&!e.value) e.value=d.ship_full_name; }
    if(d.ship_city){ var e=document.getElementById('fCity'); if(e&&!e.value) e.value=d.ship_city; }
    if(d.ship_phone){ var e=document.getElementById('fPhone'); if(e&&!e.value) e.value=d.ship_phone; }
    if(d.ship_address){ var e=document.getElementById('fAddr'); if(e&&!e.value) e.value=d.ship_address; }
    if(d.ship_country){ var e=document.getElementById('fRegion'); if(e) e.value=d.ship_country; }
  }).catch(function(){});
}
// save shipping to profile after successful order (if logged in)
function saveProfileShip(){
  var t=localStorage.getItem('token')||localStorage.getItem('mt_token'); if(!t) return;
  var body={ship_full_name:document.getElementById('fName').value,ship_phone:document.getElementById('fPhone').value,ship_address:document.getElementById('fAddr').value,ship_city:document.getElementById('fCity').value,ship_country:document.getElementById('fRegion').value};
  fetch('/api/account/shipping',{method:'PUT',headers:{'Content-Type':'application/json','Authorization':'Bearer '+t},body:JSON.stringify(body)}).catch(function(){});
}
