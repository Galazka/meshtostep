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

# 6. print price calculate (public)
import urllib.parse as _up
calc_fields = {"material": "PLA", "color": "natural", "quantity": "1",
               "shipping": "standard", "shipping_region": "PL",
               "volume_cm3": "10", "estimated_hours": "1", "dims": "20 20 25",
               "currency": "PLN"}
calc_body = _up.urlencode(calc_fields).encode()
req = urllib.request.Request(BASE + "/api/calculate", data=calc_body,
                             headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) 3dfile-e2e/1.0",
                                      "Content-Type": "application/x-www-form-urlencoded"},
                             method="POST")
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read()); s = r.status
except Exception as e:
    s, d = getattr(e, "code", "?"), {}
check("calculate", s == 200 and d.get("ok") and d.get("total", 0) > 0,
      f"status={s} total={d.get('total')}")

# 7. create order (anonymous — print checkout)
order_fields = dict(calc_fields, **{
    "name": "E2E Test", "email": EMAIL, "phone": "123456789",
    "address": "Testowa 1", "city": "Gdańsk", "postal_code": "80-000",
    "country": "PL", "payment_method": "blik", "job_uuid": "calculator",
    "notes": "smoke test order"})
order_body = _up.urlencode(order_fields).encode()
req = urllib.request.Request(BASE + "/api/orders", data=order_body,
                             headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) 3dfile-e2e/1.0",
                                      "Content-Type": "application/x-www-form-urlencoded"},
                             method="POST")
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read()); s = r.status
except Exception as e:
    s, d = getattr(e, "code", "?"), {}
check("order-create", s == 200 and d.get("order_id"), f"status={s} order={d.get('order_id')}")
order_id = d.get("order_id")

# 8. admin sees the order (admin login + list_orders)
s, d = api("POST", "/api/auth/login", data={"email": "admin@meshtostep.pl", "password": "MeshToStep2026!"})
check("admin-login", s == 200 and d.get("token") and d.get("user", {}).get("is_admin"),
      f"status={s}")
admin_tok = d.get("token", "")
s, d = api("GET", f"/api/orders?limit=5", token=admin_tok)
if not isinstance(d, dict) or "orders" not in d:
    d = {"orders": []}
ids = [o.get("id") for o in d.get("orders", [])]
check("admin-sees-order", s == 200 and order_id in ids, f"status={s} order={order_id} in {ids[:5]}")
s, d = api("GET", "/api/orders/stats", token=admin_tok)
check("admin-stats", s == 200 and d.get("stats", {}).get("total_orders", 0) >= 1, f"status={s}")

# 8b. admin updates order status + paid flag (PATCH)
patch_fields = _up.urlencode({"status": "realizacja", "is_paid": "1"}).encode()
req = urllib.request.Request(BASE + f"/api/orders/{order_id}", data=patch_fields,
                             headers={"Authorization": "Bearer " + admin_tok,
                                      "Content-Type": "application/x-www-form-urlencoded",
                                      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) 3dfile-e2e/1.0"},
                             method="PATCH")
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read()); s = r.status
except Exception as e:
    s, d = getattr(e, "code", "?"), {}
check("admin-update-status", s == 200 and d.get("status") == "realizacja" and d.get("is_paid") is True,
      f"status={s} d={d}")

# 8c. admin creates discount code + lists it
code_req = _up.urlencode({"code": "E2E10", "discount_pln": "10", "is_active": "1"}).encode()
req = urllib.request.Request(BASE + "/api/admin/discount_codes", data=code_req,
                             headers={"Authorization": "Bearer " + admin_tok,
                                      "Content-Type": "application/x-www-form-urlencoded",
                                      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) 3dfile-e2e/1.0"},
                             method="POST")
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        s = r.status; d = json.loads(r.read())
except Exception as e:
    s, d = getattr(e, "code", "?"), {}
check("admin-add-code", s == 200 and d.get("code") == "E2E10", f"status={s}")
s, d = api("GET", "/api/admin/discount_codes", token=admin_tok)
codes = [c.get("code") for c in d] if isinstance(d, list) else []
check("admin-list-code", s == 200 and "E2E10" in codes, f"status={s} codes={codes}")

# 9. health
s, d = api("GET", "/api/health")
check("health", s == 200 and d.get("ok"), f"status={s}")

# 10. cleanup account
s, d = api("DELETE", "/api/account", token=tok)
check("cleanup", s == 200, f"status={s}")

print("ALL GREEN" if not fails else f"FAILURES: {fails}")
sys.exit(1 if fails else 0)
