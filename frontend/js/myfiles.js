// myfiles.js  -  jobs grid, folders, bulk, share modal, job modal, fullscreen, editor (verbatim).
import { t } from './i18n.js';
import { token } from './shared.js';
import { toast } from './viewer3d.js';

let _shareJobId = null;
let _shareAnon = false;
let _shareVanityUrl = '';

function doShare(jobId) {
    _shareJobId = jobId;
    document.getElementById('shareUrl').value = '';
    document.getElementById('shareResult').style.display = 'none';
    document.getElementById('shareCreateBtn').style.display = '';
    document.getElementById('shareModal').classList.add('show');
}

function toggleShareAnon(){
    _shareAnon=!_shareAnon;
    const btn=document.getElementById('shareAnonBtn');
    const inp=document.getElementById('shareUrl');
    if(btn) btn.textContent='🔒 Link bez nicka: '+(_shareAnon?'ON':'OFF');
    if(inp && _shareVanityUrl){
        if(_shareAnon){
            var u=_shareVanityUrl;
            var m=u.match(/\/u\/([^/]+)\/([^/]+)$/);
            inp.value=m?'/s/'+m[2]:u;
        } else inp.value=_shareVanityUrl;
    }
}
function closeShareModal() {
    document.getElementById('shareModal').classList.remove('show');
    _shareJobId = null;
}
async function createShareLink() {
    if (!_shareJobId) return;
    const btn = document.getElementById('shareCreateBtn');
    btn.disabled = true; btn.textContent = t('shareCreate') + '...';
    const fd = new FormData();
    fd.append('job_id', _shareJobId);
    fd.append('fmt', 'step');
    fd.append('show_author', document.getElementById('shareShowAuthor').checked);
    fd.append('expires_days', document.getElementById('shareExpiry').value);
    try {
        const r = await fetch('/api/share', {method:'POST', body:fd, headers: token?{'Authorization':'Bearer '+token}:{}});
        if (r.ok) {
            const d = await r.json();
            document.getElementById('shareUrl').value = d.url;
            document.getElementById('shareResult').style.display = 'block';
            btn.style.display = 'none';
        }
    } catch(e) {}
    btn.disabled = false; btn.textContent = t('shareCreate');
}
function copyShareUrl() {
    const el = document.getElementById('shareUrl');
    el.select();
    navigator.clipboard.writeText(el.value);
    toast(t('shareLinkPrompt'), 'success');
}
function doEmbed(jobId) {
    document.getElementById('embedModal').classList.add('show');
    _embedJobId = jobId;
    const ta = document.getElementById('embedCode');
    if (ta) ta.value = '<iframe src="https://3dfile.link/e/' + jobId + '" width="800" height="500" frameborder="0" allowfullscreen></iframe>';
}
let _embedJobId = null;

function copyEmbedCode() {
    const ta = document.getElementById('embedCode');
    if (!ta) return;
    navigator.clipboard.writeText(ta.value).then(() => toast('Kod skopiowany', 'success')).catch(() => { ta.select(); document.execCommand('copy'); toast('Kod skopiowany', 'success'); });
}


let _mfFolders = [];
let _mfSelected = new Set();
async function loadQuota(){
    if(!token) return;
    try{
        const r=await fetch('/api/quota',{headers:{'Authorization':'Bearer '+token}});
        if(!r.ok) return;
        const q=await r.json();
        const bar=document.getElementById('quotaBar');
        bar.style.display='block';
        document.getElementById('quotaLabel').textContent='Wykorzystano '+q.used_mb+' / '+q.limit_mb+' MB';
        document.getElementById('quotaPct').textContent=q.percent+'%';
        const fill=document.getElementById('quotaFill');
        fill.style.width=Math.min(q.percent,100)+'%';
        fill.style.background=q.percent>90?'#dc2626':q.percent>75?'#d97706':'var(--primary)';
    }catch(e){}
}
async function loadAuthorStats(){
    if(!token) return;
    try{
        const r=await fetch('/api/jobs-author-stats',{headers:{'Authorization':'Bearer '+token}});
        if(!r.ok) return;
        const s=await r.json();
        const bar=document.getElementById('authorStats');
        if(bar) bar.style.display='block';
        if(document.getElementById('stModels')) document.getElementById('stModels').textContent=s.total_models||0;
        if(document.getElementById('stPublic')) document.getElementById('stPublic').textContent=s.public_models||0;
        if(document.getElementById('stViews')) document.getElementById('stViews').textContent=s.total_views||0;
        if(document.getElementById('stLikes')) document.getElementById('stLikes').textContent=s.total_likes||0;
    }catch(e){}
}
async function loadFolders(){
    if(!token) return;
    try{
        const r=await fetch('/api/folders',{headers:{'Authorization':'Bearer '+token}});
        if(!r.ok) return;
        _mfFolders=await r.json();
        const sel=document.getElementById('mfFolderFilter');
        const cur=sel?sel.value:'';
        if(sel) sel.innerHTML='<option value="">Wszystkie foldery</option><option value="__none">Bez folderu</option>'+_mfFolders.map(function(f){return '<option value="'+f.id+'">'+String(f.name).replace(/</g,'&lt;')+'</option>'}).join('');
        if(sel&&cur) sel.value=cur;
        renderFolderChips();
    }catch(e){}
}
function mfCountInFolder(fid){
    if(typeof _myJobsData==='undefined'||!_myJobsData) return 0;
    if(fid==='') return _myJobsData.length;
    if(fid==='__none') return _myJobsData.filter(function(j){return j.folder_id==null}).length;
    return _myJobsData.filter(function(j){return String(j.folder_id||'')===String(fid)}).length;
}

// ═══ SHARE EMAIL ═══
let _shareEmailJobId = null;

