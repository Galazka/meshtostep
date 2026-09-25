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
    try {
      var m = document.cookie.match(/(?:^|;\s*)(?:mt_)?token=([^;]+)/);
      if (m) return decodeURIComponent(m[1]);
    } catch (e) {}
    try {
      return localStorage.getItem('mt_token') || localStorage.getItem('token') || '';
    } catch (e) { return ''; }
  }

  async function checkAuth() {
    var token = getStoredToken();
    if (!token) return;                        /* anonim — nie ma po co pytac /api/me (bylo 401) */
    try {
      var res = await fetch('/api/me', {
        headers: { 'Accept': 'application/json', 'Authorization': 'Bearer ' + token }
      });
      if (res.ok) {
        currentUser = await res.json();
        if (currentUser.is_admin) {
          var adminLink = document.getElementById('adminLink');
          if (adminLink) adminLink.style.display = 'block';
        }
      } else if (res.status === 401 || res.status === 403) {
        try { localStorage.removeItem('mt_token'); } catch (e) {}
      }
    } catch (e) {}
  }

  /* ==== Materials + shipping load ==== */
  async function loadMaterials() {
    var box = document.getElementById('materialList');
    if (!box) return;
    try {
      var res = await fetch('/api/admin/materials?' + Date.now());
      var data = res.ok ? await res.json() : { materials: { "PLA": 79, "PETG": 95, "ABS": 89, "ASA": 159, "TPU": 130 }, colors: {} };
            var html = Object.keys(data.materials || {}).map(function(m) {
              var p = data.materials[m];
              var price = typeof p === 'number' ? p : (p.price_kg || 0);
              var desc = (typeof p === 'object' && p.desc) ? p.desc : '';
              return '<div class="material-card"><strong>' + m +
                                           '</strong>' +
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
    var lang = (typeof window.__pi18n !== 'undefined') ? window.__pi18n.lang : 'pl';
    var t = function(k){ if(typeof window.__pi18n !== 'undefined' && window.__pi18n.t) return window.__pi18n.t(k); return k; };
    var map = {
      'PLA': t('mPLA'),
      'PETG': t('mPETG'),
      'ABS': t('mABS'),
      'ASA': t('mASA'),
      'TPU': t('mTPU'),
      'PLA HT': t('mPLAHT'),
      'PLA CF': t('mPLACF'),
      'PETG HF': t('mPETGHF'),
      'PETG FR': t('mPETGFR'),
      'ASA CF': t('mASACF'),
      'PLA Matte': t('mPLAMatte'),
      'PLA Silk': t('mPLASilk'),
      'PLA Glow': t('mPLAGlow')
    };
    note.textContent = map[sel.value] || (typeof window.__pi18n!=='undefined'? window.__pi18n.t('matPick') : 'Wybierz materiał...');
    if (typeof calculatePrintPrice === 'function') calculatePrintPrice();
  };

  function loadShipping() {
    var tbody = document.getElementById('shippingTable');
    if (!tbody) return;
    var t = function(k){ return (typeof window.__pi18n!=='undefined' && window.__pi18n.t) ? window.__pi18n.t(k) : k; };
    var rows = [
          /* ceny z DEFAULT_SHIPPING (routes_order.py) + PACKING_FEE_PLN 3 zł; pickup bez packing */
          [t('sStand'), 19.49, 38.00, 58.00],
          [t('sExpr'), 36.00, 73.00, 113.00],
          [t('sPri'), 43.99, 98.00, 163.00],
          [t('sPick'), 0, 0, 0]
        ];
        tbody.innerHTML = '<tr><td style="padding:8px;color:#6b7280;font-size:11px" colspan="4">' + t('shipNote') + '</td></tr>' + rows.map(function(r) {
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
                    // cena ostateczna — sprzedaż jako osoba fizyczna (brak VAT/faktur), bez dopłat po fakcie
                    var vatNote = document.getElementById('priceVatNote');
                    if (vatNote) {
                      vatNote.textContent = '① Cena jest ostateczna — nie doliczamy nic po fakcie. Do zamówienia dołączamy rachunek.';
                    }
                    var fxNote = document.getElementById('priceFxNote');
                    if (fxNote) {
                      var rate = data.exchange_rate || 1.0;
                      fxNote.textContent = data.currency === 'PLN' ? 'Waluta: PLN (konto własne)' : 'Waluta: ' + data.currency + ' · kurs 1 ' + data.currency + ' = ' + (1 / rate).toFixed(4) + ' PLN';
                    }
                    if (data.free_shipping) {
                                          var shLine = document.getElementById('priceShipping');
                                          if (shLine) shLine.textContent = '0,00 zł (darmowa wysyłka ≥ 200 zł)';
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

  var __adminQ = { search: '', sort: 'newest', page: 1 };
    window.adminSetSearch = function(v, f){ if(f) __adminQ.search=v; __adminQ.page=1; loadAdminOrders(); };
    window.adminSetSort = function(v){ __adminQ.sort=v; __adminQ.page=1; loadAdminOrders(); };
    window.adminPage = function(d){ __adminQ.page = Math.max(1, __adminQ.page + d); loadAdminOrders(); };
    async function loadAdminOrders() {
      var token = getStoredToken();
      var headers = { 'Authorization': 'Bearer ' + token, 'Accept': 'application/json' };
      try {
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
    if (tab === 'orders') setTimeout(function(){ if (typeof loadAdminOrders === 'function') loadAdminOrders(); }, 50);
    if (tab === 'stats') setTimeout(function(){ if (typeof loadAdminStats === 'function') loadAdminStats(); }, 50);
    if (tab === 'pricing') setTimeout(function(){ if (typeof loadAdminPricing === 'function') loadAdminPricing(); }, 50);
    if (tab === 'codes') setTimeout(function(){ if (typeof loadAdminCodes === 'function') loadAdminCodes(); }, 50);
    if (tab === 'gallery') setTimeout(function(){ if (typeof loadAdminGallery === 'function') loadAdminGallery(); }, 50);
    if (tab === 'reviews') setTimeout(function(){ if (typeof loadAdminReviews === 'function') loadAdminReviews(); }, 50);
    if (tab === 'reports') setTimeout(function(){ if (typeof loadAdminReports === 'function') loadAdminReports(); }, 50);
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
      loadGallery();
      loadReviews();
    document.addEventListener('keydown', function(e) { if (e.key === 'Escape') closePrintModal(); });
    window.addEventListener('click', function(e) {
      if (e.target && e.target.classList && e.target.classList.contains('modal-backdrop')) closePrintModal();
    });
  });
  // Scroll reveal
  if ('IntersectionObserver' in window) {
    var _ro = new IntersectionObserver(function(es){ es.forEach(function(en){ if(en.isIntersecting){ en.target.classList.add('in'); _ro.unobserve(en.target); } }); }, {threshold: 0.12});
    document.querySelectorAll('.reveal').forEach(function(el){ _ro.observe(el); });
  } else {
    document.querySelectorAll('.reveal').forEach(function(el){ el.classList.add('in'); });
  }
  window.showToast = showToast;
  window.currencySymbol = currencySymbol;

  /* ==== Reviews (social proof) ==== */
  window.renderStars = function(n) {
    var out = '';
    for (var i = 1; i <= 5; i++) out += i <= n ? '★' : '☆';
    return out;
  };
  window.loadReviews = function() {
    var grid = document.getElementById('reviewsGrid');
    var sum = document.getElementById('revSummary');
    if (!grid) return;
    fetch('/api/reviews?t=' + Date.now()).then(function(r){ return r.json(); }).then(function(d){
      var items = (d && d.items) || [];
      if (sum) sum.innerHTML = (d && d.count) ? ('<b style="color:var(--accent);font-size:22px">' + d.avg + ' / 5</b> <span style="color:var(--muted)">na podstawie ' + d.count + ' opinii</span>') : '';
      if (!items.length) { grid.innerHTML = '<div style="text-align:center;color:var(--muted);padding:20px;grid-column:1/-1">Pierwsze opinie pojawią się wkrótce.</div>'; return; }
      grid.innerHTML = items.map(function(r){
        return '<div style="background:var(--card);border:1px solid var(--border);border-radius:12px;padding:16px;box-shadow:var(--shadow)">' +
          '<div style="color:#f59e0b;letter-spacing:2px;font-size:14px">' + renderStars(r.rating) + '</div>' +
          '<div style="font-weight:700;font-size:15px;margin-top:6px">' + esc(r.name||'') + '</div>' +
          (r.text ? '<div style="color:var(--muted);font-size:13.5px;margin-top:6px;line-height:1.5">' + esc(r.text) + '</div>' : '') +
          '<div style="color:#94a3b8;font-size:12px;margin-top:8px">' + (r.created_at||'') + '</div></div>';
      }).join('');
    }).catch(function(){ grid.innerHTML='<div style="text-align:center;padding:16px;grid-column:1/-1">Nie udało się wczytać opinii.</div>'; });
  };

  window.submitReview = function() {
    var name = (document.getElementById('revName')||{}).value||'';
    var email = (document.getElementById('revEmail')||{}).value||'';
    var text = (document.getElementById('revText')||{}).value||'';
    var rating = parseInt((document.getElementById('revRating')||{}).value||'5');
    var st = document.getElementById('revStatus');
    if (!name.trim()) { if (st) st.textContent = 'Podaj imię.'; return; }
    fetch('/api/reviews', { method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ name: name, email: email, rating: rating, text: text }) })
      .then(function(r){ return r.json(); }).then(function(d){
        if (d.ok) {
          if (st) { st.textContent = '✓ Dziękujemy! Twoja opinia została dodana.'; st.style.color = '#15803d'; }
          ['revName','revEmail','revText'].forEach(function(id){ var el=document.getElementById(id); if(el) el.value=''; });
          loadReviews();
        } else if (st) st.textContent = d.detail || 'Błąd.';
      }).catch(function(){ if (st) st.textContent = 'Błąd sieci.'; });
  };


  window.addEventListener('languagechange', function(){
    if (typeof loadShipping === 'function') loadShipping();
    if (typeof loadMaterials === 'function') loadMaterials();
    if (typeof window.updateMaterialNote === 'function') updateMaterialNote();
    if (typeof loadGallery === 'function') loadGallery();
    if (typeof loadAdminGallery === 'function') loadAdminGallery();
  });

  /* ==== Gallery (landing + admin) ==== */
  window.loadGallery = function() {
    var grid = document.getElementById('galleryGrid');
    if (!grid) return;
    fetch('/api/gallery?t=' + Date.now()).then(function(r){ return r.json(); }).then(function(d){
      var items = (d && d.items) || [];
      if (!items.length) { grid.innerHTML = '<div style="text-align:center;color:var(--muted);font-size:14px;padding:24px">Galeria w przygotowaniu — wkrótce dodamy pierwsze prace.</div>'; return; }
      grid.innerHTML = items.map(function(g){
        return '<div class="gallery-card" style="background:var(--card);border:1px solid var(--border);border-radius:12px;overflow:hidden;box-shadow:var(--shadow);transition:all .15s">' +
          '<img src="' + (g.image||'') + '" loading="lazy" style="width:100%;height:190px;object-fit:cover;display:block" onerror="this.remove()">' +
          '<div style="padding:12px 14px"><div style="font-weight:700;font-size:15px;color:var(--fg)">' + esc(g.title||'') + '</div>' +
          (g.material? '<div style="color:#64748b;font-size:12.5px;margin-top:4px">' + esc(g.material) + (g.color?' · '+esc(g.color):'') + '</div>':'') +
          (g.description? '<div style="color:var(--muted);font-size:12.5px;margin-top:4px;line-height:1.4">' + esc(g.description) + '</div>':'') +
          '</div></div>';
      }).join('');
    }).catch(function(){ grid.innerHTML='<div style="text-align:center;color:var(--muted);padding:20px">Nie udało się wczytać galerii.</div>'; });
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
  function _openAdminOnHash(){
    if (location.hash === '#admin' || location.hash.startsWith('#admin')) {
      var panel = document.getElementById('adminPanel');
      if (panel) { panel.style.display = 'block'; panel.scrollIntoView({behavior:'smooth'}); }
      if (getStoredToken()) setTimeout(checkAdminAuth, 200);
      var tab = location.hash.split('#admin')[1] || '';
      if (tab.startsWith('/')) tab = tab.slice(1);
      if (tab && typeof switchAdminTab === 'function') setTimeout(function(){ switchAdminTab(tab); }, 300);
    }
  }
  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', _openAdminOnHash); }
  else { setTimeout(_openAdminOnHash, 50); }

})();
