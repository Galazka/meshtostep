/* meshfmt.js — rozpoznawanie formatu siatki (STL / 3MF / OBJ / PLY / GLB).
   Problem: /api/stl-preview/<uuid> nie ma rozszerzenia w URL, wiec kod bral
   "ext" z UUID i wszystko parsowal jako STL -> 3MF/OBJ wygladaly jak obciete
   albo zepsute. Ten helper: (1) czyta naglowek X-Mesh-Ext z odpowiedzi,
   (2) sniffuje pierwsze bajty, (3) dopiero na koncu bierze rozszerzenie z URL. */
(function () {
  'use strict';

  function fromUrl(url) {
    try {
      var leaf = String(url || '').split('?')[0].split('#')[0].split('/').pop();
      var m = /\.([a-z0-9]{2,4})$/i.exec(leaf);
      return m ? m[1].toLowerCase() : '';
    } catch (e) { return ''; }
  }

  // Sniffing z ArrayBuffer — dziala bez naglowkow i bez rozszerzenia w URL.
  function sniff(buf) {
    try {
      if (!buf || !buf.byteLength) return '';
      var n = Math.min(2048, buf.byteLength);
      var b = new Uint8Array(buf, 0, n);
      // ZIP local file header -> 3MF (ZIP-based)
      if (b[0] === 0x50 && b[1] === 0x4b && (b[2] === 3 || b[2] === 5 || b[2] === 7)) return '3mf';
      // glTF binary magic "glTF"
      if (b[0] === 0x67 && b[1] === 0x6c && b[2] === 0x54 && b[3] === 0x46) return 'glb';
      var txt = '';
      for (var i = 0; i < n; i++) txt += String.fromCharCode(b[i]);
      var low = txt.toLowerCase();
      if (low.indexOf('ply') === 0) return 'ply';
      if (low.indexOf('facet normal') >= 0 || low.indexOf('solid ') === 0) return 'stl';
      if (low.indexOf('\nv ') >= 0 || low.indexOf('\nf ') >= 0 ||
          /^\s*(vn|vt)\s/.test(low) || low.indexOf('# ') === 0) return 'obj';
      // Binarny STL: brak sygnatury tekstowej, ale rozmiar = 84 + n*50 dokladnie.
      if (buf.byteLength >= 84) {
        var cnt = new DataView(buf).getUint32(80, true);
        if (84 + cnt * 50 === buf.byteLength) return 'stl';
      }
      // Domyslnie STL (binary bez zgodnego rozmiaru) — tak dziala reszta serwisu.
      return 'stl';
    } catch (e) { return ''; }
  }

  // Kolejnosc: byte-sniff > rozszerzenie z URL.
  function resolve(buf, url) {
    return sniff(buf) || fromUrl(url) || 'stl';
  }

  // Async: HEAD -> X-Mesh-Ext (naglowek z backendu), potem URL, potem 'stl'.
  function resolveAsync(url, cb) {
    var done = false;
    function finish(v) { if (!done) { done = true; cb(v || fromUrl(url) || 'stl'); } }
    try {
      fetch(url, { method: 'HEAD' })
        .then(function (h) {
          var hx = (h.headers.get('X-Mesh-Ext') || '').toLowerCase();
          finish(hx || fromUrl(url));
        })
        .catch(function () { finish(fromUrl(url)); });
    } catch (e) { finish(fromUrl(url)); }
    setTimeout(function () { finish(fromUrl(url)); }, 2500);
  }

  window.meshExtSync = function (buf, url) { return resolve(buf, url); };
  window.meshExtFromUrl = fromUrl;
  window.meshExtAsync = resolveAsync;
})();
