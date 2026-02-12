@echo off
echo ========================================
echo   INSTALAR VOZ RAUL (Español México)
echo ========================================
echo.
echo Este script abrirá la configuración de Windows
echo para que instales la voz masculina "Raúl"
echo.
echo PASOS A SEGUIR:
echo.
echo 1. Se abrirá "Configuración de Windows"
echo 2. Busca "Español (México)" en la lista
echo 3. Haz click en "Opciones"
echo 4. En "Voz", haz click en "+ Agregar voces"
echo 5. Busca y descarga "Raúl" (voz masculina)
echo 6. Espera a que termine la descarga (1-2 min)
echo 7. Cierra esta ventana y reinicia el servidor
echo.
echo Presiona cualquier tecla para abrir Configuración...
pause >nul

REM Abrir configuración de idioma y voz
start ms-settings:regionlanguage

echo.
echo ✅ Configuración abierta
echo.
echo Cuando termines de instalar la voz:
echo 1. Reinicia el servidor: .\Iniciar WhatsApp.bat
echo 2. La voz de Raúl será detectada automáticamente
echo.
pause
