"""STL → volume/dims/time estimation via trimesh + FreeCAD headless.

K1: auto-volume from uploaded STL → feeds pricing engine.
  • light mode: trimesh only (fast, ~1s for 1M faces)
  • auto mode: trimesh volume → empirical time estimate
  • ultra mode: FreeCAD meshToShape (precise volume, ~5–15s)
No secrets / tokens stored on disk.
"""
from __future__ import annotations
import os, subprocess, json, tempfile, shutil, math, time as _time
from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, File, Form, UploadFile, status
from fastapi.responses import JSONResponse

try:
    import trimesh
    _HAS_TRIMESH = True
except ImportError:
    _HAS_TRIMESH = False

from .database import get_db
from .routes_order import calculate_price, _split_into_parts, estimate_print_time_hours, estimate_filament_grams

router = APIRouter()

FREECAD_CMD = os.environ.get("FREECAD_CMD", "/usr/bin/freecadcmd")
MAX_STL_MB = 25
DENSITY_PLA = 1.24  # g/cm³ — default material density
# empirical throughput mm³/s (PLA/PETG ~100), used for time estimate
THROUGHPUT_MM3_S = {
    "PLA": 100, "PLA HT": 100, "PLA CF": 70, "PLA Silk": 90, "PLA Matte": 80, "PLA Glow": 80,
    "PETG": 100, "PETG FR": 80, "ABS": 90, "ASA": 90, "ASA CF": 70,
    "TPU": 60, "TPU 75D": 50, "PA12": 80, "PA12 CF": 70, "PCTG": 85,
    "Iglidur I150PF": 60, "Iglidur I180PF": 55, "Iglidur I190PF": 50,
}


def _validate_upload(file: UploadFile) -> bytes:
    """Read STL bytes, enforce size limit."""
    raw = file.file.read()
    if len(raw) > MAX_STL_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large (max {MAX_STL_MB} MB)"
        )
    name = (file.filename or "").lower()
    if not (name.endswith(".stl") or name.endswith(".obj") or name.endswith(".ply")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .stl/.obj/.ply supported"
        )
    return raw


def _trimesh_stats(data: bytes, material: str = "PLA") -> dict:
    """Fast volume + dims from trimesh (no FreeCAD).

    Root fix: trimesh.load on BytesIO with file_type='stl' mis-detects binary
    STL as a Scene (0 verts). Writing to temp file + process=False +
    scene-to-mesh conversion + abs(volume) fixes binary + ASCII STL.
    """
    import trimesh

    # Write to temp file — trimesh auto-detects binary/ASCII from path
    fd, tmp_path = tempfile.mkstemp(suffix=".stl")
    try:
        os.write(fd, data)
        os.close(fd)
        obj = trimesh.load(tmp_path, process=False)
    finally:
        os.unlink(tmp_path)

    # Scene → Trimesh (concat all geometries)
    if not isinstance(obj, trimesh.Trimesh):
        if isinstance(obj, trimesh.Scene):
            geoms = list(obj.geometry.values())
            if geoms:
                obj = trimesh.util.concatenate([g.dump() for g in geoms])
    if not isinstance(obj, trimesh.Trimesh):
        # try dump+sum as last resort
        try:
            obj = obj.dump().sum()
        except Exception:
            raise HTTPException(status_code=500, detail="Could not parse mesh")

    obj.merge_vertices()
    try:
        obj.fix_normals()
    except Exception:
        pass

    # Detect if mesh is in mm (typical STL from CAD) vs meters (trimesh default)
    bb = obj.bounds
    if bb is not None and bb[1].max() > 1.0:
        # Coordinates likely in mm (typical CAD STL) → convert to meters
        obj.vertices *= 0.001
        bb = obj.bounds

    dims_m = (bb[1] - bb[0])
    dims_mm = [round(float(d) * 1000, 2) for d in dims_m]

    vol_m3 = abs(float(obj.volume)) if obj.volume else 0.0
    vol_cm3 = round(vol_m3 * 1e6, 3)

    density = DENSITY_PLA if material == "PLA" else 1.27
    grams = round(vol_cm3 * density, 2)

    vol_mm3 = vol_cm3 * 1000
    thr = THROUGHPUT_MM3_S.get(material, 100)
    hours = max(0.5, (vol_mm3 / thr) / 3600) + 0.5  # +0.5h overhead

    return {
        "volume_cm3": vol_cm3,
        "dimensions_mm": dims_mm,
        "dimensions": f"{dims_mm[0]}×{dims_mm[1]}×{dims_mm[2]} mm",
        "grams": grams,
        "faces": len(obj.faces) if hasattr(obj, "faces") else 0,
        "print_hours": round(hours, 2),
    }


