"""
optimization/cost_engine.py
===========================
Motor Financiero de Perforación y Voladura (CostEngine).

Calcula los costos directos de perforación, explosivos y accesorios,
además de generar los KPIs económicos estandarizados ($/t, kg/t, m/m3).

Autor: Félix Fernando Bautista Layme — UNA Puno.
"""

from typing import Dict, Any
from dataclasses import dataclass

from core.geometry import BlastPattern


@dataclass
class CostParameters:
    """Parámetros unitarios de costo para la operación."""
    drilling_cost_per_m: float = 25.0      # $/m perforado
    explosive_cost_per_kg: float = 1.2     # $/kg de explosivo
    detonator_cost_unit: float = 5.0       # $/unidad (ej. detonador de fondo)
    surface_delay_cost_unit: float = 3.0   # $/unidad (ej. relé de superficie)
    booster_cost_unit: float = 8.0         # $/unidad


class CostEngine:
    """Motor de cálculo de costos directos y KPIs económicos."""
    
    def __init__(self, cost_params: CostParameters):
        self.params = cost_params

    def calculate_drilling_cost(self, pattern: BlastPattern) -> float:
        """Cálculo del costo total de perforación [$]."""
        total_length = sum(hole.length for hole in pattern.holes)
        return total_length * self.params.drilling_cost_per_m

    def calculate_explosives_cost(self, pattern: BlastPattern) -> float:
        """Cálculo del costo total de explosivos [$]."""
        return pattern.total_charge_kg * self.params.explosive_cost_per_kg

    def calculate_accessories_cost(self, pattern: BlastPattern) -> float:
        """Cálculo del costo total de accesorios (detonadores, boosters) [$].
        
        Por simplicidad, asume 1 detonador y 1 booster por taladro,
        y 1 relé de superficie por taladro (menos el último).
        """
        num_holes = pattern.total_holes
        if num_holes == 0:
            return 0.0
            
        cost_detonators = num_holes * self.params.detonator_cost_unit
        cost_boosters = num_holes * self.params.booster_cost_unit
        cost_relays = max(0, num_holes - 1) * self.params.surface_delay_cost_unit
        
        return cost_detonators + cost_boosters + cost_relays

    def calculate_kpis(self, pattern: BlastPattern, rock_density_tm3: float) -> Dict[str, Any]:
        """Calcula y consolida los KPIs técnicos y económicos.
        
        Args:
            pattern: El patrón de perforación evaluado.
            rock_density_tm3: Densidad de la roca en t/m³.
            
        Returns:
            Dict con los KPIs (Costos, Powder Factor, Drilling Factor).
        """
        total_drilling_cost = self.calculate_drilling_cost(pattern)
        total_explosives_cost = self.calculate_explosives_cost(pattern)
        total_accessories_cost = self.calculate_accessories_cost(pattern)
        
        total_cost_usd = total_drilling_cost + total_explosives_cost + total_accessories_cost
        
        volume_m3 = pattern.rock_volume_m3
        tonnage_t = volume_m3 * rock_density_tm3
        
        total_length_m = sum(hole.length for hole in pattern.holes)
        
        powder_factor_kg_m3 = pattern.powder_factor_kg_m3
        powder_factor_kg_t = (pattern.total_charge_kg / tonnage_t) if tonnage_t > 0 else 0.0
        drilling_factor_m_m3 = (total_length_m / volume_m3) if volume_m3 > 0 else 0.0
        
        cost_per_ton = (total_cost_usd / tonnage_t) if tonnage_t > 0 else 0.0
        cost_per_m3 = (total_cost_usd / volume_m3) if volume_m3 > 0 else 0.0

        return {
            "drilling_cost_usd": total_drilling_cost,
            "explosives_cost_usd": total_explosives_cost,
            "accessories_cost_usd": total_accessories_cost,
            "total_cost_usd": total_cost_usd,
            "cost_per_ton_usd": cost_per_ton,
            "cost_per_m3_usd": cost_per_m3,
            "powder_factor_kg_m3": powder_factor_kg_m3,
            "powder_factor_kg_t": powder_factor_kg_t,
            "drilling_factor_m_m3": drilling_factor_m_m3,
            "total_tonnage_t": tonnage_t,
            "total_volume_m3": volume_m3
        }
