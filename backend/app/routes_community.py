"""Community routes: vanity URL /u/{username}/{slug}, search, tags, model detail — 3dhosty.com"""
import re
import html
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from .database import get_db
from . import models
from .auth import get_current_user

router = APIRouter(tags=["community"])

def _slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r'[^a-z0-9]+', '-', s)
    s = re.sub(r'-+', '-', s).strip('-')
    return s[:80] or "model"

def _youtube_embed(url: str) -> Optional[str]:
    if not url:
        return None
    m = re.search(r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([A-Za-z0-9_-]{6,})', url)
    return m.group(1) if m else None

def _is_youtube_valid(url: str) -> bool:
    if not url:
        return True
    return _youtube_embed(url) is not None

# ---- API: search models ----
@router.get("/api/models")
def search_models(
    q: str = Query("", description="search query"),
    tag: str = Query("", description="filter by tag"),
    sort: str = Query("latest", description="latest|popular|price"),
    limit: int = Query(24, ge=1, le=60),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(models.Job).filter(
        models.Job.status == "done",
        models.Job.visibility == "public",
    )
    if q:
        like = f"%{q}%"
        query = query.filter(
            (models.Job.title.ilike(like)) |
            (models.Job.description.ilike(like)) |
            (models.Job.original_filename.ilike(like)) |
            (models.Job.tags.ilike(like))
        )
    if tag:
        query = query.filter(models.Job.tags.ilike(f"%{tag}%"))
    if sort == "popular":
        query = query.order_by(models.Job.views.desc(), models.Job.created_at.desc())
    elif sort == "price":
        query = query.order_by(models.Job.price_cents.asc())
    else:
        query = query.order_by(models.Job.created_at.desc())
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    out = []
    for j in items:
        username = j.user.username if j.user and getattr(j.user, "username", None) else (j.user.email.split("@")[0] if j.user else "anon")
        out.append({
            "id": j.id,
            "uuid": j.uuid,
            "slug": j.slug,
            "title": j.title or j.original_filename,
            "description": (j.description or "")[:200],
            "tags": [t.strip() for t in (j.tags or "").split(",") if t.strip()],
            "youtube_url": j.youtube_url,
            "visibility": j.visibility,
            "views": j.views or 0,
            "likes": j.likes or 0,
            "is_paid": bool(j.is_paid),
            "price_cents": j.price_cents or 0,
            "faces": j.result_faces,
            "created_at": str(j.created_at),
            "vanity": f"/u/{username}/{j.slug}" if j.slug and username != "anon" else f"/s/{j.uuid}",
            "username": username,
        })
    return {"total": total, "items": out}

@router.get("/api/tags")
def list_tags(db: Session = Depends(get_db)):
    rows = db.query(models.Job.tags).filter(models.Job.visibility == "public", models.Job.status == "done").all()
    counter = {}
    for (tags,) in rows:
        if not tags:
            continue
        for t in tags.split(","):
            t = t.strip().lower()
            if t:
                counter[t] = counter.get(t, 0) + 1
    sorted_tags = sorted(counter.items(), key=lambda x: -x[1])[:50]
    return [{"tag": k, "count": v} for k, v in sorted_tags]

@router.get("/api/models/{job_id}")
def get_model(job_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    j = db.query(models.Job).filter(models.Job.id == job_id, models.Job.status == "done").first()
    if not j:
        raise HTTPException(404, "Model nie znaleziony")
    if j.visibility == "private" and (not user or (j.user_id != user.id and not user.is_admin)):
        raise HTTPException(403, "Prywatny model")
    # increment views only for public/unlisted
    j.views = (j.views or 0) + 1
    db.commit()
    username = j.user.username if j.user and getattr(j.user, "username", None) else (j.user.email.split("@")[0] if j.user else "anon")
    return {
        "id": j.id, "uuid": j.uuid, "slug": j.slug,
        "title": j.title or j.original_filename,
        "description": j.description or "",
        "tags": [t.strip() for t in (j.tags or "").split(",") if t.strip()],
        "youtube_url": j.youtube_url,
        "youtube_id": _youtube_embed(j.youtube_url or ""),
        "visibility": j.visibility,
        "views": j.views, "likes": j.likes or 0,
        "is_paid": bool(j.is_paid), "price_cents": j.price_cents or 0,
        "faces": j.result_faces, "mode": j.mode,
        "original_filename": j.original_filename,
        "created_at": str(j.created_at),
        "username": username,
        "vanity": f"/u/{username}/{j.slug}" if j.slug else None,
    }

@router.patch("/api/models/{job_id}")
def update_model(job_id: int, payload: dict, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    from fastapi import HTTPException as HE
    if not user:
        raise HE(401, "Zaloguj sie")
    j = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not j:
        raise HE(404, "Model nie znaleziony")
    if j.user_id != user.id and not user.is_admin:
        raise HE(403, "Nie twoj model")
    # fields
    if "title" in payload:
        j.title = str(payload["title"])[:200] if payload["title"] else None
    if "description" in payload:
        j.description = str(payload["description"])[:5000] if payload["description"] else None
    if "tags" in payload:
        tags = str(payload["tags"])[:500]
        # normalize
        parts = [re.sub(r'[^a-z0-9-]', '', t.strip().lower()) for t in tags.split(",")]
        parts = [p for p in parts if p][:10]
        j.tags = ",".join(parts) if parts else None
    if "youtube_url" in payload:
        url = (payload["youtube_url"] or "").strip()[:512]
        if url and not _is_youtube_valid(url):
            raise HE(400, "Nieprawidlowy YouTube URL")
        j.youtube_url = url or None
    if "visibility" in payload:
        v = payload["visibility"]
        if v not in ("public", "unlisted", "private"):
            raise HE(400, "visibility: public/unlisted/private")
        j.visibility = v
        # also sync first share link if exists
        if j.shares:
            j.shares[0].visibility = v
    if "slug" in payload:
        raw = str(payload["slug"] or "").strip()
        slug = _slugify(raw) if raw else None
        if slug:
            # collision per user
            q = db.query(models.Job).filter(models.Job.user_id == user.id, models.Job.slug == slug, models.Job.id != j.id).first()
            if q:
                raise HE(409, "Slug zajety")
            j.slug = slug
    if "is_paid" in payload:
        j.is_paid = bool(payload["is_paid"])
    if "price_cents" in payload:
        try:
            pc = int(payload["price_cents"])
        except:
            raise HE(400, "price_cents int")
        if pc < 0 or pc > 1000000:
            raise HE(400, "Cena poza zakresem")
        j.price_cents = pc
        if pc > 0:
            j.is_paid = True
    db.commit()
    return {"ok": True, "slug": j.slug, "visibility": j.visibility}

# ---- Vanity page /u/{username}/{slug} ----
_VANITY_HTML = """<!DOCTYPE html>
<html lang="__LANG__">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ — 3dhosty.com</title>
<meta name="description" content="__META_DESC__">
__ROBOTS__
<link rel="canonical" href="__CANONICAL__">
<meta property="og:type" content="object">
<meta property="og:title" content="__TITLE__">
<meta property="og:description" content="__META_DESC__">
<meta property="og:url" content="__CANONICAL__">
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:Inter,system-ui,sans-serif;background:#f7f9fc;color:#1e293b;line-height:1.6}
.top{position:sticky;top:0;background:#fff;border-bottom:1px solid #e2e8f0;display:flex;align-items:center;gap:16px;padding:10px 16px;z-index:10}
.top a.logo{font-weight:800;color:#1a56db;text-decoration:none;font-size:18px}
.pills{display:flex;gap:8px;flex-wrap:wrap;flex:1;justify-content:center}
.pill{font-size:12px;padding:4px 10px;border:1px solid #e2e8f0;border-radius:999px;background:#fff;color:#64748b}
.btn{padding:9px 18px;border-radius:8px;font-weight:600;text-decoration:none;border:none;cursor:pointer}
.btn-primary{background:#1a56db;color:#fff}
.btn-sec{background:#f1f5f9;color:#1e293b}
.wrap{max-width:1100px;margin:0 auto;padding:20px;display:grid;grid-template-columns:1fr 340px;gap:20px}
#viewer{width:100%;height:420px;background:#0a0a12;border-radius:12px;overflow:hidden}
.desc{white-space:pre-wrap;background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:16px;margin-top:12px}
.tags{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}
.tag{background:#e8eefb;color:#1a56db;padding:3px 8px;border-radius:999px;font-size:12px;text-decoration:none}
.yt{margin-top:12px}
.yt iframe{width:100%;height:220px;border:none;border-radius:8px}
.side{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:16px;height:fit-content}
@media(max-width:900px){.wrap{grid-template-columns:1fr}#viewer{height:300px}.pills{display:none}}
</style>
<script type="importmap">{"imports":{"three":"https://unpkg.com/three@0.164.1/build/three.module.js","three/addons/":"https://unpkg.com/three@0.164.1/examples/jsm/"}}</script>
</head>
<body>
<header class="top">
  <a class="logo" href="/">3dhosty.com</a>
  <div class="pills">__PILLS__</div>
  <div class="actions"><a class="btn btn-primary" href="/api/download/__UUID__">⬇ Pobierz STEP</a> <a class="btn btn-sec" href="/e/__JOBID__">Embed</a></div>
</header>
<div class="wrap">
  <div>
    <div id="viewer"></div>
    <h1 style="margin:12px 0 4px;font-size:20px">__TITLE__</h1>
    <div style="color:#64748b;font-size:13px">by <a href="/u/__USERNAME__">__USERNAME__</a> · __DATE__ · __VIS_LABEL__</div>
    <div class="tags">__TAG_HTML__</div>
    <div class="desc">__DESC__</div>
    __YOUTUBE__
  </div>
  <div class="side">
    <div style="font-weight:700;margin-bottom:8px">Pliki</div>
    <div style="font-size:13px;color:#64748b;margin-bottom:12px">__FILENAME__ · __FACES__ ścianek · __SIZE__</div>
    <a class="btn btn-primary" style="display:block;text-align:center" href="/api/download/__UUID__">Pobierz STEP</a>
    <a class="btn btn-sec" style="display:block;text-align:center;margin-top:8px" href="/api/share/__TOKEN__/download">Pobierz via share</a>
    <div style="margin-top:16px;font-size:13px;color:#64748b">Wyświetlenia: __VIEWS__ · Pobrania: __DOWNLOADS__</div>
    __PAID_BOX__
  </div>
</div>
<script type="module">
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';
const el=document.getElementById('viewer');
const scene=new THREE.Scene();scene.background=new THREE.Color(0x0a0a12);
const camera=new THREE.PerspectiveCamera(50, el.clientWidth/el.clientHeight, 0.1, 1000);camera.position.set(0,40,60);
const renderer=new THREE.WebGLRenderer({antialias:true});renderer.setSize(el.clientWidth, el.clientHeight);renderer.setPixelRatio(window.devicePixelRatio);el.appendChild(renderer.domElement);
const controls=new OrbitControls(camera, renderer.domElement);controls.enableDamping=true;
scene.add(new THREE.AmbientLight(0x404060,1.2));const d1=new THREE.DirectionalLight(0x3b82f6,1.0);d1.position.set(30,50,30);scene.add(d1);
const d2=new THREE.DirectionalLight(0x8888ff,0.5);d2.position.set(-20,10,-30);scene.add(d2);
scene.add(new THREE.GridHelper(100,20,0x2a2a3a,0x16161f));
new STLLoader().load('/api/stl-preview/__UUID__', g=>{g.computeBoundingBox();const c=new THREE.Vector3();g.boundingBox.getCenter(c);g.translate(-c.x,-c.y,-c.z);const s=new THREE.Vector3();g.boundingBox.getSize(s);const mx=Math.max(s.x,s.y,s.z);if(mx>0)g.scale(30/mx,30/mx,30/mx);const m=new THREE.Mesh(g,new THREE.MeshPhongMaterial({color:0x3b82f6,specular:0x6666aa,shininess:40}));m.rotation.x=-Math.PI/2;scene.add(m);},undefined,()=>{el.style.display='none'});
function animate(){requestAnimationFrame(animate);controls.update();renderer.render(scene,camera);}animate();
window.addEventListener('resize',()=>{camera.aspect=el.clientWidth/el.clientHeight;camera.updateProjectionMatrix();renderer.setSize(el.clientWidth,el.clientHeight);});
</script>
</body>
</html>
"""

@router.get("/u/{username}/{slug}", response_class=HTMLResponse)
def vanity_page(username: str, slug: str, request: Request, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        # fallback: email prefix search
        user = db.query(models.User).filter(models.User.email.ilike(f"{username}@%")).first()
        if not user:
            return HTMLResponse("<h1>Uzytkownik nie znaleziony</h1>", status_code=404)
    job = db.query(models.Job).filter(models.Job.user_id == user.id, models.Job.slug == slug, models.Job.status == "done").first()
    if not job:
        return HTMLResponse("<h1>Model nie znaleziony</h1>", status_code=404)
    # visibility check
    token = request.headers.get("authorization","")
    # simple: private requires auth of owner — we check via optional cookie? for now block private for anon
    if job.visibility == "private":
        return HTMLResponse("<h1>Prywatny model — zaloguj sie</h1>", status_code=403)
    job.views = (job.views or 0) + 1
    db.commit()
    title = html.escape(job.title or job.original_filename or "model")
    desc = html.escape(job.description or "")
    tags = [t.strip() for t in (job.tags or "").split(",") if t.strip()]
    tag_html = "".join(f'<a class="tag" href="/#tag-{html.escape(t)}">{html.escape(t)}</a>' for t in tags) or '<span style="color:#94a3b8;font-size:12px">Brak tagow</span>'
    yt_id = _youtube_embed(job.youtube_url or "")
    yt_html = f'<div class="yt"><iframe src="https://www.youtube.com/embed/{yt_id}" allowfullscreen loading="lazy"></iframe></div>' if yt_id else ""
    vis_label = {"public": "Publiczny", "unlisted": "Niepubliczny (link)", "private": "Prywatny"}.get(job.visibility, job.visibility)
    robots = '<meta name="robots" content="noindex, nofollow">' if job.visibility == "unlisted" else ""
    faces = job.result_faces or "?"
    size_kb = f"{(job.result_size_bytes or 0)//1024} KB" if job.result_size_bytes else "?"
    # find a share token if exists
    token_share = job.shares[0].token if job.shares else ""
    paid_box = ""
    if job.is_paid and job.price_cents:
        price = job.price_cents / 100
        paid_box = f'<div style="margin-top:12px;padding:12px;background:#fef3c7;border:1px solid #f59e0b;border-radius:8px"><div style="font-weight:700">Platny model — {price:.2f} USD</div><div style="font-size:12px;color:#92400e">Prowizja 20% dla 3dhosty.com</div><button class="btn btn-primary" style="width:100%;margin-top:8px" onclick="buy({job.id})">Kup teraz</button></div><script>function buy(id){{fetch(`/api/models/${{id}}/purchase`,{{method:"POST",headers:{{"Authorization":localStorage.getItem("token")?"Bearer "+localStorage.getItem("token"):""}}}}).then(r=>r.json()).then(j=>{{if(j.checkout_url) location=j.checkout_url; else alert(JSON.stringify(j))}})}}<\/script>'
    html_page = _VANITY_HTML.replace("__LANG__","pl").replace("__TITLE__",title).replace("__META_DESC__", (desc[:150] or title)).replace("__ROBOTS__", robots).replace("__CANONICAL__", f"https://3dhosty.com/u/{html.escape(username)}/{html.escape(slug)}").replace("__PILLS__", f'<span class="pill">{faces} ścian</span><span class="pill">{html.escape(job.mode or "auto")}</span><span class="pill">{vis_label}</span>').replace("__UUID__", job.uuid).replace("__JOBID__", str(job.id)).replace("__USERNAME__", html.escape(username)).replace("__DATE__", str(job.created_at)[:10] if job.created_at else "").replace("__VIS_LABEL__", vis_label).replace("__TAG_HTML__", tag_html).replace("__DESC__", desc or "Brak opisu.").replace("__YOUTUBE__", yt_html).replace("__FILENAME__", html.escape(job.original_filename or "")).replace("__FACES__", str(faces)).replace("__SIZE__", size_kb).replace("__TOKEN__", token_share).replace("__VIEWS__", str(job.views or 0)).replace("__DOWNLOADS__", str(job.shares[0].downloads if job.shares else 0)).replace("__PAID_BOX__", paid_box)
    return HTMLResponse(html_page)

@router.get("/u/{username}", response_class=HTMLResponse)
def user_profile(username: str, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        user = db.query(models.User).filter(models.User.email.ilike(f"{username}@%")).first()
        if not user:
            return HTMLResponse("<h1>Uzytkownik nie znaleziony</h1>", status_code=404)
    jobs = db.query(models.Job).filter(models.Job.user_id == user.id, models.Job.status == "done", models.Job.visibility == "public").order_by(models.Job.created_at.desc()).limit(24).all()
    items = "".join(f'<a href="/u/{username}/{j.slug}" style="display:block;border:1px solid #e2e8f0;border-radius:8px;padding:12px;text-decoration:none;color:#1e293b"><div style="font-weight:600">{html.escape(j.title or j.original_filename)}</div><div style="font-size:12px;color:#64748b">{j.result_faces or "?"} faces · { (j.views or 0)} views</div></a>' for j in jobs if j.slug)
    return HTMLResponse(f"""<!DOCTYPE html><html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(username)} — 3dhosty.com</title><style>body{{font-family:Inter,system-ui,sans-serif;background:#f7f9fc;color:#1e293b}} .wrap{{max-width:1000px;margin:0 auto;padding:20px}} .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px}}</style></head><body><div class="wrap"><a href="/" style="color:#1a56db;font-weight:800;text-decoration:none">3dhosty.com</a><h1 style="margin:12px 0">{html.escape(username)}</h1><div style="color:#64748b;margin-bottom:16px">{html.escape(user.bio or "")}</div><div class="grid">{items or "<div>Brak publicznych modeli</div>"}</div></div></body></html>""")
