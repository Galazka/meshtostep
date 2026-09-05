"""Admin routes: stats, geo stats, users, per-user detail, credit adjustments."""
import os
import shutil
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from . import models
from .auth import require_admin
from .config import settings
from .database import get_db

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ── Overview stats ───────────────────────────────────────────────────
@router.get("/stats")
def stats(admin: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    return {
        "users": db.query(models.User).count(),
        "jobs_total": db.query(models.Job).count(),
        "jobs_done": db.query(models.Job).filter(models.Job.status == "done").count(),
        "jobs_error": db.query(models.Job).filter(models.Job.status == "error").count(),
        "credits_sold": db.query(func.sum(models.Payment.credits_granted)).scalar() or 0,
        "revenue_usd": db.query(func.sum(models.Payment.amount_usd)).filter(
            models.Payment.status == "completed").scalar() or 0,
        "shares_active": db.query(models.ShareLink).filter(
            models.ShareLink.is_active == True).count(),  # noqa: E712
        "total_downloads": db.query(func.sum(models.ShareLink.downloads)).scalar() or 0,
        "total_share_views": db.query(func.sum(models.ShareLink.views)).scalar() or 0,
    }


# ── Geo stats ───────────────────────────────────────────────────────
@router.get("/geo")
def geo_stats(
    days: int = 30,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Aggregate geo data for the last N days."""
    since = datetime.utcnow() - timedelta(days=days)

    # Country breakdown
    countries = (
        db.query(
            models.GeoLog.country,
            func.count(models.GeoLog.id).label("count"),
        )
        .filter(models.GeoLog.created_at >= since)
        .group_by(models.GeoLog.country)
        .order_by(desc("count"))
        .limit(50)
        .all()
    )

    # City breakdown
    cities = (
        db.query(
            models.GeoLog.country,
            models.GeoLog.city,
            func.count(models.GeoLog.id).label("count"),
        )
        .filter(models.GeoLog.created_at >= since, models.GeoLog.city.isnot(None))
        .group_by(models.GeoLog.country, models.GeoLog.city)
        .order_by(desc("count"))
        .limit(50)
        .all()
    )

    # Daily request volume
    daily = (
        db.query(
            func.date(models.GeoLog.created_at).label("day"),
            func.count(models.GeoLog.id).label("count"),
        )
        .filter(models.GeoLog.created_at >= since)
        .group_by(func.date(models.GeoLog.created_at))
        .order_by(desc("day"))
        .all()
    )

    # Unique IPs
    unique_ips = (
        db.query(func.count(func.distinct(models.GeoLog.ip_address)))
        .filter(models.GeoLog.created_at >= since)
        .scalar() or 0
    )

    return {
        "period_days": days,
        "total_requests": db.query(models.GeoLog).filter(
            models.GeoLog.created_at >= since).count(),
        "unique_ips": unique_ips,
        "countries": [{"country": c.country or "Unknown", "count": c.count} for c in countries],
        "cities": [
            {"country": c.country, "city": c.city, "count": c.count}
            for c in cities
        ],
        "daily": [{"date": str(d.day), "count": d.count} for d in daily],
    }


# ── User list ───────────────────────────────────────────────────────
@router.get("/users")
def list_users(admin: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    users = db.query(models.User).order_by(models.User.created_at.desc()).limit(100).all()
    return [{
        "id": u.id, "email": u.email, "credits": u.credits, "is_admin": u.is_admin,
        "created_at": str(u.created_at), "last_login": str(u.last_login),
    } for u in users]


# ── Per-user detailed stats ─────────────────────────────────────────
@router.get("/users/{user_id}")
def user_detail(
    user_id: int,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Detailed stats for a single user."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    # Jobs
    total_jobs = db.query(models.Job).filter(models.Job.user_id == user_id).count()
    done_jobs = db.query(models.Job).filter(
        models.Job.user_id == user_id, models.Job.status == "done").count()
    error_jobs = db.query(models.Job).filter(
        models.Job.user_id == user_id, models.Job.status == "error").count()

    # Share stats
    total_shares = db.query(models.ShareLink).filter(
        models.ShareLink.user_id == user_id).count()
    total_downloads = (
        db.query(func.sum(models.ShareLink.downloads))
        .filter(models.ShareLink.user_id == user_id).scalar() or 0
    )
    total_share_views = (
        db.query(func.sum(models.ShareLink.views))
        .filter(models.ShareLink.user_id == user_id).scalar() or 0
    )

    # Credit adjustments
    adjustments = (
        db.query(models.CreditAdjustment)
        .filter(models.CreditAdjustment.user_id == user_id)
        .order_by(desc(models.CreditAdjustment.created_at))
        .limit(20)
        .all()
    )

    # Recent jobs
    recent_jobs = (
        db.query(models.Job)
        .filter(models.Job.user_id == user_id)
        .order_by(desc(models.Job.created_at))
        .limit(10)
        .all()
    )

    # Payment history
    payments = (
        db.query(models.Payment)
        .filter(models.Payment.user_id == user_id)
        .order_by(desc(models.Payment.created_at))
        .limit(10)
        .all()
    )

    # Last geo activity
    last_geo = (
        db.query(models.GeoLog)
        .filter(models.GeoLog.user_id == user_id)
        .order_by(desc(models.GeoLog.created_at))
        .first()
    )

    return {
        "id": user.id,
        "email": user.email,
        "credits": user.credits,
        "is_admin": user.is_admin,
        "created_at": str(user.created_at),
        "last_login": str(user.last_login),
        "stats": {
            "total_conversions": total_jobs,
            "conversions_done": done_jobs,
            "conversions_error": error_jobs,
            "total_shares": total_shares,
            "total_downloads": total_downloads,
            "total_share_views": total_share_views,
        },
        "last_activity": str(last_geo.created_at) if last_geo else str(user.last_login),
        "last_ip": last_geo.ip_address if last_geo else None,
        "last_country": last_geo.country if last_geo else None,
        "last_city": last_geo.city if last_geo else None,
        "adjustments": [{
            "id": a.id, "amount": a.amount, "reason": a.reason,
            "credits_before": a.credits_before, "credits_after": a.credits_after,
            "admin_id": a.admin_id, "created_at": str(a.created_at),
        } for a in adjustments],
        "recent_jobs": [{
            "id": j.id, "filename": j.original_filename, "status": j.status,
            "mode": j.mode, "created_at": str(j.created_at),
        } for j in recent_jobs],
        "payments": [{
            "id": p.id, "amount_usd": p.amount_usd, "credits_granted": p.credits_granted,
            "status": p.status, "created_at": str(p.created_at),
        } for p in payments],
    }


# ── Admin jobs list ─────────────────────────────────────────────────
@router.get("/jobs")
def list_jobs(admin: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    jobs = (
        db.query(models.Job)
        .join(models.User, models.Job.user_id == models.User.id, isouter=True)
        .order_by(models.Job.created_at.desc())
        .limit(100)
        .all()
    )
    return [{
        "id": j.id, "uuid": j.uuid, "user_id": j.user_id,
        "user_email": j.user.email if j.user else None,
        "filename": j.original_filename, "status": j.status, "mode": j.mode,
        "faces": j.result_faces, "processing_time_s": j.processing_time_s,
        "created_at": str(j.created_at),
    } for j in jobs]


# ── Delete job ───────────────────────────────────────────────────────
@router.delete("/jobs/{job_id}")
def delete_job(
    job_id: int,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    db.query(models.ShareLink).filter(models.ShareLink.job_id == job.id).delete()
    jobs_dir = os.path.join(settings.DATA_DIR, "files")
    job_dir = os.path.join(jobs_dir, job.uuid)
    if os.path.isdir(job_dir):
        shutil.rmtree(job_dir, ignore_errors=True)
    db.delete(job)
    db.commit()
    return {"ok": True}


# ── Credit adjustment ───────────────────────────────────────────────
class CreditAdjustReq(BaseModel):
    amount: int  # positive = grant, negative = revoke
    reason: str = ""


@router.post("/users/{user_id}/credits")
def adjust_credits(
    user_id: int,
    body: CreditAdjustReq,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Manually adjust a user's credits with full audit trail."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    if body.amount == 0:
        raise HTTPException(400, "Amount cannot be zero")

    credits_before = user.credits
    user.credits = max(0, user.credits + body.amount)

    adjustment = models.CreditAdjustment(
        user_id=user_id,
        admin_id=admin.id,
        amount=body.amount,
        reason=body.reason or None,
        credits_before=credits_before,
        credits_after=user.credits,
    )
    db.add(adjustment)
    db.commit()

    return {
        "ok": True,
        "credits": user.credits,
        "adjustment_id": adjustment.id,
    }


# ── Toggle keep_files_forever (lifetime plan) ────────────────────────
class KeepFilesReq(BaseModel):
    keep_files_forever: bool


@router.post("/users/{user_id}/keep-files")
def toggle_keep_files(
    user_id: int,
    body: KeepFilesReq,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Grant or revoke lifetime file retention for a user."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    user.keep_files_forever = body.keep_files_forever
    db.commit()
    return {"ok": True, "keep_files_forever": user.keep_files_forever}
