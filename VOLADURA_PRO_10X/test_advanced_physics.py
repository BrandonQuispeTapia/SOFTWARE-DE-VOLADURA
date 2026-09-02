"""
test_advanced_physics.py
========================
Validación matemática del motor físico avanzado de VOLADURA_PRO_10X.
Compara termodinámica acoplada vs desacoplada y solapamientos.

Autor: Félix Fernando Bautista Layme — UNA Puno.
"""

import sys
import math
sys.path.insert(0, ".")

from core.physics.contour_blasting import ContourBlastOptimizer
from core.timing_advanced import StochasticTimingModel
from core.physics.vibration_near_field import NearFieldVibration
from core.explosives_energy import EnergyPartitionModel

def test_contour_blasting_pressure_drop():
    """Valida que la presión Pb de un taladro desacoplado cae drásticamente comparado con uno acoplado."""
    opt = ContourBlastOptimizer()
    
    # ANFO: Densidad 850 kg/m3, VOD 4500 m/s
    rho_e = 850.0
    vod = 4500.0
    
    # Taladro Acoplado (fc = 1.0)
    # Diámetro de carga == Diámetro de barreno (ej. 165mm)
    pb_coupled = opt.calculate_borehole_pressure(
        explosive_density_kg_m3=rho_e,
        vod_m_s=vod,
        charge_length_pct=1.0,
        charge_diameter_mm=165.0,
        hole_diameter_mm=165.0,
        is_wet=False
    )
    
    # Taladro Desacoplado (ej. tubo de Emulsión de 32mm en barreno de 165mm)
    pb_decoupled = opt.calculate_borehole_pressure(
        explosive_density_kg_m3=rho_e,
        vod_m_s=vod,
        charge_length_pct=1.0,
        charge_diameter_mm=32.0,
        hole_diameter_mm=165.0,
        is_wet=False
    )
    
    print(f"\nPresión Acoplada: {pb_coupled / 1e6:.2f} MPa")
    print(f"Presión Desacoplada: {pb_decoupled / 1e6:.2f} MPa")
    
    # La presión desacoplada debe ser significativamente menor
    assert pb_decoupled < (pb_coupled * 0.1), "La presión desacoplada debería caer drásticamente."
    
    # Verificar condición de fractura para roca típica (Tracción 10MPa, Compresión 150MPa)
    is_clean_fracture = opt.verify_fracture_condition(
        borehole_pressure_pa=pb_decoupled,
        tensile_strength_pa=10e6,
        compressive_strength_pa=150e6
    )
    print(f"¿Fractura limpia con carga de 32mm?: {is_clean_fracture}")
    assert is_clean_fracture is True, "La carga de 32mm debería causar fractura limpia en esta roca."

def test_stochastic_timing_overlap():
    """Valida la probabilidad de detonación fuera de secuencia."""
    model = StochasticTimingModel()
    
    # Dos taladros separados por un nominal de 17ms, mínimo requerido 8ms
    mu_1 = 100.0
    mu_2 = 117.0
    
    # Dispersión Nonel típica (~3%)
    sigma_1 = 3.0
    sigma_2 = 3.51
    
    p_osd = model.calculate_out_of_sequence_probability(mu_1, sigma_1, mu_2, sigma_2, t_min_ms=8.0)
    print(f"\nProbabilidad de solapamiento (Nonel): {p_osd*100:.2f}%")
    
    # Detonador electrónico (dispersión ~0.01%)
    sigma_1_e = 0.01
    sigma_2_e = 0.011
    
    p_osd_e = model.calculate_out_of_sequence_probability(mu_1, sigma_1_e, mu_2, sigma_2_e, t_min_ms=8.0)
    print(f"Probabilidad de solapamiento (Electrónico): {p_osd_e*100:.6f}%")
    
    assert p_osd > p_osd_e, "Los detonadores pirotécnicos deberían tener mucho más riesgo que los electrónicos."

if __name__ == "__main__":
    test_contour_blasting_pressure_drop()
    test_stochastic_timing_overlap()
    print("\n[OK] Todas las pruebas de física avanzada pasaron correctamente.")
