"""Share link public page with 3D preview."""
import html
import json
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from .database import get_db
from . import models

router = APIRouter(tags=["share"])


def _md_to_html(md: str) -> str:
    """Tiny markdown→HTML (escaped first, safe tags only). ponytail: ceiling=basic md; upgrade to markdown lib when tables/lists needed."""
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
    esc = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", esc)
    parts = re.split(r"\n\s*\n", esc)
    out = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if p.startswith("\x00CODE") and p.endswith("\x00"):
            try:
                out.append(code_blocks[int(p[5:-1])])
                continue
            except (ValueError, IndexError):
                pass
        if p.startswith("##"):
            out.append("<h3>" + p.lstrip("#").strip() + "</h3>")
            continue
        out.append("<p>" + p.replace("\n", "<br>") + "</p>")
    return "".join(out)


def _tags_list(raw) -> list:
    """Comma-separated tags → list. ponytail: ceiling=CSV string; upgrade when Tag table lands."""
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(t).strip() for t in raw if str(t).strip()]
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(t).strip() for t in parsed if str(t).strip()]
    except (ValueError, TypeError):
        pass
    return [t.strip() for t in str(raw).split(",") if t.strip()]


def _lang(request: Request) -> str:
    """Detect language from Accept-Language header."""
    try:
        accept = (request.headers.get("accept-language") or "").lower()
        if "pl" in accept.split(",")[0].split(";")[0]:
            return "pl"
        return "en"
    except Exception:
        return "en"


def _fmt_bytes(n) -> str:
    """Format byte count nicely (B / KB / MB)."""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return "?"
    if n <= 0:
        return "?"
    if n >= 1024 * 1024:
        return f"{n / 1024 / 1024:.1f} MB"
    if n >= 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n} B"


