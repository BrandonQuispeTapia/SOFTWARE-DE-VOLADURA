"""
core/physics/contour_blasting.py
================================
Módulo de Precorte y Recorte (Contour Blasting).
Cálculo analítico de presión en barreno para cargas desacopladas.

Autor: Félix Fernando Bautista Layme — UNA Puno.
"""

import math
from dataclasses import dataclass

@dataclass
class ContourBlastOptimizer:
    """Optimizador analítico para voladura de contorno.
    
    Abandona reglas empíricas y calcula la termodinámica de cargas desacopladas.
    """
    
    def calculate_borehole_pressure(
        self,
        explosive_density_kg_m3: float,
        vod_m_s: float,
        charge_length_pct: float,
        charge_diameter_mm: float,
        hole_diameter_mm: float,
        is_wet: bool = False
    ) -> float:
        r"""Calcula la presión de barreno generada por una carga desacoplada.
        
        P_b = (rho_e * VOD^2 / 8) * (C^0.5 * phi_e / phi_b)^gamma
        donde gamma = 1.8 si el barreno tiene agua, 2.4 si está seco.
        
        Args:
            explosive_density_kg_m3: Densidad del explosivo en kg/m^3 (\rho_e).
            vod_m_s: Velocidad de detonación en m/s (VOD).
            charge_length_pct: Porcentaje de longitud de columna cargada (C), ej. 0.8 para 80%.
            charge_diameter_mm: Diámetro de la carga explosiva (\phi_e).
            hole_diameter_mm: Diámetro del barreno (\phi_b).
            is_wet: True si el barreno contiene agua (fluido incompresible).
            
        Returns:
            Presión de barreno en Pascales (Pa).
        """
        if hole_diameter_mm <= 0 or charge_diameter_mm > hole_diameter_mm:
            raise ValueError("Diámetros inválidos para carga desacoplada.")
            
        # P_cj = Presión Chapman-Jouguet en Pa
        p_cj = (explosive_density_kg_m3 * (vod_m_s ** 2)) / 8.0
        
        # Relación de desacople volumétrico modificado
        decoupling_ratio = math.sqrt(charge_length_pct) * (charge_diameter_mm / hole_diameter_mm)
        
        # Exponente termodinámico (expansión adiabática)
        gamma = 1.8 if is_wet else 2.4
        
        # Presión en la pared del barreno
        p_b = p_cj * (decoupling_ratio ** gamma)
        return p_b

    def verify_fracture_condition(
        self,
        borehole_pressure_pa: float,
        tensile_strength_pa: float,
        compressive_strength_pa: float
    ) -> bool:
        """Verifica la condición de fractura limpia para voladura de contorno.
        
        Condición ideal: sigma_t < P_b < sigma_c
        La presión debe superar la resistencia a la tracción (para generar la grieta)
        pero ser menor a la resistencia a la compresión (para no triturar/dañar la pared).
        
        Args:
            borehole_pressure_pa: Presión en el barreno (Pa).
            tensile_strength_pa: Resistencia a la tracción de la roca (Pa).
            compressive_strength_pa: Resistencia a la compresión simple de la roca (Pa).
            
        Returns:
            True si se cumple la condición de fractura limpia, False caso contrario.
        """
        return tensile_strength_pa < borehole_pressure_pa < compressive_strength_pa
