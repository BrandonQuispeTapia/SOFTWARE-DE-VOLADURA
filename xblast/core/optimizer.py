"""Optimizacion del diseno y analisis de escenarios.

Barre el espacio burden-espaciamiento (y opcionalmente el factor de potencia)
evaluando cada combinacion con el motor completo, y devuelve el frente de
soluciones que cumplen las restricciones ambientales ordenadas por costo total
por tonelada. Tambien permite comparar escenarios definidos a mano.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import charging, explosives as exdb
from . import pattern as pattern_mod
from .analysis import BlastAnalysis, analyze
from .models import BlastDesign, PatternParams


@dataclass
class Scenario:
    """Una combinacion evaluada del espacio de diseno."""

    burden_m: float
    spacing_m: float
    stemming_m: float
    powder_factor: float
    x50_cm: float
    p80_cm: float
    oversize_pct: float
    ppv_mm_s: float
    airblast_db: float
    flyrock_m: float
    cost_db_usd_t: float
    cost_total_usd_t: float
    n_holes: int
    feasible: bool
    violations: List[str] = field(default_factory=list)

    def as_row(self) -> Dict[str, object]:
        return {
            "B (m)": round(self.burden_m, 2),
            "S (m)": round(self.spacing_m, 2),
            "Taco (m)": round(self.stemming_m, 2),
            "Taladros": self.n_holes,
            "PF (kg/m3)": round(self.powder_factor, 3),
            "X50 (cm)": round(self.x50_cm, 1),
            "P80 (cm)": round(self.p80_cm, 1),
            "Sobretamano (%)": round(self.oversize_pct, 1),
            "PPV (mm/s)": round(self.ppv_mm_s, 1),
            "Airblast (dBL)": round(self.airblast_db, 0),
            "Flyrock (m)": round(self.flyrock_m, 0),
            "Costo P&V (USD/t)": round(self.cost_db_usd_t, 3),
            "Costo total (USD/t)": round(self.cost_total_usd_t, 3),
            "Viable": "Si" if self.feasible else "No",
        }


@dataclass
class OptimizationResult:
    """Resultado del barrido: escenarios evaluados y el mejor viable."""

    scenarios: List[Scenario]
    best: Optional[Scenario]
    baseline: Optional[Scenario]
    target_p80_cm: float

    @property
    def feasible(self) -> List[Scenario]:
        return [s for s in self.scenarios if s.feasible]

    def savings_usd_t(self) -> float:
        if not (self.best and self.baseline):
            return 0.0
        return self.baseline.cost_total_usd_t - self.best.cost_total_usd_t


# ---------------------------------------------------------------------------
# Barrido
# ---------------------------------------------------------------------------


def optimize(
    design: BlastDesign,
    rule: charging.ChargeRule,
    burden_range: Tuple[float, float] = (0.8, 1.2),
    n_steps: int = 5,
    sb_ratios: Sequence[float] = (1.0, 1.15, 1.3),
    target_p80_cm: float = 50.0,
    keep_area: bool = True,
    progress: Optional[Callable[[int, int], None]] = None,
) -> OptimizationResult:
    """Explora variaciones de burden y relacion S/B alrededor del diseno base.

    Args:
        design: diseno base (se copia, nunca se modifica).
        rule: regla de carguio aplicada a cada escenario.
        burden_range: factores multiplicativos minimo y maximo del burden.
        n_steps: numero de burdens evaluados.
        sb_ratios: relaciones espaciamiento/burden a probar.
        target_p80_cm: P80 objetivo de la planta.
        keep_area: si es True, se mantiene el area total volada ajustando
            filas y columnas, de modo que los escenarios sean comparables.
        progress: callback ``f(hecho, total)`` para reportar avance.

    Returns:
        :class:`OptimizationResult` con todos los escenarios evaluados.
    """
    base_p = design.pattern
    area_x = base_p.spacing_m * base_p.cols
    area_y = base_p.burden_m * base_p.rows

    factors = np.linspace(burden_range[0], burden_range[1], max(2, n_steps))
    combos = [(float(f), float(r)) for f in factors for r in sb_ratios]
    total = len(combos)

    scenarios: List[Scenario] = []
    baseline: Optional[Scenario] = None

    for i, (fb, sb) in enumerate(combos, start=1):
        b = base_p.burden_m * fb
        s = b * sb
        stem = pattern_mod.konya_stemming(b)

        p = copy.deepcopy(base_p)
        p.burden_m = round(b, 2)
        p.spacing_m = round(s, 2)
        p.stemming_m = round(stem, 2)
        p.subdrill_m = round(pattern_mod.konya_subdrill(b), 2)
        if keep_area:
            p.rows = max(1, int(round(area_y / p.burden_m)))
            p.cols = max(1, int(round(area_x / p.spacing_m)))

        d = _clone_design(design, p)
        d.holes = pattern_mod.generate_pattern(p)
        charging.apply_charge(d.holes, rule.clone(stemming_m=p.stemming_m))

        a = analyze(d, compute_energy=False, target_p80_cm=target_p80_cm)
        sc = _to_scenario(d, a, target_p80_cm)
        scenarios.append(sc)

        if abs(fb - 1.0) < 1e-6 and abs(sb - base_p.s_b_ratio) < 0.06:
            baseline = sc
        if progress:
            progress(i, total)

    feasible = [s for s in scenarios if s.feasible]
    pool = feasible or scenarios
    best = min(pool, key=lambda s: s.cost_total_usd_t)

    if baseline is None and scenarios:
        baseline = min(scenarios, key=lambda s: abs(s.burden_m - base_p.burden_m))

    return OptimizationResult(scenarios, best, baseline, target_p80_cm)


def _clone_design(design: BlastDesign, p: PatternParams) -> BlastDesign:
    d = BlastDesign(
        name=design.name, site=design.site, author=design.author,
        pattern=p, rock=copy.deepcopy(design.rock),
        timing=copy.deepcopy(design.timing),
        constraints=copy.deepcopy(design.constraints),
        costs=copy.deepcopy(design.costs),
        column_explosive=design.column_explosive,
        bottom_explosive=design.bottom_explosive,
        bottom_charge_m=design.bottom_charge_m,
        primer_type=design.primer_type,
        stemming_material=design.stemming_material,
    )
    return d


def _to_scenario(design: BlastDesign, a: BlastAnalysis, target_p80_cm: float) -> Scenario:
    k = a.kpis
    cons = design.constraints
    violations: List[str] = []

    if k["ppv_mm_s"] > cons.ppv_limit_mm_s:
        violations.append(f"PPV {k['ppv_mm_s']:.1f} > {cons.ppv_limit_mm_s:.1f} mm/s")
    if k["airblast_db"] > cons.airblast_limit_db:
        violations.append(f"Airblast {k['airblast_db']:.0f} > {cons.airblast_limit_db:.0f} dBL")
    if k["safe_distance_m"] > cons.exclusion_radius_m:
        violations.append(f"Flyrock {k['safe_distance_m']:.0f} m > radio {cons.exclusion_radius_m:.0f} m")
    if k["p80_cm"] > target_p80_cm * 1.25:
        violations.append(f"P80 {k['p80_cm']:.0f} cm sobre objetivo")
    if design.pattern.stiffness_ratio < 2.0:
        violations.append("H/B < 2")

    return Scenario(
        burden_m=design.pattern.burden_m,
        spacing_m=design.pattern.spacing_m,
        stemming_m=design.pattern.stemming_m,
        powder_factor=k["powder_factor"],
        x50_cm=k["x50_cm"],
        p80_cm=k["p80_cm"],
        oversize_pct=k["oversize_pct"],
        ppv_mm_s=k["ppv_mm_s"],
        airblast_db=k["airblast_db"],
        flyrock_m=k["flyrock_m"],
        cost_db_usd_t=k["cost_db_usd_t"],
        cost_total_usd_t=k["cost_total_usd_t"],
        n_holes=k["n_holes"],
        feasible=not violations,
        violations=violations,
    )


# ---------------------------------------------------------------------------
# Sensibilidad
# ---------------------------------------------------------------------------


def sensitivity(result: OptimizationResult) -> Dict[str, np.ndarray]:
    """Series ordenadas por factor de potencia para graficar la curva de costo."""
    if not result.scenarios:
        return {}
    s = sorted(result.scenarios, key=lambda x: x.powder_factor)
    return {
        "powder_factor": np.array([x.powder_factor for x in s]),
        "cost_db_usd_t": np.array([x.cost_db_usd_t for x in s]),
        "cost_total_usd_t": np.array([x.cost_total_usd_t for x in s]),
        "x50_cm": np.array([x.x50_cm for x in s]),
        "ppv_mm_s": np.array([x.ppv_mm_s for x in s]),
        "feasible": np.array([x.feasible for x in s], bool),
    }
