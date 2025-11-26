#!/bin/bash
set -e

COMPOSE_FILE="docker/docker-compose.yml"
export HOST_IP=$(ipconfig getifaddr en0 2>/dev/null || echo "host.docker.internal")

show_help() {
    echo "🚀 Gestionnaire Docker pour Kerosene"
    echo "Usage: $0 {build|start|stop|logs|render|clean|status}"
    echo ""
    echo "Commandes:"
    echo "  build   - Construit les images Docker"
    echo "  start   - Démarre l'application GUI"
    echo "  stop    - Arrête l'application"
    echo "  logs    - Affiche les logs en temps réel"
    echo "  render  - Génère une vidéo MP4"
    echo "  clean   - Nettoie Docker"
    echo "  status  - Affiche le statut"
}

build() {
    echo "🔨 Construction des images Docker..."
    docker compose -f $COMPOSE_FILE build --no-cache
}

start() {
    echo "🚀 Démarrage de l'application GUI..."
    docker compose -f $COMPOSE_FILE up -d gui
    echo "✅ Application démarrée. Pour les logs: $0 logs"
}

stop() {
    echo "🛑 Arrêt de l'application..."
    docker compose -f $COMPOSE_FILE down
}

logs() {
    docker compose -f $COMPOSE_FILE logs -f gui
}

render() {
    echo "🎥 Génération de vidéo..."
    mkdir -p data/out
    docker compose -f $COMPOSE_FILE run --rm render
    echo "✅ Vidéo générée dans data/out/"
}

clean() {
    echo "🧹 Nettoyage Docker..."
    docker system prune -f
    docker volume prune -f
    echo "✅ Nettoyage terminé"
}

status() {
    echo "📊 Statut des conteneurs:"
    docker compose -f $COMPOSE_FILE ps
}

case "$1" in
    build) build ;;
    start) start ;;
    stop) stop ;;
    logs) logs ;;
    render) render ;;
    clean) clean ;;
    status) status ;;
    *) show_help ;;
esac
