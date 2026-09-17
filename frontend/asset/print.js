/* ===== print.js — 3D Printing service logic (EN) ===== */

(function() {
  "use strict";

  var toastContainer = document.getElementById('toastContainer');
  var currencyRates = { PLN: { symbol: 'zł', rate: 1.0 }, USD: { symbol: '$', rate: 4.2 }, EUR: { symbol: '€', rate: 4.55 } };
  var currentCurrency = 'PLN';
  var currentModel = {};

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
        // update currency hidden + re-render price if modal open
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
      return '<button type="button" onclick="switchCurrency(\'' + c + '\')" style="padding:4px 10px;border-radius:6px;border:1px solid ' +
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
      var res = await fetch('/api/admin/materials?' + Date.now(), {
        headers: { 'Authorization': 'Bearer ' + getStoredToken(), 'Accept': 'application/json' }
      });
      var data;
      if (res.ok) {
        data = await res.json();
      } else {
        data = { materials: { "PLA": 79, "PETG": 95, "ABS": 89, "ASA": 159, "PA12 CF": 349 }, colors: {} };
      }
      var html = Object.keys(data.materials || {}).map(function(m) {
        var p = data.materials[m];
        var price = typeof p === 'number' ? p : (p.price_kg || 0);
        var dens = (typeof p === 'object' && p.density) ? ' ' + p.density + ' g/cm³' : '';
        return '<div style="padding:12px;border:1px solid #e5e7eb;border-radius:8px"><strong>' + m +
               '</strong><br><span style="color:#6b7280">' + price + ' zł/kg' + dens + '</span></div>';
      }).join('');
      box.innerHTML = '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:12px">' + html + '</div>';
    } catch (e) {
      box.innerHTML = '<p style="color:#6b7280">Materials list unavailable</p>';
    }
  }

  function loadShipping() {
    var tbody = document.getElementById('shippingTable');
    if (!tbody) return;
    var rows = [
      ["Standard (5 business days)", 15, 35, 55],
      ["Express (2 days)", 25, 55, 85],
      ["Priority (next day)", 40, 80, 130],
      ["Pickup (local)", 0, 0, 0]
    ];
    tbody.innerHTML = rows.map(function(r) {
      return '<tr><td style="padding:8px">' + r[0] + '</td><td style="padding:8px">' + r[1] + ' zł</td><td style="padding:8px">' + r[2] + ' zł</td><td style="padding:8px">' + r[3] + ' zł</td></tr>';
    }).join('');
  }

  /* ==== Print order modal ==== */
  window.openPrintOrderModal = function(model) {
    model = model || {};
    currentModel = model;
    var modal = document.getElementById('printOrderModal');
    if (!modal) { showToast('Order form unavailable', 'error'); return; }
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
    if (model.dims_mm) document.getElementById('printDims').value = model.dims_mm;

    // pre-fill notes with model metadata
    var notesField = document.getElementById('printOrderNotes');
    if (notesField) {
      var desc = model.title || '';
      notesField.value = desc;
    }

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

  function getFormValues() {
    var volInput = document.getElementById('printVolume');
    var dimsInput = document.getElementById('printDims');
    var vol = parseFloat(volInput && volInput.value) || 0;

    if (!vol && dimsInput && dimsInput.value) {
      var nums = dimsInput.value.match(/[\d.]+/g);
      if (nums && nums.length >= 3) {
        vol = (parseFloat(nums[0]) * parseFloat(nums[1]) * parseFloat(nums[2])) / 1000;
        volInput.value = vol.toFixed(1);
      }
    }

    return {
      vol: vol,
      qty: parseInt(document.getElementById('printOrderQty').value) || 1,
      material: document.getElementById('printMaterial').value || 'PLA',
      color: document.getElementById('printColor').value || 'natural',
      shipping: document.getElementById('printShipping').value || 'standard',
      region: document.getElementById('printOrderRegion').value || 'PL',
      dims: dimsInput ? dimsInput.value : '',
    };
  }

  window.calculatePrintPrice = function() {
    var v = getFormValues();

    if (document.getElementById('printVolumeHidden'))
      document.getElementById('printVolumeHidden').value = v.vol.toFixed(1);
    if (document.getElementById('printDimsHidden'))
      document.getElementById('printDimsHidden').value = v.dims;

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
        body: 'material=' + encodeURIComponent(material) +
              '&color=' + encodeURIComponent(color) +
              '&quantity=' + qty +
              '&shipping=' + encodeURIComponent(shipping) +
              '&shipping_region=' + encodeURIComponent(region) +
              '&volume_cm3=' + vol +
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
          hint.textContent = data.parts > 1 ? 'Model split into ' + data.parts + ' parts (max 25×25 mm per part)' : '';
          summaryEl.style.background = '#fff';
        }
      })
      .catch(function() { showToast('Calculation error', 'error'); });
    } else {
      productEl.textContent = '—';
      shippingEl.textContent = '—';
      totalEl.textContent = '—';
      hint.textContent = 'Enter volume or dimensions to calculate price';
    }
  };

  window.applyDiscountCode = function() {
    var code = document.getElementById('printOrderCode').value.trim();
    if (!code) { showToast('Enter a discount code first', 'error'); return; }
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
        document.getElementById('printPriceSummary').style.background = '#fff';
        showToast('Discount code ' + code + ' applied: -' + data.discount_pln.toFixed(2) + ' ' + sym, 'success');
      } else {
        showToast(data.detail || 'Invalid code', 'error');
      }
    })
    .catch(function() { showToast('Network error', 'error'); });
  };

  window.submitPrintOrder = function(e) {
    e.preventDefault();
    var form = e.target;
    var fd = new FormData(form);
    fd.append('payment_method', 'blik');
    fd.append('currency', currentCurrency);

    // merge notes manual into notes
    var notesManual = document.getElementById('printOrderNotesManual') ? document.getElementById('printOrderNotesManual').value.trim() : '';
    var notesHidden = document.getElementById('printOrderNotes') ? document.getElementById('printOrderNotes').value || '' : '';
    var combinedNotes = notesHidden;
    if (notesManual) combinedNotes += (combinedNotes ? '\n' : '') + notesManual;
    fd.set('notes', combinedNotes);

    var name = fd.get('name');
    var email = fd.get('email');
    if (!name || !email) {
      showToast('Name and email are required', 'error');
      return;
    }

    var v = getFormValues();
    if (v.vol <= 0 && v.dims) {
      // recalculate vol silently — backend also derives it
    }

    fetch('/api/orders?' + Date.now(), {
      method: 'POST',
      headers: { 'Authorization': 'Bearer ' + getStoredToken() },
      body: fd
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.ok) {
        var sym = currencySymbol();
        showToast('Order placed! Price: ' + data.total.toFixed(2) + ' ' + sym + '. We will contact you to confirm payment.', 'success');
        closePrintModal();
      } else {
        showToast(data.detail || 'Order error', 'error');
      }
    })
    .catch(function() { showToast('Network error', 'error'); });
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
    if (!code) { showToast('Enter token', 'error'); return; }
    localStorage.setItem('token', code);
    checkAdminAuth();
    showToast('Admin unlocked', 'success');
  };

  async function checkAdminAuth() {
    var token = getStoredToken();
    if (!token) return;
    var headers = { 'Authorization': 'Bearer ' + token, 'Accept': 'application/json' };
    try {
      var res = await fetch('/api/orders/stats?' + Date.now(), { headers: headers });
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
        var sym = currencySymbol();
        var tbody = '';
        data.orders.forEach(function(o) {
          var statusColor = '#6b7280';
          if (o.status === 'drukowane') statusColor = '#f59e0b';
          if (o.status === 'wysłane') statusColor = '#3b82f6';
          if (o.status === 'dostarczone') statusColor = '#10b981';
          if (o.status === 'anulowane') statusColor = '#ef4444';
          var cur = o.currency || 'PLN';
          var orderSym = (currencyRates[cur] && currencyRates[cur].symbol) || 'zł';
          tbody += '<tr style="border-bottom:1px solid #e5e7eb">' +
            '<td style="padding:8px">' + o.id + '</td>' +
            '<td style="padding:8px">' + new Date(o.created_at).toLocaleString('en-GB') + '</td>' +
            '<td style="padding:8px">' + (o.customer_name || '') + '</td>' +
            '<td style="padding:8px">' + (o.customer_email || '') + '</td>' +
            '<td style="padding:8px">' + (o.customer_phone || o.phone || '') + '</td>' +
            '<td style="padding:8px">' + (o.material || '') + '</td>' +
            '<td style="padding:8px">' + (o.quantity || 1) + '</td>' +
            '<td style="padding:8px">' + (o.shipping_method || '') + '</td>' +
            '<td style="padding:8px">' + (o.filament_grams || 0) + 'g</td>' +
            '<td style="padding:8px">Fil: ' + (o.filament_cost || 0).toFixed(0) + 'zł</td>' +
            '<td style="padding:8px">Marża: ' + (o.margin_pln || 0).toFixed(0) + 'zł</td>' +
            '<td style="padding:8px;font-weight:600">' + (o.total || 0).toFixed(2) + ' ' + orderSym + '</td>' +
            '<td style="padding:8px;color:#10b981;font-weight:600">Profit: ' + ((o.total || 0) - (o.filament_cost || 0) - (o.electricity_cost || 0) - (o.shipping_cost || 0)).toFixed(0) + 'zł</td>' +
            '<td style="padding:8px"><span style="color:' + statusColor + ';font-weight:600">' + (o.status || 'nowy') + '</span></td>' +
            '<td style="padding:8px">' + (o.is_paid ? '✓' : '') + '</td>' +
            '<td style="padding:8px"><button onclick="exportOrder(' + o.id + ')" style="padding:4px 8px;border:1px solid #d1d5db;border-radius:4px;background:#f9fafb">CSV</button></td>' +
            '</tr>';
        });
        document.getElementById('adminOrders').innerHTML =
          '<button onclick="exportAllOrders()" style="padding:8px 16px;margin-bottom:12px;border:1px solid #d1d5db;border-radius:6px;background:#f9fafb">Export all (Excel)</button>' +
          '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:13px">' +
          '<thead><tr style="border-bottom:2px solid #e5e7eb"><th style="padding:8px;text-align:left">ID</th><th style="padding:8px;text-align:left">Date</th><th style="padding:8px;text-align:left">Client</th><th style="padding:8px;text-align:left">Email</th><th style="padding:8px;text-align:left">Phone</th><th style="padding:8px;text-align:left">Material</th><th style="padding:8px;text-align:left">Qty</th><th style="padding:8px;text-align:left">Fil. g</th><th style="padding:8px;text-align:left">Fil. koszt</th><th style="padding:8px;text-align:left">Marża</th><th style="padding:8px;text-align:left">Total</th><th style="padding:8px;text-align:left">Profit</th><th style="padding:8px;text-align:left">Status</th><th style="padding:8px;text-align:left">Paid</th><th style="padding:8px;text-align:left">CSV</th></tr></thead>' +
          '<tbody>' + tbody + '</tbody></table></div>';
      }
    } catch (e) {
      document.getElementById('adminOrders').innerHTML = '<p style="color:#ef4444">Load failed</p>';
    }
  }

  window.exportOrder = function(orderId) {
    window.open('/api/orders/' + orderId + '/export?' + Date.now(), '_blank');
  };

  window.exportAllOrders = function() {
    window.open('/api/orders/export?' + Date.now(), '_blank');
  };

  async function loadAdminStats() {
    var token = getStoredToken();
    var headers = { 'Authorization': 'Bearer ' + token, 'Accept': 'application/json' };
    try {
      var res = await fetch('/api/orders/stats?' + Date.now(), { headers: headers });
      var data = await res.json();
      if (data.stats) {
        var s = data.stats;
        var html = '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:16px">' +
          '<div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:12px;padding:16px"><div style="font-size:12px;color:#6b7280">Total orders</div><div style="font-size:24px;font-weight:700">' + s.total_orders + '</div></div>' +
          '<div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:12px;padding:16px"><div style="font-size:12px;color:#6b7280">Revenue (PLN)</div><div style="font-size:24px;font-weight:700">' + s.total_revenue_pln + '</div></div>' +
          '<div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:12px;padding:16px"><div style="font-size:12px;color:#6b7280">Pending</div><div style="font-size:24px;font-weight:700;color:#f59e0b">' + (s.pending || 0) + '</div></div>' +
          '<div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:12px;padding:16px"><div style="font-size:12px;color:#6b7280">Shipped</div><div style="font-size:24px;font-weight:700;color:#3b82f6">' + (s.shipped || 0) + '</div></div>' +
          '</div>';
        document.getElementById('adminStats').innerHTML = html + '<pre style="background:#1f2937;color:#e5e7eb;padding:12px;border-radius:8px;margin-top:16px;font-size:12px;overflow-x:auto">' + JSON.stringify(s, null, 2) + '</pre>';
      }
    } catch (e) {
      document.getElementById('adminStats').innerHTML = '<p style="color:#ef4444">Load failed</p>';
    }
  }

  async function loadAdminPricing() {
    var token = getStoredToken();
    var headers = { 'Authorization': 'Bearer ' + token, 'Accept': 'application/json' };
    try {
      var res = await fetch('/api/admin/pricing?' + Date.now(), { headers: headers });
      var data = await res.json();
      var html = '<table style="width:100%;border-collapse:collapse;font-size:13px"><thead><tr style="border-bottom:2px solid #e5e7eb"><th style="padding:6px;text-align:left">Key</th><th style="padding:6px;text-align:left">Value</th><th style="padding:6px;text-align:left">Type</th><th style="padding:6px">Action</th></tr></thead><tbody>';
      (data || []).forEach(function(r) {
        html += '<tr style="border-bottom:1px solid #e5e7eb"><td style="padding:6px">' + r.key + '</td>' +
                '<td style="padding:6px"><input type="text" value="' + r.value + '" onchange="updatePricing(\'' + r.key + '\', this.value)" style="width:120px;padding:4px;font-size:12px"></td>' +
                '<td style="padding:6px">' + r.kind + '</td>' +
                '<td style="padding:6px"><button onclick="deletePricing(\'' + r.key + '\')" style="padding:2px 6px;font-size:11px">del</button></td></tr>';
      });
      html += '</tbody></table><div style="margin-top:12px"><input type="text" id="newPricingKey" placeholder="key" style="padding:4px;font-size:12px;width:120px"><input type="text" id="newPricingVal" placeholder="value" style="padding:4px;font-size:12px;width:100px"><button onclick="addPricing()" style="padding:4px 8px;font-size:12px">Add</button></div>';
      document.getElementById('adminPricing').innerHTML = html;
    } catch (e) {
      document.getElementById('adminPricing').innerHTML = '<p style="color:#ef4444">Load failed</p>';
    }
  }

  window.updatePricing = function(key, value) {
    var token = getStoredToken();
    fetch('/api/admin/pricing?' + Date.now(), {
      method: 'POST',
      headers: { 'Authorization': 'Bearer ' + token, 'Content-Type': 'application/x-www-form-urlencoded' },
      body: 'key=' + encodeURIComponent(key) + '&value=' + encodeURIComponent(value)
    }).then(function() { showToast('Updated', 'success'); });
  };

  window.addPricing = function() {
    var k = document.getElementById('newPricingKey').value.trim();
    var v = document.getElementById('newPricingVal').value.trim();
    if (!k || !v) return;
    window.updatePricing(k, v);
    setTimeout(function() { loadAdminPricing(); }, 500);
  };

  window.deletePricing = function(key) {
    if (!confirm('Delete pricing key ' + key + '?')) return;
    var token = getStoredToken();
    fetch('/api/admin/pricing/' + encodeURIComponent(key) + '?' + Date.now(), {
      method: 'DELETE',
      headers: { 'Authorization': 'Bearer ' + token }
    }).then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.ok) { showToast('Deleted', 'success'); setTimeout(loadAdminPricing, 500); }
      else showToast(data.detail || 'Error', 'error');
    });
  };

  window.switchAdminTab = function(tab) {
    document.querySelectorAll('.admin-tab').forEach(function(e) { e.style.display = 'none'; });
    document.querySelectorAll('.admin-tab-btn').forEach(function(e) {
      e.classList.remove('active');
      e.style.borderBottom = 'none';
    });
    document.getElementById('admin' + tab.charAt(0).toUpperCase() + tab.slice(1)).style.display = 'block';
    var activeBtn = document.querySelector('.admin-tab-btn[onclick="switchAdminTab(\'' + tab + '\')"]');
    if (activeBtn) activeBtn.style.borderBottom = '2px solid #2563eb';
    if (tab === 'orders') setTimeout(loadAdminOrders, 50);
    if (tab === 'stats') setTimeout(loadAdminStats, 50);
    if (tab === 'pricing') setTimeout(loadAdminPricing, 50);
    if (tab === 'codes') setTimeout(loadAdminCodes, 50);
  };

  async function loadAdminCodes() {
    var token = getStoredToken();
    var headers = { 'Authorization': 'Bearer ' + token, 'Accept': 'application/json' };
    try {
      var res = await fetch('/api/admin/discount_codes?' + Date.now(), { headers: headers });
      var data = await res.json();
      var html = '<table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:12px"><thead><tr style="border-bottom:2px solid #e5e7eb"><th style="padding:6px;text-align:left">Code</th><th style="padding:6px;text-align:left">PLN off</th><th style="padding:6px;text-align:left">% off</th><th style="padding:6px;text-align:left">Uses</th><th style="padding:6px">Active</th></tr></thead><tbody>';
      (data.codes || []).forEach(function(c) {
        html += '<tr style="border-bottom:1px solid #e5e7eb"><td style="padding:6px">' + c.code + '</td><td style="padding:6px">' + (c.discount_pln || 0) + '</td><td style="padding:6px">' + (c.discount_pct || 0) + '</td><td style="padding:6px">' + (c.uses || 0) + '</td><td style="padding:6px">' + (c.is_active ? 'y' : 'n') + '</td></tr>';
      });
      html += '</tbody></table>';
      html += '<form onsubmit="addDiscountCode(event)" style="display:grid;grid-template-columns:1fr 1fr;gap:12px"><input name="code" placeholder="Code e.g. WELCOME10" required style="padding:6px;font-size:12px"><input name="discount_pln" type="number" step="0.01" placeholder="PLN off" style="padding:6px;font-size:12px"><input name="discount_pct" type="number" step="0.1" placeholder="pct off" style="padding:6px;font-size:12px"><input name="max_uses" type="number" placeholder="Max uses (blank=∞)" style="padding:6px;font-size:12px"><button type="submit" class="submit-btn">Add code</button></form>';
      document.getElementById('adminCodes').innerHTML = html;
    } catch (e) {
      document.getElementById('adminCodes').innerHTML = '<p style="color:#ef4444">Load failed</p>';
    }
  }

  window.addDiscountCode = function(e) {
    e.preventDefault();
    var form = e.target;
    var token = getStoredToken();
    var fd = new FormData(form);
    fetch('/api/admin/discount_codes?' + Date.now(), {
      method: 'POST',
      headers: { 'Authorization': 'Bearer ' + token },
      body: fd
    }).then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.ok) { showToast('Code added', 'success'); form.reset(); setTimeout(loadAdminCodes, 500); }
      else showToast(data.detail || 'Error', 'error');
    });
  };

  /* ==== Export ==== */
  function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/[&<>\"]/g, function(c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c] || c;
    });
  }

  /* ==== Init ==== */
  document.addEventListener('DOMContentLoaded', function() {
    checkAuth();
    loadMaterials();
    loadShipping();
    loadCurrencies();
    checkAdminAuth();

    document.addEventListener('keydown', function(e) {
      if (e.key === 'Escape') closePrintModal();
    });
    window.addEventListener('click', function(e) {
      if (e.target && e.target.classList && e.target.classList.contains('modal-backdrop')) closePrintModal();
    });
  });

  window.showToast = showToast;
  window.currencySymbol = currencySymbol;
})();