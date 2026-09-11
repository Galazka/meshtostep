# Professional Hosting Features — Minimal Implementation Plan

> **Repo:** `C:/Users/galaz/Desktop/MeshToStep`  
> **Stack:** FastAPI + SQLAlchemy (SQLite/PG) + vanilla JS + Three.js  
> **Principle:** Fewest files changed, shortest diff, no new deps.

---

## Audit Summary

### What Already Exists
| Feature | Status | Location |
|---------|--------|----------|
| Upload → host (STL/3MF/OBJ) | ✅ Done | `routes_convert.py:POST /api/convert` |
| On-demand STEP conversion | ✅ Done | `routes_convert.py:POST /api/convert-on-demand/{uuid}` |
| Download endpoint (format param) | ✅ Done | `routes_convert.py:GET /api/download/{uuid}?format=stl\|step\|3mf\|obj` |
| Share link with token | ✅ Done | `routes_convert.py:POST /api/share`, `routes_share.py:GET /s/{token}` |
| Vanity URL `/u/{username}/{slug}` | ✅ Done | `routes_community.py:GET /u/{username}/{slug}` |
| 3D viewer (STL/OBJ/3MF) | ✅ Done | `routes_convert.py:GET /api/stl-preview/{uuid}` |
| Embed page `/e/{job_id}` | ✅ Done | `routes_share.py:embed_page()` |
| Ad slot system (5 seeded slots) | ✅ Done | `routes_ads.py`, `models.py:AdSlot`, `database.py` seed |
| SMTP mail (verify + reset) | ✅ Done | `mail.py:send_mail()`, `send_verification()`, `send_reset()` |
| Cookie consent | ❌ Not present | — |
| Download format chooser dialog | ❌ Not present | — |
| Embed HTML dialog (proper) | ❌ Not present | `prompt()` hack in `routes_share.py:338`, `myfiles.js:62-64` |
| Email model link to someone | ❌ Not present | — |
| Larger logo / more nav tabs | ❌ Not present | Logo `<img>` has no explicit height in nav |

### Current Download Flow (the gap)
- After upload: result card shows `btn-dl` (download STL) + `btn-step` (on-demand STEP) — no format picker
- Share page: single "Pobierz STEP" button — no mesh format option
- `/api/download/{uuid}?format=stl|step|3mf|obj` already supports format param — **backend ready, frontend missing the dialog**

### Current Embed Flow (the gap)
- `showEmbed()` → `prompt()` with hardcoded iframe — no size options, no copy button, no preview
- `doEmbed()` → same prompt() hack
- `/e/{job_id}` embed page exists and works — **backend ready, frontend needs a proper modal**

---

## Implementation Plan (6 features, 9 files touched)

### Feature 1: Download Dialog (choose mesh vs solid, format)

**Files:**
- `frontend/index.html` — add download modal HTML + CSS
- `frontend/js/myfiles.js` — replace `prompt()` with modal logic, export `showDownloadDialog(job)`
- `backend/app/routes_share.py` — update share page download button to use format picker

**Implementation:**
```
1. Add HTML modal in index.html (after authModal):
   - Radio: Mesh (STL/3MF/OBJ) vs Solid (STEP)
   - Format sub-selector appears per radio
   - Preview: filename, file size, face count
   - Download button

2. JS: showDownloadDialog(job) — populates modal from job data
   - Mesh radio → show STL + 3MF + OBJ buttons (disabled if not applicable)
   - Solid radio → show STEP button (triggers convert-on-demand if status=hosted)
   - Direct download via: /api/download/{uuid}?format={fmt}

3. Share page (routes_share.py template):
   - Replace single download <a> with modal trigger or inline dropdown
   - Pass job data to JS: {uuid, filename, faces, status, original_ext}
```

**Pitfalls:**
- 3MF/OBJ originals only available if user still has source file (check JOBS_DIR/uuid/)
- STEP may not exist yet for hosted jobs — show "Convert → STEP" button instead of direct download

---

### Feature 2: Embed Dialog (proper HTML generator)

**Files:**
- `frontend/index.html` — add embed modal HTML + CSS
- `frontend/js/myfiles.js` — replace `doEmbed()` prompt() with modal

