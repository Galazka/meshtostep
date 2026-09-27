// viewer3d.js — glowny podglad na indexie = PELNY konfigurator viewer_pro
// (auto-obrot, siatka, krawedzie, podloga, tlo, pelny ekran, zrzut PNG +
// pasek kolorow/wydruku). Kiedys osobny, ubogi stack — teraz jeden shared
// viewer uzywany wszedzie: /s/, /u/, /e/, index, Moje pliki, admin, /zamow.
import { token } from './shared.js?v=111';
import { initViewerPro } from '../asset/viewer_pro.js?v=6';

let _pro = null;
let _toastT;

function toast(msg, type){
    let el=document.getElementById('toast');
    if(!el){ el=document.createElement('div'); el.id='toast'; el.className='toast'; document.body.appendChild(el); }
    el.textContent=msg;
    el.className='toast show '+(type||'');
    clearTimeout(_toastT);
    _toastT=setTimeout(function(){ el.classList.remove('show'); }, 3000);
}

function _ensurePro() {
    const container = document.getElementById('viewer3d');
    if (!container) return null;
    if (container.__pro) { _pro = container.__pro; return _pro; }
    container.querySelectorAll('canvas').forEach(function(c){ c.remove(); });
    const pro = initViewerPro({
        container: container,
        stlUrl: '',
        lang: document.documentElement.lang || 'pl',
        toolbar: true,
        printBar: true,
        grid: true,
        authToken: token || ''
    });
    container.__pro = pro;
    _pro = pro;
    window.__viewerPro = pro;
    return pro;
}

// JPG karty (preview_image) — strzal z zywego canvasa, jak kiedys.
function _capturePreview(jobUuid, pro){
    if(!jobUuid || !pro || !pro.renderer) return;
    setTimeout(function(){
        try{
            const canvas=pro.renderer.domElement;
            if(!canvas) return;
            const dataUrl=canvas.toDataURL('image/jpeg', 0.85);
            if(!dataUrl || dataUrl.length < 1000) return;
            // fetch(dataURL) jest w Chrome odrzucany — kodujemy recznie do Bloba
            const bin=atob(dataUrl.split(',')[1]);
            const arr=new Uint8Array(bin.length);
            for(let i=0;i<bin.length;i++) arr[i]=bin.charCodeAt(i);
            const fd=new FormData();
            fd.append('preview', new Blob([arr],{type:'image/jpeg'}), 'preview.jpg');
            const headers=token ? {'Authorization':'Bearer '+token} : {};
            fetch('/api/jobs/'+jobUuid+'/preview', {method:'POST', body:fd, headers: headers}).catch(function(){});
        }catch(e){}
    }, 1800);
}

function loadSTLIntoViewer(url, jobUuid) {
    if (!jobUuid) {
        try { const m = url.match(/([a-f0-9]{8,32})/i); if (m) jobUuid = m[1]; } catch (e) {}
    }
    const container = document.getElementById('viewer3d');
    if (!container) { toast('Brak kontenera podglądu', 'error'); return; }
    container.classList.add('show');
    const pro = _ensurePro();
    if (!pro) return;
    const fb = jobUuid ? '/api/thumb/' + jobUuid + '?v=8' : '';
    pro.loadUrl(url, { fallback: fb });
    _capturePreview(jobUuid, pro);
}

// compat: reszta kodu mogla wyolywac init3DViewer(container)
function init3DViewer(container) { _ensurePro(); }

export function refreshThreeTheme() {
    // viewer_pro ma swoj staly, ciemny "stage" — w dark mode lekkie przyciemnienie
    try {
        const dark = document.documentElement.getAttribute('data-theme') === 'dark';
        if (_pro) _pro.setBg(dark ? '#0b1220' : '#101a2e');
    } catch (e) {}
}

export function setMeshColor(hex) { if (_pro) _pro.setColor(hex); }
export { toast, init3DViewer, loadSTLIntoViewer };
window.setMeshColor = setMeshColor;
window.loadSTLIntoViewer = loadSTLIntoViewer;
window.toast = toast;
