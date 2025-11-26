#!/bin/bash

echo "🔧 Configuration de XQuartz..."

# Arrêter XQuartz
pkill -f Xquartz 2>/dev/null || true
sleep 2

# Configuration
defaults write org.xquartz.X11 nolisten_tcp -boolean false
defaults write org.macosforge.xquartz.X11 enable_iglx -boolean true

# Démarrer XQuartz
open -a XQuartz
sleep 5

echo "✅ XQuartz configuré"
echo ""
echo "📝 Dans un NOUVEAU terminal, exécutez:"
echo "   export DISPLAY=:0"
echo "   xhost +localhost"
echo "   xhost +"
