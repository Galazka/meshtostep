#!/usr/bin/env python3
"""E2E: tworzy zamowienie i sprawdza czy mail do drukarni (ADMIN_EMAIL_PRINTER) wyszedl.
Mail idzie przez Resend - weryfikujemy log wysylki w Railway oraz delivery w API."""
import json, os, time, uuid, urllib.request, urllib.error

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
BASE = "https://3dfile.link"
SCRATCH = r"C:\Users\galaz\AppData\Local\hermes\cache\scratch"
VARS = os.path.join(SCRATCH, "diagvars.json")


def call(path, data=None, headers=None, ctype=None):
    h = {"User-Agent": UA}
    h.update(headers or {})
    if ctype:
        h["Content-Type"] = ctype
    r = urllib.request.Request(BASE + path,
                               data=data if isinstance(data, (bytes, bytearray)) else None,
                               headers=h)
    try:
        with urllib.request.urlopen(r, timeout=180) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def jcall(path, data=None, headers=None, ctype=None):
    st, b = call(path, data, headers, ctype)
    try:
        return st, json.loads(b)
    except Exception:
        return st, {"raw": b[:200].decode("utf-8", "replace")}


env = json.load(open(VARS, encoding="utf-8"))
email = f"mailtest-{uuid.uuid4().hex[:8]}@example.com"

st, j = jcall("/api/auth/register", json.dumps({
    "email": email, "password": "Diag12345!", "password_confirm": "Diag12345!",
    "terms_accepted": True, "privacy_accepted": True}).encode(),
    ctype="application/json")
print("register:", st)
tok = j.get("token")
A = {"Authorization": "Bearer " + tok}

src = os.path.join(SCRATCH, "verify_stl.stl")
data = open(src, "rb").read()
bd = "----m" + uuid.uuid4().hex
body = (f'--{bd}\r\nContent-Disposition: form-data; name="material"\r\n\r\nPLA\r\n'.encode()
        + f'--{bd}\r\nContent-Disposition: form-data; name="file"; filename="mailtest.stl"\r\n'
          f'Content-Type: application/octet-stream\r\n\r\n'.encode()
        + data + f"\r\n--{bd}--\r\n".encode())

st, j = jcall("/api/estimate?material=PLA&mode=light", body, A,
              f"multipart/form-data; boundary={bd}")
print("estimate:", st, "uuid:", j.get("uuid"), "vol:", j.get("volume_cm3"))
job_uuid = j["uuid"]

order = {
    "name": "Test Mailowy",
    "email": email,
    "phone": "600100200",
    "address": "Testowa 1",
    "city": "Gdańsk",
    "postal": "80-001",
    "shipping_method": "pickup",
    "items": [{"job_uuid": job_uuid, "filename": "mailtest.stl", "material": "PLA",
               "quantity": 1, "color": "czarny", "colors": 1}],
    "notes": "MAILTEST",
}
st, j = jcall("/api/orders/multi", json.dumps(order).encode(), A, "application/json")
print("order/multi:", st, "order_id:", j.get("order_id"), "total:", j.get("total"))
oid = j.get("order_id")
print("MARKER_MAILTEST_ORDER", oid, flush=True)
print("Sprawdz teraz logi Railway pod 'admin mail' / kolejka Resend.")