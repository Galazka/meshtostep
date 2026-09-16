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


def _safe_url(url: str) -> str:
    """Allowlist: only http/https. javascript:/data:/vbscript: → plain text."""
    u = str(url or "").strip()
    if re.match(r"^https?://", u, re.IGNORECASE):
        return u
    return ""


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
    esc = re.sub(r"!\[([^\]]*)\]\(([^)\\s]+)\\)", lambda m: f'<img src="{_safe_url(m.group(2))}" alt="{m.group(1)}" loading="lazy">' if _safe_url(m.group(2)) else '', esc)
    esc = re.sub(r"\[([^\]]+)\]\(([^)\\s]+)\\)", lambda m: f'<a href="{_safe_url(m.group(2))}" target="_blank" rel="noopener">{m.group(1)}</a>' if _safe_url(m.group(2)) else m.group(1), esc)
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
<title>__FILENAME__ — 3dfile.link</title>
<meta property="og:type" content="website">
<meta property="og:site_name" content="3dfile.link">
<meta property="og:title" content="__FILENAME__ — 3dfile.link">
<meta property="og:description" content="__OG_DESC__">
<meta property="og:image" content="__OG_IMAGE__">
<meta property="og:url" content="__OG_URL__">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="__FILENAME__ — 3dfile.link">
<meta name="twitter:description" content="__OG_DESC__">
<meta name="twitter:image" content="__OG_IMAGE__">
__JSON_LD__
<script src="/js/cadviewer.js" defer></script>
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
    z-index: 15;
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 10px 16px;
    background: rgba(255,255,255,.85);
    backdrop-filter: blur(8px);
    border-bottom: 1px solid #e2e8f0;
  }
  .file-block { min-width: 0; max-width: 30vw; }
  .file {
    font-weight: 700;
    font-size: 14px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .shared-by { font-size: 12px; color: #64748b; margin-top: 2px; }
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
    border: 1px solid #e2e8f0;
    border-radius: 999px;
    background: #f8fafc;
    color: #475569;
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
  .btn-secondary { background: #e5e7eb; color: #374151; }
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
    <a href="/" style="text-decoration:none;margin-right:8px;flex-shrink:0"><img src="/logo.png?v=2" alt="3DFILE" style="height:48px" onerror="this.style.display='none'"></a>
    <div class="file" title="__FILENAME__">__FILENAME__</div>
    <div class="shared-by">__AUTHOR_INFO__</div>
  </div>
  <div class="pills">__CONV_INFO__</div>
  <div id="expiryInfo" style="font-size:12px;color:#64748b;padding:4px 0">__EXPIRY_INFO__</div>
  <div class="actions" style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
    <select id="dlFormat" style="padding:8px 10px;border:1px solid #d1d5db;border-radius:6px;font-size:13px;background:#fff">
      <option value="step">Solid — STEP (CAD/CAM)</option>
      <option value="stl">Mesh — __FMT_STL__</option>
      <option value="obj">Mesh — __FMT_OBJ__</option>
      <option value="3mf">Mesh — __FMT_3MF__</option>
    </select>
    <select id="dlQuality" style="padding:8px 10px;border:1px solid #d1d5db;border-radius:6px;font-size:13px;background:#fff">
      <option value="ultra">__Q_ULTRA__</option>
      <option value="auto" selected>__Q_AUTO__</option>
      <option value="light">__Q_LIGHT__</option>
      <option value="smooth">__Q_SMOOTH__</option>
      <option value="off">__Q_OFF__</option>
    </select>
    <a class="btn btn-primary" href="#" id="dlBtn" onclick="convertAndDownload('__UUID__');return false">⬇ __DOWNLOAD_BTN__</a>
    <button class="btn btn-secondary" onclick="showEmbed('__TOKEN__')">⧉ __EMBED_BTN__</button>
  </div>
</header>
<div id="viewer3d" style="position:fixed;inset:0;top:0;left:0;right:0;bottom:0"></div>
<button id="panelToggle" onclick="document.getElementById('sharePanel').classList.toggle('open')" style="position:fixed;right:16px;top:50%;transform:translateY(-50%);z-index:30;background:rgba(255,255,255,.95);border:1px solid #e2e8f0;border-radius:50%;width:44px;height:44px;font-size:20px;cursor:pointer;box-shadow:0 2px 12px rgba(0,0,0,.15)">⚙️</button>
<div id="sharePanel" style="position:fixed;right:-320px;top:0;bottom:0;width:300px;z-index:25;background:rgba(255,255,255,.97);border-left:1px solid #e2e8f0;transition:right .3s ease;overflow-y:auto;padding:16px;box-shadow:-4px 0 16px rgba(0,0,0,.1)">
<style>#sharePanel.open{right:0!important}</style>
<div id="shareColorBar" style="display:flex;gap:6px;background:#fff;padding:8px 10px;border-radius:10px;border:1px solid #e2e8f0;align-items:center;flex-wrap:wrap;margin-bottom:12px">
  <span style="font-size:10px;color:#94a3b8;margin-right:2px">Tło:</span>
  <div id="bgSwatches"></div>
  <div style="width:1px;height:20px;background:#e2e8f0;margin:0 4px"></div>
  <span style="font-size:10px;color:#94a3b8;margin-right:2px">Model:</span>
  <div id="meshSwatches"></div>
  <button id="wireBtn" style="border:none;background:#f1f5f9;border-radius:6px;padding:4px 10px;font-size:11px;cursor:pointer;margin-left:4px" onclick="(function(){var m=window._shareMesh;if(!m)return;m.material.wireframe=!m.material.wireframe;this.textContent=m.material.wireframe?'__WIRE_ON__':'__WIRE_OFF__';}).call(this)">__WIRE_OFF__</button>
</div>
<div id="materialCalc" style="display:none;position:fixed;bottom:12px;left:16px;z-index:20;background:rgba(255,255,255,.95);border:1px solid #e2e8f0;border-radius:10px;padding:12px 16px;font-size:12px;min-width:220px;box-shadow:0 2px 12px rgba(0,0,0,.08)">
  <div style="font-weight:600;margin-bottom:8px;color:#1e293b">Estymacja druku 3D</div>
  <div style="display:flex;gap:6px;margin-bottom:6px">
    <select id="matSelect" style="flex:1;padding:4px 6px;border:1px solid #d1d5db;border-radius:4px;font-size:11px">
      <option value="PLA">PLA (1.24 g/cm&sup3;)</option>
      <option value="PETG">PETG (1.27 g/cm&sup3;)</option>
      <option value="ABS">ABS (1.04 g/cm&sup3;)</option>
      <option value="TPU">TPU (1.21 g/cm&sup3;)</option>
      <option value="ASA">ASA (1.07 g/cm&sup3;)</option>
    </select>
    <select id="infillSelect" style="width:60px;padding:4px 6px;border:1px solid #d1d5db;border-radius:4px;font-size:11px">
      <option value="10">10%</option>
      <option value="20" selected>20%</option>
      <option value="50">50%</option>
      <option value="100">100%</option>
    </select>
  </div>
  <div id="matResult" style="color:#475569">
    <span id="matWeight">--</span> g
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:8px">
    <label style="font-size:10px;color:#94a3b8">Filament zł/kg<input id="matPriceKg" type="number" min="0" step="1" value="89" style="width:100%;padding:4px 6px;border:1px solid #d1d5db;border-radius:4px;font-size:11px"></label>
    <label style="font-size:10px;color:#94a3b8">Prąd zł/kWh<input id="matKwhPrice" type="number" min="0" step="0.01" value="1.15" style="width:100%;padding:4px 6px;border:1px solid #d1d5db;border-radius:4px;font-size:11px"></label>
    <label style="font-size:10px;color:#94a3b8">Drukarka W<input id="matWatts" type="number" min="0" step="10" value="150" style="width:100%;padding:4px 6px;border:1px solid #d1d5db;border-radius:4px;font-size:11px"></label>
    <label style="font-size:10px;color:#94a3b8">Czas druku h<input id="matHours" type="number" min="0" step="0.5" value="2" style="width:100%;padding:4px 6px;border:1px solid #d1d5db;border-radius:4px;font-size:11px"></label>
  </div>
  <div id="matTotal" style="margin-top:8px;font-size:13px;color:#1e293b"></div>
  <div id="matVolume" style="color:#94a3b8;font-size:10px;margin-top:4px"></div>
  <div id="matAffiliates" style="margin-top:6px;font-size:10px;color:#94a3b8"></div>
</div>
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
    "three/addons/controls/OrbitControls.js": "/vendor/three/controls/OrbitControls.js",
    "three/addons/loaders/STLLoader.js": "/vendor/three/loaders/STLLoader.js",
    "three/addons/loaders/OBJLoader.js": "/vendor/three/loaders/OBJLoader.js",
    "three/addons/loaders/3MFLoader.js": "/vendor/three/loaders/3MFLoader.js"
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

const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });  /* 3dfile share viewer */;
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
function fitViewer() {
  const w = el.clientWidth || 640, h = el.clientHeight || 420;
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h);
  renderer.domElement.style.width = '100%';
  renderer.domElement.style.height = '100%';
}
fitViewer();
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

