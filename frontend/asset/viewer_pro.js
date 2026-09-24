/* viewer_pro.js — 3dfile.link shared 3D viewer
   gray standard material + edges, orbit controls, floating toolbar,
   print-color bar with material/time/grams + prefill CTA.
   Used by /s/{token}, /u/{user}/{slug}, /e/{id}.  v2
   NOTE: color ids MUST match order.html color codes (PL names mapped there). */
import * as THREE from '/vendor/three/three.module.js';
import { OrbitControls } from '/vendor/three/controls/OrbitControls.js';
import { STLLoader } from '/vendor/three/loaders/STLLoader.js';

const T = {
  pl: { rotate:'Auto-obrót', wire:'Siatka', edges:'Krawędzie', grid:'Podłoga', fs:'Pełny ekran', reset:'Wyśrodkuj', shot:'Zrzut PNG', bg:'Tło', mat:'Materiał', color:'Kolor wydruku', time:'Czas druku', fil:'Filament', print:'Wydrukuj u nas', est:'SZACUNEK', hint:'Ustaw kolor i materiał — druk pod drzwiami w Gdańsku' },
  en: { rotate:'Auto-rotate', wire:'Wireframe', edges:'Edges', grid:'Floor', fs:'Fullscreen', reset:'Reset view', shot:'PNG shot', bg:'Background', mat:'Material', color:'Print color', time:'Print time', fil:'Filament', print:'Print with us', est:'ESTIMATE', hint:'Pick color and material — print pickup in Gdansk' }
};

export const FILAMENT_COLORS = [
  { id:'black',        pl:'czarny',       hex:'#1b1b1b', premium:0 },
  { id:'white',        pl:'biały',        hex:'#f2f2f2', premium:0 },
  { id:'gray',         pl:'szary',        hex:'#9ca3af', premium:0 },
  { id:'red',          pl:'czerwony',     hex:'#dc2626', premium:0 },
  { id:'orange',       pl:'pomarańczowy', hex:'#f97316', premium:0 },
  { id:'yellow',       pl:'żółty',        hex:'#facc15', premium:0 },
  { id:'green',        pl:'zielony',      hex:'#16a34a', premium:0 },
  { id:'blue',         pl:'niebieski',    hex:'#2563eb', premium:0 },
  { id:'purple',       pl:'fioletowy',    hex:'#7c3aed', premium:0 },
  { id:'pink',         pl:'różowy',       hex:'#ec4899', premium:0 },
  { id:'natural',      pl:'naturalny',    hex:'#e8e2d0', premium:0 },
  { id:'wood',         pl:'drewno',       hex:'#8b5e34', premium:15 },
  { id:'silver',       pl:'srebrny',      hex:'#cfd6de', premium:20 },
  { id:'gold',         pl:'złoty',        hex:'#d4af37', premium:25 },
  { id:'brass',        pl:'mosiądz',      hex:'#c9a227', premium:25 },
  { id:'transparent',  pl:'przezroczysty',hex:'#dbeafe', premium:30 }
];

const BGS = [
  { id:'light', hex:'#f0f2f5', label:'Jasne' },
  { id:'white', hex:'#ffffff', label:'Białe' },
  { id:'warm',  hex:'#f7f5f0', label:'Ciepłe' },
  { id:'mid',   hex:'#cfd6de', label:'Szare' },
  { id:'dark',  hex:'#1e293b', label:'Ciemne' },
  { id:'black', hex:'#0b1120', label:'Czarne' }
];

function el(tag, css, html) {
  const d = document.createElement(tag);
  if (css) d.style.cssText = css;
  if (html != null) d.innerHTML = html;
  return d;
}

