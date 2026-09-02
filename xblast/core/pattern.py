"""Generacion de mallas y formulas clasicas de dimensionamiento.

Incluye:
    * generacion de mallas cuadradas, rectangulares y al tresbolillo,
      orientadas segun el azimut de la cara libre;
    * proyeccion de collares sobre topografia real;
    * dimensionamiento automatico por Konya-Walter, Langefors-Kihlstrom,
      Ash y Pearse, con comparacion y recomendacion.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional

import numpy as np

from . import explosives as exdb
from .models import Deck, DeckKind, Hole, HoleType, PatternParams, PatternType, RockMass

# ---------------------------------------------------------------------------
# Generacion de malla
# ---------------------------------------------------------------------------


def generate_pattern(
    params: PatternParams,
    hole_type: str = HoleType.PRODUCCION.value,
    elevation_fn=None,
) -> List[Hole]:
    """Construye los taladros de la malla.

    Args:
        params: parametros geometricos.
        hole_type: tipo asignado por defecto a todos los taladros.
        elevation_fn: ``f(x, y) -> z`` opcional para apoyar los collares sobre
            la topografia real. Si es ``None`` se usa ``params.origin_z``.

    Returns:
        Lista de :class:`Hole` sin carga asignada.
    """
    holes: List[Hole] = []

    # Sistema local: +v apunta hacia la cara libre (direccion de salida),
    # +u es perpendicular (a lo largo de las filas).
    az = math.radians(params.face_azimuth_deg)
    v = np.array([math.sin(az), math.cos(az)])       # avance del disparo
    u = np.array([v[1], -v[0]])                      # a lo largo de la fila

    stagger = params.pattern == PatternType.TRESBOLILLO.value
    origin = np.array([params.origin_x, params.origin_y])
    n = 0

    for r in range(params.rows):
        offset = 0.5 * params.spacing_m if (stagger and r % 2) else 0.0
        for c in range(params.cols):
            n += 1
            xy = origin + u * (c * params.spacing_m + offset) - v * (r * params.burden_m)
            z = params.origin_z if elevation_fn is None else float(elevation_fn(xy[0], xy[1]))

            holes.append(
                Hole(
                    hid=f"{r + 1:02d}-{c + 1:02d}",
                    easting=float(xy[0]),
                    northing=float(xy[1]),
                    collar_z=z,
                    length_m=params.hole_length_m,
                    diameter_mm=params.diameter_mm,
                    dip_deg=params.dip_deg,
                    azimuth_deg=(params.face_azimuth_deg + 180.0) % 360.0,
                    subdrill_m=params.subdrill_m,
                    bench_height_m=params.bench_height_m,
                    hole_type=hole_type,
                    row=r,
                    col=c,
                    burden_real_m=params.burden_m,
                    spacing_real_m=params.spacing_m,
                )
            )
    return holes


def free_face_from_pattern(params: PatternParams, margin: float = 1.0) -> np.ndarray:
    """Polilinea de la cara libre implicita de una malla parametrica."""
    az = math.radians(params.face_azimuth_deg)
    v = np.array([math.sin(az), math.cos(az)])
    u = np.array([v[1], -v[0]])
    origin = np.array([params.origin_x, params.origin_y])
    width = params.spacing_m * (params.cols - 1)
    p0 = origin - u * params.spacing_m + v * params.burden_m * margin
    p1 = origin + u * (width + params.spacing_m) + v * params.burden_m * margin
    return np.vstack([p0, p1])


def apply_topography(holes: List[Hole], elevation_fn, keep_toe_level: bool = True) -> None:
    """Reproyecta collares sobre la topografia manteniendo la cota de piso.

    Con ``keep_toe_level`` la longitud de cada taladro se ajusta para que todos
    los fondos queden a la misma cota (piso de banco + subperforacion), que es
    la practica real en banco.
    """
    if not holes:
        return
    toe_target = min(h.collar_z - h.length_m * math.sin(math.radians(h.dip_deg)) for h in holes)
    for h in holes:
        z = elevation_fn(h.easting, h.northing)
        if z is None or not np.isfinite(z):
            continue
        h.collar_z = float(z)
        if keep_toe_level:
            drop = h.collar_z - toe_target
            sin_dip = max(math.sin(math.radians(h.dip_deg)), 0.15)
            h.length_m = max(1.0, drop / sin_dip)
            h.bench_height_m = max(1.0, drop - h.subdrill_m)


# ---------------------------------------------------------------------------
# Formulas de dimensionamiento
# ---------------------------------------------------------------------------


def konya_burden(diameter_mm: float, rho_exp: float, rho_rock_t_m3: float) -> float:
    """Burden de Konya-Walter (1972): B = 0.012 (2*SGe/SGr + 1.5) * De."""
    return 0.012 * (2.0 * rho_exp / rho_rock_t_m3 + 1.5) * diameter_mm


def konya_stemming(burden_m: float) -> float:
    """Taco recomendado T = 0.7 B."""
    return 0.7 * burden_m


def konya_subdrill(burden_m: float) -> float:
    """Subperforacion J = 0.3 B."""
    return 0.3 * burden_m


def konya_spacing(burden_m: float, bench_h: float, instantaneous: bool = False) -> float:
    """Espaciamiento de Konya en funcion de la relacion de rigidez H/B."""
    ratio = bench_h / max(burden_m, 1e-6)
    if ratio < 4.0:
        if instantaneous:
            return burden_m * (bench_h + 2.0 * burden_m) / (3.0 * burden_m)
        return burden_m * (bench_h + 7.0 * burden_m) / 8.0
    return burden_m * (2.0 if instantaneous else 1.4)


def langefors_burden(
    diameter_mm: float, rho_exp: float, rws: float, rock_constant_c: float = 0.4,
    s_b_ratio: float = 1.25, fixation: float = 0.95,
) -> float:
    """Burden maximo de Langefors-Kihlstrom (1963).

    B_max = (d/33) * sqrt( (rho_e * s) / (c * f * (S/B)) )   [d en mm]
    """
    s = rws / 100.0
    c = rock_constant_c + 0.05
    denom = max(c * fixation * s_b_ratio, 1e-6)
    return (diameter_mm / 33.0) * math.sqrt((rho_exp * s) / denom)


def ash_burden(diameter_mm: float, kb: float = 25.0) -> float:
    """Regla de Ash (1963): B = Kb * De / 39.37  (Kb 20-40 segun roca)."""
    return kb * (diameter_mm / 25.4) * 0.0254


def pearse_burden(diameter_mm: float, pressure_gpa: float, ucs_mpa: float, k: float = 1.0) -> float:
    """Formula de Pearse: B = k * De * sqrt(Pd / UCS)  (unidades coherentes)."""
    pd_mpa = pressure_gpa * 1000.0
    return k * (diameter_mm / 1000.0) * math.sqrt(max(pd_mpa, 1.0) / max(ucs_mpa, 1.0))


def recommend_geometry(
    diameter_mm: float,
    rock: RockMass,
    explosive_name: str,
    bench_height_m: float,
    pattern: str = PatternType.TRESBOLILLO.value,
) -> Dict[str, object]:
    """Compara las formulas clasicas y devuelve una recomendacion consensuada.

    Se descartan los valores atipicos (fuera de 1.5 desviaciones) y se promedia
    el resto, corrigiendo por relacion de rigidez H/B >= 2.
    """
    exp = exdb.get(explosive_name)
    rho_e = exp.density_g_cm3

    candidates = {
        "Konya-Walter": konya_burden(diameter_mm, rho_e, rock.density_t_m3),
        "Langefors-Kihlstrom": langefors_burden(diameter_mm, rho_e, exp.rws),
        "Ash": ash_burden(diameter_mm, kb=_ash_kb(rock)),
        "Pearse": pearse_burden(diameter_mm, exp.borehole_pressure_gpa(), rock.ucs_mpa),
    }

    vals = np.array(list(candidates.values()), float)
    med = float(np.median(vals))
    mad = float(np.median(np.abs(vals - med))) or 1e-3
    kept = vals[np.abs(vals - med) <= 2.0 * mad]
    burden = float(np.mean(kept)) if kept.size else med

    # Correccion por rigidez: H/B minimo 2.0 evita fragmentacion gruesa y sobre-rotura
    if bench_height_m / max(burden, 1e-6) < 2.0:
        burden = bench_height_m / 2.0

    if pattern == PatternType.CUADRADA.value:
        spacing = burden
    elif pattern == PatternType.TRESBOLILLO.value:
        spacing = burden * 1.15
    else:
        spacing = konya_spacing(burden, bench_height_m)

    stemming = konya_stemming(burden)
    subdrill = konya_subdrill(burden)

    return {
        "candidates": {k: round(v, 2) for k, v in candidates.items()},
        "burden_m": round(burden, 2),
        "spacing_m": round(spacing, 2),
        "stemming_m": round(stemming, 2),
        "subdrill_m": round(subdrill, 2),
        "stiffness_ratio": round(bench_height_m / max(burden, 1e-6), 2),
        "s_b_ratio": round(spacing / max(burden, 1e-6), 2),
        "rock_factor_a": round(rock.rock_factor_a, 2),
        "blastability_index": round(rock.blastability_index, 1),
    }


def _ash_kb(rock: RockMass) -> float:
    """Kb de Ash segun dureza: roca blanda 30-35, media 25-30, dura 20-25."""
    if rock.ucs_mpa < 60:
        return 32.0
    if rock.ucs_mpa < 120:
        return 27.0
    if rock.ucs_mpa < 200:
        return 23.0
    return 20.0


# ---------------------------------------------------------------------------
# Diagnostico geometrico
# ---------------------------------------------------------------------------


def audit_geometry(params: PatternParams) -> List[Dict[str, str]]:
    """Revision de buenas practicas; devuelve hallazgos con severidad."""
    out: List[Dict[str, str]] = []

    def add(level: str, item: str, msg: str) -> None:
        out.append({"level": level, "item": item, "message": msg})

    hb = params.stiffness_ratio
    if hb < 2.0:
        add("error", "Relacion de rigidez H/B",
            f"H/B = {hb:.2f} (< 2). Banco rigido: fragmentacion gruesa, "
            "sobre-rotura en el piso y alto riesgo de proyeccion. Reduzca el burden.")
    elif hb < 3.0:
        add("warn", "Relacion de rigidez H/B",
            f"H/B = {hb:.2f}. Aceptable pero por debajo del optimo (>= 3).")
    else:
        add("ok", "Relacion de rigidez H/B", f"H/B = {hb:.2f}. Adecuada.")

    sb = params.s_b_ratio
    if sb < 1.0:
        add("warn", "Relacion S/B", f"S/B = {sb:.2f} (< 1). Malla sobre-perforada en el eje de la fila.")
    elif sb > 1.8:
        add("warn", "Relacion S/B", f"S/B = {sb:.2f} (> 1.8). Riesgo de bolones entre taladros.")
    else:
        add("ok", "Relacion S/B", f"S/B = {sb:.2f}. Dentro del rango recomendado (1.0 - 1.8).")

    t_b = params.stemming_m / max(params.burden_m, 1e-6)
    if t_b < 0.5:
        add("error", "Taco",
            f"T/B = {t_b:.2f}. Taco insuficiente: alto riesgo de proyeccion (flyrock) y "
            "onda aerea excesiva.")
    elif t_b > 1.2:
        add("warn", "Taco", f"T/B = {t_b:.2f}. Taco excesivo: bolones en la parte alta del banco.")
    else:
        add("ok", "Taco", f"T/B = {t_b:.2f}. Correcto (0.5 - 1.2).")

    j_b = params.subdrill_m / max(params.burden_m, 1e-6)
    if j_b < 0.15:
        add("warn", "Subperforacion", f"J/B = {j_b:.2f}. Riesgo de lomos (toe) en el piso del banco.")
    elif j_b > 0.5:
        add("warn", "Subperforacion",
            f"J/B = {j_b:.2f}. Exceso de subperforacion: dano al banco inferior y costo innecesario.")
    else:
        add("ok", "Subperforacion", f"J/B = {j_b:.2f}. Correcto (0.15 - 0.50).")

    d_b = params.burden_m / (params.diameter_mm / 1000.0)
    if d_b > 40:
        add("warn", "Burden / diametro",
            f"B/D = {d_b:.0f}. Burden alto para el diametro: energia insuficiente en el frente.")
    elif d_b < 20:
        add("warn", "Burden / diametro", f"B/D = {d_b:.0f}. Burden corto: sobre-consumo de explosivo.")
    else:
        add("ok", "Burden / diametro", f"B/D = {d_b:.0f}. Correcto (20 - 40).")

    return out
