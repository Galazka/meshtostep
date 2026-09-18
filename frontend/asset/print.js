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
              return '<div class="material-card"><strong>' + m +
                             '</strong><br><span class="price">' + price + ' zł/kg</span>' +
                             (desc ? '<span class="desc">' + desc + '</span>' : '') +
                             '</div>';
            }).join('');
      box.innerHTML = html;
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
              if (d && (d.volume_cm3 || d.volume)) {
                var vol = d.volume_cm3 || d.volume || 0;
                document.getElementById('printVolume').value = vol;
                document.getElementById('printVolumeHidden').value = vol;
                var dims = d.dimensions || d.dims || '';
                if (dims && document.getElementById('printDims')) document.getElementById('printDims').value = dims;
                status.innerHTML = '✓ Model załadowany: ' + f.name + '<br><span style="color:#10b981;font-weight:600">' + vol.toFixed(1) + ' cm³</span>' + (dims ? ' · wymiary ' + dims : '');
                // show model summary
                var sum = document.getElementById('printModelSummary');
                if (sum) {
                  sum.style.display = 'block';
                  sum.innerHTML = '<strong>Twój model:</strong> ' + f.name + ' <span style="color:#10b981">(' + vol.toFixed(1) + ' cm³' + (dims ? ', ' + dims : '') + ')</span>';
                }
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
                    // VAT note (region-specific) + FX note
                    var vatNote = document.getElementById('priceVatNote');
                    if (vatNote) {
                      if (v.region === 'PL') vatNote.textContent = '① Do ceny doliczony zostanie VAT 23% (Polska) — Stripe naliczy go przy płatności.';
                      else if (v.region === 'EU') vatNote.textContent = '① Do ceny może zostać doliczony VAT wg kraju UE — Stripe naliczy go przy płatności.';
                      else vatNote.textContent = '① Do ceny może zostać doliczony VAT wg kraju dostawy — Stripe naliczy go przy płatności.';
                    }
                    var fxNote = document.getElementById('priceFxNote');
                    if (fxNote) {
                      var rate = data.exchange_rate || 1.0;
                      fxNote.textContent = data.currency === 'PLN' ? 'Waluta: PLN (konto własne)' : 'Waluta: ' + data.currency + ' · kurs 1 ' + data.currency + ' = ' + (1 / rate).toFixed(4) + ' PLN';
                    }
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
            var orderId = data.order_id;
            var sym = currencySymbol();
            // 1. try Stripe checkout
            fetch('/api/orders/' + orderId + '/checkout?t=' + Date.now(), {
              method: 'POST'
            }).then(function(r) { return r.json(); }).then(function(c) {
              if (c.ok && c.checkout_url) {
                showToast('Przekierowuję do płatności...', 'info');
                window.location.href = c.checkout_url;
              } else if (c.ok && c.blik_fallback) {
                // BLIK fallback — pokaz w modalu
                closePrintModal();
                showToast('Zamówienie #' + orderId + '! Cena: ' + data.total.toFixed(2) + ' ' + sym + '.', 'success');
                setTimeout(function() {
                  var t = document.getElementById('printModalTitle');
                  var old = t ? t.textContent : '';
                  var body = document.getElementById('printOrderForm');
                  if (body) body.style.display = 'none';
                  var box = document.createElement('div');
                  box.style.padding = '16px'; box.style.textAlign = 'center';
                  box.innerHTML = '<h3 style="margin:0 0 12px">Płatność BLIK</h3>' +
                    '<p style="color:#6b7280;margin:4px 0">Zamówienie #' + orderId + ', do zapłaty: <strong>' + data.total.toFixed(2) + ' ' + sym + '</strong></p>' +
                    '<p style="margin:8px 0">Kod BLIK: <strong style="font-size:22px;color:#2563eb">' + (c.blik_code || '—') + '</strong></p>' +
                    '<p style="font-size:13px;color:#6b7280">Tytuł: ' + (c.titled || '') + '<br>Skontaktujemy się do potwierdzenia płatności.</p>' +
                    '<button onclick="closePrintModal()" style="margin-top:14px;padding:10px 20px;background:#2563eb;color:#fff;border:none;border-radius:8px;cursor:pointer">OK</button>';
                  document.querySelector('.modal').appendChild(box);
                  if (t) t.textContent = 'Zamówienie #' + orderId;
                  document.getElementById('printOrderModal').style.display = 'flex';
                }, 600);
              } else {
                showToast('Zamówienie #' + orderId + '. ' + (c.detail || 'Błąd płatności'), 'warning');
              }
            }).catch(function() {
              showToast('Zamówienie #' + orderId + ' — skontaktujemy się w celu płatności.', 'success');
              closePrintModal();
            });
          } else {
                      showToast(data.detail || 'Błąd zamówienia', 'error');
                    }
                  });
            };

  /* ==== Admin panel ==== */
  window.openAdminPanel = function() {
      var panel = document.getElementById('adminPanel');
      if (!panel) return;
      // restricted — only when URL has #admin anchor (przew full auth check dalej)
      if (location.hash !== '#admin' && !location.hash.startsWith('#admin')) {
        showToast('Administracja: dostęp ograniczony', 'warning');
        return;
      }
      panel.style.display = 'block';
      panel.scrollIntoView({behavior: 'smooth'});
      if (getStoredToken()) setTimeout(checkAdminAuth, 100);
    };

  window.authenticateAdmin = function() {
      var code = document.getElementById('adminTokenInput').value.trim();
      if (!code) { showToast('Wpisz token', 'error'); return; }
      localStorage.setItem('token', code);
      showToast('Admin odblokowany', 'success');
      setTimeout(checkAdminAuth, 100);
    };

    window.adminLogin = function() {
      var email = (document.getElementById('adminEmail') || {}).value || '';
      var pass = (document.getElementById('adminPassword') || {}).value || '';
      if (!email || !pass) { showToast('Wpisz email i hasło', 'error'); return; }
      fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify({ email: email, password: pass })
      }).then(function(r) { return r.json().then(function(d) { return { ok: r.ok, d: d }; }); })
        .then(function(res) {
          if (res.ok && res.d.token) {
            localStorage.setItem('token', res.d.token);
            if (res.d.user && res.d.user.is_admin) {
              showToast('Zalogowano jako admin', 'success');
              setTimeout(checkAdminAuth, 100);
            } else {
              showToast('Brak uprawnień administratora', 'error');
            }
          } else {
            showToast('Nieprawidłowe dane logowania', 'error');
          }
        }).catch(function() { showToast('Błąd logowania', 'error'); });
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
            '<td style="padding:8px">' + (o.material || '') + ' / ' + (o.color || '') + ' x' + (o.quantity || 1) + '</td>' +
            '<td style="padding:8px">' + (o.filament_grams || 0) + 'g<br><span style="color:#9ca3af;font-size:11px">' + (o.printing_hours || 0) + 'h</span></td>' +
            '<td style="padding:8px"><span style="color:#6b7280;font-size:11px">Fil ' + (o.filament_cost || 0).toFixed(0) + 'zł | Marża ' + (o.margin_pln || 0).toFixed(0) + 'zł</span><br><strong>' + (o.total || 0).toFixed(2) + ' ' + (o.currency || 'PLN') + '</strong><br><span style="color:#10b981;font-size:11px">Profit ' + ((o.total || 0) - (o.filament_cost || 0) - (o.electricity_cost || 0) - (o.shipping_cost || 0)).toFixed(0) + 'zł</span></td>' +
            '<td style="padding:8px"><select onchange="updateOrderStatus(' + o.id + ', this.value)" style="padding:4px;border:1px solid #d1d5db;border-radius:4px;font-size:12px;color:' + (statusColor[st] || '#6b7280') + '">' + opts + '</select></td>' +
            '<td style="padding:8px;text-align:center"><input type="checkbox" ' + (o.is_paid ? 'checked' : '') + ' onchange="toggleOrderPaid(' + o.id + ', this.checked)" title="Zapłacone"></td>' +
            '<td style="padding:8px"><button data-action="exportOrder" data-id="' + o.id + '" style="padding:4px 8px;border:1px solid #d1d5db;border-radius:4px;cursor:pointer">CSV</button><br>' +
                        (o.job_id ? '<button onclick="window.open(\'/e/' + o.job_id + '\',\'_blank\')" style="padding:4px 8px;border:1px solid #3b82f6;color:#3b82f6;border-radius:4px;background:none;cursor:pointer;margin-top:4px">3D</button><br>' : '') +
                        '<button onclick="showOrderNotes(' + o.id + ')" style="padding:4px 8px;border:1px solid #d1d5db;border-radius:4px;cursor:pointer;margin-top:4px">Uwagi</button></td>' +
            '</tr>';
        });
        document.getElementById('adminOrders').innerHTML =
          '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;gap:8px"><strong>Zamówienia (' + data.orders.length + ')</strong><button onclick="exportAllOrders()" style="padding:8px 16px;border:1px solid #1d4ed8;background:#1d4ed8;color:#fff;border-radius:6px;cursor:pointer">Export Excel</button></div>' +
          '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:12px"><thead><tr style="border-bottom:2px solid #e5e7eb;text-align:left"><th style="padding:8px">ID</th><th style="padding:8px">Data</th><th style="padding:8px">Klient</th><th style="padding:8px">Model</th><th style="padding:8px">Fil.</th><th style="padding:8px">Cena</th><th style="padding:8px">Status</th><th style="padding:8px;text-align:center">Zapł.</th><th style="padding:8px">Akcje</th></tr></thead><tbody>' + tbody + '</tbody></table></div>';
      } else {
        document.getElementById('adminOrders').innerHTML = '<p style="color:#ef4444">Brak dostępu lub brak zamówień</p>';
      }
    } catch (e) {
      document.getElementById('adminOrders').innerHTML = '<p style="color:#ef4444">Błąd ładowania</p>';
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

  window.switchAdminTab = function(tab) {
    document.querySelectorAll('.admin-tab').forEach(function(e) { e.style.display = 'none'; });
    document.querySelectorAll('.admin-tab-btn').forEach(function(e) { e.classList.remove('active'); e.style.borderBottom = 'none'; });
    var t = document.getElementById('admin' + tab.charAt(0).toUpperCase() + tab.slice(1));
    if (t) t.style.display = 'block';
    if (tab === 'orders') setTimeout(loadAdminOrders, 50);
    if (tab === 'stats') setTimeout(loadAdminStats, 50);
    if (tab === 'pricing') setTimeout(loadAdminPricing, 50);
    if (tab === 'codes') setTimeout(loadAdminCodes, 50);
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
