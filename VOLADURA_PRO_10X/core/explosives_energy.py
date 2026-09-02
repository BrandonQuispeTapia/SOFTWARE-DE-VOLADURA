"""
core/explosives_energy.py
=========================
Partición Termodinámica de Energía Explosiva (Shock vs Gas).
Ajuste de partición basado en rigidez estructural (H/B).

Autor: Félix Fernando Bautista Layme — UNA Puno.
"""

from dataclasses import dataclass
from typing import Tuple

@dataclass
class EnergyPartitionModel:
    """Modelo de partición de energía de choque y gas para explosivos."""
    
    def calculate_energy_partition(
        self,
        base_shock_pct: float,
        bench_height_m: float,
        burden_m: float
    ) -> Tuple[float, float]:
        """Asigna pesos relativos a la energía de choque y energía de gas (Heave).
        
        Penaliza la energía de gas si el banco es demasiado rígido (sobreconfinado).
        
        Args:
            base_shock_pct: Porcentaje base de energía de choque del explosivo (ej. 0.15 para ANFO).
                            El resto es energía de gas base (1.0 - base_shock_pct).
            bench_height_m: Altura del banco (H) en metros.
            burden_m: Burden de diseño (B) en metros.
            
        Returns:
            Tupla con (Porcentaje final de Choque, Porcentaje final de Gas).
        """
        if burden_m <= 0:
            raise ValueError("El Burden debe ser mayor a 0.")
            
        base_gas_pct = 1.0 - base_shock_pct
        stiffness_ratio = bench_height_m / burden_m
        
        # Penalidad por sobreconfinamiento geométrico
        if stiffness_ratio < 2.0:
            # Banco muy rígido, la energía de gas se disipa como ruido/vibración 
            # en lugar de desplazar la roca útilmente.
            # Factor de penalidad lineal entre H/B = 1 y 2
            penalty_factor = (stiffness_ratio - 1.0) if stiffness_ratio > 1.0 else 0.0
            
            # Reduce la eficiencia de la energía de gas
            actual_gas_pct = base_gas_pct * (0.5 + 0.5 * penalty_factor)
            
            # La energía no aprovechada se considera pérdida
            actual_shock_pct = base_shock_pct
        else:
            actual_shock_pct = base_shock_pct
            actual_gas_pct = base_gas_pct
            
        # Normalizar para que la suma efectiva represente el uso útil total
        total_useful = actual_shock_pct + actual_gas_pct
        
        return (actual_shock_pct / total_useful, actual_gas_pct / total_useful)
