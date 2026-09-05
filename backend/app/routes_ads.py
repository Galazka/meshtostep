"""Ad slots routes — public slots + admin CRUD + retention extend."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from . import models
from .auth import get_current_user, require_admin
from .database import get_db

router = APIRouter(prefix="/api/ads", tags=["ads"])


# ── Public: get active slots ────────────────────────────────────────
@router.get("/slots")
def get_slots(db: Session = Depends(get_db)):
    """Return all active ad slots for frontend rendering."""
    slots = db.query(models.AdSlot).filter(
        models.AdSlot.is_active == True  # noqa: E712
    ).order_by(models.AdSlot.sort_order).all()
    return [{
        "id": s.id,
        "name": s.name,
        "slot_key": s.slot_key,
        "ad_code": s.ad_code,
        "ad_type": s.ad_type,
        "position": getattr(s, "position", None) or s.slot_key,
    } for s in slots]


# ── Auth: extend retention via ad click ─────────────────────────────
@router.post("/click/{slot_id}")
def ad_click(
    slot_id: int,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """User clicked an ad → extend file retention by 7 days (max 180)."""
    if not user:
        raise HTTPException(401, "Zaloguj sie by przedluzyc przechowywanie")

    slot = db.query(models.AdSlot).filter(models.AdSlot.id == slot_id).first()
    if not slot:
        raise HTTPException(404, "Slot not found")

    # Extend: +7 days per click, cap at 180 days
    user.retention_days = min((user.retention_days or 30) + 7, 180)
    slot.clicks += 1
    db.commit()

    return {
        "ok": True,
        "retention_days": user.retention_days,
        "message": f"Przedluzono do {user.retention_days} dni",
    }


# ── Admin CRUD ──────────────────────────────────────────────────────
class AdSlotReq(BaseModel):
    name: str
    slot_key: str  # e.g. "hero_bottom", "sidebar", "after_convert"
    ad_code: str   # HTML/JS ad code (AdSense etc.)
    ad_type: str = "adsense"  # adsense / custom / image
    position: str = "hero_bottom"  # hero_bottom / after_convert / page_bottom / sidebar / viewer_overlay / search_top
    sort_order: int = 0
    is_active: bool = True


@router.get("/admin/slots")
def admin_list_slots(
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    slots = db.query(models.AdSlot).order_by(models.AdSlot.sort_order).all()
    return [{
        "id": s.id, "name": s.name, "slot_key": s.slot_key,
        "ad_code": s.ad_code, "ad_type": s.ad_type,
        "position": getattr(s, "position", None) or s.slot_key,
        "sort_order": s.sort_order, "is_active": s.is_active,
        "position": getattr(s, "position", None) or s.slot_key,
        "impressions": s.impressions, "clicks": s.clicks,
        "created_at": str(s.created_at),
    } for s in slots]


@router.post("/admin/slots")
def admin_create_slot(
    req: AdSlotReq,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    # Check unique slot_key
    existing = db.query(models.AdSlot).filter(models.AdSlot.slot_key == req.slot_key).first()
    if existing:
        raise HTTPException(400, "Slot key juz istnieje")

    slot = models.AdSlot(
        name=req.name, slot_key=req.slot_key, ad_code=req.ad_code,
        ad_type=req.ad_type, position=getattr(req,"position",None) or req.slot_key, sort_order=req.sort_order, is_active=req.is_active,
    )
    db.add(slot)
    db.commit()
    db.refresh(slot)
    return {"ok": True, "id": slot.id}


@router.put("/admin/slots/{slot_id}")
def admin_update_slot(
    slot_id: int,
    req: AdSlotReq,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    slot = db.query(models.AdSlot).filter(models.AdSlot.id == slot_id).first()
    if not slot:
        raise HTTPException(404)
    slot.name = req.name
    slot.slot_key = req.slot_key
    slot.ad_code = req.ad_code
    slot.ad_type = req.ad_type
    slot.position = getattr(req,"position",None) or req.slot_key
    slot.sort_order = req.sort_order
    slot.is_active = req.is_active
    db.commit()
    return {"ok": True}


@router.delete("/admin/slots/{slot_id}")
def admin_delete_slot(
    slot_id: int,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    slot = db.query(models.AdSlot).filter(models.AdSlot.id == slot_id).first()
    if not slot:
        raise HTTPException(404)
    db.delete(slot)
    db.commit()
    return {"ok": True}


@router.post("/admin/slots/{slot_id}/toggle")
def admin_toggle_slot(
    slot_id: int,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    slot = db.query(models.AdSlot).filter(models.AdSlot.id == slot_id).first()
    if not slot:
        raise HTTPException(404)
    slot.is_active = not slot.is_active
    db.commit()
    return {"ok": True, "is_active": slot.is_active}
