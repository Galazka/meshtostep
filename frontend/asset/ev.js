/* 3dfile.link — analityka wlasna. Bez cookies, bez zewnetrznych skryptow.
   Zbiera: pageview + klikniecia CTA + outbound. Ident: sessionStorage sid. */
(function () {
  if (window.__evLoaded) return;
  window.__evLoaded = true;

  var API = '/api/ev';
  var sid = '';
  try {
    sid = sessionStorage.getItem('mt_sid') || '';
    if (!sid) {
      sid = (Date.now().toString(36) + Math.random().toString(36).slice(2, 10));
      sessionStorage.setItem('mt_sid', sid);
    }
  } catch (e) { sid = ''; }

  var QUEUE = [];
  var BUSY = false;

  function send(name, meta) {
    if (!name) return;
    var body = JSON.stringify({
      name: name,
      path: location.pathname,
      ref: document.referrer || '',
      sid: sid,
      meta: meta || null
    });
    try {
      if (navigator.sendBeacon) {
        navigator.sendBeacon(API, new Blob([body], { type: 'application/json' }));
        return;
      }
    } catch (e) { /* fallthrough */ }
    try {
      fetch(API, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: body, keepalive: true
      }).catch(function () {});
    } catch (e) { /* ignore */ }
  }

  function ev(name, meta) {
    if (!name) return;
    // nie zasmiecaj: pageview tylko raz na sciezke w sesji
    if (name === 'pageview') {
      var k = 'mt_pv_' + location.pathname;
      try { if (sessionStorage.getItem(k)) return; sessionStorage.setItem(k, '1'); } catch (e) {}
    }
    if (name === 'search' && meta && !meta.q) return;
    QUEUE.push([name, meta]);
    flush();
  }

  function flush() {
    if (BUSY || !QUEUE.length) return;
    BUSY = true;
    var job = QUEUE.shift();
    send(job[0], job[1]);
    setTimeout(function () { BUSY = false; flush(); }, 120);
  }

  window.ev = ev;

  /* ── automatyczne zdarzenia ───────────────────────────────── */
  function boot() {
    ev('pageview', null);

    document.addEventListener('click', function (e) {
      var a = e.target && e.target.closest ? e.target.closest('a,button') : null;
      if (!a) return;
      var href = a.getAttribute && a.getAttribute('href') || '';
      var txt = (a.textContent || '').trim().slice(0, 60);

      if (href.indexOf('/zamow') === 0 || /wydrukuj u nas|zamawiam|druk 3d/i.test(txt)) {
        ev('click_print', { href: href.slice(0, 120), txt: txt });
        return;
      }
      if (href.indexOf('/api/download') === 0 || href.indexOf('/download/') === 0) {
        ev('download_click', { href: href.slice(0, 120) });
        return;
      }
      if (a.dataset && a.dataset.evShare) {
        ev('share_click', { href: href.slice(0, 120) });
        return;
      }
      if (href && /^https?:\/\//i.test(href) && href.indexOf(location.host) === -1) {
        ev('outbound', { href: href.slice(0, 180), txt: txt });
      }
    }, true);

    // formularz kontaktowy
    document.addEventListener('submit', function (e) {
      var f = e.target;
      if (f && f.id === 'contactForm') ev('contact_send', {});
    }, true);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

  // odsylanie przy wyjsciu (dla SPA-ish)
  window.addEventListener('pagehide', function () { flush(); });
})();