// STEP/IGES B-Rep via OCCT WASM (client-side, zero server cost). STL/3MF/OBJ skip WASM.
window.__shareStatus = '__SHARE_STATUS__';
window.__shareFilename = '__SHARE_FILENAME__';
var _fn = (window.__shareFilename || '').toLowerCase();
var _isStep = _fn.endsWith('.step') || _fn.endsWith('.stp') || _fn.endsWith('.iges') || _fn.endsWith('.igs');
if (window.loadStepWithOcct && window.__shareStatus === "done" && _isStep) {
  fetch('/api/stl-preview/__UUID__').then(function(r){return r.arrayBuffer();}).then(function(buf){
    window.loadStepWithOcct(buf).then(function(mesh){
      if(!mesh){ loadStlFallback(); return; }
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.BufferAttribute(mesh.positions, 3));
      if(mesh.normals.length) geo.setAttribute('normal', new THREE.BufferAttribute(mesh.normals, 3));
      geo.computeBoundingSphere();
      const m = new THREE.Mesh(geo, new THREE.MeshPhongMaterial({ color: 0x3b82f6, specular: 0x6666aa, shininess: 40 }));
      m.rotation.x = -Math.PI/2;
      scene.add(m);
      document.getElementById('shareColorBar').style.display='flex';
      window._shareMesh = m;
    }).catch(loadStlFallback);
  }).catch(loadStlFallback);
} else { loadStlFallback(); }
function loadStlFallback() {
  new STLLoader().load('/api/stl-preview/__UUID__', (g) => {
  g.computeBoundingBox();
  const c = new THREE.Vector3();
  g.boundingBox.getCenter(c);
  g.translate(-c.x, -c.y, -c.z);
  const s = new THREE.Vector3();
  g.boundingBox.getSize(s);
  const mx = Math.max(s.x, s.y, s.z);
  if (mx > 0) g.scale(30 / mx, 30 / mx, 30 / mx);
  document.getElementById('shareColorBar').style.display='flex';
  window._shareMesh = new THREE.Mesh(g, new THREE.MeshPhongMaterial({
    color: 0x3b82f6,
    specular: 0x6666aa,
    shininess: 40
  }));
  window._shareMesh.rotation.x = -Math.PI / 2;
  scene.add(window._shareMesh);
  }, undefined, (err) => {
  console.error('STL load error:', err);
  var img=new Image();
  img.onload=function(){el.innerHTML='';img.style.cssText='width:100%;height:100%;object-fit:contain';el.appendChild(img);};
  img.onerror=function(){el.innerHTML='<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#64748b;font-size:14px;flex-direction:column;gap:8px"><span style="font-size:32px">△</span>Podglad 3D niedostepny</div>';};
  img.src='/api/preview/__UUID__';
});
}

