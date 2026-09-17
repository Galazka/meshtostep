/* ===== print.js — marketplace logic ===== */

(function() {
  /* ==== Toast ==== */
  const toastContainer = document.getElementById('toastContainer');

  function showToast(message, type = 'info') {
    const t = document.createElement('div');
    t.className = 'toast ' + type;
    t.textContent = message;
    toastContainer.appendChild(t);
    setTimeout(() => {
      t.style.opacity = '0';
      t.remove();
    }, 3500);
  }

  /* ==== Auth ==== */
  let currentUser = null;
  const authArea = document.getElementById('authArea');
  const loginBtn = document.getElementById('loginBtn');
  const registerBtn = document.getElementById('registerBtn');

  async function checkAuth() {
    try {
      const res = await fetch('/api/me', { headers: { 'Accept': 'application/json' } });
      if (res.ok) {
        currentUser = await res.json();
        authArea.innerHTML = '<span class="nav-link">' + (currentUser.username || 'Profil') + '</span>';
      } else {
        loginBtn.onclick = () => window.location.href = '/';
        registerBtn.onclick = () => window.location.href = '/';
      }
    } catch (e) {
      loginBtn.onclick = () => window.location.href = '/';
      registerBtn.onclick = () => window.location.href = '/';
    }
  }

  /* ==== Load requests ==== */
  async function loadRequests() {
    const list = document.getElementById('requestsList');
    list.innerHTML = '<div class="loading">Szukam zleceń w Twojej okolicy…</div>';
    try {
      const res = await fetch('/api/print/requests?test=1', { headers: { 'Accept': 'application/json' } });
      const data = await res.json();
      if (!data.ok || !data.requests || data.requests.length === 0) {
        list.innerHTML = '<div class="empty-state">Brak otwartych zleceń. <button class="btn btn-primary btn-small" onclick="openNewRequestModal()">Zamieść pierwsze zapytanie</button></div>';
        return;
      }
      list.innerHTML = data.requests.map(renderRequestCard).join('');
    } catch (e) {
      list.innerHTML = '<p class="text-error">Błąd połączenia — odśwież stronę.</p>';
    }
  }

  function formatAuctionEnd(auctionEnd) {
    const d = new Date(auctionEnd);
    const diffMs = d.getTime() - Date.now();
    const diffH = Math.floor(diffMs / 3600000);
    const diffM = Math.floor((diffMs % 3600000) / 60000);
    if (diffH > 0) return 'Licytacja: ' + diffH + 'h ' + diffM + 'm';
    return 'Licytacja: ' + diffM + 'm';
  }

  function renderRequestCard(req) {
    const materials = (req.material || 'PLA').split(',');
    const budget = req.budget_pln ? parseFloat(req.budget_pln).toFixed(2) + ' zł' : 'Brak budżetu';
    return `
<div class="request-card" onclick="openRequestDetail(${req.id})">
  <h3 class="request-title">${escapeHtml(req.title)}</h3>
  <div class="request-meta">
    ${materials.map(m => `<span class="badge badge-material">${escapeHtml(m)}</span>`).join('')}
    ${req.city ? `<span class="badge badge-city">${escapeHtml(req.city)}</span>` : ''}
    <span class="badge badge-auction">${formatAuctionEnd(req.auction_end)}</span>
  </div>
  <div class="request-budget">${budget}</div>
  <div class="offer-count">${req.offer_count || 0} ofert • kliknij by zobaczyć szczegóły</div>
</div>`;
  }

  /* ==== Modal: new request ==== */
  function openNewRequestModal() {
    if (!currentUser) { showToast('Zaloguj się najpierw', 'error'); return window.location.href = '/'; }

    document.body.style.overflow = 'hidden';
    const modal = document.getElementById('newRequestModal');
    if (modal) { modal.classList.add('active'); }
  }

  window.openNewRequestModal = openNewRequestModal;

  function closeNewRequestModal() {
    const m = document.getElementById('newRequestModal');
    if (m) m.classList.remove('active');
    document.body.style.overflow = '';
  }

  window.closeNewRequestModal = closeNewRequestModal;

  async function submitNewRequest(e) {
    e.preventDefault();
    const form = e.target;
    const fd = new FormData(form);
    try {
      const res = await fetch('/api/print/requests?' + Date.now(), {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + getStoredToken() },
        body: fd
      });
      const data = await res.json();
      if (data.ok) {
        showToast('Zamieszczono! Oczekuj oferty.', 'success');
        closeNewRequestModal();
        loadRequests();
      } else {
        showToast(data.detail || 'Błąd', 'error');
      }
    } catch (e) {
      showToast('Błąd sieci', 'error');
    }
  }

  window.submitNewRequest = submitNewRequest;

  /* ==== Request detail ==== */
  async function openRequestDetail(id) {
    const res = await fetch('/api/print/requests/' + id, { headers: { 'Accept': 'application/json' } });
    const data = await res.json();
    if (!data.ok) { showToast(data.detail || 'Nie znaleziono', 'error'); return; }
    renderRequestDetail(data.request);
    const detailModal = document.getElementById('requestDetailModal');
    if (detailModal) detailModal.classList.add('active');
    document.body.style.overflow = 'hidden';
  }

  window.openRequestDetail = openRequestDetail;

  function closeRequestDetailModal() {
    const m = document.getElementById('requestDetailModal');
    if (m) m.classList.remove('active');
    document.body.style.overflow = '';
  }

  window.closeRequestDetailModal = closeRequestDetailModal;

  function renderRequestDetail(req) {
    const container = document.getElementById('detailContent');
    if (!container) return;

    const isOwner = req.owner_username === (currentUser && currentUser.username);
    const auctionEnd = req.auction_end ? new Date(req.auction_end) : null;
    const canOffer = auctionEnd && auctionEnd.getTime() > Date.now();

    let offersHtml = '';
    if (req.offers && req.offers.length > 0) {
      offersHtml = req.offers.map(o => `
<div class="offer-item">
  <div class="offer-header">
    <strong class="offer-price">${parseFloat(o.price_pln).toFixed(2)} zł</strong>
    <span class="offer-days">${o.days ? o.days + ' dni' : 'Do ustalenia'} • ${o.shipping_method || 'Odbiór'}</span>
  </div>
  ${o.rating !== undefined ? `<div class="offer-rating">⭐ ${o.rating.toFixed(1)} (${o.rating_count || 0})</div>` : ''}
  ${o.message ? `<p class="offer-message">${escapeHtml(o.message)}</p>` : ''}
  ${isOwner && o.is_owner ? '' : (isOwner ? `<button class="btn btn-small btn-ghost" onclick="acceptOffer(${o.id})">Akceptuj</button>` : '')}
</div>`).join('');
    } else {
      offersHtml = '<p class="text-muted">Brak ofert jeszcze. Zaproś lokalnego drukarza!</p>';
    }

    const canPlaceOffer = canOffer && !isOwner;
    const offerForm = canPlaceOffer ? `
<form class="offer-form" onsubmit="submitOffer(event, ${req.id})">
  <h3>Dodaj swoją ofertę</h3>
  <div class="form-group">
    <label class="form-label">Cena (zł)</label>
    <input type="number" name="price_pln" min="0" step="0.01" required class="form-input">
  </div>
  <div class="form-group">
    <label class="form-label">Czas realizacji (dni)</label>
    <input type="number" name="days" min="1" class="form-input">
  </div>
  <div class="form-group">
    <label class="form-label">Odbiór / Wysyłka</label>
    <select name="shipping_method" class="form-select">
      <option value="pickup">Odbiór osobisty</option>
      <option value="ship">Wysyłka</option>
      <option value="both">Odbiór lub wysyłka</option>
    </select>
  </div>
  <div class="form-group">
    <label class="form-label">Wiadomość (opcjonalne)</label>
    <textarea name="message" rows="3" class="form-textarea" maxlength="500" placeholder="Dodatkowe info dla zamawiającego..."></textarea>
  </div>
  <button type="submit" class="btn btn-primary btn-block">Wyślij ofertę</button>
</form>` : '';

    container.innerHTML = `
<div class="request-detail-header">
  <h2>${escapeHtml(req.title)}</h2>
  <div class="request-meta">
    <span class="badge badge-material">${escapeHtml(req.material || 'PLA')}</span>
    <span class="badge badge-city">${escapeHtml(req.city || 'Polska')}</span>
    <span class="badge badge-auction">${formatAuctionEnd(req.auction_end)}</span>
  </div>
  <div class="request-budget">${req.budget_pln ? parseFloat(req.budget_pln).toFixed(2) + ' zł' : 'Brak budżetu'}</div>
  ${req.description ? `<div class="request-description">${escapeHtml(req.description).replace(/\n/g, '<br>')}</div>` : ''}
</div>
<div class="offers-section">
  <h3>Oferty (${req.offers ? req.offers.length : 0})</h3>
  ${offersHtml}
</div>
${offerForm}`;
  }

  window.renderRequestDetail = renderRequestDetail;

  async function submitOffer(e, requestId) {
    e.preventDefault();
    const form = e.target;
    const fd = new FormData(form);
    try {
      const res = await fetch(`/api/print/requests/${requestId}/offers?${Date.now()}`, {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + getStoredToken() },
        body: fd
      });
      const data = await res.json();
      if (data.ok) {
        showToast('Oferta wysłana!', 'success');
        closeRequestDetailModal();
        loadRequests();
      } else {
        showToast(data.detail || 'Błąd', 'error');
      }
    } catch (e) {
      showToast('Błąd sieci', 'error');
    }
  }

  window.submitOffer = submitOffer;

  async function acceptOffer(offerId) {
    if (!confirm('Akceptować tę ofertę?')) return;
    try {
      const res = await fetch(`/api/print/offers/${offerId}/accept?${Date.now()}`, {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + getStoredToken() }
      });
      const data = await res.json();
      if (data.ok) {
        showToast('Oferta zaakceptowana. Kontakt wiadomością prywatna.', 'success');
        closeRequestDetailModal();
        loadRequests();
      } else {
        showToast(data.detail || 'Błąd', 'error');
      }
    } catch (e) {
      showToast('Błąd sieci', 'error');
    }
  }

  window.acceptOffer = acceptOffer;

  /* ==== Helpers ==== */
  function getStoredToken() {
    // Check cookie or localStorage
    const m = document.cookie.match(/token=([^;]+)/);
    if (m) return m[1];
    return localStorage.getItem('token') || '';
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>"']/g, function(c) {
      return { '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c];
    });
  }

  /* ==== Init ==== */
  document.addEventListener('DOMContentLoaded', function() {
    checkAuth();
    loadRequests();

    // Close modals on Escape
    document.addEventListener('keydown', function(e) {
      if (e.key === 'Escape') {
        closeNewRequestModal();
        closeRequestDetailModal();
      }
    });

    // Close modal on backdrop click
    window.addEventListener('click', function(e) {
      if (e.target.classList.contains('modal-backdrop')) {
        closeNewRequestModal();
        closeRequestDetailModal();
      }
    });
  });

  window.showToast = showToast;
})();
