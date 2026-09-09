// discover.js — doDiscover, tags, search (verbatim, self-initializing).

let discoverOffset = 0;
let _activeTag = '';
function doDiscover(more){
    if(!more) discoverOffset = 0;
    const q = document.getElementById('discoverQ').value || '';
    const sort = document.getElementById('discoverSort').value || 'latest';
    const params = new URLSearchParams({q: q, sort: sort, offset: discoverOffset, limit: 24});
    if(_activeTag) params.set('tag', _activeTag);
    const grid = document.getElementById('discoverGrid');
    if(!more) grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;color:var(--text-muted);padding:24px">Ładowanie...</div>';
    fetch('/api/models?'+params.toString()).then(function(r){
        if(!r.ok) throw 0;
        return r.json();
    }).then(function(d){
        var items = d.items || d || [];
        var html = items.map(function(m){
            var img = m.preview_image ? m.preview_image : (m.uuid ? '/api/thumb/'+m.uuid : '');
            return '<a href="'+(m.vanity||'/s/'+m.uuid)+'" style="display:block;border:1px solid var(--border);border-radius:10px;overflow:hidden;text-decoration:none;color:inherit;background:#fff">'
            + (img ? '<img src="'+img+'" style="width:100%;height:140px;object-fit:cover" onerror="this.style.display=\'none\'">' : '<div style="height:140px;background:var(--bg-alt);display:flex;align-items:center;justify-content:center;color:var(--text-muted)">\uD83D\uDCC4</div>')
            + '<div style="padding:10px 12px"><div style="font-weight:600;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'+String(m.title||m.slug||'Model').replace(/</g,'&lt;')+'</div>'
            + '<div style="font-size:11px;color:var(--text-muted)">'+(m.username?'by '+String(m.username).replace(/</g,'&lt;')+' \u00b7 ':'')+(m.faces||'?')+' \u015b\u0105cian'+'</div></div></a>';
        }).join('');
        if(more) grid.innerHTML += html; else grid.innerHTML = html || '<div style="grid-column:1/-1;text-align:center;color:var(--text-muted);padding:24px">Brak wynik\u00f3w</div>';
        document.getElementById('discoverMore').style.display = (items.length >= 24) ? 'block' : 'none';
        updateTagHighlight();
    }).catch(function(e){
        if(!more) grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;color:var(--text-muted);padding:24px">B\u0142\u0105d wyszukiwania</div>';
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
    if(label) label.textContent = _activeTag ? 'Tag: '+_activeTag+'  \u2715' : '';
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
            html += '<button class="tag-chip" data-tag="'+String(name).replace(/"/g,'&quot;')+'" onclick="setTag(\''+String(name).replace(/'/g,"\'")+'\')" style="padding:6px 14px;border:1px solid var(--border);border-radius:999px;background:#fff;font-size:12px;cursor:pointer;color:var(--text-secondary);transition:all .15s">'+String(name).replace(/</g,'&lt;')+'</button>';
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
