"""Conversion routes: upload, convert, download, share. — 3dhosty.com"""
import os
import uuid
import time
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from . import models
from .auth import get_current_user, require_user
from .config import settings
from .database import get_db
from .engine import convert
import re

def _slugify(s: str) -> str:
    s=re.sub(r'[^a-z0-9]+','-', (s or '').lower().strip())
    s=re.sub(r'-+','-',s).strip('-')
    return s[:80] or 'model'

def _quota_used(db: Session, user_id: int) -> int:
    row = db.query(func.coalesce(func.sum(models.Job.file_size_bytes),0)).filter(models.Job.user_id==user_id).scalar()
    # also include result_size_bytes if larger
    row2 = db.query(func.coalesce(func.sum(models.Job.result_size_bytes),0)).filter(models.Job.user_id==user_id).scalar()
    return int((row or 0) + (row2 or 0))

router = APIRouter(prefix="/api", tags=["convert"])

JOBS_DIR = Path(settings.DATA_DIR) / "files"
PREVIEWS_DIR = Path(settings.DATA_DIR) / "previews"
SHARES_DIR = Path(settings.DATA_DIR) / "shares"
for d in [JOBS_DIR, PREVIEWS_DIR, SHARES_DIR]:
    d.mkdir(parents=True, exist_ok=True)

QUOTA_DEFAULT = 500 * 1024 * 1024

@router.get("/quota")
def get_quota(user: models.User = Depends(require_user), db: Session = Depends(get_db)):
    limit = getattr(user, "quota_limit_bytes", None) or QUOTA_DEFAULT
    used = _quota_used(db, user.id)
    pct = round(used / limit * 100, 1) if limit else 0
    return {"used_bytes": used, "limit_bytes": limit, "percent": pct, "used_mb": round(used/1024/1024,2), "limit_mb": round(limit/1024/1024,2)}

