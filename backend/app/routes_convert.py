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

QUOTA_DEFAULT = 100 * 1024 * 1024

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
            raise HTTPException(413, f"Przekroczono limit 100 MB. Zwolnij miejsce usuwając pliki.")
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
        # Calculate dimensions from STL bounding box
        try:
            stl_dir = os.path.join(JOBS_DIR, job.uuid)
            stl_file = None
            for fn in os.listdir(stl_dir):
                if fn.lower().endswith(('.stl','.3mf','.obj')):
                    stl_file = os.path.join(stl_dir, fn); break
            if stl_file:
                import struct
                with open(stl_file, 'rb') as f:
                    header = f.read(80)
                    num_triangles = struct.unpack('<I', f.read(4))[0]
                    min_x=min_y=min_z=float('inf'); max_x=max_y=max_z=float('-inf')
                    for _ in range(min(num_triangles, 500000)):
                        f.read(12)  # normal
                        for _ in range(3):
                            x,y,z = struct.unpack('<fff', f.read(12))
                            min_x=min(min_x,x); max_x=max(max_x,x)
                            min_y=min(min_y,y); max_y=max(max_y,y)
                            min_z=min(min_z,z); max_z=max(max_z,z)
                        f.read(2)  # attr
                    dims_str = f"{round(max_x-min_x,1)} x {round(max_y-min_y,1)} x {round(max_z-min_z,1)} mm"
                    job.dims_mm = dims_str
        except Exception: pass
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


# --- Server-side STL thumbnail (trimesh + matplotlib) ---
@router.get("/thumb/{job_uuid}")
def stl_thumbnail(job_uuid: str, db: Session = Depends(get_db)):
    """Render STL to PNG thumbnail server-side. Cached as thumb.png in JOBS_DIR/uuid/."""
    job = db.query(models.Job).filter(models.Job.uuid == job_uuid).first()
    if not job:
        raise HTTPException(404, "Job nie znaleziony")
    thumb_path = JOBS_DIR / job_uuid / "thumb.png"
    if thumb_path.exists():
        return FileResponse(str(thumb_path), media_type="image/png")
    # find mesh file
    src_dir = JOBS_DIR / job_uuid
    mesh_file = None
    if src_dir.exists():
        for ext in (".stl", ".3mf", ".obj"):
            for f in src_dir.iterdir():
                if f.suffix.lower() == ext:
                    mesh_file = str(f); break
            if mesh_file: break
    if not mesh_file:
        raise HTTPException(404, "Mesh niedostepny")
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection
        import trimesh
        mesh = trimesh.load(mesh_file, force="mesh")
        fig = plt.figure(figsize=(4, 3), dpi=100)
        ax = fig.add_subplot(111, projection="3d")
        ax.set_facecolor("#f0f2f5")
        fig.patch.set_facecolor("#f0f2f5")
        verts = mesh.vertices
        faces = mesh.faces
        # downsample for speed
        if len(faces) > 8000:
            import numpy as np
            idx = np.random.choice(len(faces), 8000, replace=False)
            faces = faces[idx]
        poly = Poly3DCollection(verts[faces], alpha=0.9, facecolor="#3b82f6", edgecolor="#1e40af", linewidths=0.1)
        ax.add_collection3d(poly)
        # auto-scale
        ax.auto_scale_xyz(verts[:,0], verts[:,1], verts[:,2])
        ax.view_init(elev=20, azim=45)
        ax.set_axis_off()
        plt.tight_layout(pad=0)
        thumb_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(str(thumb_path), dpi=100, bbox_inches="tight", facecolor="#f0f2f5", pad_inches=0.1)
        plt.close(fig)
        return FileResponse(str(thumb_path), media_type="image/png")
    except Exception as e:
        raise HTTPException(500, f"Thumbnail error: {e}")


