"""Catalogo de detonadores electronicos y no electricos.

Cada modelo impone tres limites que condicionan el diseno de la secuencia: el
retardo maximo programable, el incremento minimo con que se puede programar y
la precision real del disparo. El motor los usa para validar los tiempos y
para estimar la dispersion.

Los valores son los declarados habitualmente por los fabricantes y sirven como
punto de partida; conviene contrastarlos con la ficha tecnica del lote que se
vaya a usar.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class Detonator:
    """Modelo de detonador y sus limites de programacion."""

    name: str
    manufacturer: str
    electronic: bool
    min_delay_ms: float
    max_delay_ms: float
    increment_ms: float
    accuracy_pct: float          # dispersion como fraccion del retardo nominal
    accuracy_floor_ms: float     # dispersion minima, aunque el retardo sea corto
    max_units_per_blast: int
    cost_usd: float = 0.0

    # -- derivados ----------------------------------------------------------
    def scatter_ms(self, delay_ms: float) -> float:
        """Desviacion tipica esperada para un retardo nominal dado."""
        return max(abs(delay_ms) * self.accuracy_pct, self.accuracy_floor_ms)

    def snap(self, delay_ms: float) -> float:
        """Ajusta un retardo al incremento programable mas proximo."""
        if self.increment_ms <= 0:
            return float(delay_ms)
        step = round(float(delay_ms) / self.increment_ms)
        return round(step * self.increment_ms, 6)

    def in_range(self, delay_ms: float) -> bool:
        return self.min_delay_ms - 1e-9 <= delay_ms <= self.max_delay_ms + 1e-9

    def on_grid(self, delay_ms: float, tolerance: float = 1e-6) -> bool:
        return abs(self.snap(delay_ms) - float(delay_ms)) <= tolerance

    @property
    def summary(self) -> str:
        rango = f"{self.min_delay_ms:,.0f} a {self.max_delay_ms:,.0f} ms"
        if self.electronic:
            return (f"{rango} · incrementos de {self.increment_ms:g} ms · "
                    f"precision {self.accuracy_pct * 100:.3f}% "
                    f"(minimo {self.accuracy_floor_ms:g} ms) · "
                    f"hasta {self.max_units_per_blast:,} unidades")
        return (f"{rango} · pasos de {self.increment_ms:g} ms · "
                f"dispersion {self.accuracy_pct * 100:.1f}%")


_CATALOG: Dict[str, Detonator] = {}


def _add(det: Detonator) -> None:
    _CATALOG[det.name] = det


# -- electronicos ------------------------------------------------------------
_add(Detonator("i-kon II", "Orica", True, 0, 20000, 1.0, 0.00005, 0.1, 2400, 22.0))
_add(Detonator("i-kon III", "Orica", True, 0, 30000, 1.0, 0.00005, 0.1, 4000, 26.0))
_add(Detonator("eDev II", "Dyno Nobel", True, 0, 20000, 1.0, 0.0001, 0.1, 1600, 21.0))
_add(Detonator("DigiShot", "DetNet", True, 0, 20000, 1.0, 0.0001, 0.1, 1600, 20.0))
_add(Detonator("DigiShot Plus", "DetNet", True, 0, 30000, 1.0, 0.00005, 0.1, 4800, 25.0))
_add(Detonator("SmartShot", "DetNet", True, 0, 15000, 1.0, 0.0002, 0.2, 800, 18.0))
_add(Detonator("HotShot", "DetNet", True, 0, 10000, 1.0, 0.0005, 0.3, 400, 15.0))
_add(Detonator("ExBlast", "Exsa", True, 0, 20000, 1.0, 0.0001, 0.1, 1500, 19.0))

# -- pirotecnicos, para comparar ---------------------------------------------
_add(Detonator("NONEL MS (superficie)", "Generico", False, 0, 200, 9.0, 0.03, 0.5, 1000, 3.2))
_add(Detonator("NONEL LP (fondo)", "Generico", False, 0, 9000, 25.0, 0.03, 1.0, 1000, 3.8))
_add(Detonator("Cordon detonante", "Generico", False, 0, 0, 1.0, 0.06, 1.0, 1000, 1.1))


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


def catalog() -> Dict[str, Detonator]:
    """Diccionario nombre -> :class:`Detonator` (referencia viva)."""
    return _CATALOG


def names(electronic_only: bool = False) -> List[str]:
    items = _CATALOG.values()
    if electronic_only:
        items = [d for d in items if d.electronic]
    return sorted(d.name for d in items)


def get(name: str) -> Detonator:
    """Devuelve el detonador por nombre; cae en i-kon II si no existe."""
    return _CATALOG.get(name, _CATALOG["i-kon II"])


def register(det: Detonator) -> None:
    """Agrega o reemplaza un modelo del catalogo."""
    _add(det)


def manufacturers() -> List[str]:
    return sorted({d.manufacturer for d in _CATALOG.values()})
