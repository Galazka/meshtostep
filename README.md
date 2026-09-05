# MeshToStep — STL → STEP za grosze

Przekształć plik mesh (STL/3MF/OBJ) w edytowalną bryłę STEP. Bez limitów Fusion Personal.

## Cennik

| Pakiet | Cena | Co dostajesz |
|--------|------|--------------|
| Start | 0 zł | 3 konwersje za darmo |
| Start 5 | 0.50 zł | 5 konwersji |
| Pakiet 25 | 1.99 zł | 25 konwersji |
| Pakiet 100 | 5.99 zł | 100 konwersji |

## Uruchomienie lokalne

```bash
# 1. Zainstaluj FreeCAD (headless wystarczy)
# Windows: https://www.freecad.org/downloads.php
# Linux: apt install freecad

# 2. Depsy
pip install -r requirements.txt

# 3. Start
uvicorn backend.app.main:app --port 8000

# 4. Otwórz
http://localhost:8000
```

## Deploy na Railway

1. Push na GitHub
2. New Project → Deploy from GitHub
3. Add Variable: `SECRET_KEY=<losowy-32-znaki>`
4. Deploy — Dockerfile sam zainstaluje FreeCAD

## Stack

- **Backend**: FastAPI + SQLite (SQLAlchemy) + JWT auth
- **Engine**: FreeCAD headless (makeSolid + removeSplitter + decimate + Taubin smooth)
- **Frontend**: Single HTML + Three.js 3D preview (w planach)
- **Deploy**: Dockerfile + Railway