**Implementation:**
```
1. Add HTML modal in index.html:
   - Size presets: Responsive (default), 800×500, 640×400, 1280×720
   - iframe code textarea (auto-generated, readonly)
   - Copy button (navigator.clipboard.writeText)
   - "Preview" mini-iframe showing the embed
   - Social meta tags snippet (OG embed for Discord/Twitter)

2. JS: showEmbedDialog(jobId):
   - Template: <iframe src="/e/{jobId}" width="{W}" height="{H}" frameborder="0" allowfullscreen></iframe>
   - Size radio buttons update W/H
   - OG meta tag block:
     <meta property="og:title" content="...">
     <meta property="og:type" content="video.other">
     <meta property="og:url" content="https://3dfile.link/e/{jobId}">
     <meta property="og:image" content="https://3dfile.link/api/preview/{uuid}">

3. Share page (routes_share.py template):
   - Embed button triggers embed modal instead of prompt()
```

**Pitfalls:**
- CSP `frame-ancestors 'self'` blocks embedding on third-party sites — needs whitelist or `*`
- For social embeds, need `<meta>` tags in `/e/{job_id}` head (already partial — add og:title, og:image)

---

### Feature 3: Email Model Link

**Files:**
- `backend/app/routes_convert.py` — add `POST /api/share/{token}/email` endpoint
- `backend/app/mail.py` — add `send_share_link()` function
- `frontend/js/myfiles.js` — add "Send by email" button to share modal

**Implementation:**
```
1. Backend: POST /api/share/{token}/email
   - Body: { recipient_email: str }
   - Validate email format, rate limit (5 emails/min per user)
   - Call send_share_link(recipient_email, token, sender_email)
   - Increment a send_count on ShareLink (new optional column)

2. mail.py: send_share_link(to, token, sender_email):
   - HTML email with:
     - "X shared a 3D model with you" header
     - Preview thumbnail image: https://3dfile.link/api/preview/{uuid}
     - "View 3D Model" CTA button → /s/{token}
     - "Download STEP" secondary button
     - Footer: "Powered by 3dfile.link"
   - Reuses existing send_mail() infrastructure

3. Frontend share modal:
   - Add "Wyślij mailem" button below "Kopiuj link"
   - Input: email address field + send button
   - Feedback: "Wysłano!" / "Błąd"
```

**Pitfalls:**
- Rate limit essential to prevent spam (use existing `_login_hits` pattern or new `_email_hits`)
- SMTP may not be configured — show user-friendly "Email not configured" message
- Don't leak whether recipient email exists (always return OK)

---

### Feature 4: Cookie Consent Banner

**Files:**
- `frontend/index.html` — add banner HTML + CSS + JS
- `frontend/js/main.js` — add cookie consent logic

**Implementation:**
```
1. HTML: fixed bottom banner (similar to existing PWA banner CSS):
   - "Używamy localStorage do zapamiętania ustawień. Brak cookies śledzących."
   - + optional: "Reklamy (AdSense) mogą używać cookies. [Akceptuj] [Odrzuć]"
   - Accept/Reject buttons
   - Privacy policy link

2. JS in main.js:
   - Check localStorage.getItem('mt_cookie_consent')
   - If absent → show banner
   - Accept → set localStorage, enable ad loading
   - Reject → set localStorage, hide ad slots, disable impression tracking
   - loadAdSlots() already loads ads — gate it on consent

3. CSS:
   - Reuse .pwa-banner styling pattern
   - Bottom fixed, z-index: 9999
   - Responsive: full width on mobile

4. GDPR note:
   - App uses ONLY localStorage (mt_token, mt_theme, mt_lang) — no cookies
   - AdSense requires cookie consent in EU
   - Cookie consent is legally needed IF AdSense is loaded
   - If no ads: banner can be informational only ("we use localStorage")
```

**Pitfalls:**
- Must block AdSense script loading until consent (currently `loadAdSlots()` fires unconditionally in `main.js:104`)
- CSP already allows `pagead2.googlesyndication.com` — no change needed there
- Don't block core functionality — only ad loading depends on consent

---

### Feature 5: First-View Ad Slot

**Files:**
- `frontend/index.html` — ensure hero_top slot renders properly
- `backend/app/database.py` — slot already seeded, verify position

**Implementation:**
```
1. The hero_top ad slot is already seeded at sort_order=99:
   "Hero top" → slot_key "hero_top" → position "hero_top"
   
2. HTML already has: <div class="ad-slot" data-slot="hero_top"></div>
   placed right after hero badge, before hero title (line 437)

3. The first-view ad slot IS the hero_top — it loads on page load
   via loadAdSlots() → fetch('/api/ads/slots') → inject ad_code

4. Minor improvements:
   - Ensure hero_top slot renders at full width above the fold
   - Add CSS for better spacing (hero_top has no special styling)
   - Gate loading on cookie consent (Feature 4)
```

**Pitfalls:**
- hero_top is currently between hero badge and hero title — may break visual hierarchy
- Consider moving to position AFTER hero (hero_bottom) for better UX
- AdSense auto-ads may conflict with manual slots

