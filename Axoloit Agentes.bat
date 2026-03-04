@echo off
chcp 65001 >nul
title Axoloit Agents

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] No se encontro el entorno virtual .venv
    echo         Ejecuta primero: python -m venv .venv
    pause
    exit /b 1
)

start "" ".venv\Scripts\pythonw.exe" "agentes\axoloit_chat.py"