_SHARE_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="__LANG__">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
__ROBOTS__
<title>__FILENAME__ — 3dhosty.com</title>
<meta property="og:type" content="website">
<meta property="og:site_name" content="3dhosty.com">
<meta property="og:title" content="__FILENAME__ — 3dhosty.com">
<meta property="og:description" content="__OG_DESC__">
<meta property="og:image" content="__OG_IMAGE__">
<meta property="og:url" content="__OG_URL__">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="__FILENAME__ — 3dhosty.com">
<meta name="twitter:description" content="__OG_DESC__">
<meta name="twitter:image" content="__OG_IMAGE__">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><text y='24' font-size='24'>📁</text></svg>">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { height: 100%; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #f7f9fc;
    color: #1e293b;
    overflow: hidden;
  }
  .topbar {
    position: fixed;
    top: 0; left: 0; right: 0;
    z-index: 10;
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 10px 16px;
    background: rgba(14, 14, 22, 0.88);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    border-bottom: 1px solid #2a2a3a;
  }
  .file-block { min-width: 0; max-width: 30vw; }
  .file {
    font-weight: 700;
    font-size: 14px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .shared-by { font-size: 12px; color: #888; margin-top: 2px; }
  .shared-by:empty { display: none; }
  .pills {
    display: flex;
    flex: 1;
    justify-content: center;
    flex-wrap: wrap;
    gap: 8px;
    min-width: 0;
  }
  .pill {
    font-size: 12px;
    padding: 4px 12px;
    border: 1px solid #2a2a3a;
    border-radius: 999px;
    background: #fff;
    color: #bbb;
    white-space: nowrap;
  }
  .actions { display: flex; gap: 8px; margin-left: auto; flex-shrink: 0; }
  .btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 9px 18px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    text-decoration: none;
    cursor: pointer;
    border: none;
    transition: opacity 0.2s;
    white-space: nowrap;
  }
  .btn:hover { opacity: 0.85; }
  .btn-primary { background: #1a56db; color: #fff; }
  .btn-secondary { background: #2a2a3a; color: #1e293b; }
  #viewer3d {
    position: fixed;
    inset: 0;
    width: 100vw;
    height: 100vh;
    background: #f0f2f5;
  }
  #viewer3d canvas { display: block; }
  @media (max-width: 860px) {
    .pills { display: none; }
    .file-block { max-width: 45vw; }
    .btn { padding: 8px 12px; font-size: 13px; }
  }
  #descBody img { max-width: 100%; border-radius: 8px; margin: 12px 0; }
  #descBody pre { background: #1e293b; color: #e2e8f0; padding: 12px; border-radius: 6px; overflow-x: auto; font-size: 13px; margin: 12px 0; }
  #descBody code { background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 13px; }
  #descBody pre code { background: none; padding: 0; }
  #descBody h3 { font-size: 18px; font-weight: 700; margin: 16px 0 8px; }
  #descBody p { margin: 8px 0; }
  .comment-item { padding: 10px 0; border-bottom: 1px solid #f1f5f9; }
  .comment-item .comment-user { font-weight: 600; font-size: 13px; }
  .comment-item .comment-date { font-size: 11px; color: #94a3b8; margin-left: 8px; }
  .comment-item .comment-body { font-size: 13px; color: #475569; margin-top: 4px; }
</style>
</head>
<body>
<header class="topbar">
  <div class="file-block">
    <div class="file" title="__FILENAME__">📁 __FILENAME__</div>
    <div class="shared-by">__AUTHOR_INFO__</div>
  </div>
  <div class="pills">__CONV_INFO__</div>
  <div class="actions">
    <a class="btn btn-primary" href="/api/share/__TOKEN__/download">⬇ __DOWNLOAD_BTN__</a>
    <button class="btn btn-secondary" onclick="showEmbed()">⧉ __EMBED_BTN__</button>
  </div>
</header>
<div id="viewer3d"></div>
<div id="descriptionPanel" style="display:none;position:fixed;bottom:48px;left:0;right:0;z-index:15;background:rgba(255,255,255,0.95);border-top:1px solid #e5e7eb;max-height:45vh;overflow-y:auto;padding:24px 32px;font-size:14px;line-height:1.7">
  <div style="max-width:800px;margin:0 auto">
    <div id="descTitle" style="font-size:20px;font-weight:700;margin-bottom:12px"></div>
    <div id="descTags" style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:16px"></div>
    <div id="descBody" style="color:#334155"></div>
    <div id="descYoutube" style="margin-top:16px;display:none"><iframe id="descYoutubeFrame" width="100%" height="315" frameborder="0" allowfullscreen style="border-radius:8px"></iframe></div>
    <div style="margin-top:24px;border-top:1px solid #e5e7eb;padding-top:16px">
      <h3 id="commentsTitle" style="font-size:16px;margin-bottom:12px"></h3>
      <div id="commentsList"></div>
      <div id="commentForm" style="margin-top:12px;display:none">
        <textarea id="commentBody" rows="3" style="width:100%;padding:8px;border:1px solid #d1d5db;border-radius:6px;font-size:13px;resize:vertical" placeholder="Napisz komentarz..."></textarea>
        <button onclick="postComment()" style="margin-top:8px;padding:8px 16px;background:#1a56db;color:#fff;border:none;border-radius:6px;font-size:13px;cursor:pointer">Wyślij</button>
      </div>
    </div>
  </div>
</div>
<button id="descToggle" onclick="toggleDescPanel()" style="position:fixed;bottom:56px;right:16px;z-index:20;background:#1a56db;color:#fff;border:none;border-radius:50%;width:44px;height:44px;font-size:20px;cursor:pointer;box-shadow:0 2px 12px rgba(0,0,0,.3);display:none">📝</button>

<script type="importmap">
{
  "imports": {
    "three": "/vendor/three/three.module.js",
    "three/addons/": "/vendor/three/"
  }
}
</script>
<script type="module">
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';

const el = document.getElementById('viewer3d');
if (!el) throw new Error('no viewer3d element');

const scene = new THREE.Scene();
scene.background = new THREE.Color(0xf0f2f5);
const camera = new THREE.PerspectiveCamera(50, window.innerWidth / window.innerHeight, 0.1, 1000);
camera.position.set(0, 40, 60);

const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });  /* 3dhosty share viewer */;
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(window.devicePixelRatio);
el.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.enableRotate = true;
controls.enablePan = true;
controls.enableZoom = true;
controls.minDistance = 5;
controls.maxDistance = 500;
controls.minPolarAngle = 0.1;
controls.maxPolarAngle = Math.PI - 0.1;

scene.add(new THREE.AmbientLight(0x404060, 1.2));
const d1 = new THREE.DirectionalLight(0x3b82f6, 1.0);
d1.position.set(30, 50, 30);
scene.add(d1);
const d2 = new THREE.DirectionalLight(0x8888ff, 0.5);
d2.position.set(-20, 10, -30);
scene.add(d2);

new STLLoader().load('/api/stl-preview/__UUID__', (g) => {
  g.computeBoundingBox();
  const c = new THREE.Vector3();
  g.boundingBox.getCenter(c);
  g.translate(-c.x, -c.y, -c.z);
  const s = new THREE.Vector3();
  g.boundingBox.getSize(s);
  const mx = Math.max(s.x, s.y, s.z);
  if (mx > 0) g.scale(30 / mx, 30 / mx, 30 / mx);
  const m = new THREE.Mesh(g, new THREE.MeshPhongMaterial({
    color: 0x3b82f6,
    specular: 0x6666aa,
    shininess: 40
  }));
  m.rotation.x = -Math.PI / 2;
  scene.add(m);
}, undefined, (err) => {
  console.error('STL load error:', err);
  el.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#64748b;font-size:14px;flex-direction:column;gap:8px"><span style="font-size:32px">△</span>Nie mozna zaladowac podgladu 3D</div>';
});

function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}
animate();

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

window.showEmbed = function() {
  prompt('Embed code:', '<iframe src="/e/__JOB_ID__" width="800" height="500" frameborder="0"></iframe>');
};
</script>
<script>
let _descVisible = false;
let _jobId = __JOB_ID__;
function toggleDescPanel() {
  _descVisible = !_descVisible;
  const p = document.getElementById('descriptionPanel');
  if (p) p.style.display = _descVisible ? 'block' : 'none';
}
function renderDescription(title, tags, bodyHtml, youtubeUrl) {
  const hasDesc = title || tags.length || bodyHtml || youtubeUrl;
  if (!hasDesc) return;
  document.getElementById('descToggle').style.display = 'block';
  document.getElementById('descTitle').textContent = title || '';
  document.getElementById('descTags').innerHTML = tags.map(function(t){return '<span style="padding:2px 8px;border:1px solid #d1d5db;border-radius:999px;font-size:11px;color:#64748b">'+t+'</span>'}).join('');
  document.getElementById('descBody').innerHTML = bodyHtml || '';
  if (youtubeUrl) {
    const match = youtubeUrl.match(/(?:v=|youtu\.be\/|embed\/)([a-zA-Z0-9_-]+)/);
    if (match) {
      document.getElementById('descYoutube').style.display = 'block';
      document.getElementById('descYoutubeFrame').src = 'https://www.youtube.com/embed/' + match[1];
    }
  }
}
function renderComments(comments) {
  const el = document.getElementById('commentsList');
  if (!comments || !comments.length) { el.innerHTML = '<div style="color:#94a3b8;font-size:13px">Brak komentarzy</div>'; return; }
  el.innerHTML = comments.map(function(c){
    const d = c.created_at ? new Date(c.created_at).toLocaleDateString('pl-PL') : '';
    return '<div class="comment-item"><span class="comment-user">'+(c.username||'anon')+'</span><span class="comment-date">'+d+'</span><div class="comment-body">'+(c.body||'').replace(/</g,'&lt;')+'</div></div>';
  }).join('');
}
async function loadComments() {
  try {
    const r = await fetch('/api/jobs/' + _jobId + '/comments');
    if (r.ok) { const d = await r.json(); renderComments(d); }
  } catch(e) {}
}
async function postComment() {
  const body = document.getElementById('commentBody').value.trim();
  if (!body) return;
  const token = localStorage.getItem('mt_token');
  if (!token) { alert('Zaloguj się by komentować'); return; }
  try {
    const r = await fetch('/api/jobs/' + _jobId + '/comments', {
      method: 'POST',
      headers: {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'},
      body: JSON.stringify({body: body})
    });
    if (r.ok) { document.getElementById('commentBody').value = ''; loadComments(); }
    else { const e = await r.json().catch(function(){}); alert(e.detail || 'Błąd'); }
  } catch(e) { alert('Błąd sieci'); }
}
loadComments();
if (localStorage.getItem('mt_token')) document.getElementById('commentForm').style.display = 'block';
__DESC_INIT__
</script>
<div id="adBottom" style="position:fixed;bottom:0;left:0;right:0;z-index:20;display:flex;justify-content:center;background:rgba(255,255,255,.92);border-top:1px solid #e5e7eb;padding:8px 16px"><div class="ad-slot" data-slot="page_bottom" style="max-width:728px;min-height:90px;width:100%"></div></div>
<script>
(function(){
  fetch('/api/ads/slots').then(function(r){return r.ok?r.json():[]}).then(function(d){
    var slots=Array.isArray(d)?d:(d.slots||[]);
    slots.forEach(function(s){
      var key=s.position||s.slot_key;
      var el=document.querySelector('.ad-slot[data-slot="'+key+'"]');
      if(el&&s.ad_code){el.innerHTML=s.ad_code;}
    });
  }).catch(function(){});
})();
</script>
</body>
</html>"""


def _render_share(template: str, **kwargs) -> str:
    """Replace __KEY__ placeholders — safe for JS curly braces."""
    html_out = template
    for k, v in kwargs.items():
        html_out = html_out.replace(f"__{k.upper()}__", str(v))
    return html_out


@router.get("/s/{token}", response_class=HTMLResponse)
def share_page(token: str, request: Request, db: Session = Depends(get_db)):
    share = db.query(models.ShareLink).filter(
        models.ShareLink.token == token, models.ShareLink.is_active == True  # noqa
    ).first()

    lang = _lang(request)
    is_pl = lang == "pl"

    if not share:
        title = "Link nie istnieje" if is_pl else "Link not found"
        return HTMLResponse(f"<h1>{title}</h1>", status_code=404)

    # Increment view counter
    share.views = (share.views or 0) + 1
    db.commit()

    job = share.job
    faces_n = job.result_faces or "?"
    faces_word = "ścianek STEP" if is_pl else "STEP faces"
    mode = job.mode or "auto"
    size_kb = job.result_size_bytes // 1024 if job.result_size_bytes else "?"
    downloads = share.downloads or 0
    times_word = "razy" if is_pl else "times"
    time_word = "Czas" if is_pl else "Time"
    orig_size_word = "Oryginał" if is_pl else "Original"
    proc_time = f"{job.processing_time_s:.1f} s" if job.processing_time_s else "?"
    file_size_orig = _fmt_bytes(job.file_size_bytes)

    conv_info = (
        f'<span class="pill">📐 {faces_n} {html.escape(str(faces_word))}</span>'
        f'<span class="pill">⚙️ {html.escape(str(mode))}</span>'
        f'<span class="pill">⏱ {html.escape(time_word)}: {html.escape(str(proc_time))}</span>'
        f'<span class="pill">📄 {html.escape(orig_size_word)}: {html.escape(file_size_orig)}</span>'
        f'<span class="pill">⬇ {downloads} {html.escape(str(times_word))}</span>'
    )

    show_author = getattr(share, "show_author", True)
    if show_author and getattr(share, "user", None) and share.user.email:
        prefix = "Udostępnił" if is_pl else "Shared by"
        author_info = f"{prefix}: {html.escape(share.user.email)}"
    else:
        author_info = ""

    # robots for unlisted shares
    robots_tag = '<meta name="robots" content="noindex, nofollow">' if getattr(share, "visibility", "public") == "unlisted" else ""
    # description / blog panel data
    _desc_title = str(getattr(job, "title", None) or job.original_filename or "")
    _tags_raw = getattr(job, "tags", None)
    _tags_parsed = _tags_list(_tags_raw)
    _tags_escaped = [html.escape(str(t)) for t in _tags_parsed]
    _desc_body_html = _md_to_html(getattr(job, "description", None) or "")
    _yt = str(getattr(job, "youtube_url", None) or "")
    # Build JS-safe literals via json.dumps
    _js_title = json.dumps(_desc_title)
    _js_tags = json.dumps(_tags_escaped)
    _js_body = json.dumps(_desc_body_html)
    _js_youtube = json.dumps(_yt)
    _desc_init_js = f"renderDescription({_js_title},{_js_tags},{_js_body},{_js_youtube});"
    html_page = _render_share(
        _SHARE_HTML_TEMPLATE,
        lang=lang,
        robots=robots_tag,
        filename=html.escape(job.original_filename or "model"),
        faces=faces_n,
        faces_word=faces_word,
        mode=mode,
        size=size_kb,
        downloads=downloads,
        times_word=times_word,
        token=token,
        download_btn="Pobierz STEP" if is_pl else "Download STEP",
        embed_btn="Osadź" if is_pl else "Embed",
        uuid=job.uuid,
        job_id=job.id,
        conv_info=conv_info,
        author_info=author_info,
        time_word=time_word,
        processing_time=proc_time,
        file_size_orig=file_size_orig,
        orig_size_word=orig_size_word,
        desc_title=html.escape(_desc_title),
        desc_tags=",".join(_tags_escaped),
        desc_body=_desc_body_html,
        desc_youtube=html.escape(_yt),
        desc_init=_desc_init_js,
        og_desc=html.escape((getattr(job, "description", None) or getattr(job, "title", None) or job.original_filename or "Model 3D")[:180]),
        og_image=f"https://3dhosty.com/api/preview/{job.uuid}",
        og_url=f"/s/{token}",

    )

    return HTMLResponse(html_page)


@router.get("/e/{job_id}", response_class=HTMLResponse)
def embed_page(job_id: int, db: Session = Depends(get_db)) -> HTMLResponse:
    """Minimal embed page — Three.js viewer + download for iframe use."""
    job = db.query(models.Job).filter(
        models.Job.id == job_id, models.Job.status == "done"  # noqa
    ).first()
    if not job:
        return HTMLResponse("<h1>Job not found</h1>", status_code=404)

    faces = job.result_faces or "?"
    size_kb = job.result_size_bytes // 1024 if job.result_size_bytes else "?"
    filename = html.escape(job.original_filename or "model")
    uuid = job.uuid

    html_page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta property="og:title" content="{filename} — 3dhosty.com">
<meta property="og:description" content="Podgląd 3D — {faces} ścian STEP">
<meta property="og:image" content="https://3dhosty.com/api/preview/{uuid}">
<meta name="twitter:card" content="summary_large_image">
<title>{filename} — 3dhosty.com</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html, body {{ height: 100%; }}
  body {{ font: 13px/1.4 system-ui, sans-serif; background: #f7f9fc; color: #1e293b;
    display: flex; flex-direction: column; }}
  .top {{ display: flex; align-items: center; justify-content: space-between;
    padding: 10px 14px; border-bottom: 1px solid #2a2a3a; background: #fff; }}
  .top h1 {{ font-size: 14px; font-weight: 600; white-space: nowrap; overflow: hidden;
    text-overflow: ellipsis; margin-right: 12px; }}
  .top a {{ display: inline-block; padding: 6px 16px; background: #3b82f6; flex-shrink: 0;
    color: #fff; font-weight: 600; border-radius: 6px; text-decoration: none; font-size: 12px; }}
  #viewer3d {{ width: 100%; flex: 1; min-height: 300px; background: #f0f2f5; }}
</style>
</head>
<body>
<div class="top">
  <h1>{filename}</h1>
  <a href="/api/download/{uuid}">Download STEP ({faces} faces, {size_kb} KB)</a>
  <a href="/s/{uuid}" style="background:#6366f1;font-size:11px;padding:5px 12px" target="_blank">Pełna strona ↗</a>
</div>
<div id="viewer3d"></div>
<script type="importmap">
{{"imports":{{"three":"/vendor/three/three.module.js","three/addons/":"/vendor/three/"}}}}
</script>
<script type="module">
import * as THREE from 'three';
import {{ OrbitControls }} from 'three/addons/controls/OrbitControls.js';
import {{ STLLoader }} from 'three/addons/loaders/STLLoader.js';
const el = document.getElementById('viewer3d');
const scene = new THREE.Scene();
scene.background = new THREE.Color(0xf0f2f5);
const camera = new THREE.PerspectiveCamera(50, el.clientWidth / el.clientHeight, 0.1, 1000);
camera.position.set(0, 40, 60);
const renderer = new THREE.WebGLRenderer({{ antialias: true }});
renderer.setSize(el.clientWidth, el.clientHeight);
renderer.setPixelRatio(window.devicePixelRatio);
el.appendChild(renderer.domElement);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.enableRotate = true;
controls.enablePan = true;
controls.enableZoom = true;
controls.minDistance = 5;
controls.maxDistance = 500;
controls.minPolarAngle = 0.1;
controls.maxPolarAngle = Math.PI - 0.1;
scene.add(new THREE.AmbientLight(0x404060, 1.2));
const d1 = new THREE.DirectionalLight(0x3b82f6, 1.0); d1.position.set(30,50,30); scene.add(d1);
const d2 = new THREE.DirectionalLight(0x8888ff, 0.5); d2.position.set(-20,10,-30); scene.add(d2);
new STLLoader().load('/api/stl-preview/{uuid}', g => {{
  g.computeBoundingBox();
  const c = new THREE.Vector3(); g.boundingBox.getCenter(c);
  g.translate(-c.x, -c.y, -c.z);
  const s = new THREE.Vector3(); g.boundingBox.getSize(s);
  const mx = Math.max(s.x, s.y, s.z);
  if(mx > 0) g.scale(30/mx, 30/mx, 30/mx);
  const m = new THREE.Mesh(g, new THREE.MeshPhongMaterial({{ color: 0x3b82f6, specular: 0x6666aa, shininess: 40 }}));
  m.rotation.x = -Math.PI/2;
  scene.add(m);
}});
function animate() {{ requestAnimationFrame(animate); controls.update(); renderer.render(scene, camera); }}
animate();
window.addEventListener('resize', () => {{
  camera.aspect = el.clientWidth / el.clientHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(el.clientWidth, el.clientHeight);
}});
</script>
</body></html>"""

    return HTMLResponse(html_page)