---

### Feature 6: Larger Logo + More Header Tabs

**Files:**
- `frontend/index.html` — modify nav HTML + CSS
- `frontend/js/i18n.js` — add translations for new tabs
- `frontend/js/main.js` — add routing for new pages

**Implementation:**
```
1. Logo: Change <img> height from implicit to explicit:
   Before: <img src="/logo.png?v=2" alt="3DFILE" onerror="this.style.display='none'">
   After:  <img src="/logo.png?v=2" alt="3DFILE" style="height:32px" onerror="this.style.display='none'">
   
   Nav logo class already exists (.nav-logo) — just needs explicit size.

2. Add header tabs (after Moje pliki):
   - "FAQ" button → scrolls to FAQ section or shows page
   - "Jak to działa" button → scrolls to How It Works section
   Both already exist in the page as sections — just add nav anchors.

3. Nav HTML changes:
   - Add: <button class="nav-link" onclick="go('faq')" data-i18n="navFAQ">FAQ</button>
   - Add: <button class="nav-link" onclick="go('hiw')" data-i18n="navHowItWorks">Jak to działa</button>
   
4. go() function in index.html (inline script):
   - Add cases for 'faq' and 'hiw' that scroll to respective sections
   - These are NOT separate pages — just anchor scrolls within page-home

5. i18n.js: Keys already exist (navFAQ, navHowItWorks) — no changes needed.
```

**Pitfalls:**
- Too many nav tabs break mobile layout — keep max 5 total
- FAQ/HIW are within page-home, not separate SPA pages
- `go()` function is inline in index.html (not in a module) — must edit index.html directly

---

## File Change Summary

| File | Changes | Est. Lines |
|------|---------|------------|
| `frontend/index.html` | +Download modal, +Embed modal, +Cookie banner, Logo size, +Nav tabs, +Modal CSS | ~80 |
| `frontend/js/myfiles.js` | `showDownloadDialog()`, `showEmbedDialog()`, email send | ~60 |
| `frontend/js/main.js` | Cookie consent gate for ads, scroll routing | ~15 |
| `backend/app/routes_convert.py` | `POST /api/share/{token}/email` | ~25 |
| `backend/app/routes_share.py` | Share page: format picker data, embed modal trigger, email in template | ~30 |
| `backend/app/mail.py` | `send_share_link()` | ~15 |
| `frontend/js/i18n.js` | Minor: no new keys needed (navFAQ, navHowItWorks exist) | 0 |

**Total:** ~225 lines across 6 files. No new files. No new dependencies.

---

## Dependency Check

- No new Python packages needed
- No new JS libraries needed
- `navigator.clipboard` API — available in all modern browsers, HTTPS required (already enforced)
- AdSense — already in CSP, already loaded via `loadAdSlots()`

---

## Pitfall Summary

1. **CSP frame-ancestors** must change from `'self'` to `*` or a whitelist if embedding on 3rd-party sites is desired. Currently `main.py:62` has `frame-ancestors 'self'`.

2. **Share page download** currently hardcodes STEP format (`routes_share.py:516`) — needs to support mesh format too, but original mesh path isn't stored on ShareLink model. Workaround: fetch from JOBS_DIR by job UUID.

3. **Cookie consent gating ads** — `loadAdSlots()` in `main.js:104` runs unconditionally. Must wrap in consent check. If consent is "reject", ad slots stay empty (their CSS `:empty::before` shows slot key as placeholder).

4. **Email SMTP may not be configured** — `mail.py` returns False silently. Frontend must handle gracefully (show "Skonfiguruj SMTP" message).

5. **Download dialog for hosted-only jobs** — STEP doesn't exist yet. Must show "Konwertuj → STEP" button that triggers `/api/convert-on-demand/{uuid}` before download.

6. **Embed OG tags** — `/e/{job_id}` page (`routes_share.py:531-608`) already has partial OG meta but missing `og:title` for social previews. Minor fix.

---

## Implementation Order

1. **Feature 6** (Logo + Tabs) — 15 min, zero risk, visual win
2. **Feature 1** (Download Dialog) — 45 min, biggest UX improvement
3. **Feature 2** (Embed Dialog) — 30 min, follows from download dialog pattern
4. **Feature 5** (First-View Ad) — 10 min, already exists, just needs CSS polish
5. **Feature 4** (Cookie Consent) — 30 min, must gate ad loading
6. **Feature 3** (Email Export) — 30 min, depends on share modal being done

**Estimated total: ~2.5 hours**
