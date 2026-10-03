#!/usr/bin/env python3
"""Diagnostyka: /api/download/{uuid} dla formatow stl/obj/3mf na produkcji.
Zamawia prywatny model, probuje kazdy format jako wlasciciel i jako admin-ish (token)."""
import json, os, time, uuid, urllib.request, urllib.error, urllib.parse

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
BASE = "https://3dfile.link"
STL = os.path.expandvars(r"C:\Users\galaz\Downloads\kapajka3.stl")


def req(path, data=None, headers=None, ctype=None, method=None):
    h = {"User-Agent": UA}
    h.update(headers or {})
    if ctype:
        h["Content-Type"] = ctype
    body = data if isinstance(data, (bytes, bytearray)) else None
    r = urllib.request.Request(BASE + path, data=body, headers=h, method=method)
    try:
        with urllib.request.urlopen(r, timeout=90) as resp:
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


def multipart(fields, filepath, fld="file"):
    b = "----b" + uuid.uuid4().hex
    out = []
    for k, v in fields.items():
        out.append(f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    with open(filepath, "rb") as f:
        data = f.read()
    fn = os.path.basename(filepath)
    out.append(f"--{b}\r\nContent-Disposition: form-data; name=\"{fld}\"; filename=\"{fn}\"\r\n"
               f"Content-Type: application/octet-stream\r\n\r\n".encode() + data + b"\r\n")
    out.append(f"--{b}--\r\n".encode())
    return b"".join(out), {"Content-Type": f"multipart/form-data; boundary={b}"}


email = f"diag-{uuid.uuid4().hex[:8]}@example.com"
print("== rejestracja ==")
st, b, _ = req("/api/auth/register", json.dumps(
    {"email": email, "password": "Diag12345!", "password_confirm": "Diag12345!",
     "terms_accepted": True, "privacy_accepted": True}
).encode(), ctype="application/json")
print(" ", st, b[:120])
if st != 200:
    raise SystemExit("rejestracja nieudana")

st, b, _ = req("/api/auth/login", json.dumps(
    {"email": email, "password": "Diag12345!"}
).encode(), ctype="application/json")
tok = json.loads(b).get("token") if st == 200 else None
print("login:", st, "token:", (tok[:14] + "...") if tok else "BRAK")
if not tok:
    raise SystemExit("brak tokenu")
AUTH = {"Authorization": "Bearer " + tok}

print("\n== /api/estimate (zapisuje Job) ==")
body, hdrs = multipart({"material": "PLA"}, STL)
st, b, _ = req("/api/estimate?material=PLA&mode=light", body, AUTH, ctype=hdrs["Content-Type"])
print(" ", st, b[:160].decode("utf-8", "replace"))
if st != 200:
    raise SystemExit("estimate nieudany")
j = json.loads(b)
job_uuid = j.get("uuid")
print("uuid:", job_uuid, "| volume:", j.get("volume_cm3"), "| wymiary:", j.get("dimensions"))

print("\n== /api/download/{uuid} dla kazdego formatu ==")
for fmt in ["stl", "3mf", "obj", "step"]:
    st, b, h = req(f"/api/download/{job_uuid}?format={fmt}&t={int(time.time())}", None, AUTH)
    cd = h.get("Content-Disposition", "")[:60]
    print("  %-5s -> %s  %8s B  %s" % (fmt, st, len(b), cd))
    if st != 200:
        print("        body:", b[:120].decode("utf-8", "replace"))

print("\ndone. uuid =", job_uuid)