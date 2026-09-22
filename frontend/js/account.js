// account.js — loadAccount, quota, konto stats + avatar + shipping save.
function loadAccount() {
    var tok = localStorage.getItem('mt_token');
    fetch('/api/auth/me', { headers: { 'Authorization': 'Bearer ' + tok } }).then(function (r) { return r.ok ? r.json() : null }).then(function (u) {
        if (!u || !u.email) return;
        document.getElementById('kontoEmail').textContent = u.email || '';
        document.getElementById('kontoAdmin').style.display = u.is_admin ? 'inline-block' : 'none';
        var role = document.getElementById('kontoRole');
        if (role) role.textContent = u.is_admin ? 'Administrator' : 'Użytkownik';
        document.getElementById('kontoCreated').textContent = 'Konto od: ' + (u.created_at || '').slice(0, 10);
        var av = document.getElementById('kontoAvatar');
        if (av) {
            var nm = (u.ship_full_name || u.email || '?');
            var ini = nm.split(/[\s@._-]+/).filter(Boolean).slice(0, 2).map(function (w) { return w[0].toUpperCase(); }).join('');
            av.textContent = ini || '?';
        }
        var e1 = document.getElementById('kontoName'); if (e1) e1.value = u.ship_full_name || '';
        var e2 = document.getElementById('kontoPhone'); if (e2) e2.value = u.ship_phone || '';
        var e3 = document.getElementById('kontoAddress'); if (e3) e3.value = u.ship_address || '';
        var e4 = document.getElementById('kontoCity'); if (e4) e4.value = (u.ship_city || '');
        var e5 = document.getElementById('kontoCountry'); if (e5) e5.value = u.ship_country || 'PL';
    });
    fetch('/api/quota', { headers: { 'Authorization': 'Bearer ' + tok } }).then(function (r) { return r.ok ? r.json() : {} }).then(function (q) {
        if (!q || !q.limit_bytes) return;
        var _fmt=function(b){return b<1048576?(b/1024).toFixed(1).replace('.',',')+' KB':Math.round(b/1048576)+' MB'};
        document.getElementById('kontoQuotaUsed').textContent=(q.used_bytes!=null?_fmt(q.used_bytes):q.used_mb+' MB');
        document.getElementById('kontoQuotaLimit').textContent = q.limit_mb + ' MB';
        document.getElementById('kontoQuotaFill').style.width = Math.min(q.percent || 0, 100) + '%';
        var pc = document.getElementById('kontoQuotaPct'); if (pc) pc.textContent = Math.round(q.percent || 0) + '%';
        if (q.percent >= 90) document.getElementById('kontoQuotaFill').style.background = '#dc2626';
    });
    fetch('/api/jobs', { headers: { 'Authorization': 'Bearer ' + tok } }).then(function (r) { return r.ok ? r.json() : [] }).then(function (j) {
        var el = document.getElementById('kontoFileCount');
        if (el) el.textContent = (j && j.length ? j.length + ' szt.' : '—');
    });
    fetch('/api/account/orders', { headers: { 'Authorization': 'Bearer ' + tok, 'Accept': 'application/json' } }).then(function (r) { return r.ok ? r.json() : null }).then(function (d) {
        var el = document.getElementById('kontoOrderCount');
        if (!el) return;
        if (d && d.orders) {
            var unpaid = d.orders.filter(function (o) { return !o.is_paid; }).length;
            el.textContent = d.orders.length + ' zł.' + (unpaid ? (' · ' + unpaid + ' do opłaty') : '');
        } else el.textContent = '—';
    });
}


function saveKontoShipping() {
    var body = {
        ship_full_name: (document.getElementById('kontoName') || {}).value || '',
        ship_phone: (document.getElementById('kontoPhone') || {}).value || '',
        ship_address: (document.getElementById('kontoAddress') || {}).value || '',
        ship_city: (document.getElementById('kontoCity') || {}).value || '',
        ship_country: (document.getElementById('kontoCountry') || {}).value || 'PL'
    };
    var st = document.getElementById('kontoShipStatus');
    fetch('/api/account/shipping', { method: 'PUT', headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + localStorage.getItem('mt_token') }, body: JSON.stringify(body) })
        .then(function (r) {
            if (st) { st.textContent = r.ok ? '✓ Zapisano — dane trafią do formularza zamówienia.' : 'Nie udało się zapisać.'; st.style.color = r.ok ? '' : '#dc2626'; }
        });
}

export { loadAccount, saveKontoShipping };
window.loadAccount = loadAccount;
window.saveKontoShipping = saveKontoShipping;
