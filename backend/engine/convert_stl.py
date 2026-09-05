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
Pipeline: smooth? -> decimate -> makeShapeFromMesh -> makeSolid? -> removeSplitter? -> exportStep
Fallback: if makeSolid fails, try exportShape directly from shape/shell.
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

def convert(src_path, step_path, tolerance=0.1):
    import Part
    doc = App.newDocument("Conv")

    # Mesh.read() handles STL, 3MF, OBJ; Mesh.Mesh() only handles STL
    mesh = Mesh.Mesh()
    mesh.read(src_path)
    print("Loaded: %d pts, %d faces" % (mesh.CountPoints, mesh.CountFacets))
    mesh = preprocess(mesh)

    # Try higher tolerance for non-watertight meshes
    tol = max(tolerance, 0.1)
    shape = Part.Shape()
    shape.makeShapeFromMesh(mesh.Topology, tol)
    print("Shape: %s, valid=%s, closed=%s" % (shape.ShapeType, shape.isValid(), shape.isClosed()))

    # Strategy 1: makeSolid -> removeSplitter -> exportStep
    try:
        solid = Part.makeSolid(shape)
        print("Solid: %s, valid=%s" % (solid.ShapeType, solid.isValid()))
        if solid.isValid() and solid.ShapeType == "Solid":
            refined = solid.removeSplitter()
            print("Refined: %s, %d faces, valid=%s" % (refined.ShapeType, len(refined.Faces), refined.isValid()))
            refined.exportStep(step_path)
            print("Exported: " + step_path)
            App.closeDocument("Conv")
            return True
    except Exception as e:
        print("makeSolid/removeSplitter failed: %s" % str(e)[:200])

    # Strategy 2: try exportStep directly on shape (if it has solids/compsolids)
    try:
        shape.exportStep(step_path)
        print("Exported via shape.exportStep: " + step_path)
        App.closeDocument("Conv")
        return True
    except Exception as e:
        print("shape.exportStep failed: %s" % str(e)[:200])

    # Strategy 3: try to build a shell from faces and export
    try:
        faces = shape.Faces
        if len(faces) > 0:
            shell = Part.makeShell(faces)
            print("Shell: %d faces, valid=%s" % (len(shell.Faces), shell.isValid()))
            shell.exportStep(step_path)
            print("Exported via shell: " + step_path)
            App.closeDocument("Conv")
            return True
    except Exception as e:
        print("shell export failed: %s" % str(e)[:200])

    # Strategy 4: try with higher tolerance
    try:
        shape2 = Part.Shape()
        shape2.makeShapeFromMesh(mesh.Topology, 0.5)
        solid2 = Part.makeSolid(shape2)
        if solid2.isValid():
            solid2.exportStep(step_path)
            print("Exported via high-tolerance: " + step_path)
            App.closeDocument("Conv")
            return True
    except Exception as e:
        print("high-tolerance fallback failed: %s" % str(e)[:200])

    # Strategy 5: export as raw STEP from shape
    try:
        Part.export([shape], step_path)
        print("Exported via Part.export: " + step_path)
        App.closeDocument("Conv")
        return True
    except Exception as e:
        print("Part.export failed: %s" % str(e)[:200])

    print("ALL STRATEGIES FAILED - mesh may be non-manifold or degenerate")
    App.closeDocument("Conv")
    return False

_src = os.environ.get("FC_SRC", "")
_dst = os.environ.get("FC_DST", "")
_tol = float(os.environ.get("FC_TOL", "0.1"))

if not _src or not _dst:
    print("FC_SRC / FC_DST env vars required")
else:
    ok = convert(_src, _dst, _tol)
    print("OK" if ok else "FAIL")
