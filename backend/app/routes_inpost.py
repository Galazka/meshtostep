"""InPost paczkomaty — proxy dla frontendu (unika CORS przeglądarki).
GET /api/inpost/points?q=Gdansk  → lista paczkomatów z adresem (ulica, kod) i geo (lat/lon dla mapki).
Case-insensitive + bez polskich znaków: "gdansk", "GdAńSk", "GDANSK" → znajdzie Gdańsk.
"""
import json, unicodedata, urllib.parse, urllib.request
from fastapi import APIRouter

router = APIRouter()


def _norm(s: str) -> str:
    """Małe litery + bez polskich znaków (ą→a itd.)."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower().strip()


def _fetch(url: str):
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "3dfile.link/1.1"})
    with urllib.request.urlopen(req, timeout=12) as r:
        return json.loads(r.read().decode("utf-8"))


@router.get("/api/inpost/points")
def inpost_points(q: str = "Gdańsk", limit: int = 12):
    try:
        q = q.strip()
        # warianty zapytania: oryginał, title-case (bez polskich), bez polskich zachowując wielkość
        candidates = []
        if q:
            candidates.append(q)
            nq = _norm(q)
            if nq:
                candidates.append(nq.capitalize())  # Gdansk
                candidates.append(nq.upper())        # GDANSK
        # InPost API potrafi nie znaleźć przy małych literach / braku diakrytyk —
        # spróbuj wariantów, zbierz unikalne trafienia.
        seen = {}
        for cand in candidates:
            url = "https://api-shipx-pl.easypack24.net/v1/points?per_page=%d" % max(1, min(30, limit))
            url += "&city=" + urllib.parse.quote(cand)
            try:
                data = _fetch(url)
            except Exception:
                continue
            for it in data.get("items", []):
                name = it.get("name", "")
                if name and name not in seen:
                    seen[name] = it
            if len(seen) >= limit:
                break

        out = []
        for it in list(seen.values()):
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
        return {"ok": True, "items": out[:max(1, min(30, limit))], "count": len(out)}
    except Exception as e:
        return {"ok": False, "error": str(e), "items": []}