"""
core/physics/vibration_near_field.py
====================================
Vibraciones y Daño Estructural en campo cercano (Near Field).
Implementa el modelo integral de Holmberg-Persson.

Autor: Félix Fernando Bautista Layme — UNA Puno.
"""

import math
import numpy as np
from scipy.integrate import quad
from dataclasses import dataclass

@dataclass
class NearFieldVibration:
    """Calcula vibraciones en campo cercano para control de daño al macizo."""
    
    def calculate_impedance_attenuation(
        self,
        rock_density_kg_m3: float,
        p_wave_velocity_m_s: float,
        base_attenuation_factor: float = 1.0
    ) -> float:
        """Ajusta el factor de atenuación según la impedancia acústica de la roca.
        
        Z = rho_roca * V_p
        
        Args:
            rock_density_kg_m3: Densidad de la roca (kg/m^3).
            p_wave_velocity_m_s: Velocidad de onda P en el macizo (m/s).
            base_attenuation_factor: Factor alfa base empírico.
            
        Returns:
            Factor de atenuación alfa ajustado.
        """
        impedance = rock_density_kg_m3 * p_wave_velocity_m_s
        # Ejemplo heurístico: Rocas de alta impedancia atenúan menos la onda
        # Se normaliza respecto a un granito estándar (Z ~ 1.5e7 kg/m^2s)
        impedance_ratio = impedance / 1.5e7
        return base_attenuation_factor / math.sqrt(impedance_ratio)

    def calculate_ppv_holmberg_persson(
        self,
        k_factor: float,
        alpha: float,
        beta: float,
        charge_length_m: float,
        r0_m: float,
        x0_m: float
    ) -> float:
        """Calcula la Velocidad Pico de Partícula (PPV) integrando la carga.
        
        PPV = K * [ integral_0^L dx / (r0^2 + (x - x0)^2)^(beta/2alpha) ]^alpha
        
        Args:
            k_factor: Constante de transmisión de sitio (K).
            alpha: Constante de atenuación de sitio (alpha).
            beta: Constante de exponente espacial (beta).
            charge_length_m: Longitud de la carga cilíndrica (L).
            r0_m: Distancia perpendicular desde la carga al punto de interés.
            x0_m: Posición longitudinal del punto de interés respecto a la base de la carga.
            
        Returns:
            Velocidad Pico de Partícula (PPV) en mm/s.
        """
        # Exponente dentro de la integral
        exponent = beta / (2.0 * alpha)
        
        # Función a integrar
        def integrand(x):
            return 1.0 / ((r0_m**2 + (x - x0_m)**2) ** exponent)
            
        # Resolver integral definida desde 0 hasta L
        integral_val, _ = quad(integrand, 0.0, charge_length_m)
        
        # Calcular PPV final
        ppv = k_factor * (integral_val ** alpha)
        return ppv
        
    def get_critical_damage_radius(
        self,
        k_factor: float,
        alpha: float,
        beta: float,
        charge_length_m: float,
        critical_ppv_mm_s: float,
        x0_m: float = 0.0,
        max_search_radius_m: float = 50.0
    ) -> float:
        """Determina el radio crítico donde la PPV supera la velocidad crítica de tracción.
        
        Utiliza búsqueda binaria para encontrar el r0 donde PPV(r0) == PPV_crit.
        """
        low = 0.1
        high = max_search_radius_m
        tolerance = 0.01
        
        # Si a distancia mínima no hay daño, retornar 0
        if self.calculate_ppv_holmberg_persson(k_factor, alpha, beta, charge_length_m, low, x0_m) < critical_ppv_mm_s:
            return 0.0
            
        while (high - low) > tolerance:
            mid = (low + high) / 2.0
            ppv_mid = self.calculate_ppv_holmberg_persson(k_factor, alpha, beta, charge_length_m, mid, x0_m)
            
            if ppv_mid > critical_ppv_mm_s:
                # Daño, buscar más lejos
                low = mid
            else:
                # Seguro, buscar más cerca
                high = mid
                
        return (low + high) / 2.0
