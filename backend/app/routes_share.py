"""Share link public page with 3D preview."""
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


_SHARE_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="__LANG__">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__FILENAME__ — MeshToStep</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><text y='24' font-size='24'>📁</text></svg>">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0c0c14;
    color: #e0e0e8;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
  }
  .card {
    width: 100%;
    max-width: 640px;
    background: #16161f;
    border: 1px solid #2a2a3a;
    border-radius: 12px;
    overflow: hidden;
  }
  .card-header {
    padding: 20px 24px;
    border-bottom: 1px solid #2a2a3a;
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .card-header h1 { font-size: 16px; font-weight: 600; }
  .card-header .icon { font-size: 24px; }
  .card-body { padding: 24px; }
  .meta-row {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    margin-bottom: 20px;
    font-size: 13px;
    color: #888;
  }
  .meta-row span { display: flex; align-items: center; gap: 4px; }
  .actions { display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; }
  .btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 10px 20px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    text-decoration: none;
    cursor: pointer;
    border: none;
    transition: opacity 0.2s;
  }
  .btn:hover { opacity: 0.85; }
  .btn-primary { background: #3b82f6; color: #fff; }
  .btn-secondary { background: #2a2a3a; color: #e0e0e8; }
  #viewer3d {
    width: 100%;
    height: 380px;
    background: #0a0a12;
    border: 1px solid #2a2a3a;
    border-radius: 8px;
    overflow: hidden;
  }
  .footer-note {
    margin-top: 16px;
    font-size: 11px;
    color: #555;
    text-align: center;
  }
</style>
</head>
<body>
<div class="card">
  <div class="card-header">
    <span class="icon">📁</span>
    <h1>__FILENAME__</h1>
  </div>
  <div class="card-body">
    <div class="meta-row">
      <span>📐 __FACES__ __FACES_WORD__</span>
      <span>⚙️ __MODE__</span>
      <span>💾 __SIZE__ KB</span>
      <span>⬇ __DOWNLOADS__ __TIMES_WORD__</span>
    </div>
    <div class="actions">
      <a class="btn btn-primary" href="/api/share/__TOKEN__/download">⬇ __DOWNLOAD_BTN__</a>
      <button class="btn btn-secondary" onclick="showEmbed()">⧉ Embed</button>
    </div>
    <div id="viewer3d"></div>
    <div class="footer-note">MeshToStep · FreeCAD headless</div>
  </div>
</div>

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
const camera = new THREE.PerspectiveCamera(50, el.clientWidth / 380, 0.1, 1000);
camera.position.set(0, 40, 60);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(el.clientWidth, 380);
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
  camera.aspect = el.clientWidth / el.clientHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(el.clientWidth, el.clientHeight);
});

window.showEmbed = function() {
  prompt('Embed code:', '<iframe src="/e/__JOB_ID__" width="800" height="500" frameborder="0"></iframe>');
};
</script>
</body>
</html>"""


def _render_share(template: str, **kwargs) -> str:
    """Replace __KEY__ placeholders — safe for JS curly braces."""
    html = template
    for k, v in kwargs.items():
        html = html.replace(f"__{k.upper()}__", str(v))
    return html


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
    size_kb = job.result_size_bytes // 1024 if job.result_size_bytes else "?"
    faces_n = job.result_faces or "?"

    html = _render_share(
        _SHARE_HTML_TEMPLATE,
        lang=lang,
        filename=job.original_filename,
        faces=faces_n,
        faces_word="scianek STEP" if is_pl else "STEP faces",
        mode=job.mode,
        size=size_kb,
        downloads=share.downloads or 0,
        times_word="razy" if is_pl else "times",
        token=token,
        download_btn="Pobierz STEP" if is_pl else "Download STEP",
        uuid=job.uuid,
        job_id=job.id,
    )

    return HTMLResponse(html)


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
    filename = job.original_filename
    uuid = job.uuid

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{filename} — MeshToStep</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font: 13px/1.4 system-ui, sans-serif; background: #0c0c14; color: #e0e0e8; }}
  .top {{ display: flex; align-items: center; justify-content: space-between;
    padding: 10px 14px; border-bottom: 1px solid #2a2a3a; background: #16161f; }}
  .top h1 {{ font-size: 14px; font-weight: 600; }}
  .top a {{ display: inline-block; padding: 6px 16px; background: #3b82f6;
    color: #fff; font-weight: 600; border-radius: 6px; text-decoration: none; font-size: 12px; }}
  .info {{ font-size: 11px; color: #555; padding: 4px 14px; }}
  #viewer3d {{ width: 100%; height: calc(100vh - 70px); min-height: 300px; background: #0a0a12; }}
</style>
</head>
<body>
<div class="top">
  <h1>{filename}</h1>
  <a href="/api/download/{uuid}">Download STEP ({faces} faces, {size_kb} KB)</a>
</div>
<div class="info">MeshToStep · Three.js 3D Preview</div>
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

    return HTMLResponse(html)
