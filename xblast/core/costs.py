"""Modelo de costos mina-planta (mine-to-mill).

No se limita al costo de perforacion y voladura: incorpora el efecto de la
fragmentacion sobre carguio, acarreo y chancado, que es donde se decide si una
malla mas cerrada (mas cara en voladura) resulta mas barata por tonelada.

Relacion aguas abajo empleada (forma potencial calibrable):

    C_downstream(x50) = C_ref * (x50 / x50_ref) ^ e

con ``e`` positivo para carguio/acarreo (roca gruesa cuesta mas cargar) y para
chancado (mayor consumo especifico de energia).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

import numpy as np

from . import explosives as exdb
from .models import CostParams, Hole

#: Exponentes de sensibilidad del costo aguas abajo al tamano medio.
EXP_LOADING = 0.55
EXP_HAULING = 0.30
EXP_CRUSHING = 0.75


@dataclass
class CostBreakdown:
    """Desglose de costos de la voladura."""

    drilling_usd: float
    explosive_usd: float
    accessories_usd: float
    labor_usd: float
    loading_usd: float
    hauling_usd: float
    crushing_usd: float
    secondary_usd: float
    tonnes: float
    volume_m3: float

    @property
    def db_usd(self) -> float:
        """Costo de perforacion y voladura."""
        return self.drilling_usd + self.explosive_usd + self.accessories_usd + self.labor_usd

    @property
    def downstream_usd(self) -> float:
        return self.loading_usd + self.hauling_usd + self.crushing_usd + self.secondary_usd

    @property
    def total_usd(self) -> float:
        return self.db_usd + self.downstream_usd

    @property
    def db_usd_t(self) -> float:
        return self.db_usd / max(self.tonnes, 1e-6)

    @property
    def total_usd_t(self) -> float:
        return self.total_usd / max(self.tonnes, 1e-6)

    def as_dict(self) -> Dict[str, float]:
        return {
            "Perforacion": self.drilling_usd,
            "Explosivos": self.explosive_usd,
            "Accesorios": self.accessories_usd,
            "Mano de obra": self.labor_usd,
            "Carguio": self.loading_usd,
            "Acarreo": self.hauling_usd,
            "Chancado": self.crushing_usd,
            "Voladura secundaria": self.secondary_usd,
        }


def explosive_cost(holes: Sequence[Hole]) -> float:
    """Costo total del explosivo cargado, por producto."""
    total = 0.0
    for h in holes:
        for d in h.decks:
            if not d.is_charge:
                continue
            exp = exdb.get(d.explosive)
            kg = exp.linear_density_kg_m(h.diameter_mm, d.coupling) * d.length_m
            total += kg * exp.cost_usd_kg
    return total


def compute_costs(
    holes: Sequence[Hole],
    params: CostParams,
    rock_density_t_m3: float,
    x50_cm: float,
    oversize_pct: float,
    primer_type: str = "Booster Pentolita 450 g",
) -> CostBreakdown:
    """Calcula el desglose completo de costos de la voladura."""
    volume = sum(h.volume_m3 for h in holes)
    tonnes = volume * rock_density_t_m3
    drilled = sum(h.length_m for h in holes)
    n_primers = sum(h.n_primers for h in holes)
    n_holes = len(holes)

    drilling = drilled * params.drilling_usd_m
    expl = explosive_cost(holes)
    accessories = (n_primers * exdb.primer_cost(primer_type)
                   + n_primers * params.detonator_usd_unit
                   + n_holes * params.surface_connector_usd_unit)
    labor = n_holes * params.labor_usd_hole

    ref = max(params.reference_x50_cm, 1e-6)
    ratio = max(x50_cm, 1e-6) / ref
    loading = tonnes * params.loading_usd_t * ratio ** EXP_LOADING
    hauling = tonnes * params.hauling_usd_t * ratio ** EXP_HAULING
    crushing = tonnes * params.crushing_usd_t * ratio ** EXP_CRUSHING
    secondary = tonnes * params.secondary_breakage_usd_t * max(oversize_pct, 0.0) / 100.0

    return CostBreakdown(drilling, expl, accessories, labor,
                         loading, hauling, crushing, secondary, tonnes, volume)


def cost_curve(
    powder_factors: np.ndarray, x50_fn, params: CostParams,
    volume_m3: float, tonnes: float, drilled_m: float, n_holes: int,
    explosive_usd_kg: float,
) -> Dict[str, np.ndarray]:
    """Curva de costo total por tonelada frente al factor de potencia.

    ``x50_fn(pf) -> x50_cm`` entrega el tamano medio esperado para cada factor
    de potencia. Permite ubicar el optimo economico del diseno: el costo de
    perforacion y voladura crece con el factor de potencia mientras el costo
    aguas abajo cae, y el minimo de la suma es el punto de operacion buscado.
    """
    pf = np.asarray(powder_factors, float)
    x50 = np.array([x50_fn(float(p)) for p in pf], float)
    ratio = np.maximum(x50, 1e-6) / max(params.reference_x50_cm, 1e-6)

    db = (drilled_m * params.drilling_usd_m
          + pf * volume_m3 * explosive_usd_kg
          + n_holes * (params.labor_usd_hole + params.surface_connector_usd_unit
                       + params.detonator_usd_unit))
    down = tonnes * (params.loading_usd_t * ratio ** EXP_LOADING
                     + params.hauling_usd_t * ratio ** EXP_HAULING
                     + params.crushing_usd_t * ratio ** EXP_CRUSHING)

    total = db + down
    return {
        "powder_factor": pf,
        "x50_cm": x50,
        "db_usd_t": db / max(tonnes, 1e-6),
        "downstream_usd_t": down / max(tonnes, 1e-6),
        "total_usd_t": total / max(tonnes, 1e-6),
        "optimum_pf": float(pf[int(np.argmin(total))]) if pf.size else 0.0,
    }
