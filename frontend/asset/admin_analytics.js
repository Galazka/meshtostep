/* ============================================================
   admin_analytics.js — zakładka "Analityka" w panelu admina.
   Czyta /api/admin/analytics/{summary,live}, renderuje KPIs,
   wykres dniowy, lejek, źródła, urządzenia, kraje, feed live.
   Auth: JWT Bearer z localStorage 'mt_token' (wspolny z admin.html).
   ============================================================ */
(function () {
  var TOKEN_KEY = 'mt_token';
  var DAYS = 7;
  var _liveTimer = null;
  var _busy = false;

  function tok() {
    try { return localStorage.getItem(TOKEN_KEY) || localStorage.getItem('token') || ''; }
    catch (e) { return ''; }
  }
  function esc(s) {
    var o = (s === null || s === undefined) ? '' : String(s);
    return o.replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
  function api(path) {
    return fetch(path, { headers: { 'Authorization': 'Bearer ' + tok(), 'Accept': 'application/json' } })
      .then(function (r) { return r.json(); });
  }
  function toast(m, t) {
    if (typeof window.toast === 'function') { window.toast(m, t || ''); return; }
    var el = document.getElementById('toast');
    if (el) {
      el.textContent = m; el.className = 'toast show ' + (t || '');
      clearTimeout(window._anTimer);
      window._anTimer = setTimeout(function () { el.className = 'toast show hidden'; }, 3000);
    }
  }
  function fmtDT(s) {
    if (!s) return '';
    var iso = String(s).replace(' ', 'T');
    if (iso.indexOf('Z') < 0 && iso.indexOf('+') < 0) iso += 'Z';
    var d = new Date(iso);
    if (isNaN(d.getTime())) return String(s);
    try {
      return d.toLocaleString('pl-PL', {
        timeZone: 'Europe/Warsaw', day: '2-digit', month: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit'
      });
    } catch (e) { return d.toISOString().slice(11, 19); }
  }

  /* ── szkielet ─────────────────────────────────────────────── */
  function shell() {
    return '' +
      '<div class="an-wrap">' +
      '  <div class="an-head">' +
      '    <strong>Analityka wlasna</strong>' +
      '    <span class="an-muted">bez cookies &middot; bez zewnętrznych skryptów &middot; dane w naszej bazie</span>' +
      '    <div class="an-ctrl">' +
      '      <select id="anDays">' +
      '        <option value="1">24 h</option>' +
      '        <option value="7" selected>7 dni</option>' +
      '        <option value="30">30 dni</option>' +
      '        <option value="90">90 dni</option>' +
      '      </select>' +
      '      <button class="an-btn" id="anReload" type="button">&#8635; Odswiez</button>' +
      '      <button class="an-btn an-danger" id="anPurge" type="button">Wyczyść &gt;180 dni</button>' +
      '    </div>' +
      '  </div>' +
      '  <div id="anKpis" class="an-kpis"></div>' +
      '  <div id="anChart" class="an-card"></div>' +
      '  <div class="an-grid2">' +
      '    <div class="an-card" id="anFunnel"></div>' +
      '    <div class="an-card" id="anRefs"></div>' +
      '  </div>' +
      '  <div class="an-grid2">' +
      '    <div class="an-card" id="anPaths"></div>' +
      '    <div class="an-card" id="anDev"></div>' +
      '  </div>' +
      '  <div class="an-card" id="anLiveBox"></div>' +
      '  <div class="an-muted an-foot">Retencja 180 dni &mdash; czyszczenie leci tez automatycznie w petli cleanupu.</div>' +
      '</div>';
  }

  /* ── KPI ──────────────────────────────────────────────────── */
  function kpiHtml(t) {
    var items = [
      ['Odwiedzający', t.visitors, 'unikalne IP'],
      ['Sesje', t.sessions, 'sid w sessionStorage'],
      ['Odslony', t.pageviews, 'pageview'],
      ['Zdarzeń', t.events, 'wszystkie typy']
    ];
    return items.map(function (i) {
      return '<div class="an-kpi"><span class="an-kpi-v">' + esc(i[1]) + '</span>' +
        '<span class="an-kpi-l">' + esc(i[0]) + '</span>' +
        '<span class="an-kpi-s">' + esc(i[2]) + '</span></div>';
    }).join('');
  }

  /* ── wykres dniowy ────────────────────────────────────────── */
  function chartByDay(rows) {
    if (!rows || !rows.length) return '<h3>Ruch dzienny</h3><p class="an-muted">Brak danych w tym okresie.</p>';
    var max = Math.max.apply(null, rows.map(function (r) { return r.pageviews || 0; }).concat([1]));
    var w = 100 / rows.length;
    var bars = rows.map(function (r, i) {
      var h = Math.max(2, Math.round(100 * (r.pageviews || 0) / max));
      return '<rect x="' + (i * w + w * 0.15) + '%" y="' + (100 - h) + '%" width="' + (w * 0.7) +
        '%" height="' + h + '%" rx="1.2" fill="#2B5CE6"><title>' +
        esc(r.date) + ': ' + (r.pageviews || 0) + ' odslon / ' + (r.events || 0) + ' zdarzen</title></rect>';
    }).join('');
    var labels = rows.map(function (r, i) {
      if (rows.length > 14 && i % 3 !== 0) return '';
      return '<span style="width:' + w + '%">' + esc((r.date || '').slice(5)) + '</span>';
    }).join('');
    return '<h3>Ruch dzienny <span class="an-muted">maks ' + max + ' odsłon/dzień</span></h3>' +
      '<svg class="an-chart" viewBox="0 0 100 100" preserveAspectRatio="none">' + bars + '</svg>' +
      '<div class="an-axis">' + labels + '</div>';
  }

  /* ── lejek ────────────────────────────────────────────────── */
  function funnelHtml(rows) {
    if (!rows || !rows.length) return '<h3>Lejek</h3><p class="an-muted">Brak danych.</p>';
    var max = Math.max.apply(null, rows.map(function (r) { return r.count || 0; }).concat([1]));
    var body = rows.map(function (r) {
      var pct = Math.max(2, Math.round(100 * (r.count || 0) / max));
      return '<tr>' +
        '<td class="an-step"><b>' + esc(r.step) + '</b><br><span class="an-muted">' + esc(r.label) + '</span></td>' +
        '<td class="an-bar-cell"><div class="an-bar" style="width:' + pct + '%"></div></td>' +
        '<td class="an-num">' + esc(r.count) + '</td>' +
        '<td class="an-num an-muted">' + (r.of_pageviews || 0) + '%</td>' +
        '</tr>';
    }).join('');
    return '<h3>Lejek konwersji</h3><table class="an-tbl">' +
      '<thead><tr><th>Krok</th><th></th><th>Liczba</th><th>% odslon</th></tr></thead>' +
      '<tbody>' + body + '</tbody></table>';
  }

  /* ── tabela dwukolumnowa (lista) ──────────────────────────── */
  function listHtml(title, rows, keyName, valName, suffix) {
    if (!rows || !rows.length) return '<h3>' + esc(title) + '</h3><p class="an-muted">Brak danych.</p>';
    var max = Math.max.apply(null, rows.map(function (r) { return r[valName] || 0; }).concat([1]));
    return '<h3>' + esc(title) + '</h3><table class="an-tbl an-compact"><tbody>' +
      rows.map(function (r) {
        var pct = Math.round(100 * (r[valName] || 0) / max);
        return '<tr><td class="an-key">' + esc(r[keyName] || '—') + '</td>' +
          '<td class="an-bar-cell"><div class="an-bar an-bar-soft" style="width:' + pct + '%"></div></td>' +
          '<td class="an-num">' + esc(r[valName]) + (suffix || '') + '</td></tr>';
      }).join('') + '</tbody></table>';
  }

  function devicesHtml(dev, countries, events) {
    var out = listHtml('Urzadzenia', dev, 'device', 'events', '');
    out += listHtml('Kraje (CF)', countries, 'country', 'events', '');
    if (events && events.length) {
      out += '<h3>Typy zdarzen</h3><table class="an-tbl an-compact"><tbody>' +
        events.map(function (r) {
          return '<tr><td class="an-key">' + esc(r.name) + '</td><td class="an-num">' + esc(r.count) + '</td></tr>';
        }).join('') + '</tbody></table>';
    }
    return out;
  }

  /* ── feed live ────────────────────────────────────────────── */
  function liveHtml(items) {
    var head = '<h3>Na zywo <span class="an-muted">ostatnie ' + (items ? items.length : 0) + '</span></h3>';
    if (!items || !items.length) return head + '<p class="an-muted">Cisza. Nikt nie klika.</p>';
    return head + '<div class="an-live">' + items.map(function (e) {
      var name = esc(e.name);
      var cls = e.name === 'pageview' ? 'an-ev-pv' : 'an-ev-click';
      var meta = esc(e.meta || '');
      return '<span class="an-ev ' + cls + '" title="' + meta + '">' +
        '<b>' + fmtDT(e.at) + '</b> ' + name + ' <i>' + esc(e.path) + '</i>' +
        (e.country ? ' [' + esc(e.country) + ']' : '') +
        (e.device ? ' ' + esc(e.device) + '' : '') +
        (e.referrer ? ' &larr;' + esc(e.referrer) : '') +
        '</span>';
    }).join('') + '</div>';
  }

  /* ── ladowanie ────────────────────────────────────────────── */
  function renderLive() {
    if (_busy) return;
    _busy = true;
    api('/api/admin/analytics/live?limit=60').then(function (d) {
      var box = document.getElementById('anLiveBox');
      if (box && d && d.ok) box.innerHTML = liveHtml(d.items);
    }).catch(function () {}).then(function () { _busy = false; });
  }

  function load() {
    var kpisEl = document.getElementById('anKpis');
    if (kpisEl) kpisEl.innerHTML = '<p class="an-muted" style="padding:12px 0">Ladowanie...</p>';
    return api('/api/admin/analytics/summary?days=' + DAYS).then(function (d) {
      if (!d || !d.ok) {
        if (kpisEl) kpisEl.innerHTML = '<p class="an-err">Blad API: ' + esc((d && d.detail) || 'brak danych') + '</p>';
        return;
      }
      if (kpisEl) kpisEl.innerHTML = kpiHtml(d.totals || {});
      var set = function (id, html) { var e = document.getElementById(id); if (e) e.innerHTML = html; };
      set('anChart', chartByDay(d.by_day));
      set('anFunnel', funnelHtml(d.funnel));
      set('anRefs', listHtml('Źródła ruchu', d.top_refs, 'source', 'views', ''));
      set('anPaths', listHtml('Najczestsze strony', d.top_paths, 'path', 'views', ''));
      set('anDev', devicesHtml(d.devices, d.countries, d.events));
    }).catch(function (e) {
      if (kpisEl) kpisEl.innerHTML = '<p class="an-err">Blad sieci: ' + esc(e && e.message) + '</p>';
    });
  }

  function full() { load(); renderLive(); }

  function bind() {
    var sel = document.getElementById('anDays');
    if (sel) sel.addEventListener('change', function () { DAYS = parseInt(sel.value, 10) || 7; load(); });
    var r = document.getElementById('anReload');
    if (r) r.addEventListener('click', full);
    var p = document.getElementById('anPurge');
    if (p) p.addEventListener('click', function () { purge(); });
  }

  function purge() {
    var before = tok();
    fetch('/api/admin/analytics/purge?days=180', {
      method: 'POST', headers: { 'Authorization': 'Bearer ' + before, 'Accept': 'application/json' }
    }).then(function (r) { return r.json(); }).then(function (d) {
      if (d && d.ok) { toast('Usunieto ' + d.deleted + ' zdarzen', 'success'); full(); }
      else { toast('Blad: ' + ((d && d.detail) || '?'), 'error'); }
    }).catch(function () { toast('Blad sieci', 'error'); });
  }

  var STYLE = '' +
    '.an-wrap{font-size:13px}' +
    '.an-head{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:0 0 14px}' +
    '.an-head strong{font-size:15px}' +
    '.an-muted{color:#8a93a6;font-size:12px}' +
    '.an-ctrl{margin-left:auto;display:flex;gap:6px;align-items:center}' +
    '.an-ctrl select,.an-btn{border:1px solid #d7dce5;background:#fff;border-radius:6px;padding:6px 10px;font-size:12px;cursor:pointer;font-family:inherit}' +
    '.an-btn:hover{border-color:#2B5CE6;color:#2B5CE6}' +
    '.an-danger:hover{border-color:#c0392b;color:#c0392b}' +
    '.an-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-bottom:14px}' +
    '.an-kpi{border:1px solid #e5e9f0;border-radius:8px;padding:12px 14px;display:flex;flex-direction:column;gap:2px}' +
    '.an-kpi-v{font-size:24px;font-weight:700;font-family:"JetBrains Mono",monospace;color:#0B1730}' +
    '.an-kpi-l{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:#5b6474}' +
    '.an-kpi-s{font-size:11px;color:#98a1b0}' +
    '.an-card{border:1px solid #e5e9f0;border-radius:8px;padding:14px;margin-bottom:12px}' +
    '.an-card h3{margin:0 0 10px;font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:#3d4657}' +
    '.an-card h3 .an-muted{text-transform:none;letter-spacing:0}' +
    '.an-chart{width:100%;height:180px;display:block;background:linear-gradient(#f7f9fc,#fff);border-radius:4px}' +
    '.an-axis{display:flex;margin-top:4px}' +
    '.an-axis span{font-size:10px;color:#98a1b0;text-align:center;font-family:"JetBrains Mono",monospace}' +
    '.an-tbl{width:100%;border-collapse:collapse}' +
    '.an-tbl th{text-align:left;font-size:11px;color:#8a93a6;font-weight:500;padding:4px 6px;border-bottom:1px solid #eef1f6}' +
    '.an-tbl td{padding:5px 6px;border-bottom:1px solid #f2f4f8;vertical-align:middle}' +
    '.an-compact td{padding:3px 6px}' +
    '.an-step{max-width:180px}' +
    '.an-step b{font-family:"JetBrains Mono",monospace;font-size:12px}' +
    '.an-bar-cell{width:40%}' +
    '.an-bar{height:8px;border-radius:4px;background:#2B5CE6;min-width:2px}' +
    '.an-bar-soft{background:#9db2f0}' +
    '.an-num{text-align:right;font-family:"JetBrains Mono",monospace;white-space:nowrap}' +
    '.an-key{font-family:"JetBrains Mono",monospace;font-size:12px;word-break:break-all}' +
    '.an-grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}' +
    '.an-live{max-height:320px;overflow:auto;display:flex;flex-direction:column;gap:3px}' +
    '.an-ev{font-size:12px;padding:3px 6px;border-radius:4px;background:#f7f9fc;font-family:"JetBrains Mono",monospace}' +
    '.an-ev b{color:#5b6474;font-weight:500}' +
    '.an-ev i{color:#2B5CE6;font-style:normal}' +
    '.an-ev-click{background:#eef3ff}' +
    '.an-err{color:#c0392b}' +
    '.an-foot{padding-top:6px}' +
    '@media(max-width:640px){.an-chart{height:130px}.an-step{max-width:none}}';

  function inject() {
    if (document.getElementById('anStyles')) return;
    var s = document.createElement('style');
    s.id = 'anStyles';
    s.textContent = STYLE;
    document.head.appendChild(s);
  }

  function mount() {
    var host = document.getElementById('adminAnalytics');
    if (!host) return false;
    inject();
    if (!host.dataset.mounted) {
      host.innerHTML = shell();
      host.dataset.mounted = '1';
      bind();
    }
    full();
    if (_liveTimer) clearInterval(_liveTimer);
    _liveTimer = setInterval(function () {
      var box = document.getElementById('anLiveBox');
      if (!box) { clearInterval(_liveTimer); _liveTimer = null; return; }
      if (document.hidden) return;
      if (!document.getElementById('tab-analytics') ||
          !document.getElementById('tab-analytics').classList.contains('active')) return;
      renderLive();
    }, 15000);
    return true;
  }

  window.loadAnalytics = mount;
  window.__anMounted = false;
})();