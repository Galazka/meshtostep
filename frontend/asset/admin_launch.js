/* ============================================================
   admin_launch.js — zakładka "Uruchomienie" w panelu admina.
   Jedno miejsce: czy portal jest gotowy do ruchu (modele, smieci,
   zamowienia, SEO, reklamy) + sprzatanie wlasnych testow + reset
   zakresowy na haslo.
   Auth: JWT Bearer z localStorage 'mt_token' (wspolny z admin.html).
   ============================================================ */
(function () {
  var TOKEN_KEY = 'mt_token';
  var _busy = false;
  var _dry = null;

  function tok() {
    try { return localStorage.getItem(TOKEN_KEY) || localStorage.getItem('token') || ''; }
    catch (e) { return ''; }
  }
  function esc(s) {
    var o = (s === null || s === undefined) ? '' : String(s);
    return o.replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
  function jfetch(path, opts) {
    var o = opts || {};
    o.headers = o.headers || {};
    o.headers['Authorization'] = 'Bearer ' + tok();
    o.headers['Accept'] = 'application/json';
    return fetch(path, o).then(function (r) {
      return r.json().then(function (j) { return { status: r.status, body: j }; })
        .catch(function () { return { status: r.status, body: {} }; });
    });
  }
  function toast(m, t) {
    if (typeof window.toast === 'function') { window.toast(m, t || ''); return; }
    var el = document.getElementById('toast');
    if (el) {
      el.textContent = m; el.className = 'toast show ' + (t || '');
      clearTimeout(window._laTimer);
      window._laTimer = setTimeout(function () { el.className = 'toast show hidden'; }, 3200);
    }
  }

  var STYLE = '' +
    '#adminLaunch .la-wrap{display:flex;flex-direction:column;gap:14px}' +
    '#adminLaunch .la-head{display:flex;flex-wrap:wrap;align-items:center;gap:10px}' +
    '#adminLaunch .la-head strong{font-size:15px}' +
    '#adminLaunch .la-muted{color:#6b7280;font-size:12px}' +
    '#adminLaunch .la-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}' +
    '#adminLaunch .la-card{border:1px solid #e5e7eb;border-radius:8px;padding:10px 12px;background:#fff}' +
    '#adminLaunch .la-card .k{font-family:"JetBrains Mono",monospace;font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:#6b7280}' +
    '#adminLaunch .la-card .v{font-family:"JetBrains Mono",monospace;font-size:22px;color:#0B1220;line-height:1.25}' +
    '#adminLaunch .la-card .s{font-size:11px;color:#6b7280;font-family:"JetBrains Mono",monospace}' +
    '#adminLaunch .la-card.warn{border-color:#f0b429;background:#fffbf0}' +
    '#adminLaunch .la-sec{border:1px solid #e5e7eb;border-radius:8px;padding:12px;background:#fff}' +
    '#adminLaunch .la-sec h4{margin:0 0 8px;font-size:13px;letter-spacing:.02em}' +
    '#adminLaunch .la-issue{display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:7px 9px;border-radius:6px;background:#f7f9fc;margin-bottom:6px;font-size:13px}' +
    '#adminLaunch .la-issue.warn{background:#fffbf0}' +
    '#adminLaunch .la-dot{width:8px;height:8px;border-radius:50%;background:#2B5CE6;flex:0 0 auto}' +
    '#adminLaunch .la-dot.warn{background:#f0b429}' +
    '#adminLaunch .la-ok{color:#12805c;font-size:13px}' +
    '#adminLaunch .la-btn{border:1px solid #d1d5db;background:#fff;border-radius:6px;padding:6px 11px;font-size:12.5px;cursor:pointer;font-family:inherit}' +
    '#adminLaunch .la-btn:hover{background:#f3f4f6}' +
    '#adminLaunch .la-btn.primary{background:#2B5CE6;border-color:#2B5CE6;color:#fff}' +
    '#adminLaunch .la-btn.primary:hover{background:#1f47b8}' +
    '#adminLaunch .la-btn.danger{background:#b4231f;border-color:#b4231f;color:#fff}' +
    '#adminLaunch .la-btn.danger:hover{background:#941a17}' +
    '#adminLaunch .la-btn[disabled]{opacity:.5;cursor:not-allowed}' +
    '#adminLaunch table.la-t{width:100%;border-collapse:collapse;font-size:12.5px}' +
    '#adminLaunch table.la-t th{text-align:left;font-family:"JetBrains Mono",monospace;font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:#6b7280;border-bottom:1px solid #e5e7eb;padding:5px 6px}' +
    '#adminLaunch table.la-t td{border-bottom:1px solid #f1f3f7;padding:5px 6px;font-family:"JetBrains Mono",monospace}' +
    '#adminLaunch .la-row{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-top:8px}' +
    '#adminLaunch input.la-in, #adminLaunch select.la-in{border:1px solid #d1d5db;border-radius:6px;padding:6px 8px;font-family:inherit;font-size:13px}' +
    '#adminLaunch .la-note{font-size:12px;color:#6b7280}' +
    '#adminLaunch .la-scroll{max-height:260px;overflow:auto}' +
    '@media(max-width:640px){#adminLaunch .la-cards{grid-template-columns:repeat(auto-fit,minmax(120px,1fr))}}';

  function inject() {
    if (document.getElementById('laStyles')) return;
    var s = document.createElement('style');
    s.id = 'laStyles';
    s.textContent = STYLE;
    document.head.appendChild(s);
  }

  function shell() {
    return '' +
      '<div class="la-wrap">' +
      '  <div class="la-head">' +
      '    <strong>Uruchomienie serwisu</strong>' +
      '    <span class="la-muted">stan gotowosci do ruchu &middot; czyszczenie wlasnych testow &middot; reset zakresowy</span>' +
      '    <button class="la-btn" id="laRefresh">Odswiez</button>' +
      '  </div>' +
      '  <div class="la-cards" id="laCards"><span class="la-muted">Ladowanie...</span></div>' +
      '  <div class="la-sec"><h4>Co jeszcze nie gra</h4><div id="laIssues"><span class="la-muted">...</span></div></div>' +
      '  <div class="la-sec">' +
      '    <h4>Sprzatanie testowych smieci</h4>' +
      '    <div class="la-note">Usuwa wylacznie konta/modele/sloty rozpoznane jako testowe (uitest, e2e, testN, demouser...). Adminow nie rusza nigdy.</div>' +
      '    <div class="la-row">' +
      '      <button class="la-btn" id="laDry">Sprawdz (dry-run)</button>' +
      '      <button class="la-btn danger" id="laClean" disabled>Usun testowe</button>' +
      '      <span class="la-muted" id="laCleanMsg"></span>' +
      '    </div>' +
      '    <div id="laDryBox" style="margin-top:8px"></div>' +
      '  </div>' +
      '  <div class="la-sec">' +
      '    <h4>Reset zakresowy (nieodwracalny)</h4>' +
      '    <div class="la-note">Kasuje dane na stale. Wpisz <b>USUWAM</b> aby potwierdzic.</div>' +
      '    <div class="la-row">' +
      '      <select class="la-in" id="laScope">' +
      '        <option value="models">modele + pliki</option>' +
      '        <option value="users">uzytkownicy</option>' +
      '        <option value="orders">zamowienia</option>' +
      '        <option value="ads">sloty reklamowe</option>' +
      '        <option value="analytics">zdarzenia analityki</option>' +
      '        <option value="all">wszystko (bez admina)</option>' +
      '      </select>' +
      '      <input class="la-in" id="laConfirm" placeholder="USUWAM" autocomplete="off">' +
      '      <button class="la-btn danger" id="laReset">Wykonaj reset</button>' +
      '      <span class="la-muted" id="laResetMsg"></span>' +
      '    </div>' +
      '  </div>' +
      '</div>';
  }

  function card(k, v, s, warn) {
    return '<div class="la-card' + (warn ? ' warn' : '') + '">' +
      '<div class="k">' + esc(k) + '</div>' +
      '<div class="v">' + esc(v) + '</div>' +
      '<div class="s">' + esc(s || '') + '</div></div>';
  }

  function renderCards(d) {
    var m = d.models || {}, u = d.users || {}, o = d.orders || {},
      a = d.ads || {}, seo = d.seo || {}, an = d.analytics || {};
    var out = '';
    out += card('Modele', m.total, 'publiczne ' + (m.public || 0), (m.junk || 0) > 0);
    out += card('Do sprzatania', m.junk, 'testowe modele', (m.junk || 0) > 0);
    out += card('Uzytkownicy', u.total, 'admin ' + (u.admins || 0), (u.junk || 0) > 0);
    out += card('Zamowienia', o.total, 'oplacone ' + (o.paid || 0) + ' / otwarte ' + (o.open || 0), false);
    out += card('Reklamy', a.active + '/' + a.total, 'aktywne / wszystkie', (a.junk || 0) > 0);
    out += card('Blog', seo.blog_articles, 'artykulow SEO', (seo.blog_articles || 0) < 6);
    out += card('Zdarzenia', an.page_events, 'wlasna analityka', false);
    var host = document.getElementById('laCards');
    if (host) host.innerHTML = out;
  }

  function renderIssues(d) {
    var host = document.getElementById('laIssues');
    if (!host) return;
    var list = d.issues || [];
    if (!list.length) {
      host.innerHTML = '<span class="la-ok">Wszystko czyste.</span>' +
        '<div class="la-note" style="margin-top:6px">Sitemap: <a href="/sitemap.xml" target="_blank">/sitemap.xml</a> ' +
        '&middot; panel: <a href="/admin">/admin</a></div>';
      return;
    }
    var html = '';
    list.forEach(function (i) {
      var fix = i.fix ? '<button class="la-btn" data-fix="' + esc(i.fix) + '">napraw</button>' : '';
      html += '<div class="la-issue ' + (i.level === 'warn' ? 'warn' : '') + '">' +
        '<span class="la-dot ' + (i.level === 'warn' ? 'warn' : '') + '"></span>' +
        '<span>' + esc(i.text) + '</span>' + fix + '</div>';
    });
    host.innerHTML = html;
    host.querySelectorAll('[data-fix]').forEach(function (b) {
      b.addEventListener('click', function () {
        var f = b.getAttribute('data-fix');
        if (f === 'cleanup-test') { document.getElementById('laDry').click(); }
        else if (f === 'cleanup-ads') { toast('Sloty z testowym kodem: uzyj "Sprawdz (dry-run)"', ''); document.getElementById('laDry').click(); }
        else if (f === 'reset-orders') {
          var ss = document.getElementById('laScope');
          if (ss) ss.value = 'orders';
          toast('Ustawiono zakres: zamowienia. Wpisz USUWAM i zatwierdz.', '');
        } else if (f === 'admin/ads') {
          if (typeof window.switchAdminTab === 'function') window.switchAdminTab('ads');
        }
      });
    });
  }

  function renderDry(r) {
    var box = document.getElementById('laDryBox');
    var cnt = (r && r.counts) || {};
    if (box) {
      var users = (r && r.users) || [], mds = (r && r.models) || [], ads = (r && r.ads) || [];
      var h = '<div class="la-note" style="margin-bottom:6px">dry-run: konta <b>' + (cnt.users || 0) +
        '</b> &middot; modele <b>' + (cnt.models || 0) + '</b> &middot; sloty <b>' + (cnt.ads || 0) + '</b></div>';
      if (users.length) {
        h += '<div class="la-note">Konta:</div><div class="la-scroll"><table class="la-t"><thead><tr><th>id</th><th>nazwa</th></tr></thead><tbody>';
        users.forEach(function (u) { h += '<tr><td>' + esc(u.id) + '</td><td>' + esc(u.username) + '</td></tr>'; });
        h += '</tbody></table></div>';
      }
      if (mds.length) {
        h += '<div class="la-note" style="margin-top:8px">Modele:</div><div class="la-scroll"><table class="la-t"><thead><tr><th>id</th><th>slug</th><th>konto</th></tr></thead><tbody>';
        mds.forEach(function (m) { h += '<tr><td>' + esc(m.id) + '</td><td>' + esc(m.slug) + '</td><td>' + esc(m.user || 'anon') + '</td></tr>'; });
        h += '</tbody></table></div>';
      }
      if (ads.length) {
        h += '<div class="la-note" style="margin-top:8px">Sloty:</div><div class="la-scroll"><table class="la-t"><thead><tr><th>id</th><th>nazwa</th><th>slot</th></tr></thead><tbody>';
        ads.forEach(function (a) { h += '<tr><td>' + esc(a.id) + '</td><td>' + esc(a.name) + '</td><td>' + esc(a.slot_key) + '</td></tr>'; });
        h += '</tbody></table></div>';
      }
      if (!users.length && !mds.length && !ads.length) h += '<p class="la-ok">Nic testowego do usuniecia.</p>';
      box.innerHTML = h;
    }
    var cb = document.getElementById('laClean');
    var msg = document.getElementById('laCleanMsg');
    var n = (cnt.users || 0) + (cnt.models || 0) + (cnt.ads || 0);
    if (cb) cb.disabled = !n;
    if (msg) msg.textContent = n ? ('do usuniecia: ' + n) : 'brak smieci';
  }

  function state() {
    return jfetch('/api/admin/launch/state').then(function (r) {
      if (r.status !== 200) {
        var host = document.getElementById('laCards');
        if (host) host.innerHTML = '<span class="la-muted" style="color:#b4231f">Blad API (' + r.status + '): ' +
          esc((r.body && r.body.detail) || '') + '</span>';
        return;
      }
      renderCards(r.body);
      renderIssues(r.body);
    });
  }

  function bind() {
    var rb = document.getElementById('laRefresh');
    if (rb) rb.addEventListener('click', function () { state(); toast('Odswiezono stan', ''); });

    var db = document.getElementById('laDry');
    if (db) db.addEventListener('click', function () {
      if (_busy) return; _busy = true; db.disabled = true;
      jfetch('/api/admin/launch/cleanup-test?dry_run=true', { method: 'POST' }).then(function (r) {
        _busy = false; db.disabled = false;
        if (r.status !== 200) { toast('Blad: ' + ((r.body && r.body.detail) || r.status), 'error'); return; }
        _dry = r.body; renderDry(r.body);
      }).catch(function (e) { _busy = false; db.disabled = false; toast('Blad sieci: ' + (e && e.message), 'error'); });
    });

    var cb = document.getElementById('laClean');
    if (cb) cb.addEventListener('click', function () {
      if (_busy) return;
      if (!_dry) { toast('Najpierw dry-run', 'error'); return; }
      if (!window.confirm('Usunac testowe konta/modele/sloty z listy powyzej?')) return;
      _busy = true; cb.disabled = true;
      jfetch('/api/admin/launch/cleanup-test?dry_run=false&remove_files=true', { method: 'POST' }).then(function (r) {
        _busy = false; cb.disabled = false;
        if (r.status !== 200) { toast('Blad: ' + ((r.body && r.body.detail) || r.status), 'error'); return; }
        var rem = r.body.removed || {};
        toast('Usunieto: konta ' + (rem.users || 0) + ', modele ' + (rem.models || 0) + ', sloty ' + (rem.ads || 0), '');
        _dry = null; renderDry({ counts: {}, users: [], models: [], ads: [] });
        state();
      }).catch(function (e) { _busy = false; cb.disabled = false; toast('Blad sieci: ' + (e && e.message), 'error'); });
    });

    var rset = document.getElementById('laReset');
    if (rset) rset.addEventListener('click', function () {
      var sc = (document.getElementById('laScope') || {}).value || 'models';
      var cf = (document.getElementById('laConfirm') || {}).value || '';
      var msg = document.getElementById('laResetMsg');
      if (cf.trim().toUpperCase() !== 'USUWAM') { if (msg) msg.textContent = 'Wpisz USUWAM.'; return; }
      if (!window.confirm('RESET "' + sc + '" — nieodwracalny. Kontynuowac?')) return;
      rset.disabled = true;
      jfetch('/api/admin/launch/reset?scope=' + encodeURIComponent(sc) + '&confirm=USUWAM&keep_admin=true&remove_files=true',
        { method: 'POST' }).then(function (r) {
          rset.disabled = false;
          if (r.status !== 200) { if (msg) msg.textContent = 'Blad: ' + ((r.body && r.body.detail) || r.status); return; }
          var rm = r.body.removed || {};
          if (msg) msg.textContent = 'Zrobione: ' + JSON.stringify(rm);
          toast('Reset "' + sc + '" wykonany', '');
          document.getElementById('laConfirm').value = '';
          state();
        }).catch(function (e) { rset.disabled = false; if (msg) msg.textContent = 'Blad sieci: ' + (e && e.message); });
    });
  }

  function mount() {
    var host = document.getElementById('adminLaunch');
    if (!host) return false;
    inject();
    if (!host.dataset.mounted) { host.innerHTML = shell(); host.dataset.mounted = '1'; bind(); }
    state();
    return true;
  }

  window.loadLaunch = mount;
})();
