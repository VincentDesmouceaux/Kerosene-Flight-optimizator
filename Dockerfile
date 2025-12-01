# Dockerfile - Web / live animation
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 MPLBACKEND=Agg

WORKDIR /app

# System deps for matplotlib PNG
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpng-dev \
    libjpeg-dev \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY src/ ./src/

# Kerosene Optimisator runs from src/
WORKDIR /app/src

EXPOSE 8080

CMD ["python", "app_web.py"]