function fmtHours(h) {
  if (!h || h <= 0) return '—';
  const hh = Math.floor(h), mm = Math.round((h - hh) * 60);
  if (hh <= 0) return mm + ' min';
  return hh + ' h ' + (mm ? mm + ' min' : '').trim();
}
function fmtGrams(g) {
  if (!g || g <= 0) return '—';
  return (g < 10 ? g.toFixed(1) : Math.round(g)) + ' g';
}
export { fmtHours, fmtGrams };
export function initViewerPro(opts) {
  const cfg = Object.assign({
    container: null, stlUrl: '', fallbackImg: '', uuid: '', token: '',
    lang: 'pl', printInfo: null, defaultMaterial: 'PLA', defaultColor: 'szary',
    bg: '#f0f2f5', meshHex: '#9ca3af', toolbar: true, printBar: true,
    printBarTarget: null, compact: false, noEdges: false
  }, opts || {});
  const L = T[cfg.lang] || T.pl;
  const isPL = (cfg.lang || 'pl') === 'pl';
  const host = typeof cfg.container === 'string' ? document.getElementById(cfg.container) : cfg.container;
  if (!host) return null;

  const w0 = Math.min(host.clientWidth || 640, 1600);
  const h0 = host.clientHeight || 420;
  if (getComputedStyle(host).position === 'static') host.style.position = 'relative';

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(cfg.bg);
  const camera = new THREE.PerspectiveCamera(50, w0 / h0, 0.1, 5000);
  camera.position.set(28, 34, 44);

  const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
  renderer.setSize(w0, h0);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.domElement.style.cssText = 'display:block;width:100%;height:100%;touch-action:none';
  host.appendChild(renderer.domElement);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.enableRotate = true;
  controls.enablePan = true;
  controls.enableZoom = true;
  controls.minDistance = 4;
  controls.maxDistance = 600;
  controls.minPolarAngle = 0.05;
  controls.maxPolarAngle = Math.PI - 0.05;
  controls.autoRotateSpeed = 2.2;

  // neutral, non-tinted lighting (was blue-tinted before — made gray models look blue)
  scene.add(new THREE.HemisphereLight(0xffffff, 0xd7dde6, 1.05));
  const key = new THREE.DirectionalLight(0xffffff, 1.35); key.position.set(34, 52, 30); scene.add(key);
  const fill = new THREE.DirectionalLight(0xffffff, 0.45); fill.position.set(-28, 14, -34); scene.add(fill);
  const rim = new THREE.DirectionalLight(0xffffff, 0.35); rim.position.set(0, -30, 22); scene.add(rim);

  const group = new THREE.Group();
  scene.add(group);
  let mesh = null, edgeLines = null, grid = null, halfH = 15;
  let mat = new THREE.MeshStandardMaterial({
    color: new THREE.Color(cfg.meshHex), metalness: 0.12, roughness: 0.62, flatShading: true
  });

  function frameGeometry(geo) {
    geo.computeBoundingBox();
    const c = new THREE.Vector3(); geo.boundingBox.getCenter(c);
    geo.translate(-c.x, -c.y, -c.z);
    const s = new THREE.Vector3(); geo.boundingBox.getSize(s);
    const mx = Math.max(s.x, s.y, s.z) || 1;
    const k = 30 / mx;
    geo.scale(k, k, k);
    geo.computeVertexNormals();
    geo.computeBoundingBox();
    const s2 = new THREE.Vector3(); geo.boundingBox.getSize(s2);
    halfH = (s2.y / 2) || 15;
    return geo;
  }

  function setMesh(geo, keepView) {
    if (!geo) return;
    frameGeometry(geo);
    if (mesh) { group.remove(mesh); mesh.geometry.dispose(); }
    mesh = new THREE.Mesh(geo, mat);
    mesh.rotation.x = -Math.PI / 2;
    group.add(mesh);
    if (edgeLines) { group.remove(edgeLines); edgeLines.geometry.dispose(); edgeLines = null; }
    if (!cfg.noEdges) {
      const eg = new THREE.EdgesGeometry(geo, 25);
      edgeLines = new THREE.LineSegments(eg, new THREE.LineBasicMaterial({
        color: 0x475569, transparent: true, opacity: 0.32, depthWrite: false
      }));
      edgeLines.rotation.x = -Math.PI / 2;
      group.add(edgeLines);
    }
    if (!keepView) resetView();
    else { layoutGrid(); }
  }

  function resetView() {
    const fd = 18 / Math.tan(camera.fov * Math.PI / 360) * 1.25;
    camera.position.set(fd * 0.42, fd * 0.46, fd * 0.66);
    controls.target.set(0, 0, 0);
    controls.update();
    layoutGrid();
  }

  function layoutGrid() {
    if (!grid) return;
    grid.position.set(0, -halfH - 1.5, 0);
  }

  // ---------- toolbar ----------
  let toolbar = null;
  function tbBtn(label, title, on, active) {
    const b = el('button', 'border:1px solid ' + (active ? '#2B5CE6' : '#e2e8f0') + ';background:' +
      (active ? '#eaf0ff' : 'rgba(255,255,255,.94)') + ';color:' + (active ? '#1d4ed8' : '#475569') +
      ';border-radius:9px;width:36px;height:36px;font-size:15px;line-height:1;cursor:pointer;display:flex;' +
      'align-items:center;justify-content:center;backdrop-filter:blur(6px);box-shadow:0 1px 4px rgba(15,23,42,.08)', label);
    b.title = title;
    b.onclick = function () { on(b); };
    return b;
  }
  function buildToolbar() {
    if (!cfg.toolbar) return;
    toolbar = el('div', 'position:absolute;left:10px;top:10px;z-index:12;display:flex;flex-direction:column;gap:6px');
    const state = { rot: false, wire: false, edges: !cfg.noEdges, grid: false };
    toolbar.appendChild(tbBtn('⟳', L.rotate, b => {
      state.rot = !state.rot; controls.autoRotate = state.rot;
      b.style.background = state.rot ? '#eaf0ff' : 'rgba(255,255,255,.94)';
      b.style.borderColor = state.rot ? '#2B5CE6' : '#e2e8f0';
      b.style.color = state.rot ? '#1d4ed8' : '#475569';
    }));
    toolbar.appendChild(tbBtn('▦', L.wire, b => {
      state.wire = !state.wire; mat.wireframe = state.wire;
      b.style.background = state.wire ? '#eaf0ff' : 'rgba(255,255,255,.94)';
      b.style.borderColor = state.wire ? '#2B5CE6' : '#e2e8f0';
      b.style.color = state.wire ? '#1d4ed8' : '#475569';
    }));
    if (!cfg.noEdges) toolbar.appendChild(tbBtn('⬡', L.edges, b => {
      state.edges = !state.edges;
      if (edgeLines) edgeLines.visible = state.edges;
      b.style.background = state.edges ? '#eaf0ff' : 'rgba(255,255,255,.94)';
      b.style.borderColor = state.edges ? '#2B5CE6' : '#e2e8f0';
      b.style.color = state.edges ? '#1d4ed8' : '#475569';
    }));
    toolbar.appendChild(tbBtn('▤', L.grid, b => {
      state.grid = !state.grid;
      if (state.grid) {
        if (!grid) {
          grid = new THREE.GridHelper(90, 36, 0x94a3b8, 0xcbd5e1);
          const gm = Array.isArray(grid.material) ? grid.material : [grid.material];
          gm.forEach(m => { m.transparent = true; m.opacity = 0.5; });
          scene.add(grid);
        }
        grid.visible = true; layoutGrid();
      } else if (grid) grid.visible = false;
      b.style.background = state.grid ? '#eaf0ff' : 'rgba(255,255,255,.94)';
      b.style.borderColor = state.grid ? '#2B5CE6' : '#e2e8f0';
      b.style.color = state.grid ? '#1d4ed8' : '#475569';
    }));
    toolbar.appendChild(tbBtn('◱', L.reset, () => resetView()));
    toolbar.appendChild(tbBtn('⤓', L.shot, () => {
      try {
        renderer.render(scene, camera);
        const a = document.createElement('a');
        a.href = renderer.domElement.toDataURL('image/png');
        a.download = (cfg.filename || 'model') + '.png';
        a.click();
      } catch (e) {}
    }));
    toolbar.appendChild(tbBtn('⛶', L.fs, () => {
      if (!document.fullscreenElement) (host.requestFullscreen || host.webkitRequestFullscreen || function(){}).call(host).catch(function(){});
      else document.exitFullscreen();
    }));
    host.appendChild(toolbar);

    // background swatches (small row under toolbar)
    const bgBar = el('div', 'position:absolute;left:10px;bottom:10px;z-index:12;display:flex;gap:5px;padding:6px 8px;' +
      'background:rgba(255,255,255,.9);border:1px solid #e2e8f0;border-radius:10px;backdrop-filter:blur(6px)');
    BGS.forEach(bgc => {
      const d = el('button', 'width:20px;height:20px;border-radius:6px;border:1px solid #cbd5e1;cursor:pointer;background:' + bgc.hex);
      d.title = L.bg + ': ' + bgc.label;
      d.onclick = () => { scene.background = new THREE.Color(bgc.hex); };
      bgBar.appendChild(d);
    });
    host.appendChild(bgBar);
  }
  buildToolbar();

  // ---------- print color / material bar ----------
  const pi = cfg.printInfo || null;
  const mats = (pi && pi.materials) ? Object.keys(pi.materials) : [];
  const st = { material: cfg.defaultMaterial && mats.indexOf(cfg.defaultMaterial) >= 0 ? cfg.defaultMaterial : (mats[0] || cfg.defaultMaterial), color: cfg.defaultColor || 'gray' };
  let barEl = null, timeOut = null, filOut = null, ctaEl = null;

  function colorById(id) {
    for (let i = 0; i < FILAMENT_COLORS.length; i++) if (FILAMENT_COLORS[i].id === id) return FILAMENT_COLORS[i];
    return FILAMENT_COLORS[2];
  }
  function refreshBar() {
    if (pi && pi.materials && pi.materials[st.material]) {
      const m = pi.materials[st.material];
      if (timeOut) timeOut.textContent = fmtHours(m.h);
      if (filOut) filOut.textContent = fmtGrams(m.g);
    }
    const c = colorById(st.color);
    mat.color.set(c.hex);
    if (ctaEl) ctaEl.href = '/zamow?job=' + encodeURIComponent(cfg.uuid) + '&material=' + encodeURIComponent(st.material) + '&color=' + encodeURIComponent(c.pl);
  }
  function chip(txt, active, on) {
    const b = el('button', 'font:600 12px/1 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.02em;padding:7px 11px;' +
      'border-radius:8px;cursor:pointer;white-space:nowrap;border:1px solid ' + (active ? '#2B5CE6' : '#e2e8f0') + ';' +
      'background:' + (active ? '#2B5CE6' : '#fff') + ';color:' + (active ? '#fff' : '#334155'), txt);
    b.onclick = function () { on(b); };
    return b;
  }
  function swatch(c) {
    const b = el('button', 'width:26px;height:26px;border-radius:8px;cursor:pointer;background:' + c.hex +
      ';border:2px solid ' + (st.color === c.id ? '#2B5CE6' : '#e2e8f0') + ';flex:0 0 auto');
    b.title = c.pl + (c.premium ? (' (+' + c.premium + ' zł)') : '');
    b.setAttribute('data-col', c.id);
    b.onclick = function () {
      st.color = c.id;
      const all = barEl ? barEl.querySelectorAll('[data-col]') : [];
      for (let i = 0; i < all.length; i++) all[i].style.border = '2px solid #e2e8f0';
      b.style.border = '2px solid #2B5CE6';
      refreshBar();
    };
    return b;
  }
  function buildBar() {
    if (!cfg.printBar) return;
    const target = cfg.printBarTarget ? (typeof cfg.printBarTarget === 'string' ? document.getElementById(cfg.printBarTarget) : cfg.printBarTarget) : null;
    barEl = el('div', 'display:flex;flex-wrap:wrap;align-items:center;gap:14px;padding:12px 16px;background:#fff;' +
      'border:1px solid #e2e8f0;border-radius:12px;margin-top:10px;min-width:0');
    const monoK = 'font:600 10px/1 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.14em;text-transform:uppercase;color:#64748b';
    if (mats.length) {
      const mWrap = el('div', 'display:flex;flex-direction:column;gap:6px;min-width:0');
      mWrap.appendChild(el('span', monoK, L.mat));
      const row = el('div', 'display:flex;gap:5px;flex-wrap:wrap');
      mats.forEach(m => {
        row.appendChild(chip(m, m === st.material, function (b) {
          st.material = m;
          const all = row.querySelectorAll('button');
          for (let i = 0; i < all.length; i++) {
            all[i].style.background = '#fff'; all[i].style.color = '#334155'; all[i].style.borderColor = '#e2e8f0';
          }
          b.style.background = '#2B5CE6'; b.style.color = '#fff'; b.style.borderColor = '#2B5CE6';
          refreshBar();
        }));
      });
      mWrap.appendChild(row);
      barEl.appendChild(mWrap);
    }
    const cWrap = el('div', 'display:flex;flex-direction:column;gap:6px;min-width:0');
    cWrap.appendChild(el('span', monoK, L.color));
    const cRow = el('div', 'display:flex;gap:5px;flex-wrap:wrap;max-width:100%');
    FILAMENT_COLORS.forEach(c => cRow.appendChild(swatch(c)));
    cWrap.appendChild(cRow);
    barEl.appendChild(cWrap);

    if (pi) {
      const est = el('div', 'display:flex;gap:16px;margin-left:auto;align-items:center');
      est.appendChild(el('span', monoK, L.est));
      const tBox = el('div', 'line-height:1.25');
      tBox.appendChild(el('div', 'font:600 10px/1 ui-monospace,monospace;color:#94a3b8;letter-spacing:.1em;text-transform:uppercase', L.time));
      timeOut = el('div', 'font:700 15px/1.3 ui-monospace,monospace;color:#0f172a', '—');
      tBox.appendChild(timeOut);
      est.appendChild(tBox);
      const fBox = el('div', 'line-height:1.25');
      fBox.appendChild(el('div', 'font:600 10px/1 ui-monospace,monospace;color:#94a3b8;letter-spacing:.1em;text-transform:uppercase', L.fil));
      filOut = el('div', 'font:700 15px/1.3 ui-monospace,monospace;color:#0f172a', '—');
      fBox.appendChild(filOut);
      est.appendChild(fBox);
      barEl.appendChild(est);
    }
    ctaEl = el('a', 'display:inline-flex;align-items:center;gap:8px;padding:11px 18px;border-radius:10px;background:#2B5CE6;' +
      'color:#fff;font-size:14px;font-weight:600;text-decoration:none;white-space:nowrap', L.print + ' →');
    ctaEl.href = '/zamow?job=' + encodeURIComponent(cfg.uuid);
    barEl.appendChild(ctaEl);

    if (target) target.appendChild(barEl);
    else host.parentNode.insertBefore(barEl, host.nextSibling);
    refreshBar();
  }

  // ---------- loading + loop ----------
  const loader = new STLLoader();
  function showFallback() {
    if (!cfg.fallbackImg) {
      host.appendChild(el('div', 'position:absolute;inset:0;display:flex;flex-direction:column;gap:8px;align-items:center;' +
        'justify-content:center;color:#64748b;font-size:14px', '<span style="font-size:30px">△</span>' +
        (isPL ? 'Podgląd 3D niedostępny' : '3D preview unavailable')));
      return;
    }
    const img = new Image();
    img.onload = function () { host.appendChild(img); img.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;object-fit:contain;background:#fff'; };
    img.src = cfg.fallbackImg;
  }
  let loaded = false;
  if (cfg.stlUrl) {
    loader.load(cfg.stlUrl, function (geo) {
      try { setMesh(geo); loaded = true; } catch (e) { showFallback(); }
    }, undefined, function () { showFallback(); });
  }
  window.addEventListener('resize', function () {
    const w = Math.min(host.clientWidth || 640, 1600), h = host.clientHeight || 420;
    if (!w || !h) return;
    camera.aspect = w / h; camera.updateProjectionMatrix();
    renderer.setSize(w, h);
  });
  document.addEventListener('fullscreenchange', function () {
    setTimeout(function () {
      const w = host.clientWidth || 640, h = host.clientHeight || 420;
      camera.aspect = w / h; camera.updateProjectionMatrix(); renderer.setSize(w, h);
    }, 80);
  });
  (function loop() { requestAnimationFrame(loop); controls.update(); renderer.render(scene, camera); })();
  buildBar();

  const api = {
    three: THREE, scene, camera, renderer, controls, group,
    setMesh: function (geo, keepView) { setMesh(geo, keepView); loaded = true; },
    /* replacement mesh from an external loader (e.g. STEP via OCCT WASM) */
    attachMesh: function (geo) { setMesh(geo); loaded = true; if (barEl) refreshBar(); },
    setBg: function (hex) { scene.background = new THREE.Color(hex); },
    refreshBar: refreshBar,
    setColor: function (hex) { mat.color.set(hex); },
    resetView: resetView,
    isLoaded: function () { return loaded; },
    state: st
  };
  window.__viewerPro = api;
  return api;
}
