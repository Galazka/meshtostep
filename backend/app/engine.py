"""FreeCAD headless converter — the engine.
Runs FreeCADCmd as subprocess with env vars.
Pipeline: pymeshlab smooth/decimate -> FreeCAD makeSolid -> removeSplitter -> exportStep
"""
import os
import shutil
import subprocess
from pathlib import Path

from .config import settings

ENGINE_SCRIPT = Path(__file__).parent / "engine" / "convert_stl.py"


def find_freecad() -> str:
    """Find FreeCADCmd binary — multiple strategies."""
    cmd = settings.FREECAD_CMD

    # Strategy 1: env var points to a real file
    if cmd and os.path.isfile(cmd):
        return cmd

    # Strategy 2: env var = "auto" — search PATH and common locations
    candidates = [
        # PATH
        shutil.which("freecadcmd") or "",
        shutil.which("FreeCADCmd") or "",
        shutil.which("FreeCAD") or "",
        # AppImage extraction (our Dockerfile)
        "/usr/local/freecad/usr/bin/FreeCADCmd",
        # Our wrapper script
        "/usr/local/bin/freecadcmd",
        # Flatpak
        "/var/lib/flatpak/app/org.freecad org.freecad.Current/x86_64/stable/active/files/bin/FreeCADCmd",
        # Snap
        "/snap/freecad/current/usr/bin/FreeCADCmd",
        # System
        "/usr/bin/freecadcmd",
        "/usr/bin/FreeCADCmd",
        "/usr/bin/FreeCAD",
        # Windows dev
        r"D:\cad\FreeCAD_1.1.3-Windows-x86_64-py311\FreeCADCmd.exe",
        r"C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe",
        # Conda environments
        os.path.expanduser("~/miniforge3/envs/freecad/bin/FreeCADCmd"),
        os.path.expanduser("~/anaconda3/envs/freecad/bin/FreeCADCmd"),
    ]

    for p in candidates:
        if p and os.path.isfile(p):
            return p

    raise FileNotFoundError(
        "FreeCADCmd not found. Set FREECAD_CMD env or install FreeCAD. "
        f"Searched: {[c for c in candidates if c]}"
    )


def convert(
    src_path: str,
    dst_step: str,
    mode: str = "auto",
    faces: int = 1000,
    smooth_iters: int = 3,
    tolerance: float = 0.1,
) -> dict:
    """Convert mesh to STEP. Returns dict with status and info."""
    try:
        freecad = find_freecad()
    except FileNotFoundError as e:
        return {"ok": False, "error": str(e), "faces": 0, "result_size": 0, "output": ""}

    script = str(ENGINE_SCRIPT).replace("\\", "/")
    if not os.path.exists(script):
        return {"ok": False, "error": f"Engine script not found: {script}", "faces": 0, "result_size": 0, "output": ""}

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
        return {"ok": False, "error": "FreeCAD timeout (300s)", "faces": 0, "result_size": 0, "output": ""}
    except FileNotFoundError:
        return {"ok": False, "error": f"FreeCADCmd binary not found at: {freecad}", "faces": 0, "result_size": 0, "output": ""}

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
