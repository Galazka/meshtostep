"""Prod E2E smoke test: register -> upload -> share -> verify pages -> cleanup.
Run: python e2e_prod.py
Exit 0 = all green, 1 = failure (message on stdout).
"""
import json
import sys
import urllib.request

BASE = "https://3dfile.link"
import time as _t
EMAIL = f"e2e_smoke_{int(_t.time())}@3dfile.link"
PASS = "Smoke12345!"
STL = (
    "solid t\n"
    "facet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 5 0 0\nvertex 0 5 0\n"
    "endloop\nendfacet\nendsolid t\n"
).encode()

fails = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name, extra)
    if not cond:
        fails.append(name)


def api(method, path, token=None, data=None, files=None):
    url = BASE + path
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) 3dfile-e2e/1.0'}
    if token:
        headers["Authorization"] = "Bearer " + token
    if files:
        import uuid as _uuid
        b = "----" + _uuid.uuid4().hex
        body = b""
        for k, v in (data or {}).items():
            body += f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
        fname, ctype, fdata = files
        body += f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="{fname}"\r\nContent-Type: {ctype}\r\n\r\n'.encode() + fdata + f"\r\n--{b}--\r\n".encode()
        headers["Content-Type"] = "multipart/form-data; boundary=" + b
    elif data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    else:
        body = None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            ct = r.headers.get("Content-Type", "")
            raw = r.read()
            if "json" in ct:
                return r.status, json.loads(raw)
            return r.status, raw
    except Exception as e:
        code = getattr(e, "code", "?")
        return code, {"error": str(e)[:150]}


# 1. register (or login if exists)
s, d = api("POST", "/api/auth/register", data={
    "email": EMAIL, "password": PASS, "password_confirm": PASS,
    "terms_accepted": True, "privacy_accepted": True})
if s != 200:
    s, d = api("POST", "/api/auth/login", data={"email": EMAIL, "password": PASS})
check("register/login", s == 200 and "token" in d, f"status={s}")
if fails:
    sys.exit(1)
tok = d["token"]

# 2. upload
s, d = api("POST", "/api/convert", token=tok, data={"mode": "auto"},
           files=("smoke.stl", "model/stl", STL))
check("upload", s == 200 and d.get("uuid"), f"status={s}")
job_id, uuid = d.get("job_id"), d.get("uuid")

# 3. share named 7d (multipart Form fields)
import uuid as _uuid
b = "----" + _uuid.uuid4().hex
fields = {"job_id": str(job_id), "fmt": "step", "expires_days": "7",
          "show_author": "true", "anon": "false"}
body = b"".join(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in fields.items()) + f"--{b}--\r\n".encode()
req = urllib.request.Request(BASE + "/api/share", data=body,
                             headers={"Authorization": "Bearer " + tok, "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) 3dfile-e2e/1.0",
                                      "Content-Type": "multipart/form-data; boundary=" + b},
                             method="POST")
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read())
        s = r.status
except Exception as e:
    s, d = getattr(e, "code", "?"), {}
check("share", s == 200 and d.get("vanity"), f"status={s}")
share_tok = d.get("token", "")

# 4. pages
for name, path in [("vanity", d.get("vanity", "").replace(BASE, "")),
                   ("token-link", "/s/" + share_tok),
                   ("embed", f"/e/{job_id}")]:
    if not path:
        check(name, False, "no url")
        continue
    req = urllib.request.Request(BASE + path, method="GET",
                                 headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) 3dfile-e2e/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            check(name, r.status == 200, f"status={r.status}")
    except Exception as e:
        check(name, False, str(e)[:100])

# 5. expiry status
s, d = api("GET", f"/api/share/{share_tok}/status", token=tok)
check("expiry", s == 200 and d.get("expires_at"), f"status={s}")

# 6. health
s, d = api("GET", "/api/health")
check("health", s == 200 and d.get("ok"), f"status={s}")

# 7. cleanup account
s, d = api("DELETE", "/api/account", token=tok)
check("cleanup", s == 200, f"status={s}")

print("ALL GREEN" if not fails else f"FAILURES: {fails}")
sys.exit(1 if fails else 0)
