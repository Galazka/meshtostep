// account.js — loadAccount, quota, account menu (verbatim).

function loadAccount() {
    fetch('/api/me', {headers:{'Authorization':'Bearer '+localStorage.getItem('mt_token')}}).then(function(r){return r.json()}).then(function(u){
        document.getElementById('kontoEmail').textContent = u.email || '';
        document.getElementById('kontoAdmin').style.display = u.is_admin ? 'block' : 'none';
        document.getElementById('kontoCreated').textContent = 'Konto od: ' + (u.created_at||'').slice(0,10);
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
