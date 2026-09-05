# 3dhosty.com — Community Hosting Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Rebrand MeshToStep → 3dhosty.com i zbudować uniwersalny hosting 3D z vanity URL, visibility, search/tagi, komentarze, YouTube, paid models 20% prowizji, mapka reklam.

**Architecture:** FastAPI + SQLAlchemy (SQLite/PostgreSQL) + FreeCAD headless. Frontend vanilla JS + Three.js. DB migracje via _migrate_columns(). Nowe tabele: Comment, Sale. Rozszerzenia: User.username, Job.visibility/slug/price/tags, ShareLink.visibility/slug, AdSlot.position map.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, Three.js STL/OBJ/3MF loaders, Stripe (paid models), Railway.

---

### Task 1: Rebrand — main.py app title + CORS

**Objective:** Zmień title MeshToStep → 3dhosty.com

**Files:**
- Modify: `backend/app/main.py:23`

**Step 1:** Patch app = FastAPI(title="3dhosty.com")
**Step 2:** Verify grep title
**Step 3:** Commit

### Task 2: Rebrand — frontend index.html title/meta/og

**Objective:** title, meta description, og:image na 3dhosty.com

**Files:**
- Modify: `frontend/index.html:1-30` (head section)

### Task 3: Rebrand — header logo → /

**Objective:** Fix header nie wraca na główną

**Files:**
- Modify: `frontend/index.html` header <a href="/">

### Task 4: SEO — sitemap.xml + robots.txt

**Objective:** sitemap tylko public, robots allow

**Files:**
- Create: `frontend/sitemap.xml` (dynamic via route)
- Create: `frontend/robots.txt`
- Modify: `backend/app/main.py` add routes /sitemap.xml /robots.txt

### Task 5: Models — User.username + Job/ShareLink rozszerzenia

**Objective:** DB schema dla vanity URL + visibility + paid

**Files:**
- Modify: `backend/app/models.py`

Add:
- User.username (unique, index)
- Job: slug, visibility (public/unlisted/private), description, tags, youtube_url, price_cents, is_paid, views
- ShareLink: slug, visibility
- Comment table
- Sale/Order table (buyer, seller, amount, commission 20%, status)
- keep AdSlot.position slot_key map

### Task 6: DB migrate — _migrate_columns()

**Objective:** Kolumny powstają na istniejącej DB

**Files:**
- Modify: `backend/app/database.py`

### Task 7: Routes — vanity URL /u/{username}/{slug}

**Objective:** Alias ShareLink token → /u/{nick}/{slug}

**Files:**
- Modify: `backend/app/routes_share.py`
- Add route GET /u/{username}/{slug} lookup

### Task 8: Routes — visibility filter + search + tags

**Objective:** /api/models?q=&tag=&sort= public only

**Files:**
- Modify: `backend/app/routes_share.py` or new routes_models.py
- Add GET /api/models, GET /api/tags

### Task 9: Routes — komentarze

**Objective:** POST/GET /api/comments

**Files:**
- Create: `backend/app/routes_comments.py`
- Modify: `backend/app/main.py` include router

### Task 10: Routes — paid models 20%

**Objective:** POST /api/models/{id}/purchase, webhook, Sale

**Files:**
- Create: `backend/app/routes_sales.py`
- Modify: `backend/app/routes_payments.py` reuse Stripe

### Task 11: Frontend — model page (opis/zdjęcia/YouTube/tagi/cena)

**Objective:** Strona /u/{nick}/{slug} z pełnym UI

**Files:**
- Modify: `frontend/index.html` or create `frontend/model.html`

### Task 12: Frontend — wyszukiwarka + tag cloud

**Objective:** Search bar + filtry

**Files:**
- Modify: `frontend/index.html` add search section

### Task 13: Admin — mapka reklam (klik na layout)

**Objective:** Interaktywna mapa gdzie reklama się pojawi

**Files:**
- Modify: `frontend/admin.html` add Ads Map tab
- Modify: `backend/app/routes_ads.py` position presets

### Task 14: Cleanup — martwy kod credits + pricing

**Objective:** Usuń CreditPack/Payment legacy jeśli nieużywane

**Files:**
- Modify: `backend/app/models.py`, `routes_payments.py`, `frontend/index.html`

### Task 15: Deploy — Railway + commit

**Objective:** Push, health check

**Files:**
- Terminal: git add, commit, push, curl /api/health