function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}
animate();

// Color picker for share viewer — bg + mesh swatches
(function(){
  var bgColors=['#f0f2f5','#ffffff','#000000','#f7f9fc','#e2e8f0','#1e293b'];
  var meshColors=['#3b82f6','#ffffff','#9ca3af','#22c55e','#ef4444','#f97316','#a855f7','#06b6d3'];
  var bgBar=document.getElementById('bgSwatches');
  var meshBar=document.getElementById('meshSwatches');
  var bar=document.getElementById('shareColorBar');
  if(!bar)return;
  bar.style.display='none';
  bgColors.forEach(function(hex){
    var d=document.createElement('div');
    d.style.cssText='width:32px;height:32px;border-radius:50%;cursor:pointer;border:2px solid transparent;background:'+hex+';flex-shrink:0';
    d.className='bg-swatch';
    d.onclick=function(){
      scene.background=new THREE.Color(hex);
      var kids=bgBar.querySelectorAll('.bg-swatch');
      for(var i=0;i<kids.length;i++) kids[i].style.borderColor='transparent';
      d.style.borderColor='#333';
    };
    bgBar.appendChild(d);
  });
  meshColors.forEach(function(hex){
    var d=document.createElement('div');
    d.style.cssText='width:32px;height:32px;border-radius:50%;cursor:pointer;border:2px solid transparent;background:'+hex+';flex-shrink:0';
    d.className='m-swatch';
    d.onclick=function(){
      if(window._shareMesh) window._shareMesh.material.color.set(hex);
      var kids=meshBar.querySelectorAll('.m-swatch');
      for(var i=0;i<kids.length;i++) kids[i].style.borderColor='transparent';
      d.style.borderColor='#333';
    };
    meshBar.appendChild(d);
  });
})();

