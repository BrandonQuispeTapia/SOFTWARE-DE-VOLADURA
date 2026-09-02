@echo off
setlocal enabledelayedexpansion
title X-BLAST Enterprise v2.0 - PERVOL
cd /d "%~dp0"

echo ======================================================================
echo           X-BLAST Enterprise v2.0 - Sistema de Perforacion y Voladura
echo                   Universidad Nacional del Altiplano - Puno
echo ======================================================================
echo.

set "PY_EXE="

:: 1. Buscar en entornos virtuales locales o de la raiz
if exist "venv\Scripts\python.exe" set "PY_EXE=venv\Scripts\python.exe"
if not defined PY_EXE if exist ".venv\Scripts\python.exe" set "PY_EXE=.venv\Scripts\python.exe"
if not defined PY_EXE if exist "..\venv\Scripts\python.exe" set "PY_EXE=..\venv\Scripts\python.exe"
if not defined PY_EXE if exist "..\.venv\Scripts\python.exe" set "PY_EXE=..\.venv\Scripts\python.exe"

:: 2. Buscar en Python global
if not defined PY_EXE (
    where python >nul 2>&1
    if not errorlevel 1 set "PY_EXE=python"
)

if not defined PY_EXE (
    echo [ERROR] No se detecto ninguna instalacion de Python ni entorno virtual.
    echo Por favor instala Python 3.10 o superior y agrega Python a la variable PATH.
    echo.
    pause
    exit /b 1
)

echo [INFO] Iniciando aplicacion con: !PY_EXE!
echo.
"!PY_EXE!" "main.py"

if errorlevel 1 (
    echo.
    echo [AVISO] La aplicacion se cerro con codigo de error %errorlevel%.
    echo Si faltan dependencias, ejecuta: pip install -r ..\requirements.txt
    echo.
    pause
)