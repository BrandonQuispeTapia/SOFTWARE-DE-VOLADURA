"""Prediccion de vibraciones y onda aerea.

Modelos incluidos:

* **Distancia escalada** (USBM / raiz cuadrada y raiz cubica) para campo lejano.
* **Holmberg-Persson** para campo cercano, integrando la carga distribuida a lo
  largo de la columna — indispensable para evaluar dano al talud remanente.
* **Superposicion de onda semilla (signature hole)**: sintetiza la historia
  temporal de la voladura completa sumando la respuesta de cada taladro
  desplazada por su retardo real, que es el metodo usado para optimizar
  secuencias contra un limite de PPV.
* Criterios normativos USBM RI8507 y DIN 4150-3.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from .models import Hole, SiteConstraints

# ---------------------------------------------------------------------------
# Campo lejano — distancia escalada
# ---------------------------------------------------------------------------


def scaled_distance(distance_m: float, charge_kg: float, cube_root: bool = False) -> float:
    """Distancia escalada SD = D / W^(1/2) (o W^(1/3))."""
    w = max(charge_kg, 1e-6)
    return distance_m / (w ** (1.0 / 3.0) if cube_root else math.sqrt(w))


def ppv_scaled(distance_m: float, charge_kg: float, k: float = 1140.0,
               beta: float = 1.6, cube_root: bool = False) -> float:
    """PPV [mm/s] = K * SD^(-beta)."""
    sd = scaled_distance(distance_m, charge_kg, cube_root)
    return float(k * sd ** (-beta)) if sd > 0 else 0.0


def max_charge_for_ppv(distance_m: float, ppv_limit_mm_s: float, k: float = 1140.0,
                       beta: float = 1.6, cube_root: bool = False) -> float:
    """Carga operante maxima admisible para no superar un limite de PPV."""
    if ppv_limit_mm_s <= 0 or k <= 0:
        return 0.0
    sd_req = (k / ppv_limit_mm_s) ** (1.0 / beta)
    exp = 3.0 if cube_root else 2.0
    return float((distance_m / sd_req) ** exp)


# ---------------------------------------------------------------------------
# Campo cercano — Holmberg-Persson
# ---------------------------------------------------------------------------


def ppv_holmberg_persson(
    k: float, alpha: float, beta: float, linear_charge_kg_m: float,
    charge_length_m: float, radial_dist_m: float, offset_m: float = 0.0,
    n_steps: int = 200,
) -> float:
    """PPV [mm/s] por integracion de la carga a lo largo de la columna.

    PPV = K * [ q * integral( dz / R^(beta/alpha) ) ]^alpha
    con R la distancia del punto al elemento de carga dz.
    """
    if charge_length_m <= 0 or linear_charge_kg_m <= 0:
        return 0.0
    r = max(radial_dist_m, 0.25)
    z = np.linspace(offset_m, offset_m + charge_length_m, n_steps)
    dz = charge_length_m / n_steps
    R = np.sqrt(r ** 2 + z ** 2)
    integral = float(np.sum(dz / np.power(R, beta / max(alpha, 1e-6))))
    return float(k * (linear_charge_kg_m * integral) ** alpha)


def damage_radius(
    k: float, alpha: float, beta: float, linear_charge_kg_m: float,
    charge_length_m: float, ppv_critical_mm_s: float,
    r_max: float = 60.0, n: int = 240,
) -> float:
    """Radio a partir del cual el PPV cae bajo el umbral de dano."""
    radii = np.linspace(0.3, r_max, n)
    for r in radii:
        if ppv_holmberg_persson(k, alpha, beta, linear_charge_kg_m,
                                charge_length_m, float(r)) < ppv_critical_mm_s:
            return float(r)
    return float(r_max)


def critical_ppv(ucs_mpa: float, young_gpa: float, p_wave_m_s: float) -> Dict[str, float]:
    """Umbrales de dano derivados de la resistencia a la traccion.

    PPV_c = (sigma_t * Vp) / E, con sigma_t ~ UCS/12.
    """
    sigma_t = ucs_mpa / 12.0 * 1e6            # Pa
    e = max(young_gpa, 1.0) * 1e9             # Pa
    ppv_c = sigma_t * p_wave_m_s / e * 1000.0  # mm/s
    return {
        "ppv_incipiente_mm_s": ppv_c * 0.25,
        "ppv_fisuras_mm_s": ppv_c,
        "ppv_fracturamiento_mm_s": ppv_c * 4.0,
        "tensile_strength_mpa": sigma_t / 1e6,
    }


# ---------------------------------------------------------------------------
# Superposicion de onda semilla
# ---------------------------------------------------------------------------


def seed_waveform(duration_ms: float = 80.0, dt_ms: float = 0.25,
                  freq_hz: float = 30.0, damping: float = 22.0) -> Tuple[np.ndarray, np.ndarray]:
    """Onda semilla normalizada (respuesta de un taladro aislado).

    Se modela como una sinusoide amortiguada, forma habitual del registro de
    un signature hole en roca competente.
    """
    t = np.arange(0.0, duration_ms, dt_ms)
    s = np.exp(-damping * t / 1000.0) * np.sin(2.0 * math.pi * freq_hz * t / 1000.0)
    peak = np.max(np.abs(s)) or 1.0
    return t, s / peak


def superpose(
    holes: Sequence[Hole], receptor: np.ndarray, cons: SiteConstraints,
    dt_ms: float = 0.25, freq_hz: float = 30.0, cube_root: bool = False,
) -> Dict[str, object]:
    """Historia temporal de vibracion por superposicion lineal.

    Cada taladro aporta la onda semilla escalada por su PPV individual y
    desplazada por su tiempo real de detonacion. El maximo del registro
    resultante es la PPV predicha de la voladura completa.
    """
    if not holes:
        return {"t_ms": np.array([0.0]), "ppv_mm_s": np.array([0.0]),
                "ppv_max_mm_s": 0.0, "t_peak_ms": 0.0, "freq_hz": freq_hz}

    tw, sw = seed_waveform(freq_hz=freq_hz, dt_ms=dt_ms)
    t_end = max(h.delay_actual_ms for h in holes) + tw[-1] + 10.0
    t = np.arange(0.0, t_end, dt_ms)
    trace = np.zeros_like(t)

    for h in holes:
        if h.charge_kg <= 0:
            continue
        d = float(np.linalg.norm(np.array([h.easting, h.northing, h.collar_z]) - receptor))
        amp = ppv_scaled(max(d, 1.0), h.charge_kg, cons.k_site, cons.beta_site, cube_root)
        i0 = int(max(h.delay_actual_ms, 0.0) / dt_ms)
        i1 = min(i0 + len(sw), len(trace))
        if i1 > i0:
            trace[i0:i1] += amp * sw[: i1 - i0]

    idx = int(np.argmax(np.abs(trace)))
    return {
        "t_ms": t,
        "ppv_mm_s": trace,
        "ppv_max_mm_s": float(np.abs(trace[idx])),
        "t_peak_ms": float(t[idx]),
        "freq_hz": freq_hz,
    }


# ---------------------------------------------------------------------------
# Normativa
# ---------------------------------------------------------------------------


def usbm_limit(freq_hz: float, structure: str = "Vivienda drywall") -> float:
    """Limite de PPV segun USBM RI8507 / OSMRE en funcion de la frecuencia."""
    f = max(freq_hz, 1.0)
    if structure.startswith("Vivienda yeso"):
        if f < 4.0:
            return 12.7 * (f / 4.0)
        if f < 15.0:
            return 12.7
        if f < 40.0:
            return 12.7 + (50.8 - 12.7) * (f - 15.0) / 25.0
        return 50.8
    if f < 4.0:
        return 19.0 * (f / 4.0)
    if f < 15.0:
        return 19.0
    if f < 40.0:
        return 19.0 + (50.8 - 19.0) * (f - 15.0) / 25.0
    return 50.8


def din4150_limit(freq_hz: float, building: str = "Residencial") -> float:
    """Limite de DIN 4150-3 (velocidad en cimentacion) por tipo de edificacion."""
    f = max(freq_hz, 1.0)
    table = {
        "Industrial": [(10, 20.0), (50, 40.0), (100, 50.0)],
        "Residencial": [(10, 5.0), (50, 15.0), (100, 20.0)],
        "Sensible / patrimonio": [(10, 3.0), (50, 8.0), (100, 10.0)],
    }
    pts = table.get(building, table["Residencial"])
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return float(np.interp(f, xs, ys))


def compliance(ppv_mm_s: float, freq_hz: float, cons: SiteConstraints) -> Dict[str, object]:
    """Evalua el cumplimiento contra el limite del proyecto y las normas."""
    usbm = usbm_limit(freq_hz)
    din = din4150_limit(freq_hz)
    limit = cons.ppv_limit_mm_s
    return {
        "ppv_mm_s": ppv_mm_s,
        "limit_project_mm_s": limit,
        "limit_usbm_mm_s": usbm,
        "limit_din_mm_s": din,
        "utilization_pct": ppv_mm_s / max(limit, 1e-6) * 100.0,
        "compliant": ppv_mm_s <= limit,
        "compliant_usbm": ppv_mm_s <= usbm,
        "compliant_din": ppv_mm_s <= din,
    }


def audit_vibration(result: Dict[str, object], cons: SiteConstraints,
                    mic_kg: float, distance_m: float) -> List[Dict[str, str]]:
    """Hallazgos sobre el control de vibraciones."""
    out: List[Dict[str, str]] = []
    ppv = float(result.get("ppv_max_mm_s", 0.0))
    util = ppv / max(cons.ppv_limit_mm_s, 1e-6) * 100.0

    if util > 100.0:
        w_max = max_charge_for_ppv(distance_m, cons.ppv_limit_mm_s, cons.k_site, cons.beta_site)
        out.append({"level": "error", "item": "PPV en el receptor",
                    "message": f"PPV predicho {ppv:.1f} mm/s supera el limite de {cons.ppv_limit_mm_s:.1f} mm/s "
                               f"({util:.0f}%). Carga operante actual {mic_kg:.0f} kg; "
                               f"maxima admisible {w_max:.0f} kg."})
    elif util > 80.0:
        out.append({"level": "warn", "item": "PPV en el receptor",
                    "message": f"PPV predicho {ppv:.1f} mm/s = {util:.0f}% del limite. Margen estrecho."})
    else:
        out.append({"level": "ok", "item": "PPV en el receptor",
                    "message": f"PPV predicho {ppv:.1f} mm/s ({util:.0f}% del limite de "
                               f"{cons.ppv_limit_mm_s:.1f} mm/s)."})

    sd = scaled_distance(distance_m, mic_kg)
    if sd < 20.0:
        out.append({"level": "warn", "item": "Distancia escalada",
                    "message": f"SD = {sd:.1f} m/kg^0.5 (< 20). Zona de alto riesgo segun la practica USBM."})
    else:
        out.append({"level": "ok", "item": "Distancia escalada",
                    "message": f"SD = {sd:.1f} m/kg^0.5."})
    return out
