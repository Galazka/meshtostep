FROM python:3.11-slim

# Install FreeCAD headless + system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    freecad \
    libfreecad-pythonifcopenscad \
    && rm -rf /var/lib/apt/lists/*

# If freecad package unavailable, try flatpak or manual install
# For Railway, we use the FreeCAD AppImage or conda install
RUN which freecadcmd || which FreeCADCmd || echo "FreeCAD not in PATH — will use env var"

WORKDIR /app

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY backend/ ./backend/
COPY frontend/ ./frontend/

ENV PYTHONPATH=/app/backend
ENV FREECAD_CMD=auto
ENV DATABASE_URL=sqlite:///./data/meshtostep.db
ENV DATA_DIR=./data

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
