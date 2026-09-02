"""Exportacion del programa de tiempos a la maquina de disparo.

Los sistemas electronicos se programan desde un archivo que asocia cada
detonador con su tiempo. El formato exacto lo fija cada fabricante, asi que
aqui se generan dos salidas: una tabla completa para el area de operaciones y
un listado minimo —posicion y tiempo— que es lo que todos los equipos aceptan
como base.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from ..core import detonators as detdb
from ..core.charging import charge_units
from ..core.models import Hole


def _deck_rows(holes: Sequence[Hole]) -> List[Dict[str, object]]:
    """Una fila por detonador.

    Se cuenta por carga independiente, no por plataforma: la carga de fondo y
    la columna que va encima son continuas y llevan un solo cebo. Solo cuando
    un taco o una camara de aire las separa hacen falta dos detonadores.
    """
    rows: List[Dict[str, object]] = []
    for h in holes:
        units = charge_units(h)
        if not units:
            continue
        for i, unit in enumerate(units, start=1):
            productos = sorted({d.explosive for d in unit["decks"] if d.explosive})
            rows.append({
                "hid": h.hid,
                "deck": i if len(units) > 1 else 0,
                "delay_ms": round(h.delay_ms + float(unit["delay_ms"]), 3),
                "easting": h.easting,
                "northing": h.northing,
                "elevation": h.collar_z,
                "depth_m": round(h.length_m - float(unit["from_toe_m"])
                                 - float(unit["length_m"]), 2),
                "charge_kg": round(float(unit["mass_kg"]), 2),
                "explosive": " + ".join(productos),
                "primers": max(int(unit["primers"]), 1),
                "hole_type": h.hole_type,
            })
    rows.sort(key=lambda r: (r["delay_ms"], r["hid"]))
    return rows


def export_blast_machine(holes: Sequence[Hole], path: str | Path,
                         detonator: str = "i-kon II",
                         blast_name: str = "") -> Path:
    """Escribe el programa de tiempos completo, listo para revisar y cargar.

    Cada fila es un detonador, con su tiempo ya sumado al del taladro. Un
    taladro seccionado aporta tantas filas como cargas independientes tenga.
    """
    p = Path(path).with_suffix(".csv")
    det = detdb.get(detonator)
    rows = _deck_rows(holes)

    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["# Programa de tiempos X-BLAST"])
        w.writerow(["# Voladura", blast_name or "sin titulo"])
        w.writerow(["# Detonador", f"{det.name} ({det.manufacturer})"])
        w.writerow(["# Rango", f"{det.min_delay_ms:.0f} a {det.max_delay_ms:.0f} ms"])
        w.writerow(["# Incremento", f"{det.increment_ms:g} ms"])
        w.writerow(["# Detonadores", len(rows)])
        w.writerow(["# Generado", datetime.now().strftime("%d/%m/%Y %H:%M")])
        w.writerow([])
        w.writerow(["N", "ID", "PLATAFORMA", "RETARDO_MS", "ESTE", "NORTE", "COTA",
                    "PROFUNDIDAD_M", "CARGA_KG", "EXPLOSIVO", "CEBOS", "TIPO"])
        for n, r in enumerate(rows, start=1):
            w.writerow([
                n, r["hid"], r["deck"] or "", f"{r['delay_ms']:.1f}",
                f"{r['easting']:.3f}", f"{r['northing']:.3f}", f"{r['elevation']:.2f}",
                f"{r['depth_m']:.2f}", f"{r['charge_kg']:.1f}", r["explosive"],
                r["primers"], r["hole_type"],
            ])
    return p


def export_delay_list(holes: Sequence[Hole], path: str | Path) -> Path:
    """Listado minimo ``posicion, identificador, retardo`` para el equipo de campo."""
    p = Path(path).with_suffix(".csv")
    rows = _deck_rows(holes)
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=",")
        w.writerow(["POS", "ID", "DELAY_MS"])
        for n, r in enumerate(rows, start=1):
            label = r["hid"] if not r["deck"] else f"{r['hid']}-{r['deck']}"
            w.writerow([n, label, f"{r['delay_ms']:.0f}"])
    return p


def summary(holes: Sequence[Hole], detonator: str = "i-kon II") -> Dict[str, object]:
    """Resumen del programa: unidades, rango de tiempos y carga por evento."""
    rows = _deck_rows(holes)
    if not rows:
        return {"units": 0, "first_ms": 0.0, "last_ms": 0.0, "duration_ms": 0.0,
                "charge_kg": 0.0, "detonator": detonator}
    delays = [float(r["delay_ms"]) for r in rows]
    return {
        "units": len(rows),
        "first_ms": min(delays),
        "last_ms": max(delays),
        "duration_ms": max(delays) - min(delays),
        "charge_kg": sum(float(r["charge_kg"]) for r in rows),
        "decked_units": sum(1 for r in rows if r["deck"]),
        "detonator": detonator,
    }
