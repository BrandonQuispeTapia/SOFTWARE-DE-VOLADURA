"""
core/timing_advanced.py
=======================
Análisis Estocástico de Secuenciación y Probabilidad de Solapamiento.
Evaluación probabilística de interferencia de tiempos.

Autor: Félix Fernando Bautista Layme — UNA Puno.
"""

import math
from dataclasses import dataclass
from scipy.stats import norm

@dataclass
class StochasticTimingModel:
    """Modelo estocástico de secuenciación temporal de detonadores."""
    
    def calculate_out_of_sequence_probability(
        self,
        mu_n: float,
        sigma_n: float,
        mu_n_plus_1: float,
        sigma_n_plus_1: float,
        t_min_ms: float = 8.0
    ) -> float:
        """Calcula la probabilidad de solapamiento estocástico (Out of Sequence Detonation).
        
        P_osd = 1 - Phi( (mu_{n+1} - mu_n - t_min) / sqrt(sigma_{n+1}^2 + sigma_n^2) )
        
        Args:
            mu_n: Tiempo nominal medio del taladro n (ms).
            sigma_n: Desviación estándar del tiempo del taladro n (ms).
            mu_n_plus_1: Tiempo nominal medio del taladro n+1 (ms).
            sigma_n_plus_1: Desviación estándar del tiempo del taladro n+1 (ms).
            t_min_ms: Tiempo mínimo de separación requerido para evitar 
                      interferencia constructiva de vibraciones (ej. 8ms).
                      
        Returns:
            Probabilidad (0.0 a 1.0) de que el tiempo entre disparos sea menor a t_min_ms
            o que detonen en orden inverso.
        """
        # Diferencia de medias
        delta_mu = mu_n_plus_1 - mu_n
        
        # Varianza combinada (suma de varianzas para variables independientes)
        combined_sigma = math.sqrt(sigma_n**2 + sigma_n_plus_1**2)
        
        if combined_sigma == 0.0:
            # Determinístico puro
            return 0.0 if (delta_mu >= t_min_ms) else 1.0
            
        # Z-score para la condición (delta_t < t_min)
        z_score = (delta_mu - t_min_ms) / combined_sigma
        
        # P_osd = 1 - CDF(Z)
        p_osd = 1.0 - norm.cdf(z_score)
        
        return p_osd

    def check_overlap_risk(
        self,
        mu_n: float,
        sigma_n: float,
        mu_n_plus_1: float,
        sigma_n_plus_1: float,
        t_min_ms: float = 8.0,
        risk_threshold: float = 0.01
    ) -> bool:
        """Verifica si la probabilidad de solapamiento supera el umbral de riesgo (Ej: 1%).
        
        Returns:
            True si hay riesgo inaceptable de vibración constructiva o tiros cortados.
        """
        p_osd = self.calculate_out_of_sequence_probability(
            mu_n, sigma_n, mu_n_plus_1, sigma_n_plus_1, t_min_ms
        )
        return p_osd > risk_threshold
