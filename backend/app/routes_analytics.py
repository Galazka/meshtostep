"""Analityka wlasna 3dfile.link - bez cookies, bez zewnetrznych skryptow.

POST /api/ev                        - przyjmij event (publiczny, rate-limit per IP)
GET  /api/admin/analytics/summary   - lejek / dni / sciezki / zrodla (admin)
GET  /api/admin/analytics/live      - ostatnie eventy (admin)
POST /api/admin/analytics/purge     - usun eventy starsze niz N dni (admin)

Zero cookies: identyfikacja przez losowy session_id z sessionStorage + hash IP.
"""
import hashlib
import json
import re
import time
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Request
from jose import jwt
from pydantic import BaseModel
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from . import models
from .config import settings
from .database import get_db
from .auth import require_admin, ALGORITHM

router = APIRouter()

# dozwolone nazwy eventow (biala lista - reszta odrzucana)
ALLOWED = {
    "pageview", "upload_start", "convert_ok", "download_click", "share_click",
    "click_print", "signup", "login", "order_start", "order_paid",
    "contact_send", "search", "model_view", "outbound", "partner_apply",
}

# kolejnosc lejka (do panelu admina)
FUNNEL = [
    ("pageview", "Wejścia"),
    ("upload_start", "Start uploadu"),
    ("convert_ok", "Konwersja OK"),
    ("click_print", "Klik 'Wydrukuj u nas'"),
    ("order_start", "Zamówienie rozpoczęte"),
    ("order_paid", "Zamówienie opłacone"),
]

BOT_RE = re.compile(
    r"bot|crawl|spider|slurp|bingpreview|headless|lighthouse|"
    r"python-requests|python-urllib|curl/|wget|monitor|uptime|semrush|ahrefs|"
    r"facebookexternalhit|whatsapp|telegrambot|preview",
    re.I,
)

_rl = {}          # ip_hash -> [timestamps]
RL_MAX = 240      # eventow na godzine per IP
RL_WINDOW = 3600


def _client_ip(request: Request) -> str:
    xff = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if xff:
        return xff
    cf = (request.headers.get("cf-connecting-ip") or "").strip()
    if cf:
        return cf
    return request.client.host if request.client else ""


def _ip_hash(ip: str) -> str:
    salt = getattr(settings, "SECRET_KEY", "") or "3dfile"
    return hashlib.sha256((ip + "|" + salt).encode("utf-8")).hexdigest()[:32]


def _device(ua: str) -> str:
    if not ua:
        return "unknown"
    if BOT_RE.search(ua):
        return "bot"
    if re.search(r"ipad|tablet|android(?!.*mobile)|kindle", ua, re.I):
        return "tablet"
    if re.search(r"mobile|iphone|ipod|android", ua, re.I):
        return "mobile"
    return "desktop"


def _rate_ok(ip_hash: str) -> bool:
    now = time.time()
    arr = [t for t in (_rl.get(ip_hash) or []) if now - t < RL_WINDOW]
    if len(arr) >= RL_MAX:
        _rl[ip_hash] = arr
        return False
    arr.append(now)
    _rl[ip_hash] = arr
    if len(_rl) > 5000:  # sprzatanie starego slownika
        dead = [k for k, v in list(_rl.items()) if not [t for t in v if now - t < RL_WINDOW]]
        for k in dead[:1000]:
            _rl.pop(k, None)
    return True


def _uid_from_request(request: Request) -> Optional[int]:
    """user_id z naglowka Bearer bez zaleznosci FastAPI (funckja sync).
    Niepoprawny/brak tokenu -> None (anonim)."""
    try:
        h = (request.headers.get("authorization") or "").strip()
        if not h.lower().startswith("bearer "):
            return None
        payload = jwt.decode(h[7:].strip(), settings.SECRET_KEY,
                             algorithms=[ALGORITHM])
        return int(payload.get("sub"))
    except Exception:
        return None


def _ref_domain(ref: str) -> str:
    if not ref:
        return "(bezposrednie)"
    m = re.match(r"^https?://([^/]+)", (ref or "").strip(), re.I)
    host = (m.group(1) if m else (ref or "").strip())[:120].lower()
    return host.replace("www.", "")


def _clean_path(p: str) -> str:
    p = (p or "/")[:255].split("?")[0].split("#")[0]
    return p or "/"


