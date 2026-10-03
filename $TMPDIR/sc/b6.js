
import { initViewerPro } from '/asset/viewer_pro.js?v=15';
/* Podglad w koszyku = ten sam pelny konfigurator co wszedzie: toolbar
   (obrot/siatka/krawedzie/podloga/tlo/zoom/PNG/fullscreen) na scianie z konturem. */
window.__local3d = {
  renderBytes: function(filename, bytes, boxId){
    var box = document.getElementById(boxId || 'previewBox');
    if (!box) return;
    if (!box.__pro) {
      // NIE czyscimy boxa — canvas trzyma WebGL context, a wyczyszczenie
      // go odlacza od DOM i viewer ginie na zawsze (pusty podglad od 2 pliku)
      box.style.minHeight = '420px';
      box.__pro = initViewerPro({
        container: box, stlUrl: '',
        lang: document.documentElement.lang || 'pl',
        toolbar: true, printBar: false, grid: true
      });
    }
    var ab = (bytes instanceof ArrayBuffer) ? bytes : bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
    box.__pro.loadBytes(filename || 'model.stl', ab);
    window.__viewerPro = box.__pro;
  }
};
