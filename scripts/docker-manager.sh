#!/bin/bash
set -e

# === Paths ===
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$PROJECT_ROOT/docker/docker-compose.yml"

# Export host IP for GUI if needed
export HOST_IP=$(ipconfig getifaddr en0 2>/dev/null || echo "host.docker.internal")

show_help() {
    echo "🚀 Kerosene Docker manager"
    echo "Usage: $0 {build|up|rebuild|stop|logs|render|clean|status|help}"
    echo ""
    echo "Commands:"
    echo "  build    - Build Docker images"
    echo "  up       - Build (if needed) and start GUI container"
    echo "  rebuild  - Force rebuild (no cache) and restart GUI"
    echo "  stop     - Stop all services"
    echo "  logs     - Tail logs for GUI service"
    echo "  render   - Run one-shot render container (MP4 export)"
    echo "  clean    - Prune dangling Docker resources"
    echo "  status   - Show docker-compose services status"
    echo "  help     - Show this help"
    echo ""
    echo "Compose file:"
    echo "  $COMPOSE_FILE"
}

check_compose() {
    if [ ! -f "$COMPOSE_FILE" ]; then
        echo "❌ Compose file not found: $COMPOSE_FILE"
        echo "   Expected at: \$PROJECT_ROOT/docker/docker-compose.yml"
        exit 1
    fi
}

build() {
    check_compose
    echo "🔨 Building images..."
    (cd "$PROJECT_ROOT" && docker compose -f "$COMPOSE_FILE" build)
}

up() {
    check_compose
    echo "🚀 Starting Kerosene GUI (build if needed)..."
    (cd "$PROJECT_ROOT" && docker compose -f "$COMPOSE_FILE" up -d gui)
    echo "✅ GUI is starting. Use: $0 logs"
}

rebuild() {
    check_compose
    echo "♻️  Rebuilding images without cache..."
    (cd "$PROJECT_ROOT" && docker compose -f "$COMPOSE_FILE" build --no-cache)
    echo "🚀 Restarting GUI..."
    (cd "$PROJECT_ROOT" && docker compose -f "$COMPOSE_FILE" up -d gui)
    echo "✅ Rebuild + restart complete."
}

stop() {
    check_compose
    echo "🛑 Stopping all services..."
    (cd "$PROJECT_ROOT" && docker compose -f "$COMPOSE_FILE" down)
}

logs() {
    check_compose
    echo "📜 Tail logs for GUI..."
    (cd "$PROJECT_ROOT" && docker compose -f "$COMPOSE_FILE" logs -f gui)
}

render() {
    check_compose
    echo "🎥 Running render job..."
    mkdir -p "$PROJECT_ROOT/data/out"
    (cd "$PROJECT_ROOT" && docker compose -f "$COMPOSE_FILE" run --rm render)
    echo "✅ MP4 should be in: $PROJECT_ROOT/data/out"
}

clean() {
    echo "🧹 Docker cleanup..."
    docker system prune -f
    docker volume prune -f
    echo "✅ Cleanup done."
}

status() {
    check_compose
    echo "📊 Services status:"
    (cd "$PROJECT_ROOT" && docker compose -f "$COMPOSE_FILE" ps)
}

case "$1" in
    build)   build ;;
    up)      up ;;
    rebuild) rebuild ;;
    stop)    stop ;;
    logs)    logs ;;
    render)  render ;;
    clean)   clean ;;
    status)  status ;;
    help|"") show_help ;;
    *)       show_help ;;
esac
