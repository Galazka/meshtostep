import json
"""Community routes: vanity URL /u/{username}/{slug}, search, tags, model detail — 3dfile.link"""
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


def _md_to_html(md: str) -> str:
    if not md:
        return ""
    esc = html.escape(str(md), quote=False)
    code_blocks = []
    def _cb(m):
        code_blocks.append("<pre><code>" + m.group(1).strip("\n") + "</code></pre>")
        return f"\x00CODE{len(code_blocks)-1}\x00"
    esc = re.sub(r"```(.*?)```", _cb, esc, flags=re.DOTALL)
    esc = re.sub(r"`([^`\n]+)`", r"<code>\1</code>", esc)
    esc = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", r'<img src="\2" alt="\1" loading="lazy">', esc)
    esc = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', esc)
    esc = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", esc)
    esc = re.sub(r"(?<!\*)\*([^\*\n]+)\*(?!\*)", r"<em>\1</em>", esc)
    parts = re.split(r"\n\s*\n", esc)
    out = []
    for p in parts:
        p = p.strip()
        if not p: continue
        if p.startswith("\x00CODE") and p.endswith("\x00"):
            try: out.append(code_blocks[int(p[5:-1])]); continue
            except: pass
        if p.startswith("##"): out.append("<h3>" + p.lstrip("#").strip() + "</h3>"); continue
        out.append("<p>" + p.replace("\n", "<br>") + "</p>")
    return "".join(out)

# ---- API: search models ----
@router.get("/api/models")
def search_models(
    q: str = Query("", description="search query"),
    tag: str = Query("", description="filter by tag"),
    sort: str = Query("latest", description="latest|popular"),
    limit: int = Query(24, ge=1, le=60),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(models.Job).filter(
        models.Job.status.in_(["done", "hosted"]),
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
            "faces": j.result_faces,
            "dims_mm": getattr(j, "dims_mm", None),
            "created_at": str(j.created_at),
            "vanity": f"/u/{username}/{j.slug}" if j.slug and username != "anon" else f"/s/{j.uuid}",
            "username": username,
        })
    return {"total": total, "items": out}

@router.get("/api/tags")
def list_tags(db: Session = Depends(get_db)):
    rows = db.query(models.Job.tags).filter(models.Job.visibility == "public", models.Job.status.in_(["done", "hosted"])).all()
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
    j = db.query(models.Job).filter(models.Job.id == job_id, models.Job.status.in_(["done", "hosted"])).first()
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
        "faces": j.result_faces, "mode": j.mode,
        "dims_mm": getattr(j, "dims_mm", None),
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
    db.commit()
    return {"ok": True, "slug": j.slug, "visibility": j.visibility}

