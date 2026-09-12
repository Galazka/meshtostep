// cadviewer.js — client-side STEP parsing via occt-import-js (WASM).
// Lazy load on demand: only when user opens STEP share page.
// Fallback: server stl-preview if WASM fails.
'use strict';

let _occtModule = null;

async function loadOcct() {
  if (_occtModule) return _occtModule;
  const script = document.createElement('script');
  script.type = 'module';
  document.head.appendChild(script);
  // import occt-import-js from CDN
  const m = await import('https://cdn.jsdelivr.net/npm/occt-import-js@0.0.23/dist/occt-import-js.js');
  _occtModule = await m.default({
    locateFile: (p) => 'https://cdn.jsdelivr.net/npm/occt-import-js@0.0.23/dist/' + p
  });
  return _occtModule;
}

/**
 * Parse STEP ArrayBuffer -> Three.js BufferGeometry via OCCT triangulation.
 * Returns null on failure (caller falls back to server preview).
 */
window.loadStepWithOcct = async function(arrayBuffer) {
  try {
    const occt = await loadOcct();
    const result = occt.ReadStepFile(new Uint8Array(arrayBuffer), null);
    if (!result || !result.success) return null;
    // concatenate all face meshes
    const meshes = result.meshes || [];
    if (!meshes.length) return null;
    const positions = [];
    const normals = [];
    meshes.forEach(function(m) {
      const pos = m.attributes.position.array;
      const norm = m.attributes.normal.array;
      for (let i = 0; i < pos.length; i++) {
        positions.push(pos[i]);
        normals.push(norm[i]);
      }
    });
    return { positions: new Float32Array(positions), normals: new Float32Array(normals) };
  } catch (e) {
    console.error('OCCT load failed:', e);
    return null;
  }
};
