import numpy as np
import pyvista as pv
import pandas as pd
from scipy.spatial import Voronoi, KDTree
from scipy.interpolate import griddata
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict


class ShotplusRaycaster:
    def __init__(self, num_rays_per_direction: int = 36):
        self.num_rays_per_direction = num_rays_per_direction
        self._CONFINE_THRESHOLD_M = 500.0

    def calcular_burden_real(self, hole_center: np.ndarray, hole_vector: np.ndarray, topografia_mesh: pv.PolyData) -> float:
        hole_center = np.asarray(hole_center, dtype=np.float64).ravel()
        hole_vector = np.asarray(hole_vector, dtype=np.float64).ravel()
        norm_hv = np.linalg.norm(hole_vector)
        if norm_hv < 1e-12:
            return float('inf')
        hole_vector = hole_vector / norm_hv

        t1, t2 = self._compute_perpendicular_base(hole_vector)
        angles = np.linspace(0.0, 2.0 * np.pi, self.num_rays_per_direction, endpoint=False)
        distances = []
        mesh_surface = topografia_mesh.extract_surface(algorithm='dataset_surface')

        for depth in np.linspace(0.0, 50.0, 51):
            origin = hole_center + hole_vector * depth
            for angle in angles:
                direction = t1 * np.cos(angle) + t2 * np.sin(angle)
                norm_d = np.linalg.norm(direction)
                if norm_d < 1e-12:
                    continue
                direction = direction / norm_d
                ray_end = origin + direction * self._CONFINE_THRESHOLD_M
                try:
                    _, ipoints = mesh_surface.ray_trace(origin, ray_end, first_point_only=False)
                    if ipoints is not None and len(ipoints) > 0:
                        diffs = ipoints - origin
                        dists = np.linalg.norm(diffs, axis=1)
                        min_dist = float(np.min(dists))
                        if min_dist > 1e-6:
                            distances.append(min_dist)
                except Exception:
                    continue

        if not distances:
            return float('inf')
        return float(np.min(distances))

    def calculate_true_burden(self, hole_center: np.ndarray, free_face_mesh: pv.PolyData, hole_axis: Optional[np.ndarray] = None) -> 'BurdenResult':
        hole_center = np.asarray(hole_center, dtype=np.float64)
        if hole_axis is None:
            hole_axis = np.array([0.0, 0.0, -1.0], dtype=np.float64)
        else:
            hole_axis = np.asarray(hole_axis, dtype=np.float64)
            norm = np.linalg.norm(hole_axis)
            if norm < 1e-12:
                raise ValueError("hole_axis cannot be zero vector")
            hole_axis = hole_axis / norm

        perpendicular_dir = self._compute_perpendicular_base(hole_axis)
        all_rays = []
        angles = np.linspace(0.0, 2.0 * np.pi, self.num_rays_per_direction, endpoint=False)
        for angle in angles:
            direction = perpendicular_dir[0] * np.cos(angle) + perpendicular_dir[1] * np.sin(angle)
            norm = np.linalg.norm(direction)
            if norm < 1e-12:
                continue
            direction = direction / norm
            all_rays.append(direction)

        distances, closest_points, directions_hit = [], [], []
        mesh_surface = free_face_mesh.extract_surface()
        for ray_dir in all_rays:
            ray_endpoint = hole_center + ray_dir * self._CONFINE_THRESHOLD_M
            try:
                _, ipoints = mesh_surface.ray_trace(hole_center, ray_endpoint, first_point_only=False)
                if ipoints is not None and len(ipoints) > 0:
                    diffs = ipoints - hole_center
                    dists = np.linalg.norm(diffs, axis=1)
                    min_idx = int(np.argmin(dists))
                    min_dist = float(dists[min_idx])
                    if min_dist > 1e-6:
                        distances.append(min_dist)
                        closest_points.append(ipoints[min_idx].copy())
                        directions_hit.append(ray_dir.copy())
            except Exception:
                continue

        num_rays = len(all_rays)
        num_hits = len(distances)
        if num_hits == 0:
            return BurdenResult(float('inf'), hole_center.copy(), hole_axis.copy(), True, num_rays, 0, np.array([]))

        dist_array = np.array(distances, dtype=np.float64)
        min_idx = int(np.argmin(dist_array))
        return BurdenResult(float(dist_array[min_idx]), closest_points[min_idx], directions_hit[min_idx],
                            float(dist_array[min_idx]) > self._CONFINE_THRESHOLD_M * 0.95, num_rays, num_hits, dist_array)

    def calculate_burden_grid(self, hole_centers: np.ndarray, free_face_mesh: pv.PolyData) -> np.ndarray:
        hole_centers = np.asarray(hole_centers, dtype=np.float64)
        burdens = np.full(hole_centers.shape[0], np.inf, dtype=np.float64)
        for i in range(hole_centers.shape[0]):
            burdens[i] = self.calculate_true_burden(hole_centers[i], free_face_mesh).true_burden_m
        return burdens

    def _compute_perpendicular_base(self, axis: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        v1 = np.array([1.0, 0.0, 0.0], dtype=np.float64)
        if abs(np.dot(axis, v1)) > 0.9:
            v1 = np.array([0.0, 1.0, 0.0], dtype=np.float64)
        t1 = np.cross(axis, v1)
        t1 /= np.linalg.norm(t1)
        t2 = np.cross(axis, t1)
        t2 /= np.linalg.norm(t2)
        return t1, t2


@dataclass
class BurdenResult:
    true_burden_m: float
    closest_point: np.ndarray
    direction: np.ndarray
    is_confined: bool
    num_rays_cast: int
    num_hits: int
    all_distances: np.ndarray


@dataclass
class LoadingSegment:
    zone_id: int
    rock_type: str
    explosive_type: str
    start_depth_m: float
    end_depth_m: float
    length_m: float
    diameter_m: float
    volume_m3: float
    mass_kg: float
    density_kgm3: float
    energy_mj: float


class DeswikAutoLoader:
    EXPLOSIVE_RULES = {
        "ore": {"type": "Emulsion Sensibilizada", "density_kgm3": 1200.0, "energy_mj_kg": 4.65, "rws": 115.0},
        "mineral": {"type": "Emulsion Sensibilizada", "density_kgm3": 1200.0, "energy_mj_kg": 4.65, "rws": 115.0},
        "waste": {"type": "ANFO Pesado (HA 46)", "density_kgm3": 1150.0, "energy_mj_kg": 3.87, "rws": 100.0},
        "esteril": {"type": "ANFO Pesado (HA 46)", "density_kgm3": 1150.0, "energy_mj_kg": 3.87, "rws": 100.0},
        "fault": {"type": "Emulsion Bombeable", "density_kgm3": 1100.0, "energy_mj_kg": 4.20, "rws": 108.0},
        "fault_zone": {"type": "Emulsion Bombeable", "density_kgm3": 1100.0, "energy_mj_kg": 4.20, "rws": 108.0},
        "soil": {"type": "ANFO Estandar", "density_kgm3": 900.0, "energy_mj_kg": 3.40, "rws": 85.0},
    }

    def __init__(self, hole_diameter_m: float = 0.102):
        self.hole_diameter_m = hole_diameter_m
        self.hole_radius_m = hole_diameter_m / 2.0
        self.hole_area_m2 = np.pi * self.hole_radius_m ** 2

    def cargar_taladro_por_estratos(self, hole_top: np.ndarray, hole_bottom: np.ndarray, block_model_df: pd.DataFrame) -> Dict[str, float]:
        hole_top = np.asarray(hole_top, dtype=np.float64).ravel()
        hole_bottom = np.asarray(hole_bottom, dtype=np.float64).ravel()
        if len(hole_top) < 3 or len(hole_bottom) < 3:
            return {"Taco_m": 3.0, "Emulsion_kg": 0.0, "ANFO_kg": 0.0}
        block_coords = block_model_df[["X", "Y", "Z"]].values if all(c in block_model_df.columns for c in ["X", "Y", "Z"]) else block_model_df.iloc[:, :3].values
        ucs_values = block_model_df["UCS"].values if "UCS" in block_model_df.columns else np.full(len(block_model_df), 80.0)
        tree = KDTree(block_coords)
        axis = hole_bottom - hole_top
        total_length = float(np.linalg.norm(axis))
        if total_length < 1e-12:
            return {"Taco_m": 3.0, "Emulsion_kg": 0.0, "ANFO_kg": 0.0}
        axis_unit = axis / total_length
        num_samples = max(10, int(total_length / 0.5))
        depths = np.linspace(0, total_length, num_samples)
        ucs_samples = []
        for depth in depths:
            pt = hole_top + axis_unit * depth
            dists, idxs = tree.query(pt.reshape(1, -1), k=3)
            weights = 1.0 / (dists[0] + 1e-12)
            weights /= np.sum(weights)
            ucs_interp = float(np.sum(weights * ucs_values[idxs[0]]))
            ucs_samples.append(ucs_interp)

        ucs_promedio = float(np.mean(ucs_samples))
        volumen = self.hole_area_m2 * total_length

        if ucs_promedio > 100.0:
            masa = volumen * 1200.0
            return {"Taco_m": 3.0, "Emulsion_kg": masa, "ANFO_kg": 0.0}
        else:
            masa = volumen * 1150.0
            return {"Taco_m": 3.0, "Emulsion_kg": 0.0, "ANFO_kg": masa}

    def apply_smart_loading_rules(self, drillhole_collar: np.ndarray, drillhole_toe: np.ndarray,
                                  block_model_voxels: pv.PolyData, rock_type_array: np.ndarray,
                                  stemming_length_m: float = 3.0, subdrill_m: float = 1.0) -> List[LoadingSegment]:
        collar = np.asarray(drillhole_collar, dtype=np.float64)
        toe = np.asarray(drillhole_toe, dtype=np.float64)
        drill_axis = toe - collar
        total_depth = float(np.linalg.norm(drill_axis))
        if total_depth < 1e-6:
            return []
        drill_axis_unit = drill_axis / total_depth
        effective_top = 0.0
        effective_bottom = total_depth - stemming_length_m
        if effective_bottom <= effective_top:
            return []
        num_slices = max(int(np.ceil(total_depth / 0.1)), 50)
        slice_depths = np.linspace(effective_top, effective_bottom, num_slices + 1)
        segments_raw = []
        current_type = "waste"
        seg_start = slice_depths[0]
        for i in range(len(slice_depths) - 1):
            depth_mid = (slice_depths[i] + slice_depths[i + 1]) / 2.0
            point_in_hole = collar + drill_axis_unit * depth_mid
            detected_type = self._detect_rock_type_at_point(point_in_hole, block_model_voxels, rock_type_array)
            if detected_type.lower() != current_type.lower():
                if depth_mid > seg_start + 0.05:
                    segments_raw.append((seg_start, depth_mid, current_type))
                current_type = detected_type
                seg_start = depth_mid
        segments_raw.append((seg_start, effective_bottom, current_type))
        merged = self._merge_adjacent_segments(segments_raw)
        segments = []
        for idx, (start, end, rock) in enumerate(merged):
            length = end - start
            volume = self.hole_area_m2 * length
            rules = self.EXPLOSIVE_RULES.get(rock.lower(), self.EXPLOSIVE_RULES["waste"])
            mass = volume * rules["density_kgm3"]
            energy = mass * rules["energy_mj_kg"]
            segments.append(LoadingSegment(zone_id=idx + 1, rock_type=rock, explosive_type=rules["type"],
                            start_depth_m=start, end_depth_m=end, length_m=length, diameter_m=self.hole_diameter_m,
                            volume_m3=volume, mass_kg=mass, density_kgm3=rules["density_kgm3"], energy_mj=energy))
        return segments

    def calculate_total_charge(self, segments: List[LoadingSegment]) -> Tuple[float, float]:
        total_mass = sum(s.mass_kg for s in segments)
        total_energy = sum(s.energy_mj for s in segments)
        return total_mass, total_energy

    def calculate_powder_factor(self, segments: List[LoadingSegment], volume_m3: float) -> float:
        if volume_m3 <= 0:
            return 0.0
        total_mass, _ = self.calculate_total_charge(segments)
        return total_mass / volume_m3

    def _detect_rock_type_at_point(self, point: np.ndarray, voxels: pv.PolyData, rock_types: np.ndarray) -> str:
        if voxels.n_points == 0:
            return "waste"
        pts = voxels.points
        diffs = pts - point
        dists = np.linalg.norm(diffs, axis=1)
        nearest_idx = int(np.argmin(dists))
        if voxels.n_cells > 0:
            closest_cells = voxels.find_closest_cell(point, return_closest_cell=True)
            if isinstance(closest_cells, tuple):
                cell_id = int(closest_cells[0])
            else:
                cell_id = int(closest_cells)
            if 0 <= cell_id < len(rock_types):
                return str(rock_types[cell_id])
        if nearest_idx < len(rock_types):
            return str(rock_types[nearest_idx])
        return "waste"

    def _merge_adjacent_segments(self, segments: List[Tuple[float, float, str]]) -> List[Tuple[float, float, str]]:
        if not segments:
            return []
        merged = [segments[0]]
        for start, end, rock in segments[1:]:
            prev_start, prev_end, prev_rock = merged[-1]
            if rock.lower() == prev_rock.lower():
                merged[-1] = (prev_start, end, prev_rock)
            else:
                merged.append((start, end, rock))
        return merged

    def build_loading_column(self, segments: List[LoadingSegment], stemming_length_m: float) -> pv.PolyData:
        meshes = []
        for seg in segments:
            start_pt = np.array([0.0, 0.0, -seg.start_depth_m])
            end_pt = np.array([0.0, 0.0, -seg.end_depth_m])
            cyl = pv.Cylinder(center=(start_pt + end_pt) / 2.0, direction=(0, 0, -1),
                              radius=self.hole_radius_m, height=seg.length_m, resolution=16)
            color = (0.0, 0.7, 1.0) if "emulsion" in seg.explosive_type.lower() else (1.0, 0.6, 0.0)
            cyl["color"] = np.tile(color, (cyl.n_points, 1))
            meshes.append(cyl)
        if stemming_length_m > 0:
            stem_top = segments[0].end_depth_m if segments else 0.0
            stem_center = np.array([0.0, 0.0, -(stem_top + stemming_length_m / 2.0)])
            stem = pv.Cylinder(center=stem_center, direction=(0, 0, -1), radius=self.hole_radius_m, height=stemming_length_m, resolution=16)
            stem["color"] = np.tile(np.array([0.5, 0.5, 0.5]), (stem.n_points, 1))
            meshes.append(stem)
        if meshes:
            combined = meshes[0]
            for m in meshes[1:]:
                combined = combined.merge(m)
            return combined
        return pv.PolyData()


@dataclass
class EnergyCell:
    hole_id: int
    polygon_vertices: np.ndarray
    area_m2: float
    powder_factor_kgm3: float
    energy_density_mj: float
    color_rgb: np.ndarray


class VoronoiEnergyMapper:
    def __init__(self, grid_resolution: int = 100):
        self.grid_resolution = grid_resolution
        self._energy_min = 0.0
        self._energy_max = 0.0

    def generar_heatmap(self, coordenadas_taladros: np.ndarray, factores_de_carga: np.ndarray) -> pv.PolyData:
        coords = np.asarray(coordenadas_taladros[:, :2], dtype=np.float64)
        pf = np.asarray(factores_de_carga, dtype=np.float64)
        n_points = coords.shape[0]
        if n_points < 3:
            return pv.PolyData()

        x_min, x_max = coords[:, 0].min() - 10, coords[:, 0].max() + 10
        y_min, y_max = coords[:, 1].min() - 10, coords[:, 1].max() + 10
        xi = np.linspace(x_min, x_max, self.grid_resolution)
        yi = np.linspace(y_min, y_max, self.grid_resolution)
        grid_x, grid_y = np.meshgrid(xi, yi)
        grid_z = griddata(coords, pf, (grid_x, grid_y), method="cubic", fill_value=0.0)
        grid_z = np.nan_to_num(grid_z, nan=0.0)

        points_3d = np.column_stack([grid_x.ravel(), grid_y.ravel(), np.full(grid_x.size, 0.0)])
        mesh = pv.PolyData(points_3d)
        mesh["powder_factor"] = grid_z.ravel()
        return mesh

    def generate_energy_heatmap(self, drillhole_coords: np.ndarray, powder_factors: np.ndarray, bench_elevation: float = 0.0) -> Tuple[pv.PolyData, List[EnergyCell]]:
        coords_2d = np.asarray(drillhole_coords[:, :2], dtype=np.float64)
        pf = np.asarray(powder_factors, dtype=np.float64)
        n_points = coords_2d.shape[0]
        if n_points < 3:
            return pv.PolyData(), []

        self._energy_min = float(np.min(pf))
        self._energy_max = float(np.max(pf))
        energy_range = self._energy_max - self._energy_min
        if energy_range < 1e-12:
            energy_range = 1.0

        vor = Voronoi(coords_2d)
        energy_cells = []
        all_polygons = []
        for idx in range(n_points):
            region_idx = vor.point_region[idx]
            region_vertices_idx = vor.regions[region_idx]
            if -1 in region_vertices_idx or len(region_vertices_idx) < 3:
                continue
            polygon_pts_2d = vor.vertices[region_vertices_idx]
            n_verts = polygon_pts_2d.shape[0]
            polygon_pts_3d = np.column_stack([polygon_pts_2d, np.full(n_verts, bench_elevation)])
            poly_area = self._compute_polygon_area_2d(polygon_pts_2d)
            pf_val = float(pf[idx])
            t = max(0.0, min(1.0, (pf_val - self._energy_min) / energy_range))
            color = self._energy_to_rgb(t)
            energy_cells.append(EnergyCell(hole_id=idx, polygon_vertices=polygon_pts_3d, area_m2=poly_area,
                                powder_factor_kgm3=pf_val, energy_density_mj=poly_area * bench_elevation * pf_val * 3.87, color_rgb=np.array(color)))
            faces = np.array([n_verts] + list(range(n_verts)) + [0], dtype=np.int64).reshape(1, -1)
            all_polygons.append(pv.PolyData(polygon_pts_3d, faces))

        if not all_polygons:
            return pv.PolyData(), []

        combined = all_polygons[0]
        for pm in all_polygons[1:]:
            combined = combined.merge(pm)

        grid_x, grid_y = np.meshgrid(
            np.linspace(coords_2d[:, 0].min() - 10, coords_2d[:, 0].max() + 10, self.grid_resolution),
            np.linspace(coords_2d[:, 1].min() - 10, coords_2d[:, 1].max() + 10, self.grid_resolution),
        )
        grid_z = griddata(coords_2d, pf, (grid_x, grid_y), method="cubic", fill_value=0.0)
        grid_points = np.column_stack([grid_x.ravel(), grid_y.ravel(), np.full(grid_x.size, bench_elevation)])
        grid_mesh = pv.PolyData(grid_points)
        grid_mesh["powder_factor"] = grid_z.ravel()
        return grid_mesh, energy_cells

    def generate_interpolated_surface(self, drillhole_coords: np.ndarray, powder_factors: np.ndarray, bench_elevation: float = 0.0) -> pv.PolyData:
        coords_2d = np.asarray(drillhole_coords[:, :2], dtype=np.float64)
        pf = np.asarray(powder_factors, dtype=np.float64)
        x_min, x_max = coords_2d[:, 0].min() - 5, coords_2d[:, 0].max() + 5
        y_min, y_max = coords_2d[:, 1].min() - 5, coords_2d[:, 1].max() + 5
        xi = np.linspace(x_min, x_max, self.grid_resolution)
        yi = np.linspace(y_min, y_max, self.grid_resolution)
        grid_x, grid_y = np.meshgrid(xi, yi)
        grid_z = griddata(coords_2d, pf, (grid_x, grid_y), method="cubic", fill_value=0.0)
        grid_z = np.nan_to_num(grid_z, nan=0.0)
        points_3d = np.column_stack([grid_x.ravel(), grid_y.ravel(), np.full(grid_x.size, bench_elevation)])
        mesh = pv.PolyData(points_3d)
        mesh["powder_factor"] = grid_z.ravel()
        return mesh

    def generate_voronoi_mesh(self, drillhole_coords: np.ndarray, powder_factors: np.ndarray, bench_elevation: float = 0.0) -> pv.PolyData:
        coords_2d = np.asarray(drillhole_coords[:, :2], dtype=np.float64)
        pf = np.asarray(powder_factors, dtype=np.float64)
        n_points = coords_2d.shape[0]
        if n_points < 3:
            return pv.PolyData()
        vor = Voronoi(coords_2d)
        all_meshes = []
        energy_range = float(np.max(pf) - np.min(pf))
        if energy_range < 1e-12:
            energy_range = 1.0
        for idx in range(n_points):
            region_idx = vor.point_region[idx]
            region_verts = vor.regions[region_idx]
            if -1 in region_verts or len(region_verts) < 3:
                continue
            verts_2d = vor.vertices[region_verts]
            n_v = verts_2d.shape[0]
            verts_3d = np.column_stack([verts_2d, np.full(n_v, bench_elevation)])
            face = np.array([n_v] + list(range(n_v)) + [0], dtype=np.int64).reshape(1, -1)
            cell_mesh = pv.PolyData(verts_3d, face)
            t = max(0.0, min(1.0, (pf[idx] - float(np.min(pf))) / energy_range))
            color = self._energy_to_rgb(t)
            cell_mesh["energy_rgb"] = np.tile(color, (cell_mesh.n_points, 1))
            cell_mesh["powder_factor"] = np.full(cell_mesh.n_points, pf[idx])
            all_meshes.append(cell_mesh)
        if not all_meshes:
            return pv.PolyData()
        combined = all_meshes[0]
        for m in all_meshes[1:]:
            combined = combined.merge(m)
        return combined

    def _compute_polygon_area_2d(self, vertices_2d: np.ndarray) -> float:
        n = vertices_2d.shape[0]
        if n < 3:
            return 0.0
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += vertices_2d[i, 0] * vertices_2d[j, 1]
            area -= vertices_2d[j, 0] * vertices_2d[i, 1]
        return abs(area) / 2.0

    def _energy_to_rgb(self, t: float) -> Tuple[float, float, float]:
        t = max(0.0, min(1.0, t))
        if t < 0.25:
            s = t / 0.25
            return (0.0, 0.0, 0.5 + 0.5 * (1.0 - s))
        elif t < 0.5:
            s = (t - 0.25) / 0.25
            return (0.0, s * 0.7, 0.5 * (1.0 - s))
        elif t < 0.75:
            s = (t - 0.5) / 0.25
            return (s * 0.9, 0.7 * (1.0 - 0.3 * s), 0.0)
        else:
            s = (t - 0.75) / 0.25
            return (0.9 + 0.1 * s, 0.5 * (1.0 - s), 0.0)


# FASE 2 COMPLETADA. EL CEREBRO MATEMATICO ESTA LISTO.
# ESPERANDO EL COMANDO "EJECUTA FASE 3" PARA PROGRAMAR LA SIMULACION DE FRAGMENTACION (KUZ-RAM), VIBRACIONES (HOLMBERG-PERSSON) Y REPORTES PDF.