function showShareEmailModal(jobId) {
    _shareEmailJobId = jobId;
    const modal = document.createElement('div');
    modal.id = 'shareEmailModal';
    modal.style = 'display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.85);z-index:3000;align-items:center;justify-content:center;';
    const content = document.createElement('div');
    content.style = 'background:#fff;padding:32px;border-radius:12px;width:90%;max-width:400px;box-shadow:0 10px 30px rgba(0,0,0,.5);position:relative;max-height:90vh;overflow:auto;';
    const h3 = document.createElement('h3');
    h3.style = 'margin-top:0;color:#1a56db;';
    h3.textContent = 'Wyślij link mailem';
    const p = document.createElement('p');
    p.textContent = 'Wpisz adres email odbiorcy';
    const inp = document.createElement('input');
    inp.type = 'email';
    inp.style = 'width:100%;padding:12px;border:1px solid #e2e8f0;border-radius:8px;margin-bottom:16px;font-size:14px;';
    inp.placeholder = 'example@email.com';
    const buttonsDiv = document.createElement('div');
    buttonsDiv.style = 'display:flex;gap:8px;';
    const btnSend = document.createElement('button');
    btnSend.style = 'flex:1;background:#1a56db;color:#fff;border:none;border-radius:8px;padding:10px;font-weight:600;cursor:pointer;';
    btnSend.textContent = 'Wyślij';
    btnSend.onclick = shareEmailSend;
    const btnCancel = document.createElement('button');
    btnCancel.style = 'flex:1;background:#e2e8f0;border:none;border-radius:8px;padding:10px;font-size:14px;cursor:pointer;';
    btnCancel.textContent = 'Anuluj';
    btnCancel.onclick = () => { modal.classList.remove('show'); };
    buttonsDiv.appendChild(btnSend);
    buttonsDiv.appendChild(btnCancel);
    const resultDiv = document.createElement('div');
    resultDiv.id = 'shareEmailResult';
    resultDiv.style = 'margin-top:16px;font-size:12px;';
    const closeBtn = document.createElement('button');
    closeBtn.style = 'position:absolute;top:8px;right:16px;border:none;background:none;font-size:24px;color:#64748b;cursor:pointer;';
    closeBtn.textContent = '×';
    closeBtn.onclick = () => { modal.classList.remove('show'); };
    content.appendChild(h3);
    content.appendChild(p);
    content.appendChild(inp);
    content.appendChild(buttonsDiv);
    content.appendChild(resultDiv);
    content.appendChild(closeBtn);
    modal.appendChild(content);
    document.body.appendChild(modal);
    modal.classList.add('show');
}

