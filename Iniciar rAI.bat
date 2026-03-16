@echo off
title rAI - El Compa Culero
echo ========================================
echo     Iniciando rAI (El Compa Cabron)
echo ========================================
echo.
echo Personalidad: Despota, clasista, racista, chistoso
echo Tono: Agresivo, sin filtros, humor negro
echo.

REM Establecer personalidad RAI
set PERSONALITY_MODE=rai

REM Abrir servidor Python en una nueva ventana
start "Servidor Flask - rAI" cmd /k "call .venv\Scripts\activate.bat && set PERSONALITY_MODE=rai && python whatsapp_server.py"

REM Esperar 8 segundos para que el servidor inicie
echo Esperando a que el servidor Flask inicie...
timeout /t 8 /nobreak >nul

REM Abrir bot de WhatsApp
start "Bot WhatsApp" cmd /k "cd resources\whatsapp && node whatsapp_bot.js"

echo.
echo ========================================
echo   rAI iniciado correctamente
echo ========================================
echo.
echo Servidor Flask: http://localhost:5000
echo Bot WhatsApp: Escanea el codigo QR
echo.
echo Presiona cualquier tecla para cerrar esta ventana
pause >nul
