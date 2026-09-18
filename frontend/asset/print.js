/* ===== print.js v80 — 3D Printing service logic ===== */
(function() {
  "use strict";
  var toastContainer = document.getElementById('toastContainer');
  var currencyRates = { PLN: { symbol: 'zł', rate: 1.0 }, USD: { symbol: '$', rate: 4.2 }, EUR: { symbol: '€', rate: 4.55 } };
  var currentCurrency = 'PLN';

  function currencySymbol() {
    return (currencyRates[currentCurrency] && currencyRates[currentCurrency].symbol) || 'zł';
  }

  async function loadCurrencies() {
    try {
      var r = await fetch('/api/config/currencies?' + Date.now());
      if (r.ok) {
        var d = await r.json();
        if (d.rates) {
          currencyRates = {};
          Object.keys(d.rates).forEach(function(k) {
            currencyRates[k] = { symbol: d.rates[k].symbol, rate: d.rates[k].rate };
          });
        }
        var saved = localStorage.getItem('print_currency');
        if (saved && currencyRates[saved]) currentCurrency = saved;
        else currentCurrency = 'PLN';
        renderCurrencyToggle();
        var curHidden = document.getElementById('printCurrency');
        if (curHidden) curHidden.value = currentCurrency;
      }
    } catch (e) {}
  }

  function renderCurrencyToggle() {
    var el = document.getElementById('currencyToggle');
    if (!el) return;
    el.innerHTML = Object.keys(currencyRates).map(function(c) {
      var active = c === currentCurrency;
      return '<button type="button" data-currency="' + c + '" style="padding:4px 10px;border-radius:6px;border:1px solid ' +
        (active ? '#2563eb' : '#d1d5db') + ';background:' + (active ? '#2563eb' : '#fff') +
        ';color:' + (active ? '#fff' : '#374151') + ';font-size:12px;cursor:pointer">' + c + '</button>';
    }).join('');
  }

  window.switchCurrency = function(cur) {
    if (!currencyRates[cur]) return;
    currentCurrency = cur;
    localStorage.setItem('print_currency', cur);
    renderCurrencyToggle();
    calculatePrintPrice();
  };

  function showToast(message, type) {
    type = type || 'info';
    var t = document.createElement('div');
    t.className = 'toast ' + type;
    t.textContent = message;
    if (toastContainer) toastContainer.appendChild(t);
    setTimeout(function() { t.style.opacity = '0'; t.remove(); }, 3500);
  }

  /* ==== Auth ==== */
  var currentUser = null;
  function getStoredToken() {
    var m = document.cookie.match(/token=([^;]+)/);
    if (m) return m[1];
    return localStorage.getItem('token') || '';
  }

  async function checkAuth() {
    try {
      var res = await fetch('/api/me', { headers: { 'Accept': 'application/json' } });
      if (res.ok) {
        currentUser = await res.json();
        if (currentUser.is_admin) {
          var adminLink = document.getElementById('adminLink');
          if (adminLink) adminLink.style.display = 'block';
        }
      }
    } catch (e) {}
  }

  /* ==== Materials + shipping load ==== */
  async function loadMaterials() {
    var box = document.getElementById('materialList');
    if (!box) return;
    try {
      var res = await fetch('/api/admin/materials?' + Date.now());
      var data = res.ok ? await res.json() : { materials: { "PLA": 79, "PETG": 95, "ABS": 89, "ASA": 159, "PA12 CF": 349, "TPU": 130 }, colors: {} };
            var html = Object.keys(data.materials || {}).map(function(m) {
              var p = data.materials[m];
              var price = typeof p === 'number' ? p : (p.price_kg || 0);
              var desc = (typeof p === 'object' && p.desc) ? p.desc : '';
              return '<div class="material-card" style="padding:12px;border:1px solid #e5e7eb;border-radius:8px;background:#fff"><strong>' + m +
                     '<\/strong><br><span style="color:#6b7280">' + price + ' zł/kg<\/span>' +
                     (desc ? '<p style="color:#4b5563;font-size:12px;margin-top:6px;line-height:1.4">' + desc + '<\/p>' : '') +
                     '<\/div>';
            }).join('');
      box.innerHTML = '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px">' + html + '</div>';
    } catch (e) {
      box.innerHTML = '<p style="color:#6b7280">Materials list unavailable</p>';
    }
  }

  window.updateMaterialNote = function() {
    var sel = document.getElementById('printMaterial');
    var note = document.getElementById('printMaterialNote');
    if (!sel || !note) return;
    var map = {
      'PLA': 'PLA — uniwersalny, tani, sztywny. Do prototypów, osłon, modeli i dekoracji. Unikaj wysokich temperatur (~60°C) i intensywnej eksploatacji.',
      'PETG': 'PETG — udarny, odporny na uderzenia i chemię, w połowie przezroczysty. Klosze, osłony, elementy przezroczyste.',
      'ABS': 'ABS — trwały, udarny klasyk przemysłowy. Obudowy, uchwyty, części mechaniczne.',
      'ASA': 'ASA — odporny na UV i warunki atmosferyczne (nie żółknie na słońcu). Elementy zewnętrzne, ogrodowe, motoryzacyjne.',
      'PA12 CF': 'PA12 CF — najwyższa wytrzymałość: nylon z włóknem węglowym. Części funkcjonalne pod obciążeniem, koła zębate, wsporniki.',
      'TPU': 'TPU — elastyczny, gumowy. Uszczelki, ochraniacze, amortyzatory, części giętkie.'
    };
    note.textContent = map[sel.value] || 'Wybierz materiał — pojawi się jego opis i zastosowanie.';
    if (typeof calculatePrintPrice === 'function') calculatePrintPrice();
  };

  function loadShipping() {
    var tbody = document.getElementById('shippingTable');
    if (!tbody) return;
    var rows = [
      ["Standard (5 dni)", 15, 35, 55],
      ["Ekspres (2 dni)", 25, 55, 85],
      ["Priorytet (1 dzień)", 40, 80, 130],
      ["Odbiór osobisty", 0, 0, 0]
    ];
    tbody.innerHTML = rows.map(function(r) {
      return '<tr><td style="padding:8px">' + r[0] + '</td><td style="padding:8px">' + r[1] + ' zł</td><td style="padding:8px">' + r[2] + ' zł</td><td style="padding:8px">' + r[3] + ' zł</td></tr>';
    }).join('');
  }

  /* ==== Print order modal ==== */
  window.openPrintOrderModal = function(model) {
    model = model || {};
    var modal = document.getElementById('printOrderModal');
    if (!modal) { showToast('Formularz niedostępny', 'error'); return; }
    document.getElementById('printOrderId').value = model.job_id || '';
    document.getElementById('printOrderUuid').value = model.uuid || 'calculator';
    if (model.volume_cm3) {
      document.getElementById('printVolume').value = model.volume_cm3;
      document.getElementById('printVolumeHidden').value = model.volume_cm3;
    }
    if (model.estimated_hours) document.getElementById('printHours').value = model.estimated_hours;
    var warnBox = document.getElementById('printWarnings');
    if (warnBox && model.warnings) {
      warnBox.innerHTML = model.warnings.map(function(w) { return '<div style="background:#fef3c7;border:1px solid #f59e0b;border-radius:6px;padding:8px 12px;margin:8px 0;font-size:12px;color:#92400e">⚠ ' + w + '</div>'; }).join('');
      warnBox.style.display = model.warnings.length ? 'block' : 'none';
    }
    if (model.dims_mm && document.getElementById('printDims')) document.getElementById('printDims').value = model.dims_mm;
    loadCurrencies();
    setTimeout(function() { calculatePrintPrice(); }, 100);
    document.body.style.overflow = 'hidden';
    modal.style.display = 'flex';
  };

  window.closePrintModal = function() {
    var modal = document.getElementById('printOrderModal');
    if (modal) modal.style.display = 'none';
    document.body.style.overflow = '';
  };

  /* ==== File upload via /api/estimate ==== */
  window.onFileUpload = function() {
    var inp = document.getElementById('printFileUpload');
    var f = inp ? inp.files[0] : null;
    var status = document.getElementById('printFileStatus');
    if (!f || !status) return;
    status.textContent = 'Przesyłam ' + f.name + '...';
    var fd = new FormData();
    fd.append('file', f);
    fetch('/api/estimate?t=' + Date.now(), { method: 'POST', body: fd })
      .then(function(r) { return r.json(); })
      .then(function(d) {
        if (d.volume_cm3) {
          document.getElementById('printVolume').value = d.volume_cm3;
          document.getElementById('printVolumeHidden').value = d.volume_cm3;
          if (d.dims && document.getElementById('printDims')) document.getElementById('printDims').value = d.dims;
          status.innerHTML = '✓ ' + f.name + ' — ' + d.volume_cm3 + ' cm³, ' + d.dimensions;
          calculatePrintPrice();
        } else {
          status.textContent = 'Błąd przetwarzania — spróbuj inny format';
        }
      })
      .catch(function() { status.textContent = 'Błąd sieci — spróbuj ponownie'; });
  };

  /* ==== Form values (null-safe) ==== */
  function getFormValues() {
    function val(id, def) { var e = document.getElementById(id); return e ? (e.value || '') : ''; }
    function num(id, def) { var e = document.getElementById(id); return e ? (parseFloat(e.value) || def) : def; }
    var dims = val('printDims', '');
    var vol = num('printVolume', 0);
    if (!vol && dims) {
      var nums = dims.match(/[\d.]+/g);
      if (nums && nums.length >= 3) {
        vol = (parseFloat(nums[0]) * parseFloat(nums[1]) * parseFloat(nums[2])) / 1000;
        var vi = document.getElementById('printVolume');
        if (vi) vi.value = vol.toFixed(1);
      }
    }
    return {
      vol: vol,
      qty: num('printOrderQty', 1),
      material: val('printMaterial', 'PLA'),
      color: val('printColor', 'natural'),
      shipping: val('printOrderShipping', 'standard'),
      region: val('printOrderRegion', 'PL'),
      dims: dims
    };
  }

  window.calculatePrintPrice = function() {
    var v = getFormValues();
    var vh = document.getElementById('printVolumeHidden');
    if (vh) vh.value = v.vol.toFixed(1);
    var dh = document.getElementById('printDimsHidden');
    if (dh) dh.value = v.dims;

    var summaryEl = document.getElementById('printPriceSummary');
    var totalEl = document.getElementById('priceTotal');
    var shippingEl = document.getElementById('priceShipping');
    var productEl = document.getElementById('priceProduct');
    var discountLine = document.getElementById('discountLine');
    var discountEl = document.getElementById('priceDiscount');
    var hint = document.getElementById('priceHint');
    var sym = currencySymbol();

    if (v.vol > 0) {
      fetch('/api/calculate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: 'material=' + encodeURIComponent(v.material) +
              '&color=' + encodeURIComponent(v.color) +
              '&quantity=' + v.qty +
              '&shipping=' + encodeURIComponent(v.shipping) +
              '&shipping_region=' + encodeURIComponent(v.region) +
              '&volume_cm3=' + v.vol +
              '&dims=' + encodeURIComponent(v.dims) +
              '&currency=' + encodeURIComponent(currentCurrency)
      })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (data.ok) {
          productEl.textContent = data.product_subtotal.toFixed(2) + ' ' + sym;
          shippingEl.textContent = data.shipping_cost.toFixed(2) + ' ' + sym;
          if (data.discount_pln > 0) {
            discountLine.style.display = 'block';
            discountEl.textContent = '-' + data.discount_pln.toFixed(2) + ' ' + sym;
          } else {
            discountLine.style.display = 'none';
          }
          totalEl.textContent = data.total.toFixed(2) + ' ' + sym;
          hint.textContent = data.parts > 1 ? 'Model podzielony na ' + data.parts + ' części' : '';
          if (data.warnings && data.warnings.length) {
            var wb = document.getElementById('printWarnings');
            if (wb) wb.innerHTML = data.warnings.map(function(w) { return '<div style="background:#fef3c7;border:1px solid #f59e0b;border-radius:6px;padding:6px 10px;margin:6px 0;font-size:12px;color:#92400e">⚠ ' + w + '</div>'; }).join('');
          }
        }
      })
      .catch(function() { showToast('Błąd wyliczania', 'error'); });
    } else {
      productEl.textContent = '—';
      shippingEl.textContent = '—';
      totalEl.textContent = '—';
      hint.textContent = 'Wprowadź objętość albo wymiary';
    }
  };

  window.applyDiscountCode = function() {
    var code = document.getElementById('printOrderCode').value.trim();
    if (!code) { showToast('Wpisz kod rabatowy', 'error'); return; }
    var v = getFormValues();
    fetch('/api/calculate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: 'material=' + encodeURIComponent(v.material) +
            '&color=' + encodeURIComponent(v.color) +
            '&quantity=' + v.qty +
            '&shipping=' + encodeURIComponent(v.shipping) +
            '&shipping_region=' + encodeURIComponent(v.region) +
            '&volume_cm3=' + v.vol +
            '&discount_code=' + encodeURIComponent(code) +
            '&currency=' + encodeURIComponent(currentCurrency)
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.ok) {
        var sym = currencySymbol();
        document.getElementById('priceTotal').textContent = data.total.toFixed(2) + ' ' + sym;
        showToast('Kod ' + code + ' zastosowany: -' + data.discount_pln.toFixed(2) + ' ' + sym, 'success');
      } else {
        showToast(data.detail || 'Nieprawidłowy kod', 'error');
      }
    })
    .catch(function() { showToast('Błąd sieci', 'error'); });
  };

  window.submitPrintOrder = function(e) {
    e.preventDefault();
    var form = e.target;
    var fd = new FormData(form);
    fd.append('payment_method', 'blik');
    fd.append('currency', currentCurrency);
    var notesManual = document.getElementById('printOrderNotesManual') ? document.getElementById('printOrderNotesManual').value.trim() : '';
    var notesHidden = document.getElementById('printOrderNotes') ? (document.getElementById('printOrderNotes').value || '') : '';
    var combined = notesHidden;
    if (notesManual) combined += (combined ? '\n' : '') + notesManual;
    fd.set('notes', combined);
    var name = fd.get('name');
    var email = fd.get('email');
    if (!name || !email) { showToast('Imię i email są wymagane', 'error'); return; }
    fetch('/api/orders?t=' + Date.now(), {
      method: 'POST',
      headers: { 'Authorization': 'Bearer ' + getStoredToken() },
      body: fd
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.ok) {
        var sym = currencySymbol();
        showToast('Zamówienie #' + data.order_id + '! Cena: ' + data.total.toFixed(2) + ' ' + sym + '. Skontaktujemy się w celu potwierdzenia płatności.', 'success');
        closePrintModal();
      } else {
        showToast(data.detail || 'Błąd zamówienia', 'error');
      }
    })
    .catch(function() { showToast('Błąd sieci', 'error'); });
  };

  /* ==== Admin panel ==== */
  window.openAdminPanel = function() {
    var panel = document.getElementById('adminPanel');
    if (!panel) return;
    panel.style.display = 'block';
    panel.scrollIntoView({behavior: 'smooth'});
  };

  window.authenticateAdmin = function() {
    var code = document.getElementById('adminTokenInput').value.trim();
    if (!code) { showToast('Wpisz token', 'error'); return; }
    localStorage.setItem('token', code);
    showToast('Admin odblokowany', 'success');
    setTimeout(checkAdminAuth, 100);
  };

  async function checkAdminAuth() {
    var token = getStoredToken();
    if (!token) return;
    try {
      var res = await fetch('/api/orders/stats?' + Date.now(), { headers: { 'Authorization': 'Bearer ' + token, 'Accept': 'application/json' } });
      if (res.ok) {
        var authDiv = document.getElementById('adminAuth');
        var contentDiv = document.getElementById('adminContent');
        if (authDiv) authDiv.style.display = 'none';
        if (contentDiv) contentDiv.style.display = 'block';
        await loadAdminOrders();
      }
    } catch (e) {}
  }

  async function loadAdminOrders() {
    var token = getStoredToken();
    var headers = { 'Authorization': 'Bearer ' + token, 'Accept': 'application/json' };
    try {
      var res = await fetch('/api/orders?' + Date.now(), { headers: headers });
      var data = await res.json();
      if (data.ok && data.orders) {
        var tbody = '';
        data.orders.forEach(function(o) {
          var statusColor = '#6b7280';
          if (o.status === 'drukowane') statusColor = '#f59e0b';
          if (o.status === 'wysłane') statusColor = '#3b82f6';
          if (o.status === 'dostarczone') statusColor = '#10b981';
          if (o.status === 'anulowane') statusColor = '#ef4444';
          tbody += '<tr style="border-bottom:1px solid #e5e7eb">' +
            '<td style="padding:8px">' + o.id + '</td>' +
            '<td style="padding:8px">' + new Date(o.created_at).toLocaleString('en-GB') + '</td>' +
            '<td style="padding:8px">' + (o.customer_name || '') + '</td>' +
            '<td style="padding:8px">' + (o.customer_email || '') + '</td>' +
            '<td style="padding:8px">' + (o.material || '') + '</td>' +
            '<td style="padding:8px">' + (o.quantity || 1) + '</td>' +
            '<td style="padding:8px">' + (o.filament_grams || 0) + 'g</td>' +
            '<td style="padding:8px">Fil: ' + (o.filament_cost || 0).toFixed(0) + 'zł</td>' +
            '<td style="padding:8px">Marża: ' + (o.margin_pln || 0).toFixed(0) + 'zł</td>' +
            '<td style="padding:8px;font-weight:600">' + (o.total || 0).toFixed(2) + ' ' + (o.currency || 'PLN') + '</td>' +
            '<td style="padding:8px;color:#10b981">Profit: ' + ((o.total || 0) - (o.filament_cost || 0) - (o.electricity_cost || 0) - (o.shipping_cost || 0)).toFixed(0) + 'zł</td>' +
            '<td style="padding:8px"><span style="color:' + statusColor + ';font-weight:600">' + (o.status || 'nowy') + '</span></td>' +
            '<td style="padding:8px">' + (o.is_paid ? '✓' : '') + '</td>' +
            '<td style="padding:8px"><button data-action="exportOrder" data-id="' + o.id + '" style="padding:4px 8px;border:1px solid #d1d5db;border-radius:4px">CSV</button></td>' +
            '</tr>';
        });
        document.getElementById('adminOrders').innerHTML =
          '<button onclick="exportAllOrders()" style="padding:8px 16px;margin-bottom:12px;border:1px solid #d1d5db;border-radius:6px">Export all (Excel)</button><div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:13px"><thead><tr style="border-bottom:2px solid #e5e7eb"><th style="padding:8px">ID</th><th style="padding:8px">Data</th><th style="padding:8px">Klient</th><th style="padding:8px">Email</th><th style="padding:8px">Mat.</th><th style="padding:8px">Qty</th><th style="padding:8px">Fil.g</th><th style="padding:8px">Fil.koszt</th><th style="padding:8px">Marża</th><th style="padding:8px">Total</th><th style="padding:8px">Profit</th><th style="padding:8px">Status</th><th style="padding:8px">Zapł.</th><th style="padding:8px">CSV</th></tr></thead><tbody>' + tbody + '</tbody></table></div>';
      }
    } catch (e) {
      document.getElementById('adminOrders').innerHTML = '<p style="color:#ef4444">Błąd ładowania</p>';
    }
  }

  window.exportOrder = function(orderId) { window.open('/api/orders/' + orderId + '/export?t=' + Date.now(), '_blank'); };
  window.exportAllOrders = function() { window.open('/api/orders/export?t=' + Date.now(), '_blank'); };

  async function loadAdminStats() {
    var headers = { 'Authorization': 'Bearer ' + getStoredToken(), 'Accept': 'application/json' };
    try {
      var res = await fetch('/api/orders/stats?' + Date.now(), { headers: headers });
      var data = await res.json();
      if (data.stats) {
        var s = data.stats;
        document.getElementById('adminStats').innerHTML =
          '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px">' +
          '<div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:12px;padding:12px"><div style="font-size:11px;color:#6b7280">Zamówienia</div><div style="font-size:20px;font-weight:700">' + s.total_orders + '</div></div>' +
          '<div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:12px;padding:12px"><div style="font-size:11px;color:#6b7280">Przychód PLN</div><div style="font-size:20px;font-weight:700">' + s.total_revenue_pln + '</div></div>' +
          '</div>';
      }
    } catch (e) {}
  }

  async function loadAdminPricing() {
    var headers = { 'Authorization': 'Bearer ' + getStoredToken(), 'Accept': 'application/json' };
    try {
      var res = await fetch('/api/admin/pricing?' + Date.now(), { headers: headers });
      var data = await res.json();
      var html = '<table style="width:100%;border-collapse:collapse;font-size:13px"><thead><tr style="border-bottom:2px solid #e5e7eb"><th style="padding:6px">Key</th><th style="padding:6px">Value</th></tr></thead><tbody>';
      (data || []).forEach(function(r) {
        html += '<tr style="border-bottom:1px solid #e5e7eb"><td style="padding:6px">' + r.key + '</td><td style="padding:6px"><input type="text" value="' + r.value + '" onchange="updatePricing(\'' + r.key + '\', this.value)" style="width:120px;padding:4px;font-size:12px"></td></tr>';
      });
      html += '</tbody></table>';
      document.getElementById('adminPricing').innerHTML = html;
    } catch (e) {}
  }

  window.updatePricing = function(key, value) {
    var token = getStoredToken();
    fetch('/api/admin/pricing?' + Date.now(), {
      method: 'POST',
      headers: { 'Authorization': 'Bearer ' + token, 'Content-Type': 'application/x-www-form-urlencoded' },
      body: 'key=' + encodeURIComponent(key) + '&value=' + encodeURIComponent(value)
    }).then(function() { showToast('Zapisano', 'success'); });
  };

  window.switchAdminTab = function(tab) {
    document.querySelectorAll('.admin-tab').forEach(function(e) { e.style.display = 'none'; });
    document.querySelectorAll('.admin-tab-btn').forEach(function(e) { e.classList.remove('active'); e.style.borderBottom = 'none'; });
    var t = document.getElementById('admin' + tab.charAt(0).toUpperCase() + tab.slice(1));
    if (t) t.style.display = 'block';
    if (tab === 'orders') setTimeout(loadAdminOrders, 50);
    if (tab === 'stats') setTimeout(loadAdminStats, 50);
    if (tab === 'pricing') setTimeout(loadAdminPricing, 50);
  };

  /* ==== Init ==== */
  // event delegation for dynamically created buttons
  document.addEventListener('click', function(e) {
    var btn = e.target.closest('[data-currency]');
    if (btn) { setCurrency(btn.dataset.currency); return; }
    btn = e.target.closest('[data-action]');
    if (btn && btn.dataset.action === 'exportOrder') { exportOrder(parseInt(btn.dataset.id)); return; }
  });

  document.addEventListener('DOMContentLoaded', function() {
      loadCurrencies();
      loadMaterials();
      loadShipping();
      updateMaterialNote();
      checkAuth();
    document.addEventListener('keydown', function(e) { if (e.key === 'Escape') closePrintModal(); });
    window.addEventListener('click', function(e) {
      if (e.target && e.target.classList && e.target.classList.contains('modal-backdrop')) closePrintModal();
    });
  });
  window.showToast = showToast;
  window.currencySymbol = currencySymbol;
})();
