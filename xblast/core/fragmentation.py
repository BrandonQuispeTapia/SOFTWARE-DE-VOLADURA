"""Prediccion de fragmentacion.

Implementa tres modelos encadenados:

* **Kuznetsov-Cunningham (Kuz-Ram)** — tamano medio ``x50`` a partir del factor
  de roca de Lilly, el factor de potencia y la energia relativa del explosivo.
* **Indice de uniformidad de Cunningham** con correcciones por desviacion de
  perforacion, carga en plataformas y dispersion de retardos.
* **Swebrec / KCO (Ouchterlony, 2005)** — curva granulometrica completa, que
  corrige la sobre-estimacion de finos de Rosin-Rammler y respeta el tamano
  maximo ``xmax`` impuesto por el bloque in situ.

Todas las funciones trabajan en centimetros salvo indicacion contraria.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import explosives as exdb
from .models import Hole, RockMass


@dataclass
class FragmentationResult:
    """Resultado granulometrico de un taladro o de la voladura completa."""

    x50_cm: float
    xmax_cm: float
    n: float
    b_swebrec: float
    sizes_cm: np.ndarray
    passing_pct: np.ndarray
    p20_cm: float
    p80_cm: float
    fines_pct: float          # pasante bajo 2.5 cm
    oversize_pct: float       # retenido sobre el umbral de boca de chancadora
    model: str = "Swebrec (KCO)"

    def passing_at(self, size_cm: float) -> float:
        """Porcentaje pasante para un tamano dado."""
        return float(np.interp(size_cm, self.sizes_cm, self.passing_pct))

    def size_at(self, passing_pct: float) -> float:
        """Tamano correspondiente a un porcentaje pasante."""
        return float(np.interp(passing_pct, self.passing_pct, self.sizes_cm))


# ---------------------------------------------------------------------------
# Kuznetsov / Cunningham
# ---------------------------------------------------------------------------


def kuznetsov_x50(rock_factor_a: float, volume_m3: float, charge_kg: float,
                  rws: float, correction: float = 1.0) -> float:
    """Tamano medio ``x50`` [cm] de Kuznetsov con la forma de Cunningham.

    x50 = A * (V0/Qe)^0.8 * Qe^(1/6) * (115/RWS)^(19/30)
    """
    if charge_kg <= 0 or volume_m3 <= 0:
        return 0.0
    x50 = (rock_factor_a
           * (volume_m3 / charge_kg) ** 0.8
           * charge_kg ** (1.0 / 6.0)
           * (115.0 / max(rws, 1.0)) ** (19.0 / 30.0))
    return float(x50 * correction)


def cunningham_n(
    burden_m: float, spacing_m: float, diameter_mm: float, bench_height_m: float,
    charge_length_m: float, bottom_charge_m: float, column_charge_m: float,
    drilling_accuracy_m: float = 0.25, staggered: bool = True,
) -> float:
    """Indice de uniformidad ``n`` de Cunningham (1987, revision 2005).

    n = (2.2 - 14 B/d) * sqrt((1 + S/B)/2) * (1 - W/B)
        * (|BCL - CCL| / L_c + 0.1)^0.1 * (L_c / H)
    """
    if burden_m <= 0 or bench_height_m <= 0:
        return 1.2

    # Forma clasica de Cunningham: B en metros, d en milimetros.
    term_bd = 2.2 - 14.0 * burden_m / max(diameter_mm, 1e-6)

    sb = spacing_m / burden_m
    term_sb = math.sqrt((1.0 + sb) / 2.0)
    term_w = max(1.0 - drilling_accuracy_m / burden_m, 0.1)

    lc = max(charge_length_m, 1e-6)
    term_deck = (abs(bottom_charge_m - column_charge_m) / lc + 0.1) ** 0.1
    term_len = lc / bench_height_m

    n = term_bd * term_sb * term_w * term_deck * term_len
    if staggered:
        n *= 1.1                                    # malla al tresbolillo mejora uniformidad
    return float(np.clip(n, 0.7, 2.8))


def timing_correction(relief_ms_per_m: float) -> Tuple[float, float]:
    """Correccion de x50 y n por el tiempo de alivio (Cunningham, 2005).

    El optimo practico esta entre 3 y 6 ms/m; fuera de ese rango la
    fragmentacion se degrada y la uniformidad cae.

    Returns:
        ``(factor_x50, factor_n)``.
    """
    t = max(relief_ms_per_m, 0.1)
    if t < 3.0:
        fx = 1.0 + 0.18 * (3.0 - t) / 3.0
        fn = 1.0 - 0.15 * (3.0 - t) / 3.0
    elif t > 6.0:
        fx = 1.0 + 0.12 * min((t - 6.0) / 10.0, 1.0)
        fn = 1.0 - 0.10 * min((t - 6.0) / 10.0, 1.0)
    else:
        fx, fn = 0.95, 1.05
    return float(fx), float(np.clip(fn, 0.6, 1.2))


# ---------------------------------------------------------------------------
# Curvas granulometricas
# ---------------------------------------------------------------------------


def rosin_rammler(sizes_cm: np.ndarray, x50_cm: float, n: float) -> np.ndarray:
    """Pasante acumulado de Rosin-Rammler (base de Kuz-Ram)."""
    if x50_cm <= 0:
        return np.zeros_like(sizes_cm)
    xc = x50_cm / (0.693 ** (1.0 / n))
    return 100.0 * (1.0 - np.exp(-((sizes_cm / xc) ** n)))


def swebrec(sizes_cm: np.ndarray, x50_cm: float, xmax_cm: float, b: float) -> np.ndarray:
    """Funcion de Swebrec (Ouchterlony 2005).

    P(x) = 1 / (1 + [ln(xmax/x) / ln(xmax/x50)]^b)
    """
    if x50_cm <= 0 or xmax_cm <= x50_cm:
        return rosin_rammler(sizes_cm, x50_cm, max(b / 2.0, 0.8))
    x = np.clip(sizes_cm, 1e-6, xmax_cm * 0.999999)
    num = np.log(xmax_cm / x)
    den = math.log(xmax_cm / x50_cm)
    p = 1.0 / (1.0 + (num / den) ** b)
    p = np.where(sizes_cm >= xmax_cm, 1.0, p)
    return p * 100.0


def swebrec_b(x50_cm: float, xmax_cm: float, n: float) -> float:
    """Parametro de ondulacion b = 2 ln2 ln(xmax/x50) n."""
    if xmax_cm <= x50_cm:
        return 2.0
    return float(np.clip(2.0 * math.log(2.0) * math.log(xmax_cm / x50_cm) * n, 0.8, 8.0))


DEFAULT_SIEVE_CM = np.array(
    [0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 7.5, 10.0, 15.0, 20.0, 25.0, 30.0, 40.0,
     50.0, 60.0, 80.0, 100.0, 125.0, 150.0, 200.0, 250.0, 300.0], float)


# ---------------------------------------------------------------------------
# API principal
# ---------------------------------------------------------------------------


def predict_hole(
    hole: Hole,
    rock: RockMass,
    rws: float,
    relief_ms_per_m: float = 4.0,
    drilling_accuracy_m: float = 0.25,
    in_situ_block_cm: Optional[float] = None,
    staggered: bool = True,
    sizes_cm: Optional[np.ndarray] = None,
) -> FragmentationResult:
    """Prediccion granulometrica de un taladro individual."""
    sizes = DEFAULT_SIEVE_CM if sizes_cm is None else np.asarray(sizes_cm, float)

    fx, fn = timing_correction(relief_ms_per_m)
    x50 = kuznetsov_x50(rock.rock_factor_a, hole.volume_m3, hole.charge_kg, rws, fx)

    charge_decks = [d for d in hole.decks if d.is_charge]
    bottom = charge_decks[0].length_m if charge_decks else 0.0
    column = sum(d.length_m for d in charge_decks[1:]) if len(charge_decks) > 1 else 0.0

    n = cunningham_n(
        max(hole.burden_real_m, 0.5), max(hole.spacing_real_m, 0.5), hole.diameter_mm,
        max(hole.bench_height_m, 1.0), max(hole.charge_length_m, 0.1),
        bottom, column, drilling_accuracy_m, staggered,
    ) * fn

    # xmax: el menor entre el bloque in situ y el burden (limite fisico del fragmento)
    block = in_situ_block_cm if in_situ_block_cm else _in_situ_block_cm(rock)
    xmax = float(min(block, max(hole.burden_real_m, 0.5) * 100.0))
    xmax = max(xmax, x50 * 2.0)

    b = swebrec_b(x50, xmax, n)
    passing = swebrec(sizes, x50, xmax, b)

    return _finish(sizes, passing, x50, xmax, n, b)


def predict_blast(
    holes: Sequence[Hole],
    rock: RockMass,
    rws: float,
    relief_ms_per_m: float = 4.0,
    drilling_accuracy_m: float = 0.25,
    in_situ_block_cm: Optional[float] = None,
    staggered: bool = True,
    oversize_cm: float = 80.0,
) -> Tuple[FragmentationResult, List[FragmentationResult]]:
    """Curva global de la voladura como mezcla ponderada por masa de cada taladro.

    Returns:
        ``(curva_global, curvas_por_taladro)``.
    """
    sizes = DEFAULT_SIEVE_CM
    per_hole: List[FragmentationResult] = []
    weights: List[float] = []

    for h in holes:
        r = predict_hole(h, rock, rws, relief_ms_per_m, drilling_accuracy_m,
                         in_situ_block_cm, staggered, sizes)
        per_hole.append(r)
        weights.append(max(h.volume_m3, 1e-6))
        h.x50_cm = r.x50_cm
        h.xmax_cm = r.xmax_cm
        h.uniformity_n = r.n

    if not per_hole:
        empty = _finish(sizes, np.zeros_like(sizes), 0.0, 1.0, 1.0, 2.0, oversize_cm)
        return empty, []

    w = np.array(weights, float)
    w /= w.sum()
    passing = np.zeros_like(sizes)
    for r, wi in zip(per_hole, w):
        passing += r.passing_pct * wi

    x50 = float(np.interp(50.0, passing, sizes))
    xmax = float(max(r.xmax_cm for r in per_hole))
    n = float(np.average([r.n for r in per_hole], weights=w))
    b = swebrec_b(x50, xmax, n)

    return _finish(sizes, passing, x50, xmax, n, b, oversize_cm), per_hole


def _finish(sizes: np.ndarray, passing: np.ndarray, x50: float, xmax: float,
            n: float, b: float, oversize_cm: float = 80.0) -> FragmentationResult:
    passing = np.clip(np.maximum.accumulate(passing), 0.0, 100.0)
    p20 = float(np.interp(20.0, passing, sizes))
    p80 = float(np.interp(80.0, passing, sizes))
    fines = float(np.interp(2.5, sizes, passing))
    over = float(100.0 - np.interp(oversize_cm, sizes, passing))
    return FragmentationResult(
        x50_cm=x50, xmax_cm=xmax, n=n, b_swebrec=b,
        sizes_cm=sizes, passing_pct=passing,
        p20_cm=p20, p80_cm=p80, fines_pct=fines, oversize_pct=max(over, 0.0),
    )


def _in_situ_block_cm(rock: RockMass) -> float:
    """Tamano de bloque in situ estimado a partir del GSI y el espaciamiento."""
    # JPS 10 -> < 0.1 m ; 20 -> 0.1-1.0 m ; 50 -> > 1.0 m
    if rock.jps <= 12:
        base = 30.0
    elif rock.jps <= 30:
        base = 90.0
    else:
        base = 200.0
    return float(base * (0.6 + rock.gsi / 100.0))


def audit_fragmentation(res: FragmentationResult, target_p80_cm: float,
                        oversize_cm: float = 80.0) -> List[Dict[str, str]]:
    """Compara el resultado contra el objetivo de planta."""
    out: List[Dict[str, str]] = []
    if res.p80_cm <= 0:
        return out

    dev = (res.p80_cm - target_p80_cm) / max(target_p80_cm, 1e-6) * 100.0
    if dev > 20.0:
        out.append({"level": "error", "item": "P80",
                    "message": f"P80 = {res.p80_cm:.1f} cm, {dev:+.0f}% sobre el objetivo "
                               f"({target_p80_cm:.0f} cm). Aumente el factor de potencia o cierre la malla."})
    elif dev < -25.0:
        out.append({"level": "warn", "item": "P80",
                    "message": f"P80 = {res.p80_cm:.1f} cm, {dev:+.0f}% bajo el objetivo. "
                               "Sobre-fragmentacion: exceso de explosivo y finos."})
    else:
        out.append({"level": "ok", "item": "P80",
                    "message": f"P80 = {res.p80_cm:.1f} cm ({dev:+.0f}% del objetivo)."})

    if res.oversize_pct > 8.0:
        out.append({"level": "warn", "item": "Sobretamano",
                    "message": f"{res.oversize_pct:.1f}% sobre {oversize_cm:.0f} cm. "
                               "Prevea voladura secundaria o martillo."})
    else:
        out.append({"level": "ok", "item": "Sobretamano",
                    "message": f"{res.oversize_pct:.1f}% sobre {oversize_cm:.0f} cm."})

    if res.fines_pct > 12.0:
        out.append({"level": "warn", "item": "Finos",
                    "message": f"{res.fines_pct:.1f}% bajo 2.5 cm. Perdida de energia y dilucion."})

    if res.n < 1.0:
        out.append({"level": "warn", "item": "Uniformidad",
                    "message": f"n = {res.n:.2f} (< 1.0). Granulometria muy dispersa; "
                               "revise precision de perforacion y distribucion de carga."})
    return out
