@echo off
title Raymundo - Agente de IA de Axoloit
echo ========================================
echo     Iniciando Raymundo (Agente Pro)
echo ========================================
echo.
echo Personalidad: Agente profesional de Axoloit
echo Tono: Amable, competente, directo
echo.

REM Establecer personalidad RAYMUNDO
set PERSONALITY_MODE=raymundo

REM Abrir servidor Python en una nueva ventana
start "Servidor Flask - Raymundo" cmd /k "call .venv\Scripts\activate.bat && set PERSONALITY_MODE=raymundo && python whatsapp_server.py"

REM Esperar 8 segundos para que el servidor inicie
echo Esperando a que el servidor Flask inicie...
timeout /t 8 /nobreak >nul

REM Abrir bot de WhatsApp
start "Bot WhatsApp" cmd /k "cd resources\whatsapp && node whatsapp_bot.js"

echo.
echo ========================================
echo   Raymundo iniciado correctamente
echo ========================================
echo.
echo Servidor Flask: http://localhost:5000
echo Bot WhatsApp: Escanea el codigo QR
echo.
echo Presiona cualquier tecla para cerrar esta ventana
pause >nul
