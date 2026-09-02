#!/usr/bin/env bash
# X-BLAST Enterprise v2.0 - Launcher for Linux / macOS
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "======================================================================"
echo "          X-BLAST Enterprise v2.0 - Sistema de Perforacion y Voladura"
echo "                  Universidad Nacional del Altiplano - Puno"
echo "======================================================================"
echo

PY_EXE=""
if [ -f "venv/bin/python" ]; then
    PY_EXE="venv/bin/python"
elif [ -f ".venv/bin/python" ]; then
    PY_EXE=".venv/bin/python"
elif [ -f "VOLADURA_PRO_10X/venv/bin/python" ]; then
    PY_EXE="VOLADURA_PRO_10X/venv/bin/python"
elif command -v python3 &>/dev/null; then
    PY_EXE="python3"
elif command -v python &>/dev/null; then
    PY_EXE="python"
fi

if [ -z "$PY_EXE" ]; then
    echo "[ERROR] Python 3 no se encuentra instalado en el sistema."
    exit 1
fi

echo "[INFO] Iniciando X-BLAST con $PY_EXE..."
cd "$SCRIPT_DIR/VOLADURA_PRO_10X"
"$PY_EXE" main.py
