"""Gallery zarządzanie — publiczne i admin.
Public: GET /api/gallery (aktywne prace na landing)
Admin: list / add / delete / set-active
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from . import models
from .auth import require_admin
from .database import get_db

router = APIRouter()


def _pub(g):
    return {"id": g.id, "title": g.title, "description": g.description,
            "material": g.material, "color": g.color,
            "image": g.image_base64}


@router.get("/api/gallery")
def gallery_public(db: Session = Depends(get_db)):
    rows = db.query(models.Gallery).filter(models.Gallery.is_active == True) \
        .order_by(models.Gallery.sort_order, models.Gallery.id.desc()).all()
    return {"ok": True, "items": [_pub(g) for g in rows]}


class GalleryIn(BaseModel):
    title: str
    description: str = None
    material: str = None
    color: str = None
    image: str = ""          # data:image/...;base64,...
    sort_order: int = 0


@router.get("/api/admin/gallery")
def gallery_admin(admin: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    if not admin or not getattr(admin, "is_admin", False):
        raise HTTPException(403, detail="Admin only")
    rows = db.query(models.Gallery).order_by(models.Gallery.sort_order, models.Gallery.id.desc()).all()
    return {"ok": True, "items": [_pub(g) for g in rows]}


@router.post("/api/admin/gallery")
def gallery_add(req: GalleryIn, admin: models.User = Depends(require_admin),
                db: Session = Depends(get_db)):
    if not admin or not getattr(admin, "is_admin", False):
        raise HTTPException(403, detail="Admin only")
    if not req.title.strip():
        raise HTTPException(400, detail="Tytuł wymagany")
    if not req.image or not req.image.startswith("data:image"):
        raise HTTPException(400, detail="Brak obrazu (base64 data URL)")
    g = models.Gallery(title=req.title.strip()[:200],
                       description=(req.description or None),
                       material=(req.material or None),
                       color=(req.color or None),
                       image_base64=req.image,
                       sort_order=req.sort_order or 0,
                       is_active=True)
    db.add(g); db.commit(); db.refresh(g)
    return {"ok": True, "id": g.id}


@router.delete("/api/admin/gallery/{gid}")
def gallery_del(gid: int, admin: models.User = Depends(require_admin),
                db: Session = Depends(get_db)):
    if not admin or not getattr(admin, "is_admin", False):
        raise HTTPException(403, detail="Admin only")
    g = db.get(models.Gallery, gid)
    if not g:
        raise HTTPException(404, detail="Brak wpisu")
    db.delete(g); db.commit()
    return {"ok": True}


@router.post("/api/admin/gallery/{gid}/toggle")
def gallery_toggle(gid: int, admin: models.User = Depends(require_admin),
                   db: Session = Depends(get_db)):
    if not admin or not getattr(admin, "is_admin", False):
        raise HTTPException(403, detail="Admin only")
    g = db.get(models.Gallery, gid)
    if not g:
        raise HTTPException(404, detail="Brak wpisu")
    g.is_active = not g.is_active
    db.commit()
    return {"ok": True, "is_active": g.is_active}
