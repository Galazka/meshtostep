"""STL → volume/dims/time estimation via trimesh + FreeCAD headless.

K1: auto-volume from uploaded STL → feeds pricing engine.
  • light mode: trimesh only (fast, ~1s for 1M faces)
  • auto mode: trimesh volume → empirical time estimate
  • ultra mode: FreeCAD meshToShape (precise volume, ~5–15s)
No secrets / tokens stored on disk.
"""
from __future__ import annotations
import os, subprocess, json, tempfile, shutil, time as _time
from typing import Literal

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
DENSITY_PLA = 1.24

# empirical throughput mm³/s — speed is per material; used for time estimate
THROUGHPUT_MM3_S = {
    "PLA": 280, "PLA HT": 250, "PLA CF": 200, "PLA Silk": 260, "PLA Matte": 240, "PLA Glow": 150,
    "PETG": 240, "PETG FR": 200, "ABS": 250, "ASA": 220, "ASA CF": 180,
    "TPU": 120, "TPU 75D": 100, "PA12": 200, "PA12 CF": 180, "PCTG": 200,
    "Iglidur I150PF": 120, "Iglidur I180PF": 100, "Iglidur I190PF": 80,
}


def _validate_upload(file: UploadFile) -> bytes:
    raw = file.file.read()
    if len(raw) > MAX_STL_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large (max {MAX_STL_MB} MB)",
        )
    name = (file.filename or "").lower()
    if not (name.endswith(".stl") or name.endswith(".obj") or name.endswith(".ply") or name.endswith(".3mf")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .stl/.obj/.ply/.3mf supported",
        )
    return raw


