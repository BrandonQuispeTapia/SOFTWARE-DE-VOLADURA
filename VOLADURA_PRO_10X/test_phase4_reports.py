"""
test_phase4_reports.py
======================
Pruebas unitarias para el motor de reportabilidad y optimización Montecarlo.

Ejecutar con: pytest test_phase4_reports.py -v
"""

import pytest
import math
import base64
from pathlib import Path

from core.geometry import BlastPattern, Point3D, PatternType
from core.rock_mass import RockProperties
from optimization.cost_engine import CostEngine, CostParameters
from optimization.montecarlo import MineToMillOptimizer
from reports.charts_engine import HeadlessChartGenerator


def test_cost_engine_kpis():
    """Valida los cálculos financieros del CostEngine."""
    params = CostParameters(
        drilling_cost_per_m=20.0,
        explosive_cost_per_kg=1.5,
        detonator_cost_unit=5.0,
        surface_delay_cost_unit=3.0,
        booster_cost_unit=8.0
    )
    engine = CostEngine(params)
    
    # Patrón de prueba (2 taladros de 10m)
    pattern = BlastPattern("TEST", Point3D(0,0,0), 3.0, 4.0, 10.0, 0.0, 3.0, 1, 2)
    pattern.generate_grid(165.0)
    
    # Cargar explosivo a mano (aprox 100kg por taladro)
    for h in pattern.holes:
        h._explosive_decks.append({"charge_mass_kg": 100.0})
        
    kpis = engine.calculate_kpis(pattern, rock_density_tm3=2.6)
    
    # 20m totales * 20 $/m = 400
    assert kpis["drilling_cost_usd"] == 400.0
    
    # 200kg * 1.5 $/kg = 300
    assert kpis["explosives_cost_usd"] == 300.0
    
    # 2 det(10) + 2 boost(16) + 1 relay(3) = 29
    assert kpis["accessories_cost_usd"] == 29.0
    
    assert kpis["total_cost_usd"] == 729.0


def test_montecarlo_simulation():
    """Valida que el Montecarlo converja y retorne escenarios válidos."""
    rock = RockProperties("Granito", 2.7, 120.0, rock_factor_A=8.0)
    optimizer = MineToMillOptimizer(rock, CostParameters())
    
    # Simulación pequeña para testing rápido
    results = optimizer.run_simulation(
        base_burden=3.5, 
        base_spacing=4.0, 
        hole_diameter_mm=165.0, 
        bench_height=10.0,
        iterations=50
    )
    
    assert "best_scenario" in results
    assert "statistics" in results
    
    best = results["best_scenario"]
    assert "optimal_burden_m" in best
    assert "min_total_cost_usd_t" in best
    assert best["min_total_cost_usd_t"] > 0
    
    stats = results["statistics"]
    assert stats["max_total_cost"] >= stats["mean_total_cost"]


def test_headless_charts_base64():
    """Valida que el motor de gráficos renderiza PNG en Base64 sin fallar."""
    chart_engine = HeadlessChartGenerator()
    
    costs = {
        "drilling_cost_usd": 1000.0,
        "explosives_cost_usd": 500.0,
        "accessories_cost_usd": 100.0
    }
    
    pie_b64 = chart_engine.generate_kpi_pie_chart(costs)
    assert isinstance(pie_b64, str)
    assert len(pie_b64) > 100 # Debe contener data
    
    # Verificar que es Base64 decodificable
    try:
        base64.b64decode(pie_b64)
    except Exception as e:
        pytest.fail(f"Fallo decodificando Base64: {e}")
        
    sizes = [10, 50, 100, 200, 500]
    passing = [5, 20, 50, 80, 100]
    kuzram_b64 = chart_engine.generate_kuzram_curve(sizes, passing)
    assert isinstance(kuzram_b64, str)
    assert len(kuzram_b64) > 100
