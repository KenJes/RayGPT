@echo off
chcp 65001 >nul
color 0A

echo.
echo ═══════════════════════════════════════════════════════════════
echo   🤖 rAImundoGPT WhatsApp - Inicio Simple
echo ═══════════════════════════════════════════════════════════════
echo.
echo 🚀 Iniciando servicios...
echo.

REM Iniciar servidor Python
start "Servidor Python" cmd /k "color 0B && python whatsapp_server.py"

REM Esperar 2 segundos
timeout /t 2 >nul

REM Iniciar bot de WhatsApp
start "Bot WhatsApp" cmd /k "color 0E && node whatsapp_bot.js"

echo ✅ Servicios iniciados
echo.
echo 📱 Busca la ventana "Bot WhatsApp" y escanea el QR
echo.
pause
