"""
core/physics/fragmentation.py
=============================
Modelo predictivo de fragmentación de rocas (Kuz-Ram Extendido).

Este módulo calcula la distribución granulométrica resultante de la voladura
basándose en las propiedades del macizo rocoso, parámetros de diseño
y propiedades de los explosivos.

Bibliografía:
    - Cunningham, C.V.B. (1987). Fragmentation Estimations and the
      Kuz-Ram Model. Proc. 2nd Int. Symposium on Rock Fragmentation.
    - Ouchterlony, F. (2005). The Swebrec function: linking fragmentation
      by blasting and crushing. Mining Technology, 114(1), 29-44.

Autor: Félix Fernando Bautista Layme — UNA Puno.
"""

import math
from typing import Dict, List, Tuple
from dataclasses import dataclass

from core.rock_mass import RockProperties


@dataclass
class FragmentationPredictor:
    """Predictor de granulometría mediante el modelo de Kuz-Ram.

    Attributes:
        rock_properties: Propiedades del macizo rocoso (RockProperties).
        rock_volume_m3: Volumen total de roca volada [m³].
        total_charge_kg: Masa total de explosivo [kg].
        burden_m: Burden del patrón [m].
        spacing_m: Espaciamiento del patrón [m].
        hole_diameter_mm: Diámetro del taladro [mm].
        charge_length_m: Longitud de columna explosiva media [m].
        bench_height_m: Altura del banco [m].
        drilling_deviation_m: Desviación estándar de perforación [m] (W).
        rws_explosive: Relative Weight Strength del explosivo (ANFO=100).
    """
    rock_properties: RockProperties
    rock_volume_m3: float
    total_charge_kg: float
    burden_m: float
    spacing_m: float
    hole_diameter_mm: float
    charge_length_m: float
    bench_height_m: float
    drilling_deviation_m: float = 0.2
    rws_explosive: float = 100.0

    @property
    def mean_particle_size_mm(self) -> float:
        """Calcula el tamaño medio de fragmento X_m [mm] (Cunningham 1987).

        Fórmula:
            X_m = A * (V / Q)^0.8 * Q^(1/6) * (115 / RWS)^(19/30)

        donde:
            A = Factor de roca
            V = Volumen de roca [m³]
            Q = Masa total de explosivo [kg]
            RWS = Relative Weight Strength del explosivo

        Returns:
            Tamaño medio de fragmento (P50) en milímetros.
        """
        if self.rock_volume_m3 <= 0 or self.total_charge_kg <= 0:
            return 0.0

        A = self.rock_properties.rock_factor_A
        V_Q = self.rock_volume_m3 / self.total_charge_kg
        Q_pow = math.pow(self.total_charge_kg, 1.0 / 6.0)
        E_factor = math.pow(115.0 / self.rws_explosive, 19.0 / 30.0)

        xm_cm = A * math.pow(V_Q, 0.8) * Q_pow * E_factor
        return xm_cm * 10.0  # Convertir de cm a mm

    @property
    def uniformity_index(self) -> float:
        """Calcula el Índice de Uniformidad (n) de Rosin-Rammler.

        Fórmula:
            n = (2.2 - 14*(B/D)) * sqrt((1 + S/B)/2) * (1 - W/B) * (L/H)

        donde:
            B = Burden [m]
            D = Diámetro taladro [mm]
            S = Espaciamiento [m]
            W = Desviación de perforación [m]
            L = Longitud de carga [m]
            H = Altura de banco [m]

        Returns:
            Índice de uniformidad adimensional (n). Generalmente 0.8 a 2.0.
        """
        if self.hole_diameter_mm <= 0 or self.burden_m <= 0 or self.bench_height_m <= 0:
            return 1.0

        term1 = 2.2 - 14.0 * (self.burden_m / self.hole_diameter_mm)
        term2 = math.sqrt((1.0 + (self.spacing_m / self.burden_m)) / 2.0)
        term3 = 1.0 - (self.drilling_deviation_m / self.burden_m)
        term4 = abs(self.charge_length_m / self.bench_height_m)

        n = term1 * term2 * term3 * term4
        # Limitar a valores físicamente razonables
        return max(0.5, min(n, 3.0))

    @property
    def characteristic_size_mm(self) -> float:
        """Calcula el tamaño característico X_c [mm].

        Relaciona el tamaño medio X_m con el índice de uniformidad n.
        X_c = X_m / ln(2)^(1/n)
        """
        xm = self.mean_particle_size_mm
        n = self.uniformity_index
        if n <= 0:
            return xm
        
        # ln(0.5) = -0.693147 -> X_m = X_c * (-ln(0.5))^(1/n) => X_c = X_m / ln(2)^(1/n)
        return xm / math.pow(math.log(2.0), 1.0 / n)

    def get_passing_percentage(self, size_mm: float) -> float:
        """Calcula el porcentaje de masa que pasa la malla de tamaño 'size_mm'.

        Ecuación de Rosin-Rammler:
            P(x) = 100 * (1 - exp(-(x / X_c)^n))

        Args:
            size_mm: Tamaño de la malla en milímetros.

        Returns:
            Porcentaje pasante [%] (0 - 100).
        """
        if size_mm <= 0:
            return 0.0

        xc = self.characteristic_size_mm
        n = self.uniformity_index

        if xc <= 0:
            return 0.0

        exp_term = math.exp(-math.pow(size_mm / xc, n))
        return 100.0 * (1.0 - exp_term)

    def get_p80(self) -> float:
        """Calcula el tamaño (en mm) por el cual pasa el 80% del material.

        Solución algebraica inversa de Rosin-Rammler:
            0.80 = 1 - exp(-(X_80 / X_c)^n)
            X_80 = X_c * (-ln(0.20))^(1/n)

        Returns:
            Tamaño de malla P80 [mm].
        """
        xc = self.characteristic_size_mm
        n = self.uniformity_index

        if n <= 0 or xc <= 0:
            return 0.0

        return xc * math.pow(-math.log(0.20), 1.0 / n)

    def get_p50(self) -> float:
        """Retorna el P50 (que debe ser idéntico al mean_particle_size_mm)."""
        return self.mean_particle_size_mm

    def generate_curve(self, max_size_mm: float = 1000.0, steps: int = 50) -> Tuple[List[float], List[float]]:
        """Genera la curva granulométrica completa.

        Returns:
            Tuple con dos listas: (tamaños_mm, porcentajes_pasantes_%).
        """
        sizes = [i * (max_size_mm / steps) for i in range(1, steps + 1)]
        passing = [self.get_passing_percentage(s) for s in sizes]
        return sizes, passing
