@echo off
REM Script de instalación de audio para rAImundoGPT
REM Ejecuta este script para instalar todas las dependencias de audio

echo.
echo ========================================
echo   INSTALACION DE AUDIO - RAYMUNDO
echo ========================================
echo.

REM Verificar entorno virtual
if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] No se encontro el entorno virtual .venv
    echo Por favor crea uno primero con: python -m venv .venv
    pause
    exit /b 1
)

echo [1/5] Activando entorno virtual...
call .venv\Scripts\activate.bat

echo.
echo [2/5] Instalando dependencias de audio Python...
pip install -r resources\setup\requirements_audio.txt

echo.
echo [3/5] Verificando FFmpeg...
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo [ADVERTENCIA] FFmpeg no esta instalado en el sistema
    echo.
    echo Por favor instala FFmpeg:
    echo   1. Con Chocolatey: choco install ffmpeg
    echo   2. Manual: https://ffmpeg.org/download.html
    echo.
    echo Presiona cualquier tecla para continuar sin FFmpeg...
    pause >nul
) else (
    echo [OK] FFmpeg esta instalado correctamente
)

echo.
echo [4/5] Instalando dependencias Node.js...
if exist "package.json" (
    call npm install
    echo [OK] Dependencias Node.js instaladas
) else (
    echo [ADVERTENCIA] No se encontro package.json
)

echo.
echo [5/5] Creando directorio de voces...
if not exist "resources\data\audio\voices" (
    mkdir resources\data\audio\voices
    echo [OK] Directorio creado: resources\data\audio\voices
) else (
    echo [OK] Directorio ya existe
)

echo.
echo ========================================
echo   INSTALACION COMPLETADA
echo ========================================
echo.
echo SIGUIENTE PASO:
echo Descarga una voz en español de Piper:
echo   1. Ve a: https://github.com/rhasspy/piper/releases/tag/v1.2.0
echo   2. Descarga: es_ES-claude-medium.onnx y es_ES-claude-medium.onnx.json
echo   3. Guardalos en: resources\data\audio\voices\
echo.
echo Para probar el sistema de audio:
echo   python raymundo.py
echo.
echo Para WhatsApp con audio:
echo   Terminal 1: python whatsapp_server.py
echo   Terminal 2: node whatsapp_bot.js
echo.
echo Lee AUDIO_INTEGRATION.md para mas informacion.
echo.
pause
