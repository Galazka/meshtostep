"""MeshToStep — STL to STEP converter SaaS.
FastAPI + SQLite/PostgreSQL + FreeCAD headless.
"""
import os
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import init_db, SessionLocal
from .routes_auth import router as auth_router
from .routes_convert import router as convert_router
from .routes_admin import router as admin_router
from .routes_share import router as share_router
from .routes_ads import router as ads_router
from .routes_community import router as community_router
from .routes_comments import router as comments_router
from .routes_printer import router as printer_router
from .routes_folders import router as folders_router
from .routes_sitemap import router as sitemap_router
from .routes_interstitial import router as interstitial_router

app = FastAPI(title="3dfile.link", version="1.0.0")

# ── CORS (restrict in production) ───────────────────────────────────
# allow_credentials=True is INCOMPATIBLE with allow_origins=["*"] — browsers reject it.
# When ORIGINS="*" we disable credentials; otherwise use explicit list.
if settings.CORS_ORIGINS == "*":
    origins = ["*"]
    allow_creds = False
else:
    origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
    allow_creds = True
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=allow_creds,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── CSP middleware ──────────────────────────────────────────────────
@app.middleware("http")
async def csp_middleware(request: Request, call_next):
    response = await call_next(request)
    csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://pagead2.googlesyndication.com https://googleads.g.doubleclick.net https://tpc.googlesyndication.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https:; "
            "frame-src 'self' https://googleads.g.doubleclick.net https://tpc.googlesyndication.com https://www.youtube.com https://www.youtube-nocookie.com; "
            "frame-ancestors 'self'; "
            "worker-src 'self' blob:; "
        )
    # Embed pages are meant for third-party iframes — lift frame-ancestors there
    if request.url.path.startswith("/e/"):
        csp = csp.replace("frame-ancestors 'self';", "frame-ancestors *;")
    response.headers["Content-Security-Policy"] = csp
    # HTML, SW and app JS never cached — fresh UI + immediate updates (Cloudflare respects no-store).
    # /vendor (three.js) stays cached — stable, heavy.
    _p = request.url.path
    if _p == "/" or _p.endswith(".html") or _p == "/sw.js" or (_p.endswith(".js") and "/vendor/" not in _p):
        response.headers["Cache-Control"] = "no-store"
    # HTTPS redirect (Railway terminates TLS, X-Forwarded-Proto = https)
    if request.headers.get("x-forwarded-proto") == "http":
        url = str(request.url).replace("http://", "https://", 1)
        return RedirectResponse(url, status_code=301)
    return response

# ── Geo logging middleware ──────────────────────────────────────────
@app.middleware("http")
async def geo_log_middleware(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/api/") or path.startswith("/s/") or path.startswith("/e/"):
        try:
            from . import models
            from .auth import get_current_user
            db = SessionLocal()
            try:
                user = None
                auth_header = request.headers.get("authorization", "")
                if auth_header.startswith("Bearer "):
                    try:
                        from jose import jwt
                        from .config import settings as _settings
                        token = auth_header[7:]
                        payload = jwt.decode(token, _settings.SECRET_KEY, algorithms=["HS256"])
                        uid = int(payload.get("sub"))
                        user = db.query(models.User).filter(models.User.id == uid).first()
                    except Exception:
                        pass
                if not user:
                    geo = models.GeoLog(ip_address=request.client.host if request.client else "unknown", user_id=None)
                else:
                    geo = models.GeoLog(ip_address=request.client.host if request.client else "unknown", user_id=user.id)
                db.add(geo); db.commit()
            finally:
                db.close()
        except Exception as e:
            print(f"[geo] {e}")
    return response

# ── Register routers ────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(convert_router)
app.include_router(admin_router)
app.include_router(share_router)
app.include_router(ads_router)
app.include_router(community_router)
app.include_router(comments_router)
app.include_router(printer_router)
app.include_router(folders_router)
app.include_router(sitemap_router)
app.include_router(interstitial_router)

@app.get("/api/health")
def health():
    from .engine import find_freecad
    try:
        freecad = find_freecad()
        fc_ok = True
    except FileNotFoundError:
        fc_ok = False
        freecad = None
    # DB check
    try:
        db = SessionLocal()
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        db.close()
        db_ok = True
    except Exception:
        db_ok = False
    return {
        "ok": fc_ok and db_ok,
        "freecad": fc_ok,
        "freecad_path": freecad,
        "database": db_ok,
        "app": "3dfile.link v1.1",
    }

# ── Serve frontend ──────────────────────────────────────────────────
FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend"

@app.get("/admin", include_in_schema=False)
def admin_page():
    from fastapi.responses import FileResponse
    return FileResponse(str(FRONTEND_DIR / "admin.html"))

# Redirect legacy routes BEFORE mount (mount shadows them)
@app.get("/prywatnosc", include_in_schema=False)
def privy_redirect():
    return RedirectResponse(url="/prywatnosc.html", status_code=301)

@app.get("/regulamin", include_in_schema=False)
def regul_redirect():
    return RedirectResponse(url="/regulamin.html", status_code=301)

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    from fastapi.responses import FileResponse
    return FileResponse(str(FRONTEND_DIR / "logo.png"), media_type="image/png")

if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

# ── Startup ─────────────────────────────────────────────────────────
_cleanup_running = False
_backup_running = False

def _backup_loop():
    global _backup_running
    time.sleep(600)  # let boot finish
    while True:
        if _backup_running:
            time.sleep(600)
            continue
        _backup_running = True
        try:
            from .backup import backup_db
            backup_db()
        except Exception as e:
            print(f"[3dfile] backup error: {e}")
        finally:
            _backup_running = False
        time.sleep(24 * 3600)

def _cleanup_loop():
    global _cleanup_running
    import threading
    time.sleep(300)  # let boot finish, then catch up once
    while True:
        if _cleanup_running:
            time.sleep(600)
            continue
        _cleanup_running = True
        try:
            from .cleanup import cleanup_old_files, cleanup_expired_shares
            old = cleanup_old_files()
            exp = cleanup_expired_shares()
            print(f"[3dfile] cleanup: {old} old files, {exp} expired shares")
        except Exception as e:
            print(f"[3dfile] cleanup error: {e}")
        finally:
            _cleanup_running = False
        time.sleep(6 * 3600)

@app.on_event("startup")
def startup():
    os.makedirs(settings.DATA_DIR, exist_ok=True)
    init_db()
    import threading
    t = threading.Thread(target=_cleanup_loop, daemon=True)
    t.start()
    b = threading.Thread(target=_backup_loop, daemon=True)
    b.start()
    print("[3dfile] DB ready, cleanup+backup schedulers on, app started")