# ── publiczny zbieracz ──────────────────────────────────────────────
class EvIn(BaseModel):
    name: str
    path: Optional[str] = ""
    ref: Optional[str] = ""
    sid: Optional[str] = ""
    meta: Optional[dict] = None


@router.post("/api/ev")
def collect(req: EvIn, request: Request, db: Session = Depends(get_db)):
    name = (req.name or "").strip()[:64]
    if name not in ALLOWED:
        return {"ok": False, "reason": "unknown_event"}
    ua = (request.headers.get("user-agent") or "")[:300]
    if BOT_RE.search(ua):
        return {"ok": False, "reason": "bot"}
    iph = _ip_hash(_client_ip(request))
    if not _rate_ok(iph):
        return {"ok": False, "reason": "rate_limited"}
    meta = ""
    if req.meta:
        try:
            meta = json.dumps(req.meta, ensure_ascii=False)[:1000]
        except Exception:
            meta = ""
    uid = _uid_from_request(request)
    ev = models.PageEvent(
        name=name,
        path=_clean_path(req.path),
        referrer=(req.ref or "")[:255],
        session_id=(req.sid or "")[:64],
        ip_hash=iph,
        user_id=uid,
        country=(request.headers.get("cf-ipcountry") or "")[:8],
        device=_device(ua),
        meta=meta,
    )
    db.add(ev)
    db.commit()
    return {"ok": True}


# ── panel admina ────────────────────────────────────────────────────
@router.get("/api/admin/analytics/summary")
def summary(days: int = 7, admin: models.User = Depends(require_admin),
            db: Session = Depends(get_db)):
    days = max(1, min(int(days or 7), 180))
    since = datetime.utcnow() - timedelta(days=days)

    base = db.query(models.PageEvent).filter(models.PageEvent.created_at >= since)
    total_events = base.count()
    pageviews = base.filter(models.PageEvent.name == "pageview").count()
    sessions = db.query(func.count(func.distinct(models.PageEvent.session_id)))         .filter(models.PageEvent.created_at >= since)         .filter(models.PageEvent.session_id.isnot(None)).scalar() or 0
    uniques = db.query(func.count(func.distinct(models.PageEvent.ip_hash)))         .filter(models.PageEvent.created_at >= since).scalar() or 0

    day_col = func.date(models.PageEvent.created_at)
    rows = db.query(
        day_col.label("d"),
        func.count(models.PageEvent.id),
        func.sum(case((models.PageEvent.name == "pageview", 1), else_=0)),
    ).filter(models.PageEvent.created_at >= since).group_by(day_col).order_by(day_col).all()
    by_day = [{"date": str(d), "events": int(c or 0), "pageviews": int(pv or 0)}
              for d, c, pv in rows]

    funnel = []
    prev = None
    for key, label in FUNNEL:
        cnt = base.filter(models.PageEvent.name == key).count()
        funnel.append({
            "step": key,
            "label": label,
            "count": cnt,
            "of_pageviews": round(100.0 * cnt / pageviews, 1) if pageviews else 0.0,
            "of_prev": round(100.0 * cnt / prev, 1) if prev else None,
        })
        if cnt:
            prev = cnt

    paths = db.query(models.PageEvent.path, func.count(models.PageEvent.id).label("n"))         .filter(models.PageEvent.created_at >= since,
                models.PageEvent.name == "pageview")         .group_by(models.PageEvent.path).order_by(func.count(models.PageEvent.id).desc()).limit(15).all()
    top_paths = [{"path": p or "/", "views": int(n)} for p, n in paths]

    refs = db.query(models.PageEvent.referrer, func.count(models.PageEvent.id))         .filter(models.PageEvent.created_at >= since,
                models.PageEvent.name == "pageview")         .group_by(models.PageEvent.referrer).all()
    agg = {}
    for r, n in refs:
        d = _ref_domain(r)
        agg[d] = agg.get(d, 0) + int(n)
    top_refs = [{"source": k, "views": v}
                for k, v in sorted(agg.items(), key=lambda x: -x[1])[:15]]

    dev = db.query(models.PageEvent.device, func.count(models.PageEvent.id))         .filter(models.PageEvent.created_at >= since).group_by(models.PageEvent.device).all()
    devices = [{"device": d or "unknown", "events": int(n)} for d, n in dev]

    ctry = db.query(models.PageEvent.country, func.count(models.PageEvent.id))         .filter(models.PageEvent.created_at >= since).group_by(models.PageEvent.country).all()
    countries = sorted(([{"country": c or "??", "events": int(n)} for c, n in ctry]),
                       key=lambda x: -x["events"])[:15]

    ev_names = db.query(models.PageEvent.name, func.count(models.PageEvent.id))         .filter(models.PageEvent.created_at >= since).group_by(models.PageEvent.name).all()
    events = sorted(([{"name": n, "count": int(c)} for n, c in ev_names]),
                    key=lambda x: -x["count"])

    last = db.query(func.max(models.PageEvent.created_at)).scalar()

    return {
        "ok": True, "days": days,
        "totals": {"events": total_events, "pageviews": pageviews,
                   "sessions": int(sessions), "visitors": int(uniques)},
        "by_day": by_day, "funnel": funnel, "top_paths": top_paths,
        "top_refs": top_refs, "devices": devices, "countries": countries,
        "events": events,
        "last_event": str(last) if last else None,
    }


