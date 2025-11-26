SHELL := /bin/bash
APP_IMAGE := kerosene-app:latest

help:
	@echo "Commandes:"
	@echo "  make setup-x11       # Configure XQuartz"
	@echo "  make build           # Build l'image Docker"
	@echo "  make run-gui         # Lance l'application GUI"
	@echo "  make logs            # Affiche les logs"
	@echo "  make stop            # Arrête les conteneurs"

setup-x11:
	@echo "Configuration de XQuartz..."
	@pkill -f Xquartz || true
	@sleep 2
	@defaults write org.xquartz.X11 nolisten_tcp -boolean false
	@defaults write org.macosforge.xquartz.X11 enable_iglx -boolean true
	@open -a XQuartz
	@sleep 5
	@echo "✅ XQuartz configuré"
	@echo "📝 Dans un NOUVEAU terminal, exécutez:"
	@echo "   export DISPLAY=:0"
	@echo "   /opt/X11/bin/xhost +localhost"
	@echo "   /opt/X11/bin/xhost +"

build:
	docker compose build

run-gui:
	@echo "🚀 Lancement de l'application GUI..."
	docker compose up -d gui
	@sleep 3
	@echo "✅ Application lancée. Logs: make logs"

logs:
	docker logs -f kerosene-run

stop:
	docker compose down

render-once:
	mkdir -p out
	docker compose run --rm -e LOOP_DELAY=0 render

clean:
	docker compose down
	-docker rmi ${APP_IMAGE} 2>/dev/null || true

.PHONY: help setup-x11 build run-gui logs stop render-once clean