window.addEventListener('resize', fitViewer);
window.addEventListener('orientationchange', function(){ setTimeout(fitViewer, 300); });
document.addEventListener('fullscreenchange', function(){ setTimeout(fitViewer, 300); });

</script>
<script>
(function(){
  window.showEmbed = function(tok) {
    var code = '<iframe src="https://3dfile.link/e/__JOB_ID__" width="800" height="500" frameborder="0" allowfullscreen></iframe>';
    if(tok) code = '<iframe src="https://3dfile.link/s/' + tok + '" width="800" height="500" frameborder="0" allowfullscreen></iframe>';
    navigator.clipboard.writeText(code).then(function(){
      var el = document.getElementById('dlBtn');
      if(el){ var orig = el.textContent; el.textContent = 'Kod skopiowany!'; setTimeout(function(){ el.textContent = orig; }, 2000); }
    }).catch(function(){ prompt('Kod osadzania:', code); });
  };
  window.convertAndDownload = function(uuid){
    var fmtSel = document.getElementById('dlFormat');
    var fmt = fmtSel ? fmtSel.value : 'step';
    var qSel = document.getElementById('dlQuality');
    var mode = qSel ? qSel.value : 'auto';
    var btn = document.getElementById('dlBtn');
    if(btn) btn.textContent='Pobieranie...';
    if(fmt === 'step'){
      if(btn) btn.textContent='Konwertowanie...';
      fetch('/api/convert-on-demand/'+uuid+'?mode='+mode,{method:'POST'})
        .then(function(r){return r.json();})
        .then(function(d){
          if(!(d&&d.ok)){ alert('Błąd konwersji'); return; }
          if(d.cached){ window.location.href='/api/download/'+uuid+'?format=step'; return; }
          var t0 = Date.now();
          var iv = setInterval(function(){
            if(Date.now()-t0 > 10*60*1000){ clearInterval(iv); alert('Konwersja trwa długo — link do pobrania przyjdzie mailem (zalogowani) lub odśwież stronę.'); return; }
            fetch('/api/jobs/'+uuid+'/conv-status').then(function(rs){return rs.json();}).then(function(st){
              if(btn) btn.textContent = st.status==='converting' ? 'Konwertowanie…' : ('W kolejce'+(st.queue_position?' #'+st.queue_position:'')+'…');
              if(st.status==='done'){ clearInterval(iv); window.location.href='/api/download/'+uuid+'?format=step'; }
              if(st.status==='error'){ clearInterval(iv); alert('Błąd konwersji'); }
            });
          }, 3000);
        })
        .catch(function(){alert('Błąd sieci');});
    } else {
      window.location.href='/api/download/'+uuid+'?format='+fmt;
    }
  };
})();
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
// Expiry countdown (share page)
(function(){
  var expIso = '__EXPIRE_ISO__';
  if (!expIso) return;
  var el = document.getElementById('expiryCountdown');
  if (!el) return;
  function tick() {
    var target = new Date(expIso);
    var now = new Date();
    var ms = target.getTime() - now.getTime();
    if (isNaN(ms) || ms <= 0) {
      el.textContent = '⛔ wygasł';
      return;
    }
    var d = Math.floor(ms / 86400000);
    var h = Math.floor((ms % 86400000) / 3600000);
    var m = Math.floor((ms % 3600000) / 60000);
    var s = Math.floor((ms % 60000) / 1000);
    el.textContent = (d > 0 ? d + 'd ' : '') + h + 'h ' + m + 'm ' + s + 's';
  }
  tick();
  setInterval(tick, 1000);
})();
async function loadComments() {
  try {
    const r = await fetch('/api/jobs/' + _jobId + '/comments');
    if (r.ok) { const d = await r.json(); renderComments(d); }
  } catch(e) {}
};