@router.post("/convert")
async def convert_file(
    file: UploadFile = File(...),
    mode: str = Form("auto"),
    folder_id: str = Form(None),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    t0 = time.time()
    ext = Path(file.filename).suffix.lower()
    if ext not in (".stl", ".3mf", ".obj"):
        raise HTTPException(400, "Obsługiwane: .stl, .3mf, .obj")

    # quota check for logged users
    if user:
        limit = getattr(user, "quota_limit_bytes", None) or QUOTA_DEFAULT
        used = _quota_used(db, user.id)
        # peek size — need to read first to know size, but we check after read
        pass

    job_uuid = uuid.uuid4().hex[:12]
    job_dir = JOBS_DIR / job_uuid
    job_dir.mkdir(exist_ok=True)
    src = job_dir / file.filename
    data = await file.read()
    if len(data) > settings.MAX_FILE_MB * 1024 * 1024:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(400, f"Plik > {settings.MAX_FILE_MB} MB")
    if user:
        limit = getattr(user, "quota_limit_bytes", None) or QUOTA_DEFAULT
        used = _quota_used(db, user.id)
        if used + len(data) > limit:
            shutil.rmtree(job_dir, ignore_errors=True)
            raise HTTPException(413, f"Przekroczono limit 500 MB. Zwolnij miejsce usuwając pliki.")
    src.write_bytes(data)

    if user and not getattr(user,'username',None):
        base = re.sub(r'[^a-z0-9]+','', (user.email.split('@')[0].lower()))[:20] or 'user'
        cand=base
        n=1
        while db.query(models.User).filter(models.User.username==cand).first():
            n+=1; cand=f"{base}{n}"
        user.username=cand; db.commit()
    stem = Path(file.filename).stem
    slug = _slugify(stem)
    if user:
        base_slug=slug; k=1
        while db.query(models.Job).filter(models.Job.user_id==user.id, models.Job.slug==slug).first() is not None:
            k+=1; slug=f"{base_slug}-{k}"
    fid = None
    if folder_id and folder_id not in ("", "null", "None"):
        try:
            fid = int(folder_id)
            f = db.query(models.Folder).filter(models.Folder.id==fid, models.Folder.user_id==user.id).first() if user else None
            if not f:
                fid = None
        except:
            fid = None
    job = models.Job(
        user_id=user.id if user else None,
        uuid=job_uuid,
        original_filename=file.filename,
        file_size_bytes=len(data),
        mode=mode,
        status="processing",
        slug=slug,
        title=stem[:200],
        visibility="public",
        folder_id=fid,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    out_step = str(job_dir / (Path(file.filename).stem + ".step"))
    result = convert(str(src), out_step, mode=mode)

    if result["ok"]:
        job.status = "done"
        job.result_step_path = out_step
        job.result_faces = result["faces"]
        job.result_size_bytes = result["result_size"]
        job.processing_time_s = round(time.time() - t0, 1)
        job.completed_at = datetime.utcnow()
        job.credits_used = 0
        # try to store a JPG preview if converter produced one alongside — ponytail: no render yet, keep field null
        db.commit()
        return {
            "ok": True,
            "job_id": job.id,
            "uuid": job_uuid,
            "faces": result["faces"],
            "step_size_kb": result["result_size"] // 1024,
            "time_s": job.processing_time_s,
            "mode": mode,
            "filename": Path(file.filename).stem + ".step",
            "slug": job.slug,
            "vanity": f"/u/{user.username}/{job.slug}" if user and getattr(user,"username",None) and job.slug else None,
            "visibility": job.visibility,
        }
    else:
        job.status = "error"
        job.error_msg = result["error"][:2000]
        db.commit()
        raise HTTPException(500, result["error"][:500])


@router.get("/download/{job_uuid}")
def download(job_uuid: str, format: str = "step", db: Session = Depends(get_db)):
    job = db.query(models.Job).filter(models.Job.uuid == job_uuid, models.Job.status == "done").first()
    if not job:
        raise HTTPException(404, "Job nie znaleziony")
    fmt = format.lower()
    if fmt == "3mf":
        # find original 3mf if exists, else 404 — ponytail: no on-fly 3MF export, serve source
        src_dir = JOBS_DIR / job_uuid
        if src_dir.exists():
            for f in src_dir.iterdir():
                if f.suffix.lower() == ".3mf":
                    return FileResponse(str(f), filename=Path(job.original_filename).stem + ".3mf", media_type="application/vnd.ms-package.3dmanufacturing-3dmodel+xml")
        raise HTTPException(404, "Plik 3MF niedostępny — wgraj źródło .3mf")
    if fmt == "stl" and job.result_stl_path and os.path.exists(job.result_stl_path):
        path = job.result_stl_path
    else:
        path = job.result_step_path
    if not path or not os.path.exists(path):
        raise HTTPException(404, "Plik nie istnieje")
    return FileResponse(
        path,
        filename=Path(job.original_filename).stem + f".{fmt if fmt in ('step','stl') else 'step'}",
        media_type="application/step" if fmt == "step" else "application/octet-stream",
    )


@router.get("/stl-preview/{job_uuid}")
def stl_preview(job_uuid: str, db: Session = Depends(get_db)):
    """Return the original mesh (STL/3MF/OBJ) for Three.js preview."""
    job = db.query(models.Job).filter(
        models.Job.uuid == job_uuid, models.Job.status == "done"
    ).first()
    if not job:
        raise HTTPException(404, "Job nie znaleziony")

    stl_path = job.result_stl_path
    src_dir = JOBS_DIR / job_uuid
    if stl_path and os.path.exists(stl_path):
        return FileResponse(stl_path, media_type="model/stl")
    if src_dir.exists():
        for ext in (".stl", ".3mf", ".obj"):
            for f in src_dir.iterdir():
                if f.suffix.lower() == ext:
                    mt = "model/stl" if ext == ".stl" else "application/octet-stream"
                    return FileResponse(str(f), media_type=mt)
    raise HTTPException(404, "STL preview niedostępny")

@router.get("/preview/{job_uuid}")
def preview_image(job_uuid: str, db: Session = Depends(get_db)):
    """Serve JPG preview if exists, else 404 — frontend falls back to 3D thumb."""
    job = db.query(models.Job).filter(models.Job.uuid == job_uuid).first()
    if not job:
        raise HTTPException(404, "Job nie znaleziony")
    if job.preview_image and os.path.exists(job.preview_image):
        return FileResponse(job.preview_image, media_type="image/jpeg")
    # try JOBS_DIR preview
    p = JOBS_DIR / job_uuid / "preview.jpg"
    if p.exists():
        return FileResponse(str(p), media_type="image/jpeg")
    raise HTTPException(404, "Preview nie istnieje")


# --- Share links ---
@router.post("/share")
def create_share(
    job_id: int = Form(...),
    fmt: str = Form("step"),
    expires_days: int = Form(7),
    show_author: bool = Form(True),
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
        show_author=show_author,
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
    ).order_by(models.Job.created_at.desc()).limit(500).all()
    out=[]
    for j in jobs:
        out.append({"id": j.id, "uuid": j.uuid, "filename": j.original_filename, "title": j.title, "status": j.status,
             "mode": j.mode, "faces": j.result_faces, "processing_time_s": j.processing_time_s,
             "created_at": str(j.created_at), "folder_id": j.folder_id, "preview_image": j.preview_image,
             "visibility": j.visibility, "slug": j.slug, "file_size_bytes": j.file_size_bytes, "result_size_bytes": j.result_size_bytes})
    return out


# --- Bulk delete ---
@router.post("/jobs/bulk-delete")
def bulk_delete(payload: dict, user: models.User = Depends(require_user), db: Session = Depends(get_db)):
    ids = payload.get("ids") or []
    if not isinstance(ids, list) or not ids:
        raise HTTPException(400, "ids wymagane")
    ids = [int(x) for x in ids if str(x).isdigit()][:100]
    jobs = db.query(models.Job).filter(models.Job.user_id == user.id, models.Job.id.in_(ids)).all()
    for job in jobs:
        db.query(models.ShareLink).filter(models.ShareLink.job_id == job.id).delete()
        job_dir = JOBS_DIR / job.uuid
        if job_dir.is_dir():
            shutil.rmtree(job_dir, ignore_errors=True)
        db.delete(job)
    db.commit()
    return {"ok": True, "deleted": len(jobs)}

# --- Rename ---
@router.patch("/jobs/{job_id}/rename")
def rename_job(job_id: int, payload: dict, user: models.User = Depends(require_user), db: Session = Depends(get_db)):
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job or (job.user_id != user.id and not user.is_admin):
        raise HTTPException(404, "Job nie znaleziony")
    title = (payload.get("title") or payload.get("name") or "").strip()[:200]
    if not title:
        raise HTTPException(400, "Nazwa wymagana")
    job.title = title
    # optional folder move
    if "folder_id" in payload:
        fid = payload.get("folder_id")
        if fid in (None, "", 0, "0"):
            job.folder_id = None
        else:
            try:
                fid = int(fid)
                f = db.query(models.Folder).filter(models.Folder.id==fid, models.Folder.user_id==user.id).first()
                if not f:
                    raise HTTPException(404, "Folder nie znaleziony")
                job.folder_id = fid
            except HTTPException:
                raise
            except:
                raise HTTPException(400, "folder_id int")
    db.commit()
    return {"ok": True, "title": job.title, "folder_id": job.folder_id}

# --- Share per job ---
@router.post("/jobs/{job_id}/share")
def share_job(job_id: int, payload: dict = None, user: models.User = Depends(require_user), db: Session = Depends(get_db)):
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job or (job.user_id != user.id and not user.is_admin):
        raise HTTPException(404, "Job nie znaleziony")
    token = uuid.uuid4().hex[:16]
    share = models.ShareLink(token=token, job_id=job.id, user_id=user.id, format="step", show_author=True)
    db.add(share); db.commit()
    vanity = None
    if job.slug and user.username:
        vanity = f"{settings.APP_URL}/u/{user.username}/{job.slug}"
    share_url = vanity or f"{settings.APP_URL}/s/{token}"
    return {"url": share_url, "token": token, "vanity": vanity, "visibility": job.visibility}

# --- Publish toggle ---
@router.patch("/jobs/{job_id}/publish")
def publish_job(job_id: int, payload: dict, user: models.User = Depends(require_user), db: Session = Depends(get_db)):
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job or (job.user_id != user.id and not user.is_admin):
        raise HTTPException(404, "Job nie znaleziony")
    vis = payload.get("visibility")
    if vis not in ("public","private","unlisted"):
        # toggle
        vis = "private" if job.visibility == "public" else "public"
    job.visibility = vis
    db.commit()
    return {"ok": True, "visibility": job.visibility}

# --- User delete own job ---
@router.delete("/jobs/{job_id}")
def delete_my_job(
    job_id: int,
    user: models.User = Depends(require_user),
    db: Session = Depends(get_db),
):
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    if job.user_id != user.id and not user.is_admin:
        raise HTTPException(403, "Not your job")
    db.query(models.ShareLink).filter(models.ShareLink.job_id == job.id).delete()
    db.query(models.Comment).filter(models.Comment.job_id == job.id).delete()
    jobs_dir = Path(settings.DATA_DIR) / "files"
    job_dir = jobs_dir / job.uuid
    if job_dir.is_dir():
        shutil.rmtree(job_dir, ignore_errors=True)
    db.delete(job)
    db.commit()
    return {"ok": True}
