FROM python:3.11-slim

# Installation des packages système
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    python3-tk \
    tk \
    libx11-6 \
    libxext6 \
    libxrender1 \
    libxft2 \
    libxinerama1 \
    libxcursor1 \
    libxi6 \
    libxtst6 \
    libgl1 \
    fonts-dejavu-core \
    ffmpeg \
    x11-apps \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Installation des librairies Python
RUN pip install --no-cache-dir matplotlib>=3.8.0 numpy

# Cache-bust
ARG BUILD_ID=dev
ENV BUILD_ID=${BUILD_ID}

# Copie du code
COPY app_launcher.py .
COPY snapsac_gui.py .
COPY snapsac_render.py .

# Configuration par défaut
ENV MODE=gui
ENV MPLBACKEND=TkAgg

CMD ["python", "app_launcher.py"]