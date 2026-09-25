#!/usr/bin/env python3
"""3dfile.link — dzienny raport dla Toma (pod Hermes cron --no-agent).

Zero sekretów na dysku: hasło admina jest czytane w runtime z `railway variables`.
Wymaga: railway CLI (linked do projektu meshtostep) LUB env ADMIN_EMAIL/ADMIN_PASSWORD.

Uruchomienie:  python ops/daily_report.py
Cron:          hermes cron create '0 7 * * *' --name 3dfile-dzienny --no-agent \
                   --script 3dfile_daily.py --deliver telegram:8540922258
"""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.environ.get("REPORT_BASE", "https://3dfile.link")
UA = "3dfile.link-cron/1.0 (+https://3dfile.link)"
WARSAW = timezone(timedelta(hours=2))  # CEST; zimą +1
HTTP_TIMEOUT = 45


def _run_cli(cmd: str, timeout: int) -> str:
    """Uruchamia railway CLI (Windows: .cmd wymaga shella). Zwraca stdout+stderr."""
    try:
        p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=timeout,
                           shell=True)
        return (p.stdout or "") + (p.stderr or "")
    except Exception:  # noqa: BLE001
        return ""


def railway_env() -> dict:
    """Zmienne z Railway (bez zapisu na dysk). Puste gdy CLI niedostępne."""
    out = _run_cli("railway variables --json", 120)
    start = out.find("{")
    if start >= 0:
        try:
            return json.loads(out[start:])
        except Exception:  # noqa: BLE001
            return {}
    return {}


ENV = railway_env()
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL") or ENV.get("ADMIN_EMAIL") or "admin@meshtostep.pl"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD") or ENV.get("ADMIN_PASSWORD") or ""


def api(method: str, path: str, token: str | None = None, payload=None):
    headers = {"User-Agent": UA, "Accept": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except Exception:
            return e.code, {}
    except Exception as e:  # noqa: BLE001
        return -1, {"_err": str(e)}


def pln(v) -> str:
    try:
        v = float(v or 0)
    except Exception:  # noqa: BLE001
        v = 0.0
    return f"{v:.2f}".rstrip("0").rstrip(".").replace(".", ",") + " zł"


def mb(b) -> str:
    try:
        b = float(b or 0)
    except Exception:  # noqa: BLE001
        b = 0.0
    return f"{b/1048576:.1f} MB" if b >= 1048576 else f"{b/1024:.0f} KB"


def parse_dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return None


def hours_ago(s) -> float | None:
    d = parse_dt(s)
    if not d:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - d.astimezone(timezone.utc)).total_seconds() / 3600


TEST_MAIL_PREFIXES = ("e2e_", "e2e-", "uitest", "audit@", "test@")


def _is_test_order(email) -> bool:
    """Zamówienia z smoke-testów (example.com, e2e_*, uitest*) nie zaśmiecają alertów."""
    e = (email or "").lower()
    return (not e) or e.endswith("@example.com") or e.startswith(TEST_MAIL_PREFIXES)


def h5xx() -> str:
    """Liczba błędów 5xx w ostatnich logach Railway (best effort)."""
    out = _run_cli("railway logs --lines 400", 40)
    if not out.strip():
        return "n/a"
    n = sum(1 for ln in out.splitlines() if " 500 " in ln or "Internal Server Error" in ln)
    return f"{n} (z ostatnich 400 linii logów)"


