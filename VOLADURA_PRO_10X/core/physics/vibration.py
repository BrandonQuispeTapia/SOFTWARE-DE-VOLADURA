"""
core/physics/vibration.py
=========================
Modelo físico de propagación de vibraciones (PPV) para VOLADURA_PRO_10X.

Aplica la regla empírica de agrupamiento cooperativo (ventana de 8ms)
y el modelo de atenuación de Holmberg-Persson / Distancia Escalar.

Bibliografía:
    - Holmberg, R., & Persson, P.A. (1979). Design of tunnel perimeter
      blasthole patterns to prevent rock damage. IMM.
    - ISEE Blasters' Handbook (2011), Chapter 29: Vibrations and Airblast.

Autor: Félix Fernando Bautista Layme — UNA Puno.
"""

import math
from typing import Dict, List, Optional
from dataclasses import dataclass

from core.geometry import Point3D
from core.timing_engine import FiringResult


@dataclass
class VibrationModel:
    """Modelo de predicción de Peak Particle Velocity (PPV).

    Attributes:
        k_factor: Constante de atenuación específica del sitio (intercepto).
                  Valores típicos: 50 a 500.
        b_factor: Constante de atenuación (pendiente).
                  Valores típicos: 1.2 a 2.0.
    """
    k_factor: float = 160.0
    b_factor: float = 1.6

    def get_max_cooperative_charge(self, timing_results: List[FiringResult], window_ms: float = 8.0) -> float:
        """Calcula la carga máxima operante dentro de cualquier ventana de N milisegundos.

        La regla de los 8ms establece que todas las cargas que detonan en un intervalo
        menor o igual a 8ms cooperan para generar la vibración máxima.

        Args:
            timing_results: Lista de resultados de detonación.
            window_ms: Ancho de la ventana temporal (default 8.0 ms).

        Returns:
            Carga máxima cooperante Q_max [kg].
        """
        if not timing_results:
            return 0.0

        # Ordenar los eventos por tiempo real de detonación
        sorted_events = sorted(timing_results, key=lambda r: r.actual_time_ms)
        max_charge = 0.0
        n = len(sorted_events)

        # Evaluar ventanas deslizantes
        for i in range(n):
            current_window_charge = 0.0
            t_start = sorted_events[i].actual_time_ms

            for j in range(i, n):
                if sorted_events[j].actual_time_ms - t_start <= window_ms:
                    current_window_charge += sorted_events[j].charge_kg
                else:
                    break

            if current_window_charge > max_charge:
                max_charge = current_window_charge

        return max_charge

    def calculate_ppv(self, distance_m: float, max_charge_kg: float) -> float:
        """Calcula el PPV (Peak Particle Velocity) usando Holmberg-Persson.

        Fórmula (Scaled Distance):
            PPV = K * (D / sqrt(Q)) ^ (-B)

        Args:
            distance_m: Distancia espacial 3D desde la carga al punto de interés [m].
            max_charge_kg: Carga máxima cooperante por retardo (8ms) [kg].

        Returns:
            PPV estimado [mm/s]. Retorna 0.0 si la distancia es cero o negativa.
        """
        if distance_m <= 0 or max_charge_kg <= 0:
            return 0.0

        scaled_distance = distance_m / math.sqrt(max_charge_kg)
        
        # Holmberg-Persson
        ppv = self.k_factor * math.pow(scaled_distance, -self.b_factor)
        return ppv

    def calculate_safe_distance(self, ppv_limit_mms: float, max_charge_kg: float) -> float:
        """Determina la distancia mínima segura para no exceder un límite de PPV.

        Despeje algebraico de Holmberg-Persson:
            D = sqrt(Q) * (PPV / K) ^ (-1/B)

        Args:
            ppv_limit_mms: Límite de vibración normativo [mm/s] (ej. D.S. N° 024-2016-EM).
            max_charge_kg: Carga máxima cooperante [kg].

        Returns:
            Distancia de seguridad requerida [m].
        """
        if ppv_limit_mms <= 0 or max_charge_kg <= 0:
            return 0.0

        term = math.pow(ppv_limit_mms / self.k_factor, -1.0 / self.b_factor)
        distance = math.sqrt(max_charge_kg) * term
        return distance
