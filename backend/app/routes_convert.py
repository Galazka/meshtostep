"""Conversion routes: upload, convert, download, share. — 3dfile.link"""
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


def _auto_thumb(mesh_file: str, thumb_path):
    """Render mesh to 500x375 PNG via trimesh+matplotlib (Agg)."""
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    import trimesh
    # ponytail: trimesh handles STL natively; OBJ/3MF need force="mesh" + process
    try:
        mesh = trimesh.load(mesh_file, force="mesh")
    except Exception:
        # fallback: try without force, then concatenate if scene
        scene = trimesh.load(mesh_file)
        if hasattr(scene, 'geometry') and scene.geometry:
            mesh = trimesh.util.concatenate(list(scene.geometry.values()))
        else:
            raise
    fig = plt.figure(figsize=(4, 3), dpi=125)
    ax = fig.add_subplot(111, projection="3d")
    ax.set_facecolor("#f0f2f5"); fig.patch.set_facecolor("#f0f2f5")
    verts = mesh.vertices; faces = mesh.faces
    if len(faces) > 8000:
        import numpy as np
        faces = faces[np.random.choice(len(faces), 8000, replace=False)]
    poly = Poly3DCollection(verts[faces], alpha=0.9, facecolor="#3b82f6", edgecolor="#1e40af", linewidths=0.1)
    ax.add_collection3d(poly)
    ax.auto_scale_xyz(verts[:,0], verts[:,1], verts[:,2])
    ax.view_init(elev=20, azim=45); ax.set_axis_off()
    plt.tight_layout(pad=0)
    fig.savefig(str(thumb_path), dpi=125, facecolor="#f0f2f5", bbox_inches="tight", pad_inches=0)
    plt.close(fig)

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

    # ── hosting-first: upload bez FreeCAD, thumb + dims z trimesh ──
    stl_file = str(src)
    try:
        import trimesh
        m = trimesh.load(stl_file, force="mesh")
        if hasattr(m, 'bounds') and m.bounds is not None:
            bmin, bmax = m.bounds
            d = bmax - bmin
            job.dims_mm = f"{round(float(d[0]),1)} x {round(float(d[1]),1)} x {round(float(d[2]),1)} mm"
        if hasattr(m, 'faces'):
            job.result_faces = len(m.faces)
        # volume for filament calculator
        try:
            vol = m.volume if hasattr(m, 'volume') else 0
            job.volume_cm3 = round(float(vol) / 1000, 3)  # mm³ → cm³
        except Exception:
            pass
    except Exception: pass
    try:
        thumb_out = job_dir / "thumb.png"
        if not thumb_out.exists():
            _auto_thumb(stl_file, thumb_out)
    except Exception: pass
    job.status = "hosted"
    job.processing_time_s = round(time.time() - t0, 1)
    job.completed_at = datetime.utcnow()
    db.commit()
    return {
        "ok": True, "job_id": job.id, "uuid": job_uuid,
        "faces": job.result_faces or 0, "step_size_kb": 0,
        "time_s": job.processing_time_s, "mode": mode,
        "filename": file.filename, "slug": job.slug,
        "vanity": f"/u/{user.username}/{job.slug}" if user and getattr(user,"username",None) and job.slug else None,
        "visibility": job.visibility, "hosted": True,
    }


