@echo off
chcp 65001 >nul
color 0A

REM ============================================
REM  rAImundoGPT WhatsApp - Launcher Automático
REM ============================================

echo.
echo ═══════════════════════════════════════════════════════════════════════════════
echo   🤖 rAImundoGPT WhatsApp Bot - Launcher
echo ═══════════════════════════════════════════════════════════════════════════════
echo.

REM Verificar Node.js
echo [1/4] Verificando Node.js...
where node >nul 2>&1
if errorlevel 1 goto error_node
node --version
echo ✅ Node.js encontrado
echo.

REM Verificar Python
echo [2/4] Verificando Python...
where python >nul 2>&1
if errorlevel 1 goto error_python
python --version
echo ✅ Python encontrado
echo.

REM Verificar dependencias Node.js
echo [3/4] Verificando dependencias Node.js...
if not exist "node_modules\" (
    echo ⚠️  Dependencias no encontradas
    echo 📦 Instalando dependencias...
    echo.
    call npm install
    if errorlevel 1 goto error_npm
    echo ✅ Dependencias instaladas
) else (
    echo ✅ Dependencias encontradas
)
echo.

REM Verificar dependencias Python
echo [4/4] Verificando dependencias Python...
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo ⚠️  Flask no encontrado
    echo 📦 Instalando Flask y Flask-CORS...
    python -m pip install flask flask-cors
    if errorlevel 1 goto error_pip
    echo ✅ Flask instalado
) else (
    echo ✅ Flask encontrado
)
echo.

echo ═══════════════════════════════════════════════════════════════════════════════
echo   ✅ Todas las verificaciones pasaron
echo ═══════════════════════════════════════════════════════════════════════════════
echo.
echo 🚀 Iniciando servicios en 3 segundos...
echo.
echo    💡 Se abrirán 2 ventanas:
echo       - Terminal 1: Servidor Python Flask
echo       - Terminal 2: Bot de WhatsApp Node.js
echo.
echo    ⚠️  NO CIERRES LAS VENTANAS
echo.
timeout /t 3 >nul

REM Iniciar servidor Python en nueva ventana
start "rAImundoGPT - Servidor Python" cmd /k "color 0B && python whatsapp_server.py"

REM Esperar 2 segundos
timeout /t 2 >nul

REM Iniciar bot de WhatsApp en nueva ventana
start "rAImundoGPT - Bot WhatsApp" cmd /k "color 0E && node whatsapp_bot.js"

echo.
echo ═══════════════════════════════════════════════════════════════════════════════
echo   ✅ Servicios iniciados
echo ═══════════════════════════════════════════════════════════════════════════════
echo.
echo 📱 PRÓXIMOS PASOS:
echo.
echo    1. Busca la ventana Bot WhatsApp
echo    2. Escanea el código QR con WhatsApp
echo    3. Listo! Prueba mandando un mensaje
echo.
echo 💬 CÓMO USAR:
echo.
echo    En grupos:        raymundo que es python?
echo    Mensajes privados: Solo escribe tu pregunta
echo.
echo ⏹️  PARA DETENER: Cierra ambas ventanas
echo.
echo ═══════════════════════════════════════════════════════════════════════════════
echo.
pause
exit /b 0

:error_node
echo ❌ ERROR: Node.js no instalado
echo.
echo 💡 Descarga desde: https://nodejs.org/
echo.
pause
exit /b 1

:error_python
echo ❌ ERROR: Python no encontrado
echo.
pause
exit /b 1

:error_npm
echo ❌ Error instalando dependencias Node.js
pause
exit /b 1

:error_pip
echo ❌ Error instalando dependencias Python
echo.
echo 💡 Intenta manualmente:
echo    python -m pip install flask flask-cors
echo.
pause
exit /b 1
