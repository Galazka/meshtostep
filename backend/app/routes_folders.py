"""Folders CRUD — 3dhosty.com"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from . import models
from .auth import require_user
from .database import get_db

router = APIRouter(prefix="/api", tags=["folders"])

@router.get("/folders")
def list_folders(user: models.User = Depends(require_user), db: Session = Depends(get_db)):
    rows = db.query(models.Folder).filter(models.Folder.user_id == user.id).order_by(models.Folder.created_at.asc()).all()
    return [{"id": f.id, "name": f.name, "created_at": str(f.created_at)} for f in rows]

@router.post("/folders")
def create_folder(payload: dict, user: models.User = Depends(require_user), db: Session = Depends(get_db)):
    name = (payload.get("name") or "").strip()[:80]
    if not name:
        raise HTTPException(400, "Nazwa folderu wymagana")
    # unique per user
    if db.query(models.Folder).filter(models.Folder.user_id == user.id, models.Folder.name == name).first():
        raise HTTPException(409, "Folder już istnieje")
    f = models.Folder(user_id=user.id, name=name)
    db.add(f); db.commit(); db.refresh(f)
    return {"id": f.id, "name": f.name}

@router.patch("/folders/{folder_id}")
def rename_folder(folder_id: int, payload: dict, user: models.User = Depends(require_user), db: Session = Depends(get_db)):
    f = db.query(models.Folder).filter(models.Folder.id == folder_id).first()
    if not f or f.user_id != user.id:
        raise HTTPException(404, "Folder nie znaleziony")
    name = (payload.get("name") or "").strip()[:80]
    if not name:
        raise HTTPException(400, "Nazwa wymagana")
    if db.query(models.Folder).filter(models.Folder.user_id == user.id, models.Folder.name == name, models.Folder.id != f.id).first():
        raise HTTPException(409, "Nazwa zajęta")
    f.name = name; db.commit()
    return {"id": f.id, "name": f.name}

@router.delete("/folders/{folder_id}")
def delete_folder(folder_id: int, user: models.User = Depends(require_user), db: Session = Depends(get_db)):
    f = db.query(models.Folder).filter(models.Folder.id == folder_id).first()
    if not f or f.user_id != user.id:
        raise HTTPException(404, "Folder nie znaleziony")
    # detach jobs
    db.query(models.Job).filter(models.Job.folder_id == f.id).update({"folder_id": None})
    db.delete(f); db.commit()
    return {"ok": True}
