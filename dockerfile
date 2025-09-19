# Dockerfile (GUI)
FROM python:3.11-slim

# Pour Tkinter + X11
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-tk tk \
    libx11-6 libxext6 libxrender1 libxft2 libxinerama1 libxcursor1 \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dépendances Python
RUN pip install --no-cache-dir matplotlib>=3.8.0

# Code GUI
COPY snapsac_gui.py /app/snapsac_gui.py

# Backend GUI explicite
ENV MPLBACKEND=TkAgg

CMD ["python", "/app/snapsac_gui.py"]