def _freecad_volume(data: bytes, material: str = "PLA") -> dict:
    """Precise volume via FreeCAD meshToShape — ultra mode."""
    tmpdir = tempfile.mkdtemp()
    try:
        stl_path = os.path.join(tmpdir, "input.stl")
        with open(stl_path, "wb") as f:
            f.write(data)

        script = os.path.join(tmpdir, "calc.py")
        script_content = f'''
import FreeCAD, Mesh, Part, sys, json
doc = FreeCAD.newDocument("calc")
m = Mesh.Mesh("{stl_path}")
shape = Part.Shape().makeShapeFromMesh(m, 0.1)
shape.fix(0.1, 0.1, 0.1)
vol_mm3 = abs(shape.Volume)
bb = shape.getBoundingBox()
dims = [round(bb.XLength, 2), round(bb.YLength, 2), round(bb.ZLength, 2)]
vol_cm3 = round(vol_mm3 / 1000.0, 3)
grams = round(vol_cm3 * {DENSITY_PLA if material == "PLA" else 1.27}, 2)
vol_mm = vol_cm3 * 1000
thr = {THROUGHPUT_MM3_S.get(material, 100)}
hours = max(0.5, (vol_mm / thr) / 3600) + 0.5
result = {{"volume_cm3": vol_cm3, "dimensions_mm": dims, "dimensions": str(dims), "grams": grams, "faces": m.FaceCount, "print_hours": round(hours, 2)}}
print(json.dumps(result))
sys.stdout.flush()
'''
        with open(script, "w") as sf:
            sf.write(script_content)

        proc = subprocess.run(
            [FREECAD_CMD, "-c", f"exec(open(r'{script}').read())"],
            capture_output=True, text=True, timeout=60, cwd=tmpdir,
        )
        for line in reversed(proc.stdout.strip().split("\n")):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                return json.loads(line)
        return _trimesh_stats(data, material)
    except Exception:
        return _trimesh_stats(data, material)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def estimate_from_stl(data: bytes, material: str = "PLA", mode: Literal["light", "auto", "ultra"] = "auto") -> dict:
    if not _HAS_TRIMESH:
        if mode == "ultra":
            return _freecad_volume(data, material)
        raise HTTPException(status_code=500, detail="trimesh not installed; use mode=ultra")

    if mode == "light":
        return _trimesh_stats(data, material)
    elif mode == "auto":
        stats = _trimesh_stats(data, material)
        stats["print_hours"] = round(estimate_print_time_hours(stats["volume_cm3"], material, 1), 2)
        return stats
    elif mode == "ultra":
        return _freecad_volume(data, material)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown mode: {mode}")


@router.post("/api/estimate")
async def estimate_model(
    file: UploadFile = File(...),
    material: str = Form("PLA"),
    color: str = Form("natural"),
    mode: str = Form("auto"),
    db=Depends(get_db),
):
    """Upload STL/OBJ/PLY → get volume, dims, grams, print_hours.

    K1: Feeds /api/calculate and print order form.
    """
    raw = _validate_upload(file)
    m = mode if mode in ("light", "auto", "ultra") else "auto"

    t0 = _time.monotonic()
    stats = estimate_from_stl(raw, material, m)
    dims_str = stats["dimensions"]
    calc = calculate_price(
        material=material, color=color, quantity=1,
        shipping="standard", shipping_region="PL",
        volume_cm3=stats["volume_cm3"], dims=dims_str, db=db,
    )

    elapsed = round(_time.monotonic() - t0, 2)
    return JSONResponse({
        "ok": True,
        "volume_cm3": stats["volume_cm3"],
        "dimensions_mm": stats["dimensions_mm"],
        "dimensions": stats["dimensions"],
        "grams": stats["grams"],
        "faces": stats["faces"],
        "print_hours": stats["print_hours"],
        "parts": calc["parts"],
        "estimate": {
            "product_subtotal": calc["product_subtotal"],
            "shipping_cost": calc["shipping_cost"],
            "total": calc["total"],
        },
        "mode": m,
        "elapsed_s": elapsed,
        "bed_limit_mm2": 625,  # 25×25 mm
    })
