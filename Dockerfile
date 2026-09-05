FROM python:3.11-slim

# FreeCAD + system deps from Debian repos (reliable, no big AppImage download)
RUN apt-get update && apt-get install -y --no-install-recommends \
    freecad \
    libgl1 \
    libglu1-mesa \
    libxrender1 \
    libfontconfig1 \
    libdbus-1-3 \
    libglib2.0-0 \
    libxcb1 \
    libx11-6 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY frontend/ ./frontend/

ENV PYTHONPATH=/app/backend
ENV FREECAD_CMD=freecadcmd
ENV DATABASE_URL=sqlite:///./data/meshtostep.db
ENV DATA_DIR=./data
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

CMD ["sh", "-c", "mkdir -p $DATA_DIR && uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
