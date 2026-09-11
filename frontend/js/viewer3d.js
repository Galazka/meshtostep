// viewer3d.js — Three.js viewer, toast, setMeshColor, loadSTLIntoViewer (verbatim).
import { token } from './shared.js';

function setMeshColor(hex) {
    if (!_threeScene) return;
    _threeScene.traverse(function(c) {
        if (c.isMesh) { c.material.color.setHex(hex); c.material.needsUpdate = true; }
    });
}

let _threeScene, _threeCamera, _threeRenderer, _threeControls, _threeAnim;
let _threeToastTimer;
function toast(msg, type){
    let el=document.getElementById('toast');
    if(!el){ el=document.createElement('div'); el.id='toast'; el.className='toast'; document.body.appendChild(el); }
    el.textContent=msg;
    el.className='toast show '+(type||'');
    clearTimeout(_threeToastTimer);
    _threeToastTimer=setTimeout(function(){ el.classList.remove('show'); }, 3000);
}
function _waitThreeReady(cb){
    console.log('[3D] _waitThreeReady: __threeReady=', window.__threeReady, 'THREE=', !!window.THREE, 'STLLoader=', !!window._STLLoader);
    if(window.__threeReady && window.THREE && window._STLLoader){ console.log('[3D] _waitThreeReady: already ready'); cb(); return; }
    let done=false;
    function go(){ if(done) return; done=true; cb(); }
    window.addEventListener('three-ready', go, {once:true});
    let tries=0;
    const iv=setInterval(function(){
        tries++;
        console.log('[3D] _waitThreeReady poll', tries, '__threeReady=', window.__threeReady);
        if(window.__threeReady && window.THREE && window._STLLoader){ clearInterval(iv); console.log('[3D] _waitThreeReady: ready after poll'); go(); }
        else if(tries>40){ clearInterval(iv); console.log('[3D] _waitThreeReady: timeout'); if(!done) toast('B\u0142\u0105d \u0142adowania podgl\u0105du 3D', 'error'); }
    }, 150);
}
function _fitCameraToObject(obj){
    try{
        const box=new THREE.Box3().setFromObject(obj);
        const size=new THREE.Vector3(); box.getSize(size);
        const center=new THREE.Vector3(); box.getCenter(center);
        const maxDim=Math.max(size.x, size.y, size.z) || 1;
        const fov=_threeCamera.fov * Math.PI/180;
        let dist=(maxDim/2) / Math.tan(fov/2);
        dist*=1.6;
        const dir=new THREE.Vector3(0.6,0.8,1).normalize();
        _threeCamera.position.copy(center).add(dir.multiplyScalar(dist));
        _threeCamera.near=dist/100; _threeCamera.far=dist*100; _threeCamera.updateProjectionMatrix();
        _threeControls.target.copy(center);
        _threeControls.update();
    }catch(e){}
}
function _capturePreview(jobUuid){
    if(!jobUuid || !_threeRenderer) return;
    setTimeout(function(){
        try{
            const canvas=_threeRenderer.domElement;
            if(!canvas) return;
            const dataUrl=canvas.toDataURL('image/jpeg', 0.85);
            if(!dataUrl || dataUrl.length < 1000) return;
            // dataURL -> blob via fetch
            fetch(dataUrl).then(function(r){ return r.blob(); }).then(function(blob){
                const fd=new FormData();
                fd.append('preview', blob, 'preview.jpg');
                const headers=token ? {'Authorization':'Bearer '+token} : {};
                fetch('/api/jobs/'+jobUuid+'/preview', {method:'POST', body:fd, headers: headers}).catch(function(){});
            }).catch(function(){});
        }catch(e){}
    }, 1500);
}
function init3DViewer(container) {
    if (_threeRenderer) {
        cancelAnimationFrame(_threeAnim);
        _threeRenderer.dispose();
        _threeControls && _threeControls.dispose();
    }
    container.querySelectorAll('canvas').forEach(function(c){ c.remove(); });
    const W = container.clientWidth || 640, H = container.clientHeight || 420;
    _threeScene = new THREE.Scene();
    _threeScene.background = new THREE.Color(0xf0f2f5);
    _threeCamera = new THREE.PerspectiveCamera(50, W / H, 0.1, 1000);
    _threeCamera.position.set(0, 40, 60);
    _threeRenderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    _threeRenderer.setSize(W, H);
    _threeRenderer.setPixelRatio(window.devicePixelRatio);
    container.appendChild(_threeRenderer.domElement);
    // Force resize after DOM layout settles
    setTimeout(function(){ _threeRenderer.setSize(W, H); }, 100);
    _threeControls = new window._OrbitControls(_threeCamera, _threeRenderer.domElement);
    _threeControls.enableDamping = true;
    _threeScene.add(new THREE.AmbientLight(0xffffff, 0.8));
    const d1 = new THREE.DirectionalLight(0xffffff, 0.8); d1.position.set(30,50,30); _threeScene.add(d1);
    const d2 = new THREE.DirectionalLight(0x1a56db, 0.3); d2.position.set(-20,10,-30); _threeScene.add(d2);
    function animate() { _threeAnim = requestAnimationFrame(animate); _threeControls.update(); _threeRenderer.render(_threeScene, _threeCamera); }
    animate();
}