function shareEmailSend() {
    const inp = document.getElementById('shareEmailInput');
    const result = document.getElementById('shareEmailResult');
    if (!inp) { result.textContent = 'Błąd: modal nie znaleziony'; return; }
    const email = inp.value.trim();
    if (!email || !email.includes('@')) { result.textContent = 'Podaj poprawny adres email'; return; }
    result.textContent = 'Wysyłanie...';
    fetch('/api/share/' + _shareEmailJobId + '/email', {
        method: 'POST',
        headers: {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'},
        body: JSON.stringify({ recipient_email: email })
    }).then(r => r.json()).then(d => {
        if (d.ok) { result.textContent = 'Wysłano!'; setTimeout(()=>{ document.getElementById('shareEmailModal').classList.remove('show'); }, 2000); }
        else { result.textContent = d.detail||'Błąd'; }
    }).catch(()=>{ result.textContent = 'Błąd połączenia'; });
}


// ═══ DOWNLOAD DIALOG ═══
let _dlJobId = null;
function showDownloadDialog(jobId, fileName) {
    _dlJobId = jobId;
    const info = document.getElementById('downloadInfo');
    if (info) info.textContent = 'Pobierz: ' + (fileName || jobId);
    const opts = document.getElementById('downloadOptions');
    if (!opts) return;
    opts.innerHTML = '';
    var formats = [
        {fmt:'stl', label:'Mesh  -  STL (uniwersalny)'},
        {fmt:'obj', label:'Mesh  -  OBJ (z teksturami)'},
        {fmt:'3mf', label:'Mesh  -  3MF (druk 3D)'},
        {fmt:'step', label:'Solid  -  STEP (CAD/CAM)'}
    ];
    formats.forEach(function(f) {
        var btn = document.createElement('button');
        btn.className = 'nav-btn nav-btn-primary';
        btn.style.cssText = 'width:100%;padding:12px 16px;text-align:left;font-size:14px';
        btn.textContent = f.label;
        btn.onclick = function() { _downloadFile(_dlJobId, f.fmt); };
        opts.appendChild(btn);
    });
    document.getElementById('downloadModal').classList.add('show');
}

async function _downloadFile(uuid, fmt) {
    document.getElementById('downloadModal').classList.remove('show');
    toast('Pobieranie ' + fmt.toUpperCase() + '...');
    try {
        var url = '/api/download/' + uuid + '?format=' + fmt;
        var headers = {};
        if (token) headers['Authorization'] = 'Bearer ' + token;
        var r = await fetch(url, {headers: headers});
        if (!r.ok) { toast('Błąd: ' + r.statusText); return; }
        var blob = await r.blob();
        var a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'model.' + fmt;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(a.href);
    } catch(e) { toast('Błąd pobierania: ' + e.message); }
}

function mfSelectFolder(fid){
    const sel=document.getElementById('mfFolderFilter');
    if(sel) sel.value=fid;
    renderFolderChips();
    mfRender();
}
function renderFolderChips(){
    const c=document.getElementById('mfFolderChips');
    if(!c) return;
    const cur=(document.getElementById('mfFolderFilter')||{}).value||'';
    function chip(fid,label,count,deletable,rid){
        const act=String(cur)===String(fid);
        const dd=' ondrop="event.preventDefault();var id=event.dataTransfer.getData(\'text/jobid\');if(id&&typeof mfMoveJob===\'function\')mfMoveJob(parseInt(id),\''+fid+'\');" ondragover="event.preventDefault();"';
        const base='flex:0 0 auto;display:flex;align-items:center;gap:8px;cursor:pointer;border-radius:12px;padding:14px 20px;font-size:15px;font-weight:'+(act?'700':'600')+';border:2px solid '+(act?'var(--primary)':'var(--border)')+';background:'+(act?'var(--primary-light,#eff6ff)':'#fff')+';color:'+(act?'var(--primary)':'var(--text)')+';box-shadow:'+(act?'0 2px 10px rgba(26,86,219,.18)':'0 1px 3px rgba(0,0,0,.06)');
        const badge='display:inline-flex;align-items:center;justify-content:center;min-width:24px;height:24px;padding:0 7px;border-radius:999px;font-size:12px;font-weight:700;background:'+(act?'var(--primary)':'var(--bg-alt,#f1f5f9)')+';color:'+(act?'#fff':'var(--text-secondary)')+';border:1px solid '+(act?'var(--primary)':'var(--border)');
        const xbtn=deletable?'<button onclick="event.stopPropagation();mfDeleteFolder('+rid+')" title="Usu\u0144 folder" style="background:none;border:none;cursor:pointer;color:#dc2626;font-size:16px;line-height:1;padding:0 0 0 2px">\u00d7</button>':'';
        const nm=String(label).replace(/</g,'&lt;');
        return '<div onclick="mfSelectFolder(\''+fid+'\')" style="'+base+'" title="'+nm+'"'+dd+'><span style="font-size:18px">\uD83D\uDCC1</span><span>'+nm+'</span><span style="'+badge+'">'+count+'</span>'+xbtn+'</div>';
    }
    let html=chip('','Wszystkie',mfCountInFolder(''),false,'');
    html+=chip('__none','Bez folderu',mfCountInFolder('__none'),false,'');
    _mfFolders.forEach(function(f){ html+=chip(String(f.id),f.name,mfCountInFolder(String(f.id)),true,f.id); });
    c.innerHTML=html;
}
function renderFolderCrumbs(){
    renderFolderChips();
}
async function mfCreateFolder(){
    const name=prompt('Nazwa folderu:');
    if(!name) return;
    const r=await fetch('/api/folders',{method:'POST',headers:{'Authorization':'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify({name:name})});
    if(!r.ok){ const e=await r.json().catch(function(){return {}}); alert(e.detail||'Blad'); return; }
    await loadFolders(); mfRender();
}
async function mfRenameFolder(id){
    const f=_mfFolders.find(function(x){return x.id===id});
    const name=prompt('Nowa nazwa:', f?f.name:'');
    if(!name) return;
    const r=await fetch('/api/folders/'+id,{method:'PATCH',headers:{'Authorization':'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify({name:name})});
    if(!r.ok){ const e=await r.json().catch(function(){return {}}); alert(e.detail||'Blad'); return; }
    await loadFolders(); mfRender();
}
async function mfDeleteFolder(id){
    if(!confirm('Usunac folder? Pliki zostana bez folderu.')) return;
    await fetch('/api/folders/'+id,{method:'DELETE',headers:{'Authorization':'Bearer '+token}});
    await loadFolders(); mfRender();
}
function mfToggleAll(on){
    _mfSelected.clear();
    if(on){
        const vis=_filteredJobs();
        vis.forEach(function(j){_mfSelected.add(j.id)});
    }
    document.querySelectorAll('.mf-check').forEach(function(cb){cb.checked=on});
    updateBulkBar();
}
function updateBulkBar(){
    const b=document.getElementById('mfBulkDelete');
    b.style.display=_mfSelected.size?'':'none';
    b.textContent='Usun zaznaczone ('+_mfSelected.size+')';
}
async function mfBulkDelete(){
    if(!_mfSelected.size) return;
    if(!confirm('Usunac '+_mfSelected.size+' plikow?')) return;
    const r=await fetch('/api/jobs/bulk-delete',{method:'POST',headers:{'Authorization':'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify({ids:[..._mfSelected]})});
    if(!r.ok){ alert('Blad usuwania'); return; }
    _mfSelected.clear();
    document.getElementById('mfSelectAll').checked=false;
    await loadMyJobs();
}
async function mfInlineRename(id){
    const j=_myJobsData.find(function(x){return x.id===id});
    const title=prompt('Nowa nazwa:', j? (j.title||j.filename):'');
    if(title===null) return;
    const t2=title.trim();
    if(!t2) return;
    const r=await fetch('/api/jobs/'+id+'/rename',{method:'PATCH',headers:{'Authorization':'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify({title:t2})});
    if(!r.ok){ const e=await r.json().catch(function(){return {}}); alert(e.detail||'Blad'); return; }
    j.title=t2; mfRender();
}
function _filteredJobs(){
    const q=(document.getElementById('mfSearch').value||'').toLowerCase();
    var _ffs=document.getElementById('mfFolderFilter');var ff=_ffs?_ffs.value:'';
    return _myJobsData.filter(function(j){
        if(q && !((j.filename||'').toLowerCase().includes(q) || (j.title||'').toLowerCase().includes(q))) return false;
        if(ff==='__none' && j.folder_id!=null) return false;
        if(ff && ff!=='__none' && String(j.folder_id||'')!==String(ff)) return false;
        return true;
    });
}
function mfRender(){
    if(typeof renderFolderChips==='function'){ try{renderFolderChips();}catch(e){} }
    const jobs=_filteredJobs();
    const grid=document.getElementById('mfGrid');
    if(!jobs.length){
        grid.innerHTML='<div style="grid-column:1/-1;text-align:center;color:var(--text-muted);padding:24px">Brak plików dla filtra</div>';
        return;
    }
    grid.innerHTML=jobs.map(function(j){
        const visBadge=j.visibility==='public' ? '<span style="background:#f0fdf4;color:#16a34a;padding:2px 8px;border-radius:999px;font-size:11px;font-weight:600">public</span>' : j.visibility==='private' ? '<span style="background:#fef2f2;color:#dc2626;padding:2px 8px;border-radius:999px;font-size:11px;font-weight:600">private</span>' : '<span style="background:#fffbeb;color:#d97706;padding:2px 8px;border-radius:999px;font-size:11px;font-weight:600">unlisted</span>';
        const is3mf=(j.filename||'').toLowerCase().endsWith('.3mf');
        const titleEsc=(j.title||j.filename||'').replace(/</g,'&lt;');
        const fallbackUrl='/api/preview/'+j.uuid;
        const thumbUrl='/api/thumb/'+j.uuid;
        const previewSrc=j.preview_image || fallbackUrl;
        const folderOpts='<option value="">Bez folderu</option>'+_mfFolders.map(function(f){return '<option value="'+f.id+'"'+(String(j.folder_id||'')===String(f.id)?' selected':'')+'>'+String(f.name).replace(/</g,'&lt;')+'</option>'}).join('');
        const thumb='<img src="'+previewSrc+'" style="width:100%;height:140px;object-fit:cover" onerror="if(this.dataset.step==\'0\'){this.dataset.step=\'1\';this.src=\''+thumbUrl+'\';}else{this.style.display=\'none\';if(this.nextElementSibling) this.nextElementSibling.style.display=\'flex\';}"><div style="display:none;height:140px;background:var(--bg-subtle);align-items:center;justify-content:center;flex-direction:column;gap:6px;color:var(--text-muted);font-size:12px;padding:8px;text-align:center"><div style="font-size:22px">📄</div><div style="font-weight:600;color:var(--text);font-size:12px;max-width:90%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'+titleEsc+'</div><div style="font-size:11px">Podgląd niedostępny</div></div>';
        return '<div draggable="true" ondragstart="event.dataTransfer.setData(\'text/jobid\','+j.id+')" style="background:var(--card);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;display:flex;flex-direction:column;transition:box-shadow .15s" onmouseover="this.style.boxShadow=\'var(--shadow-md)\'" onmouseout="this.style.boxShadow=\'none\'">'
        + '<div style="position:relative;cursor:pointer" onclick="openJobModal('+j.id+')">'
        + '<div style="height:140px;overflow:hidden">'+thumb+'</div>'
        + '<input type="checkbox" class="mf-check" '+(_mfSelected.has(j.id)?'checked':'')+' onclick="event.stopPropagation()" onchange="if(this.checked)_mfSelected.add('+j.id+');else _mfSelected.delete('+j.id+');updateBulkBar()" style="position:absolute;top:8px;left:8px;width:16px;height:16px">'
        + '<button onclick="event.stopPropagation();openPreviewFullscreen(\''+previewSrc+'\')" title="Powiększ podgląd" style="position:absolute;bottom:8px;right:8px;width:28px;height:28px;border-radius:50%;background:rgba(255,255,255,.9);border:1px solid var(--border);cursor:pointer;font-size:13px">🔍</button>'
        + '</div>'
        + '<div style="padding:12px;display:flex;flex-direction:column;gap:8px">'
        + '<div style="font-weight:600;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="'+titleEsc+'">'+titleEsc+' '+visBadge+'</div>'
        + '<div style="font-size:11px;color:var(--text-muted)">'+(j.created_at||'').slice(0,16)+' · '+(j.faces||'-')+' ścian · '+(j.mode||'hosting')+'</div>'
        + '<div style="display:flex;gap:6px;flex-wrap:wrap">'
        + '<button onclick="mfInlineRename('+j.id+')" style="flex:1;padding:6px 8px;background:var(--bg);border:1px solid var(--border);border-radius:var(--radius-sm);font-size:12px;cursor:pointer;font-family:inherit">Zmień nazwę</button>'
        + '<select onchange="mfMoveJob('+j.id+',this.value)" onclick="event.stopPropagation()" style="padding:5px 6px;background:var(--bg);border:1px solid var(--border);border-radius:var(--radius-sm);font-size:12px;cursor:pointer;max-width:110px;font-family:inherit" title="Folder">'+folderOpts+'</select>'
        + '</div>'
        + '<div style="display:flex;gap:6px;flex-wrap:wrap">'
        + '<button onclick="event.stopPropagation();openEditor('+j.id+')" style="padding:6px 8px;background:var(--bg);border:1px solid var(--border);border-radius:var(--radius-sm);font-size:12px;cursor:pointer;font-family:inherit" title="Edytuj">Edytuj</button>'
        + '<button onclick="event.stopPropagation(); if(confirm(\'Usunąć?\')) deleteMyJob('+j.id+')" style="padding:6px 8px;background:var(--bg);color:var(--error);border:1px solid #fecaca;border-radius:var(--radius-sm);font-size:12px;cursor:pointer;font-family:inherit">Usuń</button>'
        + '</div>'
        + '<div style="display:flex;gap:6px;flex-wrap:wrap">'
        + '<button onclick="event.stopPropagation();showDownloadDialog(\''+j.uuid+'\',\''+(j.title||j.original_filename||'').replace(/'/g,"\\'")+'\')" style="flex:1;padding:7px 8px;background:var(--primary);color:#fff;border:none;border-radius:var(--radius-sm);font-size:12px;font-weight:600;cursor:pointer;font-family:inherit">Pobierz</button>'
        + '<button onclick="openShareModalFor('+j.id+')" style="flex:1;padding:7px 8px;background:var(--bg);border:1px solid var(--border);border-radius:var(--radius-sm);font-size:12px;cursor:pointer;font-family:inherit">Udostępnij</button>'
        + '</div>'
        + '</div></div>';
    }).join('');
}
function openShareModalFor(jobId){
    const j=_myJobsData.find(function(x){return x.id===jobId});
    if(!j) return;
    _shareJobId=jobId;
    document.getElementById('shareModal').classList.add('show');
    const tog=document.getElementById('sharePublishToggle');
    if(tog) tog.checked=(j.visibility==='public');
    updatePublishToggleUI();
    document.getElementById('shareResult').style.display='none';
    document.getElementById('shareCreateBtn').style.display='';
    document.getElementById('shareUrl').value='';
    fetch('/api/jobs/'+jobId+'/share',{method:'POST',headers:{'Authorization':'Bearer '+token,'Content-Type':'application/json'},body:'{}'}).then(function(r){return r.json()}).then(function(d){
        document.getElementById('shareUrl').value=d.url||d.vanity||'';
        document.getElementById('shareResult').style.display='block';
        document.getElementById('shareCreateBtn').style.display='none';
    }).catch(function(){});
}
function updatePublishToggleUI(){
    const tog=document.getElementById('sharePublishToggle');
    const track=document.getElementById('sharePublishTrack');
    const knob=document.getElementById('sharePublishKnob');
    if(!tog||!track||!knob) return;
    if(tog.checked){ track.style.background='#1a56db'; knob.style.left='22px'; } else { track.style.background='#cbd5e1'; knob.style.left='2px'; }
}

function openPreviewFullscreen(src){
    if(!src) return;
    var ov=document.getElementById('previewFsOverlay');
    if(!ov){
        ov=document.createElement('div');
        ov.id='previewFsOverlay';
        ov.style.cssText='display:none;position:fixed;inset:0;z-index:2500;background:rgba(15,23,42,.85);align-items:center;justify-content:center;cursor:zoom-out';
        ov.innerHTML='<button class=\"preview-fullscreen-close\" onclick=\"closePreviewFullscreen()\">\u2715</button><img id=\"previewFsImg\" src=\"\" style=\"max-width:92vw;max-height:88vh;object-fit:contain;border-radius:8px;box-shadow:0 8px 32px rgba(0,0,0,0.3)\">';
        ov.onclick=function(e){if(e.target===ov)closePreviewFullscreen();};
        document.body.appendChild(ov);
    }
    document.getElementById('previewFsImg').src=src;
    ov.style.display='flex';
}
function closePreviewFullscreen(){
    var ov=document.getElementById('previewFsOverlay');
    if(ov) ov.style.display='none';
}
document.addEventListener('keydown',function(e){if(e.key==='Escape'){closePreviewFullscreen();closeJobFullscreen();}});
    async function togglePublishFromShare(){
    updatePublishToggleUI();
    if(!_shareJobId) return;
    const vis=document.getElementById('sharePublishToggle').checked ? 'public':'private';
    const r=await fetch('/api/jobs/'+_shareJobId+'/publish',{method:'PATCH',headers:{'Authorization':'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify({visibility:vis})});
    if(r.ok){
        const d=await r.json();
        const j=_myJobsData.find(function(x){return x.id===_shareJobId});
        if(j) j.visibility=d.visibility;
        mfRender();
    }
}
async function loadMyJobs() {
    if (!token) {
        document.getElementById('myFilesEmpty').style.display = 'block';
        document.getElementById('mfGrid').style.display = 'none';
        document.getElementById('myFilesToolbar').style.display = 'none';
        const qb=document.getElementById('quotaBar'); if(qb) qb.style.display='none';
        const cr=document.getElementById('mfFolderCrumbs'); if(cr) cr.style.display='none';
        return;
    }
    try {
        loadQuota(); loadFolders(); loadAuthorStats();
        const r = await fetch('/api/jobs', {headers:{'Authorization': 'Bearer '+token}});
        if (!r.ok) { document.getElementById('myFilesEmpty').style.display = 'block'; document.getElementById('mfGrid').style.display = 'none'; document.getElementById('myFilesToolbar').style.display='none'; return; }
        const d = await r.json();
        _myJobsData = d;
        if (!d.length) {
            document.getElementById('myFilesEmpty').style.display = 'block';
            const pe=document.getElementById('myFilesEmpty').querySelector('p'); if(pe) pe.textContent = t('myFilesEmpty');
            document.getElementById('mfGrid').style.display = 'none';
            document.getElementById('myFilesToolbar').style.display = 'flex';
            const qb2=document.getElementById('quotaBar'); if(qb2) qb2.style.display='block';
            mfRender();
            return;
        }
        document.getElementById('myFilesEmpty').style.display = 'none';
        document.getElementById('mfGrid').style.display = 'grid';
        document.getElementById('myFilesToolbar').style.display = 'flex';
        updateBulkBar();
        mfRender();
    } catch(e) {
        document.getElementById('myFilesEmpty').style.display = 'block';
        const g=document.getElementById('mfGrid'); if(g) g.style.display = 'none';
    }
}

/* ═══════ JOB PREVIEW MODAL (Moje pliki) ═══════ */
let _myJobsData = [];
let _jobCurrentStlUrl = null;
let _job3Renderer = null, _job3Controls = null, _job3AnimId = null;

function openJobModal(jobId) {
    const j = _myJobsData.find(x => x.id === jobId);
    if (!j) return;
    window._jobModalJob = j;
    const modal = document.getElementById('jobModal');
    modal.classList.add('show');
    document.getElementById('jobModalTitle').textContent = j.filename || ('Job #' + j.id);
    const date = (j.created_at || '').slice(0, 16);
    var dims=j.dims_mm||j.dimensions||'';
    if(!dims&&j.bbox){try{dims=Math.round(j.bbox[0])+' × '+Math.round(j.bbox[1])+' × '+Math.round(j.bbox[2])+' mm';}catch(e){}}
    document.getElementById('jobModalMeta').textContent =
        t('jobStatus') + ': ' + j.status + '  •  ' + t('jobMode') + ': ' + (j.mode || 'hosting') + '  •  ' + date
        + (dims?'  •  ⬛ '+dims:'')
        + (j.faces?'  •  ▲ '+j.faces+' ścian':'')
        + (j.file_size_bytes?'  •  💾 '+Math.round(j.file_size_bytes/1024)+' KB':'');
    const dlStep = document.getElementById('jobDlStep');
    const dlStl = document.getElementById('jobDlStl');
    const shareBtn = document.getElementById('jobShareBtn');
    const delBtn = document.getElementById('jobDeleteBtn');
    const hosted = j.status === 'hosted';
    const done = j.status === 'done';
    dlStep.textContent = done ? t('jobDlStep') : (hosted ? 'Konwertuj → STEP' : t('jobDlStep'));
    dlStep.style.display = '';
    dlStl.style.display = '';
    shareBtn.style.display = '';
    dlStep.onclick = () => {
        if (done) { window.open('/api/download/' + j.uuid + '?format=step', '_blank'); return; }
        doConvertOnDemand(j.uuid, j.id);
    };
    dlStl.onclick = () => window.open('/api/download/' + j.uuid + '?format=stl', '_blank');
    shareBtn.onclick = () => doShare(j.id);
    delBtn.onclick = () => deleteMyJob(j.id);
    const heroSection = document.getElementById('jobPreviewHero');
    const heroImg = document.getElementById('jobPreviewHeroImg');
    const jp = j.preview_image || '/api/preview/' + j.uuid;
    heroSection.style.display = 'block';
    heroImg.src = jp;
    heroImg.onerror = function() {
        heroSection.innerHTML = '<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;padding:24px;background:var(--bg-subtle);border:1px solid var(--border-light);border-radius:8px;margin:12px 24px 0"><div style="font-size:28px">📄</div><div style="font-weight:600;font-size:14px;color:var(--text);text-align:center">'+(j.title||j.filename||('Job #'+j.id)).replace(/</g,'&lt;')+'</div><div style="font-size:12px;color:var(--text-secondary)">Podgląd niedostępny</div></div>';
        heroSection.style.display = 'block';
    };
    _jobCurrentStlUrl = '/api/stl-preview/' + j.uuid;
    document.getElementById('jobFullscreenBtn').style.display = '';
    loadJobModalSTL('/api/stl-preview/' + j.uuid);
}

async function doConvertOnDemand(uuid, jobId) {
    const dlStep = document.getElementById('jobDlStep');
    const prev = dlStep.textContent;
    dlStep.disabled = true; dlStep.textContent = 'Konwersja mesh→STEP...';
    try {
        const r = await fetch('/api/convert-on-demand/' + uuid, {method:'POST', headers: token?{'Authorization':'Bearer '+token}:{'Content-Type':'application/json'}});
        const d = await r.json();
        if (!r.ok) throw new Error(d.detail || 'Conversion failed');
        dlStep.textContent = 'Gotowe! Pobieranie...';
        setTimeout(() => { window.open('/api/download/' + uuid + '?format=step', '_blank'); }, 300);
        dlStep.textContent = 'Pobierz STEP';
        toast('STEP gotowy (' + d.step_size_kb + ' KB, ' + d.time_s + 's)');
    } catch(e) {
        toast('Błąd konwersji: ' + e.message, 'error');
        dlStep.textContent = prev;
    }
    dlStep.disabled = false;
}

function closeJobModal() {
    document.getElementById('jobModal').classList.remove('show');
    if (_job3AnimId) cancelAnimationFrame(_job3AnimId);
    _job3AnimId = null;
    if (_job3Renderer) { _job3Renderer.dispose(); _job3Renderer = null; }
    if (_job3Controls) { try { _job3Controls.dispose(); } catch(e) {} _job3Controls = null; }
    const c = document.getElementById('jobPreviewCanvas');
    if (c) c.innerHTML = '';
}

/* ═══════ FULLSCREEN 3D OVERLAY ═══════ */
let _fsRenderer = null, _fsScene = null, _fsCamera = null, _fsControls = null, _fsAnimId = null, _fsInitialPos = null;
let _fsPinchDist = 0, _fsGesturesBound = false;

function openJobFullscreen() {
    if (!_jobCurrentStlUrl || !window.THREE || !window._OrbitControls) return;
    const overlay = document.getElementById('fsOverlay');
    overlay.classList.add('show');
    const container = document.getElementById('fsViewer');
    container.innerHTML = '';
    const W = container.clientWidth || window.innerWidth;
    const H = container.clientHeight || (window.innerHeight - 60);
    _fsScene = new THREE.Scene();
    _fsScene.background = new THREE.Color(0xf0f2f5);
    _fsCamera = new THREE.PerspectiveCamera(45, W / H, 0.1, 10000);
    _fsRenderer = new THREE.WebGLRenderer({ antialias: true });
    _fsRenderer.setSize(W, H);
    _fsRenderer.setPixelRatio(window.devicePixelRatio || 1);
    container.appendChild(_fsRenderer.domElement);
    _fsScene.add(new THREE.AmbientLight(0xffffff, 0.7));
    const dl = new THREE.DirectionalLight(0xffffff, 0.9); dl.position.set(1,1,1); _fsScene.add(dl);
    const dl2 = new THREE.DirectionalLight(0x1a56db, 0.3); dl2.position.set(-1,0.5,-1); _fsScene.add(dl2);
    _fsControls = new window._OrbitControls(_fsCamera, _fsRenderer.domElement);
    _fsControls.enableDamping = true;
    _fsCamera.position.set(80, 60, 80);
    _fsCamera.lookAt(0, 0, 0);
    _fsControls.update();
    function animate() { _fsAnimId = requestAnimationFrame(animate); _fsControls.update(); _fsRenderer.render(_fsScene, _fsCamera); }
    animate();
    loadFsSTL(_jobCurrentStlUrl);
    // Lazy-bind wheel + pinch once DOM is parsed
    if (!_fsGesturesBound) {
        const fsEl = document.getElementById('fsViewer');
        if (fsEl) {
            _fsGesturesBound = true;
            fsEl.addEventListener('wheel', function(e) {
                if (!_fsRenderer) return;
                e.preventDefault();
                fsZoom(e.deltaY > 0 ? 0.1 : -0.1);
            }, { passive: false });
            fsEl.addEventListener('touchstart', function(e) {
                if (e.touches.length === 2) _fsPinchDist = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY);
            }, { passive: true });
            fsEl.addEventListener('touchmove', function(e) {
                if (e.touches.length === 2 && _fsPinchDist) {
                    e.preventDefault();
                    const nd = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY);
                    fsZoom((_fsPinchDist - nd) / _fsPinchDist * 0.5);
                    _fsPinchDist = nd;
                }
            }, { passive: false });
            fsEl.addEventListener('touchend', function(){ _fsPinchDist = 0; }, { passive: true });
        }
    }
    // Resize renderer on window resize while fullscreen open
    let _fsResize = function(){
        if (!_fsRenderer || !overlay.classList.contains('show')) return;
        const W2 = container.clientWidth || window.innerWidth;
        const H2 = container.clientHeight || (window.innerHeight - 60);
        _fsCamera.aspect = W2 / H2;
        _fsCamera.updateProjectionMatrix();
        _fsRenderer.setSize(W2, H2);
    };
    window.addEventListener('resize', _fsResize);
    // Remove listener on close (store on overlay)
    overlay._fsResize = _fsResize;
}

function closeJobFullscreen() {
    const overlay = document.getElementById('fsOverlay');
    if (!overlay.classList.contains('show')) return;
    overlay.classList.remove('show');
    if (overlay._fsResize) { window.removeEventListener('resize', overlay._fsResize); overlay._fsResize = null; }
    if (_fsAnimId) { cancelAnimationFrame(_fsAnimId); _fsAnimId = null; }
    if (_fsRenderer) { _fsRenderer.dispose(); _fsRenderer = null; }
    if (_fsControls) { try { _fsControls.dispose(); } catch(e){} _fsControls = null; }
    _fsScene = null; _fsCamera = null; _fsInitialPos = null;
}

function loadFsSTL(url) {
    if (!_fsScene) return;
    const ext = url.split('.').pop().toLowerCase().split('?')[0];
    const mat = new THREE.MeshPhongMaterial({ color: 0x1a56db, specular: 0x93b8ea, shininess: 40 });
    function addMeshObj(obj) {
        obj.traverse(function(c) { if (c.isMesh) c.material = mat; });
        obj.rotation.x = -Math.PI / 2;
        const cb = new THREE.Box3().setFromObject(obj);
        const ctr = new THREE.Vector3(); cb.getCenter(ctr); obj.position.sub(ctr);
        const sz = new THREE.Vector3(); cb.getSize(sz);
        obj.scale.setScalar(100 / (Math.max(sz.x, sz.y, sz.z) || 1));
        _fsScene.add(obj);
        _fsInitialPos = _fsCamera.position.clone();
    }
    const req = new XMLHttpRequest();
    req.open('GET', url);
    if (token) req.setRequestHeader('Authorization', 'Bearer ' + token);
    req.responseType = 'arraybuffer';
    req.onload = function() {
        if (req.status !== 200 || !req.response) return;
        const data = req.response;
        try {
            if (ext === 'obj' && window._OBJLoader) { new window._OBJLoader().load(URL.createObjectURL(new Blob([data])), addMeshObj); }
            else if (ext === '3mf' && window._3MFLoader) { new window._3MFLoader().load(URL.createObjectURL(new Blob([data])), addMeshObj); }
            else {
                const geometry = new window._STLLoader().parse(data);
                geometry.computeBoundingBox();
                const box = geometry.boundingBox;
                const center = new THREE.Vector3(); box.getCenter(center);
                geometry.translate(-center.x, -center.y, -center.z);
                const size = new THREE.Vector3(); box.getSize(size);
                const mesh = new THREE.Mesh(geometry, mat);
                mesh.scale.setScalar(100 / (Math.max(size.x, size.y, size.z) || 1));
                _fsScene.add(mesh);
                _fsInitialPos = _fsCamera.position.clone();
            }
        } catch(e) { console.error('fs preview error:', e); }
    };
    req.send();
}

function fsZoom(delta) {
    if (!_fsCamera || !_fsControls) return;
    const dir = new THREE.Vector3().subVectors(_fsCamera.position, _fsControls.target);
    const dist = dir.length();
    dir.normalize().multiplyScalar(dist * (1 + delta));
    _fsCamera.position.copy(_fsControls.target).add(dir);
    _fsControls.update();
}
function fsZoomIn() { fsZoom(-0.2); }
function fsZoomOut() { fsZoom(0.2); }
function fsResetCamera() {
    if (!_fsCamera || !_fsControls || !_fsInitialPos) return;
    _fsCamera.position.copy(_fsInitialPos);
    _fsControls.target.set(0, 0, 0);
    _fsControls.update();
}

// Scroll + pinch are bound lazily in openJobFullscreen

function _jobModalDeps(cb, errCb) {
    const T = window.THREE, OC = window._OrbitControls, SL = window._STLLoader;
    if (T && OC && SL) { cb(T, OC, SL, window._OBJLoader, window._3MFLoader); return; }
    let tries = 0;
    const iv = setInterval(() => {
        const T2 = window.THREE, OC2 = window._OrbitControls, SL2 = window._STLLoader;
        tries++;
        if (T2 && OC2 && SL2) { clearInterval(iv); cb(T2, OC2, SL2); }
        else if (tries > 50) { clearInterval(iv); errCb && errCb(); }
    }, 200);
}

function showJobModalErr() {
    const c = document.getElementById('jobPreviewCanvas');
    if (c) c.innerHTML =
        '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-secondary)">Podglad niedostepny</div>';
}

function loadJobModalSTL(url) {
    const container = document.getElementById('jobPreviewCanvas');
    console.log('[3D] loadJobModalSTL called url=', url, 'container=', !!container, 'clientW=', container && container.clientWidth);
    // Ensure container has explicit height and loading text
    const wrap = container.closest('.job-preview-wrap');
    if(wrap){ wrap.style.minHeight = '400px'; }
    container.style.minHeight = '400px';
    container.style.height = '400px';
    container.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:400px;min-height:400px;color:var(--text-secondary);font-size:14px;font-weight:500">\u0141adowanie modelu 3D...</div>';
    const req = new XMLHttpRequest();
    req.open('GET', url);
    if (token) req.setRequestHeader('Authorization', 'Bearer ' + token);
    req.responseType = 'arraybuffer';
    req.onload = function() {
        if (req.status !== 200 || !req.response) { showJobModalErr(); return; }
        const data = req.response;
        const ext = url.split('.').pop().toLowerCase().split('?')[0];
        _jobModalDeps(function(T, OC, SL, OL, TML) {
            const w = container.clientWidth || 740;
            const h = Math.min(window.innerHeight * 0.5, 480) || 400;
            container.innerHTML = '';
            const scene = new T.Scene();
            scene.background = new T.Color(0xf0f2f5);
            const camera = new T.PerspectiveCamera(45, w / h, 0.1, 10000);
            const renderer = new T.WebGLRenderer({ antialias: true });
            renderer.setSize(w, h);
            renderer.setPixelRatio(window.devicePixelRatio || 1);
            container.appendChild(renderer.domElement);
            // Force resize after DOM layout settles (modal just opened, clientWidth was 0)
            console.log('[3D] loadJobModalSTL: renderer mounted w=', w, 'h=', h);
            setTimeout(function(){ renderer.setSize(container.clientWidth || w, h); }, 100);
            scene.add(new T.AmbientLight(0xffffff, 0.7));
            const dl = new T.DirectionalLight(0xffffff, 0.9);
            dl.position.set(1, 1, 1);
            scene.add(dl);
            const controls = new OC(camera, renderer.domElement);
            controls.enableDamping = true;
            controls.target.set(0, 0, 0);
            _job3Renderer = renderer;
            _job3Controls = controls;
            try {
                const mat = new T.MeshPhongMaterial({ color: 0x1a56db, specular: 0x111111, shininess: 30 });
                function addMeshObj(obj) {
                    obj.traverse(function(c) { if (c.isMesh) c.material = mat; });
                    obj.rotation.x = -Math.PI / 2;
                    const cb = new T.Box3().setFromObject(obj);
                    const ctr = new T.Vector3(); cb.getCenter(ctr);
                    obj.position.sub(ctr);
                    const sz = new T.Vector3(); cb.getSize(sz);
                    const md = Math.max(sz.x, sz.y, sz.z) || 1;
                    obj.scale.setScalar(100 / md);
                    scene.add(obj);
                }
                if (ext === 'obj' && OL) {
                    new OL().load(URL.createObjectURL(new Blob([data])), addMeshObj, undefined, function(){ showJobModalErr(); });
                } else if (ext === '3mf' && TML) {
                    new TML().load(URL.createObjectURL(new Blob([data])), addMeshObj, undefined, function(){ showJobModalErr(); });
                } else {
                    const geometry = new SL().parse(data);
                    geometry.computeBoundingBox();
                    const box = geometry.boundingBox;
                    const center = new T.Vector3();
                    box.getCenter(center);
                    geometry.translate(-center.x, -center.y, -center.z);
                    const size = new T.Vector3(); box.getSize(size);
                    const maxDim = Math.max(size.x, size.y, size.z) || 1;
                    const mesh = new T.Mesh(geometry, mat);
                    mesh.scale.setScalar(100 / maxDim);
                    scene.add(mesh);
                }
                camera.position.set(80, 60, 80);
                camera.lookAt(0, 0, 0);
                controls.update();
                function animate() {
                    _job3AnimId = requestAnimationFrame(animate);
                    controls.update();
                    renderer.render(scene, camera);
                }
                animate();
            } catch(e) { console.error('preview error:', e); showJobModalErr(); }
        }, showJobModalErr);
    };
    req.onerror = showJobModalErr;
    req.send();
}

async function deleteMyJob(jobId) {
    if (!confirm(t('jobDeleteConfirm'))) return;
    try {
        const r = await fetch('/api/jobs/' + jobId, {
            method: 'DELETE',
            headers: token ? {'Authorization': 'Bearer ' + token} : {}
        });
        if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || 'Error'); }
        closeJobModal();
        loadMyJobs();
    } catch(e) { alert(e.message); }
}

    async function mfMoveJob(jobId, folderId){
        try{
            const r=await fetch('/api/jobs/'+jobId+'/rename',{method:'PATCH',headers:{'Authorization':'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify({folder_id:folderId})});
            if(r.ok){
                const j=_myJobsData.find(function(x){return x.id===jobId});
                if(j) j.folder_id=folderId;
                mfRender();
                toast('Przeniesiono do folderu','success');
            }
        }catch(e){}
    }

    function edInsert(before, after) {
        var desc = document.getElementById('edDesc');
        var start = desc.selectionStart, end = desc.selectionEnd;
        var sel = desc.value.substring(start, end);
        desc.value = desc.value.substring(0, start) + before + sel + after + desc.value.substring(end);
        desc.focus();
        desc.selectionStart = start + before.length;
        desc.selectionEnd = start + before.length + sel.length;
        desc.dispatchEvent(new Event('input'));
    }
    function edUpdateCharCount() {
        var desc = document.getElementById('edDesc');
        var cnt = document.getElementById('edCharCount');
        if (desc && cnt) cnt.textContent = desc.value.length + ' znaków';
    }

/* ═══════ EDITOR MODAL ═══════ */
    let _edJobId = null;
    let _edDescListener = null;

    function _mdToHtml(md) {
        if (!md) return '';
        let h = md
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
        // code blocks ```...```
        h = h.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
        // inline code
        h = h.replace(/`([^`]+)`/g, '<code>$1</code>');
        // headings
        h = h.replace(/^#### (.+)$/gm, '<h4>$1</h4>');
        h = h.replace(/^### (.+)$/gm, '<h3>$1</h3>');
        h = h.replace(/^## (.+)$/gm, '<h2>$1</h2>');
        h = h.replace(/^# (.+)$/gm, '<h1>$1</h1>');
        // bold + italic
        h = h.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
        h = h.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        h = h.replace(/\*(.+?)\*/g, '<em>$1</em>');
        // images
        h = h.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" style="max-width:100%;border-radius:8px">');
        // links
        h = h.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
        // newlines → <br> (but not inside pre)
        h = h.replace(/\n/g, '<br>');
        return h;
    }

    function openEditor(jobId) {
        const j = _myJobsData.find(function(x) { return x.id === jobId; });
        if (!j) return;
        _edJobId = jobId;

        document.getElementById('edTitle').value = j.title || j.filename || '';
        document.getElementById('edTags').value = (j.tags || []).join(', ');
        document.getElementById('edYoutube').value = j.youtube_url || '';
        document.getElementById('edVisibility').value = j.visibility || 'private';
        document.getElementById('edDesc').value = j.description || '';

        // populate folder options
        const folderSel = document.getElementById('edFolder');
        folderSel.innerHTML = '<option value="">' + t('mfFolderNone') + '</option>';
        _mfFolders.forEach(function(f) {
            const opt = document.createElement('option');
            opt.value = f.id;
            opt.textContent = f.name;
            folderSel.appendChild(opt);
        });
        folderSel.value = j.folder_id || '';

        // live markdown preview
        const descEl = document.getElementById('edDesc');
        const previewEl = document.getElementById('edPreview');
        previewEl.innerHTML = _mdToHtml(descEl.value);
        if (_edDescListener) descEl.removeEventListener('input', _edDescListener);
        _edDescListener = function() { previewEl.innerHTML = _mdToHtml(descEl.value); edUpdateCharCount(); };
        descEl.addEventListener('input', _edDescListener);

        // gallery from existing images in description
        const galEl = document.getElementById('edGallery');
        galEl.innerHTML = '';
        var imgMatches = (j.description || '').match(/!\[[^\]]*\]\([^)]+\)/g) || [];
        imgMatches.forEach(function(m) {
            var urlM = m.match(/\(([^)]+)\)/);
            if (urlM) {
                var img = document.createElement('img');
                img.src = urlM[1];
                img.style.cssText = 'width:60px;height:60px;object-fit:cover;border-radius:6px;border:1px solid #e2e8f0';
                galEl.appendChild(img);
            }
        });

        var _sse=document.getElementById('edSaveStatus');if(_sse)_sse.textContent='';
        edUpdateCharCount();
        document.getElementById('editorModal').classList.add('show');
    }

    function closeEditorModal() {
        document.getElementById('editorModal').classList.remove('show');
        _edJobId = null;
        if (_edDescListener) {
            document.getElementById('edDesc').removeEventListener('input', _edDescListener);
            _edDescListener = null;
        }
    }

    async function edSave() {
        if (!_edJobId) return;
        const statusEl = document.getElementById('edSaveStatus');
        if(!statusEl) return;
        statusEl.textContent = '...';
        const body = {
            title: document.getElementById('edTitle').value.trim(),
            description: document.getElementById('edDesc').value,
            tags: document.getElementById('edTags').value.split(',').map(function(s){return s.trim()}).filter(Boolean),
            youtube_url: document.getElementById('edYoutube').value.trim() || null,
            visibility: document.getElementById('edVisibility').value,
            folder_id: document.getElementById('edFolder').value || null
        };
        try {
            const r = await fetch('/api/jobs/' + _edJobId + '/meta', {
                method: 'PATCH',
                headers: {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'},
                body: JSON.stringify(body)
            });
            if (!r.ok) { const e = await r.json().catch(function(){return{}}); throw new Error(e.detail || 'Error'); }
            // update local data
            const j = _myJobsData.find(function(x) { return x.id === _edJobId; });
            if (j) {
                j.title = body.title;
                j.description = body.description;
                j.tags = body.tags;
                j.youtube_url = body.youtube_url;
                j.visibility = body.visibility;
                j.folder_id = body.folder_id ? Number(body.folder_id) : null;
            }
            statusEl.textContent = t('editorSaved');
            closeEditorModal();
            mfRender();
        } catch(e) {
            statusEl.textContent = t('editorSaveErr', {msg: e.message});
        }
    }

    async function edUploadImages() {
        const inp = document.getElementById('edImageInput');
        const files = inp.files;
        if (!files || !files.length || !_edJobId) return;
        const statusEl = document.getElementById('edUploadStatus');
        if(!statusEl) return;
        statusEl.textContent = t('editorUploading');
        let inserted = 0;
        for (let i = 0; i < files.length; i++) {
            try {
                const fd = new FormData();
                fd.append('image', files[i]);
                const r = await fetch('/api/jobs/' + _edJobId + '/preview', {
                    method: 'POST',
                    headers: token ? {'Authorization': 'Bearer ' + token} : {},
                    body: fd
                });
                if (!r.ok) continue;
                const d = await r.json();
                const url = d.url || d.preview_url || d.image_url || '';
                if (!url) continue;
                // insert markdown image into edDesc
                const descEl = document.getElementById('edDesc');
                const cursor = descEl.selectionStart;
                const val = descEl.value;
                const ins = (cursor > 0 && val[cursor - 1] !== '\n' ? '\n' : '') + '![](' + url + ')\n';
                descEl.value = val.slice(0, cursor) + ins + val.slice(cursor);
                descEl.dispatchEvent(new Event('input'));
                // add thumbnail to gallery
                const galEl = document.getElementById('edGallery');
                const img = document.createElement('img');
                img.src = url;
                img.style.cssText = 'width:60px;height:60px;object-fit:cover;border-radius:6px;border:1px solid #e2e8f0';
                galEl.appendChild(img);
                inserted++;
            } catch(e) {}
        }
        statusEl.textContent = t('editorUploaded', {n: inserted});
        inp.value = '';
    }

    document.getElementById('editorModal').addEventListener('click', function(e) {
        if (e.target === this) closeEditorModal();
    });

export { loadMyJobs, mfRender };
window._mfSelected = _mfSelected;
window.doShare = doShare;
window.toggleShareAnon = toggleShareAnon;
window.closeShareModal = closeShareModal;
window.createShareLink = createShareLink;
window.copyShareUrl = copyShareUrl;
window.doEmbed = doEmbed;
window.loadQuota = loadQuota;
window.loadFolders = loadFolders;
window.mfSelectFolder = mfSelectFolder;
window.renderFolderChips = renderFolderChips;
window.renderFolderCrumbs = renderFolderCrumbs;
window.mfCreateFolder = mfCreateFolder;
window.mfRenameFolder = mfRenameFolder;
window.mfDeleteFolder = mfDeleteFolder;
window.mfToggleAll = mfToggleAll;
window.updateBulkBar = updateBulkBar;
window.mfBulkDelete = mfBulkDelete;
window.mfInlineRename = mfInlineRename;
window.mfRender = mfRender;
window.openShareModalFor = openShareModalFor;
window.openPreviewFullscreen = openPreviewFullscreen;
window.closePreviewFullscreen = closePreviewFullscreen;
window.togglePublishFromShare = togglePublishFromShare;
window.loadMyJobs = loadMyJobs;
window.openJobModal = openJobModal;
window.doConvertOnDemand = doConvertOnDemand;
window.closeJobModal = closeJobModal;
window.openJobFullscreen = openJobFullscreen;
window.closeJobFullscreen = closeJobFullscreen;
window.fsZoom = fsZoom;
window.fsZoomIn = fsZoomIn;
window.fsZoomOut = fsZoomOut;
window.fsResetCamera = fsResetCamera;
window.deleteMyJob = deleteMyJob;
window.mfMoveJob = mfMoveJob;
window.edInsert = edInsert;
window.openEditor = openEditor;
window.closeEditorModal = closeEditorModal;
window.edSave = edSave;
window.edUploadImages = edUploadImages;

window.showDownloadDialog = showDownloadDialog;
window.showEmbedDialog = doEmbed;
window.copyEmbedCode = copyEmbedCode;
window.showShareEmailModal = showShareEmailModal;
window.shareEmailSend = shareEmailSend;
