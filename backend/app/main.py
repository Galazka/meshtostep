"""MeshToStep — STL to STEP converter SaaS.
FastAPI + SQLite/PostgreSQL + FreeCAD headless.
"""
import os
import time
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
from .routes_payments import router as payments_router

app = FastAPI(title="MeshToStep", version="1.0.0")

# ── CORS (restrict in production) ───────────────────────────────────
origins = settings.CORS_ORIGINS.split(",") if settings.CORS_ORIGINS != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Security headers middleware ─────────────────────────────────────
@app.middleware("http")
async def security_middleware(request: Request, call_next):
    response = await call_next(request)

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # CSP — allow Three.js from unpkg
    csp = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://unpkg.com https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https:; "
        "connect-src 'self'; "
        "frame-ancestors 'self'; "
        "worker-src 'self' blob:; "
    )
    response.headers["Content-Security-Policy"] = csp

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

                ip = request.headers.get("x-forwarded-for", "")
                if ip:
                    ip = ip.split(",")[0].strip()
                else:
                    ip = request.client.host if request.client else "unknown"

                geo = models.GeoLog(
                    user_id=user.id if user else None,
                    ip_address=ip,
                    user_agent=(request.headers.get("user-agent") or "")[:500],
                    endpoint=path,
                    country=None,
                    city=None,
                )
                db.add(geo)
                db.commit()
            except Exception:
                pass
            finally:
                db.close()
        except Exception:
            pass

    return response


# ── Register routers ────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(convert_router)
app.include_router(admin_router)
app.include_router(share_router)
app.include_router(payments_router)


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
        db.execute("SELECT 1" if hasattr(db, 'execute') else None)
        db.close()
        db_ok = True
    except Exception:
        db_ok = False

    return {
        "ok": True,
        "freecad": fc_ok,
        "freecad_path": freecad,
        "database": db_ok,
        "app": "MeshToStep v1.1",
    }


# ── Serve frontend ──────────────────────────────────────────────────
FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


# ── Startup ─────────────────────────────────────────────────────────
@app.on_event("startup")
def startup():
    os.makedirs(settings.DATA_DIR, exist_ok=True)
    init_db()
    print("[MeshToStep] DB ready, app started")
    print(f"[MeshToStep] FreeCAD: ", end="")
    try:
        from .engine import find_freecad
        print(find_freecad())
    except FileNotFoundError:
        print("NOT FOUND — conversions will fail")
    print(f"[MeshToStep] Database: {settings.DATABASE_URL[:40]}...")

    # Run cleanup on startup
    try:
        from .cleanup import cleanup_old_files, cleanup_expired_shares
        old = cleanup_old_files(days=30)
        expired = cleanup_expired_shares()
        if old or expired:
            print(f"[MeshToStep] Cleanup: {old} old jobs, {expired} expired shares")
    except Exception as e:
        print(f"[MeshToStep] Cleanup error: {e}")
