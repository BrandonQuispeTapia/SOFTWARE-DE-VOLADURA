"""
example_turpo_loader.py
=======================
Ejemplo de cómo cargar y visualizar datos TURPO.

Este script demuestra cómo:
1. Cargar datos TURPO desde CSV
2. Interpolar topografía
3. Renderizar cilindros inclinados verdaderos en PyVista

Uso:
    python example_turpo_loader.py

Requisitos:
    - Archivo: datos TURPO.csv (en la carpeta raíz)
    - Archivo: Topografia.csv (en la carpeta raíz)
"""

from pathlib import Path
import numpy as np
import pyvista as pv
from core.turpo_loader import TurpoLoader
from core.topography_interpolator import TopographyInterpolator


def find_data_file(filename: str) -> str:
    for base in [Path("."), Path("data"), Path("../data"), Path(".."), Path(__file__).resolve().parent / "data", Path(__file__).resolve().parent.parent / "data"]:
        p = base / filename
        if p.exists():
            return str(p)
    return filename


def load_topography_data(filepath: str) -> np.ndarray:
    """Carga puntos de topografía desde CSV.

    Formato esperado:
        PVALUE; PTN; XP; YP; ZP
    """
    import csv
    points = []
    try:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            first_line = f.readline()
            sep = ";" if ";" in first_line else ","
            f.seek(0)
            reader = csv.DictReader(f, delimiter=sep)
            for row in reader:
                x = float(row.get('XP', 0).strip())
                y = float(row.get('YP', 0).strip())
                z = float(row.get('ZP', 0).strip())
                points.append([x, y, z])
    except Exception as e:
        print(f"Error cargando topografía: {e}")
        return np.array([])

    return np.array(points)


def create_inclined_cylinder(collar, toe, radius, length_segment, start_depth=0.0, resolution=20):
    """Crea un cilindro inclinado."""
    direction = toe - collar
    total_length = np.linalg.norm(direction)
    if total_length < 1e-9:
        raise ValueError("Collar y toe no pueden ser iguales")

    direction_unit = direction / total_length
    segment_center = collar + direction_unit * (start_depth + length_segment / 2.0)

    cylinder = pv.Cylinder(
        center=segment_center,
        direction=direction_unit,
        radius=radius,
        height=length_segment,
        resolution=resolution
    )
    return cylinder


def main():
    """Función principal."""
    print("\n" + "="*70)
    print("EJEMPLO: Carga y Visualización de Datos TURPO")
    print("="*70 + "\n")

    # 1. Cargar datos TURPO
    print("[1/4] Cargando datos TURPO...")
    try:
        holes = TurpoLoader.load_csv(find_data_file("datos TURPO.csv"), auto_fix_length=True)
        print(f"     ✓ {len(holes)} taladros cargados")
    except Exception as e:
        print(f"     ✗ Error: {e}")
        return

    # 2. Mostrar resumen
    print("[2/4] Resumen de datos:")
    summary = TurpoLoader.summary(holes)
    for key, value in summary.items():
        print(f"     • {key}: {value}")

    # 3. Cargar topografía
    print("\n[3/4] Cargando topografía...")
    try:
        topo_points = load_topography_data(find_data_file("Topografia.csv"))
        print(f"     ✓ {len(topo_points)} puntos de topografía")
        interpolator = TopographyInterpolator(topo_points)
        print(f"     ✓ Interpolador de topografía creado")
    except Exception as e:
        print(f"     ✗ Error: {e}")
        return

    # 4. Visualizar en PyVista
    print("\n[4/4] Renderizando visualización 3D...")
    plotter = pv.Plotter(theme="dark")

    # Agregar topografía como malla
    if len(topo_points) >= 3:
        cloud = pv.PolyData(topo_points)
        try:
            surface = cloud.delaunay_2d(alpha=100)
            plotter.add_mesh(surface, color="#3D6B4F", opacity=0.3, name="topography")
        except:
            plotter.add_mesh(cloud, color="#3D6B4F", point_size=3, name="topography")

    # Renderizar taladros como cilindros inclinados
    stemming = 2.0
    diameter = 102.0
    vis_rad = max(diameter / 2000.0, 0.08)

    for hole in holes:
        collar = np.array([hole.east, hole.north, hole.elev_collar], dtype=np.float64)
        toe = np.array([hole.east, hole.north, hole.elev_toe], dtype=np.float64)
        hole_length = hole.calculated_length
        charge_len = hole_length - stemming

        # Taco (gris)
        if stemming > 0:
            try:
                sc = create_inclined_cylinder(collar, toe, vis_rad * 1.2, stemming, 0.0, resolution=16)
                plotter.add_mesh(sc, color="#64748B", opacity=0.8)
            except:
                pass

        # Carga (rojo)
        if charge_len > 0:
            try:
                cc = create_inclined_cylinder(collar, toe, vis_rad, charge_len, stemming, resolution=16)
                plotter.add_mesh(cc, color="#EF4444", opacity=0.9)
            except:
                pass

    # Etiquetas
    collar_positions = np.array([
        [h.east, h.north, h.elev_collar + 1.0] for h in holes[:20]  # Primeros 20 para no saturar
    ])
    plotter.add_point_labels(
        collar_positions,
        [h.hole_id for h in holes[:20]],
        font_size=8, text_color="#FBBF24", bold=True,
        point_size=0.5, shape_opacity=0
    )

    plotter.add_axes(
        color="white",
        x_color="#EF4444",
        y_color="#22C55E",
        z_color="#3B82F6"
    )

    print("     ✓ Visualización lista. Presiona cualquier tecla para cerrar.\n")
    plotter.show()


if __name__ == "__main__":
    main()
