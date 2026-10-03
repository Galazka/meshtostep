/* ============================================================
   order_card.js — karta zamówienia dla panelu drukarni (3dfile.link).
   Renderuje KAŻDE zamówienie jako kartę z grupami: Klient / Dostawa /
   Modele / Koszty / Notatki. Zamiast 9 gęstych kolumn.
   Zależny od admin_print.js (esc, fmtPL, showToast, loadAdminOrders).
   ============================================================ */
(function () {
  'use strict';

  var AP_TOKEN = 'mt_token';

  function esc(s) {
    var o = (s === null || s === undefined) ? '' : String(s);
    return o.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
  function zl(n, d) {
    var v = parseFloat(n || 0);
    return (isFinite(v) ? v : 0).toFixed(d === undefined ? 2 : d) + ' zl';
  }
  function num(n, d) {
    var v = parseFloat(n || 0);
    return (isFinite(v) ? v : 0).toFixed(d === undefined ? 0 : d);
  }
  function token() {
    var t = '';
    try { t = localStorage.getItem(AP_TOKEN) || localStorage.getItem('token') || ''; } catch (e) {}
    if (!t) { try { if (window.storeToken) t = window.storeToken() || ''; } catch (e2) {} }
    return t;
  }
  function tokq() {
    var t = token();
    return t ? '&token=' + encodeURIComponent(t) : '';
  }
  function fmtDate(iso) {
    if (!iso) return '';
    if (typeof window.fmtPL === 'function') { try { return window.fmtPL(iso); } catch (e) {} }
    return String(iso).slice(0, 16).replace('T', ' ');
  }

  var STATUS = {
    'nowy':        { label: 'Nowy',        bg: '#fef2f2', fg: '#b91c1c', bd: '#fecaca' },
    'wycena':      { label: 'Wycena',      bg: '#fffbeb', fg: '#b45309', bd: '#fde68a' },
    'realizacja':  { label: 'Realizacja',  bg: '#f5f3ff', fg: '#6d28d9', bd: '#ddd6fe' },
    'drukowane':   { label: 'Drukowane',   bg: '#fffbeb', fg: '#b45309', bd: '#fde68a' },
    'gotowe':     { label: 'Gotowe',     bg: '#eff6ff', fg: '#1d4ed8', bd: '#bfdbfe' },
    'wyslane':     { label: 'Wyslane',     bg: '#ecfeff', fg: '#0e7490', bd: '#a5f3fc' },
    'wysłane':    { label: 'Wysłane',     bg: '#ecfeff', fg: '#0e7490', bd: '#a5f3fc' },
    'dostarczone': { label: 'Dostarczone', bg: '#ecfdf5', fg: '#047857', bd: '#a7f3d0' },
    'anulowane':   { label: 'Anulowane',   bg: '#f8fafc', fg: '#64748b', bd: '#e2e8f0' }
  };
  var STATUS_ORDER = ['nowy', 'wycena', 'realizacja', 'drukowane', 'gotowe',
                      'wysłane', 'wyslane', 'dostarczone', 'anulowane'];

  var SHIP = {
    'pickup':         { label: 'Odbiór osobisty',    eta: 'do 5 dni' },
    'pickup_express': { label: 'Odbiór ekspres',      eta: 'do 2 dni · priorytet' },
    'standard':       { label: 'Paczkomat InPost',    eta: '1-2 dni' },
    'express':        { label: 'Kurier ekspres',      eta: 'priorytet' },
    'priority':       { label: 'Paczkomat priorytet', eta: 'priorytet' },
    'address':        { label: 'Kurier na adres',     eta: '1-2 dni' }
  };

  var FMT_LBL = { stl: 'STL', obj: 'OBJ', '3mf': '3MF', ply: 'PLY', step: 'STEP', stp: 'STP' };

  var PICKUP_ADDR = '3dfile.link — Gdańsk Osowa, ul. Międzygwiezdna 31/2, 80-299';

  /* ---------- jedna rubryczka label + value ---------- */
  function cell(label, value, opts) {
    opts = opts || {};
    if (value === null || value === undefined || value === '') return '';
    var extra = '';
    if (opts.mono) extra += 'font-family:ui-monospace,SFMono-Regular,Menlo,monospace;';
    if (opts.color) extra += 'color:' + opts.color + ';';
    if (opts.strong) extra += 'font-weight:600;';
    var val;
    if (opts.href) {
      val = '<a href="' + esc(opts.href) + '" target="_blank" rel="noopener" style="color:#2B5CE6;' + extra + '">'
          + esc(value) + '</a>';
    } else {
      val = '<span style="' + extra + '">' + esc(value) + '</span>';
    }
    return '<div style="padding:5px 0;border-bottom:1px solid #f1f5f9">'
         + '<div style="font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:#94a3b8;margin-bottom:1px">'
         + esc(label) + '</div>'
         + '<div style="font-size:13px;line-height:1.35">' + val + '</div></div>';
  }

  /* ---------- sekcja rozwijana ---------- */
  function section(id, title, meta, bodyHtml, openByDefault) {
    return '<details class="oc-sec"' + (openByDefault ? ' open' : '')
         + ' style="border:1px solid #e8edf3;border-radius:10px;background:#fff;margin-top:8px;overflow:hidden">'
         + '<summary style="display:flex;align-items:center;gap:8px;padding:9px 12px;cursor:pointer;'
         + 'background:#f8fafc;font-size:11.5px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;'
         + 'color:#334155;user-select:none;list-style:none">'
         + '<span style="font-size:10px;color:#94a3b8">&#9656;</span>'
         + '<span>' + esc(title) + '</span>'
         + (meta ? '<span style="margin-left:auto;font-weight:500;text-transform:none;letter-spacing:0;'
                  + 'font-size:12px;color:#64748b">' + esc(meta) + '</span>' : '')
         + '</summary>'
         + '<div style="padding:2px 12px 10px">' + bodyHtml + '</div>'
         + '</details>';
  }

  /* ---------- Klient ---------- */
  function secClient(o) {
    var g = cell('Imię i nazwisko', o.customer_name, { strong: true })
          + cell('E-mail', o.customer_email, { mono: true, href: 'mailto:' + o.customer_email });
    if (o.customer_phone) {
      g += cell('Telefon', o.customer_phone,
                { mono: true, href: 'tel:' + String(o.customer_phone).replace(/[^+\d]/g, '') });
    }
    if (o.customer_country) g += cell('Kraj', o.customer_country, { mono: true });
    return section('c' + o.id, 'Klient', o.customer_city || '', g, true);
  }

  /* ---------- Dostawa ---------- */
  function secShip(o) {
    var m = SHIP[o.shipping_method] || { label: o.shipping_method || 'brak', eta: '' };
    var meta = m.label;
    if (m.eta) meta += ' · ' + m.eta;

    var g = cell('Sposób dostawy', m.label, { strong: true });

    if (o.shipping_method === 'pickup' || o.shipping_method === 'pickup_express') {
      g += cell('Punkt odbioru', PICKUP_ADDR, { mono: true });
      g += cell('Charakterystyka', 'odbiór osobiisty — nic nie wysyłamy');
    } else {
      var addr = o.customer_address || '';
      // stare zamówienia: paczkomat był doklejony do adresu jako tekst
      var legacy = '';
      var m2 = /Paczkomat:\s*([^,|]+)/i.exec(addr);
      if (m2) legacy = m2[1].trim();
      var clean = addr.replace(/Paczkomat:\s*[^,|]+,?\s*/ig, '').replace(/,\s*$/, '').trim();

      if (o.shipping_point_name) g += cell('Paczkomat (kod)', o.shipping_point_name, { mono: true, strong: true });
      if (o.shipping_point_addr) g += cell('Paczkomat (adres)', o.shipping_point_addr, { mono: true });
      if (legacy && !o.shipping_point_name) g += cell('Paczkomat (z adresu)', legacy, { mono: true });
      if (o.shipping_point_lat && o.shipping_point_lon) {
        g += cell('Mapa punktu',
          num(o.shipping_point_lat, 5) + ', ' + num(o.shipping_point_lon, 5),
          { mono: true,
            href: 'https://www.openstreetmap.org/?mlat=' + o.shipping_point_lat
                + '&mlon=' + o.shipping_point_lon
                + '#map=17/' + o.shipping_point_lat + '/' + o.shipping_point_lon });
      }
      if (clean) g += cell('Adres', clean);
      if (o.customer_postal) g += cell('Kod pocztowy', o.customer_postal, { mono: true });
      if (o.customer_city) g += cell('Miasto', o.customer_city);
    }
    g += cell('Koszt dostawy',
      (parseFloat(o.shipping_cost || 0) > 0 ? zl(o.shipping_cost) : 'gratis'),
      { strong: parseFloat(o.shipping_cost || 0) === 0 });
    if (o.tracking_code) g += cell('Numer przesyłki', o.tracking_code, { mono: true, strong: true });

    return section('d' + o.id, 'Dostawa', meta, g, true);
  }

  /* ---------- Modele ---------- */
  function secModels(o) {
    var items = (o.items && o.items.length) ? o.items
      : (o.material ? [{ model_name: o.model_name, material: o.material, color: o.color,
                         quantity: o.quantity || 1, job_uuid: o.job_uuid }] : []);
    var body = '', withFile = 0, missing = 0;

    items.forEach(function (it, ix) {
      var fname = it.filename || it.model_name || ('model' + (ix + 1));
      var ext = String(fname).split('.').pop().toLowerCase();
      if (!FMT_LBL[ext]) ext = 'stl';
      var avail = [ext];
      if (ext !== 'stl') avail.push('stl');   // backend konwertuje 3MF/OBJ -> STL

      var spec = [];
      if (it.material) spec.push(esc(it.material));
      if (it.color) spec.push(esc(it.color));
      if (it.quantity > 1) spec.push('<b>&times;' + esc(it.quantity) + '</b>');
      if (it.dims_mm) spec.push(esc(it.dims_mm));
      if (it.infill && parseInt(it.infill, 10) !== 15) spec.push('<span style="color:#b45309">' + esc(it.infill) + '% wypełn.</span>');
      if (it.volume_cm3) spec.push(num(it.volume_cm3, 1) + ' cm³');

      if (!it.job_uuid) {
        missing++;
        body += '<div style="padding:10px 0;border-bottom:1px solid #f1f5f9">'
          + '<div style="font-size:13px;font-weight:600">' + esc(fname) + '</div>'
          + '<div style="font-size:11.5px;color:#b45309;margin-top:2px">'
          + '&#9888; brak pliku — zamówienie sprzed naprawy zapisu plików</div>'
          + (spec.length ? '<div style="font-size:11px;color:#64748b;margin-top:1px">' + spec.join(' · ') + '</div>' : '')
          + '</div>';
        return;
      }

      withFile++;
      var q = tokq();
      var dl = avail.map(function (f) {
        return '<a class="oc-btn" target="_blank" rel="noopener"'
             + ' href="/api/download/' + encodeURIComponent(it.job_uuid) + '?format=' + f + q + '"'
             + ' title="Pobierz ' + esc(FMT_LBL[f] || f.toUpperCase()) + '">&darr; ' + esc(FMT_LBL[f] || f.toUpperCase()) + '</a>';
      }).join('');

      body += '<div style="display:flex;gap:13px;align-items:flex-start;padding:10px 0;border-bottom:1px solid #f1f5f9">'
        + '<div style="flex:0 0 68px;display:flex;flex-direction:column;align-items:center;gap:3px">'
        + '<button class="oc-thumb" type="button" data-preview="' + esc(it.job_uuid) + '"'
        + ' data-fmt="' + esc(ext) + '" data-name="' + esc(fname) + '"'
        + ' title="Podejrzij model przed pobraniem"'
        + ' style="width:68px;height:68px;flex:0 0 68px;border:1px solid #e2e8f0;'
        + 'border-radius:8px;background:#f8fafc;cursor:pointer;overflow:hidden;padding:0">'
        + '<img src="/api/preview/' + encodeURIComponent(it.job_uuid) + '" alt="" loading="lazy"'
        + ' style="width:100%;height:100%;object-fit:contain;pointer-events:none"'
        + ' onerror="this.style.visibility=\'hidden\'">'
        + '</button>'
        + '<span style="font-size:9px;letter-spacing:.03em;color:#94a3b8;'
        + 'text-transform:uppercase;text-align:center;line-height:1.25">podgląd 3D</span>'
        + '</div>'
        + '<div style="min-width:0;flex:1">'
        + '<div style="font-size:13px;font-weight:600;word-break:break-all">' + esc(fname) + '</div>'
        + (spec.length ? '<div style="font-size:11.5px;color:#64748b;margin-top:2px">' + spec.join(' · ') + '</div>' : '')
        + '<div style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap">' + dl + '</div>'
        + '</div></div>';
    });

    if (!items.length) body = '<div style="padding:8px 0;font-size:12px;color:#94a3b8">Brak pozycji w zamówieniu.</div>';

    var extra = [];
    if (o.filament_grams) extra.push(cell('Filament', num(o.filament_grams, 1) + ' g', { mono: true }));
    if (o.printing_hours) extra.push(cell('Czas druku', num(o.printing_hours, 1) + ' h', { mono: true }));
    if (o.print_parts > 1) extra.push(cell('Podział na części', o.print_parts + ' szt.', { mono: true }));
    if (o.payment_method) extra.push(cell('Płatność', String(o.payment_method).toUpperCase(), { mono: true }));
    if (o.currency && o.currency !== 'PLN') extra.push(cell('Waluta', o.currency, { mono: true }));
    var agg = extra.length
      ? '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(118px,1fr));gap:0 16px;'
        + 'margin-top:10px;padding-top:8px;border-top:1px solid #e2e8f0">' + extra.join('') + '</div>'
      : '';

    if (o.notes) {
      body += '<div style="margin-top:8px;padding:8px 10px;background:#f8fafc;'
           + 'border-left:3px solid #cbd5e1;border-radius:0 6px 6px 0">'
           + '<div style="font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:#94a3b8">Notatka klienta</div>'
           + '<div style="font-size:12.5px;color:#334155;white-space:pre-wrap;margin-top:2px">'
           + esc(o.notes) + '</div></div>';
    }

    var n = items.length;
    var meta = n + (n === 1 ? ' model' : ' modeli');
    if (withFile) meta += ' · pliki gotowe';
    if (missing) meta += ' · ' + missing + ' bez pliku';
    return section('m' + o.id, 'Modele', meta, body + agg, true);
  }

  /* ---------- Koszty ---------- */
  function secMoney(o) {
    var num = function (v) { return parseFloat(v || 0); };
    var g = '';

    /* --- KOSZT (suma w dół) --- */
    if (o.filament_cost) g += cell('Filament', zl(o.filament_cost));
    if (o.electricity_cost) g += cell('Prąd', zl(o.electricity_cost));
    if (o.color_premium) g += cell('Pigment', zl(o.color_premium));
    if (o.multicolor_fee) g += cell('Wielokolor', zl(o.multicolor_fee));
    if (o.surcharge_pln) g += cell('Dopłata za pigment', zl(o.surcharge_pln));
    if (o.subtotal) g += cell('Koszt wytworzenia', zl(o.subtotal), { strong: true });

    // backend liczy cost_pln = koszt wytworzenia + pakowanie; bez pozycji pakowania
    // suma wyglądała na błęd (0.88 + 5.00 = 5.88 przy koszcie 0.88)
    var pack = num(o.cost_pln) - num(o.subtotal);
    if (pack > 0.005) g += cell('Pakowanie', zl(pack));
    if (o.cost_pln) g += cell('Koszt całkowity', zl(o.cost_pln), { strong: true });
    if (o.shipping_cost) g += cell('Dostawa', zl(o.shipping_cost));
    if (o.discount_pln) g += cell('Rabat', '−' + zl(o.discount_pln), { color: '#b91c1c' });

    /* --- PRZYCHÓD (nie sumuje się z kosztami — marża jest JUZ w zysku,
           bo zysk = cena − koszt całkowity − dostawa) --- */
    var profit = (o.profit_pln !== null && o.profit_pln !== undefined)
               ? num(o.profit_pln)
               : (num(o.total) - num(o.shipping_cost) - num(o.cost_pln));

    var rev = '';
    var totalTxt = zl(o.total) + ((o.currency || 'PLN') === 'PLN' ? '' : ' ' + (o.currency || 'PLN'));
    rev += cell('DO ZAPŁATY', totalTxt, { strong: true, color: '#2B5CE6' });
    rev += cell('ZYSK', zl(profit), { strong: true, color: profit >= 0 ? '#047857' : '#b91c1c' });
    if (o.margin_pln) rev += cell('w tym narzut', zl(o.margin_pln), { color: '#64748b' });

    g += '<div style="margin-top:10px;padding-top:8px;border-top:1px solid #e2e8f0;'
       + 'font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:#94a3b8">Przychód</div>'
       + rev;

    return section('k' + o.id, 'Koszty', zl(o.total, 2), g, false);
  }

function secNotes(o) {
    var body = '<div style="padding:4px 0">'
      + '<textarea id="an_' + o.id + '" rows="4"'
      + ' placeholder="Notatka wewnętrzna — widoczna tylko w panelu. Np. preferowany kontakt, uwagi do druku, historia zmian."'
      + ' style="width:100%;box-sizing:border-box;padding:9px 11px;border:1px solid #cbd5e1;'
      + 'border-radius:8px;font:inherit;font-size:12.5px;resize:vertical">'
      + esc(o.admin_notes || '') + '</textarea>'
      + '<div style="display:flex;gap:7px;margin-top:7px;flex-wrap:wrap;align-items:center">'
      + '<button class="oc-btn oc-btn-primary" type="button" data-notes-save="' + o.id + '">Zapisz notatkę</button>'
      + '<button class="oc-btn" type="button" data-notes-clear="' + o.id + '">Wyczyść</button>'
      + '<span style="font-size:11px;color:#94a3b8;margin-left:auto">'
      + (o.admin_notes
          ? 'zapisana' + (o.updated_at ? ' ' + esc(fmtDate(o.updated_at)) : '')
          : 'brak notatki') + '</span>'
      + '</div></div>';
    return section('n' + o.id, 'Notatki', o.admin_notes ? 'ma notatkę' : '', body, false);
  }

  /* ---------- karta ---------- */
  function orderCard(o) {
    var st = o.status || 'nowy';
    var s = STATUS[st] || { label: st, bg: '#f8fafc', fg: '#64748b', bd: '#e2e8f0' };
    var nItems = (o.items && o.items.length) || (o.material ? 1 : 0);
    var paid = !!o.is_paid;

    var opts = STATUS_ORDER.map(function (m) {
      return '<option value="' + m + '"' + (m === st ? ' selected' : '') + '>'
           + STATUS[m].label + '</option>';
    }).join('');

    var head =
      '<div style="display:flex;align-items:center;gap:9px;flex-wrap:wrap;padding:11px 14px;'
      + 'background:linear-gradient(180deg,#fbfcfe,#f6f8fb);border-bottom:1px solid #e8edf3">'
      + '<span style="font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:15px;font-weight:700;color:#0f172a">#'
      + esc(o.id) + '</span>'
      + '<span style="font-size:11.5px;color:#64748b;font-family:ui-monospace,monospace">'
      + esc(fmtDate(o.created_at)) + '</span>'
      + '<span style="padding:2px 8px;border-radius:999px;font-size:11px;font-weight:700;'
      + 'background:' + s.bg + ';color:' + s.fg + ';border:1px solid ' + s.bd + '">'
      + esc(s.label) + '</span>'
      + (paid
        ? '<span style="padding:2px 8px;border-radius:999px;font-size:11px;font-weight:700;'
          + 'background:#ecfdf5;color:#047857;border:1px solid #a7f3d0">ZAPŁACONE</span>'
        : '<span style="padding:2px 8px;border-radius:999px;font-size:11px;font-weight:700;'
          + 'background:#fef2f2;color:#b91c1c;border:1px solid #fecaca">NIEOPŁACONE</span>')
      + '<span style="margin-left:auto;font-size:11px;color:#94a3b8">'
      + nItems + (nItems === 1 ? ' model' : ' modeli') + '</span>'
      + '<span style="font-size:17px;font-weight:700;color:#2B5CE6;font-family:ui-monospace,monospace">'
      + esc(zl(o.total, 2)) + '</span>'
      + '</div>';

    var ctrl =
      '<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:10px 14px;'
      + 'border-bottom:1px solid #eef2f7;background:#fff">'
      + '<label style="font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:#94a3b8">Status</label>'
      + '<select id="st_' + o.id + '" data-status-sel="' + o.id + '"'
      + ' style="padding:5px 9px;border:1px solid #cbd5e1;border-radius:7px;font:inherit;'
      + 'font-size:12.5px;color:' + s.fg + ';font-weight:600;background:#fff">'
      + opts + '</select>'
      + '<span id="stbtn_' + o.id + '" style="display:none;gap:5px">'
      + '<button class="oc-btn oc-btn-ok" type="button" data-status-ok="' + o.id + '"'
      + ' title="Zatwierdź — wyśle maila do klienta">&check; zatwierdź</button>'
      + '<button class="oc-btn" type="button" data-status-cancel="' + o.id + '"'
      + ' data-prev="' + esc(st) + '" title="Cofnij zmianę">&times; cofnij</button>'
      + '</span>'
      + '<button class="oc-btn" type="button" data-paid-toggle="' + o.id + '"'
      + ' data-paid="' + (paid ? '1' : '0') + '"'
      + ' title="Zaznacz zamówienie jako opłacone"'
      + ' style="' + (paid ? 'background:#059669;border-color:#059669;color:#fff'
                           : 'background:#fff;border-color:#cbd5e1;color:#334155') + '">'
      + (paid ? '&#10003; zapłacone' : '&#9679; nieopłacone') + '</button>'
      + (!paid
        ? '<button class="oc-btn" type="button" data-sync-pay="' + o.id + '"'
          + ' title="Odśwież status płatności ze Stripe">&#8635; Stripe</button>'
        : '')
      + '<span style="flex:1"></span>'
      + ((o.is_paid && (o.shipping_method === 'standard' || o.shipping_method === 'express'
                        || o.shipping_method === 'priority'))
        ? '<button class="oc-btn oc-btn-ship" type="button" data-ship="' + o.id + '"'
          + ' title="Nadaj paczkomatem InPost (ShipX)">Nadaj InPost</button>'
        : '')
      + (o.job_id
        ? '<a class="oc-btn" target="_blank" rel="noopener" href="/e/' + encodeURIComponent(o.job_id) + '"'
          + ' title="Otwórj model w przeglądarce">&nearr; 3D</a>'
        : '')
      + '<button class="oc-btn" type="button" data-csv="' + o.id + '"'
      + ' title="Eksport tego zamówienia do CSV">CSV</button>'
      + '<button class="oc-btn oc-btn-danger" type="button" data-del="' + o.id + '"'
      + ' title="Usuń zamówienie">Usuń</button>'
      + '</div>';

    return '<article class="oc-card" data-order="' + esc(o.id) + '"'
      + ' style="border:1px solid #e2e8f0;border-radius:12px;background:#fff;margin-bottom:12px;'
      + 'box-shadow:0 1px 2px rgba(15,23,42,.04);overflow:hidden">'
      + head + ctrl
      + '<div style="padding:0 14px 12px">'
      + secClient(o) + secShip(o) + secModels(o) + secMoney(o) + secNotes(o)
      + '</div></article>';
  }

  /* ---------- modal podglądu 3D ---------- */
  function ensureModal() {
    var el = document.getElementById('oc-preview-modal');
    if (el) return el;
    el = document.createElement('div');
    el.id = 'oc-preview-modal';
    el.setAttribute('style', 'position:fixed;inset:0;z-index:10000;background:rgba(15,23,42,.78);'
      + 'display:none;align-items:center;justify-content:center;padding:20px');
    el.innerHTML =
      '<div style="background:#fff;border-radius:14px;width:min(920px,100%);height:min(760px,92vh);'
      + 'display:flex;flex-direction:column;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,.35)">'
      + '<div style="display:flex;align-items:center;gap:10px;padding:12px 16px;border-bottom:1px solid #e8edf3">'
      + '<strong id="oc-pv-title" style="font-size:14px;word-break:break-all"></strong>'
      + '<span style="flex:1"></span>'
      + '<button id="oc-pv-close" type="button"'
      + ' style="border:1px solid #cbd5e1;background:#fff;border-radius:7px;padding:5px 11px;'
      + 'cursor:pointer;font:inherit;font-size:12.5px">Zamknij &times;</button>'
      + '</div>'
      + '<div id="oc-pv-body" style="flex:1;min-height:0;position:relative;background:#f8fafc"></div>'
      + '</div>';
    document.body.appendChild(el);
    function close() {
      el.style.display = 'none';
      // canvas viewera zostalby w DOM (brak publicznego dispose) — czyscimy recznie
      var body = el.querySelector('#oc-pv-body');
      if (body) while (body.firstChild) body.removeChild(body.firstChild);
    }
    el.addEventListener('click', function (e) { if (e.target === el) close(); });
    el.querySelector('#oc-pv-close').addEventListener('click', close);
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && el.style.display !== 'none') close();
    });
    return el;
  }

  function viewerUrl(jobUuid, fmt) {
    return '/api/download/' + encodeURIComponent(jobUuid) + '?format=' + (fmt || 'stl') + tokq();
  }

  var _mod = null;
  function loadViewerModule() {
    if (_mod) return Promise.resolve(_mod);
    if (!window.__viewerPro) {
      _mod = import('/asset/viewer_pro.js?v=16').catch(function (e) {
        _mod = null;
        throw new Error('viewer_pro.js: ' + ((e && e.message) ? e.message : e));
      });
    } else {
      _mod = Promise.resolve(null);
    }
    return _mod;
  }

  function renderIn(body, jobUuid, fmt) {
    // Kazde otwarcie = nowa instancja viewera. Stara zostawiałaby canvas
    // i kontekst WebGL w DOM (viewer_pro nie ma publicznego dispose()).
    while (body.firstChild) body.removeChild(body.firstChild);

    var host = document.createElement('div');
    host.style.cssText = 'position:absolute;inset:0;overflow:hidden';
    body.appendChild(host);

    loadViewerModule().then(function (mod) {
      var api = mod ? mod.initViewerPro({
        container: host,
        lang: 'pl',
        authToken: token(),
        toolbar: false,
        compact: true
      }) : window.__viewerPro;

      if (!api || typeof api.loadUrl !== 'function') {
        body.innerHTML = '<div style="padding:24px;color:#b91c1c;font-size:13px">'
                       + 'Viewer nie jest załadowany na tej stronie.</div>';
        return;
      }
      api.loadUrl(viewerUrl(jobUuid, fmt), {
        onError: function () {
          var bar = host.querySelector('div');
          if (bar && /niedostępny|unavailable/i.test(bar.textContent || '')) return;
          body.insertAdjacentHTML('afterbegin',
            '<div style="position:absolute;z-index:2;left:10px;top:10px;padding:6px 10px;'
            + 'background:#fef2f2;border:1px solid #fecaca;border-radius:7px;color:#b91c1c;'
            + 'font-size:11.5px">Nie udało się wczytać modelu — plik może być uszkodzony '
            + 'lub nie jest jeszcze wygenerowany.</div>');
        }
      });
    }).catch(function (e) {
      body.innerHTML = '<div style="padding:24px;color:#b91c1c;font-size:13px">'
                     + esc((e && e.message) ? e.message : e) + '</div>';
    });
  }

  function openPreview(jobUuid, fmt, name) {
    var modal = ensureModal();
    modal.style.display = 'flex';
    modal.querySelector('#oc-pv-title').textContent = 'Podgląd 3D — ' + (name || jobUuid);
    var body = modal.querySelector('#oc-pv-body');
    renderIn(body, jobUuid, fmt);
  }

  /* ---------- notatki: zapis / czyszczenie ---------- */
  function toast(m, t) { if (typeof window.showToast === 'function') window.showToast(m, t); }

  function saveNotes(id, clear) {
    var ta = document.getElementById('an_' + id);
    if (!ta) return;
    var val = clear ? '' : ta.value;
    var body = new URLSearchParams();
    body.set('admin_notes', val);
    fetch('/api/orders/' + encodeURIComponent(id) + '?t=' + Date.now(), {
      method: 'PATCH',
      headers: { 'Authorization': 'Bearer ' + token(),
                 'Content-Type': 'application/x-www-form-urlencoded' },
      body: body.toString()
    }).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      if (clear) ta.value = '';
      toast(clear ? 'Notatka wyczyszczona' : 'Notatka zapisana', 'success');
      if (typeof window.loadAdminOrders === 'function') window.loadAdminOrders();
    }).catch(function (e) {
      toast('Błąd zapisu notatki: ' + e.message, 'error');
    });
  }

  /* ---------- CSS ---------- */
  var CSS =
    '.oc-card:hover{border-color:#cbd5e1}'
    + '.oc-sec>summary::-webkit-details-marker{display:none}'
    + '.oc-sec>summary:hover{background:#eef2f7}'
    + '.oc-sec>summary>span:first-child{display:inline-block;transition:transform .12s;font-size:9px}'
    + '.oc-sec[open]>summary>span:first-child{transform:rotate(90deg)}'
    + '.oc-btn{display:inline-block;padding:4px 9px;border:1px solid #cbd5e1;background:#fff;'
    + 'color:#334155;border-radius:7px;cursor:pointer;font:inherit;font-size:11.5px;text-decoration:none;'
    + 'line-height:1.4;white-space:nowrap}'
    + '.oc-btn:hover{background:#f1f5f9;border-color:#94a3b8}'
    + '.oc-btn-primary{background:#2B5CE6;border-color:#2B5CE6;color:#fff}'
    + '.oc-btn-primary:hover{background:#1e45b8;color:#fff;border-color:#1e45b8}'
    + '.oc-btn-ok{background:#059669;border-color:#059669;color:#fff}'
    + '.oc-btn-ok:hover{background:#047857;color:#fff}'
    + '.oc-btn-ship{background:#fff7ed;border-color:#fdba74;color:#c2410c}'
    + '.oc-btn-ship:hover{background:#ffedd5}'
    + '.oc-btn-danger{background:#fff;border-color:#fca5a5;color:#dc2626}'
    + '.oc-btn-danger:hover{background:#fef2f2}'
    + '.oc-thumb:hover{border-color:#2B5CE6}'
    + '.oc-thumb:hover img{opacity:.85}'
    + '@media(max-width:700px){.oc-card{border-radius:10px}}';

  function injectCss() {
    if (document.getElementById('oc-style')) return;
    var s = document.createElement('style');
    s.id = 'oc-style';
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  /* ---------- init ---------- */
  function init() {
    injectCss();

    document.addEventListener('change', function (e) {
      var sel = e.target.closest ? e.target.closest('[data-status-sel]') : null;
      if (sel) {
        var id = sel.getAttribute('data-status-sel');
        var bar = document.getElementById('stbtn_' + id);
        if (bar) bar.style.display = 'inline-flex';
        return;
      }
    });

    document.addEventListener('click', function (e) {
      var el = e.target.closest
        ? e.target.closest('[data-preview],[data-notes-save],[data-notes-clear],[data-status-ok],'
                          + '[data-status-cancel],[data-sync-pay],[data-ship],[data-csv],[data-del],'
                          + '[data-paid-toggle]')
        : null;
      if (!el) return;

      if (el.hasAttribute('data-preview')) {
        openPreview(el.getAttribute('data-preview'), el.getAttribute('data-fmt'),
                    el.getAttribute('data-name'));
        return;
      }
      if (el.hasAttribute('data-notes-save')) { saveNotes(el.getAttribute('data-notes-save'), false); return; }
      if (el.hasAttribute('data-notes-clear')) {
        var cid = el.getAttribute('data-notes-clear');
        if (confirm('Wyczyścić notatkę do zamówienia #' + cid + '?')) saveNotes(cid, true);
        return;
      }
      if (el.hasAttribute('data-status-ok')) {
        if (typeof window.confirmStatus === 'function') window.confirmStatus(el.getAttribute('data-status-ok'));
        return;
      }
      if (el.hasAttribute('data-status-cancel')) {
        var oid = el.getAttribute('data-status-cancel');
        var s = document.getElementById('st_' + oid);
        if (s) s.value = el.getAttribute('data-prev');
        var bar = document.getElementById('stbtn_' + oid);
        if (bar) bar.style.display = 'none';
        return;
      }
      if (el.hasAttribute('data-paid-toggle')) {
        var pid = el.getAttribute('data-paid-toggle');
        var on = el.getAttribute('data-paid') === '1';
        if (typeof window.toggleOrderPaid === 'function') window.toggleOrderPaid(pid, !on);
        return;
      }
      if (el.hasAttribute('data-sync-pay')) {
        if (typeof window.syncPayment === 'function') window.syncPayment(el.getAttribute('data-sync-pay'), el);
        return;
      }
      if (el.hasAttribute('data-ship')) {
        if (typeof window.createShipment === 'function') window.createShipment(el.getAttribute('data-ship'));
        return;
      }
      if (el.hasAttribute('data-csv')) {
        if (typeof window.exportOrder === 'function') window.exportOrder(el.getAttribute('data-csv'));
        return;
      }
      if (el.hasAttribute('data-del')) {
        if (typeof window.deleteOrder === 'function') window.deleteOrder(el.getAttribute('data-del'));
      }
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();

  window.orderCard = orderCard;
  window.openOrderPreview = openPreview;
})();