@router.post("/jobs/{job_uuid}/preview")
async def upload_preview(
    job_uuid: str,
    preview: UploadFile = File(...),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Accept canvas screenshot (image/jpeg or image/png) and save as JOBS_DIR/uuid/preview.jpg"""
    job = db.query(models.Job).filter(models.Job.uuid == job_uuid).first()
    if not job:
        raise HTTPException(404, "Job nie znaleziony")
    # ownership check if logged — allow anon uploads for anon jobs, require owner for owned jobs
    if job.user_id is not None:
        if not user or (job.user_id != user.id and not getattr(user, "is_admin", False)):
            raise HTTPException(403, "Brak uprawnien")
    ctype = (preview.content_type or "").lower()
    if ctype not in ("image/jpeg", "image/jpg", "image/png", "image/webp", "application/octet-stream"):
        # still accept — frontend sends jpeg; be permissive
        pass
    data = await preview.read()
    if not data or len(data) < 100:
        raise HTTPException(400, "Pusty plik preview")
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(400, "Preview > 5 MB")
    job_dir = JOBS_DIR / job_uuid
    job_dir.mkdir(parents=True, exist_ok=True)
    out = job_dir / "preview.jpg"
    # if png/webp, try to convert via PIL else just save; ponytail: no PIL dep required — save raw bytes as jpg path, browsers handle it
    # if PIL available, convert to JPEG for consistency
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(data))
        if img.mode in ("RGBA", "LA", "P"):
            bg = Image.new("RGB", img.size, (247, 249, 252))
            if img.mode == "P":
                img = img.convert("RGBA")
            bg.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
            img = bg
        elif img.mode != "RGB":
            img = img.convert("RGB")
        img.save(str(out), "JPEG", quality=85)
    except Exception:
        # fallback: write raw bytes
        out.write_bytes(data)
    job.preview_image = str(out)
    db.commit()
    return {"ok": True, "preview": f"/api/preview/{job_uuid}"}




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

# --- Author stats ---
@router.get("/jobs-author-stats")
def author_stats(user: models.User = Depends(require_user), db: Session = Depends(get_db)):
    """Return author-specific statistics."""
    jobs = db.query(models.Job).filter(models.Job.user_id == user.id).all()
    total_models = len(jobs)
    total_views = sum(j.views or 0 for j in jobs)
    total_likes = sum(j.likes or 0 for j in jobs)
    public_models = sum(1 for j in jobs if j.visibility == "public")
    done_models = sum(1 for j in jobs if j.status == "done")
    total_size = sum(j.file_size_bytes or 0 for j in jobs)
    return {"total_models": total_models, "done_models": done_models, "public_models": public_models, "total_views": total_views, "total_likes": total_likes, "total_size_bytes": total_size}


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
             "visibility": j.visibility, "slug": j.slug, "file_size_bytes": j.file_size_bytes, "result_size_bytes": j.result_size_bytes, "dims_mm": j.dims_mm,
             "views": j.views or 0, "likes": j.likes or 0, "description": (j.description or "")[:5000], "tags": j.tags or [], "youtube_url": j.youtube_url or "", "is_paid": j.is_paid, "price_cents": j.price_cents})
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
    # extended: accept title + description/tags/youtube_url/visibility/is_paid/price_cents/folder_id/slug
    updated = {}
    if "title" in payload or "name" in payload:
        title = (payload.get("title") or payload.get("name") or "").strip()[:200]
        if title:
            job.title = title
            # also update slug if title changed and no explicit slug
            if "slug" not in payload:
                new_slug = _slugify(title)
                # ensure unique per user
                base = new_slug; k = 1
                while db.query(models.Job).filter(models.Job.user_id==job.user_id, models.Job.slug==new_slug, models.Job.id!=job.id).first() is not None:
                    k+=1; new_slug=f"{base}-{k}"
                job.slug = new_slug
            updated["title"] = job.title
            updated["slug"] = job.slug
        elif "title" in payload:
            raise HTTPException(400, "Nazwa wymagana")
    if "slug" in payload:
        s = _slugify(payload.get("slug") or "")
        base=s; k=1
        while db.query(models.Job).filter(models.Job.user_id==job.user_id, models.Job.slug==s, models.Job.id!=job.id).first() is not None:
            k+=1; s=f"{base}-{k}"
        job.slug=s; updated["slug"]=s
    if "description" in payload:
        job.description = (payload.get("description") or "")[:10000]
        updated["description"] = job.description
    if "tags" in payload:
        raw = payload.get("tags") or ""
        if isinstance(raw, list):
            raw = ",".join(str(x) for x in raw)
        job.tags = ",".join([t.strip()[:40] for t in raw.split(",") if t.strip()])[:500]
        updated["tags"] = job.tags
    if "youtube_url" in payload:
        job.youtube_url = (payload.get("youtube_url") or "")[:512] or None
        updated["youtube_url"] = job.youtube_url
    if "visibility" in payload:
        v = payload.get("visibility")
        if v in ("public","private","unlisted"):
            job.visibility = v
            updated["visibility"] = v
    if "is_paid" in payload:
        job.is_paid = bool(payload.get("is_paid"))
        updated["is_paid"] = job.is_paid
    if "price_cents" in payload:
        try:
            pc = int(payload.get("price_cents") or 0)
            pc = max(0, min(pc, 9999999))
            job.price_cents = pc
            updated["price_cents"] = pc
        except Exception:
            raise HTTPException(400, "price_cents int")
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
        updated["folder_id"] = job.folder_id
    if not updated and "title" not in payload and "name" not in payload:
        # no recognized fields — require at least one
        raise HTTPException(400, "Brak pol do aktualizacji")
    db.commit()
    db.refresh(job)
    return {"ok": True, "title": job.title, "slug": job.slug, "folder_id": job.folder_id, "visibility": job.visibility, "description": job.description, "tags": job.tags, "youtube_url": job.youtube_url, "is_paid": job.is_paid, "price_cents": job.price_cents, "updated": updated}


@router.patch("/jobs/{job_id}/meta")
def update_job_meta(job_id: int, payload: dict, user: models.User = Depends(require_user), db: Session = Depends(get_db)):
    """Alias for rename with full meta fields — keeps frontend compat."""
    return rename_job(job_id, payload, user, db)

# --- Share per job ---
@router.post("/jobs/{job_id}/share")
def share_job(job_id: int, payload: dict = None, user: models.User = Depends(require_user), db: Session = Depends(get_db)):
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job or (job.user_id != user.id and not user.is_admin):
        raise HTTPException(404, "Job nie znaleziony")
    token = uuid.uuid4().hex[:16]
    anon = (payload or {}).get("anon", False)
    show_author = (payload or {}).get("show_author", True)
    share = models.ShareLink(token=token, job_id=job.id, user_id=user.id, format="step", show_author=show_author)
    db.add(share); db.commit()
    vanity = None
    if job.slug and user.username and not anon:
        vanity = f"{settings.APP_URL}/u/{user.username}/{job.slug}"
    share_url = vanity or f"{settings.APP_URL}/s/{token}"
    return {"url": share_url, "token": token, "vanity": vanity, "visibility": job.visibility, "anon": anon}

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