// Material / filament calculator
(function(){
  var uuid = '__UUID__';
  fetch('/api/material/' + uuid).then(function(r){return r.ok?r.json():null}).then(function(d){
    if(!d||!d.estimates) return;
    var el = document.getElementById('materialCalc');
    if(el) el.style.display = 'block';
    var volEl = document.getElementById('matVolume');
    if(volEl) volEl.textContent = 'Objetosc: ' + d.volume_cm3 + ' cm3' + (d.dims_mm ? ' | ' + d.dims_mm : '');
    function updateCalc(){
      var matEl = document.getElementById('matSelect');
      var infillEl = document.getElementById('infillSelect');
      if(!matEl || !infillEl) return;
      var mat = matEl.value;
      var infill = infillEl.value;
      var key = mat + '_' + infill;
      var e = d.estimates[key];
      var num = function(id, def){ var el = document.getElementById(id); var v = el ? parseFloat(el.value) : NaN; return isNaN(v) ? def : v; };
      if(e){
        document.getElementById('matWeight').textContent = e.weight_g;
        var filCost = e.weight_g / 1000 * num('matPriceKg', 89);
        var powCost = num('matWatts', 150) / 1000 * num('matHours', 2) * num('matKwhPrice', 1.15);
        var total = filCost + powCost;
        document.getElementById('matTotal').innerHTML =
          'Filament: <b>' + filCost.toFixed(2) + ' zł</b> + prąd: <b>' + powCost.toFixed(2) + ' zł</b><br>' +
          '<span style="font-size:15px">Razem: <b>' + total.toFixed(2) + ' zł</b></span>';
      }
      var aff = document.getElementById('matAffiliates');
      if(aff){
        aff.innerHTML = 'Kup filament: <a href="https://allegro.pl/listing?string=' + encodeURIComponent(mat+' filament') + '" target="_blank" rel="nofollow sponsored noopener" style="color:#1a56db">Allegro</a> &middot; <a href="https://www.amazon.pl/s?k=' + encodeURIComponent(mat+' filament 1.75') + '" target="_blank" rel="nofollow sponsored noopener" style="color:#1a56db">Amazon</a>';
      }
    }
    document.getElementById('matSelect').onchange = updateCalc;
    document.getElementById('infillSelect').onchange = updateCalc;
    ['matPriceKg','matKwhPrice','matWatts','matHours'].forEach(function(id){
      var el = document.getElementById(id);
      if(el) el.oninput = updateCalc;
    });
    updateCalc();
  }).catch(function(){});
})();
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
    # Expiry: dead links stay dead
    if getattr(share, "expires_at", None):
        from datetime import datetime as _dt
        if share.expires_at < _dt.utcnow():
            title = "Link wygasł" if is_pl else "Link expired"
            return HTMLResponse(f"<h1>{title}</h1>", status_code=410)
    job = share.job
    if not job or getattr(job, "status", None) == "deleted":
        title = "Link nie istnieje" if is_pl else "Link not found"
        return HTMLResponse(f"<h1>{title}</h1>", status_code=404)

    # Increment view counter (atomic)
    db.query(models.ShareLink).filter(models.ShareLink.id == share.id).update(
        {models.ShareLink.views: models.ShareLink.views + 1}
    )
    db.commit()

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

    # Expiry info
    expires_at = getattr(share, "expires_at", None)
    if expires_at:
        from datetime import datetime as _dt
        _exp_str = str(expires_at)
        _exp_iso = _exp_str.replace(" ", "T") if "T" not in _exp_str else _exp_str
        expiry_word = "Ważny do" if is_pl else "Expires"
        expire_label = "wygasł" if is_pl else "expired"
        expiry_info = f'<span class="pill">{html.escape(expiry_word)}: <b id="expiryCountdown">{html.escape(_exp_str[:16])}</b></span>'
    else:
        _exp_iso = ""
        expiry_info = f'<span class="pill">{"Bez limitu" if is_pl else "No expiry"}</span>'

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
        fmt_stl="STL (uniwersalny)" if is_pl else "STL (universal)",
        fmt_obj="OBJ (z teksturami)" if is_pl else "OBJ (with textures)",
        fmt_3mf="3MF (druk 3D)" if is_pl else "3MF (3D printing)",
        q_ultra="Ultra — min. ścianek" if is_pl else "Ultra — min. faces",
        q_auto="Auto — balans detale/rozmiar" if is_pl else "Auto — detail/size balance",
        q_light="Lekko — scala koplanarne" if is_pl else "Light — merge coplanar",
        q_smooth="Gładki — wygładzanie" if is_pl else "Smooth — smoothing",
        q_off="Bez optymalizacji" if is_pl else "No optimization",
        uuid=job.uuid,
        job_id=job.id,
        conv_info=conv_info,
        author_info=author_info,
        expiry_info=expiry_info,
        expire_iso=_exp_iso,
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
        og_image=f"https://3dfile.link/api/og/{job.uuid}",
        og_url=f"https://3dfile.link/s/{token}",
        share_status=job.status,
        share_filename=job.original_filename or "",
        json_ld=f"""<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"3DModel","name":{json.dumps(html.escape(job.title or job.original_filename or ""))},"description":{json.dumps((getattr(job, "description", None) or "")[:300])},"encoding":{{"@type":"MediaObject","fileFormat":"STEP/STL","contentUrl":"https://3dfile.link/api/download/{job.uuid}"}},"image":"https://3dfile.link/api/og/{job.uuid}","url":"https://3dfile.link/s/{token}"}}</script>""",
    )

    return HTMLResponse(html_page)