@router.get("/api/admin/analytics/live")
def live(limit: int = 60, admin: models.User = Depends(require_admin),
         db: Session = Depends(get_db)):
    limit = max(1, min(int(limit or 60), 300))
    rows = db.query(models.PageEvent).order_by(models.PageEvent.id.desc()).limit(limit).all()
    return {"ok": True, "items": [{
        "id": e.id,
        "name": e.name,
        "path": e.path,
        "referrer": _ref_domain(e.referrer) if e.referrer else "",
        "session": (e.session_id or "")[:8],
        "country": e.country or "",
        "device": e.device or "",
        "user_id": e.user_id,
        "meta": e.meta or "",
        "at": str(e.created_at),
    } for e in rows]}


@router.post("/api/admin/analytics/purge")
def purge(days: int = 180, admin: models.User = Depends(require_admin),
          db: Session = Depends(get_db)):
    return {"ok": True, "deleted": purge_old_events(db, days)}


def purge_old_events(db: Session, days: int = 180) -> int:
    """Usun eventy starsze niz N dni. Wolane tez z pętli cleanupu."""
    cutoff = datetime.utcnow() - timedelta(days=max(1, int(days)))
    n = db.query(models.PageEvent).filter(models.PageEvent.created_at < cutoff).delete()
    db.commit()
    return int(n or 0)


# ── zdarzenia serwerowe (lejek: order_start / order_paid) ───────────
def record(db: Session, name: str, request: Request = None, meta: dict = None,
           path: str = "/", user_id: int = None):
    """Zapis eventu po stronie serwera (bez JS, bez cookie).
    UA bota -> odrzucone. Blad zapisu nigdy nie psuje zamowienia."""
    try:
        if name not in ALLOWED:
            return None
        ua = ""
        iph = "srv"
        country = ""
        if request is not None:
            ua = (request.headers.get("user-agent") or "")[:300]
            if BOT_RE.search(ua):
                return None
            try:
                iph = _ip_hash(_client_ip(request))
                country = (request.headers.get("cf-ipcountry") or "")[:8]
            except Exception:
                iph = "srv"
        m = ""
        if meta:
            try:
                m = json.dumps(meta, ensure_ascii=False)[:1000]
            except Exception:
                m = ""
        ev = models.PageEvent(
            name=name, path=_clean_path(path), referrer="", session_id="",
            ip_hash=iph, user_id=user_id, country=country,
            device=_device(ua) if ua else "server", meta=m,
        )
        db.add(ev)
        db.commit()
        return ev.id
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return None


def record_paid(db: Session, order, request: Request = None, path: str = "/platnosc"):
    """order_paid dokladnie raz na zamowienie (dedupe po meta.order_id)."""
    try:
        oid = int(order.id)
    except Exception:
        return None
    try:
        dup = db.query(models.PageEvent.id).filter(
            models.PageEvent.name == "order_paid",
            models.PageEvent.meta.like(f'%"order_id": {oid}%'),
        ).first()
        if dup:
            return None
    except Exception:
        pass
    return record(db, "order_paid", request, {
        "order_id": oid,
        "total": float(getattr(order, "total", 0) or 0),
        "currency": (getattr(order, "currency", None) or "PLN"),
        "method": (getattr(order, "payment_method", None) or ""),
    }, path=path)
