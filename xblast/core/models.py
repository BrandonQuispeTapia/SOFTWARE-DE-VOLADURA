"""Modelo de datos del dominio de perforacion y voladura.

Define las entidades que el resto del motor consume: explosivos, macizo rocoso,
columna de carga por plataformas (decks), taladros y el diseno completo.

Todas las unidades son SI salvo indicacion explicita en el nombre del campo
(``_mm``, ``_ms``, ``_deg``, ``_cm``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Enumeraciones
# ---------------------------------------------------------------------------


class HoleType(str, Enum):
    """Funcion del taladro dentro de la malla."""

    PRODUCCION = "Produccion"
    PRECORTE = "Precorte"
    RECORTE = "Recorte"
    AMORTIGUADO = "Amortiguado"
    ALIVIO = "Alivio"
    RAINURA = "Rainura"
    CONTORNO = "Contorno"

    @property
    def color(self) -> str:
        return HOLE_TYPE_COLORS.get(self.value, "#c0392b")


#: Paleta consistente para tipos de taladro (2D, 3D y reportes).
HOLE_TYPE_COLORS: Dict[str, str] = {
    "Produccion": "#c0392b",
    "Precorte": "#2980b9",
    "Recorte": "#16a085",
    "Amortiguado": "#8e44ad",
    "Alivio": "#7f8c8d",
    "Rainura": "#d35400",
    "Contorno": "#27ae60",
}


class DeckKind(str, Enum):
    """Tipo de plataforma dentro de la columna del taladro."""

    CARGA = "Carga"
    TACO = "Taco"
    AIRE = "Aire"


class PatternType(str, Enum):
    """Disposicion geometrica de la malla."""

    CUADRADA = "Cuadrada"
    RECTANGULAR = "Rectangular"
    TRESBOLILLO = "Tresbolillo"


class InitiationSystem(str, Enum):
    """Sistema de iniciacion, determina la dispersion de tiempos."""

    ELECTRONICO = "Electronico"
    NONEL = "Pirotecnico (NONEL)"
    CORDON = "Cordon detonante"

    @property
    def scatter_pct(self) -> float:
        """Coeficiente de variacion tipico del retardo nominal."""
        return {"Electronico": 0.0002, "Pirotecnico (NONEL)": 0.03,
                "Cordon detonante": 0.06}[self.value]


# ---------------------------------------------------------------------------
# Explosivo
# ---------------------------------------------------------------------------


@dataclass
class Explosive:
    """Propiedades termodinamicas y comerciales de un agente de voladura."""

    name: str
    density_g_cm3: float          # densidad de copiado
    vod_m_s: float                # velocidad de detonacion en diametro de uso
    rws: float                    # Relative Weight Strength (ANFO = 100)
    rbs: float                    # Relative Bulk Strength (ANFO = 100)
    energy_mj_kg: float           # energia absoluta en peso
    gas_vol_l_kg: float = 950.0   # volumen de gases a CNPT
    min_diameter_mm: float = 50.0
    water_resistant: bool = False
    cost_usd_kg: float = 0.85
    family: str = "Agente"

    # -- derivados ----------------------------------------------------------
    @property
    def density_kg_m3(self) -> float:
        return self.density_g_cm3 * 1000.0

    def linear_density_kg_m(self, diameter_mm: float, coupling: float = 1.0) -> float:
        """Densidad lineal de carga [kg/m] para un diametro dado.

        ``coupling`` es la relacion diametro de carga / diametro de taladro
        (1.0 = acoplada, <1 = desacoplada tipica de voladura controlada).
        """
        d_charge = (diameter_mm / 1000.0) * max(0.05, min(1.0, coupling))
        return math.pi * (d_charge ** 2) / 4.0 * self.density_kg_m3

    def detonation_pressure_gpa(self, coupling: float = 1.0) -> float:
        """Presion de detonacion P_d = rho * VOD^2 / 4  [GPa]."""
        vod = self.vod_m_s * (0.6 + 0.4 * coupling)
        return self.density_kg_m3 * vod ** 2 / 4.0 / 1e9

    def borehole_pressure_gpa(self, coupling: float = 1.0) -> float:
        """Presion sobre la pared del taladro, con correccion por desacople."""
        return self.detonation_pressure_gpa(coupling) * 0.5 * (coupling ** 2.6)

    def energy_kj_kg(self) -> float:
        return self.energy_mj_kg * 1000.0


# ---------------------------------------------------------------------------
# Macizo rocoso
# ---------------------------------------------------------------------------


@dataclass
class RockMass:
    """Caracterizacion geomecanica del macizo para diseno de voladura."""

    name: str = "Andesita competente"
    density_t_m3: float = 2.70
    ucs_mpa: float = 150.0
    young_gpa: float = 60.0
    poisson: float = 0.25
    gsi: int = 60
    p_wave_m_s: float = 4500.0

    # Indice de volabilidad de Lilly (componentes)
    rmd: float = 25.0     # descripcion del macizo (10 friable / 20 diaclasado / 50 masivo)
    jps: float = 25.0     # espaciamiento de discontinuidades
    jpa: float = 30.0     # orientacion de discontinuidades respecto a la cara
    moisture_pct: float = 2.0

    # -- derivados ----------------------------------------------------------
    @property
    def rdi(self) -> float:
        """Influencia de la densidad: RDI = 25 * SG - 50."""
        return 25.0 * self.density_t_m3 - 50.0

    @property
    def hardness_factor(self) -> float:
        """HF de Lilly: E/3 si E < 50 GPa, sino UCS/5."""
        if self.young_gpa < 50.0:
            return self.young_gpa / 3.0
        return self.ucs_mpa / 5.0

    @property
    def blastability_index(self) -> float:
        """Indice de volabilidad de Lilly (1986)."""
        return 0.5 * (self.rmd + self.jps + self.jpa + self.rdi + self.hardness_factor)

    @property
    def rock_factor_a(self) -> float:
        """Factor de roca A de Kuz-Ram.

        A = 0.06 (RMD + JPS + JPA + RDI + HF) = 0.12 * BI  (Cunningham, 1987).
        Valores tipicos: 4-6 roca media, 7-10 dura, 10-13 muy dura.
        """
        return float(np.clip(0.12 * self.blastability_index, 0.8, 22.0))

    @property
    def impedance(self) -> float:
        """Impedancia acustica [kg/(m2 s)] — gobierna la transmision de energia."""
        return self.density_t_m3 * 1000.0 * self.p_wave_m_s

    @property
    def classification(self) -> str:
        bi = self.blastability_index
        if bi < 30:
            return "Muy facil de volar"
        if bi < 50:
            return "Facil de volar"
        if bi < 70:
            return "Volabilidad media"
        if bi < 90:
            return "Dificil de volar"
        return "Muy dificil de volar"


# ---------------------------------------------------------------------------
# Columna de carga
# ---------------------------------------------------------------------------


@dataclass
class Deck:
    """Plataforma dentro del taladro, medida desde el fondo hacia el collar."""

    kind: DeckKind = DeckKind.CARGA
    length_m: float = 1.0
    explosive: Optional[str] = None    # nombre en el catalogo
    coupling: float = 1.0              # d_carga / d_taladro
    primers: int = 0                   # numero de cebos en la plataforma
    from_toe_m: float = 0.0            # calculado por ChargeColumn.resolve()
    delay_ms: float = 0.0              # retardo propio dentro del taladro

    @property
    def is_charge(self) -> bool:
        return self.kind is DeckKind.CARGA and self.explosive is not None


# ---------------------------------------------------------------------------
# Taladro
# ---------------------------------------------------------------------------


@dataclass
class Hole:
    """Taladro individual con geometria 3D, carga y resultados de analisis."""

    hid: str
    easting: float
    northing: float
    collar_z: float
    length_m: float = 12.0
    diameter_mm: float = 152.0
    dip_deg: float = 90.0          # 90 = vertical, medido desde la horizontal
    azimuth_deg: float = 0.0       # 0 = Norte, sentido horario
    subdrill_m: float = 1.0
    bench_height_m: float = 10.0
    hole_type: str = HoleType.PRODUCCION.value
    decks: List[Deck] = field(default_factory=list)

    # asignaciones de malla / secuencia
    row: int = 0
    col: int = 0
    delay_ms: float = 0.0
    delay_locked: bool = False    # retardo fijado a mano
    charge_locked: bool = False   # carga editada a mano, no la pisa la regla global
    delay_actual_ms: float = 0.0   # con dispersion del sistema de iniciacion

    # resultados calculados por el motor
    burden_real_m: float = 0.0
    spacing_real_m: float = 0.0
    relief_burden_m: float = 0.0   # burden hacia la cara efectiva al momento de disparo
    volume_m3: float = 0.0         # volumen de responsabilidad (Voronoi)
    charge_kg: float = 0.0
    energy_mj: float = 0.0
    powder_factor: float = 0.0     # kg/m3
    energy_factor: float = 0.0     # MJ/t
    x50_cm: float = 0.0
    xmax_cm: float = 0.0
    uniformity_n: float = 1.5
    ppv_contrib_mm_s: float = 0.0
    confinement: float = 1.0       # 0 = libre, 1 = muy confinado

    # -- geometria ----------------------------------------------------------
    @property
    def collar(self) -> np.ndarray:
        return np.array([self.easting, self.northing, self.collar_z], float)

    @property
    def axis(self) -> np.ndarray:
        """Vector unitario del eje del taladro, del collar hacia el fondo."""
        dip = math.radians(self.dip_deg)
        az = math.radians(self.azimuth_deg)
        horiz = math.cos(dip)
        return np.array([horiz * math.sin(az), horiz * math.cos(az), -math.sin(dip)], float)

    @property
    def toe(self) -> np.ndarray:
        return self.collar + self.axis * self.length_m

    @property
    def toe_z(self) -> float:
        return float(self.toe[2])

    @property
    def inclination_from_vertical_deg(self) -> float:
        return 90.0 - self.dip_deg

    @property
    def diameter_m(self) -> float:
        return self.diameter_mm / 1000.0

    @property
    def area_m2(self) -> float:
        return math.pi * self.diameter_m ** 2 / 4.0

    def point_at(self, distance_from_collar_m: float) -> np.ndarray:
        """Punto 3D sobre el eje a una distancia dada desde el collar."""
        return self.collar + self.axis * float(distance_from_collar_m)

    def point_from_toe(self, distance_from_toe_m: float) -> np.ndarray:
        return self.toe - self.axis * float(distance_from_toe_m)

    # -- carga --------------------------------------------------------------
    @property
    def charge_length_m(self) -> float:
        return sum(d.length_m for d in self.decks if d.is_charge)

    @property
    def stemming_length_m(self) -> float:
        return sum(d.length_m for d in self.decks if d.kind is DeckKind.TACO)

    @property
    def air_length_m(self) -> float:
        return sum(d.length_m for d in self.decks if d.kind is DeckKind.AIRE)

    @property
    def collar_stemming_m(self) -> float:
        """Longitud del taco superior (ultima plataforma de la columna)."""
        for d in reversed(self.decks):
            if d.kind is DeckKind.TACO:
                return d.length_m
            if d.is_charge:
                return 0.0
        return 0.0

    @property
    def n_primers(self) -> int:
        return sum(d.primers for d in self.decks)

    @property
    def is_decked(self) -> bool:
        """True si la columna esta partida en cargas independientes.

        Cuenta cargas separadas por taco o aire, no plataformas: dos tramos
        contiguos de explosivo distinto siguen siendo una sola carga.
        """
        separadas = 0
        previa_era_carga = False
        for d in self.decks:
            if d.is_charge and not previa_era_carga:
                separadas += 1
            previa_era_carga = d.is_charge
        return separadas > 1

    def charge_segments(self) -> List[Tuple[np.ndarray, np.ndarray, Deck]]:
        """Segmentos 3D (inicio, fin, deck) de cada plataforma de carga."""
        out: List[Tuple[np.ndarray, np.ndarray, Deck]] = []
        for d in self.decks:
            if d.is_charge:
                p0 = self.point_from_toe(d.from_toe_m)
                p1 = self.point_from_toe(d.from_toe_m + d.length_m)
                out.append((p0, p1, d))
        return out

    def to_dict(self) -> dict:
        data = asdict(self)
        data["decks"] = [
            {**asdict(d), "kind": d.kind.value if isinstance(d.kind, DeckKind) else d.kind}
            for d in self.decks
        ]
        return data


# ---------------------------------------------------------------------------
# Parametros y diseno
# ---------------------------------------------------------------------------


@dataclass
class DirectionVector:
    """Vector que gobierna la propagacion del disparo.

    Es la forma directa de temporizar una voladura: se dibuja una flecha
    sobre la malla y el retardo de cada taladro sale de su posicion respecto
    de ella. ``brb_ms_m`` es el tiempo por metro recorrido en la direccion de
    avance —el alivio del burden— y ``brs_ms_m`` el tiempo por metro en el
    sentido transversal, que abre la salida hacia los lados.

    ``angle_deg`` se mide desde la vertical: 90 deja la flecha horizontal, que
    es lo normal en banco; valores menores la inclinan hacia abajo para que la
    secuencia progrese tambien en profundidad.
    """

    origin_x: float = 0.0
    origin_y: float = 0.0
    origin_z: float = 0.0
    azimuth_deg: float = 180.0
    angle_deg: float = 90.0
    brb_ms_m: float = 3.0
    brs_ms_m: float = 0.0
    length_m: float = 30.0

    # -- geometria ---------------------------------------------------------
    @property
    def origin(self) -> np.ndarray:
        return np.array([self.origin_x, self.origin_y, self.origin_z], float)

    @property
    def direction(self) -> np.ndarray:
        """Vector unitario de avance del disparo."""
        theta = math.radians(self.angle_deg)
        az = math.radians(self.azimuth_deg)
        horiz = math.sin(theta)
        return np.array([horiz * math.sin(az), horiz * math.cos(az),
                         -math.cos(theta)], float)

    @property
    def transverse(self) -> np.ndarray:
        """Unitario horizontal perpendicular al avance, en planta."""
        az = math.radians(self.azimuth_deg)
        return np.array([math.cos(az), -math.sin(az), 0.0], float)

    @property
    def tip(self) -> np.ndarray:
        return self.origin + self.direction * self.length_m

    @classmethod
    def from_points(cls, start, end, **kwargs) -> "DirectionVector":
        """Construye el vector a partir de dos puntos 3D.

        Es lo que usa la colocacion interactiva: el usuario marca de donde sale
        el disparo y hacia donde avanza, y de ahi salen azimut, angulo y
        longitud.
        """
        a = np.asarray(start, float)
        b = np.asarray(end, float)
        d = b - a
        length = float(np.linalg.norm(d))
        if length < 1e-9:
            return cls(origin_x=float(a[0]), origin_y=float(a[1]),
                       origin_z=float(a[2]), **kwargs)
        horiz = float(np.linalg.norm(d[:2]))
        azimuth = math.degrees(math.atan2(d[0], d[1])) % 360.0
        angle = math.degrees(math.atan2(horiz, -d[2]))
        return cls(origin_x=float(a[0]), origin_y=float(a[1]), origin_z=float(a[2]),
                   azimuth_deg=azimuth, angle_deg=angle, length_m=length, **kwargs)


@dataclass
class PatternParams:
    """Parametros geometricos de la malla."""

    burden_m: float = 4.5
    spacing_m: float = 5.2
    diameter_mm: float = 152.0
    bench_height_m: float = 10.0
    subdrill_m: float = 1.2
    stemming_m: float = 3.5
    inclination_deg: float = 15.0     # desde la vertical
    face_azimuth_deg: float = 180.0   # direccion de salida (hacia la cara libre)
    rows: int = 6
    cols: int = 10
    pattern: str = PatternType.TRESBOLILLO.value
    origin_x: float = 0.0
    origin_y: float = 0.0
    origin_z: float = 0.0

    @property
    def hole_length_m(self) -> float:
        incl = math.radians(self.inclination_deg)
        return (self.bench_height_m / max(math.cos(incl), 1e-6)) + self.subdrill_m

    @property
    def dip_deg(self) -> float:
        return 90.0 - self.inclination_deg

    @property
    def stiffness_ratio(self) -> float:
        """H/B — relacion de rigidez; <2 produce mala fragmentacion."""
        return self.bench_height_m / max(self.burden_m, 1e-6)

    @property
    def s_b_ratio(self) -> float:
        return self.spacing_m / max(self.burden_m, 1e-6)

    @property
    def area_per_hole_m2(self) -> float:
        return self.burden_m * self.spacing_m


@dataclass
class TimingParams:
    """Configuracion de la secuencia de salida."""

    system: str = InitiationSystem.ELECTRONICO.value
    hole_delay_ms: float = 17.0       # retardo entre taladros de una misma fila
    row_delay_ms: float = 65.0        # retardo entre filas
    in_hole_delay_ms: float = 0.0     # retardo de fondo
    pattern: str = "Fila por fila"    # "Fila por fila" | "V" | "Diagonal" | "Eco"
    echelon_deg: float = 45.0
    cooperation_window_ms: float = 8.0

    # secuencia electronica
    mode: str = "Patron de amarre"    # o "Vector de direccion" | "Punto central"
    detonator: str = "i-kon II"
    deck_delay_ms: float = 5.0        # entre plataformas del mismo taladro
    inner_delay_ms: float = 0.0       # entre cebos dentro de una plataforma
    snap_to_increment: bool = True    # ajustar al incremento programable
    radial_ms_m: float = 3.0          # ms/m en la salida desde un punto


@dataclass
class SiteConstraints:
    """Restricciones ambientales y de seguridad del entorno."""

    receptor_easting: float = 0.0
    receptor_northing: float = 500.0
    receptor_elev: float = 0.0
    ppv_limit_mm_s: float = 12.7      # USBM RI8507 estructura residencial
    airblast_limit_db: float = 133.0
    exclusion_radius_m: float = 300.0
    k_site: float = 1140.0            # constante de sitio (regresion de campo)
    beta_site: float = 1.6            # exponente de atenuacion
    alpha_site: float = 0.7           # exponente de carga (Holmberg-Persson)


@dataclass
class CostParams:
    """Costos unitarios de perforacion, voladura y aguas abajo."""

    drilling_usd_m: float = 9.5
    primer_usd_unit: float = 12.0
    detonator_usd_unit: float = 18.0
    surface_connector_usd_unit: float = 6.5
    labor_usd_hole: float = 4.0
    loading_usd_t: float = 0.42       # carguio
    hauling_usd_t: float = 0.85       # acarreo
    crushing_usd_t: float = 0.95      # chancado primario (base)
    reference_x50_cm: float = 25.0    # x50 de referencia del modelo mina-planta
    oversize_threshold_cm: float = 80.0
    secondary_breakage_usd_t: float = 3.20


@dataclass
class BlastDesign:
    """Diseno completo: geometria, macizo, carga, secuencia y restricciones."""

    name: str = "Voladura sin titulo"
    site: str = "Mina"
    author: str = ""
    pattern: PatternParams = field(default_factory=PatternParams)
    rock: RockMass = field(default_factory=RockMass)
    timing: TimingParams = field(default_factory=TimingParams)
    constraints: SiteConstraints = field(default_factory=SiteConstraints)
    costs: CostParams = field(default_factory=CostParams)
    holes: List[Hole] = field(default_factory=list)

    # explosivos de la columna (nombres del catalogo)
    column_explosive: str = "ANFO"
    bottom_explosive: str = "Emulsion Gasificada 1.15"
    bottom_charge_m: float = 2.5
    primer_type: str = "Booster Pentolita 450 g"
    stemming_material: str = "Grava chancada 3/8\""

    # topografia, cara libre y vector de direccion
    topography: Optional[np.ndarray] = None      # (N,3)
    free_face: Optional[np.ndarray] = None       # polilinea (M,2) o (M,3)
    direction: Optional[DirectionVector] = None

    @property
    def n_holes(self) -> int:
        return len(self.holes)

    @property
    def total_charge_kg(self) -> float:
        return sum(h.charge_kg for h in self.holes)

    @property
    def total_drilled_m(self) -> float:
        return sum(h.length_m for h in self.holes)

    @property
    def total_volume_m3(self) -> float:
        return sum(h.volume_m3 for h in self.holes)

    @property
    def total_tonnes(self) -> float:
        return self.total_volume_m3 * self.rock.density_t_m3

    @property
    def powder_factor(self) -> float:
        v = self.total_volume_m3
        return self.total_charge_kg / v if v > 0 else 0.0

    @property
    def drill_factor_m_m3(self) -> float:
        v = self.total_volume_m3
        return self.total_drilled_m / v if v > 0 else 0.0
