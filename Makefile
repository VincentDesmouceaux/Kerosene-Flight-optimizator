SHELL := /bin/bash

# ------- Réglages -------
APP_IMAGE := kerosene-app:latest

# ------- Aide -------
help:
	@echo "Commandes:"
	@echo "  make xquartz         # (macOS) Ouvre XQuartz et autorise les clients X11"
	@echo "  make build           # Build l'image ${APP_IMAGE}"
	@echo "  make run-gui         # Lance la fenêtre animée (GUI) et auto-restart"
	@echo "  make logs            # Affiche les logs de la GUI"
	@echo "  make stop            # Stoppe/retire les services"
	@echo "  make render-once     # Rend 1 MP4 dans ./out puis sort"
	@echo "  make render-loop     # Rend des MP4 en boucle (LOOP_DELAY=10)"
	@echo "  make clean-images    # (option) Supprime l'image locale ${APP_IMAGE}"

# ------- macOS XQuartz -------
xquartz:
	@open -a XQuartz || true
	@sleep 1
	@/opt/X11/bin/xhost +localhost || true
	@echo "XQuartz OK. DISPLAY=host.docker.internal:0"

# ------- Build -------
build:
	docker compose build

# ------- GUI -------
run-gui: xquartz build
	docker compose up -d gui
	@echo "Fenêtre en cours…  => docker logs -f kerosene-run"

logs:
	docker logs -f kerosene-run

stop:
	docker compose down

# ------- RENDER (MP4) -------
render-once: build
	mkdir -p out
	# un rendu MP4, puis sortie
	docker compose run --rm -e LOOP_DELAY=0 render
	@echo "MP4 écrit dans ./out"

render-loop: build
	mkdir -p out
	# rend en boucle (10s entre rendus)
	docker compose run --rm -e LOOP_DELAY=10 render

# ------- Option nettoyage -------
clean-images:
	-docker rm -f kerosene-run kerosene-render 2>/dev/null || true
	-docker rmi ${APP_IMAGE} 2>/dev/null || true