@router.get("/e/{job_id}", response_class=HTMLResponse)
def embed_page(job_id: str, db: Session = Depends(get_db)) -> HTMLResponse:
    """Minimal embed page — Three.js viewer + download for iframe use."""
    job = None
    if job_id.isdigit():
        job = db.query(models.Job).filter(models.Job.id == int(job_id)).first()
    if not job:
        job = db.query(models.Job).filter(models.Job.uuid == job_id).first()
    if not job or job.status not in ["done", "hosted"]:
        return HTMLResponse("<h1>Job not found</h1>", status_code=404)
    if getattr(job, "visibility", "public") == "private":
        return HTMLResponse("<h1>Job not found</h1>", status_code=404)

    faces = job.result_faces or "?"
    _tok = ""
    try:
        for sh in (getattr(job, "shares", None) or []):
            if getattr(sh, "is_active", False) and getattr(sh, "token", None):
                _tok = sh.token
                break
    except Exception:
        _tok = ""
    size_kb = job.result_size_bytes // 1024 if job.result_size_bytes else "?"
    filename = html.escape(job.original_filename or "model")
    uuid = job.uuid

    html_page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta property="og:title" content="{filename} — 3dfile.link">
<meta property="og:description" content="Podgląd 3D — {faces} ścian STEP">
<meta property="og:image" content="https://3dfile.link/api/preview/{uuid}">
<meta name="twitter:card" content="summary_large_image">
<title>{filename} — 3dfile.link</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html, body {{ height: 100%; }}
  body {{ font: 13px/1.4 system-ui, sans-serif; background: #f7f9fc; color: #1e293b;
    display: flex; flex-direction: column; }}
  .top {{ display: flex; align-items: center; justify-content: space-between;
    padding: 10px 14px; border-bottom: 1px solid #e2e8f0; background: #fff; }}
  .top h1 {{ font-size: 14px; font-weight: 600; white-space: nowrap; overflow: hidden;
    text-overflow: ellipsis; margin-right: 12px; }}
  .top a {{ display: inline-block; padding: 6px 16px; background: #3b82f6; flex-shrink: 0;
    color: #fff; font-weight: 600; border-radius: 6px; text-decoration: none; font-size: 12px; }}
  #viewer3d {{ width: 100%; flex: 1; min-height: 300px; background: #f0f2f5; }}
  .brandbar {{ display: flex; align-items: center; justify-content: center; gap: 6px;
    padding: 5px 10px; background: #0f172a; color: #cbd5e1; font-size: 11px; }}
  .brandbar a {{ color: #fff; font-weight: 700; text-decoration: none; }}
  .brandbar a:hover {{ text-decoration: underline; }}
</style>
</head>
<body>
<div class="top">
  <h1>{filename}</h1>
  <a href="/api/download/{uuid}">Download STEP ({faces} faces, {size_kb} KB)</a>
  <a href="{('/s/' + _tok) if _tok else 'https://3dfile.link'}" style="background:#6366f1;font-size:11px;padding:5px 12px" target="_blank">Pełna strona ↗</a>
</div>
<div id="viewer3d"></div>
<div class="brandbar">Model 3D hostowany za darmo przez <a href="{('https://3dfile.link/s/' + _tok) if _tok else 'https://3dfile.link'}" target="_blank">3dfile.link</a> · <a href="https://3dfile.link" target="_blank">wgraj własny</a></div>
<script type="importmap">
{{"imports":{{"three":"/vendor/three/three.module.js","three/addons/controls/OrbitControls.js":"/vendor/three/controls/OrbitControls.js","three/addons/loaders/STLLoader.js":"/vendor/three/loaders/STLLoader.js"}}}}
</script>
<script type="module">
import * as THREE from 'three';
import {{ OrbitControls }} from 'three/addons/controls/OrbitControls.js';
import {{ STLLoader }} from 'three/addons/loaders/STLLoader.js';
const el = document.getElementById('viewer3d');
// cap canvas to prevent horizontal scroll blowout (mobile 1920px issue)
const _cw = Math.min(el.clientWidth || 640, 1200), _ch = el.clientHeight || 420;
const scene = new THREE.Scene();
scene.background = new THREE.Color(0xf0f2f5);
const camera = new THREE.PerspectiveCamera(50, _cw / _ch, 0.1, 1000);
camera.position.set(0, 40, 60);
const renderer = new THREE.WebGLRenderer({{ antialias: true }});
renderer.setSize(_cw, _ch);
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
  const w = Math.min(el.clientWidth || 640, 1200);
  camera.aspect = w / el.clientHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(w, el.clientHeight);
}});
</script>
</body></html>"""

    return HTMLResponse(html_page)
