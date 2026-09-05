"""Conversion routes: upload, convert, download, share."""
import os
import uuid
import time
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from . import models
from .auth import get_current_user, require_user
from .config import settings
from .database import get_db
from .engine import convert

router = APIRouter(prefix="/api", tags=["convert"])

JOBS_DIR = Path(settings.DATA_DIR) / "files"
PREVIEWS_DIR = Path(settings.DATA_DIR) / "previews"
SHARES_DIR = Path(settings.DATA_DIR) / "shares"
for d in [JOBS_DIR, PREVIEWS_DIR, SHARES_DIR]:
    d.mkdir(parents=True, exist_ok=True)


@router.post("/convert")
async def convert_file(
    file: UploadFile = File(...),
    mode: str = Form("auto"),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    t0 = time.time()
    ext = Path(file.filename).suffix.lower()
    if ext not in (".stl", ".3mf", ".obj"):
        raise HTTPException(400, "Obsługiwane: .stl, .3mf, .obj")

    # Check credits
    if user:
        if user.credits < 1:
            raise HTTPException(402, "Brak kredytów. Dokup pakiet.")
    # anon gets 1 free conversion (no account needed)

    # Save upload
    job_uuid = uuid.uuid4().hex[:12]
    job_dir = JOBS_DIR / job_uuid
    job_dir.mkdir(exist_ok=True)
    src = job_dir / file.filename
    data = await file.read()
    if len(data) > settings.MAX_FILE_MB * 1024 * 1024:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(400, f"Plik > {settings.MAX_FILE_MB} MB")
    src.write_bytes(data)

    # Create job record
    job = models.Job(
        user_id=user.id if user else None,
        uuid=job_uuid,
        original_filename=file.filename,
        file_size_bytes=len(data),
        mode=mode,
        status="processing",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Deduct credit
    if user:
        user.credits -= 1
        job.credits_used = 1
        db.commit()

    # Convert
    out_step = str(job_dir / (Path(file.filename).stem + ".step"))
    result = convert(str(src), out_step, mode=mode)

    if result["ok"]:
        job.status = "done"
        job.result_step_path = out_step
        job.result_faces = result["faces"]
        job.result_size_bytes = result["result_size"]
        job.processing_time_s = round(time.time() - t0, 1)
        job.completed_at = datetime.utcnow()
        db.commit()

        return {
            "ok": True,
            "job_id": job.id,
            "uuid": job_uuid,
            "faces": result["faces"],
            "step_size_kb": result["result_size"] // 1024,
            "time_s": job.processing_time_s,
            "mode": mode,
            "credits_remaining": user.credits if user else None,
            "filename": Path(file.filename).stem + ".step",
        }
    else:
        job.status = "error"
        job.error_msg = result["error"][:2000]
        db.commit()
        # Refund credit
        if user:
            user.credits += 1
            db.commit()
        raise HTTPException(500, result["error"][:500])


@router.get("/download/{job_uuid}")
def download(job_uuid: str, format: str = "step", db: Session = Depends(get_db)):
    job = db.query(models.Job).filter(models.Job.uuid == job_uuid, models.Job.status == "done").first()
    if not job:
        raise HTTPException(404, "Job nie znaleziony")
    path = job.result_step_path
    if not path or not os.path.exists(path):
        raise HTTPException(404, "Plik nie istnieje")
    return FileResponse(
        path,
        filename=Path(job.original_filename).stem + f".{format}",
        media_type="application/step" if format == "step" else "application/octet-stream",
    )


# --- Share links ---
@router.post("/share")
def create_share(
    job_id: int = Form(...),
    fmt: str = Form("step"),
    expires_days: int = Form(7),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(404)
    if user and job.user_id != user.id and not user.is_admin:
        raise HTTPException(403)

    token = uuid.uuid4().hex[:16]
    share = models.ShareLink(
        token=token,
        job_id=job.id,
        user_id=user.id if user else None,
        format=fmt,
        expires_at=datetime.utcnow() + timedelta(days=expires_days) if expires_days > 0 else None,
    )
    db.add(share)
    db.commit()

    return {"url": f"{settings.APP_URL}/s/{token}", "token": token}


@router.get("/share/{token}")
def get_share(token: str, db: Session = Depends(get_db)):
    share = db.query(models.ShareLink).filter(
        models.ShareLink.token == token, models.ShareLink.is_active == True
    ).first()
    if not share:
        raise HTTPException(404, "Link nie istnieje")
    if share.expires_at and share.expires_at < datetime.utcnow():
        raise HTTPException(410, "Link wygasł")
    if share.max_downloads and share.downloads >= share.max_downloads:
        raise HTTPException(410, "Limit pobrań osiągnięty")

    job = share.job
    return {
        "job": {
            "original_filename": job.original_filename,
            "faces": job.result_faces,
            "mode": job.mode,
            "size_kb": job.result_size_bytes // 1024 if job.result_size_bytes else 0,
            "created_at": str(job.created_at),
        },
        "format": share.format,
        "downloads": share.downloads,
    }


@router.get("/share/{token}/download")
def share_download(token: str, db: Session = Depends(get_db)):
    share = db.query(models.ShareLink).filter(
        models.ShareLink.token == token, models.ShareLink.is_active == True
    ).first()
    if not share:
        raise HTTPException(404)
    if share.expires_at and share.expires_at < datetime.utcnow():
        raise HTTPException(410, "Link wygasł")

    job = share.job
    path = job.result_step_path
    if not path or not os.path.exists(path):
        raise HTTPException(404, "Plik usunięty")

    share.downloads += 1
    db.commit()

    fmt = share.format
    ext = "step" if fmt == "step" else "stl"
    return FileResponse(
        path,
        filename=Path(job.original_filename).stem + f".{ext}",
        media_type="application/step" if ext == "step" else "application/octet-stream",
    )


# --- User jobs list ---
@router.get("/jobs")
def list_jobs(user: models.User = Depends(require_user), db: Session = Depends(get_db)):
    jobs = db.query(models.Job).filter(
        models.Job.user_id == user.id
    ).order_by(models.Job.created_at.desc()).limit(50).all()
    return [{"id": j.id, "uuid": j.uuid, "filename": j.original_filename, "status": j.status,
             "mode": j.mode, "faces": j.result_faces, "created_at": str(j.created_at)} for j in jobs]
