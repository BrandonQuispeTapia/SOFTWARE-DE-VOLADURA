"""
test_phase2_physics.py
======================
Pruebas unitarias para el motor físico de la Fase 2 (VOLADURA_PRO_10X).
Valida matemáticamente la regla de los 8ms y el cálculo de fragmentación Kuz-Ram.

Ejecutar con: pytest test_phase2_physics.py
"""

import math
import pytest

from core.geometry import Point3D, Vector3D
from core.rock_mass import RockProperties
from core.timing_engine import FiringResult
from core.physics.fragmentation import FragmentationPredictor
from core.physics.vibration import VibrationModel
from core.physics.ssoma_physics import FlyrockPredictor
from core.ore_control import HeaveModel


def test_vibration_8ms_rule():
    """Valida el cálculo de carga máxima cooperante en ventana de 8ms."""
    model = VibrationModel()
    
    # Secuencia de detonación (tiempos en ms, carga en kg)
    results = [
        FiringResult("H1", 0, 0.0, 50.0, Point3D(0,0,0)),     # t=0, q=50
        FiringResult("H2", 0, 3.0, 50.0, Point3D(0,0,0)),     # t=3, q=50 -> Suma=100
        FiringResult("H3", 0, 7.0, 50.0, Point3D(0,0,0)),     # t=7, q=50 -> Suma=150 (ventana [0,8])
        FiringResult("H4", 0, 9.0, 50.0, Point3D(0,0,0)),     # t=9, q=50 -> Fuera de [0,8]. Nueva ventana [3,11] suma 150
        FiringResult("H5", 0, 100.0, 200.0, Point3D(0,0,0)),  # t=100, q=200 -> Suma=200
        FiringResult("H6", 0, 105.0, 200.0, Point3D(0,0,0)),  # t=105, q=200 -> Suma=400 (ventana [100,108])
    ]
    
    # La carga máxima debería ser la de la ventana [100, 105] => 200 + 200 = 400 kg
    max_charge = model.get_max_cooperative_charge(results, window_ms=8.0)
    assert max_charge == 400.0


def test_vibration_scaled_distance():
    """Valida el cálculo PPV con Holmberg-Persson."""
    model = VibrationModel(k_factor=160.0, b_factor=1.6)
    distance = 300.0  # metros
    max_charge = 400.0 # kg
    
    # D = 300, Q = 400 => SD = 300 / sqrt(400) = 300 / 20 = 15
    # PPV = 160 * (15)^(-1.6)
    expected_ppv = 160.0 * math.pow(15.0, -1.6)
    
    ppv = model.calculate_ppv(distance_m=distance, max_charge_kg=max_charge)
    assert math.isclose(ppv, expected_ppv, rel_tol=1e-5)


def test_fragmentation_mean_size():
    """Valida la fórmula de Cunningham (1987) para el tamaño medio X_m."""
    rock = RockProperties(
        name="TestRock", density_tm3=2.6, ucs_mpa=100.0, rock_factor_A=8.0
    )
    
    # Valores de prueba
    A = 8.0
    V = 1000.0 # m3
    Q = 800.0  # kg
    RWS = 115.0
    
    predictor = FragmentationPredictor(
        rock_properties=rock,
        rock_volume_m3=V,
        total_charge_kg=Q,
        burden_m=3.0,
        spacing_m=4.0,
        hole_diameter_mm=165.0,
        charge_length_m=10.0,
        bench_height_m=10.0,
        rws_explosive=RWS
    )
    
    # Cálculo manual
    V_Q = V / Q  # 1.25
    Q_pow = math.pow(Q, 1/6)
    E_factor = math.pow(115.0 / RWS, 19/30) # 1.0 ya que RWS=115
    
    expected_xm_cm = A * math.pow(V_Q, 0.8) * Q_pow * E_factor
    expected_xm_mm = expected_xm_cm * 10.0
    
    calculated_xm = predictor.mean_particle_size_mm
    assert math.isclose(calculated_xm, expected_xm_mm, rel_tol=1e-5)


def test_flyrock_richards_moore():
    """Valida el modelo de Flyrock de Richards & Moore."""
    predictor = FlyrockPredictor(material_constant_k=27.0, gravity_g=9.81)
    
    # Parámetros normales
    l_charge = 15.0 # kg/m
    burden_e = 3.5  # m
    stemming = 3.5  # m
    dia_mm = 165.0
    
    # L_max sin penalidad
    term1 = (27.0 ** 2) / 9.81
    term2 = math.pow(math.sqrt(15.0) / 3.5, 2.6)
    expected_l_max = term1 * term2
    
    calc_l_max = predictor.calculate_max_throw_distance(l_charge, burden_e, stemming, dia_mm)
    assert math.isclose(calc_l_max, expected_l_max, rel_tol=1e-5)
    
    # Con penalidad (taco crítico < 20 * dia)
    stemming_critical = 2.0 # < 20 * 0.165 (3.3m)
    calc_l_max_penalized = predictor.calculate_max_throw_distance(l_charge, burden_e, stemming_critical, dia_mm)
    assert math.isclose(calc_l_max_penalized, expected_l_max * 1.5, rel_tol=1e-5)


def test_heave_kinematics():
    """Valida el modelo cinemático de desplazamiento (Heave)."""
    model = HeaveModel(heave_proportionality_constant=2.5)
    
    centroid = Point3D(100.0, 200.0, 50.0)
    normal = Vector3D(1.0, 0.0, 0.0) # Apunta al Este puro
    pf = 0.8 # kg/m3
    
    displacement = model.calculate_mass_center_displacement(centroid, normal, pf)
    
    # dx = k * PF * normal.x = 2.5 * 0.8 * 1.0 = 2.0
    assert math.isclose(displacement.dx, 2.0, rel_tol=1e-5)
    assert math.isclose(displacement.dy, 0.0, rel_tol=1e-5)
    assert math.isclose(displacement.dz, 0.0, rel_tol=1e-5)