function loadSTLIntoViewer(url, jobUuid) {
    if(!jobUuid){
        try{ const m=url.match(/([a-f0-9]{8,32})/i); if(m) jobUuid=m[1]; }catch(e){}
    }
    _waitThreeReady(function(){
        const container = document.getElementById('viewer3d');
        if(!container){ toast('Brak kontenera podgl\u0105du', 'error'); return; }
        container.classList.add('show');
        container.querySelectorAll('canvas').forEach(function(c){ c.remove(); });
        var oldLd = document.getElementById('viewer3d-loading');
        if (oldLd) oldLd.remove();
        var ld = document.createElement('div');
        ld.id = 'viewer3d-loading';
        ld.style.cssText = 'display:flex;align-items:center;justify-content:center;height:100%;min-height:280px;color:var(--text-secondary);font-size:14px;position:absolute;inset:0';
        ld.textContent = '\u0141adowanie modelu 3D...';
        container.appendChild(ld);
        var mcb=document.getElementById('meshColorBar');if(mcb)mcb.style.display='flex';
        init3DViewer(container);
        const ext = url.split('.').pop().toLowerCase().split('?')[0];
        const mat = new THREE.MeshPhongMaterial({ color: 0x1a56db, specular: 0x93b8ea, shininess: 40 });

        function addMesh(obj) {
            var ldd = document.getElementById('viewer3d-loading');
            if (ldd) ldd.remove();
            obj.traverse(function(c) { if (c.isMesh) c.material = mat; });
            obj.rotation.x = -Math.PI / 2;
            _threeScene.add(obj);
            _fitCameraToObject(obj);
            _capturePreview(jobUuid);
        }
        function showJpgFallback(){
            var ldd = document.getElementById('viewer3d-loading');
            if (ldd) ldd.remove();
            if(!jobUuid) return;
            var img=new Image();
            img.onload=function(){ container.innerHTML=''; img.style.cssText='width:100%;height:100%;object-fit:contain;border-radius:12px'; container.appendChild(img); };
            img.onerror=function(){ container.innerHTML='<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-muted)">Podglad 3D niedostepny</div>'; };
            img.src='/api/preview/'+jobUuid;
        }
        function onErr(e){
            console.error('loadSTLIntoViewer error', e);
            showJpgFallback();
        }

        if (ext === 'obj') {
            const loader = new window._OBJLoader();
            loader.load(url, addMesh, undefined, onErr);
        } else if (ext === '3mf') {
            const loader = new window._3MFLoader();
            loader.load(url, addMesh, undefined, onErr);
        } else {
            // Sanity check: HEAD request to reject HTML error pages / corrupt files
            fetch(url, {method:'HEAD'}).then(function(h){
                var len = parseInt(h.headers.get('content-length')||'0', 10);
                var ct = (h.headers.get('content-type')||'').toLowerCase();
                if ((ct.indexOf('text/html')>=0) || (len > 500*1024*1024)) { onErr(new Error('bad file')); return; }
                loadStlNow();
            }).catch(loadStlNow);
            function loadStlNow(){
                const loader = new window._STLLoader();
                loader.load(url, function(geometry) {
                    try{
                        geometry.computeBoundingBox();
                        const bb = geometry.boundingBox, center = new THREE.Vector3();
                        bb.getCenter(center); geometry.translate(-center.x, -center.y, -center.z);
                        const mesh=new THREE.Mesh(geometry, mat);
                        addMesh(mesh);
                    }catch(e){ onErr(e); }
                }, undefined, onErr);
            }
        }
    });
}

export function refreshThreeTheme() {
    if (!_threeScene) return;
    try {
        const dark = document.documentElement.getAttribute('data-theme') === 'dark';
        _threeScene.background = new window.THREE.Color(dark ? 0x111827 : 0xf0f2f5);
    } catch (e) {}
}

export { toast, init3DViewer, loadSTLIntoViewer, setMeshColor };
window.setMeshColor = setMeshColor;
window.loadSTLIntoViewer = loadSTLIntoViewer;
window.toast = toast;
