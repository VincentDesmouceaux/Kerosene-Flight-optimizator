# Dockerfile
FROM python:3.11-slim

# Logs non bufferisés + backend headless
ENV PYTHONUNBUFFERED=1 \
    MPLBACKEND=Agg

# OS deps (ffmpeg pour encoder le MP4)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dépendances Python (matplotlib suffit)
RUN pip install --no-cache-dir matplotlib>=3.8.0

# Code
COPY snapsac_render.py /app/snapsac_render.py

# Dossier de sortie (monté depuis l’hôte)
RUN mkdir -p /out

# Petit test ffmpeg au démarrage, puis run
CMD ["bash", "-lc", "echo \"[BOOT] ffmpeg: $(ffmpeg -version | head -n1)\"; python /app/snapsac_render.py"]
