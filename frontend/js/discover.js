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
        var html = items.map(function(m){
            var img = m.preview_url ? m.preview_url : (m.uuid ? '/api/thumb/'+m.uuid : '');
            var title = m.title || m.slug || 'Model';
            var safeTitle = String(title).replace(/</g,'&lt;');
            var safeUser = String(m.username||'').replace(/</g,'&lt;');
            var safeUuid = String(m.uuid||'').replace(/'/g, "&#39;");
            var safeTitleAttr = String(title).replace(/'/g, "&#39;");
            return ''
            + '<a href="'+(m.vanity||'/s/'+m.uuid)+'" style="display:block;border:1px solid var(--border);border-radius:10px;overflow:hidden;text-decoration:none;color:inherit;background:#fff;position:relative">'
            + '<button onclick="sendToPrinter(event,'+m.job_id+',\''+safeUuid+'\',\''+safeTitleAttr+'\')" title="Wyślij do drukarni" style="position:absolute;top:6px;right:6px;background:#2563eb;color:#fff;border:none;border-radius:6px;padding:4px 8px;font-size:11px;cursor:pointer;width:24px;height:24px;display:flex;align-items:center;justify-content:center">🖨</button>'
            + (img ? '<img src="'+img+'" style="width:100%;height:140px;object-fit:cover" onerror="this.style.display=\'none\'">' : '<div style="height:140px;background:var(--bg-alt);display:flex;align-items:center;justify-content:center;color:var(--text-muted)">📄</div>')
            + '<div style="padding:10px 12px"><div style="font-weight:600;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'+safeTitle+'</div>'
            + '<div style="font-size:11px;color:var(--text-muted)">'+(m.username?'by '+safeUser+' · ':'')+(m.faces||'?')+' śącian'+'</div></div></a>';
        }).join('');
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
          openPrintOrderModal({ job_id: jobId, uuid: uuid, title: title, volume_cm3: est.volume_cm3, dims_mm: est.dimensions });
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
