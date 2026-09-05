"""Share link public page with 3D preview."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from .database import get_db
from . import models

router = APIRouter(tags=["share"])


@router.get("/s/{token}", response_class=HTMLResponse)
def share_page(token: str, db: Session = Depends(get_db)):
    share = db.query(models.ShareLink).filter(
        models.ShareLink.token == token, models.ShareLink.is_active == True
    ).first()
    if not share:
        return "<h1>Link nie istnieje</h1>", 404

    job = share.job
    return f"""<!DOCTYPE html>
<html lang="pl">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{job.original_filename} — MeshToStep</title>
<style>
body{{font:15px/1.6 system-ui;background:#08080f;color:#eee;margin:0;padding:32px 24px;text-align:center}}
.card{{max-width:500px;margin:0 auto;background:#111;border:1px solid #1a1a2e;border-radius:16px;padding:32px}}
h1{{font-size:20px;margin-bottom:8px}}
.info{{color:#666;font-size:13px;margin-bottom:24px}}
.btn{{display:inline-block;padding:12px 32px;background:linear-gradient(135deg,#00f0ff,#ff00ff);color:#000;font-weight:700;border-radius:8px;text-decoration:none;font-size:15px}}
.meta{{color:#666;font-size:12px;margin-top:16px}}
</style></head>
<body>
<div class="card">
<h1>📁 {job.original_filename}</h1>
<div class="info">
{job.result_faces or '?'} ścianek STEP · {job.mode} · {job.result_size_bytes // 1024 if job.result_size_bytes else '?'} KB<br>
Pobrano: {share.downloads} razy
</div>
<a class="btn" href="/api/share/{token}/download">⬇ Pobierz STEP</a>
<div class="meta">Wygenerowano przez MeshToStep · FreeCAD headless</div>
</div></body></html>"""
