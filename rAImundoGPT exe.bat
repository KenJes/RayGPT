@echo off
cd /d "%~dp0"
set GITHUB_TOKEN=
set GH_TOKEN=
call .venv\Scripts\activate.bat

REM Iniciar Ollama en segundo plano si no está corriendo
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I "ollama.exe" >NUL
if %ERRORLEVEL% NEQ 0 (
    echo Iniciando Ollama en segundo plano...
    start "" /min ollama serve
    timeout /t 4 /nobreak >nul
)

if "%1"=="--voice" (
    echo Iniciando R.E.I.N.A. en modo voz...
    python -m core.voice_assistant
) else (
    python raymundo.py
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ========================================
    echo   ERROR al iniciar Raymundo
    echo   Revisa: data\raymundo_error.log
    echo ========================================
    pause
)
