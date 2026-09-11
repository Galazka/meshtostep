// convert.js — dropzone, pickFile, doConvert, quickUpload (verbatim).
import { t } from './i18n.js';
import { token } from './shared.js';
import { toast, loadSTLIntoViewer } from './viewer3d.js';

let selectedFile = null;

function setupDropZone() {
    const d = document.getElementById('dropZone');
    const inp = document.getElementById('fileInput');
    d.addEventListener('click', () => inp.click());
    d.addEventListener('dragover', e => { e.preventDefault(); d.classList.add('drag-over'); });
    d.addEventListener('dragleave', () => d.classList.remove('drag-over'));
    d.addEventListener('drop', e => { e.preventDefault(); d.classList.remove('drag-over'); pickFile(e.dataTransfer.files[0]); });
    inp.addEventListener('change', () => pickFile(inp.files[0]));
}

function pickFile(f) {
    if (!f) return;
    selectedFile = f;
    document.getElementById('fileName').textContent = f.name;
    document.getElementById('fileSize').textContent = (f.size/1024/1024).toFixed(2) + ' MB';
    document.getElementById('fileInfo').classList.add('show');
    document.getElementById('convertBtn').classList.add('show');
    const res = document.getElementById('result');
    if (res) { res.classList.remove('show'); res.style.display = ''; }
    const vw = document.getElementById('viewer3d');
    if (vw) { vw.classList.remove('show'); vw.style.display = ''; }
    // Auto-start upload
    setTimeout(() => { doConvert(); }, 100);
}

async function doConvert() {
    if (!selectedFile) return;
    const btn = document.getElementById('convertBtn');
    btn.disabled = true; btn.textContent = t('progressUploading');
    document.getElementById('progress').classList.add('show');
    let pct = 0;
    const iv = setInterval(() => {
        pct = Math.min(pct + 3 + Math.random()*4, 92);
        document.getElementById('progressFill').style.width = pct + '%';
        document.getElementById('progressText').textContent = pct < 50 ? t('progressUploading') : 'Zapisywanie...';
    }, 200);
    const fd = new FormData();
    fd.append('file', selectedFile);
    fd.append('mode', 'hosting');
    try {
        const r = await fetch('/api/convert', {
            method: 'POST', body: fd,
            headers: token ? {'Authorization': 'Bearer ' + token} : {}
        });
        clearInterval(iv);
        document.getElementById('progressFill').style.width = '100%';
        if (!r.ok) { const e = await r.json(); throw new Error(e.detail || 'Error'); }
        const d = await r.json();
        const fileSz = (selectedFile.size/1024/1024).toFixed(2);
        document.getElementById('result').className = 'result show';
        document.getElementById('result').innerHTML =
            '<div class="result-card">' +
            '<div class="result-stats">' +
            (d.faces ? '<div class="result-stat">' + t('faceCount') + ': <b>' + d.faces + '</b></div>' : '') +
            (d.dims_mm ? '<div class="result-stat">⬛ ' + d.dims_mm + '</div>' : '') +
            '<div class="result-stat">Plik: <b>' + fileSz + ' MB</b></div>' +
            '<div class="result-stat">' + t('thTime') + ': <b>' + d.time_s + 's</b></div>' +
            '</div>' +
            '<div class="result-actions">' +
            '<a class="btn-dl" href="/api/download/' + d.uuid + '?format=stl">' + t('downloadText') + ' oryginał</a>' +
            '<button class="btn-step" onclick="doConvertOnDemand(\'' + d.uuid + '\', ' + d.job_id + ')">Pobierz STEP</button>' +
            '<button class="btn-share" onclick="doShare(' + d.job_id + ')">' + t('shareText') + '</button>' +
            '</div></div>';
        document.getElementById('result').style.display = 'block';
        try { loadSTLIntoViewer('/api/stl-preview/' + d.uuid, d.uuid); } catch(e) { console.error('[3D] loadSTLIntoViewer threw:', e); }
    } catch(e) {
        clearInterval(iv);
        document.getElementById('result').className = 'result show';
        document.getElementById('result').innerHTML = '<div class="result-card error">' + t('resultError', {msg: e.message}) + '</div>';
        document.getElementById('result').style.display = 'block';
    }
    btn.disabled = false; btn.textContent = t('convertBtn');
    document.getElementById('progress').classList.remove('show');
}

function quickUpload(){
    const input=document.createElement('input');
    input.type='file';input.accept='.stl,.3mf,.obj';
    input.onchange=function(){
        if(!input.files.length) return;
        window.go('home');
        const dz=document.getElementById('dropZone');
        if(dz){const dt=new DataTransfer();dt.items.add(input.files[0]);dz.files=dt.files;dz.dispatchEvent(new Event('drop',{bubbles:true,dataTransfer:dt}));}
        document.getElementById('fileInput').files=input.files;
        document.getElementById('convertBtn').style.display='inline-block';
        toast('Plik gotowy: ' + input.files[0].name);
    };
    input.click();
}

export { setupDropZone, pickFile };
window.doConvert = doConvert;
window.quickUpload = quickUpload;
window.pickFile = pickFile;
