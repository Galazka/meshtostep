/* ============================================================
   admin_partner.js — zakładka "Partnerzy" w panelu admina.
   Lista zgłoszeń do sieci partnerskiej druku (podwykonawcy):
   scoring, filtry, zmiana statusu, notatki wewnętrzne, CSV.
   Auth: JWT Bearer z localStorage 'mt_token' (wspólny z admin.html).
   ============================================================ */
(function () {
  var TOKEN_KEY = 'mt_token';
  var ST = [
    ['new', 'Nowe'],
    ['contacted', 'Kontakt'],
    ['approved', 'Zatwierdzona'],
    ['on_hold', 'Wstrzymana'],
    ['rejected', 'Odrzucona']
  ];
  var ST_LABEL = {};
  ST.forEach(function (s) { ST_LABEL[s[0]] = s[1]; });
  var ST_CLASS = {
    new: 'pn-new', contacted: 'pn-contact', approved: 'pn-ok',
    on_hold: 'pn-hold', rejected: 'pn-no'
  };

  var _loaded = false;
  var _items = [];
  var _counts = {};
  var _target = 5;
  var _filter = '';
  var _q = '';
  var _open = {};

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
      clearTimeout(window._pnTimer);
      window._pnTimer = setTimeout(function () { el.className = 'toast show hidden'; }, 3200);
    } else {
      console.log('[partner]', m);
    }
  }
  function dt(iso) {
    if (!iso) return '—';
    try {
      var d = new Date(iso.endsWith('Z') || iso.indexOf('+') > 0 ? iso : iso + 'Z');
      return d.toLocaleString('pl-PL', { timeZone: 'Europe/Warsaw',
        year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
    } catch (e) { return iso; }
  }
  function scoreBadge(n) {
    n = Number(n || 0);
    var c = n >= 70 ? '#16a34a' : (n >= 45 ? '#d97706' : '#64748b');
    return '<span style="display:inline-block;min-width:34px;text-align:center;padding:2px 7px;border-radius:6px;' +
      'font:700 12px/1.4 ui-monospace,Menlo,Consolas,monospace;background:' + c + '1a;color:' + c +
      ';border:1px solid ' + c + '55">' + n + '</span>';
  }
  function matList(s) {
    return String(s || '').split(',').map(function (x) { return x.trim(); })
      .filter(Boolean).join(' · ') || '—';
  }

  function shell() {
    var host = document.getElementById('adminPartners');
    if (!host) return null;
    if (host.dataset.built === '1') return host;
    host.dataset.built = '1';
    host.innerHTML =
      '<div id="pnKpis" class="pn-kpis"></div>' +
      '<div class="pn-bar">' +
      '  <select id="pnStatus" class="pn-input"><option value="">Wszystkie statusy</option>' +
      ST.map(function (s) { return '<option value="' + s[0] + '">' + s[1] + '</option>'; }).join('') +
      '  </select>' +
      '  <input id="pnQ" class="pn-input" placeholder="Szukaj: pracownia / email / miasto">' +
      '  <button id="pnReload" class="pn-btn">Odśwież</button>' +
      '  <a id="pnCsv" class="pn-btn pn-btn-ghost" href="#">Eksport CSV</a>' +
      '  <span id="pnInfo" class="pn-info"></span>' +
      '</div>' +
      '<div id="pnTable" class="pn-tablewrap"><div class="pn-empty">Wczytywanie…</div></div>';
    document.getElementById('pnStatus').addEventListener('change', function () {
      _filter = this.value; render();
    });
    var qEl = document.getElementById('pnQ');
    var tmr = null;
    qEl.addEventListener('input', function () {
      var v = this.value;
      clearTimeout(tmr);
      tmr = setTimeout(function () { _q = v.trim(); load(); }, 350);
    });
    document.getElementById('pnReload').addEventListener('click', function () { load(true); });
    document.getElementById('pnCsv').addEventListener('click', function (e) {
      e.preventDefault();
      var url = '/api/admin/partners/export.csv';
      fetch(url, { headers: { 'Authorization': 'Bearer ' + tok() } }).then(function (r) {
        if (!r.ok) { toast('Eksport nieudany (' + r.status + ')', 'error'); return null; }
        return r.blob();
      }).then(function (b) {
        if (!b) return;
        var a = document.createElement('a');
        a.href = URL.createObjectURL(b);
        a.download = 'partnerzy-3dfile.csv';
        document.body.appendChild(a); a.click(); a.remove();
        toast('CSV pobrany', 'ok');
      }).catch(function () { toast('Eksport nieudany', 'error'); });
    });
    return host;
  }

  function kpis() {
    var el = document.getElementById('pnKpis');
    if (!el) return;
    var total = 0;
    ST.forEach(function (s) { total += (_counts[s[0]] || 0); });
    var approved = _counts.approved || 0;
    var left = Math.max(0, _target - ((_counts.approved || 0) + (_counts.contacted || 0)));
    var cells = [
      ['Zgłoszenia', total, '#0f172a'],
      ['Nowe', _counts['new'] || 0, '#2B5CE6'],
      ['W kontakcie', _counts.contacted || 0, '#d97706'],
      ['Zatwierdzone', approved, '#16a34a'],
      ['Do celu', left + ' / ' + _target, '#64748b'],
      ['Odrzucone / wstrzymane', (_counts.rejected || 0) + (_counts.on_hold || 0), '#94a3b8']
    ];
    el.innerHTML = cells.map(function (c) {
      return '<div class="pn-kpi"><span class="pn-kpi-v" style="color:' + c[2] + '">' + c[1] +
        '</span><span class="pn-kpi-l">' + c[0] + '</span></div>';
    }).join('');
  }

  function rows() {
    return _items.filter(function (it) {
      if (_filter && it.status !== _filter) return false;
      return true;
    });
  }

  function render() {
    var host = document.getElementById('pnTable');
    if (!host) return;
    kpis();
    var list = rows();
    var info = document.getElementById('pnInfo');
    if (info) info.textContent = list.length + ' / ' + _items.length + ' zgłoszeń';
    if (!list.length) {
      host.innerHTML = '<div class="pn-empty">Brak zgłoszeń' + (_filter ? ' w tym statusie' : '') + '.</div>';
      return;
    }
    var html = '<table class="pn-tbl"><thead><tr>' +
      '<th>Score</th><th>Pracownia / osoba</th><th>Kontakt</th><th>Lokalizacja</th>' +
      '<th>Park maszynowy</th><th>Materiały</th><th>Moce</th><th>JDG</th><th>Status</th><th>Zgłoszono</th>' +
      '</tr></thead><tbody>';
    list.forEach(function (it) {
      var open = !!_open[it.id];
      html += '<tr class="pn-row' + (open ? ' pn-row-open' : '') + '" data-id="' + it.id + '">' +
        '<td>' + scoreBadge(it.score) + '</td>' +
        '<td><b>' + esc(it.company || '—') + '</b><div class="pn-sub">' + esc(it.contact_name || '') +
        (it.website ? ' · <a href="' + esc(it.website) + '" target="_blank" rel="noopener">www</a>' : '') + '</div></td>' +
        '<td><a href="mailto:' + esc(it.email) + '">' + esc(it.email) + '</a>' +
        (it.phone ? '<div class="pn-sub"><a href="tel:' + esc(it.phone) + '">' + esc(it.phone) + '</a></div>' : '') + '</td>' +
        '<td>' + esc(it.city || '—') + '<div class="pn-sub">' + esc(it.region || '') + '</div></td>' +
        '<td>' + esc(it.printers || '—') + (it.count_printers ? ' <span class="pn-sub">(' + esc(it.count_printers) + ' szt.)</span>' : '') +
        (it.build_volume ? '<div class="pn-sub">' + esc(it.build_volume) + '</div>' : '') + '</td>' +
        '<td class="pn-mats">' + esc(matList(it.materials)) + '</td>' +
        '<td>' + esc(it.monthly_capacity || '—') + '<div class="pn-sub">' + (it.offer_shipping ? 'wysyłka: tak' : 'wysyłka: nie') + '</div></td>' +
        '<td>' + (it.has_jdg ? '<span style="color:#16a34a;font-weight:700">tak</span>' : '<span style="color:#dc2626">nie</span>') + '</td>' +
        '<td><select class="pn-status ' + (ST_CLASS[it.status] || '') + '" data-id="' + it.id + '">' +
        ST.map(function (s) {
          return '<option value="' + s[0] + '"' + (it.status === s[0] ? ' selected' : '') + '>' + s[1] + '</option>';
        }).join('') + '</select></td>' +
        '<td class="pn-sub">' + dt(it.created_at) + '</td>' +
        '</tr>';
      if (open) {
        html += '<tr class="pn-detail"><td colspan="10">' +
          '<div class="pn-dgrid">' +
          '<div><span class="pn-lbl">Wiadomość</span><div class="pn-txt">' + (it.message ? esc(it.message).replace(/\n/g, '<br>') : '—') + '</div></div>' +
          '<div><span class="pn-lbl">Wolumen / moce</span><div class="pn-txt">' + esc(it.monthly_capacity || '—') + '</div>' +
          '<span class="pn-lbl">Pole robocze</span><div class="pn-txt">' + esc(it.build_volume || '—') + '</div>' +
          '<span class="pn-lbl">Źródło</span><div class="pn-txt">' + esc(it.source || '—') + '</div>' +
          '<span class="pn-lbl">Aktualizacja</span><div class="pn-txt">' + dt(it.updated_at) + '</div></div>' +
          '</div>' +
          '<div class="pn-notes">' +
          '<span class="pn-lbl">Notatki wewnętrzne</span>' +
          '<textarea class="pn-ta" id="pnNotes' + it.id + '" rows="3" placeholder="Ustalenia, stawka, warunki, data kontaktu…">' + esc(it.notes || '') + '</textarea>' +
          '<div class="pn-acts">' +
          '<button class="pn-btn" data-save="' + it.id + '">Zapisz notatki</button>' +
          '<a class="pn-btn pn-btn-ghost" href="mailto:' + esc(it.email) +
          '?subject=' + encodeURIComponent('3dfile.link — sieć partnerska druku 3D') +
          '&body=' + encodeURIComponent('Dzień dobry,\n\ndziękujemy za zgłoszenie pracowni do naszej sieci partnerskiej.\n\n') + '">Napisz mail</a>' +
          '</div></div>' +
          '</td></tr>';
      }
    });
    html += '</tbody></table>';
    host.innerHTML = html;

    host.querySelectorAll('.pn-row').forEach(function (tr) {
      tr.addEventListener('click', function (e) {
        if (e.target.closest('select') || e.target.closest('a')) return;
        var id = Number(tr.dataset.id);
        _open[id] = !_open[id];
        render();
      });
    });
    host.querySelectorAll('.pn-status').forEach(function (sel) {
      sel.addEventListener('click', function (e) { e.stopPropagation(); });
      sel.addEventListener('change', function (e) {
        e.stopPropagation();
        patch(Number(sel.dataset.id), { status: sel.value });
      });
    });
    host.querySelectorAll('[data-save]').forEach(function (b) {
      b.addEventListener('click', function (e) {
        e.stopPropagation();
        var id = Number(b.dataset.save);
        var ta = document.getElementById('pnNotes' + id);
        patch(id, { notes: ta ? ta.value : '' });
      });
    });
  }

  function load(force) {
    if (_loaded && !force) { render(); return; }
    var host = shell();
    if (!host) return;
    var url = '/api/admin/partners?limit=500';
    if (_q) url += '&q=' + encodeURIComponent(_q);
    jfetch(url).then(function (r) {
      if (r.status === 401 || r.status === 403) {
        document.getElementById('pnTable').innerHTML =
          '<div class="pn-empty">Brak dostępu — zaloguj się ponownie jako admin.</div>';
        return;
      }
      if (!r.status.toString().startsWith('2')) {
        document.getElementById('pnTable').innerHTML =
          '<div class="pn-empty">Błąd pobierania (' + r.status + ').</div>';
        return;
      }
      _items = (r.body.items || []);
      _counts = r.body.counts || {};
      _target = r.body.target || 5;
      _loaded = true;
      render();
    }).catch(function () {
      document.getElementById('pnTable').innerHTML = '<div class="pn-empty">Błąd sieci.</div>';
    });
  }

  function patch(id, body) {
    jfetch('/api/admin/partners/' + id, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    }).then(function (r) {
      if (r.body && r.body.ok && r.body.item) {
        for (var i = 0; i < _items.length; i++) {
          if (_items[i].id === id) { _items[i] = r.body.item; break; }
        }
        var st = r.body.item.status;
        _counts[st] = (_counts[st] || 0);
        load(true);
        toast('Zapisano: ' + (body.status ? (ST_LABEL[st] || st) : 'notatki'), 'ok');
      } else {
        toast('Nie udało się zapisać (' + (r.status || '?') + ')', 'error');
      }
    }).catch(function () { toast('Nie udało się zapisać', 'error'); });
  }

  window.loadPartners = function () { load(false); };
  window.loadPartnersForce = function () { load(true); };
})();
