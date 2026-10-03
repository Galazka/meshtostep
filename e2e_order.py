"""E2E: /zamow od wgrania STL do zamówienia jako ZALOGOWANY uzytkownik.
Sprawdza 4 rzeczy, ktore Tom zglosil:
  1. /api/estimate zwraca uuid (plik zapisywany do jobs)
  2. /api/download/{uuid} oddaje plik
  3. /api/orders/multi zapisuje user_id  -> „Moje zamówienia" nie jest puste
  4. /api/account/orders pokazuje to zamówienie
Rejestracja w locie (unikalny email), bez zapisu sekretow na dysk.
"""
import json, os, sys, time, urllib.request, urllib.error, urllib.parse, uuid as _u

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"}
BASE = "https://3dfile.link"
STL = "C:/Users/galaz/Downloads/kapajka3.stl"

ok = 0
fail = 0


def chk(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print("  PASS  %-46s %s" % (name, detail))
    else:
        fail += 1
        print("  FAIL  %-46s %s" % (name, detail))


def req(path, token=None, files=None, form=None, body=None):
    h = dict(UA)
    b = None
    if token:
        h["Authorization"] = "Bearer " + token
    if files:
        b = form or {}
        boundary = "----b" + _u.uuid4().hex
        parts = []
        for k, v in b.items():
            parts.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n" % (boundary, k, v)).encode())
        fname, fpath = files
        with open(fpath, "rb") as f:
            parts.append(("--%s\r\nContent-Disposition: form-data; name=\"file\"; filename=\"%s\"\r\nContent-Type: application/octet-stream\r\n\r\n" % (boundary, fname)).encode())
            parts.append(f.read())
            parts.append(b"\r\n")
        parts.append(("--%s--\r\n" % boundary).encode())
        b = b"".join(parts)
        h["Content-Type"] = "multipart/form-data; boundary=" + boundary
    elif body is not None:
        b = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    r = urllib.request.Request(BASE + path, data=b, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=90) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return 0, str(e).encode()


print("=== 1. /api/estimate zwraca uuid ===")
st, b = req("/api/estimate?t=%d" % time.time(), files=("kapajka3.stl", STL))
d = json.loads(b)
job_uuid = d.get("uuid")
chk("estimate 200", st == 200, str(st))
chk("estimate ma uuid", bool(job_uuid), str(job_uuid))
chk("estimate ma wolumenc", d.get("volume_cm3", 0) > 0, str(d.get("volume_cm3")))

print("=== 2. /api/download/{uuid} oddaje plik ===")
st, b = req("/api/download/%s?format=stl&t=%d" % (job_uuid, time.time()))
# 403 dla anonima na PRYWATNYM pliku = poprawne (testujemy to nizej jako wartosc)
chk("anonim NIE pobiera prywatnego", st == 403, "%s (oczekiwane 403)" % st)
chk("blad czytelny", b"Prywatny" in b or b"rywatn" in b, b[:40].decode("utf8","replace"))

print("=== 3. nowy uzytkownik + logowanie ===")
email = "e2e-%s@test.pl" % _u.uuid4().hex[:10]
pw = "TestE2E!%s99" % _u.uuid4().hex[:6]
st, b = req("/api/auth/register", body={"email": email, "password": pw, "password_confirm": pw,
                                        "terms_accepted": True, "privacy_accepted": True})
chk("rejestracja", st in (200, 201), str(st))
if st not in (200, 201):
    print(b[:300])
    sys.exit(2)
st, b = req("/api/auth/login", body={"email": email, "password": pw})
tok = json.loads(b).get("token")
chk("login", bool(tok), "token OK" if tok else b[:200].decode())
if not tok:
    sys.exit(2)

print("=== 4. zamowienie jako zalogowany ===")
items = [{
    "job_uuid": job_uuid, "job_id": None, "model_name": "kapajka3.stl",
    "material": "PLA", "color": "czarny", "colors": 1, "quantity": 1,
    "volume_cm3": d["volume_cm3"], "estimated_hours": 0,
    "dims": d.get("dimensions", ""), "infill": 15,
}]
payload = {
    "name": "E2E Test", "email": email, "phone": "790000000",
    "address": "Testowa 1", "city": "Gdańsk", "postal_code": "80-001",
    "country": "PL", "shipping": "pickup", "shipping_region": "PL",
    "discount_code": "", "notes": "", "payment_method": "stripe",
    "currency": "PLN", "items": items,
}
st, b = req("/api/orders/multi?t=%d" % time.time(), token=tok, body=payload)
chk("zamowienie utworzone", st == 200, str(st))
od = json.loads(b)
oid = od.get("order_id")
chk("order_id zwrocony", bool(oid), str(oid) + " cena " + str(od.get("total")))
if not oid:
    print(b[:400])
    sys.exit(2)

print("=== 5. /api/account/orders pokazuje zamowienie ===")
st, b = req("/api/account/orders?t=%d" % time.time(), token=tok)
ad = json.loads(b)
orders = ad.get("orders", [])
chk("account/orders 200", st == 200, str(st))
chk("lista NIE pusta", len(orders) > 0, "%d zamowien" % len(orders))
mine = [o for o in orders if o.get("id") == oid]
chk("nasze zamowienie widoczne", len(mine) == 1, "znaleziono %d" % len(mine))
if mine:
    its = mine[0].get("items", [])
    chk("ma pozycje", len(its) > 0, "%d pozycji" % len(its))
    ju = its[0].get("job_uuid") if its else None
    chk("item ma job_uuid", bool(ju), str(ju))
if ju:
    st2, b2 = req("/api/download/%s?format=stl&t=%d" % (ju, time.time()), token=tok)
    chk("download naglowkiem", st2 == 200, "%s (%d B)" % (st2, len(b2)))
    import urllib.parse as _up
    st3, b3 = req("/api/download/%s?format=stl&token=%s&t=%d" % (ju, _up.quote(tok), time.time()))
    chk("download tokenem w query (jak panel admina)", st3 == 200, "%s (%d B)" % (st3, len(b3)))
    b2 = b3
    chk("wlasciciel pobiera swoj model", st2 == 200, "%s (%d B)" % (st2, len(b2)))

print("=== 6. sprzatanie ===")
print("  (zamowienie zostaje w bazie jako zadanie dla drukarni - nie kasuje)")

print()
print("%d/%d PASS" % (ok, ok + fail))
sys.exit(1 if fail else 0)