FROM python:3.11-slim

# System deps for FreeCAD headless + OpenCASCADE
# Note: libgl1-mesa-glx replaced by libgl1 in Debian trixie+
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    bzip2 \
    xz-utils \
    libgl1 \
    libglu1-mesa \
    libxmu6 \
    libxi6 \
    libxrender1 \
    libxkbcommon0 \
    libfontconfig1 \
    libdbus-1-3 \
    libglib2.0-0 \
    libxcb1 \
    libx11-6 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install FreeCAD via AppImage
RUN wget -q "https://github.com/FreeCAD/FreeCAD/releases/download/0.21.2/FreeCAD_0.21.2-Linux-x86_64.AppImage" \
        -O /usr/local/bin/FreeCAD.AppImage \
    && chmod +x /usr/local/bin/FreeCAD.AppImage

# Create wrapper script
RUN printf '#!/bin/bash\n\
exec /usr/local/bin/FreeCAD.AppImage --console "$@"\n' \
    > /usr/local/bin/freecadcmd && chmod +x /usr/local/bin/freecadcmd

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY frontend/ ./frontend/

ENV PYTHONPATH=/app/backend
ENV FREECAD_CMD=auto
ENV DATABASE_URL=sqlite:///./data/meshtostep.db
ENV DATA_DIR=./data
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
