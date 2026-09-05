"""Comments on models — 3dhosty.com"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from .database import get_db
from . import models
from .auth import get_current_user

router = APIRouter(prefix="/api/comments", tags=["comments"])

class CommentReq(BaseModel):
    job_id: int
    body: str

@router.get("/{job_id}")
def list_comments(job_id: int, db: Session = Depends(get_db)):
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(404, "Model nie znaleziony")
    rows = db.query(models.Comment).filter(models.Comment.job_id==job_id, models.Comment.is_hidden==False).order_by(models.Comment.created_at.asc()).all()
    out=[]
    for c in rows:
        uname = c.user.username if c.user and getattr(c.user,"username",None) else (c.user.email.split("@")[0] if c.user else "anon")
        out.append({"id":c.id,"body":c.body,"username":uname,"created_at":str(c.created_at)})
    return out

@router.post("")
def add_comment(req: CommentReq, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "Zaloguj sie by komentowac")
    if not req.body or not req.body.strip():
        raise HTTPException(400, "Komentarz pusty")
    if len(req.body) > 2000:
        raise HTTPException(400, "Komentarz za dlugi (max 2000)")
    job = db.query(models.Job).filter(models.Job.id == req.job_id, models.Job.status=="done").first()
    if not job:
        raise HTTPException(404, "Model nie znaleziony")
    c = models.Comment(job_id=job.id, user_id=user.id, body=req.body.strip()[:2000])
    db.add(c); db.commit(); db.refresh(c)
    return {"ok": True, "id": c.id}

@router.delete("/{comment_id}")
def delete_comment(comment_id: int, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401)
    c = db.query(models.Comment).filter(models.Comment.id==comment_id).first()
    if not c:
        raise HTTPException(404)
    if c.user_id != user.id and not user.is_admin:
        raise HTTPException(403)
    c.is_hidden=True; db.commit()
    return {"ok": True}
