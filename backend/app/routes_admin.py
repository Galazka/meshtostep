"""Admin routes: stats, geo stats, users, per-user detail."""
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
    total_users = db.query(models.User).count()
    total_jobs = db.query(models.Job).filter(models.Job.status != "deleted").count()
    # keep fallback total including deleted for compat
    total_jobs_all = db.query(models.Job).count()

    total_storage_bytes = db.query(func.sum(models.Job.file_size_bytes)).filter(
        models.Job.status != "deleted"
    ).scalar() or 0

    total_downloads = db.query(func.sum(models.ShareLink.downloads)).scalar() or 0

    # jobs_by_status
    status_rows = db.query(models.Job.status, func.count(models.Job.id)).group_by(models.Job.status).all()
    jobs_by_status = {row[0] or "unknown": row[1] for row in status_rows}

    # storage_by_user: top users by total bytes
    storage_rows = (
        db.query(
            models.Job.user_id,
            func.sum(models.Job.file_size_bytes).label("total_bytes"),
            func.count(models.Job.id).label("cnt"),
        )
        .filter(models.Job.status != "deleted", models.Job.user_id.isnot(None))
        .group_by(models.Job.user_id)
        .order_by(desc("total_bytes"))
        .limit(20)
        .all()
    )
    # map user_id -> email/username
    user_ids = [r.user_id for r in storage_rows]
    users_map = {}
    if user_ids:
        for u in db.query(models.User).filter(models.User.id.in_(user_ids)).all():
            users_map[u.id] = u
    storage_by_user = []
    for r in storage_rows:
        u = users_map.get(r.user_id)
        storage_by_user.append({
            "user_id": r.user_id,
            "username": u.username if u else None,
            "email": u.email if u else None,
            "total_size_bytes": int(r.total_bytes or 0),
            "job_count": int(r.cnt or 0),
        })

    # daily_uploads_last_30d
    since = datetime.utcnow() - timedelta(days=30)
    daily_rows = (
        db.query(
            func.date(models.Job.created_at).label("day"),
            func.count(models.Job.id).label("count"),
        )
        .filter(models.Job.created_at >= since, models.Job.status != "deleted")
        .group_by(func.date(models.Job.created_at))
        .order_by(func.date(models.Job.created_at))
        .all()
    )
    # build full 30-day array filling zeros
    daily_map = {str(r.day): int(r.count) for r in daily_rows}
    daily_uploads_last_30d = []
    for i in range(30):
        d = (since + timedelta(days=i + 1)).date()
        ds = str(d)
        daily_uploads_last_30d.append({"date": ds, "count": daily_map.get(ds, 0)})

    # top_models: most viewed jobs
    top_jobs = (
        db.query(models.Job)
        .filter(models.Job.status != "deleted")
        .order_by(desc(models.Job.views))
        .limit(10)
        .all()
    )
    top_models = [
        {
            "id": j.id,
            "uuid": j.uuid,
            "filename": j.original_filename,
            "title": j.title,
            "views": j.views or 0,
            "likes": j.likes or 0,
            "user_id": j.user_id,
            "created_at": str(j.created_at),
        }
        for j in top_jobs
    ]

    # legacy fields for backward compat with old frontend
    jobs_done = jobs_by_status.get("done", 0)
    jobs_error = jobs_by_status.get("error", 0)
    revenue_usd = 0  # payments removed — ads only
    shares_active = db.query(models.ShareLink).filter(
        models.ShareLink.is_active == True).count()  # noqa: E712
    total_share_views = db.query(func.sum(models.ShareLink.views)).scalar() or 0

    return {
        # required new keys
        "total_users": total_users,
        "total_jobs": total_jobs,
        "total_downloads": int(total_downloads),
        "total_storage_bytes": int(total_storage_bytes),
        "storage_by_user": storage_by_user,
        "daily_uploads_last_30d": daily_uploads_last_30d,
        "jobs_by_status": jobs_by_status,
        "top_models": top_models,
        # legacy / compat aliases
        "users": total_users,
        "jobs_total": total_jobs_all,
        "jobs": total_jobs,
        "jobs_done": jobs_done,
        "jobs_error": jobs_error,
        "revenue_usd": revenue_usd,
        "revenue": revenue_usd,
        "shares_active": shares_active,
        "total_share_views": total_share_views,
        "total_revenue": revenue_usd,
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
    if not users:
        return []
    user_ids = [u.id for u in users]
    # aggregate job counts + storage per user (exclude soft-deleted)
    agg_rows = (
        db.query(
            models.Job.user_id,
            func.count(models.Job.id).label("cnt"),
            func.coalesce(func.sum(models.Job.file_size_bytes), 0).label("total_bytes"),
            func.max(models.Job.created_at).label("last_job_at"),
        )
        .filter(models.Job.user_id.in_(user_ids), models.Job.status != "deleted")
        .group_by(models.Job.user_id)
        .all()
    )
    agg_map = {r.user_id: r for r in agg_rows}
    result = []
    for u in users:
        agg = agg_map.get(u.id)
        job_count = int(agg.cnt) if agg else 0
        total_size_bytes = int(agg.total_bytes) if agg else 0
        last_job_at = str(agg.last_job_at) if agg and agg.last_job_at else None
        # last_active: prefer last_login, fallback to last_job_at, then created_at
        last_active = str(u.last_login) if u.last_login else (last_job_at or str(u.created_at))
        result.append({
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "is_admin": u.is_admin,
            "created_at": str(u.created_at),
            "last_login": str(u.last_login) if u.last_login else None,
            "last_active": last_active,
            "job_count": job_count,
            "jobs_count": job_count,  # compat alias
            "total_size_bytes": total_size_bytes,
            "total_storage_bytes": total_size_bytes,
            "last_job_at": last_job_at,
        })
    return result


# ── Per-user files list ─────────────────────────────────────────────
@router.get("/users/{user_id}/files")
def user_files(
    user_id: int,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    jobs = (
        db.query(models.Job)
        .filter(models.Job.user_id == user_id)
        .order_by(desc(models.Job.created_at))
        .limit(100)
        .all()
    )
    return [
        {
            "id": j.id,
            "uuid": j.uuid,
            "filename": j.original_filename,
            "original_filename": j.original_filename,
            "file_size_bytes": j.file_size_bytes or 0,
            "mode": j.mode,
            "status": j.status,
            "views": j.views or 0,
            "likes": j.likes or 0,
            "created_at": str(j.created_at),
            "completed_at": str(j.completed_at) if j.completed_at else None,
        }
        for j in jobs
    ]


# ── Cleanup: soft-delete excess files per user ──────────────────────
class CleanupReq(BaseModel):
    max_files_per_user: int = 10


@router.post("/cleanup")
def cleanup(
    body: CleanupReq = None,
    max_files_per_user: int = None,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    # accept both JSON body and query param
    limit = None
    if body and body.max_files_per_user is not None:
        limit = body.max_files_per_user
    if max_files_per_user is not None:
        limit = max_files_per_user
    if limit is None:
        limit = 10
    if limit < 0:
        raise HTTPException(400, "max_files_per_user must be >= 0")
    if limit > 10000:
        raise HTTPException(400, "max_files_per_user too large")

    # find users with > limit active files
    # get per-user active counts
    active_counts = (
        db.query(models.Job.user_id, func.count(models.Job.id).label("cnt"))
        .filter(models.Job.status != "deleted", models.Job.user_id.isnot(None))
        .group_by(models.Job.user_id)
        .having(func.count(models.Job.id) > limit)
        .all()
    )
    deleted_total = 0
    affected_users = 0
    details = []
    for row in active_counts:
        uid = row.user_id
        cnt = int(row.cnt)
        excess = cnt - limit
        if excess <= 0:
            continue
        # oldest files first
        oldest = (
            db.query(models.Job)
            .filter(models.Job.user_id == uid, models.Job.status != "deleted")
            .order_by(models.Job.created_at.asc(), models.Job.id.asc())
            .limit(excess)
            .all()
        )
        for job in oldest:
            job.status = "deleted"
            deleted_total += 1
        affected_users += 1
        details.append({"user_id": uid, "deleted": len(oldest), "had": cnt, "kept": limit})

    if deleted_total:
        db.commit()

    return {
        "ok": True,
        "max_files_per_user": limit,
        "deleted_count": deleted_total,
        "affected_users": affected_users,
        "details": details,
    }


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

    # Recent jobs
    recent_jobs = (
        db.query(models.Job)
        .filter(models.Job.user_id == user_id)
        .order_by(desc(models.Job.created_at))
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
        "username": user.username,
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
        "recent_jobs": [{
            "id": j.id, "filename": j.original_filename, "status": j.status,
            "mode": j.mode, "created_at": str(j.created_at),
        } for j in recent_jobs],
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

# Bulk delete jobs by admin
@router.post("/jobs/bulk-delete")
def admin_bulk_delete(
    payload: dict,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    ids = payload.get("ids") or []
    if not isinstance(ids, list) or not ids:
        raise HTTPException(400, "ids required")
    ids = [int(x) for x in ids if str(x).isdigit()][:500]
    jobs = db.query(models.Job).filter(models.Job.id.in_(ids)).all()
    jobs_dir = os.path.join(settings.DATA_DIR, "files")
    for job in jobs:
        db.query(models.ShareLink).filter(models.ShareLink.job_id == job.id).delete()
        job_dir = os.path.join(jobs_dir, job.uuid)
        if os.path.isdir(job_dir):
            shutil.rmtree(job_dir, ignore_errors=True)
        db.delete(job)
    db.commit()
    return {"ok": True, "deleted": len(jobs)}


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


# ── Orphan cleanup: jobs whose mesh files are gone from disk ─────────
@router.get("/orphans")
def list_orphans(
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List jobs whose mesh files no longer exist on disk (broken previews)."""
    from pathlib import Path
    jobs_dir = Path(settings.DATA_DIR) / "files"
    orphans = []
    jobs = db.query(models.Job).filter(models.Job.status != "deleted").all()
    for job in jobs:
        ok = False
        # check known path
        if job.result_stl_path and os.path.exists(job.result_stl_path):
            ok = True
        else:
            d = jobs_dir / job.uuid
            if d.is_dir():
                for f in d.iterdir():
                    if f.suffix.lower() in (".stl", ".3mf", ".obj", ".step"):
                        ok = True
                        break
        if not ok:
            orphans.append({
                "id": job.id, "uuid": job.uuid,
                "filename": job.original_filename, "title": job.title,
                "status": job.status, "user_id": job.user_id,
                "created_at": str(job.created_at),
            })
    return {"count": len(orphans), "orphans": orphans}


@router.post("/orphans/delete")
def delete_orphans(
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Delete all orphan jobs (no mesh files on disk). Irreversible."""
    from pathlib import Path
    jobs_dir = Path(settings.DATA_DIR) / "files"
    deleted = 0
    jobs = db.query(models.Job).filter(models.Job.status != "deleted").all()
    for job in jobs:
        ok = False
        if job.result_stl_path and os.path.exists(job.result_stl_path):
            ok = True
        else:
            d = jobs_dir / job.uuid
            if d.is_dir():
                for f in d.iterdir():
                    if f.suffix.lower() in (".stl", ".3mf", ".obj", ".step"):
                        ok = True
                        break
        if not ok:
            db.query(models.ShareLink).filter(models.ShareLink.job_id == job.id).delete()
            db.query(models.Comment).filter(models.Comment.job_id == job.id).delete()
            from . import models as _m
            db.query(_m.JobRating).filter(_m.JobRating.job_id == job.id).delete()
            d = jobs_dir / job.uuid
            if d.is_dir():
                import shutil as _sh
                _sh.rmtree(d, ignore_errors=True)
            db.delete(job)
            deleted += 1
    db.commit()
    return {"ok": True, "deleted": deleted}


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
