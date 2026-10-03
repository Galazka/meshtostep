"""Sprawdza ze panel admina da sie pobrac plik z zamowienia (drukarnia).
Loguje sie ADMINEM (token ze srodowiska, nie zapisuje na dysk),
pobiera /api/orders/{id} z zamowieniem testowym i probuje download.
"""
import json, os, sys, time, urllib.request, urllib.error

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"}
BASE = "https://3dfile.link"
EMAIL = os.environ.get("MTS_ADMIN_EMAIL", "")
PW = os.environ.get("MTS_ADMIN_PASSWORD", "")

if not (EMAIL and PW):
    print("Brak zmiennych MTS_ADMIN_EMAIL / MTS_ADMIN_PASSWORD — pomijam (nie zapisuje sekretow na dysk).")
    sys.exit(0)


def req(path, token=None):
    h = dict(UA)
    if token:
        h["Authorization"] = "Bearer " + token
    r = urllib.request.Request(BASE + path, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=90) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


st, b = req("/api/auth/login")
print("login (bez tokena w body, oczekiwane 422):", st)

import urllib.parse
data = json.dumps({"email": EMAIL, "password": PW}).encode()
r = urllib.request.Request(BASE + "/api/auth/login", data=data,
                           headers={**UA, "Content-Type": "application/json"})
try:
    with urllib.request.urlopen(r, timeout=90) as resp:
        tok = json.loads(resp.read()).get("token")
except urllib.error.HTTPError as e:
    print("login FAIL", e.code, e.read()[:200])
    sys.exit(1)
print("admin login OK, token len =", len(tok or ""))

st, b = req("/api/orders?limit=5&t=%d" % time.time(), token=tok)
d = json.loads(b)
orders = d.get("orders", d if isinstance(d, list) else [])
print("zamowien:", len(orders))

# znajdz zamowienie z plikiem
target = None
for o in orders:
    for it in (o.get("items") or []):
        if it.get("job_uuid"):
            target = (o["id"], it["job_uuid"], it.get("model_name"))
            break
    if target:
        break

if not target:
    print("BRAK zamowienia z job_uuid w ostatnich 5 — nic do sprawdzenia")
    sys.exit(0)

oid, ju, nm = target
print("testuje zamowienie %d, plik %s (%s)" % (oid, ju, nm))
st, b = req("/api/download/%s?format=stl&token=%s&t=%d" % (ju, urllib.parse.quote(tok), time.time()))
print("download z tokenem admina: %s (%d B)" % (st, len(b)))
ok = st == 200 and len(b) > 1000
print("WYNIK:", "PASS" if ok else "FAIL")

# czy button w panelu jest widoczny
st, b = req("/admin?t=%d" % time.time())
html = b.decode("utf8", "replace")
has = "downloadOrderItem" in html or "admin_print.js" in html
print("admin.html ma panel drukarni:", "PASS" if has else "FAIL")
sys.exit(0 if ok else 1)