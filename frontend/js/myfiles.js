// myfiles.js  -  jobs grid, folders, bulk, share modal, job modal, fullscreen, editor (verbatim).
import { t } from './i18n.js?v=105';
import { token } from './shared.js?v=105';
import { toast } from './viewer3d.js?v=105';

let _shareJobId = null;
let _shareVanityUrl = '';
let _shareToken = '';

function doShare(jobId) {
    _shareJobId = jobId;
    _shareToken = '';
    _shareVanityUrl = '';
    document.getElementById('shareUrl').value = '';
    document.getElementById('shareResult').style.display = 'none';
    document.getElementById('shareSettings').style.display = '';
    document.getElementById('shareCreateBtn').disabled = false;
    document.getElementById('shareCreateBtn').textContent = t('shareCreate');
    document.getElementById('shareEmbedCode').style.display = 'none';
    // Anon radios: hide for non-logged-in users
    const choice = document.getElementById('shareAnonChoice');
    const info = document.getElementById('shareAnonInfo');
    if (token) {
        if (choice) { choice.style.display = ''; }
        if (info) info.style.display = 'none';
    } else {
        if (choice) choice.style.display = 'none';
        if (info) info.style.display = '';
    }
    // Preset radio to "named" if logged in
    const namedRadio = document.querySelector('input[name="shareAnonMode"][value="named"]');
    const anonRadio = document.querySelector('input[name="shareAnonMode"][value="anon"]');
    if (namedRadio) namedRadio.checked = !!token;
    if (anonRadio) anonRadio.checked = !token;
    // Reset publish toggle from job data
    const j = _myJobsData ? _myJobsData.find(function(x) { return x.id === jobId; }) : null;
    const tog = document.getElementById('sharePublishToggle');
    if (tog && j) tog.checked = (j.visibility === 'public');
    updatePublishToggleUI();
    document.getElementById('shareModal').classList.add('show');
}
function closeShareModal() {
    document.getElementById('shareModal').classList.remove('show');
    _shareJobId = null;
}
async function createShareLink(embedMode) {
    if (!_shareJobId) return;
    const btn = document.getElementById('shareCreateBtn');
    btn.disabled = true; btn.textContent = t('shareCreate') + '...';
    // Read settings
    const isAnon = token ? !document.querySelector('input[name="shareAnonMode"][value="named"]').checked : true;
    const expiresDays = document.getElementById('shareExpiry').value;
    const fd = new FormData();
    fd.append('job_id', _shareJobId);
    fd.append('fmt', 'step');
    fd.append('show_author', !isAnon);
    fd.append('anon', isAnon);
    fd.append('expires_days', expiresDays);
    try {
        const r = await fetch('/api/share', {method:'POST', body:fd, headers: token?{'Authorization':'Bearer '+token}:{}});
        if (!r.ok) { const e = await r.json().catch(()=>({})); throw new Error(e.detail || 'Error ' + r.status); }
        const d = await r.json();
        _shareVanityUrl = d.vanity || '';
        _shareToken = d.token || '';
        // Show URL
        const urlInput = document.getElementById('shareUrl');
        if (isAnon || !d.vanity) {
            urlInput.value = window.location.origin + '/s/' + d.token;
        } else {
            urlInput.value = d.vanity;
        }
        document.getElementById('shareResult').style.display = 'block';
        // Embed code
        const embedSection = document.getElementById('shareEmbedCode');
        const embedInput = document.getElementById('shareEmbedInput');
        if (embedMode && embedSection && embedInput) {
            const job = _myJobsData ? _myJobsData.find(function(x) { return x.id === _shareJobId; }) : null;
            const slug = job && job.slug ? job.slug : '';
            const embedUrl = isAnon
                ? window.location.origin + '/s/' + d.token
                : (d.vanity || window.location.origin + '/s/' + d.token);
            embedInput.value = '<iframe src="' + embedUrl + '" width="800" height="500" frameborder="0" allowfullscreen></iframe>';
            embedSection.style.display = 'block';
        }
        // Expiry info
        const infoEl = document.getElementById('shareExpiryInfo');
        if (infoEl) {
            if (expiresDays > 0) {
                infoEl.innerHTML = '⏳ Link ważny <b>' + expiresDays + ' dni</b> — auto-usuwany po wygaśnięciu.';
            } else {
                infoEl.innerHTML = '⏒ Link bez limitu czasowego.';
            }
        }
        startExpiryCountdown(d.token || '');
        // Publish to Odkrywaj if toggle on
        const tog = document.getElementById('sharePublishToggle');
        if (tog && tog.checked) {
            fetch('/api/jobs/' + _shareJobId + '/publish', {
                method: 'PATCH',
                headers: {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'},
                body: JSON.stringify({visibility: 'public'})
            }).then(function(r2) { if (r2.ok) { var j2 = _myJobsData ? _myJobsData.find(function(x) { return x.id === _shareJobId; }) : null; if (j2) j2.visibility = 'public'; mfRender(); } });
        }
    } catch(e) {
        document.getElementById('shareResult').style.display = 'block';
        document.getElementById('shareUrl').value = 'Błąd: ' + (e.message || e);
    }
    btn.disabled = false; btn.textContent = t('shareCreate');
}
function copyShareUrl() {
    const el = document.getElementById('shareUrl');
    el.select();
    navigator.clipboard.writeText(el.value);
    try { if (window.ev) window.ev('share_click', { href: String(el.value).slice(0, 120) }); } catch (e) {}
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
        var _kb=function(b){return b<1048576?(b/1024).toFixed(1).replace('.',',')+' KB':(b/1048576).toFixed(1).replace('.',',')+' MB'};
        document.getElementById('quotaLabel').textContent='Wykorzystano '+(q.used_bytes!=null?_kb(q.used_bytes):q.used_mb+' MB')+' / '+(q.limit_mb>=1024?(Math.round(q.limit_mb/102.4)/10)+' GB':q.limit_mb+' MB');
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
    var vis=window._mfVis||'';
    var jobs=_myJobsData.filter(function(j){
        if(q && !((j.filename||'').toLowerCase().includes(q) || (j.title||'').toLowerCase().includes(q))) return false;
        if(ff==='__none' && j.folder_id!=null) return false;
        if(ff && ff!=='__none' && String(j.folder_id||'')!==String(ff)) return false;
        if(vis && (j.visibility||'private')!==vis) return false;
        return true;
    });
    var sort=(document.getElementById('mfSort')||{}).value||'date';
    jobs.sort(function(a,b){
        if(sort==='name') return (a.title||a.filename||'').localeCompare(b.title||b.filename||'','pl');
        if(sort==='size') return (b.file_size_bytes||0)-(a.file_size_bytes||0);
        if(sort==='views') return (b.views||0)-(a.views||0);
        if(sort==='oldest') return new Date(a.created_at||0)-new Date(b.created_at||0);
        return new Date(b.created_at||0)-new Date(a.created_at||0);
    });
    return jobs;
}
function mfSetSort(v){mfRender();}
function mfSetVis(v){
    window._mfVis=v;
    document.querySelectorAll('#mfVisChips .mf-vchip').forEach(function(b){b.classList.toggle('on',b.dataset.v===v)});
    mfRender();
}

function mfRender(){
    if(typeof renderFolderChips==='function'){ try{renderFolderChips();}catch(e){} }
    const jobs=_filteredJobs();
    window.__mfJobs = jobs;
    const grid=document.getElementById('mfGrid');
    if(!jobs.length){
        grid.innerHTML='<div class="mf-empty-f"><b>'+(window._mfVis||document.getElementById('mfSearch').value||document.getElementById('mfFolderFilter').value?'Brak plików dla tych filtrów':'Nie masz jeszcze plików')+'</b>'
        +(window._mfVis||document.getElementById('mfSearch').value?'<button class="mfc-a" style="margin-top:12px" onclick="mfResetFilters()">Wyczyść filtry</button>':'<button class="mfc-a" style="margin-top:12px;background:var(--accent);border-color:var(--accent);color:#fff" onclick="quickUpload()">↑ Wgraj pierwszy plik</button>')
        +'</div>';
        return;
    }
    grid.innerHTML=jobs.map(function(j){
        const vis=j.visibility||'private';
        const visBadge='<span class="mfc-badge '+({public:'pub',unlisted:'unl'}[vis]||'pri')+'">'+({public:'publiczny',unlisted:'link'}[vis]||'prywatny')+'</span>';
        const titleEsc=(j.title||j.filename||'').replace(/</g,'&lt;');
        const thumbUrl='/api/thumb/'+j.uuid+'?v=3';
        const previewSrc='/api/thumb/'+j.uuid+'?v=3';
        const folderOpts='<option value="">Bez folderu</option>'+_mfFolders.map(function(f){return '<option value="'+f.id+'"'+(String(j.folder_id||'')===String(f.id)?' selected':'')+'>'+String(f.name).replace(/</g,'&lt;')+'</option>'}).join('');
        const when=(j.created_at||'').slice(0,10);
        const kb=j.file_size_bytes?Math.round(j.file_size_bytes/1024)+' KB':'';
        const dims=(j.dims_mm||'').replace(/ ?x ?/g,' × ');
        const thumb='<img src="'+previewSrc+'" alt="" loading="lazy" onerror="if(this.dataset.step==\'0\'){this.dataset.step=\'1\';this.src=\''+thumbUrl+'\';}else{this.style.display=\'none\';}">'
        +'<div class="mfc-zoom" title="Powiększ" onclick="event.stopPropagation();openPreviewFullscreen(\''+previewSrc+'\')"><svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3M11 8v6M8 11h6"/></svg></div>';
        return '<div class="mfc" draggable="true" ondragstart="event.dataTransfer.setData(\'text/jobid\','+j.id+')">'
        + '<div class="mfc-thumb" onclick="openJobModal('+j.id+')">'+thumb
        + '<input type="checkbox" class="mfc-check" '+(_mfSelected.has(j.id)?'checked':'')+' onclick="event.stopPropagation()" onchange="if(this.checked)_mfSelected.add('+j.id+');else _mfSelected.delete('+j.id+');updateBulkBar()">'
        + '</div>'
        + '<div class="mfc-b">'
        + '<div class="mfc-name" title="'+titleEsc+'"><span>'+titleEsc+'</span>'+visBadge+'</div>'
        + '<div class="mfc-meta"><span>'+when+'</span>'+(kb?'<span>'+kb+'</span>':'')+(j.faces?'<span>'+j.faces+' ścian</span>':'')+(dims?'<span>'+dims+'</span>':'')+((j.views||0)>0?'<span>'+j.views+' odsłon</span>':'')+'</div>'
        + '<div class="mfc-acts">'
        + '<button class="mfc-a" onclick="event.stopPropagation();openEditor('+j.id+')" title="Edytuj opis / tagi / widoczność">Edytuj</button>'
        + '<button class="mfc-a" onclick="event.stopPropagation();openShareModalFor('+j.id+')">Udostępnij</button>'
        + '<button class="mfc-a" data-action="mfPrint" data-id="'+j.id+'" title="Wyślij do druku">Druk</button>'
        + '<button class="mfc-a dgr" onclick="event.stopPropagation(); if(confirm(\'Usunąć ten plik?\')) deleteMyJob('+j.id+')">Usuń</button>'
        + '<label class="mfc-fld" style="margin-left:auto"><select onchange="mfMoveJob('+j.id+',this.value)" onclick="event.stopPropagation()" title="Przenieś do folderu">'+folderOpts+'</select></label>'
        + '</div>'
        + '<button class="mfc-a" style="justify-content:center;width:100%" onclick="event.stopPropagation();showDownloadDialog(\''+j.uuid+'\',\''+(j.title||j.original_filename||'').replace(/'/g,"\\'")+'\')">↓ Pobierz</button>'
        + '<div style="display:flex;gap:6px;align-items:center;font-size:10.5px;color:var(--muted)"><span style="font-weight:700;text-transform:uppercase;letter-spacing:.08em">'+(j.mode||'hosting')+'</span><span style="font-family:var(--font-mono)">'+(j.status==='hosted'?'skopiuj link /s/…':(j.status==='done'?'STEP gotowy':'przetwarzanie…'))+'</span></div>'
        + '</div></div>';
    }).join('');
}
function mfResetFilters(){
    document.getElementById('mfSearch').value='';
    document.getElementById('mfFolderFilter').value='';
    if(typeof mfSetVis==='function') mfSetVis('');
    if(typeof renderFolderChips==='function'){try{renderFolderChips();}catch(e){}}
    mfRender();
}

function openShareModalFor(jobId){
    doShare(jobId);
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
            const h3=document.getElementById('myFilesEmpty').querySelector('h3');
            if(h3) h3.textContent = t('myFilesNoFiles') || 'Brak plików';
            const pe=document.getElementById('myFilesEmpty').querySelector('p');
            if(pe) pe.textContent = 'Wgraj plik STL / 3MF / OBJ, aby rozpocząć.';
            const cta=document.getElementById('myFilesEmpty').querySelector('button');
            if(cta) cta.style.display='none';
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
    var printBtn = document.getElementById('jobPrintOrderBtn');
    if (printBtn) {
        printBtn.style.display = '';
        printBtn.onclick = () => { if (typeof openPrintOrderModal === 'function') { openPrintOrderModal({ job_id: j.id, uuid: j.uuid, title: j.original_filename || j.filename }); } else { window.open('/zamow?job=' + encodeURIComponent(j.uuid), '_blank'); } };
    }
    shareBtn.onclick = () => doShare(j.id);
    delBtn.onclick = () => deleteMyJob(j.id);
    const heroSection = document.getElementById('jobPreviewHero');
    const heroImg = document.getElementById('jobPreviewHeroImg');
    const jp = '/api/thumb/' + j.uuid + '?v=3';
    heroImg.src = jp;
    // JPG hero = fallback only (shown by showJobModalErr when 3D fails).
    heroSection.style.display = 'none';
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
        if (d.cached) {
            window.open('/api/download/' + uuid + '?format=step', '_blank');
            toast('STEP gotowy (' + d.step_size_kb + ' KB)');
        } else if (d.queued) {
            dlStep.textContent = 'W kolejce' + (d.queue_position ? ' #' + d.queue_position : '') + '…';
            if (d.notify) toast('Dam znać mailem jak STEP będzie gotowy');
            const t0 = Date.now();
            while (Date.now() - t0 < 10 * 60 * 1000) {
                await new Promise(function(res){ setTimeout(res, 3000); });
                const rs = await fetch('/api/jobs/' + uuid + '/conv-status');
                if (!rs.ok) break;
                const st = await rs.json();
                if (st.status === 'done') {
                    dlStep.textContent = 'Gotowe! Pobieranie...';
                    setTimeout(() => { window.open('/api/download/' + uuid + '?format=step', '_blank'); }, 300);
                    toast('STEP gotowy (' + st.step_size_kb + ' KB)');
                    break;
                }
                if (st.status === 'error') throw new Error('Konwersja nieudana');
                dlStep.textContent = st.status === 'converting' ? 'Konwertowanie…' : ('W kolejce' + (st.queue_position ? ' #' + st.queue_position : '') + '…');
            }
        } else {
            dlStep.textContent = 'Gotowe! Pobieranie...';
            setTimeout(() => { window.open('/api/download/' + uuid + '?format=step', '_blank'); }, 300);
            dlStep.textContent = 'Pobierz STEP';
            toast('STEP gotowy (' + d.step_size_kb + ' KB, ' + d.time_s + 's)');
        }
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
    if (c) { c.innerHTML = ''; }
    // Reset JPG hero fallback
    const heroSection = document.getElementById('jobPreviewHero');
    if (heroSection) heroSection.style.display = 'none';
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
    const dl2 = new THREE.DirectionalLight(0xdfe5f0, 0.35); dl2.position.set(-1,0.5,-1); _fsScene.add(dl2);
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
    const mat = new THREE.MeshPhongMaterial({ color: 0xc9ced6, specular: 0x8a94a6, shininess: 28 });
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
    if (c) c.innerHTML = '';
    // Fallback: JPG hero when 3D fails.
    const heroSection = document.getElementById('jobPreviewHero');
    if (heroSection) heroSection.style.display = 'block';
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
            setTimeout(function(){ renderer.setSize(Math.min(container.clientWidth || w, 1200), h); }, 100);
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
                const mat = new T.MeshPhongMaterial({ color: 0xc9ced6, specular: 0x8a94a6, shininess: 28 });
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
        _edJobId = j.uuid;

        document.getElementById('edTitle').value = j.title || j.filename || '';
        document.getElementById('edTags').value = (Array.isArray(j.tags) ? j.tags : String(j.tags || '').split(',').map(function(s){return s.trim();}).filter(Boolean)).join(', ');
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

    function fmtErr(d){ if(!d) return ''; if(typeof d==='string') return d; if(Array.isArray(d)) return d.map(function(x){ return x.msg || x.message || JSON.stringify(x); }).join('; '); try{ return JSON.stringify(d); }catch(e){ return 'Error'; } }
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
            if (!r.ok) { const e = await r.json().catch(function(){return{}}); throw new Error(fmtErr(e.detail) || 'Error'); }
            // update local data
            const j = _myJobsData.find(function(x) { return x.uuid === _edJobId; });
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
                const r = await fetch('/api/jobs/' + _edJobId + '/images', {
                    method: 'POST',
                    headers: token ? {'Authorization': 'Bearer ' + token} : {},
                    body: fd
                });
                if (!r.ok) continue;
                const d = await r.json();
                const url = d.url || d.image_url || '';
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
async function publishToDiscover(jobId, btn){
    try{
        const r = await fetch('/api/jobs/' + jobId + '/publish', {method:'PATCH', headers:{'Authorization':'Bearer '+token,'Content-Type':'application/json'}, body:JSON.stringify({visibility:'public'})});
        if(!r.ok) throw new Error('Error ' + r.status);
        if(btn){ btn.textContent = '✓ ' + t('published'); btn.disabled = true; }
        toast(t('published'), 'success');
        if (typeof loadMyJobs === 'function') { try { loadMyJobs(); } catch(_){} }
    }catch(e){ toast(t('resultError', {msg: e.message}), 'error'); }
}
window.publishToDiscover = publishToDiscover;
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
async function edFormat(cmd) {
    const ta = document.getElementById('edDesc');
    const sel = ta.selectionStart;
    const val = ta.value;
    let ins = '';
    if (cmd === 'bold') ins = '**' + (val.slice(sel-1, sel) || '') + '**';
    else if (cmd === 'italic') ins = '*' + (val.slice(sel-1, sel) || '') + '*';
    else if (cmd === 'heading') ins = '\n# ';
    else if (cmd === 'link') {
        const url = prompt('Adres URL'); if (!url) return;
        const txt = prompt('Tekst linku'); ins = '[' + (txt || '') + '](' + url + ')';
    } else if (cmd === 'bullet') ins = '\n- ';
    else if (cmd === 'image') {
        const url = prompt('Adres obrazka'); if (!url) return;
        ins = '![](' + url + ')';
    }
    if (ins) {
        ta.value = val.slice(0, sel) + ins + val.slice(sel);
        ta.dispatchEvent(new Event('input'));
    }
}
async function edImageBtn() {
    const url = prompt('Adres obrazka'); if (!url) return;
    const ins = '![](' + url + ')\n';
    const ta = document.getElementById('edDesc');
    ta.value = ta.value.slice(0, ta.selectionStart) + ins + ta.value.slice(ta.selectionStart);
    ta.dispatchEvent(new Event('input'));
}
window.edFormat = edFormat;
window.edImageBtn = edImageBtn;
window.edUploadImages = edUploadImages;

window.showDownloadDialog = showDownloadDialog;
window.showEmbedDialog = doEmbed;
window.copyEmbedCode = copyEmbedCode;

let _expiryTimer=null;
function startExpiryCountdown(token){
    const el=document.getElementById('shareExpiryInfo');
    if(!el||!token) return;
    if(_expiryTimer) clearInterval(_expiryTimer);
    async function tick(){
        try{
            const r=await fetch('/api/share/'+token+'/status');
            if(!r.ok) return;
            const d=await r.json();
            if(!d.expires_at){ return; }
            const ms=new Date(d.expires_at).getTime()-Date.now();
            if(isNaN(ms)) return;
            if(ms<=0){ el.innerHTML='⛔ Link wygasł.'; clearInterval(_expiryTimer); return; }
            const h=Math.floor(ms/36e5), m=Math.floor(ms%36e5/6e4);
            el.innerHTML='⏳ Link ważny jeszcze: <b>'+(ms>864e5?(Math.floor(ms/864e5)+'d '+h%24+'h'):(h+'h '+m+'m'))+'</b>';
        }catch(e){}
    }
    tick(); _expiryTimer=setInterval(tick,60000);
}
window.startExpiryCountdown=startExpiryCountdown;
async function deleteAllMyFiles(){
    try{
        const r=await fetch('/api/account/files',{method:'DELETE',headers:{'Authorization':'Bearer '+token}});
        const d=await r.json().catch(()=>({}));
        if(r.ok){ alert('Usunięto '+(d.deleted||0)+' plików.'); loadMyJobs(); loadQuota && loadQuota(); }
        else alert('Błąd: '+(d.detail||r.status));
    }catch(e){ alert('Błąd: '+e.message); }
}
async function deleteMyAccount(){
    try{
        const r=await fetch('/api/account',{method:'DELETE',headers:{'Authorization':'Bearer '+token}});
        if(r.ok){ logout(); }
        else { const d=await r.json().catch(()=>({})); alert('Błąd: '+(d.detail||r.status)); }
    }catch(e){ alert('Błąd: '+e.message); }
}
window.deleteAllMyFiles=deleteAllMyFiles;
window.deleteMyAccount=deleteMyAccount;
async function logoutEverywhere(){
    try{
        const r=await fetch('/api/auth/logout-all',{method:'POST',headers:{'Authorization':'Bearer '+token}});
        if(r.ok){ logout(); }
        else { const d=await r.json().catch(()=>({})); alert('Błąd: '+(d.detail||r.status)); }
    }catch(e){ alert('Błąd: '+e.message); }
}
window.logoutEverywhere=logoutEverywhere;


// mfPrint: open print order modal for a stored job (data-action button)
window.addEventListener('click', function(e){
  var btn = e.target.closest ? e.target.closest('[data-action]') : null;
  if (btn && btn.dataset && btn.dataset.action === 'mfPrint') {
    var id = parseInt(btn.dataset.id, 10);
    var jobs = window.__mfJobs || [];
    var j = null;
    for (var i=0;i<jobs.length;i++){ if ((jobs[i].id===id)||(jobs[i].id+''===btn.dataset.id)){ j=jobs[i]; break; } }
    if (typeof window.openPrintOrderModal === 'function') {
          window.openPrintOrderModal({ job_id: j ? j.id : id, uuid: j ? j.uuid : '', title: j ? (j.original_filename || j.title || j.filename || '') : '' });
        } else {
          // redirect to /zamow with the job's uuid so order.html loads it into the cart
          var target = '/zamow?job=' + encodeURIComponent(j ? j.uuid : btn.dataset.id);
          window.location.href = target;
        }
  }
});
window.mfSetVis = mfSetVis;
window.mfSetSort = mfSetSort;
window.mfResetFilters = mfResetFilters;
window.mfRender = mfRender;
window.openShareModalFor = openShareModalFor;
