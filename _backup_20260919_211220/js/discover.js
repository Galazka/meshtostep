// discover.js — doDiscover, tags, search (verbatim, self-initializing).

let discoverOffset = 0;
let _activeTag = '';
let _currentModels = [];

function doDiscover(more){
    if(!more) discoverOffset = 0;
    const q = document.getElementById('discoverQ').value || '';
    const sort = document.getElementById('discoverSort').value || 'latest';
    const params = new URLSearchParams({q: q, sort: sort, offset: discoverOffset, limit: 24});
    if(_activeTag) params.set('tag', _activeTag);
    const grid = document.getElementById('discoverGrid');
    if(!more) grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;color:var(--text-muted);padding:24px">Ładowanie…</div>';
    fetch('/api/models?'+params.toString()).then(function(r){
        if(!r.ok) throw 0;
        return r.json();
    }).then(function(d){
        var items = d.items || d || [];
        _currentModels = items;
        
        /* Profesjonalna karta modelu (prt-model-card) z metrykami */
        function _relTime(iso){
          try{
            var t=(new Date(iso)).getTime ? new Date(iso).getTime() : Date.parse(iso);
            var d=((Date.now()-t)/1000); if(d<0)d=0;
            if(d<60)return 'przed chwilą'; d/=60;
            if(d<60)return Math.floor(d)+' min temu'; d/=60;
            if(d<24)return Math.floor(d)+' h temu'; d/=24;
            if(d<30)return Math.floor(d)+' dni temu'; d/=30;
            if(d<12)return Math.floor(d)+' mies. temu';
            return Math.floor(d/12)+' lat temu';
          }catch(e){ return ''; }
        }
        function _fmtDims(mm){
          try{ if(!mm)return ''; var s=String(mm).replace(/[\[\]()]/g,'').split(/[,x X\s]+/).map(Number).filter(Boolean);
            if(!s.length)return '';
            var mm2=s.map(function(n){return Math.round(n*10)/10;});
            return mm2.join(' × ');
          }catch(e){ return ''; }
        }
        function _cardTag(t){ var safe=String(t||'').replace(/</g,'&lt;'); return '<span class="prt-model-card-tag">'+safe+'</span>'; }
        var html = items.map(function(m){
            var img = m.preview_url ? m.preview_url : (m.uuid ? '/api/thumb/'+m.uuid : '');
            var title = m.title || m.slug || 'Model';
            var safeTitle = String(title).replace(/</g,'&lt;');
            var safeUser = String(m.username||'anonim').replace(/</g,'&lt;');
            var safeUuid = String(m.uuid||'').replace(/'/g, "&#39;");
            var safeTitleAttr = String(title).replace(/'/g, "&#39;");
            var vw = m.views ? '<span class="pm-m">👁 <b>'+(m.views>999?(Math.round(m.views/100)/10)+'k':m.views)+'</b></span>' : '';
            var lk = m.likes ? '<span class="pm-m">👍 <b>'+m.likes+'</b></span>' : '';
            var fc = m.faces ? '<span class="pm-m">◍ <b>'+m.faces+'</b></span>' : '';
            var dm = _fmtDims(m.dims_mm);
            var tg = (m.tags && m.tags.length) ? m.tags.slice(0,4).map(_cardTag).join('') : '';
            var rt = _relTime(m.created_at);
            return ''
            + '<a href="'+(m.vanity||'/s/'+m.uuid)+'" class="prt-model-card" data-uuid="'+safeUuid+'">'
            + '<button class="prt-print-btn" onclick="sendToPrinter(event,'+m.job_id+',\''+safeUuid+'\',\''+safeTitleAttr+'\')" title="Wyślij do drukarni" aria-label="Drukuj">🖨</button>'
            + (img ? '<img class="pm-thumb" src="'+img+'" loading="lazy" onerror="this.remove()">' : '<div class="pm-thumb" style="aspect-ratio:16/10;background:var(--bg-blue);display:grid;place-items:center;color:var(--accent);font-size:26px">⬡</div>')
            + '<div class="pm-body">'
            +   '<div class="pm-title">'+safeTitle+'</div>'
            +   (tg? '<div class="pm-tags">'+tg+'</div>':'')
            +   (!dm && !rt ? '' : '<div class="pm-meta-line">'+ (dm?'<span class="pm-m">📐 <b>'+dm+'</b></span>':'') + (rt?'<span class="pm-m">🕒 '+rt+'</span>':'') +'</div>')
            +   '<div class="pm-meta"><span class="pm-author">👤 '+safeUser+'</span>'+ vw + lk + fc +'</div>'
            + '</div></a>';
        }).join('');
        if(more) grid.innerHTML += html; else
if(more) grid.innerHTML += html; else grid.innerHTML = html || '<div style="grid-column:1/-1;text-align:center;color:var(--text-muted);padding:24px">Brak wyników</div>';
        document.getElementById('discoverMore').style.display = (items.length >= 24) ? 'block' : 'none';
        updateTagHighlight();
    }).catch(function(e){
        if(!more) grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;color:var(--text-muted);padding:24px">Błąd wyszukiwania</div>';
    });
}
function setTag(tag){
    _activeTag = (_activeTag === tag) ? '' : tag;
    var inp = document.getElementById('discoverQ');
    if(inp && !_activeTag) inp.value = '';
    updateTagHighlight();
    doDiscover();
}
function updateTagHighlight(){
    document.querySelectorAll('#discoverTags .tag-chip').forEach(function(b){
        b.style.background = (b.dataset.tag === _activeTag) ? 'var(--primary)' : '#fff';
        b.style.color = (b.dataset.tag === _activeTag) ? '#fff' : 'var(--text-secondary)';
        b.style.borderColor = (b.dataset.tag === _activeTag) ? 'var(--primary)' : 'var(--border)';
    });
    var label = document.getElementById('activeTagLabel');
    if(label) label.textContent = _activeTag ? 'Tag: '+_activeTag+'  ×' : '';
}
function clearTag(){ _activeTag=''; updateTagHighlight(); doDiscover(); }
async function loadPopularTags(){
    try{
        var r = await fetch('/api/tags');
        if(!r.ok) return;
        var tags = await r.json();
        var box = document.getElementById('discoverTags');
        if(!box || !tags || !tags.length) return;
        var html = '<button class="tag-chip" data-tag="" onclick="clearTag()" style="padding:6px 14px;border:1px solid var(--border);border-radius:999px;background:var(--primary);color:#fff;font-size:12px;cursor:pointer;font-weight:600">Wszystkie</button>';
        tags.forEach(function(tg){
            var name = typeof tg==='string' ? tg : (tg.name||tg.tag);
            var safe = String(name).replace(/</g,'&lt;');
            var sq = String(name).replace(/'/g, "\\'");
            html += '<a class="tag-chip" data-tag="'+String(name)+'" href="/tag/'+encodeURIComponent(String(name).toLowerCase())+'" onclick="setTag(&quot;'+sq+'&quot;);return false" style="padding:6px 14px;border:1px solid var(--border);border-radius:999px;background:#fff;font-size:12px;cursor:pointer;color:var(--text-secondary);transition:all .15s;text-decoration:none">'+safe+'</a>';
        });
        box.innerHTML = html;
    }catch(e){}
}

document.addEventListener('DOMContentLoaded', function(){ loadPopularTags(); });

function discoverMore() { discoverOffset += 24; doDiscover(true); }
export { doDiscover, discoverMore };
window.doDiscover = doDiscover;
window.discoverMore = discoverMore;
window.setTag = setTag;
window.clearTag = clearTag;
window.loadPopularTags = loadPopularTags;
window.discoverMore = discoverMore;

window.escapeAttr = function(s){ return String(s||'').replace(/'/g, "&#39;").replace(/"/g,'&quot;'); };

window.sendToPrinter = async function(e, jobId, uuid, title) {
    e.preventDefault();
    e.stopPropagation();
    var btn = e.currentTarget;
    btn.disabled = true;
    btn.textContent = '🔄';
    try {
      // Fetch source STL for auto-estimate
      var r = await fetch('/download/' + encodeURIComponent(uuid) + '?format=stl&t=' + Date.now());
      if (r.ok) {
        var blob = await r.blob();
        var fd = new FormData();
        fd.append('file', blob, 'model.stl');
        fd.append('material', 'PLA');
        fd.append('mode', 'auto');
        var estRes = await fetch('/api/estimate?v=' + Date.now(), { method: 'POST', body: fd });
        if (estRes.ok) {
          var est = await estRes.json();
          openPrintOrderModal({ job_id: jobId, uuid: uuid, title: title, volume_cm3: est.volume_cm3, dims_mm: est.dimensions, estimated_hours: est.print_hours, warnings: est.warnings });
        } else {
          openPrintOrderModal({ job_id: jobId, uuid: uuid, title: title });
        }
      } else {
        openPrintOrderModal({ job_id: jobId, uuid: uuid, title: title });
      }
    } catch (_) {
      openPrintOrderModal({ job_id: jobId, uuid: uuid, title: title });
    } finally {
      btn.disabled = false;
      btn.textContent = '🖨';
    }
};
