// account.js — loadAccount, quota, account menu (verbatim).

function loadAccount() {
    fetch('/api/auth/me', {headers:{'Authorization':'Bearer '+localStorage.getItem('mt_token')}}).then(function(r){return r.json()}).then(function(u){
        if(!u || !u.email) return;
        document.getElementById('kontoEmail').textContent = u.email || '';
        document.getElementById('kontoAdmin').style.display = u.is_admin ? 'block' : 'none';
        document.getElementById('kontoCreated').textContent = 'Konto od: ' + (u.created_at||'').slice(0,10);
        // wypełnij dane do wysyłki z profilu
        var nm = document.getElementById('kontoName'); if (nm) nm.value = u.ship_full_name || '';
        var ph = document.getElementById('kontoPhone'); if (ph) ph.value = u.ship_phone || '';
        var ad = document.getElementById('kontoAddress'); if (ad) ad.value = u.ship_address || '';
        var ct = document.getElementById('kontoCity'); if (ct) ct.value = (u.ship_city || '');
        var cy = document.getElementById('kontoCountry'); if (cy) cy.value = u.ship_country || 'PL';
    });
    fetch('/api/quota', {headers:{'Authorization':'Bearer '+localStorage.getItem('mt_token')}}).then(function(r){return r.ok?r.json():{}}).then(function(q){
        if (!q.limit_bytes) return;
        document.getElementById('kontoQuotaUsed').textContent = q.used_mb + ' MB';
        document.getElementById('kontoQuotaLimit').textContent = q.limit_mb + ' MB';
        document.getElementById('kontoQuotaFill').style.width = Math.min(q.percent, 100) + '%';
    });
}


export { loadAccount };
window.loadAccount = loadAccount;


function saveKontoShipping(){
  var body = {
    ship_full_name: (document.getElementById('kontoName')||{}).value||'',
    ship_phone: (document.getElementById('kontoPhone')||{}).value||'',
    ship_address: (document.getElementById('kontoAddress')||{}).value||'',
    ship_city: (document.getElementById('kontoCity')||{}).value||'',
    ship_country: (document.getElementById('kontoCountry')||{}).value||'PL'
  };
  var st = document.getElementById('kontoShipStatus');
  fetch('/api/account/shipping', {method:'PUT', headers:{'Content-Type':'application/json','Authorization':'Bearer '+localStorage.getItem('mt_token')}, body:JSON.stringify(body)})
    .then(function(r){return r.json();}).then(function(d){
      if(st){ st.textContent = d.ok ? '✓ Zapisano — dane użyją się przy następnym zamówieniu druku.' : 'Błąd zapisu'; st.style.color = d.ok ? 'var(--success)' : 'var(--error)'; }
    }).catch(function(){ if(st){ st.textContent='Błąd sieci'; st.style.color='var(--error)'; } });
}
window.saveKontoShipping = saveKontoShipping;
