"""MeshToStep — STL to STEP converter SaaS.
FastAPI + SQLite/PostgreSQL + FreeCAD headless.
"""
import os
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
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
from .routes_order import router as order_router
from .routes_print import router as print_router
from .routes_folders import router as folders_router
from .routes_sitemap import router as sitemap_router
from .routes_admin_launch import router as launch_router
from .routes_interstitial import router as interstitial_router
from .routes_stripe import router as stripe_router
from .routes_gallery import router as gallery_router
from .routes_reviews import router as reviews_router
from .routes_contact import router as contact_router
from .routes_inpost import router as inpost_router
from .routes_analytics import router as analytics_router
from .routes_partner import router as partner_router

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
    try:
        response = await call_next(request)
    except HTTPException as exc:
        # Przyjazny 404: budujemy świeży HTML (nie da się edytować body
        # HTTPException, bo pole response bywa _StreamingResponse bez .body).
        accept = (request.headers.get("accept") or "").lower()
        if "text/html" in accept and not request.url.path.startswith("/api"):
            from fastapi.responses import HTMLResponse
            html = f"""<!DOCTYPE html><html lang="pl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Nie znaleziono — 3dfile.link</title>
<style>body{{margin:0;font-family:Inter,system-ui,sans-serif;background:#f7f8fb;color:#0b1730;min-height:100vh;display:flex;align-items:center;justify-content:center}}
.c{{text-align:center;padding:40px;max-width:480px}} h1{{font-size:56px;margin:0 0 8px;color:#2B5CE6}}
p{{color:#5b6b86;line-height:1.6}} a{{display:inline-block;margin-top:18px;padding:11px 20px;border-radius:8px;background:#2B5CE6;color:#fff;text-decoration:none;font-weight:600}}
a:hover{{background:#1e45b8}}</style>
<!-- clarity-fallback -->
</head><body><div class="c"><h1>404</h1>
<p>Nie znaleziono strony <code>{request.url.path}</code>. Może link się zestarzał?</p>
<a href="/">← Wróć na stronę główną</a></div></body></html>"""
            headers = dict(getattr(exc, "headers", None) or {})
            # CSP nadal musi być — poza tym blokujemy ewentualny inline JS
            response = HTMLResponse(html, status_code=exc.status_code, headers=headers)
        else:
            raise
    csp = (
            "default-src 'self'; "
            # Google AdSense (Auto ads) + jego CMP (fundingchoicesmessages) dla ruchu z UE.
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cloud.umami.is "
            "https://pagead2.googlesyndication.com https://*.googlesyndication.com "
            "https://googleads.g.doubleclick.net https://securepubads.g.doubleclick.net "
            "https://tpc.googlesyndication.com https://adservice.google.com "
            "https://www.googletagservices.com https://fundingchoicesmessages.google.com "
            "https://www.googletagmanager.com https://*.googletagmanager.com "
            "https://*.google.com https://www.clarity.ms https://*.clarity.ms; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https:; "
            # bez connect-src beacony AdSense lecą w default-src 'self' i są blokowane
            "connect-src 'self' https://cloud.umami.is https://gateway.umami.is https://pagead2.googlesyndication.com https://*.googlesyndication.com "
            "https://googleads.g.doubleclick.net https://*.doubleclick.net "
            "https://adservice.google.com https://*.adtrafficquality.google "
            "https://*.google.com https://fundingchoicesmessages.google.com "
            "https://www.google-analytics.com https://*.google-analytics.com "
            "https://stats.g.doubleclick.net https://*.googletagmanager.com "
            "https://*.clarity.ms https://*.msn.com; "
            "frame-src 'self' https://googleads.g.doubleclick.net https://tpc.googlesyndication.com "
            "https://*.googlesyndication.com https://*.doubleclick.net https://www.google.com "
            "https://fundingchoicesmessages.google.com "
            "https://www.youtube.com https://www.youtube-nocookie.com https://www.openstreetmap.org "
            "https://www.googletagmanager.com; "
            "frame-ancestors 'self'; "
            "worker-src 'self' blob:; "
        )
    # Embed pages are meant for third-party iframes — lift frame-ancestors there
    if request.url.path.startswith("/e/"):
        csp = csp.replace("frame-ancestors 'self';", "frame-ancestors *;")
    response.headers["Content-Security-Policy"] = csp
    # ── dodatkowe security headers ──
    if not request.url.path.startswith("/e/"):
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(self), interest-cohort=()"
    if request.headers.get("x-forwarded-proto") == "https":
        try:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        except Exception:
            pass
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

