"""Onda aerea (airblast) y proyeccion de rocas (flyrock).

Onda aerea: modelo de distancia escalada por raiz cubica con correcciones por
confinamiento del taco, presencia de cara libre expuesta y condiciones
atmosfericas (inversion termica y viento).

Flyrock: modelos de Lundborg (1975) y Richards & Moore (2004) para los tres
mecanismos clasicos — reventon de cara, crateres por taco y rotura de collar.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence

import numpy as np

from .models import Hole

P_REF_PA = 2.0e-5  # presion de referencia acustica


# ---------------------------------------------------------------------------
# Onda aerea
# ---------------------------------------------------------------------------


def overpressure_pa(distance_m: float, charge_kg: float, k: float = 3.3,
                    a: float = 1.2) -> float:
    """Sobrepresion [Pa] por distancia escalada cubica: P = K * (D/W^(1/3))^-a.

    ``k`` esta en kPa y corresponde al grado de confinamiento (Siskind):
    0.1 carga bien confinada, 3.3 voladura de produccion normal,
    185 carga desnuda al aire.
    """
    w = max(charge_kg, 1e-6)
    sd = distance_m / (w ** (1.0 / 3.0))
    return float(k * 1000.0 * sd ** (-a)) if sd > 0 else 0.0


def to_db(pressure_pa: float) -> float:
    """Convierte sobrepresion a nivel lineal [dBL]."""
    return float(20.0 * math.log10(max(pressure_pa, 1e-9) / P_REF_PA))


def from_db(db: float) -> float:
    return float(P_REF_PA * 10.0 ** (db / 20.0))


def confinement_correction_db(stemming_m: float, diameter_mm: float,
                              stemming_factor: float = 1.0,
                              exposed_face: bool = True) -> float:
    """Correccion en dB por confinamiento del taco y exposicion de la cara.

    Un taco corto (< 20 diametros) deja escapar los gases y sube el nivel;
    un taco bien dimensionado y confinado lo reduce.
    """
    ratio = stemming_m / max(diameter_mm / 1000.0, 1e-6)
    corr = 0.0
    if ratio < 20.0:
        corr += (20.0 - ratio) * 0.55
    else:
        corr -= min((ratio - 20.0) * 0.18, 6.0)
    corr -= (stemming_factor - 1.0) * 4.0
    if exposed_face:
        corr += 3.0
    return float(corr)


def atmospheric_correction_db(temp_inversion: bool = False, wind_toward: bool = False,
                              wind_speed_m_s: float = 0.0) -> float:
    """Aumento tipico por inversion termica y viento hacia el receptor."""
    corr = 0.0
    if temp_inversion:
        corr += 6.0
    if wind_toward:
        corr += min(1.6 * wind_speed_m_s, 10.0)
    return float(corr)


def predict_airblast(distance_m: float, mic_kg: float, stemming_m: float,
                     diameter_mm: float, stemming_factor: float = 1.0,
                     temp_inversion: bool = False, wind_toward: bool = False,
                     wind_speed_m_s: float = 0.0) -> Dict[str, float]:
    """Nivel de onda aerea predicho en el receptor [dBL]."""
    base = to_db(overpressure_pa(max(distance_m, 1.0), mic_kg))
    conf = confinement_correction_db(stemming_m, diameter_mm, stemming_factor)
    atm = atmospheric_correction_db(temp_inversion, wind_toward, wind_speed_m_s)
    total = base + conf + atm
    return {
        "base_db": base,
        "confinement_db": conf,
        "atmospheric_db": atm,
        "airblast_db": total,
        "overpressure_pa": from_db(total),
        "scaled_distance": distance_m / max(mic_kg, 1e-6) ** (1.0 / 3.0),
    }


def audit_airblast(result: Dict[str, float], limit_db: float) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    db = result.get("airblast_db", 0.0)
    if db > limit_db:
        out.append({"level": "error", "item": "Onda aerea",
                    "message": f"{db:.0f} dBL supera el limite de {limit_db:.0f} dBL. "
                               "Aumente el taco, reduzca la carga operante o evite disparar con inversion termica."})
    elif db > limit_db - 5.0:
        out.append({"level": "warn", "item": "Onda aerea",
                    "message": f"{db:.0f} dBL, a menos de 5 dB del limite ({limit_db:.0f} dBL)."})
    else:
        out.append({"level": "ok", "item": "Onda aerea",
                    "message": f"{db:.0f} dBL (limite {limit_db:.0f} dBL)."})
    return out


# ---------------------------------------------------------------------------
# Flyrock
# ---------------------------------------------------------------------------


def lundborg_throw_m(diameter_mm: float) -> float:
    """Alcance maximo de Lundborg (1975).

    Formulacion original en pies: Lmax = 260 * d^(2/3) con d en pulgadas;
    aqui se devuelve directamente en metros.
    """
    d_in = diameter_mm / 25.4
    return float(260.0 * d_in ** (2.0 / 3.0) * 0.3048)


def richards_moore_face_burst(charge_kg_m: float, burden_m: float, k: float = 13.5) -> float:
    """Reventon de cara: Lmax = (k^2/g) * (sqrt(q)/B)^2.6."""
    if burden_m <= 0:
        return 0.0
    return float((k ** 2 / 9.81) * (math.sqrt(max(charge_kg_m, 1e-6)) / burden_m) ** 2.6)


def richards_moore_cratering(charge_kg_m: float, stemming_m: float, k: float = 13.5) -> float:
    """Crateres por taco: Lmax = (k^2/g) * (sqrt(q)/T)^2.6."""
    if stemming_m <= 0:
        return 0.0
    return float((k ** 2 / 9.81) * (math.sqrt(max(charge_kg_m, 1e-6)) / stemming_m) ** 2.6)


def predict_flyrock(holes: Sequence[Hole], k_factor: float = 13.5,
                    safety_factor: float = 1.5) -> Dict[str, object]:
    """Alcance maximo esperado y distancia de seguridad recomendada."""
    if not holes:
        return {"max_throw_m": 0.0, "safe_distance_m": 0.0, "mechanism": "-", "critical_holes": []}

    face, crater, lundborg = 0.0, 0.0, 0.0
    critical: List[str] = []

    for h in holes:
        if h.charge_length_m <= 0:
            continue
        q = h.charge_kg / max(h.charge_length_m, 1e-6)   # kg/m
        f = richards_moore_face_burst(q, max(h.relief_burden_m or h.burden_real_m, 0.5), k_factor)
        c = richards_moore_cratering(q, max(h.collar_stemming_m, 0.3), k_factor)
        lundborg = max(lundborg, lundborg_throw_m(h.diameter_mm))
        if f > face:
            face = f
        if c > crater:
            crater = c
        if max(f, c) > 150.0:
            critical.append(h.hid)

    worst = max(face, crater)
    mechanism = "Reventon de cara" if face >= crater else "Crateres por taco"
    return {
        "face_burst_m": face,
        "cratering_m": crater,
        "lundborg_m": lundborg,
        "max_throw_m": worst,
        "mechanism": mechanism,
        "safe_distance_m": worst * safety_factor,
        "critical_holes": critical[:20],
        "n_critical": len(critical),
    }


def audit_flyrock(result: Dict[str, object], exclusion_radius_m: float) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    safe = float(result.get("safe_distance_m", 0.0))
    throw = float(result.get("max_throw_m", 0.0))

    if safe > exclusion_radius_m:
        out.append({"level": "error", "item": "Radio de exclusion",
                    "message": f"Alcance maximo {throw:.0f} m ({result.get('mechanism')}); "
                               f"distancia segura {safe:.0f} m > radio declarado {exclusion_radius_m:.0f} m. "
                               "Amplie el area de evacuacion o corrija taco y burden."})
    else:
        out.append({"level": "ok", "item": "Radio de exclusion",
                    "message": f"Alcance maximo {throw:.0f} m; distancia segura {safe:.0f} m "
                               f"dentro del radio de {exclusion_radius_m:.0f} m."})

    n_crit = int(result.get("n_critical", 0))
    if n_crit:
        ids = ", ".join(result.get("critical_holes", [])[:8])
        out.append({"level": "warn", "item": "Taladros criticos",
                    "message": f"{n_crit} taladro(s) con alcance > 150 m ({ids}). "
                               "Revise burden real y longitud de taco."})
    return out
