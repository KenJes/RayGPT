@echo off
title Raymundo WhatsApp - Inicializador
echo ========================================
echo     Iniciando Raymundo WhatsApp Bot
echo ========================================
echo.
echo Abriendo servidor Flask y bot de WhatsApp...
echo.

REM Abrir servidor Python en una nueva ventana (con venv activado)
start "Servidor Flask" cmd /k "call .venv\Scripts\activate.bat && python whatsapp_server.py"

REM Esperar 8 segundos para que el servidor inicie completamente (carga Whisper, etc.)
echo Esperando a que el servidor Flask inicie completamente...
timeout /t 8 /nobreak >nul

REM Abrir bot de WhatsApp en otra ventana (desde carpeta resources/whatsapp)
start "Bot WhatsApp" cmd /k "cd resources\whatsapp && node whatsapp_bot.js"

echo.
echo ========================================
echo   Ambos procesos iniciados correctamente
echo ========================================
echo.
echo Servidor Flask: http://localhost:5000
echo Bot WhatsApp: Escanea el codigo QR
echo.
echo Presiona cualquier tecla para cerrar esta ventana
echo (Los procesos continuaran ejecutandose)
pause >nul
