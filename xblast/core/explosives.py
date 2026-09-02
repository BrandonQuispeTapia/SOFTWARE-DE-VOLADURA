"""Catalogo de explosivos, accesorios y materiales de taco.

Los valores corresponden a productos comerciales de uso habitual en mineria
superficial peruana (Famesa / Exsa / Orica). El catalogo es editable en
tiempo de ejecucion mediante :func:`register`.
"""

from __future__ import annotations

from typing import Dict, List

from .models import Explosive

# ---------------------------------------------------------------------------
# Catalogo base
# ---------------------------------------------------------------------------

_CATALOG: Dict[str, Explosive] = {}


def _add(exp: Explosive) -> None:
    _CATALOG[exp.name] = exp


_add(Explosive("ANFO", 0.82, 4200, 100.0, 100.0, 3.72, 970, 50, False, 0.72, "Agente"))
_add(Explosive("ANFO Pesado 30/70", 1.06, 4700, 108.0, 140.0, 3.95, 940, 75, False, 0.95, "Agente"))
_add(Explosive("ANFO Pesado 50/50", 1.20, 5100, 112.0, 164.0, 4.10, 920, 89, True, 1.12, "Agente"))
_add(Explosive("Emulsion Gasificada 1.15", 1.15, 5300, 105.0, 147.0, 3.20, 900, 76, True, 1.28, "Emulsion"))
_add(Explosive("Emulsion Gasificada 1.25", 1.25, 5600, 108.0, 165.0, 3.30, 890, 89, True, 1.35, "Emulsion"))
_add(Explosive("Emulsion Encartuchada 65mm", 1.18, 5200, 110.0, 158.0, 3.35, 880, 51, True, 2.10, "Emulsion"))
_add(Explosive("Emulsion Bombeable HA-46", 1.30, 5800, 115.0, 182.0, 3.45, 870, 102, True, 1.42, "Emulsion"))
_add(Explosive("Dinamita Semexsa 65%", 1.12, 4500, 118.0, 165.0, 4.05, 910, 22, True, 3.40, "Dinamita"))
_add(Explosive("Dinamita Exadit 45%", 1.05, 3600, 96.0, 126.0, 3.30, 930, 22, True, 2.85, "Dinamita"))
_add(Explosive("Carga de contorno 22mm", 0.95, 3200, 92.0, 109.0, 3.10, 940, 22, True, 4.60, "Contorno"))
_add(Explosive("Cordon detonante 10 g/m", 1.40, 6500, 130.0, 182.0, 5.40, 800, 5, True, 1.10, "Iniciacion"))

#: Cebos / boosters disponibles (masa en gramos y energia asociada).
PRIMERS: Dict[str, Dict[str, float]] = {
    "Booster Pentolita 150 g": {"mass_g": 150.0, "vod_m_s": 7500.0, "cost_usd": 4.20},
    "Booster Pentolita 300 g": {"mass_g": 300.0, "vod_m_s": 7600.0, "cost_usd": 7.10},
    "Booster Pentolita 450 g": {"mass_g": 450.0, "vod_m_s": 7600.0, "cost_usd": 12.00},
    "Booster Pentolita 900 g": {"mass_g": 900.0, "vod_m_s": 7700.0, "cost_usd": 21.50},
    "Dinamita 1 1/8 x 8": {"mass_g": 210.0, "vod_m_s": 4500.0, "cost_usd": 2.90},
}

#: Materiales de taco y su factor de retencion relativo (1.0 = detritus).
STEMMING_MATERIALS: Dict[str, float] = {
    "Detritus de perforacion": 1.00,
    "Grava chancada 3/8\"": 1.35,
    "Grava chancada 1/2\"": 1.30,
    "Arena seca": 0.85,
    "Tapon plastico + grava": 1.45,
}


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


def catalog() -> Dict[str, Explosive]:
    """Diccionario nombre -> :class:`Explosive` (referencia viva)."""
    return _CATALOG


def names() -> List[str]:
    return sorted(_CATALOG.keys())


def get(name: str) -> Explosive:
    """Devuelve el explosivo por nombre; cae en ANFO si no existe."""
    return _CATALOG.get(name, _CATALOG["ANFO"])


def register(exp: Explosive) -> None:
    """Agrega o reemplaza un explosivo del catalogo."""
    _add(exp)


def by_family(family: str) -> List[str]:
    return sorted(n for n, e in _CATALOG.items() if e.family == family)


def families() -> List[str]:
    return sorted({e.family for e in _CATALOG.values()})


def suitable_for_diameter(diameter_mm: float) -> List[str]:
    """Explosivos cuyo diametro minimo de uso admite el taladro dado."""
    return sorted(n for n, e in _CATALOG.items() if e.min_diameter_mm <= diameter_mm)


def primer_names() -> List[str]:
    return list(PRIMERS.keys())


def primer_cost(name: str) -> float:
    return PRIMERS.get(name, {"cost_usd": 0.0})["cost_usd"]


def stemming_factor(material: str) -> float:
    """Factor de retencion del taco: >1 retiene mejor los gases."""
    return STEMMING_MATERIALS.get(material, 1.0)
