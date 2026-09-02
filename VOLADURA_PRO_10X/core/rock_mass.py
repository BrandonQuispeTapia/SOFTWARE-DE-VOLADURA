"""
core/rock_mass.py
=================
Modelos geomecánicos del macizo rocoso para VOLADURA_PRO_10X.

Soporta clasificaciones RMR (Bieniawski), GSI y datos MWD
(Measure While Drilling) como perfiles de dureza a lo largo del taladro.

Bibliografía:
    - Bieniawski, Z.T. (1989). Engineering Rock Mass Classifications. Wiley.
    - Barton, N. (1974). Q-System. NGI.
    - López Jimeno (1995). Manual de Perforación y Voladura de Rocas. IGME.
    - Schunnesson, H. (1998). Rock Characterisation Using Percussive Drilling.
      Int. J. Rock Mech. Min. Sci., 35(6), 711-725.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np


# ══════════════════════════════════════════════════════════════════════════════
# Enumeraciones de dominio
# ══════════════════════════════════════════════════════════════════════════════

class RockClass(Enum):
    """Clasificación cualitativa del macizo rocoso (Bieniawski, 1989)."""
    VERY_GOOD  = "I"     # RMR 81-100
    GOOD       = "II"    # RMR 61-80
    FAIR       = "III"   # RMR 41-60
    POOR       = "IV"    # RMR 21-40
    VERY_POOR  = "V"     # RMR 0-20


class BlastabilityIndex(Enum):
    """Índice de volabilidad según resistencia UCS."""
    EASY    = auto()   # UCS < 50 MPa
    MEDIUM  = auto()   # 50–100 MPa
    HARD    = auto()   # 100–150 MPa
    VERY_HARD = auto() # > 150 MPa


# ══════════════════════════════════════════════════════════════════════════════
# Registro MWD (Measure While Drilling)
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class MWDRecord:
    """Registro de un intervalo de Perforación con Medición (MWD).

    Cada registro representa un segmento del taladro con propiedades
    físicas medidas por los sensores de la perforadora.

    Attributes:
        depth_from_m: Profundidad de inicio del intervalo [m].
        depth_to_m: Profundidad de fin del intervalo [m].
        penetration_rate_mmin: Velocidad de penetración [m/min].
        rotation_pressure_bar: Presión de rotación [bar].
        feed_pressure_bar: Presión de avance [bar].
        percussion_pressure_bar: Presión de percusión [bar].
        flush_flow_lmin: Flujo de agua de barrido [L/min].
        bit_diameter_mm: Diámetro de la broca [mm].
        rock_strength_mpa: UCS estimada del intervalo [MPa].
            Calculado via correlación de Schunnesson (1998).

    References:
        Schunnesson, H. (1998): UCS ≈ f(feed_pressure, rotation_pressure)
    """
    depth_from_m: float
    depth_to_m: float
    penetration_rate_mmin: float = 0.0
    rotation_pressure_bar: float = 0.0
    feed_pressure_bar: float = 0.0
    percussion_pressure_bar: float = 0.0
    flush_flow_lmin: float = 0.0
    bit_diameter_mm: float = 0.0

    def __post_init__(self) -> None:
        if self.depth_from_m < 0:
            raise ValueError("depth_from_m no puede ser negativo.")
        if self.depth_to_m <= self.depth_from_m:
            raise ValueError(
                f"depth_to ({self.depth_to_m}) debe ser > depth_from ({self.depth_from_m})."
            )

    @property
    def interval_length_m(self) -> float:
        """Longitud del intervalo [m]."""
        return self.depth_to_m - self.depth_from_m

    @property
    def mid_depth_m(self) -> float:
        """Profundidad media del intervalo [m]."""
        return (self.depth_from_m + self.depth_to_m) / 2.0

    @property
    def rock_strength_mpa(self) -> float:
        """Resistencia UCS estimada por correlación MWD [MPa].

        Correlación empírica simplificada (Schunnesson, 1998):
            UCS ≈ k1 * (feed_pressure / penetration_rate)

        donde k1 = 1.5 es una constante de calibración general.
        Debe calibrarse con datos de laboratorio para cada sitio.

        Returns:
            Resistencia estimada [MPa]. Retorna 0 si sin datos.
        """
        if self.penetration_rate_mmin <= 0 or self.feed_pressure_bar <= 0:
            return 0.0
        k1 = 1.5
        return k1 * (self.feed_pressure_bar / self.penetration_rate_mmin)

    @property
    def drillability_index(self) -> float:
        """Índice de perforabilidad (inverso de la penetrabilidad).

        DI = 1 / PR  [min/m]

        Valores altos → roca dura.
        """
        if self.penetration_rate_mmin <= 0:
            return float("inf")
        return 1.0 / self.penetration_rate_mmin

    def __repr__(self) -> str:
        return (
            f"MWDRecord({self.depth_from_m:.2f}–{self.depth_to_m:.2f}m, "
            f"PR={self.penetration_rate_mmin:.2f}m/min, "
            f"UCS≈{self.rock_strength_mpa:.1f}MPa)"
        )


# ══════════════════════════════════════════════════════════════════════════════
# Perfil MWD del taladro
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class DrillholeMWD:
    """Perfil MWD completo a lo largo de un taladro.

    Contiene la secuencia ordenada de MWDRecords y expone
    propiedades estadísticas del macizo rocoso perforado.

    Attributes:
        hole_id: ID del taladro asociado.
        total_length_m: Longitud total del taladro [m].
        records: Lista ordenada de MWDRecord.
    """
    hole_id: str
    total_length_m: float
    records: List[MWDRecord] = field(default_factory=list)

    def add_record(self, record: MWDRecord) -> None:
        """Agrega un registro MWD y mantiene el orden por profundidad.

        Args:
            record: MWDRecord a agregar.
        """
        self.records.append(record)
        self.records.sort(key=lambda r: r.depth_from_m)

    @property
    def average_penetration_rate(self) -> float:
        """Velocidad de penetración media ponderada por longitud [m/min]."""
        total_len = sum(r.interval_length_m for r in self.records)
        if total_len <= 0:
            return 0.0
        return sum(
            r.penetration_rate_mmin * r.interval_length_m for r in self.records
        ) / total_len

    @property
    def average_ucs_mpa(self) -> float:
        """UCS media ponderada por longitud del intervalo [MPa]."""
        total_len = sum(r.interval_length_m for r in self.records)
        if total_len <= 0:
            return 0.0
        return sum(
            r.rock_strength_mpa * r.interval_length_m for r in self.records
        ) / total_len

    @property
    def hardness_profile(self) -> List[Tuple[float, float]]:
        """Perfil de dureza: lista de (profundidad_media, UCS_MPa).

        Útil para graficar variación litológica a lo largo del taladro.

        Returns:
            Lista de tuplas (mid_depth_m, ucs_mpa).
        """
        return [(r.mid_depth_m, r.rock_strength_mpa) for r in self.records]

    def ucs_at_depth(self, depth_m: float) -> Optional[float]:
        """Retorna la UCS estimada en una profundidad específica [MPa].

        Interpola entre intervalos si la profundidad cae entre registros.

        Args:
            depth_m: Profundidad desde el collar [m].

        Returns:
            UCS [MPa] o None si no hay datos en esa profundidad.
        """
        for record in self.records:
            if record.depth_from_m <= depth_m < record.depth_to_m:
                return record.rock_strength_mpa
        return None

    def get_weak_zones(self, ucs_threshold_mpa: float = 30.0) -> List[MWDRecord]:
        """Identifica zonas de baja resistencia (posibles fracturas, arcillas).

        Args:
            ucs_threshold_mpa: Umbral de UCS [MPa]. Default 30 MPa.

        Returns:
            Lista de MWDRecords con UCS < umbral.
        """
        return [r for r in self.records if r.rock_strength_mpa < ucs_threshold_mpa]

    def get_hard_zones(self, ucs_threshold_mpa: float = 100.0) -> List[MWDRecord]:
        """Identifica zonas de alta resistencia que requieren mayor energía.

        Args:
            ucs_threshold_mpa: Umbral de UCS [MPa]. Default 100 MPa.

        Returns:
            Lista de MWDRecords con UCS ≥ umbral.
        """
        return [r for r in self.records if r.rock_strength_mpa >= ucs_threshold_mpa]

    def to_numpy_profile(self) -> np.ndarray:
        """Retorna perfil como array numpy shape (N, 2).

        Columnas: [mid_depth_m, ucs_mpa].
        Útil para análisis scipy o plotting.
        """
        if not self.records:
            return np.empty((0, 2))
        return np.array([[r.mid_depth_m, r.rock_strength_mpa] for r in self.records])

    def __repr__(self) -> str:
        return (
            f"DrillholeMWD(hole='{self.hole_id}', "
            f"{len(self.records)} registros, "
            f"UCS_mean={self.average_ucs_mpa:.1f}MPa)"
        )


# ══════════════════════════════════════════════════════════════════════════════
# Propiedades Geomecánicas de la Roca
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class RockProperties:
    """Propiedades físicas y geomecánicas de un dominio litológico.

    Parámetros directamente usados en cálculos de:
        - Burden/Spacing (Konya): density_tm3
        - Kuz-Ram fragmentación: rock_factor_A
        - PPV / vibraciones: density_tm3, p_wave_velocity_ms
        - Flyrock: ucs_mpa, tensile_strength_mpa

    Attributes:
        name: Nombre del litotipo (ej. "Granito Porfirítico").
        density_tm3: Densidad de la roca in situ [t/m³].
        ucs_mpa: Resistencia a la compresión uniaxial [MPa].
        tensile_strength_mpa: Resistencia a la tracción brasileña [MPa].
        youngs_modulus_gpa: Módulo de Young estático [GPa].
        poissons_ratio: Relación de Poisson [-].
        p_wave_velocity_ms: Velocidad de onda P [m/s].
        s_wave_velocity_ms: Velocidad de onda S [m/s].
        rqd_percent: Rock Quality Designation [%] (0–100).
        joint_spacing_m: Espaciamiento medio de discontinuidades [m].
        joint_condition: Condición de las juntas (1–30 para RMR).
        groundwater_rating: Condición de agua subterránea RMR (0–15).
        rock_factor_A: Factor de roca para Kuz-Ram.
            Valores típicos: blanda=4, media=6, dura=8, gneis=9, cuarcita=10.
        swell_factor_percent: Factor de esponjamiento del material volado [%].

    References:
        Bieniawski (1989): RMR = sum(ratings 1-5 + correction orientación).
        Cunningham (1987): rock_factor_A para Kuz-Ram.
    """

    name: str
    density_tm3: float
    ucs_mpa: float
    tensile_strength_mpa: float = 0.0
    youngs_modulus_gpa: float = 0.0
    poissons_ratio: float = 0.25
    p_wave_velocity_ms: float = 3500.0
    s_wave_velocity_ms: float = 2000.0
    rqd_percent: float = 75.0
    joint_spacing_m: float = 0.3
    joint_condition: float = 20.0
    groundwater_rating: float = 10.0
    rock_factor_A: float = 6.0
    swell_factor_percent: float = 30.0

    def __post_init__(self) -> None:
        if not (1.0 <= self.density_tm3 <= 5.0):
            raise ValueError(
                f"density_tm3={self.density_tm3} fuera del rango [1, 5] t/m³."
            )
        if self.ucs_mpa < 0:
            raise ValueError("UCS no puede ser negativa.")
        if not (0 <= self.rqd_percent <= 100):
            raise ValueError("RQD debe estar entre 0 y 100 %.")

    @property
    def blastability_index(self) -> BlastabilityIndex:
        """Índice de volabilidad basado en UCS."""
        if self.ucs_mpa < 50:
            return BlastabilityIndex.EASY
        elif self.ucs_mpa < 100:
            return BlastabilityIndex.MEDIUM
        elif self.ucs_mpa < 150:
            return BlastabilityIndex.HARD
        else:
            return BlastabilityIndex.VERY_HARD

    @property
    def rmr89(self) -> float:
        """Calcula el Rock Mass Rating (Bieniawski, 1989).

        Suma de 5 parámetros (orientación no incluida aquí):
            R1: Resistencia material intacto (UCS)
            R2: RQD
            R3: Espaciamiento de discontinuidades
            R4: Condición de discontinuidades
            R5: Condiciones de agua subterránea

        Returns:
            RMR89 calculado (0–100, sin corrección de orientación).

        References:
            Bieniawski, Z.T. (1989). Engineering Rock Mass Classifications.
            John Wiley & Sons, Table 4.2.
        """
        # R1: Resistencia del material intacto (UCS)
        if self.ucs_mpa > 250:
            r1 = 15
        elif self.ucs_mpa > 100:
            r1 = 12
        elif self.ucs_mpa > 50:
            r1 = 7
        elif self.ucs_mpa > 25:
            r1 = 4
        elif self.ucs_mpa > 5:
            r1 = 2
        else:
            r1 = 1

        # R2: RQD
        r2 = min(20, max(3, self.rqd_percent * 0.2))

        # R3: Espaciamiento de discontinuidades
        if self.joint_spacing_m > 2.0:
            r3 = 20
        elif self.joint_spacing_m > 0.6:
            r3 = 15
        elif self.joint_spacing_m > 0.2:
            r3 = 10
        elif self.joint_spacing_m > 0.06:
            r3 = 8
        else:
            r3 = 5

        # R4: Condición de discontinuidades (0–30, entrada directa)
        r4 = float(max(0, min(30, self.joint_condition)))

        # R5: Condiciones de agua subterránea (0–15, entrada directa)
        r5 = float(max(0, min(15, self.groundwater_rating)))

        return r1 + r2 + r3 + r4 + r5

    @property
    def rock_class(self) -> RockClass:
        """Clase del macizo según RMR89 (Bieniawski, 1989)."""
        rmr = self.rmr89
        if rmr >= 81:
            return RockClass.VERY_GOOD
        elif rmr >= 61:
            return RockClass.GOOD
        elif rmr >= 41:
            return RockClass.FAIR
        elif rmr >= 21:
            return RockClass.POOR
        else:
            return RockClass.VERY_POOR

    @property
    def gsi(self) -> float:
        """GSI aproximado a partir de RMR89.

        GSI ≈ RMR89 - 5  (para RMR > 18)
        (Hoek & Brown, 1997)

        Returns:
            GSI estimado (0–100).
        """
        return max(0.0, self.rmr89 - 5.0)

    @property
    def fragmentation_coefficient_f(self) -> float:
        """Coeficiente de fragmentabilidad (adimensional).

        Derivado de la Hardgrove-based formula simplificada.
        Usado en algunas variantes de Kuz-Ram como factor de corrección:

        F = (UCS / 100)^0.5  (normalizado a roca media = 100 MPa)

        Returns:
            Coeficiente F [-].
        """
        return math.sqrt(self.ucs_mpa / 100.0)

    def suggest_rock_factor_A(self) -> float:
        """Sugiere el factor A para Kuz-Ram basado en UCS y RMR.

        Escala empírica (Cunningham, 1987):
            UCS < 50 MPa  → A ≈ 4  (blanda)
            50–100 MPa    → A ≈ 6  (media)
            100–150 MPa   → A ≈ 8  (dura)
            > 150 MPa     → A ≈ 10 (muy dura)

        Ajuste por RMR89: A * (1 - (80 - RMR89)/200) si RMR < 80.

        Returns:
            Factor A sugerido para Kuz-Ram.
        """
        if self.ucs_mpa < 50:
            base_a = 4.0
        elif self.ucs_mpa < 100:
            base_a = 6.0
        elif self.ucs_mpa < 150:
            base_a = 8.0
        else:
            base_a = 10.0

        rmr = self.rmr89
        correction = 1.0 - max(0, (80 - rmr) / 200.0)
        return round(base_a * correction, 2)

    def to_dict(self) -> Dict:
        """Serializa las propiedades a diccionario para reportes/JSON."""
        return {
            "name": self.name,
            "density_tm3": self.density_tm3,
            "ucs_mpa": self.ucs_mpa,
            "tensile_strength_mpa": self.tensile_strength_mpa,
            "p_wave_velocity_ms": self.p_wave_velocity_ms,
            "rqd_percent": self.rqd_percent,
            "rmr89": round(self.rmr89, 1),
            "rock_class": self.rock_class.value,
            "gsi": round(self.gsi, 1),
            "rock_factor_A": self.rock_factor_A,
            "blastability": self.blastability_index.name,
        }

    def __repr__(self) -> str:
        return (
            f"RockProperties('{self.name}', "
            f"ρ={self.density_tm3}t/m³, "
            f"UCS={self.ucs_mpa}MPa, "
            f"RMR={self.rmr89:.0f} [{self.rock_class.value}])"
        )


# ══════════════════════════════════════════════════════════════════════════════
# Estrato litológico (para perfiles estratigráficos)
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class LithologicStratum:
    """Estrato litológico a una profundidad dentro del taladro.

    Permite modelar variación vertical de propiedades dentro de un banco,
    esencial para ajuste automático de carga con datos MWD.

    Attributes:
        depth_from_m: Tope del estrato [m desde collar].
        depth_to_m: Base del estrato [m desde collar].
        rock: Propiedades geomecánicas de este estrato.
        name_override: Nombre específico (sobreescribe rock.name).
    """
    depth_from_m: float
    depth_to_m: float
    rock: RockProperties
    name_override: Optional[str] = None

    @property
    def thickness_m(self) -> float:
        """Espesor del estrato [m]."""
        return self.depth_to_m - self.depth_from_m

    @property
    def label(self) -> str:
        return self.name_override or self.rock.name

    def __repr__(self) -> str:
        return (
            f"LithologicStratum('{self.label}', "
            f"{self.depth_from_m:.1f}–{self.depth_to_m:.1f}m, "
            f"UCS={self.rock.ucs_mpa}MPa)"
        )


# ══════════════════════════════════════════════════════════════════════════════
# Catálogo de rocas predefinidas (basado en López Jimeno, 1995)
# ══════════════════════════════════════════════════════════════════════════════

ROCK_CATALOG: Dict[str, RockProperties] = {
    "soft": RockProperties(
        name="Roca Blanda (Caliza/Esquisto)",
        density_tm3=2.3,
        ucs_mpa=30.0,
        tensile_strength_mpa=3.0,
        p_wave_velocity_ms=2500.0,
        rqd_percent=65.0,
        rock_factor_A=4.0,
        swell_factor_percent=25.0,
    ),
    "medium": RockProperties(
        name="Roca Media (Arenisca/Dolomita)",
        density_tm3=2.6,
        ucs_mpa=75.0,
        tensile_strength_mpa=7.0,
        p_wave_velocity_ms=3500.0,
        rqd_percent=75.0,
        rock_factor_A=6.0,
        swell_factor_percent=30.0,
    ),
    "hard": RockProperties(
        name="Roca Dura (Granito/Basalto)",
        density_tm3=2.7,
        ucs_mpa=120.0,
        tensile_strength_mpa=12.0,
        p_wave_velocity_ms=5000.0,
        rqd_percent=85.0,
        rock_factor_A=8.0,
        swell_factor_percent=33.0,
    ),
    "gneiss": RockProperties(
        name="Gneis",
        density_tm3=2.75,
        ucs_mpa=140.0,
        tensile_strength_mpa=14.0,
        p_wave_velocity_ms=5500.0,
        rqd_percent=80.0,
        rock_factor_A=9.0,
        swell_factor_percent=35.0,
    ),
    "very_hard": RockProperties(
        name="Roca Muy Dura (Cuarcita)",
        density_tm3=2.85,
        ucs_mpa=200.0,
        tensile_strength_mpa=20.0,
        p_wave_velocity_ms=6000.0,
        rqd_percent=90.0,
        rock_factor_A=10.0,
        swell_factor_percent=38.0,
    ),
}
