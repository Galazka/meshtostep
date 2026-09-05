"""Share link public page with 3D preview."""
import html

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from .database import get_db
from . import models

router = APIRouter(tags=["share"])


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
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><text y='24' font-size='24'>📁</text></svg>">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { height: 100%; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0c0c14;
    color: #e0e0e8;
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
    background: #16161f;
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
  .btn-primary { background: #3b82f6; color: #fff; }
  .btn-secondary { background: #2a2a3a; color: #e0e0e8; }
  #viewer3d {
    position: fixed;
    inset: 0;
    width: 100vw;
    height: 100vh;
    background: #0a0a12;
  }
  #viewer3d canvas { display: block; }
  @media (max-width: 860px) {
    .pills { display: none; }
    .file-block { max-width: 45vw; }
    .btn { padding: 8px 12px; font-size: 13px; }
  }
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

<script type="importmap">
{
  "imports": {
    "three": "https://unpkg.com/three@0.164.1/build/three.module.js",
    "three/addons/": "https://unpkg.com/three@0.164.1/examples/jsm/"
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
scene.background = new THREE.Color(0x0a0a12);
const camera = new THREE.PerspectiveCamera(50, window.innerWidth / window.innerHeight, 0.1, 1000);
camera.position.set(0, 40, 60);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(window.devicePixelRatio);
el.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;

scene.add(new THREE.AmbientLight(0x404060, 1.2));
const d1 = new THREE.DirectionalLight(0x3b82f6, 1.0);
d1.position.set(30, 50, 30);
scene.add(d1);
const d2 = new THREE.DirectionalLight(0x8888ff, 0.5);
d2.position.set(-20, 10, -30);
scene.add(d2);
scene.add(new THREE.GridHelper(100, 20, 0x2a2a3a, 0x16161f));

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
}, undefined, () => { el.style.display = 'none'; });

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
<title>{filename} — 3dhosty.com</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html, body {{ height: 100%; }}
  body {{ font: 13px/1.4 system-ui, sans-serif; background: #0c0c14; color: #e0e0e8;
    display: flex; flex-direction: column; }}
  .top {{ display: flex; align-items: center; justify-content: space-between;
    padding: 10px 14px; border-bottom: 1px solid #2a2a3a; background: #16161f; }}
  .top h1 {{ font-size: 14px; font-weight: 600; white-space: nowrap; overflow: hidden;
    text-overflow: ellipsis; margin-right: 12px; }}
  .top a {{ display: inline-block; padding: 6px 16px; background: #3b82f6; flex-shrink: 0;
    color: #fff; font-weight: 600; border-radius: 6px; text-decoration: none; font-size: 12px; }}
  #viewer3d {{ width: 100%; flex: 1; min-height: 300px; background: #0a0a12; }}
</style>
</head>
<body>
<div class="top">
  <h1>{filename}</h1>
  <a href="/api/download/{uuid}">Download STEP ({faces} faces, {size_kb} KB)</a>
</div>
<div id="viewer3d"></div>
<script type="importmap">
{{"imports":{{"three":"https://unpkg.com/three@0.164.1/build/three.module.js","three/addons/":"https://unpkg.com/three@0.164.1/examples/jsm/"}}}}
</script>
<script type="module">
import * as THREE from 'three';
import {{ OrbitControls }} from 'three/addons/controls/OrbitControls.js';
import {{ STLLoader }} from 'three/addons/loaders/STLLoader.js';
const el = document.getElementById('viewer3d');
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0a0a12);
const camera = new THREE.PerspectiveCamera(50, el.clientWidth / el.clientHeight, 0.1, 1000);
camera.position.set(0, 40, 60);
const renderer = new THREE.WebGLRenderer({{ antialias: true }});
renderer.setSize(el.clientWidth, el.clientHeight);
renderer.setPixelRatio(window.devicePixelRatio);
el.appendChild(renderer.domElement);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
scene.add(new THREE.AmbientLight(0x404060, 1.2));
const d1 = new THREE.DirectionalLight(0x3b82f6, 1.0); d1.position.set(30,50,30); scene.add(d1);
const d2 = new THREE.DirectionalLight(0x8888ff, 0.5); d2.position.set(-20,10,-30); scene.add(d2);
scene.add(new THREE.GridHelper(100, 20, 0x2a2a3a, 0x16161f));
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
