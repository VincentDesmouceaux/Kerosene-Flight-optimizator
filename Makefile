SHELL := /bin/bash

.PHONY: help setup build start stop logs render clean status

help:
	@echo "🏗️  Commandes disponibles:"
	@echo "  make setup    Configure XQuartz"
	@echo "  make build    Construit les images Docker"
	@echo "  make start    Démarre l'application GUI"
	@echo "  make stop     Arrête l'application"
	@echo "  make logs     Affiche les logs en temps réel"
	@echo "  make render   Génère une vidéo MP4"
	@echo "  make clean    Nettoie l'environnement Docker"
	@echo "  make status   Affiche le statut"

setup:
	./scripts/setup-xquartz.sh

build:
	./scripts/docker-manager.sh build

start:
	./scripts/docker-manager.sh start

stop:
	./scripts/docker-manager.sh stop

logs:
	./scripts/docker-manager.sh logs

render:
	./scripts/docker-manager.sh render

clean:
	./scripts/docker-manager.sh clean

status:
	./scripts/docker-manager.sh status

run: build start
	@echo "✅ Application démarrée!"
	@echo "📊 Pour voir les logs: make logs"
	@echo "🛑 Pour arrêter: make stop"
