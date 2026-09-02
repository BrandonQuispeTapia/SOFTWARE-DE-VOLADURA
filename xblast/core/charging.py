"""Diseno de la columna de carga por plataformas (decks).

Resuelve la distribucion carga de fondo / carga de columna / tacos intermedios
/ taco de collar dentro de cada taladro y calcula masa, energia y distribucion
lineal de energia a lo largo del eje.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import explosives as exdb
from .models import Deck, DeckKind, Hole


@dataclass
class ChargeRule:
    """Regla de carguio aplicada a un conjunto de taladros."""

    column_explosive: str = "ANFO"
    bottom_explosive: Optional[str] = "Emulsion Gasificada 1.15"
    bottom_charge_m: float = 2.5
    stemming_m: float = 3.2
    coupling: float = 1.0
    n_decks: int = 1                # numero de plataformas de carga
    inter_deck_stem_m: float = 1.5  # taco intermedio entre plataformas
    air_deck_m: float = 0.0         # camara de aire sobre la carga
    primer_per_deck: int = 1
    primer_type: str = "Booster Pentolita 450 g"
    stemming_material: str = "Grava chancada 3/8\""

    def clone(self, **kw) -> "ChargeRule":
        data = self.__dict__.copy()
        data.update(kw)
        return ChargeRule(**data)


# ---------------------------------------------------------------------------
# Resolucion de la columna
# ---------------------------------------------------------------------------


def build_column(hole: Hole, rule: ChargeRule) -> List[Deck]:
    """Genera las plataformas del taladro de fondo hacia collar.

    La longitud disponible es la del taladro. Se reserva primero el taco de
    collar, luego la camara de aire, luego los tacos intermedios; el resto se
    reparte entre carga de fondo y carga de columna.
    """
    L = max(hole.length_m, 0.5)
    n_decks = max(1, int(rule.n_decks))

    stem_collar = min(max(rule.stemming_m, 0.0), L * 0.9)
    air = min(max(rule.air_deck_m, 0.0), (L - stem_collar) * 0.5)
    inter_total = rule.inter_deck_stem_m * (n_decks - 1)

    charge_total = L - stem_collar - air - inter_total
    if charge_total <= 0.3:
        # taladro demasiado corto: solo taco
        return [Deck(DeckKind.TACO, L, None, 1.0, 0, 0.0)]

    bottom_len = 0.0
    if rule.bottom_explosive and rule.bottom_charge_m > 0:
        bottom_len = min(rule.bottom_charge_m, charge_total * 0.8)

    column_total = charge_total - bottom_len
    per_deck = column_total / n_decks if n_decks else column_total

    decks: List[Deck] = []
    cursor = 0.0

    def push(kind: DeckKind, length: float, explosive: Optional[str],
             primers: int = 0, coupling: float = 1.0) -> None:
        nonlocal cursor
        if length <= 1e-6:
            return
        decks.append(Deck(kind, round(length, 3), explosive, coupling, primers, round(cursor, 3)))
        cursor += length

    # 1) carga de fondo
    if bottom_len > 0:
        push(DeckKind.CARGA, bottom_len, rule.bottom_explosive, rule.primer_per_deck, rule.coupling)

    # 2) plataformas de columna separadas por taco intermedio
    for i in range(n_decks):
        if per_deck > 1e-6:
            primers = rule.primer_per_deck if (i > 0 or bottom_len == 0) else 0
            push(DeckKind.CARGA, per_deck, rule.column_explosive, primers, rule.coupling)
        if i < n_decks - 1 and rule.inter_deck_stem_m > 0:
            push(DeckKind.TACO, rule.inter_deck_stem_m, None)

    # 3) camara de aire y taco de collar
    push(DeckKind.AIRE, air, None)
    push(DeckKind.TACO, stem_collar, None)

    return decks


def apply_charge(holes: Sequence[Hole], rule: ChargeRule,
                 force: bool = False) -> int:
    """Aplica la regla de carguio y actualiza masa y energia de cada taladro.

    Los taladros marcados con ``charge_locked`` conservan su columna: son los
    que el usuario edito a mano y la regla global no debe pisar. Con
    ``force`` se recargan tambien esos y se les quita el bloqueo.

    Returns:
        Numero de taladros efectivamente recargados.
    """
    changed = 0
    for h in holes:
        if h.charge_locked and not force:
            refresh_hole_charge(h)
            continue
        h.decks = build_column(h, rule)
        h.charge_locked = False
        refresh_hole_charge(h)
        changed += 1
    return changed


def set_column(hole: Hole, decks: List[Deck], autofit: bool = True) -> None:
    """Reemplaza la columna de un taladro recolocando las plataformas.

    Las plataformas llegan ordenadas del fondo al collar; aqui se recalcula
    su distancia al fondo y, con ``autofit``, se ajusta el taco de collar
    para que la columna ocupe exactamente la longitud perforada. El taladro
    queda marcado como editado a mano.
    """
    cursor = 0.0
    clean: List[Deck] = []
    for d in decks:
        length = round(max(float(d.length_m), 0.0), 3)
        if length <= 1e-6:
            continue
        d.length_m = length
        d.from_toe_m = round(cursor, 3)
        clean.append(d)
        cursor += length

    if autofit and clean:
        gap = round(hole.length_m - cursor, 3)
        if abs(gap) > 0.01:
            top = clean[-1]
            if top.kind is DeckKind.TACO and top.length_m + gap > 0.05:
                top.length_m = round(top.length_m + gap, 3)
            elif gap > 0.05:
                clean.append(Deck(DeckKind.TACO, gap, None, 1.0, 0, round(cursor, 3)))
            else:
                _trim_from_top(clean, -gap)
            cursor = 0.0
            for d in clean:
                d.from_toe_m = round(cursor, 3)
                cursor += d.length_m

    hole.decks = clean
    hole.charge_locked = True
    refresh_hole_charge(hole)


def _trim_from_top(decks: List[Deck], excess: float) -> None:
    """Recorta el exceso de longitud empezando por el collar."""
    for d in reversed(decks):
        if excess <= 1e-6:
            return
        take = min(d.length_m - 0.05, excess)
        if take > 0:
            d.length_m = round(d.length_m - take, 3)
            excess -= take


def unlock_charge(holes: Sequence[Hole], rule: ChargeRule) -> int:
    """Devuelve los taladros indicados a la regla global de carguio."""
    for h in holes:
        h.charge_locked = False
    return apply_charge(holes, rule)


def refresh_hole_charge(hole: Hole) -> None:
    """Recalcula masa [kg] y energia [MJ] a partir de las plataformas."""
    mass = 0.0
    energy = 0.0
    for d in hole.decks:
        if not d.is_charge:
            continue
        exp = exdb.get(d.explosive)
        lin = exp.linear_density_kg_m(hole.diameter_mm, d.coupling)
        m = lin * d.length_m
        mass += m
        energy += m * exp.energy_mj_kg
    hole.charge_kg = mass
    hole.energy_mj = energy


# ---------------------------------------------------------------------------
# Metricas por taladro
# ---------------------------------------------------------------------------


def linear_charge_profile(hole: Hole, n: int = 120) -> Tuple[np.ndarray, np.ndarray]:
    """Perfil de densidad lineal de carga [kg/m] a lo largo del taladro.

    Returns:
        ``(z_desde_collar, kg_por_m)`` con ``n`` muestras.
    """
    s = np.linspace(0.0, hole.length_m, n)
    q = np.zeros_like(s)
    for d in hole.decks:
        if not d.is_charge:
            continue
        exp = exdb.get(d.explosive)
        lin = exp.linear_density_kg_m(hole.diameter_mm, d.coupling)
        a = hole.length_m - (d.from_toe_m + d.length_m)
        b = hole.length_m - d.from_toe_m
        q[(s >= a) & (s <= b)] = lin
    return s, q


def energy_profile(hole: Hole, n: int = 120) -> Tuple[np.ndarray, np.ndarray]:
    """Perfil de energia lineal [MJ/m] a lo largo del taladro."""
    s = np.linspace(0.0, hole.length_m, n)
    e = np.zeros_like(s)
    for d in hole.decks:
        if not d.is_charge:
            continue
        exp = exdb.get(d.explosive)
        lin = exp.linear_density_kg_m(hole.diameter_mm, d.coupling)
        a = hole.length_m - (d.from_toe_m + d.length_m)
        b = hole.length_m - d.from_toe_m
        e[(s >= a) & (s <= b)] = lin * exp.energy_mj_kg
    return s, e


def charge_summary(hole: Hole) -> Dict[str, float]:
    """Resumen numerico de la carga del taladro."""
    exps: Dict[str, float] = {}
    for d in hole.decks:
        if d.is_charge:
            exp = exdb.get(d.explosive)
            lin = exp.linear_density_kg_m(hole.diameter_mm, d.coupling)
            exps[d.explosive] = exps.get(d.explosive, 0.0) + lin * d.length_m

    lin_avg = hole.charge_kg / hole.charge_length_m if hole.charge_length_m > 0 else 0.0
    return {
        "charge_kg": hole.charge_kg,
        "energy_mj": hole.energy_mj,
        "charge_length_m": hole.charge_length_m,
        "stemming_m": hole.collar_stemming_m,
        "linear_density_kg_m": lin_avg,
        "n_decks": sum(1 for d in hole.decks if d.is_charge),
        "n_primers": hole.n_primers,
        "by_explosive": exps,
    }


def decoupling_damage_factor(hole: Hole) -> float:
    """Factor de dano relativo a la pared por acoplamiento (1 = carga acoplada).

    Basado en la reduccion de presion de pared con el desacople:
    P_w / P_d = (d_c/d_h)^2.6.
    """
    if not hole.decks:
        return 1.0
    couplings = [d.coupling for d in hole.decks if d.is_charge]
    if not couplings:
        return 0.0
    c = float(np.mean(couplings))
    return float(np.clip(c ** 2.6, 0.0, 1.0))


def suggest_stemming(hole: Hole, material: str = "Grava chancada 3/8\"") -> float:
    """Taco minimo recomendado: 20-25 diametros, ajustado por el material."""
    base = 22.0 * hole.diameter_m
    return base / max(exdb.stemming_factor(material), 0.5)


def audit_charge(hole: Hole, material: str = "Grava chancada 3/8\"") -> List[Dict[str, str]]:
    """Revision de la columna de carga de un taladro."""
    out: List[Dict[str, str]] = []
    t_min = suggest_stemming(hole, material)
    t = hole.collar_stemming_m

    if t < t_min * 0.85:
        out.append({"level": "error", "item": "Taco de collar",
                    "message": f"Taco {t:.2f} m < minimo recomendado {t_min:.2f} m "
                               f"({22.0 * hole.diameter_m:.2f} m ~ 22 diametros). Riesgo de flyrock."})
    elif t > t_min * 1.8:
        out.append({"level": "warn", "item": "Taco de collar",
                    "message": f"Taco {t:.2f} m muy largo frente a {t_min:.2f} m; esperar bolones en la cresta."})
    else:
        out.append({"level": "ok", "item": "Taco de collar", "message": f"{t:.2f} m — adecuado."})

    ratio = hole.charge_length_m / max(hole.length_m, 1e-6)
    if ratio < 0.35:
        out.append({"level": "warn", "item": "Ocupacion de carga",
                    "message": f"Solo {ratio * 100:.0f}% del taladro esta cargado."})
    else:
        out.append({"level": "ok", "item": "Ocupacion de carga",
                    "message": f"{ratio * 100:.0f}% de la columna cargada."})

    if hole.n_primers == 0 and hole.charge_kg > 0:
        out.append({"level": "error", "item": "Iniciacion",
                    "message": "La columna no tiene cebo asignado."})

    for d in hole.decks:
        if d.is_charge:
            exp = exdb.get(d.explosive)
            if hole.diameter_mm < exp.min_diameter_mm:
                out.append({"level": "error", "item": "Diametro critico",
                            "message": f"{exp.name} requiere >= {exp.min_diameter_mm:.0f} mm; "
                                       f"el taladro es de {hole.diameter_mm:.0f} mm. Riesgo de falla de detonacion."})
    return out
