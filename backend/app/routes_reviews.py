"""Order reviews — public social proof + customer submit + admin moderation.
Public:  GET  /api/reviews          (approved only, 4-6 newest)
Submit:  POST /api/reviews          (name, email, rating, text; one per order email)
Admin:   GET  /api/admin/reviews    (all, newest first)
         PATCH /api/admin/reviews/{id}   toggle is_approved
         DELETE /api/admin/reviews/{id}
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from . import models
from .auth import require_admin
from .database import get_db

router = APIRouter()


def _pub(r):
    return {"id": r.id, "name": r.reviewer_name, "rating": r.rating,
            "text": r.text, "created_at": r.created_at.strftime("%Y-%m-%d") if r.created_at else None}


@router.get("/api/reviews")
def reviews_public(db: Session = Depends(get_db)):
    rows = db.query(models.OrderReview).filter(
        models.OrderReview.is_approved == True
    ).order_by(models.OrderReview.created_at.desc()).limit(50).all()
    return {"ok": True, "items": [_pub(r) for r in rows],
            "count": len(rows),
            "avg": round(sum(r.rating for r in rows) / len(rows), 1) if rows else 0}


class ReviewIn(BaseModel):
    name: str
    email: str = None
    rating: int
    text: str = None
    order_id: int = None


@router.post("/api/reviews")
def review_submit(req: ReviewIn, db: Session = Depends(get_db)):
    if not req.name.strip():
        raise HTTPException(400, detail="Podaj imię/nazwę")
    if not (1 <= req.rating <= 5):
        raise HTTPException(400, detail="Ocena 1-5")
    r = models.OrderReview(reviewer_name=req.name.strip()[:120],
                           reviewer_email=(req.email or None),
                           rating=int(req.rating), text=(req.text or None),
                           order_id=req.order_id or None,
                           is_approved=True)
    db.add(r); db.commit(); db.refresh(r)
    return {"ok": True, "id": r.id}


@router.get("/api/admin/reviews")
def reviews_admin(admin: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    if not admin or not getattr(admin, "is_admin", False):
        raise HTTPException(403, detail="Admin only")
    rows = db.query(models.OrderReview).order_by(models.OrderReview.created_at.desc()).limit(200).all()
    out = []
    for r in rows:
        d = _pub(r); d["email"] = r.reviewer_email; d["approved"] = r.is_approved
        out.append(d)
    return {"ok": True, "items": out}


@router.patch("/api/admin/reviews/{rid}")
def review_toggle(rid: int, admin: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    if not admin or not getattr(admin, "is_admin", False):
        raise HTTPException(403, detail="Admin only")
    r = db.get(models.OrderReview, rid)
    if not r:
        raise HTTPException(404, detail="Brak recenzji")
    r.is_approved = not r.is_approved
    db.commit()
    return {"ok": True, "approved": r.is_approved}


@router.delete("/api/admin/reviews/{rid}")
def review_del(rid: int, admin: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    if not admin or not getattr(admin, "is_admin", False):
        raise HTTPException(403, detail="Admin only")
    r = db.get(models.OrderReview, rid)
    if not r:
        raise HTTPException(404, detail="Brak recenzji")
    db.delete(r); db.commit()
    return {"ok": True}