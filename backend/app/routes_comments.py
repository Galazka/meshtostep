"""Comments routes — public read + auth create + admin delete. — 3dhosty.com"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from . import models
from .auth import get_current_user, require_admin, require_user
from .database import get_db

router = APIRouter(tags=["comments"])


class CommentReq(BaseModel):
    body: str


# ── Public: list comments for a job ───────────────────────────────
@router.get("/api/jobs/{job_id}/comments")
def list_comments(job_id: int, db: Session = Depends(get_db)):
    comments = (
        db.query(models.Comment)
        .filter(
            models.Comment.job_id == job_id,
            models.Comment.is_hidden == False,  # noqa: E712
        )
        .order_by(models.Comment.created_at.desc())
        .limit(100)
        .all()
    )
    return [
        {
            "id": c.id,
            "body": c.body,
            "username": getattr(getattr(c, "user", None), "username", None) or "anon",
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in comments
    ]


# ── Auth: create comment ──────────────────────────────────────────
@router.post("/api/jobs/{job_id}/comments")
def create_comment(
    job_id: int,
    req: CommentReq,
    user: models.User = Depends(require_user),
    db: Session = Depends(get_db),
):
    if not req.body or not req.body.strip():
        raise HTTPException(400, "Pusty komentarz")
    if len(req.body) > 5000:
        raise HTTPException(400, "Komentarz max 5000 znakow")

    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job nie znaleziony")
    if job.visibility == "private":
        raise HTTPException(403, "Komentarze do prywatnych modeli")

    comment = models.Comment(job_id=job_id, user_id=user.id, body=req.body.strip())
    db.add(comment)
    db.commit()
    db.refresh(comment)

    return {
        "id": comment.id,
        "body": comment.body,
        "username": getattr(user, "username", None) or user.email.split("@")[0],
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
    }


# ── Admin: hide comment ───────────────────────────────────────────
@router.delete("/api/admin/comments/{comment_id}")
def hide_comment(
    comment_id: int,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    comment = db.query(models.Comment).filter(models.Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(404)
    comment.is_hidden = True
    db.commit()
    return {"ok": True}