# ---- Rating: 1-5 stars, one vote per user (update allowed) ----
@router.get("/api/jobs/{job_id}/rating")
def get_rating(job_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    from sqlalchemy import func as _func
    rows = db.query(models.JobRating).filter(models.JobRating.job_id == job_id).all()
    avg = round(sum(r.stars for r in rows) / len(rows), 1) if rows else 0
    mine = None
    if user:
        r = db.query(models.JobRating).filter(models.JobRating.job_id == job_id, models.JobRating.user_id == user.id).first()
        mine = r.stars if r else None
    return {"avg": avg, "count": len(rows), "mine": mine}

@router.post("/api/jobs/{job_id}/rating")
def set_rating(job_id: int, payload: dict, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    from fastapi import HTTPException as HE
    if not user:
        raise HE(401, "Zaloguj sie")
    try:
        stars = int(payload.get("stars"))
    except:
        raise HE(400, "stars 1-5")
    if stars < 1 or stars > 5:
        raise HE(400, "stars 1-5")
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HE(404, "Model nie znaleziony")
    r = db.query(models.JobRating).filter(models.JobRating.job_id == job_id, models.JobRating.user_id == user.id).first()
    if r:
        r.stars = stars
    else:
        db.add(models.JobRating(job_id=job_id, user_id=user.id, stars=stars))
    db.commit()
    rows = db.query(models.JobRating).filter(models.JobRating.job_id == job_id).all()
    avg = round(sum(x.stars for x in rows) / len(rows), 1) if rows else 0
    return {"ok": True, "avg": avg, "count": len(rows), "mine": stars}

# ---- Like: dedup via user_likes table, one like per user per job ----
@router.post("/api/jobs/{job_id}/like")
def toggle_like(job_id: int, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    from fastapi import HTTPException as HE
    if not user:
        raise HE(401, "Zaloguj sie")
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HE(404, "Model nie znaleziony")
    existing = db.query(models.UserLike).filter(
        models.UserLike.job_id == job_id, models.UserLike.user_id == user.id
    ).first()
    if existing:
        # unlike: remove + decrement
        db.delete(existing)
        job.likes = max((job.likes or 1) - 1, 0)
        db.commit()
        return {"ok": True, "likes": job.likes, "liked": False}
    db.add(models.UserLike(job_id=job_id, user_id=user.id))
    job.likes = (job.likes or 0) + 1
    db.commit()
    return {"ok": True, "likes": job.likes, "liked": True}

# ---- Vanity page /u/{username}/{slug} ----
_VANITY_HTML = """<!DOCTYPE html>
<html lang="__LANG__">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ — 3dfile.link</title>
<meta name="description" content="__META_DESC__">
__ROBOTS__
<link rel="canonical" href="__CANONICAL__">
<meta property="og:type" content="object">
<meta property="og:title" content="__TITLE__">
<meta property="og:description" content="__META_DESC__">
<meta property="og:url" content="__CANONICAL__">
<meta property="og:image" content="__OG_IMAGE__">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="__TITLE__">
<meta name="twitter:description" content="__META_DESC__">
<meta name="twitter:image" content="__OG_IMAGE__">
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
#viewer{width:100%;height:420px;background:#f0f2f5;border-radius:12px;overflow:hidden;position:relative}
.viewer-toolbar{position:absolute;top:8px;right:8px;display:flex;gap:4px;z-index:10}
.viewer-toolbar button{background:rgba(255,255,255,.9);border:1px solid #e2e8f0;border-radius:6px;padding:6px 10px;font-size:12px;cursor:pointer;backdrop-filter:blur(4px)}
.viewer-toolbar button:hover{background:#fff;border-color:#1a56db;color:#1a56db}
.desc{white-space:pre-wrap;background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:16px;margin-top:12px}
.tags{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}
.tag{background:#e8eefb;color:#1a56db;padding:3px 8px;border-radius:999px;font-size:12px;text-decoration:none}
.yt{margin-top:12px}
.yt iframe{width:100%;height:220px;border:none;border-radius:8px}
.side{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:16px;height:fit-content}
@media(max-width:900px){.wrap{grid-template-columns:1fr}#viewer{height:300px}.pills{display:none}}
</style>
<script type="importmap">{"imports":{"three":"/vendor/three/three.module.js","three/addons/controls/OrbitControls.js":"/vendor/three/controls/OrbitControls.js","three/addons/loaders/STLLoader.js":"/vendor/three/loaders/STLLoader.js"}}</script>
</head>
<body>
<header class="top">
  <a class="logo" href="/"><img src="/logo.png?v=2" alt="3DFILE" style="height:28px" onerror="this.style.display='none'"></a>
  <div class="pills">__PILLS__</div>
  <div class="actions"><a class="btn btn-primary" href="/api/download/__UUID__">⬇ Pobierz STEP</a> <a class="btn btn-sec" href="/e/__JOBID__">Embed</a></div>
</header>
<div class="wrap">
  <div>
    <div id="viewer">
      <div class="viewer-toolbar">
        <button id="btnFs" title="Pełny ekran">⛶</button>
        <button id="btnColor" title="Kolor modelu" style="width:28px;height:28px;border-radius:50%;background:#3b82f6"></button>
      </div>
    </div>
    <h1 style="margin:12px 0 4px;font-size:20px">__TITLE__</h1>
    <div style="color:#64748b;font-size:13px">by <a href="/u/__USERNAME__">__USERNAME__</a> · __DATE__ · __VIS_LABEL__</div>
    <div class="tags">__TAG_HTML__</div>
    __YOUTUBE__
  </div>
  <div class="side">
    <div style="font-weight:700;margin-bottom:8px">Pliki</div>
    <div style="font-size:13px;color:#64748b;margin-bottom:12px">__FILENAME__ · __FACES__ ścianek · __SIZE__</div>
    <a class="btn btn-primary" style="display:block;text-align:center" href="/api/download/__UUID__">Pobierz STEP</a>
    <a class="btn btn-sec" style="display:block;text-align:center;margin-top:8px" href="/api/share/__TOKEN__/download">Pobierz via share</a>
    <div style="margin-top:16px;font-size:13px;color:#64748b">Wyświetlenia: <b id="viewsCount">__VIEWS__</b></div>
    <div style="margin-top:12px;display:flex;gap:12px;align-items:center">
      <button id="likeBtn" onclick="doLike()" style="border:1px solid #e2e8f0;background:#fff;border-radius:8px;padding:6px 12px;cursor:pointer;font-size:13px;display:flex;align-items:center;gap:4px">♥ <span id="likesCount">__LIKES__</span></button>
      <div id="starWrap" style="display:flex;align-items:center;gap:2px;font-size:18px;cursor:pointer;color:#d1d5db"></div>
      <span id="ratingInfo" style="font-size:11px;color:#94a3b8"></span>
    </div>
    __PAID_BOX__
  </div>
</div>
<script type="module">
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';
const el=document.getElementById('viewer');
const viewerWrap = el;
const scene=new THREE.Scene();scene.background=new THREE.Color(0xf0f2f5);
const camera=new THREE.PerspectiveCamera(50, el.clientWidth/el.clientHeight, 0.1, 1000);camera.position.set(0,40,60);
const renderer=new THREE.WebGLRenderer({antialias:true});renderer.setSize(el.clientWidth, el.clientHeight);renderer.setPixelRatio(window.devicePixelRatio);el.appendChild(renderer.domElement);
const controls=new OrbitControls(camera, renderer.domElement);controls.enableDamping=true;controls.enableRotate=true;controls.enablePan=true;controls.enableZoom=true;controls.minDistance=5;controls.maxDistance=500;controls.minPolarAngle=0.1;controls.maxPolarAngle=Math.PI-0.1;
scene.add(new THREE.AmbientLight(0x404060,1.2));const d1=new THREE.DirectionalLight(0x3b82f6,1.0);d1.position.set(30,50,30);scene.add(d1);
const d2=new THREE.DirectionalLight(0x8888ff,0.5);d2.position.set(-20,10,-30);scene.add(d2);
let viewerMesh=null;
new STLLoader().load('/api/stl-preview/__UUID__', g=>{g.computeBoundingBox();const c=new THREE.Vector3();g.boundingBox.getCenter(c);g.translate(-c.x,-c.y,-c.z);const s=new THREE.Vector3();g.boundingBox.getSize(s);const mx=Math.max(s.x,s.y,s.z);if(mx>0)g.scale(30/mx,30/mx,30/mx);viewerMesh=new THREE.Mesh(g,new THREE.MeshPhongMaterial({color:0x3b82f6,specular:0x6666aa,shininess:40}));viewerMesh.rotation.x=-Math.PI/2;scene.add(viewerMesh);},undefined,()=>{
    // Fallback: try JPG preview
    var img=new Image();
    img.onload=function(){el.innerHTML='';img.style.cssText='width:100%;height:100%;object-fit:contain;border-radius:12px';el.appendChild(img);};
    img.onerror=function(){el.innerHTML='<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#64748b;font-size:14px;flex-direction:column;gap:8px"><span style="font-size:32px">△</span>Podglad 3D niedostepny</div>';};
    img.src='/api/preview/__UUID__';
});
function animate(){requestAnimationFrame(animate);controls.update();renderer.render(scene,camera);}animate();
window.addEventListener('resize',()=>{camera.aspect=el.clientWidth/el.clientHeight;camera.updateProjectionMatrix();renderer.setSize(el.clientWidth,el.clientHeight);});
// Fullscreen
document.getElementById('btnFs').onclick=()=>{
  if(!document.fullscreenElement){viewerWrap.requestFullscreen().catch(()=>{});}
  else{document.exitFullscreen();}
};
document.addEventListener('fullscreenchange',()=>{
  setTimeout(()=>{camera.aspect=viewerWrap.clientWidth/viewerWrap.clientHeight;camera.updateProjectionMatrix();renderer.setSize(viewerWrap.clientWidth,viewerWrap.clientHeight);},100);
});
// Color picker
const colors=['#ffffff','#9ca3af','#3b82f6','#22c55e','#ef4444','#f97316','#a855f7','#06b6d4'];
let colorIdx=0;
document.getElementById('btnColor').onclick=()=>{
  colorIdx=(colorIdx+1)%colors.length;
  document.getElementById('btnColor').style.background=colors[colorIdx];
  if(viewerMesh)viewerMesh.material.color.set(colors[colorIdx]);
};
</script>
<!-- ── Opis / blog + Komentarze ── -->
<div style="max-width:800px;margin:24px auto;padding:0 16px">
  <div id="descSection" style="background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:20px;margin-bottom:20px">
    <h3 style="margin:0 0 8px;font-size:16px">Opis modelu</h3>
    <div id="descBody" style="font-size:14px;line-height:1.6;color:#334155;white-space:pre-wrap"></div>
    <div id="descTags" style="margin-top:10px;display:flex;gap:6px;flex-wrap:wrap"></div>
    <div id="descYoutube" style="margin-top:12px;display:none"><iframe id="descYoutubeFrame" width="100%" height="315" frameborder="0" allowfullscreen style="border-radius:8px"></iframe></div>
  </div>
  <div style="background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:20px">
    <h3 style="margin:0 0 12px;font-size:16px">Komentarze <span id="cmCount" style="font-weight:400;color:#94a3b8"></span></h3>
    <div id="commentsList"></div>
    <div id="commentForm" style="margin-top:12px;display:none">
      <textarea id="commentBody" rows="3" style="width:100%;padding:8px;border:1px solid #d1d5db;border-radius:6px;font-size:13px;resize:vertical" placeholder="Napisz komentarz..."></textarea>
      <button onclick="postComment()" style="margin-top:8px;padding:8px 16px;background:#1a56db;color:#fff;border:none;border-radius:6px;font-size:13px;cursor:pointer">Wyslij</button>
    </div>
  </div>
</div>
<script>
(function(){
  var jobId = __JOBID__;
  // description from placeholders
  var descTitle = __DESCTITLE__;
  var descBody = __DESCBODY__;
  var descTags = __DESCTAGS__;
  var descYoutube = __DESCYOUTUBE__;
  document.getElementById('descBody').innerHTML = descBody || '<span style="color:#94a3b8">Brak opisu</span>';
  document.getElementById('descTags').innerHTML = (descTags||[]).map(function(tg){return '<span style="padding:2px 8px;border:1px solid #d1d5db;border-radius:999px;font-size:11px;color:#64748b">'+tg+'</span>'}).join('');
  if (descYoutube) {
    var m = String(descYoutube).match(/(?:v=|youtu\.be\/|embed\/)([a-zA-Z0-9_-]+)/);
    if (m) { document.getElementById('descYoutube').style.display='block'; document.getElementById('descYoutubeFrame').src='https://www.youtube.com/embed/'+m[1]; }
  }
  // comments (with owner/admin delete)
  var myName = null;
  try {
    var tok = localStorage.getItem('mt_token');
    if (tok) { var pl = JSON.parse(atob(tok.split('.')[1])); myName = pl.email ? String(pl.email).split('@')[0] : null; }
  } catch(e) {}
  function renderComments(comments){
    var el = document.getElementById('commentsList');
    if (!comments || !comments.length) { el.innerHTML = '<div style="color:#94a3b8;font-size:13px">Brak komentarzy — badz pierwszy</div>'; document.getElementById('cmCount').textContent=''; return; }
    document.getElementById('cmCount').textContent = '('+comments.length+')';
    el.innerHTML = comments.map(function(c){
      var d = c.created_at ? new Date(c.created_at).toLocaleDateString('pl-PL') : '';
      var canDel = myName && (myName === c.username);
      var delBtn = canDel ? '<button onclick="delComment('+c.id+')" style="margin-left:8px;border:none;background:none;color:#dc2626;cursor:pointer;font-size:11px">Usuń</button>' : '';
      return '<div style="border-bottom:1px solid #f1f5f9;padding:8px 0"><span style="font-weight:600;font-size:13px">'+(c.username||'anon')+'</span><span style="font-size:11px;color:#94a3b8;margin-left:8px">'+d+'</span>'+delBtn+'<div style="font-size:13px;margin-top:4px">'+String(c.body||'').replace(/</g,'&lt;')+'</div></div>';
    }).join('');
  }
  window.delComment = function(cid){
    if (!confirm('Usunąć komentarz?')) return;
    var token = localStorage.getItem('mt_token');
    fetch('/api/jobs/comments/' + cid, {method:'DELETE',headers:{'Authorization':'Bearer '+token}}).then(function(r){
      if (r.ok) loadComments(); else alert('Brak uprawnień');
    });
  };
  function loadComments(){
    fetch('/api/jobs/' + jobId + '/comments').then(function(r){return r.ok?r.json():[]}).then(renderComments).catch(function(){});
  }
  window.postComment = function(){
    var body = document.getElementById('commentBody').value.trim();
    if (!body) return;
    var token = localStorage.getItem('mt_token');
    if (!token) { alert('Zaloguj sie by komentowac'); return; }
    fetch('/api/jobs/' + jobId + '/comments', {method:'POST',headers:{'Authorization':'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify({body:body})}).then(function(r){ if(r.ok){document.getElementById('commentBody').value='';loadComments();} else {r.json().then(function(e){alert(e.detail||'Blad')}).catch(function(){alert('Blad')});} }).catch(function(){alert('Blad sieci')});
  };
  loadComments();
  if (localStorage.getItem('mt_token')) document.getElementById('commentForm').style.display = 'block';
  // ── like (♥) ──
  window.doLike = function(){
    var token = localStorage.getItem('mt_token');
    if (!token) { alert('Zaloguj sie by polubic'); return; }
    fetch('/api/jobs/' + jobId + '/like', {method:'POST',headers:{'Authorization':'Bearer '+token}}).then(function(r){
      if (r.ok) return r.json().then(function(j){ document.getElementById('likesCount').textContent = j.likes; document.getElementById('likeBtn').style.color = '#dc2626'; });
      return r.json().then(function(e){ alert(e.detail || 'Blad'); });
    }).catch(function(){ alert('Blad sieci'); });
  };
  // ── rating (★ 1-5) ──
  var _myStars = 0;
  function paintStars(n){
    var w = document.getElementById('starWrap');
    var html = '';
    for (var i = 1; i <= 5; i++) {
      html += '<span data-s="'+i+'" style="color:'+(i <= n ? '#f59e0b' : '#d1d5db')+'">★</span>';
    }
    w.innerHTML = html;
    Array.prototype.forEach.call(w.querySelectorAll('span'), function(sp){
      sp.onclick = function(){
        var v = parseInt(sp.getAttribute('data-s'));
        sendRating(v);
      };
    });
  }
  function loadRating(){
    var headers = {};
    var token = localStorage.getItem('mt_token');
    if (token) headers['Authorization'] = 'Bearer ' + token;
    fetch('/api/jobs/' + jobId + '/rating', {headers: headers}).then(function(r){ return r.ok ? r.json() : null; }).then(function(j){
      if (!j) return;
      _myStars = j.mine || 0;
      paintStars(_myStars || Math.round(j.avg) || 0);
      document.getElementById('ratingInfo').textContent = j.count ? (j.avg + ' (' + j.count + ')') : 'Brak ocen';
    }).catch(function(){});
  }
  function sendRating(v){
    var token = localStorage.getItem('mt_token');
    if (!token) { alert('Zaloguj sie by ocenic'); return; }
    fetch('/api/jobs/' + jobId + '/rating', {method:'POST',headers:{'Authorization':'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify({stars:v})}).then(function(r){
      if (r.ok) return r.json().then(function(j){ _myStars = j.mine; paintStars(j.mine); document.getElementById('ratingInfo').textContent = j.avg + ' (' + j.count + ')'; });
      return r.json().then(function(e){ alert(e.detail || 'Blad'); });
    }).catch(function(){ alert('Blad sieci'); });
  }
  paintStars(0);
  loadRating();
})();
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
    job = db.query(models.Job).filter(models.Job.user_id == user.id, models.Job.slug == slug, models.Job.status.in_(["done", "hosted"])).first()
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
    paid_box = ""  # payments removed — free hosting, ads only
    likes = job.likes or 0
    html_page = _VANITY_HTML.replace("__LANG__","pl").replace("__TITLE__",title).replace("__META_DESC__", (desc[:150] or title)).replace("__ROBOTS__", robots).replace("__CANONICAL__", f"https://3dfile.link/u/{html.escape(username)}/{html.escape(slug)}").replace("__PILLS__", f'<span class="pill">{faces} ścian</span><span class="pill">{html.escape(job.mode or "auto")}</span><span class="pill">{vis_label}</span>').replace("__UUID__", job.uuid).replace("__JOBID__", str(job.id)).replace("__USERNAME__", html.escape(username)).replace("__DATE__", str(job.created_at)[:10] if job.created_at else "").replace("__VIS_LABEL__", vis_label).replace("__TAG_HTML__", tag_html).replace("__YOUTUBE__", yt_html).replace("__FILENAME__", html.escape(job.original_filename or "")).replace("__FACES__", str(faces)).replace("__SIZE__", size_kb).replace("__TOKEN__", token_share).replace("__VIEWS__", str(job.views or 0)).replace("__LIKES__", str(likes)).replace("__PAID_BOX__", paid_box).replace("__DESCTITLE__", json.dumps(html.escape(job.title or job.original_filename or ""))).replace("__DESCBODY__", json.dumps(_md_to_html(job.description or ""))).replace("__DESCTAGS__", json.dumps(tags)).replace("__DESCYOUTUBE__", json.dumps(str(job.youtube_url or ""))).replace("__OG_IMAGE__", f"https://3dfile.link/api/og/{job.uuid}")
    return HTMLResponse(html_page)

@router.get("/u/{username}", response_class=HTMLResponse)
def user_profile(username: str, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        user = db.query(models.User).filter(models.User.email.ilike(f"{username}@%")).first()
        if not user:
            return HTMLResponse("<h1>Uzytkownik nie znaleziony</h1>", status_code=404)
    jobs = (
        db.query(models.Job)
        .filter(models.Job.user_id == user.id, models.Job.status.in_(["done", "hosted"]), models.Job.visibility == "public")
        .order_by(models.Job.created_at.desc())
        .limit(48)
        .all()
    )
    total_views = sum(j.views or 0 for j in jobs)
    model_count = len(jobs)
    member_since = user.created_at.strftime("%b %Y") if getattr(user, "created_at", None) else ""
    avatar_letter = (username or "?")[0].upper()
    avatar_img = (
        f'<img src="{html.escape(user.avatar_url)}" alt="" style="width:80px;height:80px;border-radius:50%;object-fit:cover">'
        if getattr(user, "avatar_url", None)
        else f'<div style="width:80px;height:80px;border-radius:50%;background:#1a56db;color:#fff;display:flex;align-items:center;justify-content:center;font-size:32px;font-weight:700">{html.escape(avatar_letter)}</div>'
    )
    cards = ""
    for j in jobs:
        if not j.slug:
            continue
        title = html.escape(j.title or j.original_filename or "model")
        faces = j.result_faces or "?"
        views = j.views or 0
        preview_url = f"/api/preview/{j.uuid}"
        cards += (
            f'<a href="/u/{html.escape(username)}/{html.escape(j.slug)}" class="card">'
            f'<img src="{preview_url}" alt="{title}" loading="lazy">'
            f'<div class="card-body">'
            f'<div class="card-title">{title}</div>'
            f'<div class="card-meta">{faces} faces · {views} views</div>'
            f'</div></a>'
        )
    if not cards:
        cards = '<div style="grid-column:1/-1;text-align:center;color:#94a3b8;padding:40px 0">Brak publicznych modeli</div>'
    page = f"""<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(username)} — 3dfile.link</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:Inter,system-ui,sans-serif;background:#f7f9fc;color:#1e293b;line-height:1.6}}
.top{{background:#fff;border-bottom:1px solid #e2e8f0;padding:12px 20px;display:flex;align-items:center}}
.top a{{font-weight:800;color:#1a56db;text-decoration:none;font-size:18px}}
.wrap{{max-width:1000px;margin:0 auto;padding:24px 20px}}
.profile{{display:flex;gap:20px;align-items:center;background:#fff;border:1px solid #e2e8f0;border-radius:14px;padding:24px;margin-bottom:24px}}
.profile-info{{flex:1}}
.profile-info h1{{font-size:22px;font-weight:800;margin-bottom:2px}}
.profile-info .bio{{font-size:14px;color:#64748b;margin-bottom:8px}}
.stats{{display:flex;gap:16px;flex-wrap:wrap}}
.stat{{font-size:13px;color:#475569}}
.stat strong{{color:#1e293b}}
.section-title{{font-size:16px;font-weight:700;margin-bottom:12px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:14px}}
.card{{display:flex;flex-direction:column;background:#fff;border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;text-decoration:none;color:#1e293b;transition:box-shadow .15s}}
.card:hover{{box-shadow:0 4px 16px rgba(0,0,0,.08)}}
.card img{{width:100%;aspect-ratio:4/3;object-fit:cover;background:#f0f2f5}}
.card-body{{padding:12px}}
.card-title{{font-weight:600;font-size:14px;margin-bottom:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.card-meta{{font-size:12px;color:#64748b}}
@media(max-width:600px){{.profile{{flex-direction:column;text-align:center}}.stats{{justify-content:center}}}}
</style>
</head>
<body>
<header class="top"><a href="/">3dfile.link</a></header>
<div class="wrap">
  <div class="profile">
    {avatar_img}
    <div class="profile-info">
      <h1>{html.escape(username)}</h1>
      <div class="bio">{html.escape(user.bio or "Brak opisu")}</div>
      <div class="stats">
        <span class="stat"><strong>{model_count}</strong> modeli</span>
        <span class="stat"><strong>{total_views}</strong> wyświetleń</span>
        <span class="stat">Członek od <strong>{member_since}</strong></span>
      </div>
    </div>
  </div>
  <div class="section-title">Modele publiczne</div>
  <div class="grid">{cards}</div>
</div>
</body>
</html>"""
    return HTMLResponse(page)
