"""
optimization/montecarlo.py
==========================
Simulador estocástico Mine-to-Mill (Montecarlo).

Minimiza el costo combinado (Voladura + Chancado/Molienda) mediante 
simulación estocástica de variables de diseño y parámetros del macizo.

Autor: Félix Fernando Bautista Layme — UNA Puno.
"""

import math
from typing import Dict, Any, Tuple
import numpy as np

from core.geometry import BlastPattern, Point3D, PatternType
from core.rock_mass import RockProperties
from optimization.cost_engine import CostEngine, CostParameters
from core.physics.fragmentation import FragmentationPredictor


class MineToMillOptimizer:
    """Optimizador estocástico del ciclo Mine-to-Mill.
    
    Evalúa el trade-off entre la energía química (explosivos) y la 
    energía mecánica (conminución) penalizando fragmentaciones gruesas.
    """
    
    def __init__(self, base_rock: RockProperties, base_cost_params: CostParameters):
        self.base_rock = base_rock
        self.cost_engine = CostEngine(base_cost_params)

    def crushing_milling_cost(self, p80_mm: float) -> float:
        """Función de penalidad empírica: Costo de conminución basado en P80.
        
        A mayor P80, el costo de chancado/molienda aumenta no linealmente.
        Basado vagamente en la Tercera Ley de Bond.
        
        Args:
            p80_mm: Tamaño P80 de la fragmentación [mm].
            
        Returns:
            Costo de conminución [$/ton].
        """
        # Función heurística (ejemplo): Costo Base + penalidad exponencial
        # Supongamos un P80 ideal de 300 mm. Si es mayor, el costo se dispara.
        base_cost = 2.50 # $/ton
        
        if p80_mm <= 0:
            return base_cost
            
        # Penalidad si P80 excede los 250 mm
        penalty = 0.0
        if p80_mm > 250.0:
            penalty = 0.005 * math.pow(p80_mm - 250.0, 1.5)
            
        return base_cost + penalty

    def evaluate_scenario(
        self,
        burden: float, 
        spacing: float, 
        hole_diameter_mm: float, 
        bench_height: float,
        ucs_mpa: float
    ) -> Tuple[float, float, float, Dict[str, Any]]:
        """Evalúa un único escenario determinístico.
        
        Returns:
            Tuple con (Cost_Total_USD/t, Cost_D&B_USD/t, P80_mm, KPIs_Dict).
        """
        # 1. Crear patrón temporal
        pattern = BlastPattern(
            pattern_id="SIM",
            origin=Point3D(0,0,0),
            burden=burden,
            spacing=spacing,
            bench_height=bench_height,
            subdrill=bench_height * 0.1,
            stemming=burden * 0.7,
            num_rows=4,
            holes_per_row=10,
            pattern_type=PatternType.STAGGERED
        )
        pattern.generate_grid(diameter_mm=hole_diameter_mm)
        
        # Simular carga (usando ANFO referencial)
        for h in pattern.holes:
            h.load_explosives({"name": "ANFO", "density_gcc": 0.85}, top_stemming=pattern.stemming)
            
        # 2. Modificar roca con el UCS estocástico
        sim_rock = RockProperties(
            name="SimRock",
            density_tm3=self.base_rock.density_tm3,
            ucs_mpa=ucs_mpa,
            rock_factor_A=self.base_rock.rock_factor_A
        )
        
        # 3. Calcular Costos D&B
        kpis = self.cost_engine.calculate_kpis(pattern, sim_rock.density_tm3)
        cost_db_per_ton = kpis["cost_per_ton_usd"]
        
        # 4. Calcular Fragmentación (P80)
        frag = FragmentationPredictor(
            rock_properties=sim_rock,
            rock_volume_m3=kpis["total_volume_m3"],
            total_charge_kg=pattern.total_charge_kg,
            burden_m=burden,
            spacing_m=spacing,
            hole_diameter_mm=hole_diameter_mm,
            charge_length_m=pattern.holes[0].charge_length if pattern.holes else 0,
            bench_height_m=bench_height,
            rws_explosive=100.0
        )
        p80 = frag.get_p80()
        
        # 5. Calcular Costo Conminución
        cost_crushing_per_ton = self.crushing_milling_cost(p80)
        
        total_cost_per_ton = cost_db_per_ton + cost_crushing_per_ton
        
        return total_cost_per_ton, cost_db_per_ton, p80, kpis

    def run_simulation(
        self,
        base_burden: float,
        base_spacing: float,
        hole_diameter_mm: float,
        bench_height: float,
        iterations: int = 1000
    ) -> Dict[str, Any]:
        """Ejecuta la simulación Montecarlo variando B, S y UCS.
        
        Args:
            base_burden: Burden central geométrico [m].
            base_spacing: Espaciamiento central geométrico [m].
            hole_diameter_mm: Diámetro del taladro [mm].
            bench_height: Altura de banco [m].
            iterations: Número de iteraciones (muestras).
            
        Returns:
            Diccionario con el mejor resultado y estadísticas de la simulación.
        """
        best_cost = float('inf')
        best_scenario = {}
        
        # Generar variables aleatorias vectorizadas para mayor eficiencia
        # Burden/Spacing variando ±15% uniforme
        b_array = np.random.uniform(base_burden * 0.85, base_burden * 1.15, iterations)
        s_array = np.random.uniform(base_spacing * 0.85, base_spacing * 1.15, iterations)
        
        # UCS variando con distribución Normal (±20% de CV aprox)
        std_ucs = self.base_rock.ucs_mpa * 0.20
        ucs_array = np.random.normal(self.base_rock.ucs_mpa, std_ucs, iterations)
        ucs_array = np.clip(ucs_array, 10.0, 300.0) # Acotar físicamente
        
        results_costs = []
        
        for i in range(iterations):
            b_sim = b_array[i]
            s_sim = s_array[i]
            ucs_sim = ucs_array[i]
            
            total_cost, db_cost, p80, kpis = self.evaluate_scenario(
                b_sim, s_sim, hole_diameter_mm, bench_height, ucs_sim
            )
            
            results_costs.append(total_cost)
            
            if total_cost < best_cost:
                best_cost = total_cost
                best_scenario = {
                    "iteration": i,
                    "optimal_burden_m": round(b_sim, 2),
                    "optimal_spacing_m": round(s_sim, 2),
                    "simulated_ucs_mpa": round(ucs_sim, 1),
                    "min_total_cost_usd_t": round(total_cost, 3),
                    "db_cost_usd_t": round(db_cost, 3),
                    "crushing_cost_usd_t": round(total_cost - db_cost, 3),
                    "predicted_p80_mm": round(p80, 1),
                    "powder_factor_kg_t": round(kpis["powder_factor_kg_t"], 3)
                }
                
        return {
            "best_scenario": best_scenario,
            "statistics": {
                "mean_total_cost": round(float(np.mean(results_costs)), 3),
                "std_total_cost": round(float(np.std(results_costs)), 3),
                "max_total_cost": round(float(np.max(results_costs)), 3),
            }
        }