# ── Microsoft Clarity (behavior analytics) ──────────────────────────
# Injected into <head> of every HTML response (site + server-rendered pages:
# /, /u/, /s/, /e/, /blog, /zamow, admin…). One place instead of per-file.
CLARITY_TAG = """<script type="text/javascript">
    (function(c,l,a,r,i,t,y){
        c[a]=c[a]||function(){(c[a].q=c[a].q||[]).push(arguments)};
        t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;
        y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);
    })(window, document, "clarity", "script", "ypigm7bngb");
</script>"""

# ── Google Tag Manager (GTM-PSGG68W2) ────────────────────────────────
# Wstrzykiwane tym samym middleware co Clarity: jedno miejsce zamiast
# 53 plikow HTML. Skrypt wchodzi w <head> jak najwyzej, noscript iframe
# tuz po <body> — inaczej GTM nie widzi ruchu z wylaczonym JavaScriptem.
GTM_ID = "GTM-PSGG68W2"
GTM_HEAD = """
<!-- Google Tag Manager -->
<script>(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
})(window,document,'script','dataLayer','GTM-PSGG68W2');</script>
<!-- End Google Tag Manager -->"""

GTM_BODY = """
<!-- Google Tag Manager (noscript) -->
<noscript><iframe src="https://www.googletagmanager.com/ns.html?id=GTM-PSGG68W2" height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>
<!-- End Google Tag Manager (noscript) -->"""

@app.middleware("http")
async def clarity_inject_middleware(request: Request, call_next):
    response = await call_next(request)
    try:
        ctype = response.headers.get("content-type", "")
        if "text/html" not in ctype:
            return response
        # StreamingResponse (np. HTML z handlera 404) nie ma atrybutu body —
        # BaseHTTPMiddleware pakaje odpowiedzi w _StreamingResponse (podklasę
        # Response), więc sprawdzamy body_iterator duck-typingiem, nie isinstance.
        # UWAGA: po spławieniu iteratora ORYGINALNA odpowiedź ma wypaloną
        # iterację — trzeba zwrócić zawsze nowy obiekt Response, inaczej
        # strony 200 wracają puste (len=0).
        consumed = False
        if hasattr(response, "body"):
            body = response.body
        elif hasattr(response, "body_iterator"):
            consumed = True
            chunks = []
            async for chunk in response.body_iterator:
                chunks.append(chunk if isinstance(chunk, bytes) else chunk.encode("utf-8"))
            body = b"".join(chunks)
        else:
            return response
        new_body = body
        if b"</head>" in body and b"clarity.ms" not in body:
            injected = body.replace(b"</head>", CLARITY_TAG.encode() + b"</head>", 1)
            if len(injected) != len(body):
                new_body = injected
        # GTM: skrypt do <head> (jak najwyzej), noscript iframe zaraz po <body>.
        # Identyfikator jest w jednym miejscu, wiec warunek "czy juz jest"
        # to prosty grep po GTM_ID — bez latania po 53 plikach HTML.
        if GTM_ID.encode() not in body:
            _gm = new_body
            if b"</head>" in _gm:
                _gm = _gm.replace(b"</head>", GTM_HEAD.encode() + b"</head>", 1)
            _bo = _gm.find(b"<body")
            if _bo != -1:
                _cut = _gm.find(b">", _bo)
                if _cut != -1:
                    _cut += 1
                    _gm = _gm[:_cut] + GTM_BODY.encode() + _gm[_cut:]
            if _gm != new_body:
                new_body = _gm
        if consumed or new_body is not body:
            from starlette.responses import Response as _Resp
            headers = dict(response.headers)
            headers.pop("content-length", None)  # inaczej: 2x Content-Length = malformed headers = 502
            return _Resp(content=new_body, status_code=response.status_code,
                         headers=headers, media_type=ctype.split(";")[0])
        return response
    except Exception as e:
        print(f"[clarity] {e}")
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
app.include_router(order_router)
app.include_router(print_router)
app.include_router(folders_router)
app.include_router(sitemap_router)
app.include_router(launch_router)
app.include_router(interstitial_router)
app.include_router(stripe_router)
app.include_router(gallery_router)
app.include_router(reviews_router)
app.include_router(contact_router)
app.include_router(inpost_router)
app.include_router(analytics_router)
app.include_router(partner_router)

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

