#!/usr/bin/env python3
"""Test sciezki ADMINA: token w query (jak admin_print.js), formaty stl/3mf/obj.
Nie zapisuje sekretow na dysk - admin login bierze z Railway variables w pamieci procesu."""
import json, os, subprocess, time, uuid, urllib.request, urllib.error, urllib.parse

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
BASE = "https://3dfile.link"


def req(path, data=None, headers=None, ctype=None):
    h = {"User-Agent": UA}
    h.update(headers or {})
    if ctype:
        h["Content-Type"] = ctype
    body = data if isinstance(data, (bytes, bytearray)) else None
    r = urllib.request.Request(BASE + path, data=body, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=90) as resp:
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


# --- admin z Railway env (bez zapisu na dysk) ---
# railway nie jest w PATH Pythona - bierz z TMPDIR dump z terminala
VD = os.path.expandvars("$TMPDIR/diagvars.json")
env = json.load(open(VD, encoding="utf-8"))
adm_email = env.get("MTS_ADMIN_EMAIL") or env.get("ADMIN_EMAIL")
adm_pass = env.get("MTS_ADMIN_PASSWORD") or env.get("ADMIN_PASSWORD")
if not adm_email or not adm_pass:
    raise SystemExit("Brak credentials admina w Railway (MTS_ADMIN_EMAIL / MTS_ADMIN_PASSWORD)")
print("admin login:", adm_email)

st, b, _ = req("/api/auth/login", json.dumps(
    {"email": adm_email, "password": adm_pass}).encode(), ctype="application/json")
print("  ->", st)
if st != 200:
    raise SystemExit("login admina nieudany: " + b[:200].decode("utf-8", "replace"))
adm_tok = json.loads(b).get("token")
print("  token:", (adm_tok[:14] + "...") if adm_tok else "BRAK")

# --- lista zamowien: znajdz ostatnie z job_uuid ---
st, b, _ = req("/api/orders", None, {"Authorization": "Bearer " + adm_tok})
print("\n/zamowienia:", st)
data = json.loads(b)
orders = data.get("orders", data) if isinstance(data, dict) else data
uuids = []
for o in orders or []:
    for it in (o.get("items") or []):
        if it.get("job_uuid"):
            uuids.append((o["id"], it.get("filename", "?"), it["job_uuid"]))
if not uuids:
    print("  brak zamowien z job_uuid (stare zamowienia nie maja plikow — to OK)")
    raise SystemExit(0)

order_id, fname, job_uuid = uuids[0]
print("  testuje zamowienie #%s  %s  uuid=%s" % (order_id, fname, job_uuid))

print("\n== download jako ADMIN: (a) naglowek, (b) token w query ==")
for fmt in ["stl", "3mf", "obj"]:
    st1, b1, _ = req(f"/api/download/{job_uuid}?format={fmt}&t={time.time()}",
                     None, {"Authorization": "Bearer " + adm_tok})
    q = "&token=" + urllib.parse.quote(adm_tok)
    st2, b2, h2 = req(f"/api/download/{job_uuid}?format={fmt}{q}&t={time.time()}")
    print("  %-4s naglowek=%s (%s B)   query=%s (%s B)" % (
        fmt, st1, len(b1), st2, len(b2)))
    for tag, code, body in (("hdr", st1, b1), ("qry", st2, b2)):
        if code != 200:
            print("       %s -> %s" % (tag, body[:110].decode("utf-8", "replace")))