"""Convert STL to STEP using FreeCAD headless.
Reads paths/settings from env vars:
  FC_SRC, FC_DST, FC_TOL, FC_MODE, FC_FACES, FC_SMOOTH
Modes:
  off    - no decimation, straight convert
  light  - mergeFacets only
  auto   - mergeFacets + decimate (default 1000)
  ultra  - mergeFacets + decimate (500)
  smooth - Taubin smoothing + decimate (for decorative models)
  s+auto - Taubin + mergeFacets + decimate (1000)
Pipeline: smooth? -> decimate -> makeShapeFromMesh -> makeSolid -> removeSplitter -> exportStep
"""
import os
import numpy as np
import FreeCAD as App
import Mesh
import Part

MODE = os.environ.get("FC_MODE", "auto")
FC_FACES = int(os.environ.get("FC_FACES", "1000"))
FC_SMOOTH = int(os.environ.get("FC_SMOOTH", "3"))  # Taubin iterations
LAMBDA_S = 0.4   # push
MU_S = -0.42     # pull-back (volume preserving)

def taubin_smooth(points, faces, iters=3, lam=0.4, mu=-0.42):
    """Taubin low-pass: volume-preserving smoothing on mesh vertices."""
    # Build vertex adjacency from faces
    adj = {}
    for f in faces:
        for i in range(3):
            a, b = int(f[i]), int(f[(i+1)%3])
            adj.setdefault(a, set()).add(b)
            adj.setdefault(b, set()).add(a)
    pts = points.copy()
    for _ in range(iters):
        # Lambda step
        nv = pts.copy()
        for i in range(len(pts)):
            nb = list(adj.get(i, []))
            if nb:
                nv[i] = pts[i] + lam * (pts[nb].mean(axis=0) - pts[i])
        pts = nv
        # Mu step
        nv = pts.copy()
        for i in range(len(pts)):
            nb = list(adj.get(i, []))
            if nb:
                nv[i] = pts[i] + mu * (pts[nb].mean(axis=0) - pts[i])
        pts = nv
    return pts

def preprocess(mesh):
    before = mesh.CountFacets
    pts, fac = mesh.Topology
    points = np.array([[p.x, p.y, p.z] for p in pts])
    faces_arr = np.array([[f[0], f[1], f[2]] for f in fac])

    do_smooth = "smooth" in MODE or "s+" in MODE
    if do_smooth:
        print("Taubin smooth: %d iterations" % FC_SMOOTH)
        points = taubin_smooth(points, faces_arr, iters=FC_SMOOTH,
                               lam=LAMBDA_S, mu=MU_S)
        print("  vertices shifted")

    if MODE == "off":
        print("decimation: OFF")
        return mesh

    if MODE == "light":
        try:
            mesh.mergeFacets()
            print("decimation: light mergeFacets %d -> %d" % (before, mesh.CountFacets))
        except Exception as e:
            print("mergeFacets fail: %s" % str(e)[:80])
        return mesh

    # auto / ultra / smooth / s+auto: mergeFacets + decimate
    target = 500 if MODE == "ultra" else FC_FACES

    if do_smooth:
        # Rebuild mesh with smoothed vertices using correct addFacets format
        import FreeCAD as FC
        fc_pts = [FC.Vector(float(p[0]), float(p[1]), float(p[2])) for p in points]
        fc_faces = [(int(f[0]), int(f[1]), int(f[2])) for f in faces_arr]
        smooth_mesh = Mesh.Mesh()
        smooth_mesh.addFacets((fc_pts, fc_faces))
        mesh = smooth_mesh
        print("smoothed mesh built: %d pts, %d faces" % (mesh.CountPoints, mesh.CountFacets))

    try:
        mesh.mergeFacets()
        merged = mesh.CountFacets
    except Exception as e:
        print("mergeFacets fail: %s" % str(e)[:80])
        merged = before
    try:
        mesh.decimate(target)
        print("decimation: %s mesh %d -> %d -> decimate(%d) -> %d faces" % (
            MODE, before, merged, target, mesh.CountFacets))
    except Exception as e:
        print("decimate fail: %s" % str(e)[:80])
    return mesh

def convert(stl_path, step_path, tolerance=0.1):
    doc = App.newDocument("Conv")
    mesh = Mesh.Mesh(stl_path)
    print("Loaded: %d pts, %d faces" % (mesh.CountPoints, mesh.CountFacets))
    mesh = preprocess(mesh)
    shape = Part.Shape()
    shape.makeShapeFromMesh(mesh.Topology, tolerance)
    print("Shape: %s, valid=%s" % (shape.ShapeType, shape.isValid()))
    solid = Part.makeSolid(shape)
    print("Solid: %s, valid=%s" % (solid.ShapeType, solid.isValid()))
    refined = solid.removeSplitter()
    print("Refined: %s, %d faces, valid=%s" % (refined.ShapeType, len(refined.Faces), refined.isValid()))
    refined.exportStep(step_path)
    print("Exported: " + step_path)
    App.closeDocument("Conv")
    return True

_src = os.environ.get("FC_SRC", "")
_dst = os.environ.get("FC_DST", "")
_tol = float(os.environ.get("FC_TOL", "0.1"))

if not _src or not _dst:
    print("FC_SRC / FC_DST env vars required")
else:
    ok = convert(_src, _dst, _tol)
    print("OK" if ok else "FAIL")