@router.post("/convert-on-demand/{job_uuid}")
def convert_on_demand(job_uuid: str, mode: str = "auto", db: Session = Depends(get_db)):
    """Konwersja mesh→STEP na żądanie (przy pobieraniu). Hosting-first: zero CPU na upload."""
    job = db.query(models.Job).filter(models.Job.uuid == job_uuid).first()
    if not job:
        raise HTTPException(404, "Job nie znaleziony")
    # już przekonwertowany → zwróć od razu
    if job.status == "done" and job.result_step_path and os.path.exists(job.result_step_path):
        sz = os.path.getsize(job.result_step_path)
        return {"ok": True, "cached": True, "uuid": job_uuid, "step_size_kb": sz // 1024}
    t0 = time.time()
    job_dir = JOBS_DIR / job_uuid
    src = None
    if job_dir.exists():
        for ext in (".stl", ".3mf", ".obj", ".step"):
            for f in job_dir.iterdir():
                if f.suffix.lower() == ext and f.suffix.lower() != ".step":
                    src = str(f); break
            if src: break
    if not src:
        raise HTTPException(404, "Plik źródłowy niedostępny")
    job.status = "converting"
    db.commit()
    out_step = str(job_dir / (Path(job.original_filename).stem + ".step"))
    result = convert(src, out_step, mode=mode)
    if result["ok"]:
        job.status = "done"
        job.result_step_path = out_step
        job.result_faces = result["faces"]
        job.result_size_bytes = result["result_size"]
        job.processing_time_s = round(time.time() - t0, 1)
        job.completed_at = datetime.utcnow()
        db.commit()
        return {"ok": True, "cached": False, "uuid": job_uuid,
                "step_size_kb": result["result_size"] // 1024,
                "time_s": job.processing_time_s}
    job.status = "error"
    job.error_msg = result["error"][:2000]
    db.commit()
    raise HTTPException(500, result["error"][:500])


@router.get("/download/{job_uuid}")
def download(job_uuid: str, format: str = "step", db: Session = Depends(get_db)):
    job = db.query(models.Job).filter(models.Job.uuid == job_uuid).first()
    if not job:
        raise HTTPException(404, "Job nie znaleziony")
    # hosting-first: oryginał dostępny od razu niezależnie od statusu
    fmt = format.lower()
    if fmt == "3mf" or fmt == "obj":
        src_dir = JOBS_DIR / job_uuid
        if src_dir.exists():
            for f in src_dir.iterdir():
                if f.suffix.lower() == "." + fmt:
                    mt = "application/octet-stream"
                    return FileResponse(str(f), filename=Path(job.original_filename).stem + f".{fmt}", media_type=mt)
        if fmt == "3mf":
            raise HTTPException(404, "Plik 3MF niedostępny")
    if fmt == "stl":
        src_dir = JOBS_DIR / job_uuid
        if src_dir.exists():
            for f in src_dir.iterdir():
                if f.suffix.lower() == ".stl":
                    return FileResponse(str(f), filename=Path(job.original_filename).stem + ".stl", media_type="model/stl")
        if job.result_stl_path and os.path.exists(job.result_stl_path):
            return FileResponse(job.result_stl_path, filename=Path(job.original_filename).stem + ".stl", media_type="model/stl")
        raise HTTPException(404, "Plik STL niedostępny")
    # STEP: wymaga konwersji
    if fmt == "step":
        if job.status == "done" and job.result_step_path and os.path.exists(job.result_step_path):
            return FileResponse(job.result_step_path, filename=Path(job.original_filename).stem + ".step", media_type="application/step")
        if job.status == "hosted":
            raise HTTPException(400, "STEP nie gotowy — najpierw POST /api/convert-on-demand/{uuid}")
        raise HTTPException(404, "STEP nie istnieje")
    raise HTTPException(400, f"Nieznany format: {fmt}")


@router.get("/stl-preview/{job_uuid}")
def stl_preview(job_uuid: str, db: Session = Depends(get_db)):
    """Return the original mesh (STL/3MF/OBJ) for Three.js preview."""
    job = db.query(models.Job).filter(
        models.Job.uuid == job_uuid
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
    # No mesh file at all
    raise HTTPException(404, "STL preview niedostepny")

@router.get("/preview/{job_uuid}")
def preview_image(job_uuid: str, db: Session = Depends(get_db)):
    """Serve JPG preview → auto-gen thumb from mesh → 404 only if no mesh at all."""
    job = db.query(models.Job).filter(models.Job.uuid == job_uuid).first()
    if not job:
        raise HTTPException(404, "Job nie znaleziony")
    # 1) stored preview
    if job.preview_image and os.path.exists(job.preview_image):
        return FileResponse(job.preview_image, media_type="image/jpeg")
    # 2) preview.jpg in job dir
    jp = JOBS_DIR / job_uuid / "preview.jpg"
    if jp.exists():
        return FileResponse(str(jp), media_type="image/jpeg")
    # 3) cached thumb.png
    tp = JOBS_DIR / job_uuid / "thumb.png"
    if tp.exists():
        return FileResponse(str(tp), media_type="image/png")
    # 4) auto-generate thumb from mesh on the fly (trimesh+matplotlib)
    src_dir = JOBS_DIR / job_uuid
    if src_dir.exists():
        mesh_file = None
        for ext in (".stl", ".3mf", ".obj", ".step"):
            for f in src_dir.iterdir():
                if f.suffix.lower() == ext:
                    mesh_file = str(f); break
            if mesh_file: break
        if mesh_file:
            try:
                _auto_thumb(mesh_file, str(tp))
                return FileResponse(str(tp), media_type="image/png")
            except Exception:
                pass
    # 5) 1x1 placeholder PNG so img tag doesn't break
    import io
    placeholder = io.BytesIO(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82')
    from starlette.responses import StreamingResponse
    placeholder.seek(0)
    return StreamingResponse(placeholder, media_type="image/png")


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
    if not src_dir.exists():
        # job dir doesn't exist — return logo as placeholder
        logo = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "logo.png")
        if os.path.exists(logo):
            return FileResponse(logo, media_type="image/png")
        raise HTTPException(404, "Job dir niedostepny")
    mesh_file = None
    if src_dir.exists():
        for ext in (".stl", ".3mf", ".obj"):
            for f in src_dir.iterdir():
                if f.suffix.lower() == ext:
                    mesh_file = str(f); break
            if mesh_file: break
    if not mesh_file:
        # fallback: return logo as thumbnail placeholder
        logo = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "logo.png")
        if os.path.exists(logo):
            return FileResponse(logo, media_type="image/png")
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
        # Auto-convert hosted job on first download
        job_dir = JOBS_DIR / job.uuid
        src = None
        if job_dir.exists():
            for ext in (".stl", ".3mf", ".obj"):
                for f in job_dir.iterdir():
                    if f.suffix.lower() == ext:
                        src = str(f); break
                if src: break
        if not src:
            raise HTTPException(404, "Plik usuniety")
        dst_step = str(job_dir / "result.step")
        from .engine import convert as _engine_convert
        job.status = "converting"
        db.commit()
        res = _engine_convert(src, dst_step, mode=job.mode or "auto")
        if not res.get("ok"):
            job.status = "hosted"
            db.commit()
            raise HTTPException(500, "Konwersja nieudana")
        job.status = "done"
        job.result_step_path = dst_step
        job.result_faces = res.get("faces", job.result_faces)
        job.result_size_bytes = os.path.getsize(dst_step) if os.path.exists(dst_step) else job.result_size_bytes
        job.completed_at = datetime.utcnow()
        db.commit()
        path = dst_step

    share.downloads += 1
    db.commit()

    fmt = share.format
    ext = "step" if fmt == "step" else "stl"
    return FileResponse(
        path,
        filename=Path(job.original_filename).stem + f".{ext}",
        media_type="application/step" if ext == "step" else "application/octet-stream",
    )


# --- Material / filament estimate ---
MATERIALS = {"PLA": 1.24, "PETG": 1.27, "ABS": 1.04, "TPU": 1.21, "ASA": 1.07}
FILAMENT_PRICE_PLN_G = 0.12  # ~120 PLN/kg avg


@router.get("/material/{job_uuid}")
def material_estimate(job_uuid: str, db: Session = Depends(get_db)):
    """Estimate filament weight + cost from mesh volume."""
    job = db.query(models.Job).filter(models.Job.uuid == job_uuid).first()
    if not job:
        raise HTTPException(404, "Job nie znaleziony")
    vol = job.volume_cm3
    if not vol:
        # lazy compute from mesh on disk
        src_dir = JOBS_DIR / job_uuid
        mesh_file = None
        if src_dir.exists():
            for ext in (".stl", ".3mf", ".obj"):
                for f in src_dir.iterdir():
                    if f.suffix.lower() == ext:
                        mesh_file = str(f); break
                if mesh_file: break
        if mesh_file:
            try:
                import trimesh
                m = trimesh.load(mesh_file, force="mesh")
                vol = round(float(m.volume) / 1000, 3) if hasattr(m, "volume") else 0
                job.volume_cm3 = vol
                db.commit()
            except Exception:
                pass
    if not vol:
        raise HTTPException(404, "Brak danych objetosci")
    out = {"volume_cm3": vol, "dims_mm": job.dims_mm, "estimates": {}}
    for mat, density in MATERIALS.items():
        for infill in (10, 20, 50, 100):
            w_g = round(vol * density * (infill / 100), 1)
            out["estimates"][f"{mat}_{infill}"] = {
                "weight_g": w_g,
                "cost_pln": round(w_g * FILAMENT_PRICE_PLN_G, 2),
            }
    return out


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
             "created_at": str(j.created_at), "folder_id": j.folder_id, "preview_image": f"/api/preview/{j.uuid}",
             "visibility": j.visibility, "slug": j.slug, "file_size_bytes": j.file_size_bytes, "result_size_bytes": j.result_size_bytes, "dims_mm": j.dims_mm,
             "views": j.views or 0, "likes": j.likes or 0, "description": (j.description or "")[:5000], "tags": j.tags or [], "youtube_url": j.youtube_url or ""})
    return out



