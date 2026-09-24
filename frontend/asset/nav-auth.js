/* nav-auth.js — jedno źródło prawdy dla stanu logowania w nawigacji (3dfile.link).
   Wstrzykuje jednolity blok akcji do .prt-actions na KAŻDEJ stronie:
     wylogowany: [Zaloguj] [Załóż konto]
     zalogowany: [Moje pliki] [Konto] [Wyloguj]
   Nie zależy od id-ek w HTML (authBtns/userPanel) — te są tylko ukrywane,
   więc strony bez własnej obsługi authu też pokazują poprawny stan.
   v1 */
(function () {
  var TOKENS = ['mt_token', 'token'];
  var BOX_ID = 'navAuthBox';

  function lsGet(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function lsDel(k) { try { localStorage.removeItem(k); } catch (e) {} }
  function token() { for (var i = 0; i < TOKENS.length; i++) { var v = lsGet(TOKENS[i]); if (v) return v; } return null; }
  function clearTokens() { TOKENS.forEach(lsDel); }

  function box() {
    var b = document.getElementById(BOX_ID);
    if (b) return b;
    var actions = document.querySelector('.prt-actions');
    if (!actions) return null;
    b = document.createElement('span');
    b.id = BOX_ID;
    b.style.cssText = 'display:inline-flex;align-items:center;gap:8px;margin-left:4px';
    var burger = actions.querySelector('.prt-burger');
    if (burger) actions.insertBefore(b, burger); else actions.appendChild(b);
    return b;
  }

  /* ukrywa stary, statyczny blok authu z HTML — żeby nie było dwóch prawd */
  function hideLegacy() {
    ['authBtns', 'userPanel'].forEach(function (id) {
      var e = document.getElementById(id);
      if (e) e.style.display = 'none';
    });
  }

  /* mobilne menu (index): chowaj/pokaz linki zależne od stanu */
  function mobile(on) {
    ['navFilesM', 'navKontoM', 'navOrdersM'].forEach(function (id) {
      var e = document.getElementById(id); if (e) e.style.display = on ? '' : 'none';
    });
    var am = document.getElementById('navAuthMobile');
    if (am) am.querySelectorAll('[data-i18n="navLogin"],[data-i18n="navSignup"]').forEach(function (e) {
      e.style.display = on ? 'none' : '';
    });
  }

  function loggedOut() {
    var b = box(); if (!b) return;
    hideLegacy(); mobile(false);
    b.innerHTML =
      '<button class="prt-btn ghost" data-i18n="navLogin" onclick="location.href=\'/?login=1\'">Zaloguj</button>' +
      '<button class="prt-btn primary" data-i18n="navSignup" onclick="location.href=\'/?register=1\'">Załóż konto</button>';
    retranslate(b);
  }

  function loggedIn(email, isAdmin) {
    var b = box(); if (!b) return;
    hideLegacy(); mobile(true);
    var initial = (email || '?').trim().charAt(0).toUpperCase();
    b.innerHTML =
      '<a class="prt-btn ghost" href="/?files=1" data-i18n="navMyFiles">Moje pliki</a>' +
      '<a class="prt-btn ghost" href="/konto" data-i18n="navMyAccount">Konto</a>' +
      (isAdmin ? '<a class="prt-btn ghost" href="/admin">Admin</a>' : '') +
      '<button class="prt-btn primary" title="' + (email || '') + '" onclick="window.__navAuth.logout()">' +
      '<span style="font-family:var(--mono,monospace);font-size:12px">' + initial + '</span>' +
      '<span data-i18n="navLogout" style="margin-left:6px">Wyloguj</span></button>';
    retranslate(b);
  }

  function retranslate(root) {
    try {
      if (window.__pi18n && window.__pi18n.lang) { /* page-specific i18n handled on load */ }
      if (typeof window.applyI18n === 'function') window.applyI18n();
    } catch (e) {}
  }

  function logout() { clearTokens(); location.href = '/'; }

  function start() {
    hideLegacy();
    var tok = token();
    if (!tok) { loggedOut(); return; }
    fetch('/api/auth/me', { headers: { 'Authorization': 'Bearer ' + tok } })
      .then(function (r) {
        if (r.status === 401 || r.status === 403) { clearTokens(); return null; }
        if (!r.ok) return null;
        return r.json();
      })
      .then(function (d) {
        if (d && (d.email || d.id || d.user)) loggedIn((d.email || (d.user && d.user.email) || ''), !!(d.is_admin || (d.user && d.user.is_admin)));
        else loggedOut();
      })
      .catch(function () { loggedOut(); });
  }

  window.__navAuth = { start: start, logout: logout, refresh: start };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
  /* SPA (index) potrafi zalogować bez przeładowania — dołóż nasłuch */
  window.addEventListener('hashchange', start);
})();