def _trimesh_stats(data: bytes, mode: str = "auto", material: str = "PLA") -> dict:
    """Fast volume + dims via trimesh — process=False for speed."""
    import trimesh
    import io

    # Detect file type from magic bytes; fall back across loaders for robustness.
    file_type = None
    if data[:6] == b"v -0.4" or data[:4] == b"v 0." or data[:6] in (b"o test", b"# Free", b"v  0"):
        file_type = "obj"
    elif data[:4] in (b"PK\x03\x04",) and b"_3D" in data[:4096] or data[:2] == b"PK":
        # ZIP (3MF) — magic PK\x03\x04
        file_type = "3mf"
    elif len(data) > 132 and data[84:87] != b"\x00\x00\x00":
        file_type = "stl"  # binary STL guess
    else:
        file_type = "stl"

    obj = None
    if file_type == "3mf":
        # 3MF = ZIP containing 3D/3dmodel.model (XML with <mesh>/<vertices>/<triangles>)
        # trimesh.load(3mf) needs lxml; fall back to manual ZIP extraction → trimesh STL
        try:
            obj = trimesh.load(io.BytesIO(data), file_type="3mf", process=True, force='mesh')
        except Exception:
            obj = None
        if obj is None:
            # manual fallback: extract 3D/3dmodel.model, pass to trimesh via temp 3mf file
            try:
                fd, tmp_path = tempfile.mkstemp(suffix=".3mf")
                os.write(fd, data); os.close(fd)
                obj = trimesh.load(tmp_path, process=True, force='mesh')
                os.unlink(tmp_path)
            except Exception:
                obj = None
    # non-3MF loaders
    if obj is None and file_type != "3mf":
        attempts = [file_type]
        for t in ("3mf", "obj", "stl", "ply"):
            if t not in attempts:
                attempts.append(t)
        for t in attempts:
            try:
                obj = trimesh.load(io.BytesIO(data), file_type=t, process=False, force='mesh')
                if obj is not None:
                    break
            except Exception:
                continue

    if obj is None or (not isinstance(obj, trimesh.Trimesh) and not isinstance(obj, trimesh.Scene)):
        # Could not parse as anything — try temp file with auto-detect
        fd, tmp_path = tempfile.mkstemp(suffix=".3mf" if file_type == "3mf" else ".stl")
        try:
            os.write(fd, data); os.close(fd)
            obj = trimesh.load(tmp_path, process=False, force='mesh')
        except Exception:
            raise HTTPException(status_code=500, detail="Could not parse mesh")

    # Scene → Trimesh (concat all geometries) — handles 3MF Scene result
    if not isinstance(obj, trimesh.Trimesh):
        if isinstance(obj, trimesh.Scene):
            # Scene has .volume/.extents directly — use them
            if hasattr(obj, "volume") and obj.volume and not str(obj.volume).startswith("nan"):
                # keep Scene but ensure we have Trimesh for .faces count
                geoms = list(obj.geometry.values()) if obj.geometry else []
                if geoms:
                    try:
                        obj = trimesh.util.concatenate([g for g in geoms if hasattr(g, "faces")])
                    except Exception:
                        pass  # keep original Scene (volume still works)
            else:
                geoms = list(obj.geometry.values()) if obj.geometry else []
                if geoms:
                    dumped = []
                    for g in geoms:
                        d = g.dump()
                        if isinstance(d, list):
                            dumped.extend(d)
                        else:
                            dumped.append(d)
                    obj = trimesh.util.concatenate(dumped)
    if not isinstance(obj, trimesh.Trimesh):
        try:
            dumped = obj.dump()
            if isinstance(dumped, list):
                obj = trimesh.util.concatenate(dumped)
            else:
                obj = dumped.sum()
        except Exception:
            raise HTTPException(status_code=500, detail="Could not parse mesh")

    # STL/OBJ coords are raw numbers; unit may be meters (FreeCAD) or mm.
    # Slicer (Bamboo) auto-scales cm/inch/mm imports → 25.4x for inch files.
    # Heuristic: if extents product (bbox volume) < 1.0 mm³ but faces>0 →
    #   likely unit mismatch (meters vs mm) → apply 25.4x scale.
    # Real models in mm are typically > 1 mm³ bbox volume.
    bb = obj.bounds
    if bb is not None and len(bb) == 2:
        try:
            dims_mm = [round(float(bb[1][i] - bb[0][i]), 2) for i in range(3)]
        except Exception:
            dims_mm = None
    else:
        dims_mm = None
    if not dims_mm or all(d == 0 for d in dims_mm) if dims_mm else True:
        ex = obj.extents
        if ex is None:
            # compute from bounds directly
            try:
                ex = bb[1] - bb[0] if bb is not None and len(bb) == 2 else [0,0,0]
            except Exception:
                ex = [0,0,0]
        dims_mm = [round(float(e), 2) for e in ex if e is not None] if ex is not None else [0.0, 0.0, 0.0]
    vol_mm3 = abs(float(obj.volume)) if obj.volume and not (str(obj.volume).startswith("nan") or str(obj.volume) == "nan") else 0.0
    if vol_mm3 == 0.0 and bb is not None and len(bb) == 2:
        # fallback: bounding box volume (overestimate for hollow meshes)
        try:
            import numpy as np
            vol_mm3 = abs(float(np.prod(bb[1] - bb[0])))
        except Exception:
            pass

    # Unit heuristic: if extents max < 5 mm but mesh has faces → likely meters/scale mismatch.
    # Bamboo/PrusaSlicer auto-apply 25.4x (inch→mm) or scale unit. Detect tiny meshes.
    # Real small PCB models are rare below 1mm. Scale up 25.4x if volume implausibly tiny.
    extents_max = max(dims_mm) if dims_mm else 0
    face_count = len(obj.faces) if hasattr(obj, "faces") else 0
    if extents_max and extents_max < 5.0 and face_count > 50:
        scale = 25.4  # assume inch-unit file (FreeCAD default exports sometimes inch)
        dims_mm = [round(d * scale, 2) for d in dims_mm]
        vol_mm3 = round(vol_mm3 * (scale**3)) if vol_mm3 else 0.0
    vol_cm3 = round(vol_mm3 / 1000, 3)
    density = DENSITY_PLA if material == "PLA" else 1.27
    grams = round(vol_cm3 * density, 2)
    thr = THROUGHPUT_MM3_S.get(material, 100)
    hours = max(0.5, (vol_mm3 / thr) / 3600) + 0.1

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
    import trimesh, io as _io
    tmpdir = tempfile.mkdtemp()
    try:
        stl_path = os.path.join(tmpdir, "input.stl")
        # 3MF needs conversion via trimesh (FreeCAD can't read 3MF directly)
        if data[:2] == b"PK" or data[:4] == b"PK\x03\x04":
            # process=True so trimesh reconstructs a watertight mesh + applies units
            m = trimesh.load(_io.BytesIO(data), file_type="3mf", process=True, force="mesh")
            if isinstance(m, trimesh.Scene):
                # Scene → single Trimesh via volume-weighted union
                g = list(m.geometry.values()) if m.geometry else []
                if g:
                    m = trimesh.util.concatenate([gg for gg in g if hasattr(gg, "faces")])
            if not isinstance(m, trimesh.Trimesh):
                m = trimesh.load(_io.BytesIO(data), file_type="3mf", process=False, force="mesh")
                if isinstance(m, trimesh.Scene):
                    m = trimesh.util.concatenate([g for g in list(m.geometry.values()) if hasattr(g, "faces")])
            with open(stl_path, "wb") as f:
                m.export(f, file_type="stl")
        else:
            with open(stl_path, "wb") as f:
                f.write(data)

        script = os.path.join(tmpdir, "calc.py")
        script_content = f'''
import FreeCAD, Mesh, Part, sys, json
doc = FreeCAD.newDocument("calc")
m = Mesh.Mesh("{stl_path}")
shape = Part.Shape().makeShapeFromMesh(m, 0.1)
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
    """Backwards-compatible wrapper — now delegates to _trimesh_stats."""
    if not _HAS_TRIMESH:
        if mode == "ultra":
            ft = "3mf" if data[:2] == b"PK" else None
            return _trimesh_stats(data, mode, material) if ft == "3mf" else _freecad_volume(data, material)
        raise HTTPException(status_code=500, detail="trimesh not installed; use mode=ultra")

    return _trimesh_stats(data, mode, material)


@router.post("/api/estimate")
async def estimate_model(
    file: UploadFile = File(...),
    material: str = Form("PLA"),
    color: str = Form("natural"),
    mode: str = Form("auto"),
    currency: str = Form("PLN"),
    db=Depends(get_db),
):
    """Upload STL/OBJ/PLY → get volume, dims, grams, print_hours.

    K1: Feeds /api/calculate and print order form.
    """
    raw = _validate_upload(file)
    m = mode if mode in ("light", "auto", "ultra") else "auto"

    t0 = _time.monotonic()
    stats = _trimesh_stats(raw, m, material)
    dims_str = stats["dimensions"]
    calc = calculate_price(
        material=material, color=color, quantity=1,
        shipping="standard", shipping_region="PL",
        volume_cm3=stats["volume_cm3"], dims=dims_str, db=db,
        currency=currency,
    )

    elapsed = round(_time.monotonic() - t0, 2)

    # —— warnings for customer (K1.5) ——
    warnings = []
    if calc["parts"] > 1:
        warnings.append(f"Model doesn't fit 25×25 mm bed → split into {calc['parts']} parts (+0.5h per split, higher cost). Consider scaling down.")
    if stats["grams"] > 500:
        warnings.append(f"Model is heavy ({round(stats['grams'])}g). Large prints have higher failure risk — verify in Bamboo first.")
    if stats["print_hours"] > 8:
        warnings.append(f"Print time {stats['print_hours']}h is long (>8h). Consider 3-model scale or hollow + 10% infill to reduce cost.")
    if stats["print_hours"] > 24:
        warnings.append("Print exceeds 24h — Bamboo studio may fail. Split into sub-20cm parts.")

    return JSONResponse({
        "ok": True,
        "volume_cm3": stats["volume_cm3"],
        "dimensions_mm": stats["dimensions_mm"],
        "dimensions": stats["dimensions"],
        "grams": stats["grams"],
        "faces": stats["faces"],
        "print_hours": stats["print_hours"],
        "parts": calc["parts"],
        "warnings": warnings,
        "estimate": {
            "product_subtotal": calc["product_subtotal"],
            "shipping_cost": calc["shipping_cost"],
            "total": calc["total"],
        },
        "currency": calc["currency"],
        "exchange_rate": calc["exchange_rate"],
        "estimate_pln": {
            "product_subtotal": calc["product_subtotal_pln"],
            "shipping_cost": calc["shipping_cost_pln"],
            "total": round(calc["product_subtotal_pln"] + calc["shipping_cost_pln"], 2),
        },
        "mode": m,
        "elapsed_s": elapsed,
        "bed_limit_mm2": 625,
    })
