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

  // Stuby: publiczna galeria/reviews NIE istnieją w tym panelu — no-op.
  window.$ = window.$ || null;
  if (!window.loadGallery) window.loadGallery = function () {};
  if (!window.loadReviews) window.loadReviews = function () {};
  if (!window.renderStars) window.renderStars = function (n) { var o=''; for (var i=1;i<=5;i++) o += i<=n?'★':'☆'; return o; };

    if (s === null || s === undefined) return '';
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

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

  window.switchPrintTab = function(tab) {
    document.querySelectorAll('.admin-tab').forEach(function(e) { e.style.display = 'none'; });
    document.querySelectorAll('.admin-tab-btn').forEach(function(e) { e.classList.remove('active'); e.style.borderBottom = 'none'; });
    var t = document.getElementById('admin' + tab.charAt(0).toUpperCase() + tab.slice(1));
    if (t) t.style.display = 'block';
    if (tab === 'orders') setTimeout(loadAdminOrders, 50);
    if (tab === 'stats') setTimeout(loadAdminStats, 50);
    if (tab === 'pricing') setTimeout(loadAdminPricing, 50);
    if (tab === 'codes') setTimeout(loadAdminCodes, 50);
    if (tab === 'gallery') setTimeout(loadAdminGallery, 50);
    if (tab === 'reviews') setTimeout(loadAdminReviews, 50);
    if (tab === 'reports') setTimeout(loadAdminReports, 50);
  };

  /* ==== Init ==== */
  // event delegation for dynamically created buttons
  
document.addEventListener('click', function(e) {
    var btn = e.target.closest('[data-currency]');
    if (btn) { setCurrency(btn.dataset.currency); return; }
    btn = e.target.closest('[data-action]');
    if (btn && btn.dataset.action === 'exportOrder') { exportOrder(parseInt(btn.dataset.id)); return; }
  });

  

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
  function switchPrintTab(tab) {
    document.querySelectorAll('.tab-content').forEach(function (p_) { p_.classList.remove('active'); });
    document.querySelectorAll('.admin-tab').forEach(function (b_) { b_.classList.remove('active'); });
    document.querySelectorAll('.print-tab-btn').forEach(function (b_) { b_.classList.remove('active'); });
    var tgt = document.getElementById((tab === 'stats' ? 'p' : '') + 'tab-' + tab);
    if (tgt) tgt.classList.add('active');
    var btn = document.querySelector('[data-tabs="print"][data-tab="' + tab + '"]');
    if (btn) btn.classList.add('active');
    try { document.title = 'PT:' + tab; } catch(e) {}
    var lazy = { 'orders': loadAdminOrders, 'stats': loadAdminStats, 'pricing': loadAdminPricing,
                 'codes': loadAdminCodes, 'gallery': loadAdminGallery, 'reviews': loadAdminReviews,
                 'reports': loadAdminReports };
    if (lazy[tab]) { setTimeout(function(){ try { lazy[tab](); } catch(e) { console.error('print-tab loader', tab, e); } }, 60); }
  }
  window.switchPrintTab = switchPrintTab;

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
  window.loadAdminOrders = loadAdminOrders;
  window.loadAdminStats = loadAdminStats;
  window.loadAdminPricing = loadAdminPricing;
  window.loadAdminCodes = loadAdminCodes;
  window.loadAdminGallery = loadAdminGallery;
  window.loadAdminReviews = loadAdminReviews;
  window.loadAdminReports = loadAdminReports;

  // ── init: (przez switchPrintTab) ─────────────────────────────────
})();
