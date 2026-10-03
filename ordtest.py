"""Loguje sie jako admin (haslo z env) i sprawdza:
1. czy /api/orders zwraca job_uuid w items (zrodlo prawdy dla przycisku pobierz)
2. czy /api/download/{job_uuid} realnie oddaje plik dla tego zamowienia
Zmienne env: ADMIN_EMAIL, ADMIN_PASSWORD (nie zapisujemy ich nigdzie).
"""
import json, os, sys, urllib.request, urllib.error, urllib.parse

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"}
BASE = "https://3dfile.link"

email = os.environ.get("ADMIN_EMAIL")
pw = os.environ.get("ADMIN_PASSWORD")
if not email or not pw:
    for f in (".env", "backend/.env", "../.env"):
        try:
            for line in open(f, encoding="utf-8", errors="ignore"):
                if line.startswith("ADMIN_EMAIL="):
                    email = line.split("=", 1)[1].strip().strip('"')
                if line.startswith("ADMIN_PASSWORD="):
                    pw = line.split("=", 1)[1].strip().strip('"')
        except Exception:
            pass
        if email and pw:
            break

if not email or not pw:
    print("BRAK CREDENTIALS - ustaw ADMIN_EMAIL i ADMIN_PASSWORD w env")
    sys.exit(2)


def req(path, data=None, token=None, method=None, json_body=None):
    h = dict(UA)
    if token:
        h["Authorization"] = "Bearer " + token
    body = None
    if json_body is not None:
        # /api/auth/login przyjmuje JSON, nie form-data (422 inaczej)
        body = json.dumps(json_body).encode()
        h["Content-Type"] = "application/json"
    elif data is not None:
        body = urllib.parse.urlencode(data).encode()
        h["Content-Type"] = "application/x-www-form-urlencoded"
    r = urllib.request.Request(BASE + path, data=body, headers=h,
                               method=method or ("POST" if (data or json_body) else "GET"))
    try:
        with urllib.request.urlopen(r, timeout=45) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return 0, str(e).encode()


st, b = req("/api/auth/login", json_body={"email": email, "password": pw})
tok = None
try:
    # pole nazywa sie "token", nie "access_token"
    _j = json.loads(b)
    tok = _j.get("token") or _j.get("access_token")
except Exception:
    pass
print("login:", st, "token:", "OK" if tok else "BRAK")

if not tok:
    print(b[:300])
    sys.exit(2)

st, b = req("/api/orders", token=tok)
print("GET /api/orders:", st)
try:
    d = json.loads(b)
except Exception:
    print(b[:300])
    sys.exit(2)

orders = d.get("orders", []) if isinstance(d, dict) else d
print("zamowien:", len(orders))

with_uuid = 0
tested = 0
for o in orders[:12]:
    for it in (o.get("items") or []):
        ju = it.get("job_uuid")
        print("  #%s %-22s job_uuid=%s" % (o.get("id"), (it.get("model_name") or "")[:22], ju))
        if ju:
            with_uuid += 1
            if tested < 3:
                s2, b2 = req("/api/download/%s?format=stl&token=%s" % (ju, urllib.parse.quote(tok)), token=tok)
                print("      -> download %s (%d B)" % (s2, len(b2)))
                tested += 1

print()
print("items z job_uuid: %d" % with_uuid)