"""Secuencia de salida, amarre y analisis temporal.

Asigna tiempos de detonacion segun el patron de amarre elegido, simula la
dispersion del sistema de iniciacion, calcula la carga operante maxima por
ventana de cooperacion (MIC) y evalua el tiempo de alivio por metro de burden.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from .models import Hole, InitiationSystem, TimingParams

#: Patrones de amarre soportados.
TIE_PATTERNS = ["Fila por fila", "V (cuna)", "Diagonal (echelon)", "Eco / caja", "Punto central"]


# ---------------------------------------------------------------------------
# Asignacion de tiempos
# ---------------------------------------------------------------------------


def assign_delays(holes: Sequence[Hole], params: TimingParams,
                  face_azimuth_deg: float = 180.0) -> None:
    """Asigna ``delay_ms`` a cada taladro segun el patron de amarre."""
    if not holes:
        return

    az = math.radians(face_azimuth_deg)
    v = np.array([math.sin(az), math.cos(az)])   # hacia la cara libre
    u = np.array([v[1], -v[0]])                  # a lo largo de la fila

    pts = np.array([[h.easting, h.northing] for h in holes], float)
    origin = pts.mean(axis=0)
    local = pts - origin
    s_row = local @ u          # posicion a lo largo de la fila
    s_burden = -(local @ v)    # profundidad hacia el interior (0 en la cara)

    s_row = s_row - s_row.min()
    s_burden = s_burden - s_burden.min()

    pattern = params.pattern
    hd, rd = params.hole_delay_ms, params.row_delay_ms

    if pattern == "Fila por fila":
        t = s_burden * (rd / max(_median_step(s_burden), 1e-6)) + s_row * (hd / max(_median_step(s_row), 1e-6))

    elif pattern == "V (cuna)":
        center = s_row.mean()
        t = (np.abs(s_row - center) * (hd / max(_median_step(s_row), 1e-6))
             + s_burden * (rd / max(_median_step(s_burden), 1e-6)))

    elif pattern == "Diagonal (echelon)":
        ang = math.radians(params.echelon_deg)
        proj = s_row * math.cos(ang) + s_burden * math.sin(ang)
        t = proj * (hd / max(_median_step(s_row), 1e-6))

    elif pattern == "Eco / caja":
        t = (s_burden * (rd / max(_median_step(s_burden), 1e-6))
             + (s_row % max(_median_step(s_row), 1e-6)) * hd)
        order = np.argsort(s_row)
        t[order] += np.arange(len(order)) * hd * 0.15

    else:  # "Punto central"
        d = np.linalg.norm(local, axis=1)
        t = d * (hd / max(_median_step(s_row), 1e-6))

    t = t - t.min()
    for h, ti in zip(holes, t):
        h.delay_ms = float(round(ti, 1)) + params.in_hole_delay_ms

    simulate_scatter(holes, params)


def _median_step(values: np.ndarray) -> float:
    """Paso caracteristico de una coordenada discretizada (espaciamiento medio)."""
    u = np.unique(np.round(values, 2))
    if u.size < 2:
        return 1.0
    return float(np.median(np.diff(u)))


def simulate_scatter(holes: Sequence[Hole], params: TimingParams,
                     seed: Optional[int] = 42) -> None:
    """Aplica la dispersion del sistema de iniciacion a los tiempos nominales."""
    try:
        cv = InitiationSystem(params.system).scatter_pct
    except ValueError:
        cv = 0.03
    rng = np.random.default_rng(seed)
    for h in holes:
        sigma = max(h.delay_ms * cv, 0.05 if cv < 0.001 else 0.5)
        h.delay_actual_ms = float(h.delay_ms + rng.normal(0.0, sigma))


# ---------------------------------------------------------------------------
# Analisis
# ---------------------------------------------------------------------------


def cooperating_charge(holes: Sequence[Hole], window_ms: float = 8.0,
                       use_actual: bool = True) -> Dict[str, object]:
    """Carga operante maxima (MIC) dentro de una ventana deslizante.

    La regla de 8 ms de la USBM considera que cargas que detonan dentro de esa
    ventana cooperan sismicamente y deben sumarse para predecir vibraciones.
    """
    if not holes:
        return {"mic_kg": 0.0, "window_ms": window_ms, "t_start_ms": 0.0, "holes": []}

    t = np.array([h.delay_actual_ms if use_actual else h.delay_ms for h in holes], float)
    w = np.array([h.charge_kg for h in holes], float)
    order = np.argsort(t)
    t, w = t[order], w[order]

    best, best_i, best_j = 0.0, 0, 0
    j = 0
    run = 0.0
    for i in range(len(t)):
        while j < len(t) and t[j] - t[i] <= window_ms:
            run += w[j]
            j += 1
        if run > best:
            best, best_i, best_j = run, i, j
        run -= w[i]

    ids = [holes[order[k]].hid for k in range(best_i, best_j)]
    return {
        "mic_kg": float(best),
        "window_ms": window_ms,
        "t_start_ms": float(t[best_i]) if len(t) else 0.0,
        "n_cooperating": len(ids),
        "holes": ids,
    }


def relief_time_analysis(holes: Sequence[Hole], params: TimingParams) -> Dict[str, object]:
    """Tiempo de alivio por metro de burden y deteccion de secuencias criticas.

    Criterio practico: 3-6 ms/m entre taladros de una fila y 10-30 ms/m entre
    filas. Menos de 3 ms/m no da tiempo al movimiento del burden (confinamiento
    excesivo, vibracion alta); mas de 30 ms/m rompe la cooperacion entre cargas.
    """
    if not holes:
        return {}

    b = float(np.mean([h.burden_real_m for h in holes if h.burden_real_m > 0] or [1.0]))
    s = float(np.mean([h.spacing_real_m for h in holes if h.spacing_real_m > 0] or [1.0]))

    hole_ms_m = params.hole_delay_ms / max(s, 1e-6)
    row_ms_m = params.row_delay_ms / max(b, 1e-6)

    times = sorted(h.delay_ms for h in holes)
    total = times[-1] - times[0] if len(times) > 1 else 0.0
    gaps = np.diff(times) if len(times) > 1 else np.array([0.0])

    return {
        "hole_relief_ms_m": hole_ms_m,
        "row_relief_ms_m": row_ms_m,
        "total_duration_ms": total,
        "min_gap_ms": float(np.min(gaps)) if gaps.size else 0.0,
        "mean_gap_ms": float(np.mean(gaps)) if gaps.size else 0.0,
        "simultaneous_pairs": int(np.sum(gaps < 1.0)),
    }


def overlap_probability(holes: Sequence[Hole], params: TimingParams,
                        n_sim: int = 400, threshold_ms: float = 1.0,
                        seed: Optional[int] = 7) -> Dict[str, float]:
    """Probabilidad de solape por dispersion (Monte Carlo).

    Cada realizacion perturba los retardos nominales con el CV del sistema y
    cuenta cuantos pares consecutivos quedan a menos de ``threshold_ms``.
    """
    if len(holes) < 2:
        return {"p_overlap_pct": 0.0, "mean_overlaps": 0.0, "p_out_of_sequence_pct": 0.0}

    try:
        cv = InitiationSystem(params.system).scatter_pct
    except ValueError:
        cv = 0.03

    nominal = np.array([h.delay_ms for h in holes], float)
    order = np.argsort(nominal)
    nominal = nominal[order]
    sigma = np.maximum(nominal * cv, 0.05 if cv < 0.001 else 0.5)

    rng = np.random.default_rng(seed)
    overlaps = np.zeros(n_sim)
    out_of_seq = np.zeros(n_sim, bool)

    for k in range(n_sim):
        t = nominal + rng.normal(0.0, sigma)
        d = np.diff(np.sort(t))
        overlaps[k] = int(np.sum(d < threshold_ms))
        out_of_seq[k] = bool(np.any(np.diff(t) < 0))

    return {
        "p_overlap_pct": float(np.mean(overlaps > 0) * 100.0),
        "mean_overlaps": float(np.mean(overlaps)),
        "p_out_of_sequence_pct": float(np.mean(out_of_seq) * 100.0),
        "scatter_cv_pct": cv * 100.0,
    }


def timing_histogram(holes: Sequence[Hole], bin_ms: float = 8.0) -> Tuple[np.ndarray, np.ndarray]:
    """Histograma de carga detonada por ventana temporal."""
    if not holes:
        return np.array([0.0]), np.array([0.0])
    t = np.array([h.delay_actual_ms for h in holes], float)
    w = np.array([h.charge_kg for h in holes], float)
    edges = np.arange(t.min(), t.max() + bin_ms * 1.5, bin_ms)
    hist, _ = np.histogram(t, bins=edges, weights=w)
    return edges[:-1], hist


def audit_timing(holes: Sequence[Hole], params: TimingParams) -> List[Dict[str, str]]:
    """Revision de la secuencia contra criterios de buena practica."""
    out: List[Dict[str, str]] = []
    if not holes:
        return out

    rel = relief_time_analysis(holes, params)
    h_ms = rel.get("hole_relief_ms_m", 0.0)
    r_ms = rel.get("row_relief_ms_m", 0.0)

    if h_ms < 2.5:
        out.append({"level": "error", "item": "Retardo entre taladros",
                    "message": f"{h_ms:.1f} ms/m (< 2.5). Cargas practicamente simultaneas: "
                               "vibracion elevada y fragmentacion pobre."})
    elif h_ms > 10.0:
        out.append({"level": "warn", "item": "Retardo entre taladros",
                    "message": f"{h_ms:.1f} ms/m (> 10). Se pierde la interaccion entre cargas vecinas."})
    else:
        out.append({"level": "ok", "item": "Retardo entre taladros",
                    "message": f"{h_ms:.1f} ms/m — dentro de 3-6 ms/m recomendado."})

    if r_ms < 8.0:
        out.append({"level": "error", "item": "Retardo entre filas",
                    "message": f"{r_ms:.1f} ms/m (< 8). El burden de la fila previa no alcanza a moverse: "
                               "confinamiento, sobre-rotura y riesgo de tiros soplados."})
    elif r_ms > 35.0:
        out.append({"level": "warn", "item": "Retardo entre filas",
                    "message": f"{r_ms:.1f} ms/m (> 35). Secuencia muy lenta; puede producirse corte de linea."})
    else:
        out.append({"level": "ok", "item": "Retardo entre filas",
                    "message": f"{r_ms:.1f} ms/m — dentro de 10-30 ms/m recomendado."})

    ov = overlap_probability(holes, params)
    if ov["p_overlap_pct"] > 25.0:
        out.append({"level": "warn", "item": "Dispersion de retardos",
                    "message": f"Probabilidad de solape {ov['p_overlap_pct']:.0f}% con "
                               f"CV = {ov['scatter_cv_pct']:.1f}%. Considere iniciacion electronica."})
    if ov["p_out_of_sequence_pct"] > 5.0:
        out.append({"level": "error", "item": "Salida fuera de secuencia",
                    "message": f"{ov['p_out_of_sequence_pct']:.0f}% de las simulaciones invierten el orden de salida."})

    return out