# --- Email share link ---
@router.post("/share/{token}/email")
def email_share(token: str, payload: dict, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    from .mail import send_share_link
    recipient = (payload.get("recipient_email") or "").strip()
    if not recipient or "@" not in recipient:
        raise HTTPException(400, "Podaj poprawny email")
    # rate limit: 5 emails/min per user
    key = f"email_{user.id}"
    hits = _email_hits.get(key, [])
    now = time.time()
    hits = [h for h in hits if now - h < 60]
    if len(hits) >= 5:
        raise HTTPException(429, "Za dużo wiadomości — poczekaj chwilę")
    hits.append(now)
    _email_hits[key] = hits
    # find share link + job
    share = db.query(models.ShareLink).filter(models.ShareLink.token == token).first()
    if not share:
        raise HTTPException(404, "Link nie znaleziony")
    job = db.query(models.Job).filter(models.Job.id == share.job_id).first()
    title = getattr(job, "title", None) or getattr(job, "original_filename", "Model 3D")
    sent = send_share_link(recipient, token, getattr(user, "email", ""), title)
    if not sent:
        raise HTTPException(500, "SMTP nie skonfigurowane — nie wysłano")
    return {"ok": True, "message": f"Wysłano do {recipient}"}


_email_hits: dict = {}

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
    # extended: accept title + description/tags/youtube_url/visibility/folder_id/slug
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
    return {"ok": True, "title": job.title, "slug": job.slug, "folder_id": job.folder_id, "visibility": job.visibility, "description": job.description, "tags": job.tags, "youtube_url": job.youtube_url, "updated": updated}


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