@app.get("/platnosc", include_in_schema=False)
def payment_page():
    """Status płatności: success / pending / cancel / error (?status=&order=)."""
    from fastapi.responses import FileResponse
    return FileResponse(str(FRONTEND_DIR / "payment.html"))

@app.get("/admin", include_in_schema=False)
def admin_page():
    # JEDEN spójny panel: /admin serwuje admin.html = hosting (użytkownicy/pliki/stats/ads/geo/...)
    # ORAZ zakładki drukarni (Zamówienia/Cennik/Kody/Galeria/Recenzje/Raporty).
    # Koniec z 302 do /drukuje#admin — drukarnia to zakładki w tym samym interfejsie.
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

# ── Clean-URL aliases (no .html): /drukuje + /print → landing, /zamow → order page ──
@app.get("/drukuje", response_class=HTMLResponse, include_in_schema=False)
def drukuje_landing():
    from fastapi.responses import FileResponse
    return FileResponse(str(FRONTEND_DIR / "print.html"))

@app.get("/print", response_class=HTMLResponse, include_in_schema=False)
def print_landing():
    from fastapi.responses import FileResponse
    return FileResponse(str(FRONTEND_DIR / "print.html"))

@app.get("/zamow", response_class=HTMLResponse, include_in_schema=False)
def zamow_order():
    from fastapi.responses import FileResponse
    return FileResponse(str(FRONTEND_DIR / "order.html"))

# EN locales: same pages, JS forces language=EN (persisted) via injected snippet
_EN_INJECT = "<script>(function(){try{localStorage.setItem('mt_lang','en');}catch(e){}})();</script>"

@app.get("/en/print", response_class=HTMLResponse, include_in_schema=False)
def en_print_landing():
    from fastapi.responses import HTMLResponse
    html = (FRONTEND_DIR / "print.html").read_text(encoding="utf-8")
    html = html.replace("</head>", _EN_INJECT + "</head>", 1)
    return HTMLResponse(content=html)

@app.get("/en/order", response_class=HTMLResponse, include_in_schema=False)
def en_order_page():
    from fastapi.responses import HTMLResponse
    html = (FRONTEND_DIR / "order.html").read_text(encoding="utf-8")
    html = html.replace("</head>", _EN_INJECT + "</head>", 1)
    return HTMLResponse(content=html)

@app.get("/kontakt", response_class=HTMLResponse, include_in_schema=False)
def kontakt_page():
    from fastapi.responses import FileResponse
    return FileResponse(str(FRONTEND_DIR / "kontakt.html"))

@app.get("/projektowanie", response_class=HTMLResponse, include_in_schema=False)
def projektowanie_page():
    from fastapi.responses import FileResponse
    return FileResponse(str(FRONTEND_DIR / "projektowanie.html"))

