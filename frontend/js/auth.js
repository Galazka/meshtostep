// auth.js — forgot-password, modal, doAuth, fetchUser, logout (verbatim).
import { t } from './i18n.js';
import { token, setToken } from './shared.js';

async function openForgotModal(){ document.getElementById('forgotModal').classList.add('show'); document.getElementById('forgotError').style.display='none'; }
function closeForgotModal(){ document.getElementById('forgotModal').classList.remove('show'); }
async function sendForgotPassword(){
const email=document.getElementById('forgotEmail').value.trim();
if(!email){ showForgotErr('Podaj email.'); return; }
try{
    const r=await fetch('/api/auth/forgot-password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email})});
    const d=await r.json();
    if(!r.ok) throw new Error(d.detail||t('errorGeneric'));
    showForgotOK(d.detail||'Wyslano link. Sprawdz poczte.');
}catch(e){ showForgotErr(e.message||String(e)); }
}
function showForgotErr(msg){ const e=document.getElementById('forgotError'); e.textContent=msg; e.style.display='block'; e.style.color='var(--error)'; }
function showForgotOK(msg){ const e=document.getElementById('forgotError'); e.textContent=msg; e.style.display='block'; e.style.color='var(--success)'; }

let authMode = 'login';

function showModal(mode) {
    authMode = mode;
    document.getElementById('authModal').classList.add('show');
    document.getElementById('modalTitle').textContent = mode === 'login' ? t('authLoginTitle') : t('authRegisterTitle');
    document.getElementById('authSubmit').textContent = mode === 'login' ? t('authLoginBtn') : t('authRegisterBtn');
    var swEl = document.getElementById('authSwitch');
    if (swEl) swEl.innerHTML =
        (mode === 'login' ? t('authNoAccount') : t('authHasAccount')) +
        ' <a onclick="toggleAuth()">' + (mode === 'login' ? t('authFreeSignup') : t('authLoginLink')) + '</a>';
    const regExtra = document.getElementById('registerExtra');
    const forgotLink = document.getElementById('forgotLink');
    if (mode === 'register') {
        regExtra.classList.add('show');
        forgotLink.style.display = 'none';
    } else {
        regExtra.classList.remove('show');
        forgotLink.style.display = 'block';
    }
    hideAuthError();
    document.getElementById('authPass').value = '';
    if (mode === 'register') {
        document.getElementById('authPassConfirm').value = '';
        document.getElementById('authTerms').checked = false;
        document.getElementById('authPrivacy').checked = false;
        document.getElementById('authMarketing').checked = false;
        updatePwStrength('');
    }
}
function toggleAuth() { showModal(authMode==='login'?'register':'login'); }
function closeModal() { document.getElementById('authModal').classList.remove('show'); }

function showAuthError(msg) {
    const el = document.getElementById('authError');
    el.textContent = msg;
    el.classList.add('show');
}
function hideAuthError() {
    const el = document.getElementById('authError');
    el.classList.remove('show');
    el.textContent = '';
}

function updatePwStrength(pw) {
    const fill = document.getElementById('pwStrengthFill');
    if (!pw) { fill.style.width = '0'; fill.style.background = 'transparent'; return; }
    let score = 0;
    if (pw.length >= 8) score++;
    if (/[A-Z]/.test(pw)) score++;
    if (/[a-z]/.test(pw)) score++;
    if (/[0-9]/.test(pw)) score++;
    if (/[^A-Za-z0-9]/.test(pw)) score++;
    const pct = (score / 5) * 100;
    fill.style.width = pct + '%';
    fill.style.background = score <= 2 ? '#dc2626' : score <= 3 ? '#d97706' : '#059669';
}

document.getElementById('authPass').addEventListener('input', function() {
    if (authMode === 'register') updatePwStrength(this.value);
});

async function doAuth() {
    const email = document.getElementById('authEmail').value;
    const pass = document.getElementById('authPass').value;
    hideAuthError();

    if (!email || !pass) { showAuthError('Email and password are required'); return; }

    if (authMode === 'register') {
        const passConfirm = document.getElementById('authPassConfirm').value;
        const terms = document.getElementById('authTerms').checked;
        const privacy = document.getElementById('authPrivacy').checked;

        if (!passConfirm) { showAuthError('Please confirm your password'); return; }
        if (pass !== passConfirm) { showAuthError(t('authErrMismatch')); return; }
        if (!terms) { showAuthError(t('authErrTerms')); return; }
        if (!privacy) { showAuthError(t('authErrPrivacy')); return; }
    }

    const ep = authMode === 'register' ? '/api/auth/register' : '/api/auth/login';
    const body = authMode === 'register'
        ? { email, password: pass, password_confirm: document.getElementById('authPassConfirm').value,
            terms_accepted: true, privacy_accepted: true,
            marketing_consent: document.getElementById('authMarketing').checked }
        : { email, password: pass };

    try {
        const r = await fetch(ep, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body) });
        const d = await r.json();
        if (!r.ok) { showAuthError(d.detail || 'Error'); return; }
        setToken(d.token); localStorage.setItem('mt_token', token);
        closeModal(); fetchUser();
    } catch(e) { showAuthError('Network error'); }
}

async function fetchUser() {
    if (!token) return;
    const r = await fetch('/api/auth/me', {headers:{'Authorization':'Bearer '+token}});
    if (!r.ok) { setToken(null); localStorage.removeItem('mt_token'); return; }
    const d = await r.json();
    document.getElementById('authBtns').style.display='none';
    document.getElementById('userPanel').style.display='inline';
    document.getElementById('navFiles').style.display='';
    if (d.is_admin) {
        const a = document.createElement('a'); a.href='/admin'; a.textContent='Admin'; a.style.cssText='margin-left:8px;font-size:13px;color:var(--text-secondary)';
        document.querySelector('.nav-right').insertBefore(a, document.getElementById('themeToggle'));
    }
}

function logout() { setToken(null); localStorage.removeItem('mt_token'); location.reload(); }
function showMyJobs() { window.go('files'); }

export { fetchUser, showModal };
window.openForgotModal = openForgotModal;
window.closeForgotModal = closeForgotModal;
window.sendForgotPassword = sendForgotPassword;
window.showModal = showModal;
window.toggleAuth = toggleAuth;
window.closeModal = closeModal;
window.doAuth = doAuth;
window.fetchUser = fetchUser;
window.logout = logout;
window.showMyJobs = showMyJobs;
