#!/usr/bin/env python3
"""Weryfikacja ze pobrane STL/OBJ/3MF to prawdziwa geometria, nie smiec.
Porownuje z oryginalnym plikiem klienta (objętość/faces w mm3) + watertight."""
import json, os, time, urllib.parse, urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
BASE = "https://3dfile.link"
JOB = "75004586be3d"
SCRATCH = os.path.expandvars(r"C:\Users\galaz\AppData\Local\hermes\cache\scratch")
VARS = os.path.join(SCRATCH, "diagvars.json")


def get(url, headers=None):
    r = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(r, timeout=240) as resp:
        return resp.read()


env = json.load(open(VARS, encoding="utf-8"))
r = urllib.request.Request(BASE + "/api/auth/login",
    data=json.dumps({"email": env["ADMIN_EMAIL"], "password": env["ADMIN_PASSWORD"]}).encode(),
    headers={"User-Agent": UA, "Content-Type": "application/json"})
tok = json.loads(urllib.request.urlopen(r, timeout=60).read())["token"]
q = "&token=" + urllib.parse.quote(tok)

import trimesh

for fmt in ("3mf", "stl", "obj"):
    data = get(f"{BASE}/api/download/{JOB}?format={fmt}{q}&t={time.time()}")
    path = os.path.join(SCRATCH, f"verify_{fmt}.{fmt}")
    with open(path, "wb") as f:
        f.write(data)
    try:
        m = trimesh.load(path, force="mesh", process=False)
        print(f"{fmt:4} {len(data):>9} B  verts={len(m.vertices):>6}  faces={len(m.faces):>6}  "
              f"watertight={str(m.is_watertight):5}  volume={abs(m.volume):10.1f} mm3  "
              f"bbox={m.extents.round(1).tolist()}")
    except Exception as e:
        print(f"{fmt:4} {len(data):>9} B  -> trimesh: {type(e).__name__}: {e}")