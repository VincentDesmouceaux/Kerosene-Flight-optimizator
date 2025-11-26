FROM python:3.11-slim

WORKDIR /app

# Installation des dépendances système minimales
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpng-dev \
    libjpeg-dev \
    && rm -rf /var/lib/apt/lists/*

# Copier requirements d'abord (optimisation cache Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code
COPY app_web.py .
COPY src/ ./src/

# Exposer le port pour Northflank
EXPOSE 8080

# Commande pour Northflank
CMD ["python", "app_web.py"]