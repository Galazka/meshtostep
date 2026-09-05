FROM python:3.11-slim

# System deps for FreeCAD headless + OpenCASCADE
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    bzip2 \
    xz-utils \
    libgl1-mesa-glx \
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
    && rm -rf /var/lib/apt/lists/*

# Install FreeCAD 0.21 via AppImage (stable, works on headless)
RUN wget -q "https://github.com/FreeCAD/FreeCAD/releases/download/0.21.2/FreeCAD_0.21.2-Linux-x86_64.AppImage" \
        -O /usr/local/bin/FreeCAD.AppImage \
    && chmod +x /usr/local/bin/FreeCAD.AppImage \
    && /usr/local/bin/FreeCAD.AppImage --appimage-extract 2>/dev/null || true \
    && mv /squashfs-root /usr/local/freecad || true

# Fallback: create a wrapper that tries freecadcmd, FreeCAD, or AppImage
RUN echo '#!/bin/bash\n\
if [ -x /usr/local/freecad/usr/bin/FreeCADCmd ]; then\n\
    exec /usr/local/freecad/usr/bin/FreeCADCmd "$@"\n\
elif command -v freecadcmd >/dev/null 2>&1; then\n\
    exec freecadcmd "$@"\n\
elif [ -x /usr/local/bin/FreeCAD.AppImage ]; then\n\
    exec /usr/local/bin/FreeCAD.AppImage --console "$@"\n\
else\n\
    echo "FreeCAD not found" >&2\n\
    exit 1\n\
fi' > /usr/local/bin/freecadcmd && chmod +x /usr/local/bin/freecadcmd

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
