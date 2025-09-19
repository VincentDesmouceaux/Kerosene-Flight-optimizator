# Dockerfile (GUI par défaut, MODE=render pour headless)
FROM python:3.11-slim

# Update system packages to fix vulnerabilities
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    python3-tk tk \
    libx11-6 libxext6 libxrender1 libxft2 libxinerama1 libxcursor1 \
    fonts-dejavu-core \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Libs Python
RUN pip install --no-cache-dir matplotlib>=3.8.0 numpy

# Canari cache-bust
ARG BUILD_ID=dev
ENV BUILD_ID=${BUILD_ID}

# Code
COPY app_launcher.py .
COPY snapsac_gui.py  .
COPY snapsac_render.py .

# Par défaut : GUI
ENV MODE=gui
ENV MPLBACKEND=TkAgg

CMD ["python", "app_launcher.py"]