@app.get("/konto", response_class=HTMLResponse, include_in_schema=False)
def konto_page():
    from fastapi.responses import FileResponse
    return FileResponse(str(FRONTEND_DIR / "konto.html"))

@app.get("/partner", response_class=HTMLResponse, include_in_schema=False)
def partner_page():
    from fastapi.responses import FileResponse
    return FileResponse(str(FRONTEND_DIR / "partner.html"))

@app.get("/en/partner", response_class=HTMLResponse, include_in_schema=False)
def en_partner_page():
    from fastapi.responses import HTMLResponse
    _en = "<script>(function(){try{localStorage.setItem('mt_lang','en');}catch(e){}})();</script>"
    html = (FRONTEND_DIR / "partner.html").read_text(encoding="utf-8")
    html = html.replace("</head>", _en + "</head>", 1)
    return HTMLResponse(content=html)

@app.get("/blog", response_class=HTMLResponse, include_in_schema=False)
@app.get("/blog/{slug}", response_class=HTMLResponse, include_in_schema=False)
def blog_page(slug: str = ""):
    from fastapi.responses import FileResponse
    if slug:
        name = slug if slug.endswith(".html") else slug + ".html"
        fp = FRONTEND_DIR / "blog" / name
        # ochrona przed path traversal
        if fp.is_file() and fp.resolve().parent == (FRONTEND_DIR / "blog").resolve():
            return FileResponse(str(fp))
        # nieznany artykul = PRAWDZIWE 404 (bez soft-404, Google to karze)
        raise HTTPException(status_code=404, detail="not found")
    return FileResponse(str(FRONTEND_DIR / "blog.html"))

# ── Przyjazny 404 dla ludzi (JSON zostaje dla /api/*) ───────────────
from starlette.exceptions import HTTPException as _StarHTTP
from fastapi.responses import HTMLResponse as _HTML

@app.exception_handler(_StarHTTP)
async def _friendly_404(request, exc):
    path = request.url.path
    if exc.status_code == 404 and not path.startswith(("/api/", "/js/", "/asset/", "/vendor/")):
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            return _HTML(
                "<!doctype html><html lang=pl><head><meta charset=utf-8>"
                "<meta name=viewport content='width=device-width,initial-scale=1'>"
                "<title>404 — nie znaleziono | 3dfile.link</title><style>"
                "body{font-family:Inter,system-ui,sans-serif;background:#0B1730;color:#fff;display:flex;"
                "align-items:center;justify-content:center;min-height:100vh;margin:0;text-align:center}"
                ".box{max-width:440px;padding:32px}h1{font-size:64px;margin:0;color:#2B5CE6}"
                "p{color:#9fb3d1;line-height:1.6}a{display:inline-block;margin-top:18px;padding:12px 22px;"
                "background:#2B5CE6;color:#fff;border-radius:10px;text-decoration:none;font-weight:600}"
                "code{background:#16294a;padding:2px 8px;border-radius:6px;font-size:12px}</style></head><body>"
                "<div class=box><h1>404</h1><h2 style='margin:6px 0'>Nic tu nie ma</h2>"
                "<p>Ten adres nie istnieje albo model był prywatny i wygasł.<br>"
                "Sprawdź link lub wróć na stronę główną.</p>"
                "<p><code>" + path.replace("<", "&lt;")[:80] + "</code></p>"
                "<a href='/'>← 3dfile.link — hosting i druk 3D</a></div></body></html>",
                status_code=404)
    from fastapi.exception_handlers import http_exception_handler
    return await http_exception_handler(request, exc)


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
            from .database import SessionLocal
            from .routes_analytics import purge_old_events
            old = cleanup_old_files()
            exp = cleanup_expired_shares()
            _db = SessionLocal()
            try:
                ev = purge_old_events(_db, 180)
            finally:
                _db.close()
            print(f"[3dfile] cleanup: {old} old files, {exp} expired shares, {ev} events")
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