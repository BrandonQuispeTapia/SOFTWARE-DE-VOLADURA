"""
core/geometry.py
================
Motor de geometría 3D para VOLADURA_PRO_10X.

Convenciones del sistema de coordenadas:
    - X: Este (Easting)
    - Y: Norte (Northing)
    - Z: Elevación (positivo hacia arriba)
    - Azimuth: 0° = Norte, sentido horario (como brújula)
    - Dip: 0° = vertical hacia abajo, 90° = horizontal
      (convención open-pit: un taladro vertical tiene Dip=0°)

Bibliografía:
    - Konya, C.J. & Walter, E.J. (1990). Surface Blast Design. Prentice Hall.
    - Richard Ash (1963). The Mechanics of Rock Breakage. Pit and Quarry.
    - López Jimeno, C. (1995). Manual de Perforación y Voladura de Rocas. IGME.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Sequence, Tuple

import numpy as np


# ══════════════════════════════════════════════════════════════════════════════
# Primitivas 3D
# ══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Point3D:
    """Punto inmutable en espacio cartesiano 3D.

    Attributes:
        x: Coordenada Este [m].
        y: Coordenada Norte [m].
        z: Elevación [m].
    """
    x: float
    y: float
    z: float

    def as_array(self) -> np.ndarray:
        """Retorna el punto como vector columna numpy."""
        return np.array([self.x, self.y, self.z], dtype=np.float64)

    def distance_to(self, other: "Point3D") -> float:
        """Distancia euclidiana 3D entre dos puntos [m]."""
        return float(np.linalg.norm(self.as_array() - other.as_array()))

    def __add__(self, vec: "Vector3D") -> "Point3D":
        a = self.as_array() + vec.as_array()
        return Point3D(float(a[0]), float(a[1]), float(a[2]))

    def __sub__(self, other: "Point3D") -> "Vector3D":
        a = self.as_array() - other.as_array()
        return Vector3D(float(a[0]), float(a[1]), float(a[2]))

    def __repr__(self) -> str:
        return f"Point3D(X={self.x:.3f}, Y={self.y:.3f}, Z={self.z:.3f})"


@dataclass(frozen=True)
class Vector3D:
    """Vector libre en espacio 3D.

    Attributes:
        x: Componente Este.
        y: Componente Norte.
        z: Componente Elevación.
    """
    x: float
    y: float
    z: float

    def as_array(self) -> np.ndarray:
        return np.array([self.x, self.y, self.z], dtype=np.float64)

    @property
    def magnitude(self) -> float:
        """Magnitud (norma L2) del vector."""
        return float(np.linalg.norm(self.as_array()))

    def normalize(self) -> "Vector3D":
        """Retorna el vector unitario."""
        mag = self.magnitude
        if mag < 1e-12:
            raise ValueError("No se puede normalizar un vector nulo.")
        a = self.as_array() / mag
        return Vector3D(float(a[0]), float(a[1]), float(a[2]))

    def dot(self, other: "Vector3D") -> float:
        """Producto punto."""
        return float(np.dot(self.as_array(), other.as_array()))

    def cross(self, other: "Vector3D") -> "Vector3D":
        """Producto vectorial (cruz)."""
        a = np.cross(self.as_array(), other.as_array())
        return Vector3D(float(a[0]), float(a[1]), float(a[2]))

    def scale(self, factor: float) -> "Vector3D":
        a = self.as_array() * factor
        return Vector3D(float(a[0]), float(a[1]), float(a[2]))

    def __repr__(self) -> str:
        return f"Vector3D({self.x:.4f}, {self.y:.4f}, {self.z:.4f})"


# ══════════════════════════════════════════════════════════════════════════════
# Enumeraciones de dominio
# ══════════════════════════════════════════════════════════════════════════════

class PatternType(Enum):
    """Tipos de patrón de perforación."""
    SQUARE = auto()       # Cuadrado: B == S
    RECTANGULAR = auto()  # Rectangular: B != S
    STAGGERED = auto()    # Tresbolillo (quincunx)
    ECHELON = auto()      # Escalonado


class FirePattern(Enum):
    """Secuencias de iniciación."""
    LINE = "ligne"
    V = "v"
    ECHELON = "echelon"
    FAN = "eventail"
    CHEVRON = "chevron"
    CASCADE = "cascade"
    CUSTOM = "custom"


# ══════════════════════════════════════════════════════════════════════════════
# Clase Drillhole (Taladro 3D)
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Drillhole:
    """Representación geométrica completa de un taladro de perforación en 3D.

    Un taladro es un cilindro definido por su collar, orientación
    (azimuth + dip) y dimensiones. El fondo (toe) se calcula
    automáticamente a partir de la geometría.

    Convención de ángulos:
        - azimuth_deg: 0° = Norte, sentido horario.
        - dip_deg: 0° = vertical, 90° = horizontal.
          Un taladro de banco típico tiene dip_deg ∈ [0°, 20°].

    Args:
        hole_id: Identificador único del taladro (ej. "H-01").
        collar: Coordenada 3D de la boca del taladro [m].
        diameter_mm: Diámetro del taladro [mm].
        length: Longitud total del taladro a lo largo del eje [m].
        azimuth_deg: Azimuth de la dirección de perforación [°].
        dip_deg: Inclinación desde la vertical [°]. 0 = vertical.
        bench_height: Altura del banco [m].
        subdrill: Subperforación (más allá del piso del banco) [m].
        stemming: Longitud del taco (retacado) desde el collar [m].
        row: Fila dentro del patrón (1-indexed).
        col: Columna dentro del patrón (1-indexed).

    References:
        Konya & Walter (1990): subdrill ≈ 0.3*B; stemming ≈ 0.7*B.
    """

    hole_id: str
    collar: Point3D
    diameter_mm: float
    length: float
    azimuth_deg: float = 0.0
    dip_deg: float = 0.0
    bench_height: float = 10.0
    subdrill: float = 0.0
    stemming: float = 0.0
    row: int = 1
    col: int = 1

    # Datos de carga (asignados por load_explosives)
    _explosive_decks: List[dict] = field(default_factory=list, repr=False)
    _delay_ms: float = 0.0

    # ─── Propiedades geométricas derivadas ────────────────────────────────

    @property
    def diameter_m(self) -> float:
        """Diámetro en metros."""
        return self.diameter_mm / 1000.0

    @property
    def radius_m(self) -> float:
        """Radio en metros."""
        return self.diameter_m / 2.0

    @property
    def direction_vector(self) -> Vector3D:
        """Vector unitario a lo largo del eje del taladro (collar → toe).

        Matemáticas (Konya, 1990):
            azimuth_rad = azimuth en radianes (desde Norte, CW)
            dip_rad     = inclinación desde la vertical

            dx = sin(azimuth) * sin(dip)
            dy = cos(azimuth) * sin(dip)
            dz = -cos(dip)   ← negativo porque va hacia abajo

        Returns:
            Vector3D unitario en dirección de perforación.
        """
        az = math.radians(self.azimuth_deg)
        dp = math.radians(self.dip_deg)

        dx = math.sin(az) * math.sin(dp)
        dy = math.cos(az) * math.sin(dp)
        dz = -math.cos(dp)  # Hacia abajo

        return Vector3D(dx, dy, dz).normalize()

    @property
    def toe(self) -> Point3D:
        """Coordenada 3D del fondo (toe) del taladro.

        Calculado como:  toe = collar + length * direction_vector
        """
        d = self.direction_vector
        return self.collar + d.scale(self.length)

    @property
    def charge_length(self) -> float:
        """Longitud de columna explosiva [m].

        charge_length = length - stemming

        Args garantizados:
            stemming < length (validado en método).
        """
        cl = self.length - self.stemming
        return max(0.0, cl)

    @property
    def cross_section_area(self) -> float:
        """Área de la sección transversal circular [m²].

        A = π * r²
        """
        return math.pi * self.radius_m ** 2

    def calculate_volume(self) -> float:
        """Calcula el volumen total del cilindro del taladro [m³].

        Fórmula:
            V = π * r² * L

        Returns:
            Volumen del taladro [m³].
        """
        return self.cross_section_area * self.length

    def calculate_charge_volume(self) -> float:
        """Volumen de la columna explosiva [m³].

        V_charge = π * r² * charge_length
        """
        return self.cross_section_area * self.charge_length

    def point_at_depth(self, depth: float) -> Point3D:
        """Coordenada 3D de un punto a profundidad 'depth' desde el collar.

        Útil para interpolar datos MWD a lo largo del taladro.

        Args:
            depth: Profundidad desde el collar a lo largo del eje [m].
                   Debe ser ≥ 0 y ≤ self.length.

        Returns:
            Point3D en la posición solicitada.

        Raises:
            ValueError: Si depth está fuera del rango válido.
        """
        if depth < 0 or depth > self.length + 1e-9:
            raise ValueError(
                f"depth={depth:.2f} fuera del rango [0, {self.length:.2f}] m."
            )
        return self.collar + self.direction_vector.scale(depth)

    def load_explosives(
        self,
        explosive_data: dict,
        top_stemming: float,
        bottom_subdrill: float = 0.0,
        decoupling_ratio: float = 1.0,
    ) -> None:
        """Asigna la columna explosiva al taladro.

        Registra un 'deck' (columna continua) de explosivo. Para cargas
        partidas (deck loading), llamar múltiples veces con distintos
        intervalos de profundidad.

        Args:
            explosive_data: Dict con claves 'name', 'density_gcc',
                            'vod_ms', 'rws', 'rbs'.
            top_stemming: Longitud del taco desde el collar [m].
            bottom_subdrill: Subperforación efectiva desde el piso [m].
            decoupling_ratio: dc/dh — relación carga/taladro (≤ 1.0).
                              1.0 = acoplado; < 1.0 = desacoplado.

        Side Effects:
            Actualiza self._explosive_decks con el nuevo deck.
        """
        charge_start_depth = top_stemming
        charge_end_depth = self.length - bottom_subdrill
        charge_len = max(0.0, charge_end_depth - charge_start_depth)

        # Volumen con desacople: V = π*(dc/2)² * L
        eff_radius = self.radius_m * decoupling_ratio
        eff_volume = math.pi * eff_radius**2 * charge_len  # m³

        # Masa: ρ [g/cc] → [kg/m³] = ρ * 1000
        density_kgm3 = explosive_data.get("density_gcc", 0.85) * 1000.0
        charge_mass_kg = eff_volume * density_kgm3

        deck = {
            "explosive": explosive_data,
            "start_depth_m": charge_start_depth,
            "end_depth_m": charge_end_depth,
            "charge_length_m": charge_len,
            "decoupling_ratio": decoupling_ratio,
            "effective_volume_m3": eff_volume,
            "charge_mass_kg": charge_mass_kg,
        }
        self._explosive_decks.append(deck)

    @property
    def total_charge_kg(self) -> float:
        """Masa total de explosivo en todos los decks [kg]."""
        return sum(d["charge_mass_kg"] for d in self._explosive_decks)

    @property
    def delay_ms(self) -> float:
        """Retardo de iniciación asignado [ms]."""
        return self._delay_ms

    @delay_ms.setter
    def delay_ms(self, value: float) -> None:
        if value < 0:
            raise ValueError("El retardo no puede ser negativo.")
        self._delay_ms = value

    def get_axis_polyline(self, n_points: int = 10) -> List[Point3D]:
        """Genera una polilínea de N puntos a lo largo del eje del taladro.

        Útil para renderizado VTK (PyVista).

        Args:
            n_points: Número de puntos intermedios + extremos.

        Returns:
            Lista de Point3D desde collar hasta toe.
        """
        depths = np.linspace(0.0, self.length, n_points)
        return [self.point_at_depth(d) for d in depths]

    def __repr__(self) -> str:
        return (
            f"Drillhole(id='{self.hole_id}', "
            f"Ø={self.diameter_mm:.0f}mm, L={self.length:.2f}m, "
            f"Az={self.azimuth_deg:.1f}°, Dip={self.dip_deg:.1f}°, "
            f"charge={self.total_charge_kg:.1f}kg)"
        )


# ══════════════════════════════════════════════════════════════════════════════
# Clase BlastPattern (Patrón de Perforación)
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class BlastPattern:
    """Patrón completo de perforación para un banco de voladura.

    Contiene la malla geométrica y la colección de Drillholes.
    Los parámetros B y S se calculan según Konya & Richard Ash.

    Attributes:
        pattern_id: Identificador único.
        origin: Origen del patrón (collar del taladro [1,1]) [m].
        burden: Distancia de burden (fila → cara libre) [m].
        spacing: Espaciamiento entre taladros en fila [m].
        bench_height: Altura del banco [m].
        subdrill: Subperforación [m].
        stemming: Taco [m].
        num_rows: Número de filas.
        holes_per_row: Taladros por fila.
        azimuth_face: Azimuth hacia la cara libre [°].
        drilling_angle_deg: Ángulo de inclinación del taladro [°].
        pattern_type: Tipo de distribución (square/staggered).
        holes: Lista de Drillhole generados.

    References:
        Konya (1990): B = 0.012 * (2*SGe/SGr + 1.5) * De
            donde SGe = densidad explosivo, SGr = densidad roca, De = diámetro mm.
        Richard Ash (1963): S = (1.0 a 1.5) * B
    """

    pattern_id: str
    origin: Point3D
    burden: float
    spacing: float
    bench_height: float
    subdrill: float
    stemming: float
    num_rows: int
    holes_per_row: int
    azimuth_face: float = 0.0
    drilling_angle_deg: float = 0.0
    pattern_type: PatternType = PatternType.RECTANGULAR
    holes: List[Drillhole] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.burden <= 0:
            raise ValueError(f"Burden debe ser > 0, recibido: {self.burden}")
        if self.spacing <= 0:
            raise ValueError(f"Spacing debe ser > 0, recibido: {self.spacing}")
        if self.num_rows < 1 or self.holes_per_row < 1:
            raise ValueError("num_rows y holes_per_row deben ser ≥ 1.")

    @property
    def total_holes(self) -> int:
        """Número total de taladros en el patrón."""
        return len(self.holes)

    @property
    def total_charge_kg(self) -> float:
        """Carga explosiva total del patrón [kg]."""
        return sum(h.total_charge_kg for h in self.holes)

    @property
    def rock_volume_m3(self) -> float:
        """Volumen de roca diseñado para volar [m³].

        V = B * S * H * N_taladros
        """
        return self.burden * self.spacing * self.bench_height * self.total_holes

    @property
    def powder_factor_kg_m3(self) -> float:
        """Factor de carga [kg/m³] = Carga Total / Volumen Roca."""
        vol = self.rock_volume_m3
        return self.total_charge_kg / vol if vol > 0 else 0.0

    def generate_grid(
        self,
        diameter_mm: float,
        length_override: Optional[float] = None,
    ) -> None:
        """Genera la cuadrícula de Drillholes según el patrón geométrico.

        Calcula la posición 3D (collar) de cada taladro usando
        transformación de coordenadas basada en el azimuth de la cara libre.

        Args:
            diameter_mm: Diámetro de todos los taladros [mm].
            length_override: Si se provee, fuerza esta longitud.
                             Por defecto: (bench_height + subdrill) / cos(dip).

        Side Effects:
            Rellena self.holes con los Drillhole generados.
        """
        self.holes.clear()

        # Ángulo de perforación: 0° = vertical, positivo = inclinado hacia cara libre
        dip_rad = math.radians(self.drilling_angle_deg)
        az_perp = self.azimuth_face  # Azimuth perpendicular a la cara libre

        # Longitud del taladro a lo largo de su eje
        if length_override is not None:
            hole_length = length_override
        else:
            cos_dip = math.cos(dip_rad) if self.drilling_angle_deg < 90 else 1e-6
            hole_length = (self.bench_height + self.subdrill) / cos_dip

        # Vectores de la grilla en el plano horizontal
        # row_dir: dirección de avance (hacia la cara libre)
        az_row = math.radians(self.azimuth_face)
        row_dir = Vector3D(math.sin(az_row), math.cos(az_row), 0.0)

        # col_dir: dirección a lo largo de la fila (perpendicular a row_dir)
        az_col = math.radians(self.azimuth_face + 90.0)
        col_dir = Vector3D(math.sin(az_col), math.cos(az_col), 0.0)

        hole_counter = 1
        for r in range(self.num_rows):
            for c in range(self.holes_per_row):
                # Offset de tresbolillo en filas impares
                col_offset = c
                if self.pattern_type == PatternType.STAGGERED and r % 2 == 1:
                    col_offset += 0.5

                # Posición del collar en 3D
                row_vec = row_dir.scale(r * self.burden)
                col_vec = col_dir.scale(col_offset * self.spacing)
                offset = Vector3D(
                    row_vec.x + col_vec.x,
                    row_vec.y + col_vec.y,
                    row_vec.z + col_vec.z,
                )
                collar = self.origin + offset

                hole = Drillhole(
                    hole_id=f"H-{hole_counter:03d}",
                    collar=collar,
                    diameter_mm=diameter_mm,
                    length=hole_length,
                    azimuth_deg=az_perp,
                    dip_deg=self.drilling_angle_deg,
                    bench_height=self.bench_height,
                    subdrill=self.subdrill,
                    stemming=self.stemming,
                    row=r + 1,
                    col=c + 1,
                )
                self.holes.append(hole)
                hole_counter += 1

    @staticmethod
    def konya_burden(
        diameter_mm: float,
        density_explosive_gcc: float,
        density_rock_tm3: float,
    ) -> float:
        """Burden óptimo según fórmula empírica de Konya (1990).

        Fórmula:
            B = 0.012 * (2*SGe/SGr + 1.5) * De

        donde:
            SGe = densidad del explosivo [g/cc]
            SGr = densidad de la roca [t/m³] (equivalente a g/cc)
            De  = diámetro del explosivo ≈ diámetro del taladro [mm]

        Args:
            diameter_mm: Diámetro del taladro [mm].
            density_explosive_gcc: Densidad del explosivo [g/cc].
            density_rock_tm3: Densidad de la roca [t/m³].

        Returns:
            Burden recomendado [m].

        References:
            Konya, C.J. & Walter, E.J. (1990). Surface Blast Design.
            Prentice Hall, Chapter 4, Eq. 4.1.
        """
        sge = density_explosive_gcc
        sgr = density_rock_tm3
        de = diameter_mm
        burden = 0.012 * (2.0 * sge / sgr + 1.5) * de
        return round(burden, 3)

    @staticmethod
    def ash_spacing(burden: float, ratio: float = 1.25) -> float:
        """Espaciamiento según Richard Ash (1963).

        S = ratio * B

        Ratio típico: 1.0 – 1.5.
        Para roca media: ratio = 1.25 (Ash, 1963).

        Args:
            burden: Burden calculado [m].
            ratio: S/B ratio (default 1.25).

        Returns:
            Espaciamiento recomendado [m].

        References:
            Ash, R.L. (1963). The Mechanics of Rock Breakage.
            Pit and Quarry, 56(2), 98–100.
        """
        return round(burden * ratio, 3)

    def get_collar_matrix(self) -> np.ndarray:
        """Retorna una matriz (N×3) con las coordenadas de todos los collares.

        Útil para renderizado masivo en PyVista / numpy.

        Returns:
            np.ndarray shape (N, 3): [X, Y, Z] por fila.
        """
        if not self.holes:
            return np.empty((0, 3))
        return np.array([h.collar.as_array() for h in self.holes])

    def get_toe_matrix(self) -> np.ndarray:
        """Retorna una matriz (N×3) con las coordenadas de todos los fondos."""
        if not self.holes:
            return np.empty((0, 3))
        return np.array([h.toe.as_array() for h in self.holes])

    def get_hole_by_id(self, hole_id: str) -> Optional[Drillhole]:
        """Busca un taladro por su ID.

        Args:
            hole_id: Identificador del taladro.

        Returns:
            El Drillhole encontrado o None.
        """
        return next((h for h in self.holes if h.hole_id == hole_id), None)

    def summary(self) -> dict:
        """Resumen estadístico del patrón para reportes.

        Returns:
            Dict con KPIs principales del patrón.
        """
        return {
            "pattern_id": self.pattern_id,
            "total_holes": self.total_holes,
            "burden_m": self.burden,
            "spacing_m": self.spacing,
            "bench_height_m": self.bench_height,
            "subdrill_m": self.subdrill,
            "stemming_m": self.stemming,
            "rock_volume_m3": round(self.rock_volume_m3, 1),
            "total_charge_kg": round(self.total_charge_kg, 1),
            "powder_factor_kg_m3": round(self.powder_factor_kg_m3, 4),
            "pattern_type": self.pattern_type.name,
            "drilling_angle_deg": self.drilling_angle_deg,
        }

    def __repr__(self) -> str:
        return (
            f"BlastPattern('{self.pattern_id}', "
            f"{self.total_holes} holes, "
            f"B={self.burden:.2f}m, S={self.spacing:.2f}m)"
        )
