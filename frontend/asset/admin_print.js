/* ============================================================
   admin_print.js — panel Drukarni (Zamówienia / Cennik / Kody /
   Galeria / Recenzje / Raporty) dla 3dfile.link.
   Ładowany przez admin.html (hosting). Zero kolizji z admin.js.
   Auth: JWT Bearer przez localStorage 'mt_token' (wspólny token admina).
   ============================================================ */
(function () {
  var AP_TOKEN = 'mt_token';

  function _tok() {
    var t = localStorage.getItem(AP_TOKEN) || localStorage.getItem('token') || '';
    try { if (window.storeToken) t = storeToken() || t; } catch (e) {}
    return t;
  }
  function _auth() { return { 'Authorization': 'Bearer ' + _tok(), 'Accept': 'application/json' }; }
  function _fd() { return { 'Authorization': 'Bearer ' + _tok() }; }

  function _showToast(m, t) {
    if (typeof window.toast === 'function') { window.toast(m, t || ''); return; }
    var el = document.getElementById('toast');
    if (el) { el.textContent = m; el.className = 'toast show ' + (t || ''); clearTimeout(window._apTimer); window._apTimer = setTimeout(function () { el.className = 'toast show hidden'; }, 3000); }
  }
  var showToast = _showToast;

  function esc(s) {
    var o = (s === null || s === undefined) ? '' : String(s);
    return o.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\x22/g, '&quot;').replace(/'/g, '&#39;');
  }

  // Stuby: publiczna galeria/reviews NIE istnieją w tym panelu — no-op.
  window.$ = window.$ || null;
  if (!window.loadGallery) window.loadGallery = function () {};
  if (!window.loadReviews) window.loadReviews = function () {};
  if (!window.renderStars) window.renderStars = function (n) { var o=''; for (var i=1;i<=5;i++) o += i<=n?'★':'☆'; return o; };

  var THINK_PREFIX = '';

  var __adminQ = { search: '', sort: 'newest', page: 1 };

  // Aliasy kompatybilne (body z print.js używa tych nazw)
  window.getStoredToken = function () { return _tok(); };
  var getStoredToken = _tok;
  window.currencySymbol = function () { return 'zł'; };
  var currencySymbol = function () { return 'zł'; };
  if (!window.renderStars) window.renderStars = function (n) { var o=''; for (var i=1;i<=5;i++) o += i<=n?'★':'☆'; return o; };

window.adminSetSearch = function(v, f){ if(f) __adminQ.search=v; __adminQ.page=1; loadAdminOrders(); };
    window.adminSetSort = function(v){ __adminQ.sort=v; __adminQ.page=1; loadAdminOrders(); };
    window.adminPage = function(d){ __adminQ.page = Math.max(1, __adminQ.page + d); loadAdminOrders(); };
    async function loadAdminOrders() {
      var token = getStoredToken();
      var headers = { 'Authorization': 'Bearer ' + token, 'Accept': 'application/json' };
      try {
        var _ao = document.getElementById('adminOrders'); if (_ao) _ao.innerHTML = '<div style="padding:18px;color:#64748b">⏳ Ładowanie zamówień…</div>';
        var q = '/api/orders?t=' + Date.now() + '&page=' + __adminQ.page + '&sort=' + __adminQ.sort;
        if (__adminQ.search) q += '&search=' + encodeURIComponent(__adminQ.search);
        var res = await fetch(q, { headers: headers });
      var data = await res.json();
      if (res.ok && data.ok && data.orders) {
        var tbody = '';
        var ms = ['nowy', 'wycena', 'realizacja', 'drukowane', 'gotowe', 'wysłane', 'dostarczone', 'anulowane'];
        var statusColor = { 'nowy': '#ef4444', 'wycena': '#f59e0b', 'realizacja': '#7c3aed', 'drukowane': '#f59e0b', 'gotowe': '#3b82f6', 'wysłane': '#06b6d4', 'dostarczone': '#10b981', 'anulowane': '#6b7280' };
        data.orders.forEach(function(o) {
          var st = o.status || 'nowy';
          var opts = ms.map(function(m) { return '<option value="' + m + '"' + (m === st ? ' selected' : '') + '>' + m + '</option>'; }).join('');
          tbody += '<tr style="border-bottom:1px solid #e5e7eb;vertical-align:top">' +
            '<td style="padding:8px;font-weight:600">#' + o.id + '</td>' +
            '<td style="padding:8px;white-space:nowrap">' + new Date(o.created_at).toLocaleString('en-GB') + '</td>' +
            '<td style="padding:8px"><strong>' + (o.customer_name || '') + '</strong><br><span style="color:#6b7280;font-size:11px">' + (o.customer_email || '') + (o.customer_phone ? '<br>' + o.customer_phone : '') + '</span><br><span style="color:#9ca3af;font-size:11px">' + (o.customer_city || '') + ' ' + (o.customer_country || '') + '</span></td>' +
            '<td style="padding:8px">' + (function(){
          var items = (o.items && o.items.length) ? o.items : (o.material ? [{ model_name: (o.job_uuid ? '' : ''), material: o.material, color: o.color, quantity: o.quantity || 1, job_uuid: o.job_uuid }] : []);
          return items.map(function(it){
            var dl = '';
            if (it.job_uuid) { var _tokq = (function(){ var t=localStorage.getItem('mt_token')||localStorage.getItem('token')||''; return t ? '&token=' + encodeURIComponent(t) : ''; })();
              dl = '<div style="margin-top:2px;white-space:nowrap">' +
              '<a href="/download/' + it.job_uuid + '?format=stl' + _tokq + '" target="_blank" style="font-size:11px" title="Pobierz STL">⬇ STL</a> ' +
              '<a href="/download/' + it.job_uuid + '?format=3mf' + _tokq + '" target="_blank" style="font-size:11px" title="Pobierz oryginalny 3MF">⬇ 3MF</a> ' +
              '<a href="/download/' + it.job_uuid + '?format=obj' + _tokq + '" target="_blank" style="font-size:11px" title="Pobierz OBJ">⬇ OBJ</a></div>'; }
            return '<div style="font-size:11px">' + (it.model_name ? '📄 ' + esc(it.model_name) + ' ' : '📦 model ') +
                   (it.material ? '<span style="color:#6b7280">' + esc(it.material) + (it.color ? ' / ' + esc(it.color) : '') + '</span>' : '') +
                   (it.quantity > 1 ? ' ×' + it.quantity : '') + dl + '</div>';
          }).join('');
        })() + '</td>' +
            '<td style="padding:8px">' + (o.filament_grams || 0) + 'g<br><span style="color:#9ca3af;font-size:11px">' + (o.printing_hours || 0) + 'h</span></td>' +
            '<td style="padding:8px"><span style="color:#6b7280;font-size:11px">Fil ' + (o.filament_cost || 0).toFixed(0) + 'zł | Marża ' + (o.margin_pln || 0).toFixed(0) + 'zł</span><br><strong>' + (o.total || 0).toFixed(2) + ' ' + (o.currency || 'PLN') + '</strong><br><span style="color:#10b981;font-size:11px">Profit ' + ((o.total || 0) - (o.filament_cost || 0) - (o.electricity_cost || 0) - (o.shipping_cost || 0)).toFixed(0) + 'zł</span></td>' +
            '<td style="padding:8px"><select onchange="updateOrderStatus(' + o.id + ', this.value)" style="padding:4px;border:1px solid #d1d5db;border-radius:4px;font-size:12px;color:' + (statusColor[st] || '#6b7280') + '">' + opts + '</select></td>' +
            '<td style="padding:8px;text-align:center"><input type="checkbox" ' + (o.is_paid ? 'checked' : '') + ' onchange="toggleOrderPaid(' + o.id + ', this.checked)" title="Zapłacone"></td>' +
            '<td style="padding:8px"><button data-action="exportOrder" data-id="' + o.id + '" style="padding:4px 8px;border:1px solid #d1d5db;border-radius:4px;cursor:pointer">CSV</button><br>' +
                        (o.job_id ? '<button onclick="window.open(\'/e/' + o.job_id + '\',\'_blank\')" style="padding:4px 8px;border:1px solid #3b82f6;color:#3b82f6;border-radius:4px;background:none;cursor:pointer;margin-top:4px">3D</button><br>' : '') +
                        '<button onclick="showOrderNotes(' + o.id + ')" style="padding:4px 8px;border:1px solid #d1d5db;border-radius:4px;cursor:pointer;margin-top:4px">Uwagi</button><br>' +
                        '<button onclick="deleteOrder(' + o.id + ')" style="padding:4px 8px;border:1px solid #ef4444;color:#ef4444;border-radius:4px;background:none;cursor:pointer;margin-top:4px">Usuń</button></td>' +
            '</tr>';
        });
        document.getElementById('adminOrders').innerHTML =
                  '<div class="admin-toolbar" style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:12px">' +
                  '<input type="text" id="adminSearchInp" placeholder="🔎 Szukaj: nazwa, tel, email, adres, miasto, uwagi…" value="' + (__adminQ.search||'').replace(/\"/g,'&quot;') + '" onkeydown="if(event.key===\'Enter\')adminSetSearch(this.value,true)" style="padding:8px 12px;border:1px solid #d1d5db;border-radius:8px;min-width:260px;font-size:13px">' +
                  '<button onclick="adminSetSearch(document.getElementById(\'adminSearchInp\').value,true)" style="padding:8px 14px;border:1px solid #1d4ed8;background:#1d4ed8;color:#fff;border-radius:8px;cursor:pointer">Szukaj</button>' +
                  '<select onchange="adminSetSort(this.value)" style="padding:8px;border:1px solid #d1d5db;border-radius:8px;font-size:12px">' +
                    '<option value="newest"' + (__adminQ.sort==='newest'?'selected':'') + '>Najnowsze</option>' +
                    '<option value="oldest"' + (__adminQ.sort==='oldest'?'selected':'') + '>Najstarsze</option>' +
                    '<option value="total"' + (__adminQ.sort==='total'?'selected':'') + '>Wartość od najwyższej</option>' +
                  '</select>' +
                  '<strong>Zamówienia: ' + data.total + '</strong>' +
                  '<button onclick="exportAllOrders()" style="padding:8px 16px;border:1px solid #1d4ed8;background:#1d4ed8;color:#fff;border-radius:8px;cursor:pointer">Export Excel</button>' +
                  '</div>' +
                  '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:12px"><thead><tr style="border-bottom:2px solid #e5e7eb;text-align:left"><th style="padding:8px">ID</th><th style="padding:8px">Data</th><th style="padding:8px">Klient</th><th style="padding:8px">Model</th><th style="padding:8px">Fil.</th><th style="padding:8px">Cena</th><th style="padding:8px">Status</th><th style="padding:8px;text-align:center">Zapł.</th><th style="padding:8px">Akcje</th></tr></thead><tbody>' + tbody + '</tbody></table></div>' +
                  '<div style="margin-top:10px;display:flex;gap:8px;align-items:center">' +
                    '<button onclick="adminPage(-1)" ' + (__adminQ.page<=1?'disabled':'') + ' style="padding:6px 12px;border:1px solid #d1d5db;border-radius:8px;cursor:pointer">← Poprzednia</button>' +
                    '<span style="font-size:13px;color:#6b7280">Strona ' + __adminQ.page + '</span>' +
                    '<button onclick="adminPage(1)" ' + ((__adminQ.page*data.limit||50)>=data.total?'disabled':'') + ' style="padding:6px 12px;border:1px solid #d1d5db;border-radius:8px;cursor:pointer">Następna →</button>' +
                  '</div>';
      } else {
        document.getElementById('adminOrders').innerHTML = '<p style="color:#ef4444">Brak dostępu lub brak zamówień</p>';
      }
    } catch (e) {
      document.getElementById('adminOrders').innerHTML = '<p style="color:#ef4444;padding:12px">Błąd: '+ (e && e.message ? e.message : e) +'</p>';
    }
  }

  window.exportOrder = function(orderId) {
      fetch('/api/orders/' + orderId + '/export?t=' + Date.now(), {
        headers: { 'Authorization': 'Bearer ' + getStoredToken(), 'Accept': 'text/csv' }
      }).then(function(r) {
        if (!r.ok) { showToast('Błąd eksportu (' + r.status + ')', 'error'); return; }
        return r.blob();
      }).then(function(b) {
        if (!b) return;
        var url = URL.createObjectURL(b);
        var a = document.createElement('a');
        a.href = url; a.download = 'zamowienie_' + orderId + '_' + Date.now() + '.csv';
        document.body.appendChild(a); a.click(); document.body.removeChild(a);
        setTimeout(function() { URL.revokeObjectURL(url); }, 5000);
      });
    };
    window.exportAllOrders = function() {
      fetch('/api/orders/export?t=' + Date.now(), {
        headers: { 'Authorization': 'Bearer ' + getStoredToken(), 'Accept': 'text/csv' }
      }).then(function(r) {
        if (!r.ok) { showToast('Błąd eksportu (' + r.status + ')', 'error'); return; }
        return r.blob();
      }).then(function(b) {
        if (!b) return;
        var url = URL.createObjectURL(b);
        var a = document.createElement('a');
        a.href = url; a.download = 'zamowienia_3dfile_' + Date.now() + '.csv';
        document.body.appendChild(a); a.click(); document.body.removeChild(a);
        setTimeout(function() { URL.revokeObjectURL(url); }, 5000);
      });
    };

  window.updateOrderStatus = function(id, status) {
    fetch('/api/orders/' + id + '?' + Date.now(), {
      method: 'PATCH',
      headers: { 'Authorization': 'Bearer ' + getStoredToken(), 'Content-Type': 'application/x-www-form-urlencoded' },
      body: 'status=' + encodeURIComponent(status)
    }).then(function(r) { if (r.ok) { showToast('Status #' + id + ' → ' + status, 'success'); } else { showToast('Błąd zmiany statusu', 'error'); } });
  };

  window.toggleOrderPaid = function(id, checked) {
    fetch('/api/orders/' + id + '?' + Date.now(), {
      method: 'PATCH',
      headers: { 'Authorization': 'Bearer ' + getStoredToken(), 'Content-Type': 'application/x-www-form-urlencoded' },
      body: 'is_paid=' + (checked ? '1' : '0')
    }).then(function(r) { if (r.ok) { showToast('#' + id + ' zapłacone: ' + (checked ? 'TAK' : 'NIE'), 'success'); } else { showToast('Błąd', 'error'); } });
  };

  window.showOrderNotes = function(id) {
    var notes = prompt('Notatki do zamówienia #' + id + ' (dla klienta):');
    if (notes === null) return;
    fetch('/api/orders/' + id + '?' + Date.now(), {
      method: 'PATCH',
      headers: { 'Authorization': 'Bearer ' + getStoredToken(), 'Content-Type': 'application/x-www-form-urlencoded' },
      body: 'notes=' + encodeURIComponent(notes || '')
    }).then(function(r) { if (r.ok) showToast('Notatki zapisane', 'success'); });
  };

  async function loadAdminStats() {
    var headers = { 'Authorization': 'Bearer ' + getStoredToken(), 'Accept': 'application/json' };
    try {
      var res = await fetch('/api/orders/stats?' + Date.now(), { headers: headers });
      var data = await res.json();
      if (res.ok && data.stats) {
        var s = data.stats;
        var cards = [
          ['Zamówienia', s.total_orders],
          ['Zapłacone', s.paid_orders],
          ['Nieopłacone', s.unpaid_orders],
          ['Przychód (PLN)', s.total_revenue_pln + ' zł']
        ].map(function(c) {
          return '<div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:12px;padding:12px"><div style="font-size:11px;color:#6b7280">' + c[0] + '</div><div style="font-size:20px;font-weight:700">' + c[1] + '</div></div>';
        }).join('');
        var byStatus = (s.by_status || []).map(function(x) { return x.status + ': <strong>' + x.count + '</strong>'; }).join(' &middot; ') || '—';
        var byMat = (s.by_material || []).map(function(x) { return x.material + ': <strong>' + x.count + '</strong>'; }).join(' &middot; ') || '—';
        var byCountry = (s.by_country || []).map(function(x) { return x.country + ': <strong>' + x.count + '</strong>'; }).join(' &middot; ') || '—';
        document.getElementById('adminStats').innerHTML =
          '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px">' + cards + '</div>' +
          '<div style="margin-top:16px;display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px">' +
          '<div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:12px"><div style="font-size:11px;color:#6b7280;margin-bottom:6px">Statusy</div><div style="font-size:13px">' + byStatus + '</div></div>' +
          '<div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:12px"><div style="font-size:11px;color:#6b7280;margin-bottom:6px">Materiały</div><div style="font-size:13px">' + byMat + '</div></div>' +
          '<div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:12px"><div style="font-size:11px;color:#6b7280;margin-bottom:6px">Kraje</div><div style="font-size:13px">' + byCountry + '</div></div></div>';
      }
    } catch (e) {}
  }

  async function loadAdminPricing() {
    var headers = { 'Authorization': 'Bearer ' + getStoredToken(), 'Accept': 'application/json' };
    try {
      var res = await fetch('/api/admin/pricing?' + Date.now(), { headers: headers });
      var data = await res.json();
      var html = '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:13px"><thead><tr style="border-bottom:2px solid #e5e7eb;text-align:left"><th style="padding:6px">Klucz</th><th style="padding:6px">Wartość</th><th style="padding:6px">Typ</th></tr></thead><tbody>';
      (data || []).forEach(function(r) {
        var safeKey = String(r.key).replace(/'/g, "\\'");
        html += '<tr style="border-bottom:1px solid #e5e7eb"><td style="padding:6px">' + r.key + '</td><td style="padding:6px"><input type="text" value="' + r.value + '" onchange="updatePricing(\'' + safeKey + '\', this.value)" style="width:140px;padding:4px;font-size:12px"></td><td style="padding:6px;color:#9ca3af">' + r.kind + '</td></tr>';
      });
      html += '</tbody></table></div>';
      document.getElementById('adminPricing').innerHTML = html;
    } catch (e) {}
  }

  window.updatePricing = function(key, value) {
    var token = getStoredToken();
    fetch('/api/admin/pricing?' + Date.now(), {
      method: 'POST',
      headers: { 'Authorization': 'Bearer ' + token, 'Content-Type': 'application/x-www-form-urlencoded' },
      body: 'key=' + encodeURIComponent(key) + '&value=' + encodeURIComponent(value)
    }).then(function(r) { if (r.ok) showToast('Zapisano', 'success'); else showToast('Błąd zapisu', 'error'); });
  };

  // — discount codes tab —
  async function loadAdminCodes() {
    var headers = { 'Authorization': 'Bearer ' + getStoredToken(), 'Accept': 'application/json' };
    var el = document.getElementById('adminCodes');
    if (!el) return;
    try {
      var res = await fetch('/api/admin/discount_codes?' + Date.now(), { headers: headers });
      var data = res.ok ? await res.json() : [];
      var rows = (data || []).map(function(c) {
        return '<tr style="border-bottom:1px solid #e5e7eb"><td style="padding:8px;font-weight:600">' + c.code + '</td>' +
          '<td style="padding:8px">' + (c.discount_pln || 0) + ' zł' + (c.discount_pct ? ' / ' + c.discount_pct + '%' : '') + '</td>' +
          '<td style="padding:8px">' + (c.is_active ? '<span style="color:#10b981">aktywny</span>' : '<span style="color:#ef4444">nieaktywny</span>') + '</td>' +
          '<td style="padding:8px">' + (c.uses || 0) + '/' + (c.max_uses || '∞') + '</td>' +
          '<td style="padding:8px"><button onclick="deleteDiscountCode(\'' + c.code + '\')" style="padding:4px 8px;border:1px solid #ef4444;color:#ef4444;border-radius:4px;background:none;cursor:pointer">Usuń</button></td></tr>';
      }).join('');
      el.innerHTML =
        '<div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:16px;margin-bottom:16px"><strong>Dodaj kod rabatowy</strong>' +
        '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px">' +
        '<input id="codeName" placeholder="Kod (np. DZIE10)" style="padding:8px;border:1px solid #d1d5db;border-radius:6px;flex:1;min-width:120px">' +
        '<input id="codePln" type="number" placeholder="Rabat zł" style="padding:8px;border:1px solid #d1d5db;border-radius:6px;width:90px">' +
        '<input id="codePct" type="number" placeholder="Rabat %" style="padding:8px;border:1px solid #d1d5db;border-radius:6px;width:90px">' +
        '<input id="codeMax" type="number" placeholder="Max użyć" style="padding:8px;border:1px solid #d1d5db;border-radius:6px;width:90px">' +
        '<button onclick="addDiscountCode()" style="padding:8px 16px;background:#1d4ed8;color:#fff;border:none;border-radius:6px;cursor:pointer">Dodaj</button></div></div>' +
        '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:13px"><thead><tr style="border-bottom:2px solid #e5e7eb;text-align:left"><th style="padding:8px">Kod</th><th style="padding:8px">Rabat</th><th style="padding:8px">Status</th><th style="padding:8px">Użycia</th><th style="padding:8px">Akcja</th></tr></thead><tbody>' + rows + '</tbody></table></div>';
    } catch (e) {
      el.innerHTML = '<p style="color:#ef4444">Błąd ładowania kodów</p>';
    }
  }

  window.addDiscountCode = function() {
    var code = (document.getElementById('codeName') || {}).value || '';
    var pln = (document.getElementById('codePln') || {}).value || '0';
    var pct = (document.getElementById('codePct') || {}).value || '0';
    var max = (document.getElementById('codeMax') || {}).value || '0';
    if (!code) { showToast('Podaj nazwę kodu', 'error'); return; }
    fetch('/api/admin/discount_codes?' + Date.now(), {
      method: 'POST',
      headers: { 'Authorization': 'Bearer ' + getStoredToken(), 'Content-Type': 'application/x-www-form-urlencoded' },
      body: 'code=' + encodeURIComponent(code) + '&discount_pln=' + pln + '&discount_pct=' + pct + '&max_uses=' + max + '&is_active=1&min_order_pln=0'
    }).then(function(r) { if (r.ok) { showToast('Kod dodany', 'success'); loadAdminCodes(); } else showToast('Błąd', 'error'); });
  };

  window.deleteDiscountCode = function(code) {
    if (!confirm('Usunąć kod ' + code + '?')) return;
    fetch('/api/admin/discount_codes/' + encodeURIComponent(code) + '?' + Date.now(), {
      method: 'DELETE',
      headers: { 'Authorization': 'Bearer ' + getStoredToken() }
    }).then(function(r) { if (r.ok) { showToast('Usunięto', 'success'); loadAdminCodes(); } });
  };

  /* ==== Init ==== */
  // event delegation for dynamically created buttons
  
document.addEventListener('click', function(e) {
    var btn = e.target.closest('[data-currency]');
    if (btn) { setCurrency(btn.dataset.currency); return; }
    btn = e.target.closest('[data-action]');
    if (btn && btn.dataset.action === 'exportOrder') { exportOrder(parseInt(btn.dataset.id)); return; }
  });

  

  /* ── MATERIAŁY + SYMULATOR KOSZTÓW (admin) ───────────────────────── */
  var _matState = null;
  function _pf(rows, key, dflt) {
    var r = rows.filter(function(x){ return x.key === key; })[0];
    return r ? parseFloat(r.value) : dflt;
  }
  window.loadAdminMaterials = function() {
    var box = document.getElementById('adminMaterials'); if (!box) return;
    box.innerHTML = '<div style="padding:18px;color:#64748b">⏳ Ładowanie cennika materiałów…</div>';
    fetch('/api/admin/pricing?t=' + Date.now(), { headers: { 'Authorization': 'Bearer ' + getStoredToken() } })
      .then(function(r){ return r.json(); })
      .then(function(rows){
        _matState = rows;
        var mats = rows.filter(function(r){ return r.key.indexOf('material:') === 0; }).map(function(r){ return r.key.slice(9); });
        var margin = _pf(rows, 'margin_percent', 68), kwh = _pf(rows, 'kwh_pln', 1.5), watts = _pf(rows, 'watts', 150);
        var head = '<div style="font-size:12px;color:#6b7280;margin-bottom:10px">Silnik wyceny: <b>cena klienta = (koszt materiału + prąd + premium koloru) × (1 + marża/100)</b>. Marża globalna teraz: <b>' + margin + '% narzutu</b> (efektywna marża od ceny: ' + (margin/(1+margin/100)*1).toFixed(1) + '%). Wszystkie pola edytowalne — zapis trafia do bazy i natychmiast zmienia ceny dla klientów.</div>';
        var tbl = '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:13px"><thead><tr style="border-bottom:2px solid #e5e7eb;text-align:left">' +
          '<th style="padding:8px">Materiał</th><th style="padding:8px">Cena szpuli (zł/kg)</th><th style="padding:8px">Gęstość (g/cm³)</th>' +
          '<th style="padding:8px">Przepust. (mm³/s)</th><th style="padding:8px">g na 10 cm³</th><th style="padding:8px">Koszt / 10 cm³</th>' +
          '<th style="padding:8px">Cena klienta 10 cm³*</th><th style="padding:8px">Cena 50 cm³*</th><th style="padding:8px">Zapisz</th></tr></thead><tbody>';
        mats.forEach(function(m){
          var price = _pf(rows, 'material:' + m, 100), dens = _pf(rows, 'density:' + m, 1.24), th = _pf(rows, 'throughput:' + m, 200);
          tbl += '<tr style="border-bottom:1px solid #f1f5f9" data-mat="' + esc(m) + '">' +
            '<td style="padding:8px;font-weight:600">' + esc(m) + '</td>' +
            '<td><input data-k="material:' + esc(m) + '" type="number" step="0.01" value="' + price + '" style="width:90px;padding:5px;border:1px solid #d1d5db;border-radius:6px"></td>' +
            '<td><input data-k="density:' + esc(m) + '" type="number" step="0.01" value="' + dens + '" style="width:70px;padding:5px;border:1px solid #d1d5db;border-radius:6px"></td>' +
            '<td><input data-k="throughput:' + esc(m) + '" type="number" step="1" value="' + th + '" style="width:80px;padding:5px;border:1px solid #d1d5db;border-radius:6px"></td>' +
            '<td style="padding:8px" class="mc-g10"></td><td style="padding:8px" class="mc-cost"></td>' +
            '<td style="padding:8px;font-weight:600" class="mc-p10"></td><td style="padding:8px;font-weight:600" class="mc-p50"></td>' +
            '<td><button data-action="saveMat" data-mat="' + esc(m) + '" style="padding:5px 12px;background:#1d4ed8;color:#fff;border:none;border-radius:6px;cursor:pointer">Zapisz</button></td></tr>';
        });
        tbl += '</tbody></table></div><div style="font-size:11px;color:#9ca3af;margin-top:6px">* przy marży ' + margin + '%, prąd z ' + watts + 'W × ' + kwh + ' zł/kWh, bez wysyłki i bez minimum 3 zł (cena samego wydruku).</div>';
        box.innerHTML = head + tbl + _simHTML(mats);
        _recalcMatRows();
      })
      .catch(function(e){ box.innerHTML = '<p style="color:#ef4444">Błąd: ' + e.message + '</p>'; });
  };
  function _simHTML(mats) {
    var opts = mats.map(function(m){ return '<option>' + esc(m) + '</option>'; }).join('');
    return '<div style="margin-top:22px;padding:16px;border:1px solid #e5e7eb;border-radius:12px">' +
      '<h3 style="margin:0 0 10px;font-size:15px">🧮 Symulator kosztów i zysków (co-ifla bez zapisu)</h3>' +
      '<div style="display:flex;flex-wrap:wrap;gap:10px;align-items:flex-end;font-size:13px">' +
      '<label>Obj. cm³<br><input id="simVol" type="number" value="50" style="width:80px;padding:6px;border:1px solid #d1d5db;border-radius:6px"></label>' +
      '<label>Ilość szt<br><input id="simQty" type="number" value="1" style="width:60px;padding:6px;border:1px solid #d1d5db;border-radius:6px"></label>' +
      '<label>Materiał<br><select id="simMat" style="padding:6px;border:1px solid #d1d5db;border-radius:6px">' + opts + '</select></label>' +
      '<label>Kolory<br><input id="simCol" type="number" value="1" min="1" style="width:56px;padding:6px;border:1px solid #d1d5db;border-radius:6px"></label>' +
      '<label>Wysyłka<br><select id="simShip" style="padding:6px;border:1px solid #d1d5db;border-radius:6px"><option value="pickup">odbiór 0 zł</option><option value="pickup_express">odbiór ekspres 19</option><option value="standard" selected>paczkomat PL</option></select></label>' +
      '<label>💰 REALNA cena szpuli zł/kg (co-if)<br><input id="simSpool" type="number" step="0.01" placeholder="z tabeli" style="width:110px;padding:6px;border:1px dashed #b45309;border-radius:6px"></label>' +
      '<label>Marża narzut % (co-if)<br><input id="simMargin" type="number" step="0.1" placeholder="globalna" style="width:100px;padding:6px;border:1px dashed #b45309;border-radius:6px"></label>' +
      '<button onclick="runSim()" style="padding:8px 16px;background:#0B1730;color:#fff;border:none;border-radius:8px;cursor:pointer">Licz</button>' +
      '<button onclick="verifySim()" style="padding:8px 16px;background:#fff;color:#1d4ed8;border:1px solid #1d4ed8;border-radius:8px;cursor:pointer">Zweryfikuj z silnikiem API</button>' +
      '</div><div id="simOut" style="margin-top:12px"></div></div>';
  }
  function _matVals(m) {
    var rows = _matState || [];
    return { price: _pf(rows, 'material:' + m, 100), dens: _pf(rows, 'density:' + m, 1.24), th: _pf(rows, 'throughput:' + m, 200) };
  }
  function _recalcMatRows() {
    var rows = _matState || [];
    var margin = _pf(rows, 'margin_percent', 68), kwh = _pf(rows, 'kwh_pln', 1.5), watts = _pf(rows, 'watts', 150);
    document.querySelectorAll('#adminMaterials tbody tr[data-mat]').forEach(function(tr){
      var m = tr.getAttribute('data-mat');
      var price = parseFloat(tr.querySelector('[data-k^="material:"]').value) || 0;
      var dens = parseFloat(tr.querySelector('[data-k^="density:"]').value) || 1.24;
      var th = parseFloat(tr.querySelector('[data-k^="throughput:"]').value) || 200;
      function priceFor(vol) {
        var g = vol * dens;
        var fcost = g / 1000 * price;
        var hours = Math.max(0.25, vol * 1000 / (th * 3600)) + 0.1;
        var ecost = watts / 1000 * hours * kwh;
        var sub = fcost + ecost;
        return { g: g, cost: sub, price: Math.max(3, sub * (1 + margin / 100)) };
      }
      var p10 = priceFor(10), p50 = priceFor(50);
      tr.querySelector('.mc-g10').textContent = p10.g.toFixed(1) + ' g';
      tr.querySelector('.mc-cost').textContent = p10.cost.toFixed(2) + ' zł';
      tr.querySelector('.mc-p10').textContent = p10.price.toFixed(2) + ' zł';
      tr.querySelector('.mc-p50').textContent = p50.price.toFixed(2) + ' zł';
    });
  }
  window.runSim = function() {
    if (!_matState) return;
    var vol = parseFloat(document.getElementById('simVol').value) || 0;
    var qty = parseInt(document.getElementById('simQty').value) || 1;
    var m = document.getElementById('simMat').value;
    var ncol = parseInt(document.getElementById('simCol').value) || 1;
    var ship = document.getElementById('simShip').value;
    var v = _matVals(m);
    var price = parseFloat(document.getElementById('simSpool').value); if (isNaN(price)) price = v.price;
    var margin = parseFloat(document.getElementById('simMargin').value); if (isNaN(margin)) margin = _pf(_matState, 'margin_percent', 68);
    var kwh = _pf(_matState, 'kwh_pln', 1.5), watts = _pf(_matState, 'watts', 150);
    var g = vol * v.dens * qty;
    var fcost = g / 1000 * price;
    var hours = (Math.max(0.25, vol * 1000 / (v.th * 3600)) + 0.1) * qty;
    var ecost = watts / 1000 * hours * kwh;
    var cprem = ncol > 1 ? (20 + (ncol - 2) * 10) * qty : 0;
    var cost = fcost + ecost + cprem;
    var product = Math.max(3 * qty, cost * (1 + margin / 100));
    var pack = _pf(_matState, 'packing_pln', 3);
    var shipCost = ship === 'pickup' ? 0 : ship === 'pickup_express' ? 19 : 16.49 + pack;
    if (shipCost > 0 && product < 40 && ship === 'standard') shipCost = Math.min(shipCost, 9.90);
    if (shipCost > 0 && product >= 200 && ship === 'standard') shipCost = 0;
    var total = product + shipCost;
    var profit = product - cost; // wysyłka po kosztach (flat/promocja może dopłacać — liczona osobno)
    var eff = total > 0 ? (profit / total * 100) : 0;
    var netto = total / 1.23;
    document.getElementById('simOut').innerHTML =
      '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;font-size:13px">' +
      '<div style="padding:10px;background:#f8fafc;border-radius:8px">Filtrament<br><b>' + g.toFixed(1) + ' g</b> · ' + fcost.toFixed(2) + ' zł</div>' +
      '<div style="padding:10px;background:#f8fafc;border-radius:8px">Prąd (' + hours.toFixed(1) + ' h)<br><b>' + ecost.toFixed(2) + ' zł</b></div>' +
      '<div style="padding:10px;background:#f8fafc;border-radius:8px">Premium kolory<br><b>' + cprem.toFixed(2) + ' zł</b></div>' +
      '<div style="padding:10px;background:#fef3c7;border-radius:8px">Koszt własny SUMA<br><b>' + cost.toFixed(2) + ' zł</b></div>' +
      '<div style="padding:10px;background:#dcfce7;border-radius:8px">Cena klienta (druk)<br><b>' + product.toFixed(2) + ' zł</b></div>' +
      '<div style="padding:10px;background:#e0e7ff;border-radius:8px">Wysyłka<br><b>' + shipCost.toFixed(2) + ' zł</b></div>' +
      '<div style="padding:10px;background:#0B1730;color:#fff;border-radius:8px">DO ZAPŁATY<br><b>' + total.toFixed(2) + ' zł</b> <span style="font-size:11px">netto ' + netto.toFixed(2) + '</span></div>' +
      '<div style="padding:10px;background:' + (profit > 0 ? '#dcfce7' : '#fee2e2') + ';border-radius:8px">Zysk na zamówieniu<br><b>' + profit.toFixed(2) + ' zł</b> · ' + eff.toFixed(1) + '% ceny</div>' +
      '</div><div style="font-size:12px;color:#6b7280;margin-top:8px">Break-even: przy tym koszcie (' + cost.toFixed(2) + ' zł) minimalna cena bez straty = <b>' + cost.toFixed(2) + ' zł</b> (narzut 0%). Przy marży docelowej X% ze sprzedaży: cena = koszt/(1−X). Np. 30% marży od ceny → ' + (cost / 0.7).toFixed(2) + ' zł.</div>';
  };
  window.verifySim = function() {
    var vol = parseFloat(document.getElementById('simVol').value) || 0;
    var m = document.getElementById('simMat').value;
    var fd = new FormData();
    fd.append('material', m); fd.append('color', 'black'); fd.append('quantity', document.getElementById('simQty').value || '1');
    fd.append('volume_cm3', vol); fd.append('estimated_hours', '0'); fd.append('shipping', document.getElementById('simShip').value);
    fd.append('shipping_region', 'PL'); fd.append('currency', 'PLN');
    fetch('/api/calculate?t=' + Date.now(), { method: 'POST', body: fd })
      .then(function(r){ return r.json(); })
      .then(function(d){
        var el = document.getElementById('simOut');
        el.innerHTML += '<div style="margin-top:8px;padding:10px;border:1px solid #1d4ed8;border-radius:8px;font-size:13px">🔌 Silnik API dla tych samych danych (bez co-ifli): <b>cena ' + (d.total != null ? d.total.toFixed(2) : '?') + ' ' + (d.currency || 'PLN') + '</b> · produkt ' + (d.product_subtotal != null ? d.product_subtotal.toFixed(2) : '?') + ' zł · druk ' + (d.print_hours != null ? d.print_hours : '?') + ' h · części ' + (d.parts || 1) + '. Różnica z symulatorem = twoje co-ifle (realna szpula / marża).</div>';
      }).catch(function(e){ alert('Błąd weryfikacji: ' + e.message); });
  };
  document.addEventListener('click', function(e) {
    var b = e.target.closest('[data-action="saveMat"]');
    if (!b) return;
    var tr = b.closest('tr');
    var inputs = tr.querySelectorAll('input[data-k]');
    var jobs = [];
    inputs.forEach(function(inp){
      jobs.push(fetch('/api/admin/pricing', { method: 'POST', headers: { 'Authorization': 'Bearer ' + getStoredToken(), 'Content-Type': 'application/x-www-form-urlencoded' },
        body: 'key=' + encodeURIComponent(inp.getAttribute('data-k')) + '&value=' + encodeURIComponent(inp.value) + '&kind=float' }));
    });
    Promise.all(jobs).then(function(rs){
      var ok = rs.every(function(r){ return r.ok; });
      showToast(ok ? 'Zapisano — ceny klientów przeliczone' : 'Część zapisu nie powiodła się', ok ? 'success' : 'error');
      if (ok) loadAdminMaterials();
    });
  });
  document.addEventListener('input', function(e){ if (e.target.closest('#adminMaterials tbody')) _recalcMatRows(); });


  window.renderStars = function(n) {
    var out = '';
    for (var i = 1; i <= 5; i++) out += i <= n ? '★' : '☆';
    return out;
  };
  
window.loadAdminGallery = function() {
    var box = document.getElementById('adminGallery');
    if (!box) return;
    var headers = { 'Authorization': 'Bearer ' + getStoredToken(), 'Accept': 'application/json' };
    fetch('/api/admin/gallery?t=' + Date.now(), { headers: headers }).then(function(r){ return r.json(); }).then(function(d){
      var items = (d && d.items) || [];
      var rows = items.map(function(g){
        return '<div class="gallery-item" style="display:flex;gap:10px;align-items:center;border:1px solid var(--border);border-radius:10px;padding:8px;margin-bottom:8px;background:var(--card)">' +
          (g.image? '<img src="' + g.image + '" style="width:56px;height:56px;object-fit:cover;border-radius:8px">':'<div style="width:56px;height:56px;background:#e5e7eb;border-radius:8px"></div>') +
          '<div style="flex:1"><b>' + esc(g.title||'') + '</b><br><span style="color:var(--muted);font-size:12px">' + (g.material||'') + (g.color?' · '+esc(g.color):'') + (g.is_active===false?' · <span style="color:#ef4444">ukryta</span>':'') + '</span></div>' +
          '<button onclick="toggleGalleryItem(' + g.id + ')" style="padding:5px 10px;border:1px solid var(--border);border-radius:7px;cursor:pointer;font-size:12px">' + (g.is_active === false ? 'Pokaż' : 'Ukryj') + '</button>' +
          '<button onclick="delGalleryItem(' + g.id + ')" style="padding:5px 10px;border:1px solid #dc2626;color:#dc2626;border-radius:7px;cursor:pointer;font-size:12px;background:none">Usuń</button>' +
          '</div>';
      }).join('');
      box.innerHTML =
        '<div style="background:var(--card);border:1px solid var(--border);border-radius:12px;padding:16px;margin-bottom:16px"><b>Dodaj pracę do galerii</b>' +
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px">' +
        '<input id="galTitle" placeholder="Tytuł (np. Obudowa robota)" style="padding:8px;border:1px solid var(--border);border-radius:8px">' +
        '<input id="galMat" placeholder="Materiał (np. PETG)" style="padding:8px;border:1px solid var(--border);border-radius:8px">' +
        '<input id="galColor" placeholder="Kolor" style="padding:8px;border:1px solid var(--border);border-radius:8px">' +
        '<input id="galFile" type="file" accept="image/*" style="padding:6px;border:1px solid var(--border);border-radius:8px">' +
        '</div>' +
        '<textarea id="galDesc" rows="2" placeholder="Krótki opis (opcjonalnie)" style="width:100%;padding:8px;border:1px solid var(--border);border-radius:8px;margin-top:8px"></textarea>' +
        '<button onclick="addGalleryItem()" style="margin-top:8px;padding:9px 16px;background:var(--accent);color:#fff;border:none;border-radius:8px;cursor:pointer">Dodaj do galerii</button></div>' +
        (rows ? '<b style="font-size:13px">Wpisy (' + items.length + '):</b>' + rows : '<p style="color:var(--muted)">Brak wpisów.</p>');
    }).catch(function(){ box.innerHTML = '<p style="color:var(--error)">Błąd ładowania galerii</p>'; });
  };

  window.addGalleryItem = function() {
    var title = (document.getElementById('galTitle')||{}).value||'';
    var file = (document.getElementById('galFile')||{}).files ? document.getElementById('galFile').files[0] : null;
    if (!title) { showToast('Podaj tytuł', 'error'); return; }
    if (!file) { showToast('Wybierz obrazek', 'error'); return; }
    var rd = new FileReader(); rd.onloadend = function(){
      var data = rd.result ? String(rd.result) : '';
      var body = {
        title: title,
        material: (document.getElementById('galMat')||{}).value||'',
        color: (document.getElementById('galColor')||{}).value||'',
        description: (document.getElementById('galDesc')||{}).value||'',
        image: data
      };
      fetch('/api/admin/gallery', { method:'POST', headers:{ 'Content-Type':'application/json','Authorization':'Bearer '+getStoredToken() }, body: JSON.stringify(body) })
        .then(function(r){ return r.json(); }).then(function(d){
          if (d.ok) { showToast('Dodano do galerii', 'success'); loadAdminGallery(); loadGallery(); } else showToast((d.detail)||'Błąd', 'error');
        }).catch(function(){ showToast('Błąd sieci', 'error'); });
    };
    rd.readAsDataURL(file);
  };

  window.toggleGalleryItem = function(id) {
    fetch('/api/admin/gallery/' + id + '/toggle', { method:'POST', headers:{ 'Authorization':'Bearer '+getStoredToken() } })
      .then(function(r){ loadAdminGallery(); loadGallery(); });
  };
  window.delGalleryItem = function(id) {
    if (!confirm('Usunąć z galerii?')) return;
    fetch('/api/admin/gallery/' + id, { method:'DELETE', headers:{ 'Authorization':'Bearer '+getStoredToken() } })
      .then(function(r){ loadAdminGallery(); loadGallery(); });
  };

  /* ==== Admin Reviews (moderacja) ==== */
  window.loadAdminReviews = function() {
    var box = document.getElementById('adminReviews');
    if (!box) return;
    var headers = { 'Authorization': 'Bearer ' + getStoredToken(), 'Accept':'application/json' };
    fetch('/api/admin/reviews?t=' + Date.now(), { headers: headers }).then(function(r){ return r.json(); }).then(function(d){
      var items = (d && d.items) || [];
      var rows = items.map(function(rg){
        return '<div style="display:flex;gap:12px;align-items:flex-start;border:1px solid var(--border);border-radius:10px;padding:10px;margin-bottom:8px;background:var(--card)">' +
          '<div style="min-width:70px;color:#f59e0b">' + renderStars(rg.rating) + '</div>' +
          '<div style="flex:1"><b>' + esc(rg.name||'') + '</b>' + (rg.email? ' <span style="color:#94a3b8;font-size:12px">(' + esc(rg.email) + ')</span>':'') +
          '<div style="color:var(--muted);font-size:13px;margin-top:3px">' + esc(rg.text||'') + '</div>' +
          '<div style="color:#94a3b8;font-size:11px;margin-top:4px">' + (rg.created_at||'') + (rg.approved===false ? ' · <span style="color:#ef4444">ukryta</span>':'') + '</div></div>' +
          '<div style="display:flex;flex-direction:column;gap:6px"><button onclick="toggleReview(' + rg.id + ')" style="padding:5px 12px;border:1px solid var(--border);border-radius:7px;cursor:pointer;font-size:12px">' + (rg.approved===false?'Pokaż':'Ukryj') + '</button>' +
          '<button onclick="delReview(' + rg.id + ')" style="padding:5px 12px;border:1px solid #dc2626;color:#dc2626;background:none;border-radius:7px;cursor:pointer;font-size:12px">Usuń</button></div></div>';
      }).join('');
      box.innerHTML = (items.length ? '<b style="font-size:13px">Recenzje (' + items.length + '):</b>' + rows : '<p style="color:var(--muted)">Brak recenzji.</p>');
    }).catch(function(){ box.innerHTML = '<p style="color:var(--error)">Błąd ładowania</p>'; });
  };
  window.toggleReview = function(id) {
    fetch('/api/admin/reviews/' + id, { method:'PATCH', headers:{ 'Authorization':'Bearer '+getStoredToken() } })
      .then(function(){ loadAdminReviews(); loadReviews(); });
  };
  window.delReview = function(id) {
    if (!confirm('Usunąć recenzję?')) return;
    fetch('/api/admin/reviews/' + id, { method:'DELETE', headers:{ 'Authorization':'Bearer '+getStoredToken() } })
      .then(function(){ loadAdminReviews(); loadReviews(); });
  };

  /* ==== Admin Reports (wykres + export) ==== */
  window.loadAdminReports = function() {
    var box = document.getElementById('adminReports');
    if (!box) return;
    var headers = { 'Authorization': 'Bearer ' + getStoredToken(), 'Accept':'application/json' };
    fetch('/api/admin/report?kind=week&t=' + Date.now(), { headers: headers }).then(function(r){ return r.json(); }).then(function(d){
      if (!(d && d.ok)) { box.innerHTML = '<p style="color:var(--error)">Błąd raportu</p>'; return; }
      var rows = d.rows || [];
      var t = d.totals || {};
      // prosta tabela + mini bar chart (inline SVG)
      var max = 1;
      rows.forEach(function(r){ if (r.revenue > max) max = r.revenue; });
      var bars = rows.map(function(r){
        var h = Math.max(4, Math.round((r.revenue / max) * 110));
        return '<div style="display:flex;flex-direction:column;align-items:center;gap:4px;flex:1">' +
          '<div style="height:' + h + 'px;width:22px;background:var(--accent);border-radius:4px 4px 0 0" title="' + r.revenue + ' zł"></div>' +
          '<span style="font-size:10px;color:var(--muted)">' + r.label.slice(5) + '</span></div>';
      }).join('');
      box.innerHTML =
        '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:16px">' +
        '<div style="background:var(--card);border:1px solid var(--border);border-radius:10px;padding:12px;text-align:center"><div style="font-size:22px;font-weight:800;color:var(--accent)">' + t.orders + '</div><div style="color:var(--muted);font-size:12px">zamówienia</div></div>' +
        '<div style="background:var(--card);border:1px solid var(--border);border-radius:10px;padding:12px;text-align:center"><div style="font-size:22px;font-weight:800;color:var(--accent)">' + t.revenue + '</div><div style="color:var(--muted);font-size:12px">przychód (zł)</div></div>' +
        '<div style="background:var(--card);border:1px solid var(--border);border-radius:10px;padding:12px;text-align:center"><div style="font-size:22px;font-weight:800;color:var(--accent)">' + t.margin + '</div><div style="color:var(--muted);font-size:12px">marża (zł)</div></div>' +
        '<div style="background:var(--card);border:1px solid var(--border);border-radius:10px;padding:12px;text-align:center"><div style="font-size:22px;font-weight:800;color:var(--accent)">' + t.reviews + '</div><div style="color:var(--muted);font-size:12px">recenzje</div></div></div>' +
        '<div style="display:flex;gap:6px;align-items:flex-end;height:140px;background:var(--card);border:1px solid var(--border);border-radius:12px;padding:14px 16px;margin-bottom:14px">' + bars + '</div>' +
        '<div style="margin-top:6px"><a href="/api/admin/report/export?kind=week" style="display:inline-block;padding:9px 18px;background:var(--accent);color:#fff;border-radius:8px;font-size:13px;font-weight:600;text-decoration:none" onclick="exportReport(event)">Eksport CSV (tydzień)</a> ' +
        '<a href="/api/admin/report/export?kind=month" style="display:inline-block;padding:9px 18px;border:1px solid var(--accent);color:var(--accent);border-radius:8px;font-size:13px;font-weight:600;text-decoration:none" onclick="exportReport(event)">Eksport CSV (miesiąc)</a></div>';
    }).catch(function(){ box.innerHTML='<p style="color:var(--error)">Błąd raportu</p>'; });
  };
  window.exportReport = function(ev) {
    // ensure auth header on CSV GET — fetch with Bearer then blob-download
    ev.preventDefault();
    var url = ev.target.getAttribute('href');
    fetch(url + (url.indexOf('?')>-1?'&':'?') + 't=' + Date.now(), { headers:{ 'Authorization':'Bearer '+getStoredToken() } })
      .then(function(r){ return r.ok ? r.blob() : Promise.reject(); })
      .then(function(b){
        var a = document.createElement('a'); a.href = URL.createObjectURL(b);
        a.download = url.indexOf('month')>-1 ? '3dfile-report-month.csv' : '3dfile-report-week.csv';
        document.body.appendChild(a); a.click(); a.remove();
      }).catch(function(){ showToast('Błąd eksportu', 'error'); });
  };
  // auto-open admin panel when URL has #admin (np. /admin -> /drukuje#admin)
  
  // ── Drukarnia: przełącznik zakładek (VERSION B / tab-p*) ─────────
  // NOTA: admin_print.js musi sam definiowac switchPrintTab — admin.html
  // wywoluje go z onclick tabow drukarni oraz z switchAdminTab (pusta rozwijka).
  // Mapuje nazwe przycisku ('orders','stats','pricing',...) NA ID kontenera
  // .tab-content w admin.html (tab-orders, tab-pstats, tab-pricing, ...).
  var _printTabMap = {
    'orders': 'tab-orders',
    'stats': 'tab-pstats',
    'pstats': 'tab-pstats',
    'pricing': 'tab-pricing',
    'codes': 'tab-codes',
    'gallery': 'tab-gallery',
    'reviews': 'tab-reviews',
    'materials': 'tab-materials',
    'reports': 'tab-reports'
  };
  var _printLoaders = {
    'orders': loadAdminOrders,
    'stats': loadAdminStats,
    'pstats': loadAdminStats,
    'pricing': loadAdminPricing,
    'codes': loadAdminCodes,
    'gallery': window.loadAdminGallery,
    'reviews': window.loadAdminReviews,
    'materials': window.loadAdminMaterials,
    'reports': window.loadAdminReports
  };
  window.switchPrintTab = function (name) {
    name = String(name || '').toLowerCase();
    // 1. podswietl aktywny przycisk drukarni (usuń active z wszystkich print-tab-btn)
    document.querySelectorAll('.print-tab-btn').forEach(function (b) {
      b.classList.toggle('active', b.getAttribute('data-tab') === name);
    });
    // 2. ukryj wszystkie .tab-content
    document.querySelectorAll('.tab-content').forEach(function (p) { p.classList.remove('active'); });
    // 3. pokaż właściwy panel
    var cid = _printTabMap[name];
    var target = cid ? document.getElementById(cid) : null;
    if (target) target.classList.add('active');
    // 4. odpalenie loadera (jeśli istnieje)
    var loader = _printLoaders[name];
    if (typeof loader === 'function') setTimeout(function () { try { loader(); } catch (e) { console.error('printtab-loader', name, e); } }, 50);
  };

  // ── DELETE order (backend: DELETE /api/orders/{id}) ──────────────
  window.deleteOrder = function (id) {
    if (!confirm('Usunąć zamówienie #' + id + '? Tej operacji nie można cofnąć.')) return;
    fetch('/api/orders/' + id + '?t=' + Date.now(), { method: 'DELETE', headers: _fd() })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
      .then(function (res) {
        if (res.ok && res.d.ok) { _showToast('Zamówienie #' + id + ' usunięte', 'success'); loadAdminOrders(); }
        else { _showToast((res.d && res.d.detail) || 'Błąd usuwania', 'error'); }
      }).catch(function () { _showToast('Błąd sieci', 'error'); });
  };

  // ── Pobierz model 3D klienta (per item) ──────────────────────────
  // list_orders zwraca per item: { id, model_name, job_uuid, material, color, quantity, volume_cm3, dims_mm }
  // Download: GET /download/{job_uuid}?format=stl (alg/subst), lub 3mf (oryginał).
  window.downloadOrderItem = function (uuid, fmt) {
    if (!uuid) { _showToast('Brak pliku', 'error'); return; }
    window.open('/download/' + uuid + '?format=' + fmt + '&t=' + Date.now(), '_blank');
  };


  // Eksport loaderView dla lazy-load z admin.html switchAdminTab
  // UWAGA: loadAdminGallery/Reviews/Reports są już przypisane do window
  // (anonymous function expressions) — NIE re-eksportować (ReferenceError).
  window.loadAdminOrders = loadAdminOrders;
  window.loadAdminStats = loadAdminStats;
  window.loadAdminPricing = loadAdminPricing;
  window.loadAdminCodes = loadAdminCodes;

  // ── init: (przez switchPrintTab) ─────────────────────────────────
})();
