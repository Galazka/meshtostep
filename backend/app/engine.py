"""FreeCAD headless converter — the engine.
Runs FreeCADCmd as subprocess with env vars.
Pipeline: pymeshlab smooth/decimate -> FreeCAD makeSolid -> removeSplitter -> exportStep
"""
import os
import subprocess
import tempfile
from pathlib import Path

from .config import settings

# FreeCAD conversion script (runs inside FreeCADCmd)
ENGINE_SCRIPT = Path(__file__).parent / "engine" / "convert_stl.py"


def find_freecad() -> str:
    """Find FreeCADCmd binary."""
    cmd = settings.FREECAD_CMD
    if os.path.exists(cmd):
        return cmd
    # Windows dev fallback
    for p in [
        r"D:\cad\FreeCAD_1.1.3-Windows-x86_64-py311\FreeCADCmd.exe",
        r"C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe",
        "/usr/bin/freecadcmd",
        "/usr/bin/FreeCADCmd",
    ]:
        if os.path.exists(p):
            return p
    raise FileNotFoundError("FreeCADCmd not found — install FreeCAD or set FREECAD_CMD env")


def convert(
    src_path: str,
    dst_step: str,
    mode: str = "auto",
    faces: int = 1000,
    smooth_iters: int = 3,
    tolerance: float = 0.1,
) -> dict:
    """Convert mesh to STEP. Returns dict with status and info."""
    freecad = find_freecad()
    script = str(ENGINE_SCRIPT).replace("\\", "/")

    if not os.path.exists(script):
        return {"ok": False, "error": f"Engine script not found: {script}"}

    env = dict(os.environ)
    env["FC_SRC"] = str(src_path).replace("\\", "/")
    env["FC_DST"] = str(dst_step).replace("\\", "/")
    env["FC_TOL"] = str(tolerance)
    env["FC_MODE"] = mode
    env["FC_FACES"] = str(faces)
    env["FC_SMOOTH"] = str(smooth_iters)

    code = "exec(open(r'%s').read())" % script
    cmd = [freecad, "-c", code]

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=env)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "FreeCAD timeout (300s)"}
    except FileNotFoundError:
        return {"ok": False, "error": "FreeCADCmd not found"}

    output = r.stdout + r.stderr
    ok = os.path.exists(dst_step) and os.path.getsize(dst_step) > 100

    result_size = os.path.getsize(dst_step) if ok else 0

    # Parse face count from output
    result_faces = 0
    for line in output.splitlines():
        if "Refined:" in line and "faces" in line:
            try:
                result_faces = int(line.split(",")[1].strip().split(" ")[0])
            except (IndexError, ValueError):
                pass

    return {
        "ok": ok,
        "error": None if ok else f"Conversion failed: {output[-500:]}",
        "faces": result_faces,
        "result_size": result_size,
        "output": output[-1000:] if not ok else "",
    }
