@echo off
call .venv\Scripts\activate.bat

if "%1"=="--voice" (
    echo Iniciando R.E.I.N.A. en modo voz...
    python -m core.voice_assistant
) else (
    python raymundo.py
)
