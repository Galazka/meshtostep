# MeshToStep

STL/3MF/OBJ → STEP converter SaaS powered by FreeCAD headless + OpenCASCADE.

## Features

- **FreeCAD headless** — true B-Rep conversion, not just faceted mesh
- **5 optimization modes** — Auto, Ultra, Smooth (Taubin), Light, Off
- **3D preview** — Three.js viewer before and after conversion
- **Share links** — public download with view/download counters
- **Embed iframe** — embed converter in any website
- **Stripe payments** — USD credit packs ($0.99/$2.99/$7.99)
- **Admin panel** — geo stats, per-user drill-down, manual credit adjustment
- **i18n** — Polish + English, auto-detect browser language
- **REST API** — OpenAPI docs at `/docs`

## Quick Start (Local)

```bash
# Install FreeCAD (if not installed)
# Windows: https://www.freecad.org/downloads.php
# Linux: sudo apt install freecad

# Install Python deps
pip install -r requirements.txt

# Run
export DATABASE_URL=sqlite:///./data/meshtostep.db
export SECRET_KEY=$(openssl rand -hex 32)
export ADMIN_EMAIL=admin@test.pl
export ADMIN_PASSWORD=Test123!
PYTHONPATH=backend uvicorn backend.app.main:app --reload --port 8000
```

## Deploy to Railway

1. **Create Railway project** → New → Dockerfile
2. **Set environment variables** in Railway Dashboard:
   - `SECRET_KEY` — run `openssl rand -hex 32`
   - `DATABASE_URL` — Railway auto-provides PostgreSQL URL
   - `ADMIN_EMAIL` — your admin email
   - `ADMIN_PASSWORD` — your admin password
   - `APP_URL` — your Railway domain (e.g. `https://meshtostep.up.railway.app`)
   - `STRIPE_SECRET_KEY` — from Stripe Dashboard
   - `STRIPE_WEBHOOK_SECRET` — from Stripe Webhooks
   - `STRIPE_CURRENCY` — `usd`
3. **Push to GitHub** and connect Railway to repo
4. **Set up Stripe webhook** → `https://meshtostep.up.railway.app/api/payments/webhook`
5. **Add credit packs** in Stripe Dashboard matching DB seed (5/$0.99, 25/$2.99, 100/$7.99)

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | (required) | JWT signing key |
| `DATABASE_URL` | `sqlite:///./data/meshtostep.db` | PostgreSQL recommended for production |
| `FREE_CREDITS` | `3` | Credits on signup |
| `MAX_FILE_MB` | `200` | Max upload size |
| `APP_URL` | `http://localhost:8000` | Public URL |
| `ADMIN_EMAIL` | (empty) | Bootstrap admin on first run |
| `ADMIN_PASSWORD` | (empty) | Bootstrap admin password |
| `STRIPE_SECRET_KEY` | (empty) | Stripe API key |
| `STRIPE_WEBHOOK_SECRET` | (empty) | Stripe webhook secret |
| `STRIPE_CURRENCY` | `usd` | Payment currency |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |
| `FREECAD_CMD` | `auto` | Path to FreeCADCmd or `auto` |
| `EMAIL_VERIFICATION_REQUIRED` | `false` | Require email verification |
| `RATE_LIMIT_PER_MIN` | `30` | Auth attempts per IP per minute |

## API Endpoints

### Public
- `GET /api/health` — health check
- `GET /api/plans` — list credit packs
- `GET /api/share/{token}` — share link info
- `GET /api/share/{token}/download` — download shared file
- `GET /s/{token}` — share page with 3D preview
- `GET /e/{job_id}` — embed page

### Auth required
- `POST /api/auth/register` — create account
- `POST /api/auth/login` — login
- `GET /api/auth/me` — current user
- `POST /api/convert` — upload + convert file
- `GET /api/download/{uuid}` — download converted file
- `POST /api/share` — create share link
- `GET /api/jobs` — list user's conversions
- `POST /api/payments/checkout` — Stripe checkout
- `POST /api/forgot-password` — request password reset

### Admin required
- `GET /api/admin/stats` — dashboard stats
- `GET /api/admin/geo` — geo statistics
- `GET /api/admin/users` — user list
- `GET /api/admin/users/{id}` — user detail
- `POST /api/admin/users/{id}/credits` — adjust credits
- `GET /api/admin/jobs` — job list

## Tech Stack

- **Backend**: FastAPI, SQLAlchemy, python-jose, Pydantic
- **Database**: SQLite (dev) / PostgreSQL (prod)
- **Engine**: FreeCAD headless (OpenCASCADE) + pymeshlab
- **Frontend**: Vanilla JS, Three.js, Inter font
- **Payments**: Stripe
- **Deploy**: Railway (Docker)

## License

Proprietary. All rights reserved.
