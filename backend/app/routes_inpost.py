"""InPost paczkomaty — proxy dla frontendu (unika CORS przeglądarki).
GET /api/inpost/points?q=Gdansk  → paczkomaty z adresem (ulica/kod) + geo (lat/lon).

InPost API wymaga DOKŁADNYCH diakrytyk (Gdansk→0, Gdańsk→OK) i nie ma
case-insensitive filtra. Rozwiązanie: mapujemy popularne polskie miasta
z pisowni bez polskich znaków (gdansk/gdynia) na poprawną formę i pytamy API
z tą formą. Małe/duże litery nie mają znaczenia bo sami normalizujemy.
"""
import json, unicodedata, urllib.error, urllib.parse, urllib.request
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from . import models, config
from .db import get_db
from .auth import require_admin

router = APIRouter()

# ascii (bez polskich znaków) -> poprawna polska pisownia (małymi literami)
_PL_CITIES = {
    "gdansk": "Gdańsk", "gdynia": "Gdynia", "sopot": "Sopot", "szczecin": "Szczecin",
    "krakow": "Kraków", "lodz": "Łódź", "wroclaw": "Wrocław", "poznan": "Poznań",
    "warszawa": "Warszawa", "biaystok": "Białystok", "bydgoszcz": "Bydgoszcz",
    "czestochowa": "Częstochowa", "elblag": "Elbląg", "katowice": "Katowice",
    "kielce": "Kielce", "koszalin": "Koszalin", "lublin": "Lublin",
    "olsztyn": "Olsztyn", "opole": "Opole", "plock": "Płock", "rzeszow": "Rzeszów",
    "slupsk": "Słupsk", "sosnowiec": "Sosnowiec", "torun": "Toruń",
    "tarnobrzeg": "Tarnobrzeg", "tarnów": "Tarnów", "imbice": "Zamość",
    "zielona gora": "Zielona Góra", "gorzow": "Gorzów Wielkopolski",
    "radom": "Radom", "bielsko": "Bielsko-Biała", "czstochowa": "Częstochowa",
    "legnica": "Legnica", "kalisz": "Kalisz", "grudziadz": "Grudziądz",
    "jelenia gora": "Jelenia Góra", "nowy sacz": "Nowy Sącz", "suwalki": "Suwałki",
    "starachowice": "Starachowice", "inowroclaw": "Inowrocław",
    "skierniewice": "Skierniewice", "mielec": "Mielec", "jes": "Jasło",
    "tarnowskie gory": "Tarnowskie Góry", "pulawy": "Puławy", "ostrowiec": "Ostrowiec Świętokrzyski",
    "zdunska wola": "Zduńska Wola", "rybnik": "Rybnik", "gliwice": "Gliwice",
    "zabrze": "Zabrze", "bielawa": "Bielawa", "walbrzych": "Wałbrzych",
    "pruszcz": "Pruszcz Gdański", "tpkm": "Tczew", "starogard": "Starogard Gdański",
    "malbork": "Malbork", "kartuzy": "Kartuzy", "wejherowo": "Wejherowo",
    "rumia": "Rumia", "reda": "Reda", "luzino": "Luzino", "dzialdowo": "Działdowo",
    "kwidzyn": "Kwidzyn", "sztum": "Sztum", "pelplin": "Pelplin",
    "czersk": "Czersk", "kościerzyna": "Kościerzyna",
}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower().strip()


def _fetch(url: str):
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "3dfile.link/1.1"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


@router.get("/api/inpost/points")
def inpost_points(q: str = "Gdańsk", limit: int = 12):
    try:
        q = (q or "").strip()
        nq = _norm(q)
        # poprawna forma dla API (diakrytyki) — z mapy lub oryginalnej pisowni
        api_city = _PL_CITIES.get(nq)
        if not api_city and nq:
            # miasta dwuwyrazowe bez diakrytyk ("starogard gdanski") — mapa ma klucz jednowyrazowy
            first = nq.split()[0]
            api_city = _PL_CITIES.get(first)
        if not api_city and q:
            # user mógł podać z diakrytykami (np. "Gdańsk") — użyj wprost
            api_city = q

        hit_limit = max(1, min(30, limit))
        found = {}

        def _add_from(data):
            for it in data.get("items", []) or []:
                name = it.get("name", "")
                if name and name not in found:
                    found[name] = it

        # 1) najlepszy strzał: zapytanie z poprawną pisownią
        if api_city:
            try:
                url = "https://api-shipx-pl.easypack24.net/v1/points?per_page=%d&city=%s" % (
                    max(hit_limit, 20), urllib.parse.quote(api_city))
                _add_from(_fetch(url))
            except Exception:
                pass

        # 2) fallback: jeśli 0 trafień i znamy miasto w mapie — spróbuj wariantów pisowni
        if not found and api_city:
            for cand in [api_city, api_city.upper(), _PL_CITIES.get(_norm(api_city), "")]:
                if not cand or cand in (api_city,):
                    continue
                try:
                    url = "https://api-shipx-pl.easypack24.net/v1/points?per_page=%d&city=%s" % (
                        max(hit_limit, 20), urllib.parse.quote(cand))
                    _add_from(_fetch(url))
                except Exception:
                    pass
                if found:
                    break

        out = []
        for it in list(found.values()):
            loc = it.get("location", {}) or {}
            ad = it.get("address_details", {}) or {}
            out.append({
                "name": it.get("name", ""),
                "display_name": it.get("display_name", ""),
                "street": ad.get("street", ""),
                "building_number": ad.get("building_number", ""),
                "post_code": ad.get("post_code", ""),
                "city": ad.get("city", ""),
                "status": it.get("status", ""),
                "lat": loc.get("latitude"),
                "lon": loc.get("longitude"),
            })
        out = sorted(out, key=lambda x: x["display_name"])
        return {"ok": True, "items": out[:hit_limit], "count": len(out)}
    except Exception as e:
        return {"ok": False, "error": str(e), "items": []}


