"""InPost paczkomaty — proxy dla frontendu (unika CORS przeglądarki).
GET /api/inpost/points?q=Gdańsk  → lista paczkomatów (nazwa + adres).
"""
import json, urllib.parse, urllib.request
from fastapi import APIRouter

router = APIRouter()


@router.get("/api/inpost/points")
def inpost_points(q: str = "Gdańsk", limit: int = 12):
    try:
        url = "https://api-shipx-pl.easypack24.net/v1/points?per_page=%d" % max(1, min(30, limit))
        if q and q.strip():
            url += "&city=" + urllib.parse.quote(q.strip())
        req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "3dfile.link/1.1"})
        with urllib.request.urlopen(req, timeout=12) as r:
            data = json.loads(r.read().decode("utf-8"))
        items = data.get("items", [])
        out = []
        for it in items:
            loc = it.get("location", {}) or {}
            addr = it.get("address", {}) or {}
            out.append({
                "name": it.get("name", ""),
                "display_name": it.get("display_name", ""),
                "street": addr.get("street", ""),
                "building_number": addr.get("building_number", ""),
                "post_code": addr.get("post_code", ""),
                "city": addr.get("city", ""),
                "status": it.get("status", ""),
            })
        return {"ok": True, "items": out, "count": len(out)}
    except Exception as e:
        return {"ok": False, "error": str(e), "items": []}
