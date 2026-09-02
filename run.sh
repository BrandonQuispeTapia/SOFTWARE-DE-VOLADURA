#!/usr/bin/env bash
# Lanzador de X-BLAST para Linux y macOS.
set -euo pipefail

cd "$(dirname "$0")"

echo "======================================================================"
echo "  X-BLAST - Diseno, simulacion y optimizacion de voladura de rocas"
echo "  Universidad Nacional del Altiplano - Puno / Ingenieria de Minas"
echo "======================================================================"

if [ -x "venv/bin/python" ]; then
    PY="venv/bin/python"
elif [ -x ".venv/bin/python" ]; then
    PY=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PY="python3"
else
    echo "[ERROR] No se encontro Python 3.10 o superior." >&2
    exit 1
fi

echo "[INFO] Interprete: $PY"
exec "$PY" -m xblast
