"""Admin routes: stats, users, jobs."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func

from . import models
from .auth import require_admin
from .database import get_db

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/stats")
def stats(admin: models.User = Depends(require_admin), db=Depends(get_db)):
    return {
        "users": db.query(models.User).count(),
        "jobs_total": db.query(models.Job).count(),
        "jobs_done": db.query(models.Job).filter(models.Job.status == "done").count(),
        "jobs_error": db.query(models.Job).filter(models.Job.status == "error").count(),
        "credits_sold": db.query(func.sum(models.Payment.credits_granted)).scalar() or 0,
        "revenue_pln": db.query(func.sum(models.Payment.amount_pln)).filter(
            models.Payment.status == "completed").scalar() or 0,
        "shares_active": db.query(models.ShareLink).filter(models.ShareLink.is_active == True).count(),
        "total_downloads": db.query(func.sum(models.ShareLink.downloads)).scalar() or 0,
    }


@router.get("/users")
def list_users(admin: models.User = Depends(require_admin), db=Depends(get_db)):
    users = db.query(models.User).order_by(models.User.created_at.desc()).limit(100).all()
    return [{"id": u.id, "email": u.email, "credits": u.credits, "is_admin": u.is_admin,
             "created_at": str(u.created_at), "last_login": str(u.last_login)} for u in users]


@router.get("/jobs")
def list_jobs(admin: models.User = Depends(require_admin), db=Depends(get_db)):
    jobs = db.query(models.Job).order_by(models.Job.created_at.desc()).limit(100).all()
    return [{"id": j.id, "uuid": j.uuid, "user_id": j.user_id, "filename": j.original_filename,
             "status": j.status, "mode": j.mode, "faces": j.result_faces,
             "processing_time_s": j.processing_time_s, "created_at": str(j.created_at)} for j in jobs]


@router.post("/users/{user_id}/credits")
def add_credits(user_id: int, amount: int = 5, admin: models.User = Depends(require_admin), db=Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(404)
    user.credits += amount
    db.commit()
    return {"ok": True, "credits": user.credits}
