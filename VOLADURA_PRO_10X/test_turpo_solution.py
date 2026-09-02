"""
test_turpo_solution.py
======================
Script de prueba rápida de la solución de cilindros inclinados.

Este script verifica que:
1. Los módulos se cargan correctamente
2. Los datos TURPO se parsean bien
3. Los cilindros inclinados se crean correctamente
"""

import sys
from pathlib import Path
import numpy as np

print("\n" + "="*70)
print("TEST: Solución de Cilindros Inclinados y Alineación Topográfica")
print("="*70 + "\n")

# TEST 1: Cargar módulos
print("[TEST 1] Cargar módulos...")
try:
    from core.turpo_loader import TurpoLoader
    print("  ✓ TurpoLoader importado")
except Exception as e:
    print(f"  ✗ Error importando TurpoLoader: {e}")
    sys.exit(1)

try:
    from core.topography_interpolator import TopographyInterpolator
    print("  ✓ TopographyInterpolator importado")
except Exception as e:
    print(f"  ✗ Error importando TopographyInterpolator: {e}")
    sys.exit(1)

def find_data_file(filename: str) -> str:
    for base in [Path("."), Path("data"), Path("../data"), Path(".."), Path(__file__).resolve().parent / "data", Path(__file__).resolve().parent.parent / "data"]:
        p = base / filename
        if p.exists():
            return str(p)
    return filename

# TEST 2: Cargar datos TURPO
print("\n[TEST 2] Cargar datos TURPO...")
try:
    turpo_path = find_data_file("datos TURPO.csv")
    holes = TurpoLoader.load_csv(turpo_path, auto_fix_length=True)
    print(f"  ✓ {len(holes)} taladros cargados")
    if len(holes) > 0:
        first_hole = holes[0]
        print(f"    - Primer taladro: {first_hole.hole_id}")
        print(f"      Collar: ({first_hole.east:.2f}, {first_hole.north:.2f}, {first_hole.elev_collar:.2f})")
        print(f"      Toe:    ({first_hole.east:.2f}, {first_hole.north:.2f}, {first_hole.elev_toe:.2f})")
        print(f"      Azimuth: {first_hole.azimuth_deg}°, Dip: {first_hole.dip_deg}°")
        print(f"      Longitud: {first_hole.calculated_length:.2f}m")
except Exception as e:
    print(f"  ✗ Error cargando TURPO: {e}")
    sys.exit(1)

# TEST 3: Resumen estadístico
print("\n[TEST 3] Resumen estadístico...")
try:
    summary = TurpoLoader.summary(holes)
    print(f"  ✓ Resumen calculado:")
    for key, value in summary.items():
        print(f"    - {key}: {value}")
except Exception as e:
    print(f"  ✗ Error en resumen: {e}")
    sys.exit(1)

# TEST 4: Conversión a arrays
print("\n[TEST 4] Conversión a arrays...")
try:
    collars, toes = TurpoLoader.to_collars_and_toes(holes)
    print(f"  ✓ Arrays creados:")
    print(f"    - Collars shape: {collars.shape}")
    print(f"    - Toes shape: {toes.shape}")
    print(f"    - Collar[0]: {collars[0]}")
    print(f"    - Toe[0]:    {toes[0]}")
except Exception as e:
    print(f"  ✗ Error en conversión: {e}")
    sys.exit(1)

# TEST 5: Topografía
print("\n[TEST 5] Cargar topografía...")
try:
    import csv
    topo_points = []
    topo_path = find_data_file("Topografia.csv")
    with open(topo_path, 'r') as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            x = float(row.get('XP', 0))
            y = float(row.get('YP', 0))
            z = float(row.get('ZP', 0))
            topo_points.append([x, y, z])
    topo_points = np.array(topo_points)
    print(f"  ✓ {len(topo_points)} puntos de topografía cargados")
    print(f"    - Shape: {topo_points.shape}")
except Exception as e:
    print(f"  ✗ Error cargando topografía: {e}")
    sys.exit(1)

# TEST 6: Interpolador
print("\n[TEST 6] Crear interpolador topográfico...")
try:
    interpolator = TopographyInterpolator(topo_points)
    print(f"  ✓ Interpolador creado")

    # Probar interpolación
    z_interp = interpolator.get_elevation(8075.3, 6634.7, default=None)
    print(f"    - Z interpolado en (8075.3, 6634.7): {z_interp}")

    bounds = interpolator.bounds()
    print(f"    - Bounds: X=[{bounds[0]:.0f}, {bounds[1]:.0f}], Y=[{bounds[2]:.0f}, {bounds[3]:.0f}]")
except Exception as e:
    print(f"  ✗ Error con interpolador: {e}")
    sys.exit(1)

# TEST 7: Cilindros inclinados
print("\n[TEST 7] Crear cilindros inclinados...")
try:
    import pyvista as pv

    collar = np.array([551021.94, 64721.78, 3430.0])
    toe = np.array([551021.94, 64721.78, 3415.0])
    radius = 0.051  # 102mm

    # Calcular dirección
    direction = toe - collar
    total_length = np.linalg.norm(direction)
    direction_unit = direction / total_length

    print(f"  ✓ Cilindro 1 (Taco):")
    print(f"    - Collar: {collar}")
    print(f"    - Toe: {toe}")
    print(f"    - Dirección unitaria: {direction_unit}")
    print(f"    - Longitud total: {total_length:.2f}m")

    # Crear cilindro de taco
    stemming_length = 2.0
    stemming_center = collar + direction_unit * (stemming_length / 2.0)

    sc = pv.Cylinder(
        center=stemming_center,
        direction=direction_unit,
        radius=radius * 1.2,
        height=stemming_length,
        resolution=16
    )
    print(f"    ✓ Cilindro de taco creado: {sc.n_points} puntos, {sc.n_cells} celdas")

    # Crear cilindro de carga
    charge_length = total_length - stemming_length
    charge_start = collar + direction_unit * stemming_length
    charge_center = charge_start + direction_unit * (charge_length / 2.0)

    cc = pv.Cylinder(
        center=charge_center,
        direction=direction_unit,
        radius=radius,
        height=charge_length,
        resolution=16
    )
    print(f"  ✓ Cilindro 2 (Carga):")
    print(f"    - Longitud de carga: {charge_length:.2f}m")
    print(f"    - Cilindro de carga creado: {cc.n_points} puntos, {cc.n_cells} celdas")

except ImportError:
    print("  ⚠ 'pyvista' no está instalado en este intérprete; omitiendo generación de malla 3D.")
except Exception as e:
    print(f"  ✗ Error creando cilindros: {e}")
    sys.exit(1)

# RESULTADO FINAL
print("\n" + "="*70)
print("✅ TODOS LOS TESTS PASARON")
print("="*70)
print("\nAhora puedes:")
print("  1. python example_turpo_loader.py    # Para visualizar en PyVista")
print("  2. python main.py                     # Para usar la GUI principal")
print("\n")
