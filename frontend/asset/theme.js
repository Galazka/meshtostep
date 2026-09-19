/* theme.js — ciemny motyw 3dfile.link
   - ustawia motyw PRZED renderem (brak mignięcia)
   - wstrzykuje przycisk przełącznika do .prt-actions (jeśli nie ma własnego themeToggle)
   - zapis: localStorage 'mt_theme' ('light'|'dark')
*/
(function () {
  function apply(t) {
    document.documentElement.setAttribute('data-theme', t);
    var b = document.getElementById('themeToggle');
    if (b) b.textContent = t === 'dark' ? '☀' : '◐';
  }
  var saved = 'light';
  try {
    var qp = new URLSearchParams(window.location.search).get('theme');
    saved = (qp === 'dark' || qp === 'light') ? qp : (localStorage.getItem('mt_theme') || 'light');
  } catch (e) {}
  apply(saved);

  window.toggleTheme = function () {
    var cur = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    try { localStorage.setItem('mt_theme', cur); } catch (e) {}
    apply(cur);
    window.dispatchEvent(new CustomEvent('themechange', { detail: cur }));
  };

  function inject() {
    var acts = document.querySelectorAll('.prt-actions');
    if (!acts.length) return;
    var host = acts[acts.length - 1];
    if (document.getElementById('themeToggleAuto') || document.getElementById('themeToggle')) return;
    var b = document.createElement('button');
    b.id = 'themeToggleAuto';
    b.className = 'prt-btn ghost';
    b.title = 'Motyw ciemny / jasny';
    b.setAttribute('aria-label', 'Motyw');
    b.style.padding = '7px 11px';
    b.textContent = document.documentElement.getAttribute('data-theme') === 'dark' ? '☀' : '◐';
    b.onclick = window.toggleTheme;
    var burger = host.querySelector('.prt-burger');
    host.insertBefore(b, burger || null);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', inject);
  else inject();
})();
