@echo off
echo ======================================================
echo   RAYMUNDO VISION - Asistente de Voz + DeepFace
echo   Camara en tiempo real: edad, genero, emocion, raza
echo   Raymundo comenta lo que ve cada ~20 segundos
echo ======================================================
echo.
echo   Requisitos: pip install deepface
echo   (TensorFlow se instala automaticamente con deepface)
echo.
set GITHUB_TOKEN=
set GH_TOKEN=
call .venv\Scripts\activate.bat
python -m core.voice_assistant --vision
pause
