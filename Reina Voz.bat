@echo off
echo ======================================================
echo   RAYMUNDO / REINA - Asistente de Voz
echo   Voces neurales Edge TTS (Jorge / Dalia)
echo   Arranca como Raymundo. Di "cambia a Reina" para switchear.
echo ======================================================
call .venv\Scripts\activate.bat
python -m core.voice_assistant
pause
