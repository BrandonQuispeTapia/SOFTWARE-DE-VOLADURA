"""
core/explosives.py
==================
Termodinámica y cálculo energético de explosivos para VOLADURA_PRO_10X.

Implementa el modelo de energía explosiva según RWS/RBS (Relative Weight/Bulk
Strength), cálculo de masa por columna cilíndrica con desacoplamiento, y
un catálogo completo de explosivos comerciales.

Bibliografía:
    - López Jimeno, C. (1995). Manual de Perforación y Voladura de Rocas.
      IGME, Madrid. Cap. 3: Propiedades de los Explosivos.
    - Ouchterlony, F. & Sanchidrián, J.A. (2019). A Plea for More
      Realism in Blast Fragmentation Models. Proceedings FRAGBLAST.
    - Cunningham, C.V.B. (1987). Fragmentation Estimations and the
      Kuz-Ram Model. Proc. 2nd Int. Symposium on Rock Fragmentation.
    - ISEE Blasters' Handbook (2011). 18th Edition.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional

import numpy as np


# ══════════════════════════════════════════════════════════════════════════════
# Enumeraciones
# ══════════════════════════════════════════════════════════════════════════════

class ExplosiveType(Enum):
    """Familia química del explosivo."""
    ANFO          = "anfo"
    HEAVY_ANFO    = "anfo_pesado"
    ANFO_EMULSION = "anfo_emulsion"
    EMULSION      = "emulsion"
    EMULSION_BULK = "emulsion_granel"
    DYNAMITE      = "dinamita"
    POWERGEL      = "powergel"
    SLURRY        = "slurry"
    PENTOLITE     = "pentolite"


class DetonatorType(Enum):
    """Sistema de iniciación."""
    NONEL_DOWNHOLE    = "nonel_fondo"
    NONEL_SURFACE_MS  = "nonel_superficie"
    ELECTRONIC        = "electronico"
    ELECTRIC          = "electrico"


class DetonatorManufacturer(Enum):
    """Fabricante de detonadores Nonel."""
    ORICA  = "orica"
    DYNO   = "dyno_nobel"
    AUSTIN = "austin_powder"


# ══════════════════════════════════════════════════════════════════════════════
# Clase Explosive
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Explosive:
    """Propiedades físico-químicas de un agente explosivo.

    Attributes:
        name: Nombre comercial.
        explosive_type: Familia química (enum ExplosiveType).
        density_gcc: Densidad del explosivo [g/cc] = [t/m³].
        vod_ms: Velocidad de Detonación (VOD) ideal [m/s].
        rws: Relative Weight Strength vs ANFO (ANFO=100).
            RWS = (Energía_explosivo / Energía_ANFO) * 100
        rbs: Relative Bulk Strength vs ANFO (ANFO=100).
            RBS = RWS * (densidad_explosivo / densidad_ANFO)
        heat_of_explosion_kjkg: Calor de explosión [kJ/kg].
        oxygen_balance_pct: Balance de oxígeno [%].
            0% = neutro (ideal). Negativo = déficit O₂.
        is_water_resistant: Resistencia al agua.
        min_diameter_mm: Diámetro mínimo de sensibilización [mm].
        cartridge_diameter_mm: Diámetro del cartucho [mm] (para dinamitas).
        cartridge_length_mm: Longitud del cartucho [mm].
        cartridge_mass_kg: Masa del cartucho [kg].
        unit_cost_per_kg: Costo unitario [USD/kg] (referencial).

    References:
        López Jimeno (1995), Tabla 3.1: Propiedades típicas de explosivos.
        ISEE Handbook (2011), Appendix B: Explosive Properties.
    """
    name: str
    explosive_type: ExplosiveType
    density_gcc: float
    vod_ms: float
    rws: float
    rbs: float
    heat_of_explosion_kjkg: float = 0.0
    oxygen_balance_pct: float = 0.0
    is_water_resistant: bool = False
    min_diameter_mm: float = 0.0
    cartridge_diameter_mm: float = 0.0
    cartridge_length_mm: float = 0.0
    cartridge_mass_kg: float = 0.0
    unit_cost_per_kg: float = 0.0

    def __post_init__(self) -> None:
        if not (0.5 <= self.density_gcc <= 2.5):
            raise ValueError(
                f"Densidad {self.density_gcc} g/cc fuera del rango [0.5, 2.5]."
            )
        if self.vod_ms <= 0:
            raise ValueError("VOD debe ser positivo.")
        if self.rws <= 0 or self.rbs <= 0:
            raise ValueError("RWS y RBS deben ser > 0.")

    @property
    def density_kgm3(self) -> float:
        """Densidad en [kg/m³]. Equivale a density_gcc * 1000."""
        return self.density_gcc * 1000.0

    @property
    def energy_per_kg_mj(self) -> float:
        """Energía por kg [MJ/kg] = calor de explosión / 1000."""
        return self.heat_of_explosion_kjkg / 1000.0

    def cylindrical_charge_mass(
        self,
        hole_diameter_m: float,
        charge_length_m: float,
        decoupling_ratio: float = 1.0,
    ) -> float:
        """Calcula la masa de explosivo en una columna cilíndrica.

        Modelo de carga continua (sin decks) con desacoplamiento opcional.

        Fórmula:
            V = π * (dc/2)² * L
            m = V * ρe

        donde:
            dc = hole_diameter_m * decoupling_ratio  [m]
            L  = charge_length_m                     [m]
            ρe = density_kgm3                        [kg/m³]

        Args:
            hole_diameter_m: Diámetro del taladro [m].
            charge_length_m: Longitud de la columna explosiva [m].
            decoupling_ratio: dc/dh ≤ 1.0 (1.0 = acoplado).

        Returns:
            Masa de explosivo [kg].

        References:
            López Jimeno (1995), Capítulo 5: Diseño de la Carga.
        """
        if hole_diameter_m <= 0 or charge_length_m <= 0:
            return 0.0
        effective_diameter_m = hole_diameter_m * min(1.0, decoupling_ratio)
        radius_m = effective_diameter_m / 2.0
        volume_m3 = math.pi * radius_m**2 * charge_length_m
        return volume_m3 * self.density_kgm3

    def decoupling_factor(
        self,
        hole_diameter_mm: float,
        charge_diameter_mm: float,
    ) -> float:
        """Factor de desacoplamiento volumétrico.

        FD = (Dh / Dc)²

        donde FD > 1 implica reducción de presión en pared del taladro.

        Args:
            hole_diameter_mm: Diámetro del taladro [mm].
            charge_diameter_mm: Diámetro del cartucho explosivo [mm].

        Returns:
            Factor de desacoplamiento [-].
        """
        if charge_diameter_mm <= 0:
            return float("inf")
        return (hole_diameter_mm / charge_diameter_mm) ** 2

    def peak_borehole_pressure_mpa(
        self,
        decoupling_ratio: float = 1.0,
    ) -> float:
        """Presión de detonación en pared del taladro [MPa].

        Para carga acoplada (DR=1):
            P = ρe * VOD² / 8   (aproximación Chapman-Jouguet)

        Con desacoplamiento:
            P_eff = P_acoplado / FD^γ  (γ ≈ 1.3, gas adiabático)

        Args:
            decoupling_ratio: dc/dh ≤ 1.0.

        Returns:
            Presión de borehole [MPa].

        References:
            López Jimeno (1995), Eq. 3.15: P_d = ρ_e * D² / 8
        """
        # Presión Chapman-Jouguet
        p_cj_pa = self.density_kgm3 * self.vod_ms**2 / 8.0
        p_cj_mpa = p_cj_pa / 1e6

        if decoupling_ratio >= 1.0:
            return p_cj_mpa

        # Corrección adiabática por desacoplamiento
        gamma = 1.3
        fd = (1.0 / decoupling_ratio) ** 2
        return p_cj_mpa / (fd**gamma)

    def specific_energy_mj_m3(self) -> float:
        """Energía volumétrica disponible [MJ/m³] = Energía/kg * densidad."""
        return self.energy_per_kg_mj * self.density_kgm3 / 1000.0  # MJ/m³

    def __repr__(self) -> str:
        return (
            f"Explosive('{self.name}', "
            f"ρ={self.density_gcc}g/cc, "
            f"VOD={self.vod_ms}m/s, "
            f"RWS={self.rws}, RBS={self.rbs})"
        )


# ══════════════════════════════════════════════════════════════════════════════
# Clase ExplosiveDeck (Columna de carga)
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ExplosiveDeck:
    """Columna (deck) de explosivo dentro de un taladro.

    Permite modelar cargas partidas (deck loading) con distintos
    explosivos separados por material inerte (taco intermedio).

    Attributes:
        explosive: Explosivo asignado a este deck.
        start_depth_m: Profundidad de inicio del deck [m desde collar].
        end_depth_m: Profundidad de fin del deck [m desde collar].
        hole_diameter_m: Diámetro del taladro [m].
        decoupling_ratio: dc/dh (1.0 = acoplado).
        deck_label: Etiqueta (ej. "Carga de pie", "Carga de columna").
    """
    explosive: Explosive
    start_depth_m: float
    end_depth_m: float
    hole_diameter_m: float
    decoupling_ratio: float = 1.0
    deck_label: str = ""

    def __post_init__(self) -> None:
        if self.end_depth_m <= self.start_depth_m:
            raise ValueError("end_depth debe ser > start_depth.")
        if not (0.01 <= self.decoupling_ratio <= 1.0):
            raise ValueError("decoupling_ratio debe estar en [0.01, 1.0].")

    @property
    def length_m(self) -> float:
        """Longitud del deck [m]."""
        return self.end_depth_m - self.start_depth_m

    @property
    def mass_kg(self) -> float:
        """Masa del explosivo en este deck [kg]."""
        return self.explosive.cylindrical_charge_mass(
            self.hole_diameter_m, self.length_m, self.decoupling_ratio
        )

    @property
    def energy_mj(self) -> float:
        """Energía disponible en el deck [MJ] = mass_kg * RWS/100 * ANFO_ref."""
        # ANFO referencia: 3.87 MJ/kg (López Jimeno, 1995)
        anfo_energy_mjkg = 3.87
        return self.mass_kg * (self.explosive.rws / 100.0) * anfo_energy_mjkg

    def __repr__(self) -> str:
        return (
            f"ExplosiveDeck('{self.explosive.name}', "
            f"{self.start_depth_m:.2f}–{self.end_depth_m:.2f}m, "
            f"{self.mass_kg:.2f}kg, "
            f"{self.energy_mj:.2f}MJ)"
        )


# ══════════════════════════════════════════════════════════════════════════════
# Detonador
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Detonator:
    """Detonador con sus propiedades de retardo.

    Attributes:
        detonator_type: Sistema de iniciación.
        manufacturer: Fabricante (para Nonel).
        nominal_delay_ms: Retardo nominal de fábrica [ms].
        actual_delay_ms: Retardo real/programado [ms].
            Para electrónicos: = actual_delay_ms.
            Para Nonel: ≈ nominal con dispersión estadística.
        dispersion_ms: Dispersión típica del retardo [ms].
            Nonel: ±5%; Electrónico: ±0.1ms.
        unit_cost_usd: Costo unitario [USD].
    """
    detonator_type: DetonatorType
    manufacturer: Optional[DetonatorManufacturer] = None
    nominal_delay_ms: float = 0.0
    actual_delay_ms: float = 0.0
    dispersion_ms: float = 1.0
    unit_cost_usd: float = 0.0

    @property
    def is_electronic(self) -> bool:
        return self.detonator_type == DetonatorType.ELECTRONIC

    def __repr__(self) -> str:
        mfg = self.manufacturer.value if self.manufacturer else "N/A"
        return (
            f"Detonator({self.detonator_type.value}, "
            f"{mfg}, {self.nominal_delay_ms}ms±{self.dispersion_ms}ms)"
        )


# ══════════════════════════════════════════════════════════════════════════════
# Catálogo de Explosivos (fuente: López Jimeno, 1995 + ISEE 2011)
# ══════════════════════════════════════════════════════════════════════════════

EXPLOSIVE_CATALOG: Dict[str, Explosive] = {
    # ── ANFO ──────────────────────────────────────────────────
    "anfo": Explosive(
        name="ANFO Standard",
        explosive_type=ExplosiveType.ANFO,
        density_gcc=0.85,
        vod_ms=4500.0,
        rws=100.0,
        rbs=85.0,
        heat_of_explosion_kjkg=3870.0,
        oxygen_balance_pct=+0.5,
        is_water_resistant=False,
        min_diameter_mm=75.0,
        unit_cost_per_kg=1.20,
    ),
    "anfo_pesado": Explosive(
        name="ANFO Pesado",
        explosive_type=ExplosiveType.HEAVY_ANFO,
        density_gcc=1.15,
        vod_ms=5000.0,
        rws=115.0,
        rbs=132.0,
        heat_of_explosion_kjkg=4000.0,
        oxygen_balance_pct=-1.5,
        is_water_resistant=True,
        min_diameter_mm=100.0,
        unit_cost_per_kg=1.55,
    ),
    "anfo_emulsion_5050": Explosive(
        name="ANFO + Emulsión 50/50",
        explosive_type=ExplosiveType.ANFO_EMULSION,
        density_gcc=1.05,
        vod_ms=4800.0,
        rws=108.0,
        rbs=113.0,
        heat_of_explosion_kjkg=3950.0,
        oxygen_balance_pct=-0.5,
        is_water_resistant=True,
        min_diameter_mm=89.0,
        unit_cost_per_kg=1.40,
    ),
    # ── Emulsión ──────────────────────────────────────────────
    "emulsion": Explosive(
        name="Emulsión Sensibilizada",
        explosive_type=ExplosiveType.EMULSION,
        density_gcc=1.20,
        vod_ms=5200.0,
        rws=120.0,
        rbs=144.0,
        heat_of_explosion_kjkg=3600.0,
        oxygen_balance_pct=-1.0,
        is_water_resistant=True,
        min_diameter_mm=64.0,
        unit_cost_per_kg=2.10,
    ),
    "emulsion_granel": Explosive(
        name="Emulsión a Granel",
        explosive_type=ExplosiveType.EMULSION_BULK,
        density_gcc=1.25,
        vod_ms=5500.0,
        rws=125.0,
        rbs=156.0,
        heat_of_explosion_kjkg=3700.0,
        oxygen_balance_pct=-1.2,
        is_water_resistant=True,
        min_diameter_mm=76.0,
        unit_cost_per_kg=1.90,
    ),
    # ── Dinamita ──────────────────────────────────────────────
    "dynamite_32": Explosive(
        name="Dinamita Ø32mm",
        explosive_type=ExplosiveType.DYNAMITE,
        density_gcc=1.45,
        vod_ms=5800.0,
        rws=115.0,
        rbs=167.0,
        heat_of_explosion_kjkg=4200.0,
        oxygen_balance_pct=-2.5,
        is_water_resistant=True,
        min_diameter_mm=32.0,
        cartridge_diameter_mm=32.0,
        cartridge_length_mm=200.0,
        cartridge_mass_kg=0.2,
        unit_cost_per_kg=4.50,
    ),
    "dynamite_65": Explosive(
        name="Dinamita Ø65mm",
        explosive_type=ExplosiveType.DYNAMITE,
        density_gcc=1.50,
        vod_ms=6000.0,
        rws=120.0,
        rbs=180.0,
        heat_of_explosion_kjkg=4300.0,
        oxygen_balance_pct=-2.5,
        is_water_resistant=True,
        min_diameter_mm=65.0,
        cartridge_diameter_mm=65.0,
        cartridge_length_mm=400.0,
        cartridge_mass_kg=1.0,
        unit_cost_per_kg=4.00,
    ),
    # ── Otros ─────────────────────────────────────────────────
    "powergel": Explosive(
        name="PowerGel / Gelatina",
        explosive_type=ExplosiveType.POWERGEL,
        density_gcc=1.40,
        vod_ms=6500.0,
        rws=130.0,
        rbs=182.0,
        heat_of_explosion_kjkg=4500.0,
        oxygen_balance_pct=-3.0,
        is_water_resistant=True,
        min_diameter_mm=25.0,
        unit_cost_per_kg=5.20,
    ),
    "pentolite": Explosive(
        name="Pentolite (Booster)",
        explosive_type=ExplosiveType.PENTOLITE,
        density_gcc=1.65,
        vod_ms=7400.0,
        rws=156.0,
        rbs=257.0,
        heat_of_explosion_kjkg=5300.0,
        oxygen_balance_pct=-10.0,
        is_water_resistant=True,
        min_diameter_mm=0.0,
        unit_cost_per_kg=12.00,
    ),
}


# ══════════════════════════════════════════════════════════════════════════════
# Catálogo de Detonadores Nonel (Serie comercial real)
# Fuente: Orica Exel / Dyno Nobel UniTronic / Austin EZ-Det
# ══════════════════════════════════════════════════════════════════════════════

NONEL_DELAYS_MS: Dict[str, Dict[str, List[int]]] = {
    "orica": {
        "downhole":  [25, 42, 67, 100, 125, 175, 250, 350, 500],
        "surface_ms": [17, 25, 42, 67, 100, 150, 250, 350, 500],
    },
    "dyno_nobel": {
        "downhole":  [9, 17, 25, 42, 67, 100, 150, 200, 350, 500],
        "surface_ms": [17, 25, 42, 67, 100, 150, 200, 350, 500],
    },
    "austin_powder": {
        "downhole":  [17, 25, 42, 67, 100, 150, 250, 350],
        "surface_ms": [17, 25, 42, 67, 100, 150, 250, 350],
    },
}


def find_nearest_nonel_delay(
    manufacturer: str,
    delay_type: str,
    target_ms: float,
) -> int:
    """Encuentra el número Nonel más cercano al retardo objetivo.

    Args:
        manufacturer: Clave en NONEL_DELAYS_MS ('orica', 'dyno_nobel', etc).
        delay_type: 'downhole' o 'surface_ms'.
        target_ms: Retardo objetivo [ms].

    Returns:
        El valor de retardo Nonel más cercano [ms].

    Raises:
        KeyError: Si el fabricante o tipo no existe.
    """
    delays = NONEL_DELAYS_MS[manufacturer][delay_type]
    return min(delays, key=lambda d: abs(d - target_ms))
