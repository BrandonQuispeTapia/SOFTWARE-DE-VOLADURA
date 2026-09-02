"""
core/physics/ssoma_physics.py
=============================
Física de SSOMA (Seguridad, Salud Ocupacional y Medio Ambiente).
Modelo de proyección de rocas (Flyrock) según Richards & Moore.

Bibliografía:
    - Richards, A.B., & Moore, A.J. (2004). Flyrock control - by chance
      or design? ISEE Proceedings.

Autor: Félix Fernando Bautista Layme — UNA Puno.
"""

import math
from dataclasses import dataclass


@dataclass
class FlyrockPredictor:
    """Predictor de proyecciones de roca (Flyrock).

    Evalúa la distancia máxima de proyección por cráterización de taco
    y cara libre.

    Attributes:
        material_constant_k: Constante del sitio (k). Generalmente ~27.
        gravity_g: Constante gravitacional [m/s^2].
    """
    material_constant_k: float = 27.0
    gravity_g: float = 9.81

    def calculate_max_throw_distance(
        self,
        linear_charge_mass_kg_m: float,
        effective_burden_m: float,
        stemming_m: float,
        hole_diameter_mm: float
    ) -> float:
        """Calcula la distancia máxima de proyección de roca L_max [m].

        Basado en el modelo de Richards & Moore adaptado:
            L_max = (k^2 / g) * (sqrt(m) / B_e)^2.6

        donde:
            k = Constante del material (27)
            g = Gravedad (9.81)
            m = Carga lineal (kg/m)
            B_e = Burden efectivo o distancia mínima de roca al explosivo (m).

        Aplica penalización si el taco es peligrosamente corto.

        Args:
            linear_charge_mass_kg_m: Masa de explosivo por metro [kg/m].
            effective_burden_m: Burden efectivo (m).
            stemming_m: Longitud del taco (retacado) [m].
            hole_diameter_mm: Diámetro del taladro [mm].

        Returns:
            Distancia máxima de proyección proyectada [m].
        """
        if effective_burden_m <= 0 or linear_charge_mass_kg_m <= 0:
            return 0.0

        # Termino principal del modelo de Richards & Moore
        term1 = (self.material_constant_k ** 2) / self.gravity_g
        term2 = math.pow(math.sqrt(linear_charge_mass_kg_m) / effective_burden_m, 2.6)
        
        l_max = term1 * term2

        # Penalizador por "Riesgo Severo de Craterización"
        # Si el taco es menor a 20 veces el diámetro del taladro
        safe_stemming_limit_m = 20.0 * (hole_diameter_mm / 1000.0)
        
        if stemming_m < safe_stemming_limit_m:
            l_max *= 1.5

        return l_max
