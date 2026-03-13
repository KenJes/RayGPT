@echo off
echo ======================================================
echo   REINA - Raymundo's Enhanced Intelligent Neural Assistant
echo   Asistente de voz con voces neurales (Edge TTS)
echo ======================================================
call .venv\Scripts\activate.bat
python -m core.voice_assistant
pause
