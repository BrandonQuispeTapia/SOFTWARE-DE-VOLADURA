"""Campo 3D de distribucion de energia explosiva.

Discretiza cada columna de carga en elementos y acumula la energia que aporta
cada uno sobre una grilla regular, con un nucleo de atenuacion radial. El
resultado permite ver donde queda roca sub-energizada (bolones, lomos) y donde
hay exceso de energia (finos, proyeccion, sobre-rotura), que es el diagnostico
central de una revision de diseno.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import explosives as exdb
from .models import Hole


@dataclass
class EnergyField:
    """Campo escalar de energia sobre una grilla regular."""

    origin: np.ndarray          # (3,) esquina minima
    spacing: float              # tamano de celda [m]
    dims: Tuple[int, int, int]  # (nx, ny, nz)
    values: np.ndarray          # (nx, ny, nz) en MJ/m3

    @property
    def flat(self) -> np.ndarray:
        """Valores en orden Fortran, listo para ``pyvista.ImageData``."""
        return self.values.ravel(order="F")

    def stats(self) -> Dict[str, float]:
        v = self.values[self.values > 0]
        if v.size == 0:
            return {"min": 0.0, "max": 0.0, "mean": 0.0, "p10": 0.0, "p90": 0.0}
        return {
            "min": float(v.min()), "max": float(v.max()), "mean": float(v.mean()),
            "p10": float(np.percentile(v, 10)), "p90": float(np.percentile(v, 90)),
        }

    def coverage(self, target_mj_m3: float, tolerance: float = 0.5) -> Dict[str, float]:
        """Fraccion del volumen sub-energizado, en rango y sobre-energizado.

        Solo se consideran las celdas dentro del bloque efectivamente volado;
        el halo exterior de la grilla, con energia residual, se descarta para
        no sesgar el diagnostico hacia el lado sub-energizado.
        """
        v = self.values.ravel()
        active = v[v > max(1e-6, target_mj_m3 * 0.2)]
        if active.size == 0:
            return {"under_pct": 0.0, "in_range_pct": 0.0, "over_pct": 0.0}
        lo = target_mj_m3 * (1.0 - tolerance)
        hi = target_mj_m3 * (1.0 + tolerance)
        return {
            "under_pct": float(np.mean(active < lo) * 100.0),
            "in_range_pct": float(np.mean((active >= lo) & (active <= hi)) * 100.0),
            "over_pct": float(np.mean(active > hi) * 100.0),
        }


def compute_energy_field(
    holes: Sequence[Hole],
    cell_size: float = 1.0,
    padding: float = 3.0,
    influence_radius: Optional[float] = None,
    max_cells: int = 900_000,
) -> Optional[EnergyField]:
    """Calcula el campo de energia [MJ/m3] alrededor de la malla.

    Args:
        holes: taladros cargados.
        cell_size: arista de celda [m]; se ajusta si excede ``max_cells``.
        padding: margen alrededor de la nube de taladros [m].
        influence_radius: radio de influencia de cada elemento de carga; por
            defecto 1.6 veces el burden medio.
    """
    charged = [h for h in holes if h.charge_kg > 0]
    if not charged:
        return None

    pts = np.array([[h.easting, h.northing, h.collar_z] for h in charged], float)
    toes = np.array([h.toe for h in charged], float)
    lo = np.minimum(pts.min(axis=0), toes.min(axis=0)) - padding
    hi = np.maximum(pts.max(axis=0), toes.max(axis=0)) + padding

    if influence_radius is None:
        b = np.mean([h.burden_real_m for h in charged if h.burden_real_m > 0] or [3.0])
        influence_radius = float(max(b * 2.2, 2.5))

    # Ajuste de resolucion para no explotar en memoria
    span = hi - lo
    for _ in range(8):
        dims = np.maximum(np.ceil(span / cell_size).astype(int) + 1, 2)
        if int(np.prod(dims)) <= max_cells:
            break
        cell_size *= 1.35
    dims = tuple(int(d) for d in dims)

    xs = lo[0] + np.arange(dims[0]) * cell_size
    ys = lo[1] + np.arange(dims[1]) * cell_size
    zs = lo[2] + np.arange(dims[2]) * cell_size

    field = np.zeros(dims, float)
    cell_vol = cell_size ** 3
    r2 = influence_radius ** 2

    for h in charged:
        for p0, p1, deck in h.charge_segments():
            exp = exdb.get(deck.explosive)
            lin = exp.linear_density_kg_m(h.diameter_mm, deck.coupling)
            n_seg = max(2, int(deck.length_m / max(cell_size * 0.75, 0.25)))
            seg_len = deck.length_m / n_seg
            seg_energy = lin * seg_len * exp.energy_mj_kg     # MJ por elemento
            centers = np.linspace(0.0, 1.0, n_seg, endpoint=False) + 0.5 / n_seg
            elems = p0[None, :] + (p1 - p0)[None, :] * centers[:, None]

            for e in elems:
                ix0 = max(0, int((e[0] - influence_radius - lo[0]) / cell_size))
                ix1 = min(dims[0], int((e[0] + influence_radius - lo[0]) / cell_size) + 2)
                iy0 = max(0, int((e[1] - influence_radius - lo[1]) / cell_size))
                iy1 = min(dims[1], int((e[1] + influence_radius - lo[1]) / cell_size) + 2)
                iz0 = max(0, int((e[2] - influence_radius - lo[2]) / cell_size))
                iz1 = min(dims[2], int((e[2] + influence_radius - lo[2]) / cell_size) + 2)
                if ix0 >= ix1 or iy0 >= iy1 or iz0 >= iz1:
                    continue

                gx = xs[ix0:ix1][:, None, None]
                gy = ys[iy0:iy1][None, :, None]
                gz = zs[iz0:iz1][None, None, :]
                d2 = (gx - e[0]) ** 2 + (gy - e[1]) ** 2 + (gz - e[2]) ** 2

                # nucleo de soporte compacto (Wendland C2) normalizado en volumen
                w = np.clip(1.0 - d2 / r2, 0.0, 1.0) ** 2
                s = w.sum()
                if s > 0:
                    field[ix0:ix1, iy0:iy1, iz0:iz1] += seg_energy * w / (s * cell_vol)

    return EnergyField(origin=lo, spacing=cell_size, dims=dims, values=field)


def target_energy_mj_m3(powder_factor_kg_m3: float, energy_mj_kg: float = 3.72) -> float:
    """Energia objetivo equivalente al factor de potencia de diseno."""
    return float(powder_factor_kg_m3 * energy_mj_kg)


def audit_energy(field: Optional[EnergyField], target: float) -> List[Dict[str, str]]:
    """Diagnostico de la distribucion de energia."""
    out: List[Dict[str, str]] = []
    if field is None:
        return out
    cov = field.coverage(target)
    if cov["under_pct"] > 45.0:
        out.append({"level": "warn", "item": "Zonas sub-energizadas",
                    "message": f"{cov['under_pct']:.0f}% del volumen recibe menos energia de la de diseno. "
                               "Esperar bolones y lomos en esas zonas."})
    if cov["over_pct"] > 35.0:
        out.append({"level": "warn", "item": "Zonas sobre-energizadas",
                    "message": f"{cov['over_pct']:.0f}% del volumen excede la energia de diseno. "
                               "Exceso de finos, vibracion y riesgo de proyeccion."})
    if cov["in_range_pct"] >= 45.0:
        out.append({"level": "ok", "item": "Distribucion de energia",
                    "message": f"{cov['in_range_pct']:.0f}% del volumen dentro de +/-50% de la energia objetivo."})
    return out
