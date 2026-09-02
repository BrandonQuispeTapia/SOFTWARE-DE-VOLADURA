@echo off
setlocal enabledelayedexpansion
title X-BLAST - Blast Design ^& Optimization Suite
cd /d "%~dp0"

echo ======================================================================
echo   X-BLAST - Diseno, simulacion y optimizacion de voladura de rocas
echo   Universidad Nacional del Altiplano - Puno / Ingenieria de Minas
echo ======================================================================
echo.

set "PY_EXE="
if exist "%~dp0venv\Scripts\python.exe"  set "PY_EXE=%~dp0venv\Scripts\python.exe"
if not defined PY_EXE if exist "%~dp0.venv\Scripts\python.exe" set "PY_EXE=%~dp0.venv\Scripts\python.exe"
if not defined PY_EXE (
    where python >nul 2>&1
    if not errorlevel 1 set "PY_EXE=python"
)

if not defined PY_EXE (
    echo [ERROR] No se encontro Python. Instale Python 3.10 o superior
    echo         y asegurese de agregarlo al PATH.
    echo.
    pause
    exit /b 1
)

echo [INFO] Interprete: !PY_EXE!
echo [INFO] Iniciando la aplicacion...
echo.

"!PY_EXE!" -m xblast

if errorlevel 1 (
    echo.
    echo [AVISO] La aplicacion termino con codigo %errorlevel%.
    echo         Si faltan dependencias ejecute:  pip install -r requirements.txt
    echo.
    pause
)
