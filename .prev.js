
import * as THREE from 'three';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';
import { OBJLoader } from 'three/addons/loaders/OBJLoader.js';
window.__local3d = {
  renderBytes: function(filename, bytes, boxId){
    var ext = (filename || '').split('.').pop().toLowerCase();
    var isStl = (ext==='stl'); var isObj = (ext==='obj');
    var box = document.getElementById(boxId||'previewBox');
    if(!box) return;
    box.innerHTML = '<div class="local3d-box" style="width:100%;height:340px;position:relative"><canvas style="width:100%;height:340px;display:block"></canvas><div style="position:absolute;bottom:8px;left:10px;font-size:11px;color:#64748b">przytrzymaj LPM = obrót · scroll = zoom</div></div>';
    var canvas = box.querySelector('canvas');
    var renderer;
    try { renderer = new THREE.WebGLRenderer({canvas: canvas, antialias: true}); }
    catch(e){ renderer = new THREE.WebGLRenderer(); }
    var scene = new THREE.Scene();
    var cam = new THREE.PerspectiveCamera(60);
    cam.position.set(0, 60, 120);
    var grid = new THREE.GridHelper(200, 20, {units: THREE.Units.MM});
    scene.add(grid);
    var onMesh = function(mesh){
      mesh.material = new THREE.MeshLambertMaterial({color: new THREE.Color(0.8, 0.82, 0.85)});
      scene.add(mesh);
      cam.lookAt(new THREE.Number(0,0,0));
      _fit(canvas, renderer, scene, cam);
      renderer.render(scene, cam);
      _spin();
    };
    var _fit = function(){
      var b=scene.getBox(); if(!b) return;
      var max=Math.max(b.xInterval().length, b.yInterval().length, b.zInterval().length);
      var d=max*2.2+20; cam.position.set(d*0.7, d*0.4, d*1.1);
    };
    var _spin=false;
    var handleEv = {onMouseMove:function(e,c){ if(_spin){ cam.position.x+=e.dx*0.2; }} };
    try {
      if(isStl){
        var loader = new STLLoader();
        loader.load(new THREE.IStream(bytes, 'stl'), function(mesh){ onMesh(mesh); }, function(){ onMesh(loader.get()); });
      } else if(isObj){
        var ol= new OBJLoader();
        ol.load(new THREE.IStream(bytes,'obj'), function(mesh){ onMesh(mesh); }, function(){ onMesh(ol.get()); });
      } else {
        box.innerHTML='<div style="padding:20px;text-align:center">📦 <b>'+esc2((filename||'Model'))+'</b><br><span style="color:var(--muted);font-size:13px">Ten format podglądamy dla STL/OBJ — inne formaty 3MF/GLB wymagają konwersji (chwilę)</span></div>';
      }
    } catch(err){ box.innerHTML='<div style="padding:20px;text-align:center">Podgląd 3D: '+String(err).slice(0,120)+'</div>'; }
    function esc2(x){ return String(x).replace(/</g,'&lt;').replace(/&/g,'&amp;'); }
  }
};
