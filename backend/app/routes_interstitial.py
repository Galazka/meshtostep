"""Interstitial download page — 5s timer + ad before STEP download. — 3dfile.link"""
from pathlib import Path
import html as html_mod

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from . import models
from .config import settings
from .database import get_db

router = APIRouter(tags=["interstitial"])

INTERSTITIAL_HTML = """<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pobieranie — 3dfile.link</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Inter,-apple-system,sans-serif;background:#f8fafc;color:#1e293b;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center}
.card{background:#fff;border:1px solid #e2e8f0;border-radius:16px;padding:40px 32px;max-width:480px;width:90%;text-align:center;box-shadow:0 4px 24px rgba(0,0,0,.06)}
.logo{font-size:20px;font-weight:800;color:#1a56db;margin-bottom:24px}
.filename{font-size:16px;font-weight:600;color:#0f172a;margin-bottom:8px;word-break:break-all}
.meta{font-size:13px;color:#64748b;margin-bottom:24px}
.timer-ring{width:80px;height:80px;margin:0 auto 20px}
.timer-ring circle{fill:none;stroke-width:4}
.timer-ring .bg{stroke:#e2e8f0}
.timer-ring .fg{stroke:#1a56db;stroke-linecap:round;transform:rotate(-90deg);transform-origin:center;transition:stroke-dashoffset 1s linear}
.timer-text{font-size:28px;font-weight:700;fill:#1e293b}
.ad-slot{background:#f1f5f9;border:1px dashed #cbd5e1;border-radius:8px;min-height:90px;margin:16px 0;display:flex;align-items:center;justify-content:center;font-size:12px;color:#94a3b8}
.btn{display:inline-block;padding:14px 32px;background:#1a56db;color:#fff;text-decoration:none;border-radius:8px;font-size:15px;font-weight:600;transition:opacity .2s}
.btn:disabled{opacity:.3;pointer-events:none;background:#94a3b8}
.btn:hover:not(:disabled){background:#1e40af}
.brand{margin-top:24px;font-size:12px;color:#94a3b8}
.brand a{color:#1a56db;text-decoration:none}
</style>
</head>
<body>
<div class="card">
<div class="logo">3dfile.link</div>
<div class="filename">__FILENAME__</div>
<div class="meta">Format: STEP &middot; __SIZE__ &middot; Konwersja z __FORMAT_SRC__</div>
<svg class="timer-ring" viewBox="0 0 80 80">
<circle class="bg" cx="40" cy="40" r="36"/>
<circle class="fg" id="ring" cx="40" cy="40" r="36" stroke-dasharray="226.2" stroke-dashoffset="0"/>
<text class="timer-text" x="40" y="46" text-anchor="middle" id="countdown">5</text>
</svg>
<div class="ad-slot" id="interstitialAd"><span>Reklama</span></div>
<a class="btn" id="downloadBtn" href="__DOWNLOAD_URL__" disabled>Pobierz plik STEP</a>
<div class="brand">Powered by <a href="https://3dfile.link">3dfile.link</a></div>
</div>
<script>
(function(){
  var SEC=5,el=document.getElementById('countdown'),ring=document.getElementById('ring'),
      btn=document.getElementById('downloadBtn'),C=226.2;
  function tick(){
    if(SEC<=0){btn.disabled=false;btn.textContent='Pobierz plik STEP';ring.setAttribute('stroke-dashoffset','0');return;}
    el.textContent=SEC;ring.setAttribute('stroke-dashoffset',(C*(1-SEC/5)).toFixed(1));SEC--;setTimeout(tick,1000);
  }
  tick();
})();
</script>
</body>
</html>"""


@router.get("/download-step/{job_uuid}", response_class=HTMLResponse)
def interstitial_download(job_uuid: str, db: Session = Depends(get_db)):
    """Interstitial: 5s countdown + ad, then reveal STEP download."""
    job = db.query(models.Job).filter(models.Job.uuid == job_uuid).first()
    if not job:
        raise HTTPException(404, "Job nie znaleziony")
    if job.visibility == "private":
        raise HTTPException(403, "Prywatny model")
    filename = job.original_filename or "model"
    size_kb = (job.result_size_bytes or 0) // 1024
    size_str = f"{size_kb} KB" if size_kb < 1024 else f"{round(size_kb/1024, 1)} MB"
    src_ext = Path(job.original_filename).suffix.upper().lstrip(".")
    download_url = f"{settings.APP_URL}/api/download/{job_uuid}?format=step"
    html = INTERSTITIAL_HTML.replace("__FILENAME__", html_mod.escape(filename))
    html = html.replace("__SIZE__", size_str)
    html = html.replace("__FORMAT_SRC__", src_ext or "STL")
    html = html.replace("__DOWNLOAD_URL__", download_url)
    return HTMLResponse(html)
