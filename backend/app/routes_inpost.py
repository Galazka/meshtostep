"""InPost paczkomaty — proxy dla frontendu (unika CORS przeglądarki).
GET /api/inpost/points?q=Gdansk  → paczkomaty z adresem (ulica/kod) + geo (lat/lon).

InPost API wymaga DOKŁADNYCH diakrytyk (Gdansk→0, Gdańsk→OK) i nie ma
case-insensitive filtra. Rozwiązanie: mapujemy popularne polskie miasta
z pisowni bez polskich znaków (gdansk/gdynia) na poprawną formę i pytamy API
z tą formą. Małe/duże litery nie mają znaczenia bo sami normalizujemy.
"""
import json, unicodedata, urllib.parse, urllib.request
from fastapi import APIRouter

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