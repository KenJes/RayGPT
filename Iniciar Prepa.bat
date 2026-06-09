@echo off
title Raymundo — Modo Prepa (Axoloit)
echo ========================================
echo    Iniciando Raymundo — Modo Prepa
echo ========================================
echo.
echo Personalidad: Agresivo-limpio, sin groserías
echo Publico: Jovenes 14-17 anos (preparatoria)
echo Tono: Directo, sarcastico, sin palabrotas
echo.

REM Evitar que tokens GitHub heredados bloqueen gh auth login / Copilot CLI
set GITHUB_TOKEN=
set GH_TOKEN=

REM Cerrar servidor Flask anterior si existe
echo Cerrando servidor Flask anterior...
taskkill /FI "WINDOWTITLE eq Servidor Flask*" /F >NUL 2>&1
timeout /t 2 /nobreak >nul

REM Establecer personalidad PREPA
set PERSONALITY_MODE=prepa

REM Iniciar Ollama en segundo plano si no está corriendo
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I "ollama.exe" >NUL
if %ERRORLEVEL% NEQ 0 (
    echo Iniciando Ollama en segundo plano...
    start "" /min ollama serve
    timeout /t 4 /nobreak >nul
)

REM Abrir servidor Python en una nueva ventana
start "Servidor Flask - Prepa" cmd /k "call .venv\Scripts\activate.bat && set PERSONALITY_MODE=prepa && python whatsapp_server.py"

REM Esperar 8 segundos para que el servidor inicie
echo Esperando a que el servidor Flask inicie...
timeout /t 8 /nobreak >nul

REM Abrir bot de WhatsApp
start "Bot WhatsApp - Prepa" cmd /k "cd resources\whatsapp && node whatsapp_bot.js"

echo.
echo ========================================
echo   Raymundo Prepa iniciado correctamente
echo ========================================
echo.
echo Servidor Flask: http://localhost:5000
echo Bot WhatsApp: Escanea el codigo QR
echo Comando para cambiar modo en WA: /prepa
echo.
echo Presiona cualquier tecla para cerrar esta ventana
pause >nul
