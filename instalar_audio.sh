#!/bin/bash
# Script de instalación de audio para rAImundoGPT
# Ejecuta este script para instalar todas las dependencias de audio

echo ""
echo "========================================"
echo "  INSTALACIÓN DE AUDIO - RAYMUNDO"
echo "========================================"
echo ""

# Verificar entorno virtual
if [ ! -d ".venv" ]; then
    echo "[ERROR] No se encontró el entorno virtual .venv"
    echo "Por favor crea uno primero con: python3 -m venv .venv"
    exit 1
fi

echo "[1/5] Activando entorno virtual..."
source .venv/bin/activate

echo ""
echo "[2/5] Instalando dependencias de audio Python..."
pip install -r resources/setup/requirements_audio.txt

echo ""
echo "[3/5] Verificando FFmpeg..."
if command -v ffmpeg &> /dev/null; then
    echo "[OK] FFmpeg está instalado correctamente"
else
    echo "[ADVERTENCIA] FFmpeg no está instalado en el sistema"
    echo ""
    echo "Por favor instala FFmpeg:"
    echo "  Ubuntu/Debian: sudo apt install ffmpeg"
    echo "  macOS: brew install ffmpeg"
    echo "  Fedora: sudo dnf install ffmpeg"
    echo ""
    read -p "Presiona Enter para continuar sin FFmpeg..."
fi

echo ""
echo "[4/5] Instalando dependencias Node.js..."
if [ -f "package.json" ]; then
    npm install
    echo "[OK] Dependencias Node.js instaladas"
else
    echo "[ADVERTENCIA] No se encontró package.json"
fi

echo ""
echo "[5/5] Creando directorio de voces..."
if [ ! -d "resources/data/audio/voices" ]; then
    mkdir -p resources/data/audio/voices
    echo "[OK] Directorio creado: resources/data/audio/voices"
else
    echo "[OK] Directorio ya existe"
fi

echo ""
echo "========================================"
echo "  INSTALACIÓN COMPLETADA"
echo "========================================"
echo ""
echo "SIGUIENTE PASO:"
echo "Descarga una voz en español de Piper:"
echo "  1. Ve a: https://github.com/rhasspy/piper/releases/tag/v1.2.0"
echo "  2. Descarga: es_ES-claude-medium.onnx y es_ES-claude-medium.onnx.json"
echo "  3. Guárdalos en: resources/data/audio/voices/"
echo ""
echo "Para probar el sistema de audio:"
echo "  python raymundo.py"
echo ""
echo "Para WhatsApp con audio:"
echo "  Terminal 1: python whatsapp_server.py"
echo "  Terminal 2: node whatsapp_bot.js"
echo ""
echo "Lee AUDIO_INTEGRATION.md para más información."
echo ""
