// main.js — entry: tabs/routing, theme, FAQ, ads, home-recent, modal glue, init.
import { applyI18n } from './i18n.js';
import { token } from './shared.js';
import { refreshThreeTheme } from './viewer3d.js';
import { fetchUser, showModal } from './auth.js';
import { setupDropZone } from './convert.js';
import { loadMyJobs } from './myfiles.js';
import { loadAccount } from './account.js';

// Expose window globals for onclick handlers in index.html
window.showModal = showModal;
window.toggleLang = window.toggleLang || (() => {});
window.toggleTheme = toggleTheme;
window.go = window.go || (() => {});
window.closeDropdown = window.closeDropdown || (() => {});
window.loadMyJobs = loadMyJobs;
window.loadAccount = loadAccount;

function toggleTheme() {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    if (isDark) { document.documentElement.removeAttribute('data-theme'); localStorage.setItem('mt_theme','light'); }
    else { document.documentElement.setAttribute('data-theme', 'dark'); localStorage.setItem('mt_theme','dark'); }
    const btn = document.getElementById('themeToggle');
    if (btn) btn.textContent = isDark ? '🌙' : '☀️';
    try { refreshThreeTheme(); } catch(e) {}
}

function toggleFaq(btn) {
    const item = btn.closest('.faq-item');
    const isOpen = item.classList.contains('open');
    document.querySelectorAll('.faq-item').forEach(i => i.classList.remove('open'));
    if (!isOpen) item.classList.add('open');
}

async function loadAdSlots() {
    try {
        const r = await fetch('/api/ads/slots');
        if (!r.ok) { console.warn('[ADS] /api/ads/slots status:', r.status); return; }
        const data = await r.json();
        console.log('[ADS] public loadAdSlots response:', JSON.stringify(data).slice(0,300));
        const slots = Array.isArray(data) ? data : (data.slots || data.items || []);
        if (!slots.length) { console.log('[ADS] no active slots'); return; }
        const counts = {};
        slots.forEach(function(s) {
            const key = s.position || s.slot_key || s.slot;
            if (!key || !s.ad_code) return;
            counts[key] = (counts[key] || 0) + 1;
            let el = document.querySelector('.ad-slot[data-slot="' + key + '"]');
            if (!el) { console.warn('[ADS] no placeholder for slot:', key); return; }
            if (counts[key] > 1) {
                var clone = document.createElement('div');
                clone.className = 'ad-slot';
                clone.setAttribute('data-slot', key + '-' + counts[key]);
                el.parentNode.insertBefore(clone, el.nextSibling);
                el = clone;
            }
            // Sanitize ad_code: strip dangerous tags, keep safe ones
            var _safe = s.ad_code.replace(/<script[\s\S]*?<\/script>/gi, '')
                .replace(/on\w+\s*=\s*["'][^"']*["']/gi, '')
                .replace(/javascript\s*:/gi, '');
            el.innerHTML = _safe;
            if (!el.innerHTML.trim()) el.textContent = s.ad_code;
            console.log('[ADS] injected', key, '→', el.children.length, 'elements');
            try { fetch('/api/ads/impression/' + s.id, {method:'POST'}).catch(function(){}); } catch(e) {}
        });
    } catch(e) { console.error('[ADS] loadAdSlots error:', e); }
}

document.getElementById('jobModal').addEventListener('click', function(e) {
    if (e.target === this) window.closeJobModal();
});
document.getElementById('authModal').addEventListener('click', function(e) {
    if (e.target === this) window.closeModal();
});
document.getElementById('jobModal').addEventListener('click', function(e) {
    if (e.target === this) window.closeJobModal();
});
document.getElementById('shareModal').addEventListener('click', function(e) {
    if (e.target === this) window.closeShareModal();
});
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') { if (document.getElementById('fsOverlay').classList.contains('show')) { window.closeJobFullscreen(); } else { window.closeJobModal(); window.closeShareModal(); window.closeModal(); } }
});

async function loadHomeRecent(){
  try{
    const r=await fetch('/api/models?limit=8&sort=latest');
    const j=await r.json();
    if(!j.items || !j.items.length) return;
    const grid=document.getElementById('homeRecentGrid');
    const wrap=document.getElementById('homeRecent');
    wrap.style.display='block';
    grid.innerHTML='';
    for(const m of j.items.slice(0,8)){
      const a=document.createElement('a');
      a.href=m.vanity||'/s/'+m.uuid;
      a.style.cssText='display:block;border:1px solid var(--border);border-radius:10px;overflow:hidden;text-decoration:none;color:inherit;background:#fff';
      const img = m.slug ? `/api/preview/${m.uuid}` : '';
      a.innerHTML=`<div style="height:120px;background:var(--bg-alt);display:flex;align-items:center;justify-content:center;overflow:hidden">${img?`<img src="${img}" style="width:100%;height:100%;object-fit:cover" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'"><div style="display:none;width:100%;height:100%;align-items:center;justify-content:center;color:var(--text-muted);font-size:12px">Podglad 3D</div>`:`<span style="color:var(--text-muted);font-size:12px">Podglad 3D</span>`}</div><div style="padding:10px"><div style="font-weight:700;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${(m.title||m.slug||'Model')}</div><div style="font-size:11px;color:var(--text-secondary)">by ${m.username||'anon'} · ${(m.tags||[]).slice(0,2).join(', ')}</div></div>`;
      grid.appendChild(a);
    }
  }catch(e){}
}
loadHomeRecent();

// init (original order)
applyI18n();
if (token) fetchUser();
setupDropZone();
if(localStorage.getItem('mt_cookie_consent')==='accepted') loadAdSlots();

window.toggleTheme = toggleTheme;
window.loadAdSlots = loadAdSlots;
// go() and toggleFaq() are defined inline in index.html (navigation + FAQ accordion)
window.toggleFaqCompat = null;