# ---------------------------------------------------------------------------
# InPost ShipX — nadawanie paczek bezpośrednio z panelu admina.
# Bez klucza API (jeszcze przed założeniem działalności) admin dostaje
# link-zastępczy do szybkiego nadania w apce InPost z prefillem adresu Toma.
# ---------------------------------------------------------------------------

_SHIPX = "https://api-shipx-pl.easypack24.net/v1"
_ML_PER_KG = 8000  # 6.6 cm³/kompakt zgodnie z pamięcią; InPost wymaga ~4 L/kg — luz.


def _inpost_get(settings, url: str):
    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "3dfile.link/1.1",
        "Authorization": "Bearer " + (settings.INPOST_API_KEY or ""),
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def _inpost_post(settings, url: str, payload):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "3dfile.link/1.1",
        "Authorization": "Bearer " + (settings.INPOST_API_KEY or ""),
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8")), r.status


def _extract_point_name(o) -> str:
    """Wydobywa kod punktu (np. GDN03) z customer_address / customer_city."""
    import re
    src = " ".join([o.customer_address or "", o.customer_city or ""])
    m = re.search(r"\b([A-Z]{2,3}\d{2,4})\b", src)
    if m:
        return m.group(1)
    m = re.search(r"Paczkomat[:\s-]*\s*([A-Za-z]{2,6}[- ]?\d{1,5})", src, re.I)
    if m:
        return m.group(1).replace(" ", "").upper()
    if o.customer_city:
        return _norm(o.customer_city).capitalize()
    return ""


def _order_payload(o, settings) -> dict:
    """Buduje strukturę shipments dla ShipX v1 z zamówienia 3dfile."""
    point = _extract_point_name(o) or "GDN03"
    weight_kg = max(0.5, round((o.filament_grams or 0) / 1000.0, 2))
    # wymiary kompaktu paczkomatu; realnie mały wydruk
    dims = {"length": 8, "width": 8, "height": 8}
    ref = "3DF-%d" % (o.id or 0)
    receiver = {
        "first_name": (o.customer_name or "Odbiorca").split()[0].strip(),
        "last_name": " ".join((o.customer_name or "Odbiorca").split()[1:]).strip() or "KLIENT",
        "email": o.customer_email or "",
        "phone": o.customer_phone or "",
    }
    if o.customer_phone:
        receiver["phone"] = o.customer_phone
    address = {
        "street": o.customer_address or "",
        "city": o.customer_city or "",
        "post_code": o.customer_postal or "",
        "country_code": (o.customer_country or "PL").upper()[:2],
    }
    return {
        "service": "inpost_locker_standard",
        "parcel": {
            "dimensions": dims,
            "weight": weight_kg,
            "id": ref,
        },
        "receiver": receiver,
        "address": address,
        "sender": {
            "company_name": settings.INPOST_SENDER_ORG,
        },
        "reference": ref,
        "is_primary": True,
        "custom_attributes": {
            "target_point": point,
            "dropoff_point": "KRA01",
        },
    }


@router.get("/api/inpost/config")
def inpost_config():
    return {"configured": bool(config.settings.INPOST_API_KEY)}


@router.post("/api/orders/{order_id}/shipment")
def create_shipment(order_id: int, admin: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    o = db.get(models.Order, order_id)
    if not o:
        raise HTTPException(404, "Brak zamówienia")

    if not config.settings.INPOST_API_KEY:
        # Tryb bez klucza → link zastępczy do apki z prefillem (admin klika)
        return {
            "configured": False,
            "fallback": True,
            "create_url": "https://inpost.pl/znajdz-paczkomat",
            "message": "Klucz InPost nie skonfigurowany — skorzystaj z linku-zastępczego.",
        }

    if not o.is_paid:
        raise HTTPException(400, "Zamówienie nieopłacone — najpierw potwierdź płatność.")
    if o.shipping_method not in ("standard", "express"):
        raise HTTPException(400, "Ten rodzaj dostawy nie obsługuje paczkomatu InPost.")

    try:
        data, status = _inpost_post(config.settings, _SHIPX + "/shipments",
                                    {"shipments": [_order_payload(o, config.settings)]})
    except urllib.error.HTTPError as e:
        raise HTTPException(502, "InPost API: %s" % e)
    except Exception as e:
        raise HTTPException(502, "InPost API: %s" % e)

    s = (data.get("shipments") or [{}])[0]
    if status >= 400 or s.get("errors"):
        raise HTTPException(502, "InPost odrzucił przesyłkę: %s" % json.dumps(s.get("errors", s), ensure_ascii=False)[:500])

    # zapisz ID przesyłki — wygodnie dla śledzenia + etykieta
    o.tracking_code = s.get("id") or o.tracking_code or ""
    db.commit()

    return {
        "configured": True,
        "ok": True,
        "shipment_id": s.get("id"),
        "tracking_number": s.get("tracking_number"),
        "status": s.get("status"),
        "label_url": s.get("label_url"),
        "points": s.get("points"),
    }