def main() -> int:
    now = datetime.now(WARSAW)
    out = [f"🦞 3dfile.link — raport dzienny {now:%d.%m.%Y %H:%M}"]

    # -- logowanie ---------------------------------------------------------
    st, body = api("POST", "/api/auth/login", payload={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    token = body.get("token") if isinstance(body, dict) else None
    if not token:
        out.append(f"\n❌ LOGOWANIE ADMINA PADŁO (HTTP {st}). Raport bez danych panelu.")
        out.append("Sprawdź ADMIN_EMAIL/ADMIN_PASSWORD w Railway.")
        print("\n".join(out))
        return 0

    warn = []

    # -- zdrowie -----------------------------------------------------------
    st, h = api("GET", "/api/health")
    if st == 200 and h.get("ok"):
        out.append(f"ZDROWIE: ✅ API · {'✅' if h.get('database') else '❌'} DB · "
                   f"{'✅' if h.get('freecad') else '❌'} FreeCAD ({h.get('app','?')})")
        if not h.get("database"):
            warn.append("baza nie odpowiada")
        if not h.get("freecad"):
            warn.append("FreeCAD nie działa — konwersje STL→STEP padną")
    else:
        out.append(f"ZDROWIE: ❌ API NIE ODPOWIADA (HTTP {st}) — sprawdź https://3dfile.link/api/health")
        warn.append("API down")

    # -- ruch --------------------------------------------------------------
    st, s24 = api("GET", "/api/admin/analytics/summary?days=1", token=token)
    st, s7 = api("GET", "/api/admin/analytics/summary?days=7", token=token)
    if s24.get("totals"):
        t = s24["totals"]
        out.append(f"RUCH 24h: {t.get('pageviews',0)} odsłon · {t.get('visitors',0)} unikalnych · "
                   f"{t.get('sessions',0)} sesji")
    if s7.get("totals"):
        t7 = s7["totals"]
        out.append(f"RUCH 7 dni: {t7.get('pageviews',0)} odsłon · {t7.get('visitors',0)} unikalnych")
        days = s7.get("by_day") or []
        if days:
            last = days[-1]
            out.append(f"  wczoraj/dziś ({last.get('date')}): {last.get('pageviews')} odsłon")
        fun = [f for f in (s7.get("funnel") or []) if f.get("count")]
        if fun:
            chain = " → ".join(f"{f['label']} {f['count']}" for f in fun)
            out.append(f"LEJEK 7d: {chain}")
        paths = (s7.get("top_paths") or [])[:4]
        if paths:
            out.append("TOP STRONY: " + " · ".join(f"{p['path']} ({p['views']})" for p in paths))
        refs = [r for r in (s7.get("top_refs") or []) if r.get("source") not in ("(direct)", "")]
        if refs:
            out.append("ŹRÓDŁA: " + " · ".join(f"{r['source']} {r['views']}" for r in refs[:4]))

    # -- zamówienia --------------------------------------------------------
    st, orders = api("GET", "/api/orders", token=token)
    if isinstance(orders, dict):
        orders = orders.get("orders", [])
    if isinstance(orders, list) and orders:
        paid = [o for o in orders if o.get("is_paid")]
        unpaid = [o for o in orders if not o.get("is_paid") and (o.get("status") or "") != "anulowane"]
        rev = sum(float(o.get("total") or 0) for o in paid)
        rev7 = sum(float(o.get("total") or 0) for o in paid
                   if (hours_ago(o.get("created_at")) or 999) <= 168)
        out.append(f"\nZAMÓWIENIA: {len(orders)} łącznie · ✅ opłacone {len(paid)} ({pln(rev)}) · "
                   f"⏳ nieopłacone {len(unpaid)}")
        out.append(f"PRZYCHÓD: 7 dni {pln(rev7)} · łącznie {pln(rev)}")
        fresh = [o for o in orders if (hours_ago(o.get("created_at")) or 999) <= 24]
        for o in fresh:
            out.append(f"  nowe 24h: #{o['id']} {pln(o.get('total'))} · {o.get('status')} · "
                       f"{o.get('customer_email') or 'brak maila'}")
        stale = [o for o in unpaid if (hours_ago(o.get("created_at")) or 0) > 48
                 and not _is_test_order(o.get("customer_email"))]
        if stale:
            warn.append(f"{len(stale)} zamówień czeka >48h")
            out.append("⚠️ CZEKAJĄ >48h (nieopłacone):")
            for o in stale[:8]:
                out.append(f"  #{o['id']} {pln(o.get('total'))} · {o.get('status')} · "
                           f"{hours_ago(o.get('created_at')):.0f}h · {o.get('customer_email') or '-'}")
    else:
        out.append("\nZAMÓWIENIA: brak (albo endpoint nie odpowiedział)")

    # -- pliki / konwersje -------------------------------------------------
    st, q = api("GET", "/api/admin/queue", token=token)
    st, stats = api("GET", "/api/admin/stats", token=token)
    if stats:
        out.append(f"\nPLIKI: {stats.get('total_jobs','?')} modeli · {mb(stats.get('total_storage_bytes'))} · "
                   f"{stats.get('total_users','?')} kont")
    if q:
        out.append(f"KONWERSJE 24h: ✅ {q.get('done_24h',0)} · ❌ {q.get('error_24h',0)} · "
                   f"śr. {q.get('avg_processing_time_s',0)}s")
        if q.get("error_24h"):
            warn.append(f"{q['error_24h']} błędów konwersji w 24h")

    # -- backupy -----------------------------------------------------------
    st, bks = api("GET", "/api/admin/backups", token=token)
    if isinstance(bks, list) and bks:
        newest = bks[0]
        name = newest.get("name", "")
        try:
            d = datetime.strptime(name.split("-", 1)[1].split(".")[0], "%Y%m%d-%H%M").replace(tzinfo=WARSAW)
            age = (datetime.now(WARSAW) - d).total_seconds() / 3600
        except Exception:  # noqa: BLE001
            age = None
        age_txt = f"{age:.0f}h temu" if age is not None else "?"
        out.append(f"\nBACKUP DB: {name} ({newest.get('size_kb','?')} KB, {age_txt}) · kopii {len(bks)}")
        if age is not None and age > 26:
            warn.append(f"backup ma {age:.0f}h — sprawdź scheduler")
    else:
        warn.append("brak backupów DB")
        out.append("\nBACKUP DB: ❌ brak kopii")

    # -- błędy 5xx ---------------------------------------------------------
    out.append(f"BŁĘDY 5xx: {h5xx()}")

    # -- nowi użytkownicy --------------------------------------------------
    st, rep = api("GET", "/api/admin/report?kind=week", token=token)
    rows = (rep or {}).get("rows") or []
    if rows:
        nu = sum(int(r.get("new_users") or 0) for r in rows[-2:])
        o2 = sum(int(r.get("orders") or 0) for r in rows[-2:])
        p2 = sum(int(r.get("paid") or 0) for r in rows[-2:])
        r2 = sum(float(r.get("revenue") or 0) for r in rows[-2:])
        out.append(f"\nOSTATNIE 48h: nowych kont {nu} · zamówień {o2} · opłaconych {p2} ({pln(r2)})")

    # -- werdykt -----------------------------------------------------------
    if warn:
        out.append("\n⚠️ DO ZROBIENIA: " + "; ".join(warn))
    else:
        out.append("\n✅ Wszystko zielone, nic nie wymaga reakcji.")

    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
