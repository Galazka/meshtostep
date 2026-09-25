"""Sieć partnerska druku 3D — zbieranie leadów (lista oczekujących).

Publiczne:
  POST /api/partner/apply     — zapis do sieci partnerskiej (formularz z /partner)
  GET  /api/partner/stats     — licznik: ile zgłoszeń w kolejce (social proof)

Admin:
  GET   /api/admin/partners             — lista zgłoszeń (filtry: status, q)
  PATCH /api/admin/partners/{id}        — status/notatki/scoring
  GET   /api/admin/partners/export.csv  — eksport do arkusza
"""
import csv
import io
import re
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import models
from .auth import require_admin
from .config import settings
from .database import get_db
from .mail import send_mail
from .routes_analytics import record

router = APIRouter()

# Statusy — JEDEN zestaw (backend i admin). Poziomy progresu leada.
STATUSES = ("new", "waiting", "vetted", "active", "rejected")
ACTIVE_STATUSES = ("new", "waiting", "vetted", "active")

DEFAULT_PARTNER_TARGET = 20
DEFAULT_PARTNER_PROGRESS = 18


def _notify_email() -> str:
    return (getattr(settings, "ADMIN_EMAIL_PRINTER", "") or "tomekgalazka@gmail.com").strip()


def _h(s) -> str:
    return (str(s or "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _norm_website(s) -> str:
    """Normalizuje adres WWW: dodaje https:// gdy brak i przycina do 200 znaków."""
    s = (s or "").strip()
    if not s:
        return None
    if not re.match(r"^https?://", s, re.I):
        s = "https://" + s
    return s[:200]


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")

# ── prosty rate-limit w pamięci (max 3 zgłoszenia / 10 min / IP) ──
_rl: dict = {}


def _rate_ok(key: str, limit: int = 3, window: int = 600) -> bool:
    now = datetime.utcnow()
    hits = [t for t in _rl.get(key, []) if (now - t).total_seconds() < window]
    if len(hits) >= limit:
        _rl[key] = hits
        return False
    hits.append(now)
    _rl[key] = hits
    if len(_rl) > 5000:                     # sprzątanie starego klucza
        for k in [k for k, v in list(_rl.items())
                  if not any((now - t).total_seconds() < window for t in v)]:
            _rl.pop(k, None)
    return True


def _ip_hash(request: Request) -> str:
    try:
        ip = request.headers.get("cf-connecting-ip") or (request.client.host if request.client else "")
        import hashlib
        return hashlib.sha256((ip + "|3dfile-partner").encode()).hexdigest()[:32]
    except Exception:
        return ""


def _score(lead) -> int:
    """Ranking zgłoszenia — im pełniejszy warsztat, tym wyżej."""
    pts = 0
    if lead.phone: pts += 3
    if lead.city: pts += 2
    if lead.website: pts += 1
    if lead.printers: pts += 3
    if (lead.count_printers or 0) >= 2: pts += 3
    if (lead.count_printers or 0) >= 4: pts += 2
    if lead.build_volume: pts += 1
    n_mat = len([m for m in (lead.materials or "").split(",") if m.strip()])
    if n_mat >= 2: pts += 2
    if n_mat >= 4: pts += 1
    if lead.monthly_capacity: pts += 2
    if lead.has_jdg: pts += 4          # JDG = faktury/podwykonawstwo
    if lead.offer_shipping: pts += 2
    if lead.message and len(lead.message) > 80: pts += 2
    return pts


def _queue_count(db: Session) -> int:
    return (db.query(models.PartnerLead)
            .filter(models.PartnerLead.status.in_(ACTIVE_STATUSES))
            .count())


class PartnerApply(BaseModel):
    company: str
    email: str
    contact_name: str = None
    phone: str = None
    city: str = None
    region: str = None
    website: str = None
    printers: str = None
    count_printers: int = None
    build_volume: str = None
    materials: list = None
    monthly_capacity: str = None
    has_jdg: bool = False
    offer_shipping: bool = False
    message: str = None
    consent: bool = False
    hp: str = ""                       # honeypot — musi zostać pusty
    source: str = "partner_landing"


@router.post("/api/partner/apply")
def partner_apply(req: PartnerApply, request: Request, db: Session = Depends(get_db)):
    if req.hp:
        return {"ok": True, "position": 0, "silent": True}   # bot — cicho udajemy sukces

    company = (req.company or "").strip()[:160]
    email = (req.email or "").strip().lower()[:200]
    if len(company) < 2:
        raise HTTPException(400, "Podaj nazwę pracowni / firmy")
    if not _EMAIL_RE.match(email):
        raise HTTPException(400, "Podaj poprawny adres email")
    if not req.consent:
        raise HTTPException(400, "Potrzebujemy zgody na kontakt w sprawie sieci partnerskiej")

    iph = _ip_hash(request)
    if iph and not _rate_ok(iph):
        raise HTTPException(429, "Zbyt wiele zgłoszeń — spróbuj ponownie za kilka minut")

    materials = ",".join([str(m).strip()[:30] for m in (req.materials or []) if str(m).strip()])[:300]

    lead = db.query(models.PartnerLead).filter(models.PartnerLead.email == email).first()
    already = bool(lead)
    if not lead:
        lead = models.PartnerLead(email=email, created_at=datetime.utcnow())
        db.add(lead)

    lead.company = company
    lead.contact_name = (req.contact_name or "").strip()[:120] or None
    lead.phone = (req.phone or "").strip()[:40] or None
    lead.city = (req.city or "").strip()[:120] or None
    lead.region = (req.region or "").strip()[:80] or None
    lead.website = _norm_website(req.website)
    lead.printers = (req.printers or "").strip()[:300] or None
    lead.count_printers = req.count_printers if (req.count_printers or 0) > 0 else None
    lead.build_volume = (req.build_volume or "").strip()[:80] or None
    lead.materials = materials or None
    lead.monthly_capacity = (req.monthly_capacity or "").strip()[:80] or None
    lead.has_jdg = bool(req.has_jdg)
    lead.offer_shipping = bool(req.offer_shipping)
    lead.message = (req.message or "").strip()[:4000] or None
    lead.consent = True
    lead.source = (req.source or "partner_landing")[:40]
    lead.ip_hash = iph or None
    lead.updated_at = datetime.utcnow()
    if lead.status in (None, ""):
        lead.status = "new"
    lead.score = _score(lead)

    db.commit()
    db.refresh(lead)

    position = _queue_count(db)
    record(db, "partner_apply", request=request, path="/partner",
           meta={"city": lead.city, "jdg": lead.has_jdg, "printers": lead.count_printers})

    # mail do Toma (nie blokuje odpowiedzi na błąd maila)
    try:
        mats = (lead.materials or "—").replace(",", ", ")
        body = (
            "<h2>Nowe zgłoszenie do sieci partnerskiej druku 3D</h2>"
            f"<p><b>Pracownia:</b> {_h(lead.company)}</p>"
            f"<p><b>Osoba:</b> {_h(lead.contact_name or '—')}</p>"
            f"<p><b>Email:</b> {_h(lead.email)}</p>"
            f"<p><b>Telefon:</b> {_h(lead.phone or '—')}</p>"
            f"<p><b>Lokalizacja:</b> {_h(lead.city or '—')} {_h(lead.region or '')}</p>"
            f"<p><b>WWW:</b> {_h(lead.website or '—')}</p>"
            f"<p><b>Drukarki:</b> {_h(lead.printers or '—')} "
            f"({_h(lead.count_printers or '—')} szt.)</p>"
            f"<p><b>Pole robocze:</b> {_h(lead.build_volume or '—')}</p>"
            f"<p><b>Materiały:</b> {_h(mats)}</p>"
            f"<p><b>Wolumen:</b> {_h(lead.monthly_capacity or '—')}</p>"
            f"<p><b>JDG / faktury:</b> {'tak' if lead.has_jdg else 'nie'} · "
            f"<b>Wysyłka:</b> {'tak' if lead.offer_shipping else 'nie'}</p>"
            f"<p><b>Wiadomość:</b><br>{_h(lead.message or '—').replace(chr(10), '<br>')}</p>"
            f"<p style='color:#64748b;font-size:12px'>Scoring: <b>{lead.score}</b> · "
            f"Pozycja w kolejce: <b>{position}</b> · ID: {lead.id}</p>"
        )
        subj = ("[3dfile partner] " + ("POWTÓRKA — " if already else "")
                + f"{lead.company} ({lead.city or 'brak miasta'})")
        send_mail(_notify_email(), subj, body)
    except Exception:
        pass

    # potwierdzenie do zgłaszającego — "jesteś na liście, odezwiemy się"
    if not already:
        try:
            ack_body = (
                "<h2>Dziękujemy za zgłoszenie do sieci partnerskiej 3dfile.link</h2>"
                "<p>Twoje zgłoszenie dotarło. Jesteś na liście oczekujących na "
                "dostęp do zamówień z naszej sieci partnerskiej druku 3D.</p>"
                f"<p><b>Zgłoszona pracownia:</b> {_h(lead.company)}</p>"
                "<p>Jak tylko zwolnimy miejsce w sieci — lub będziemy mieć pierwsze "
                "zamówienia w Twojej okolicy — napiszemy na ten adres email.</p>"
                "<p style='color:#64748b;font-size:12px'>Pozdrawiamy,<br>"
                "zespół <a href='https://3dfile.link'>3dfile.link</a></p>"
            )
            send_mail(lead.email, "Zgłoszenie przyjęte — sieć partnerska 3dfile.link", ack_body)
        except Exception:
            pass

    return {"ok": True, "position": position, "score": lead.score, "already": already}


@router.get("/api/partner/stats")
def partner_stats(db: Session = Depends(get_db)):
    waiting = _queue_count(db)
    target_v = int(models.SiteSetting.get(db, "partner_target", DEFAULT_PARTNER_TARGET))
    progress_v = int(models.SiteSetting.get(db, "partner_display", DEFAULT_PARTNER_PROGRESS))
    return {"ok": True, "waiting": waiting, "target": target_v,
            "progress": progress_v,
            "spots_left": max(0, target_v - progress_v)}


# ── ADMIN ────────────────────────────────────────────────────────────

def _lead_row(lead) -> dict:
    return {
        "id": lead.id,
        "company": lead.company,
        "contact_name": lead.contact_name,
        "email": lead.email,
        "phone": lead.phone,
        "city": lead.city,
        "region": lead.region,
        "website": lead.website,
        "printers": lead.printers,
        "count_printers": lead.count_printers,
        "build_volume": lead.build_volume,
        "materials": lead.materials,
        "monthly_capacity": lead.monthly_capacity,
        "has_jdg": bool(lead.has_jdg),
        "offer_shipping": bool(lead.offer_shipping),
        "message": lead.message,
        "status": lead.status or "new",
        "notes": lead.notes,
        "score": lead.score or 0,
        "source": lead.source,
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
        "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
    }


@router.get("/api/admin/partners")
def admin_partners_list(status: str = None, q: str = None, limit: int = 200,
                        admin=Depends(require_admin), db: Session = Depends(get_db)):
    query = db.query(models.PartnerLead)
    if status and status in STATUSES:
        query = query.filter(models.PartnerLead.status == status)
    if q:
        like = f"%{q.strip()[:80]}%"
        query = query.filter(
            models.PartnerLead.company.ilike(like) |
            models.PartnerLead.email.ilike(like) |
            models.PartnerLead.city.ilike(like)
        )
    rows = (query.order_by(models.PartnerLead.score.desc(),
                           models.PartnerLead.created_at.desc())
            .limit(max(1, min(limit, 1000))).all())
    counts = {}
    for st in STATUSES:
        counts[st] = db.query(models.PartnerLead).filter(models.PartnerLead.status == st).count()
    target_v = int(models.SiteSetting.get(db, "partner_target", DEFAULT_PARTNER_TARGET))
    progress_v = int(models.SiteSetting.get(db, "partner_display", DEFAULT_PARTNER_PROGRESS))
    return {"ok": True, "items": [_lead_row(r) for r in rows],
            "counts": counts, "target": target_v, "progress": progress_v,
            "total": sum(counts.values())}


class PartnerSettings(BaseModel):
    target: int = None
    progress: int = None


@router.post("/api/admin/partners/settings")
def admin_partner_settings(body: PartnerSettings,
                           admin=Depends(require_admin), db: Session = Depends(get_db)):
    if body.target is not None:
        target_v = max(1, min(int(body.target), 100000))
        models.SiteSetting.set(db, "partner_target", target_v)
    if body.progress is not None:
        progress_v = max(0, min(int(body.progress), 100000))
        models.SiteSetting.set(db, "partner_display", progress_v)
    return {"ok": True,
            "target": int(models.SiteSetting.get(db, "partner_target", DEFAULT_PARTNER_TARGET)),
            "progress": int(models.SiteSetting.get(db, "partner_display", DEFAULT_PARTNER_PROGRESS))}


class PartnerPatch(BaseModel):
    status: str = None
    notes: str = None


@router.patch("/api/admin/partners/{lead_id}")
def admin_partner_patch(lead_id: int, body: PartnerPatch,
                        admin=Depends(require_admin), db: Session = Depends(get_db)):
    lead = db.query(models.PartnerLead).filter(models.PartnerLead.id == lead_id).first()
    if not lead:
        raise HTTPException(404, "Zgłoszenie nie istnieje")
    if body.status:
        st = body.status.strip().lower()
        if st not in STATUSES:
            raise HTTPException(400, f"Status musi być jednym z: {', '.join(STATUSES)}")
        lead.status = st
    if body.notes is not None:
        lead.notes = body.notes.strip()[:4000] or None
    lead.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "item": _lead_row(lead)}


@router.get("/api/admin/partners/export.csv")
def admin_partners_csv(admin=Depends(require_admin), db: Session = Depends(get_db)):
    rows = (db.query(models.PartnerLead)
            .order_by(models.PartnerLead.score.desc(),
                      models.PartnerLead.created_at.desc()).all())
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["ID", "Data", "Status", "Scoring", "Pracownia", "Osoba", "Email", "Telefon",
                "Miasto", "Region", "WWW", "Drukarki", "Szt.", "Pole robocze", "Materiały",
                "Wolumen", "JDG", "Wysyłka", "Wiadomość", "Notatki"])
    for r in rows:
        w.writerow([
            r.id,
            r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
            r.status or "new", r.score or 0, r.company, r.contact_name or "", r.email,
            r.phone or "", r.city or "", r.region or "", r.website or "",
            r.printers or "", r.count_printers or "", r.build_volume or "",
            (r.materials or "").replace(",", ", "), r.monthly_capacity or "",
            "tak" if r.has_jdg else "nie", "tak" if r.offer_shipping else "nie",
            (r.message or "").replace("\n", " "), (r.notes or "").replace("\n", " "),
        ])
    data = "\ufeff" + buf.getvalue()          # BOM — Excel + polskie znaki
    return StreamingResponse(
        iter([data]), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="partnerzy-3dfile.csv"'})
