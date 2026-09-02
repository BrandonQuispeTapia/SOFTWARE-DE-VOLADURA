"""Analisis de burden real, alivio y volumen de responsabilidad.

En vez de asumir que todos los taladros tienen el burden nominal, este modulo
calcula para cada taladro:

    * el **burden real** a la cara libre geometrica;
    * el **burden de alivio**, medido a la cara efectiva en el instante del
      disparo (cara original o el hueco dejado por taladros que ya salieron);
    * el **volumen de responsabilidad** por teselacion de Voronoi acotada,
      que reemplaza el producto B x S x H uniforme;
    * un indice de **confinamiento** que alimenta la fragmentacion y el
      riesgo de proyeccion.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from .models import Hole

try:  # scipy es dependencia dura del proyecto, pero degradamos con elegancia
    from scipy.spatial import Voronoi, cKDTree
    _HAS_SCIPY = True
except Exception:  # pragma: no cover
    _HAS_SCIPY = False


# ---------------------------------------------------------------------------
# Utilidades geometricas
# ---------------------------------------------------------------------------


def _distance_point_polyline(p: np.ndarray, poly: np.ndarray) -> float:
    """Distancia minima 2D de un punto a una polilinea."""
    if poly is None or len(poly) < 2:
        return float("inf")
    a = poly[:-1, :2]
    b = poly[1:, :2]
    ab = b - a
    ap = p[:2] - a
    denom = np.einsum("ij,ij->i", ab, ab)
    denom[denom == 0] = 1e-12
    t = np.clip(np.einsum("ij,ij->i", ap, ab) / denom, 0.0, 1.0)
    proj = a + t[:, None] * ab
    return float(np.min(np.linalg.norm(p[:2] - proj, axis=1)))


def _polygon_area(pts: np.ndarray) -> float:
    """Area de un poligono simple por la formula del zapatero."""
    x, y = pts[:, 0], pts[:, 1]
    return 0.5 * abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


def _clip_polygon(poly: np.ndarray, clip: np.ndarray) -> np.ndarray:
    """Recorte de Sutherland-Hodgman de ``poly`` contra el convexo ``clip``."""
    out = poly
    n = len(clip)
    for i in range(n):
        if len(out) == 0:
            return np.empty((0, 2))
        a, b = clip[i], clip[(i + 1) % n]
        edge = b - a
        inside = lambda p: edge[0] * (p[1] - a[1]) - edge[1] * (p[0] - a[0]) >= -1e-9
        new: List[np.ndarray] = []
        for j in range(len(out)):
            cur, prv = out[j], out[j - 1]
            ci, pi = inside(cur), inside(prv)
            if ci:
                if not pi:
                    new.append(_intersect(prv, cur, a, b))
                new.append(cur)
            elif pi:
                new.append(_intersect(prv, cur, a, b))
        out = np.array(new) if new else np.empty((0, 2))
    return out


def _intersect(p1: np.ndarray, p2: np.ndarray, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    d1 = p2 - p1
    d2 = b - a
    den = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(den) < 1e-12:
        return p2
    t = ((a[0] - p1[0]) * d2[1] - (a[1] - p1[1]) * d2[0]) / den
    return p1 + t * d1


def _convex_hull(pts: np.ndarray) -> np.ndarray:
    """Envolvente convexa 2D (monotone chain)."""
    p = np.unique(pts[:, :2], axis=0)
    if len(p) < 3:
        return p
    p = p[np.lexsort((p[:, 1], p[:, 0]))]
    cross = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower: List[np.ndarray] = []
    for q in p:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], q) <= 0:
            lower.pop()
        lower.append(q)
    upper: List[np.ndarray] = []
    for q in p[::-1]:
        while len(upper) >= 2 and cross(upper[-2], upper[-1], q) <= 0:
            upper.pop()
        upper.append(q)
    return np.array(lower[:-1] + upper[:-1])


# ---------------------------------------------------------------------------
# Volumen de responsabilidad
# ---------------------------------------------------------------------------


def responsibility_areas(holes: Sequence[Hole], nominal_area: float) -> np.ndarray:
    """Area de influencia [m2] de cada taladro por Voronoi acotado.

    El diagrama se recorta contra la envolvente convexa de los collares
    dilatada media malla, de modo que los taladros del perimetro no reciben
    celdas infinitas.
    """
    n = len(holes)
    if n == 0:
        return np.empty(0)
    if n < 4 or not _HAS_SCIPY:
        return np.full(n, nominal_area, float)

    pts = np.array([[h.easting, h.northing] for h in holes], float)
    hull = _convex_hull(pts)
    if len(hull) < 3:
        return np.full(n, nominal_area, float)

    centroid = hull.mean(axis=0)
    pad = math.sqrt(max(nominal_area, 1.0)) * 0.5
    dirs = hull - centroid
    norms = np.linalg.norm(dirs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    clip = hull + dirs / norms * pad

    try:
        vor = Voronoi(pts)
    except Exception:
        return np.full(n, nominal_area, float)

    areas = np.full(n, nominal_area, float)
    for i, reg_idx in enumerate(vor.point_region):
        region = vor.regions[reg_idx]
        if not region or -1 in region:
            cell = clip                      # celda abierta: usar el recorte
        else:
            cell = vor.vertices[region]
        cell = _clip_polygon(np.asarray(cell, float), clip)
        if len(cell) >= 3:
            a = _polygon_area(cell)
            if 0.15 * nominal_area <= a <= 6.0 * nominal_area:
                areas[i] = a
    return areas


# ---------------------------------------------------------------------------
# Burden real y de alivio
# ---------------------------------------------------------------------------


def compute_true_burden(
    holes: Sequence[Hole],
    free_face: Optional[np.ndarray],
    nominal_burden: float,
    nominal_spacing: float,
    face_azimuth_deg: Optional[float] = None,
) -> None:
    """Calcula ``burden_real_m``, ``spacing_real_m`` y ``confinement``.

    El burden de un taladro es la roca que tiene delante hasta la cara que lo
    libera. Para los taladros de la primera fila esa cara es la cara libre
    geometrica; para los del interior es la fila que sale antes, de modo que el
    burden real es la distancia al taladro mas proximo situado *hacia* la cara.
    El menor de ambos valores es el que gobierna.
    """
    if not holes:
        return

    pts = np.array([[h.easting, h.northing] for h in holes], float)

    # Direccion de salida: la del azimut declarado o, si no se conoce, la que
    # va del centroide de la malla hacia el punto mas cercano de la cara.
    if face_azimuth_deg is not None:
        az = math.radians(face_azimuth_deg)
        v = np.array([math.sin(az), math.cos(az)])
    elif free_face is not None and len(free_face) >= 2:
        centroid = pts.mean(axis=0)
        seg = free_face[:, :2].mean(axis=0) - centroid
        norm = np.linalg.norm(seg)
        v = seg / norm if norm > 1e-6 else np.array([0.0, 1.0])
    else:
        v = np.array([0.0, 1.0])

    depth = pts @ v                      # mayor = mas cerca de la cara
    tree = cKDTree(pts) if (_HAS_SCIPY and len(pts) > 1) else None

    for i, h in enumerate(holes):
        p = pts[i]
        d_face = _distance_point_polyline(p, free_face) if free_face is not None else float("inf")

        # Vecino mas cercano por delante (mas proximo a la cara libre)
        ahead = np.where(depth > depth[i] + nominal_burden * 0.35)[0]
        d_ahead = float(np.min(np.linalg.norm(pts[ahead] - p, axis=1))) if ahead.size else float("inf")

        candidates = [d for d in (d_face, d_ahead) if np.isfinite(d) and d > 0.1]
        h.burden_real_m = float(min(candidates)) if candidates else nominal_burden

        # Espaciamiento: vecino mas cercano dentro de la misma banda de burden
        same = np.where(np.abs(depth - depth[i]) <= nominal_burden * 0.35)[0]
        same = same[same != i]
        if same.size:
            h.spacing_real_m = float(np.min(np.linalg.norm(pts[same] - p, axis=1)))
        elif tree is not None and len(pts) > 1:
            dist = np.atleast_1d(tree.query(p, k=min(2, len(pts)))[0])[-1]
            h.spacing_real_m = float(dist) if dist > 0 else nominal_spacing
        else:
            h.spacing_real_m = nominal_spacing

        # Confinamiento: 0 contra la cara libre, ->1 hacia el interior de la malla
        rel = d_face / (nominal_burden * 4.0) if np.isfinite(d_face) else 1.0
        h.confinement = float(np.clip(rel, 0.05, 1.0))


def compute_relief_burden(holes: Sequence[Hole], min_relief_ms: float = 5.0) -> None:
    """Burden de alivio: distancia a la cara efectiva en el instante del disparo.

    Para cada taladro se busca el vecino que detona al menos ``min_relief_ms``
    antes; ese hueco actua como cara libre. Si no existe tal vecino, el
    taladro dispara contra la cara original (``burden_real_m``).
    """
    n = len(holes)
    if n == 0:
        return
    pts = np.array([[h.easting, h.northing] for h in holes], float)
    times = np.array([h.delay_ms for h in holes], float)

    for i, h in enumerate(holes):
        earlier = np.where(times <= times[i] - min_relief_ms)[0]
        if earlier.size == 0:
            h.relief_burden_m = h.burden_real_m
            continue
        d = np.linalg.norm(pts[earlier] - pts[i], axis=1)
        h.relief_burden_m = float(min(np.min(d), h.burden_real_m))


def assign_volumes(holes: Sequence[Hole], nominal_area: float) -> None:
    """Asigna ``volume_m3`` a cada taladro (area de Voronoi x altura de banco)."""
    areas = responsibility_areas(holes, nominal_area)
    for h, a in zip(holes, areas):
        h.volume_m3 = float(a * max(h.bench_height_m, 0.1))


def burden_statistics(holes: Sequence[Hole]) -> Dict[str, float]:
    """Estadistica de dispersion del burden real (indicador de calidad de malla)."""
    if not holes:
        return {}
    b = np.array([h.burden_real_m for h in holes], float)
    r = np.array([h.relief_burden_m for h in holes], float)
    return {
        "burden_mean_m": float(np.mean(b)),
        "burden_std_m": float(np.std(b)),
        "burden_cv_pct": float(np.std(b) / max(np.mean(b), 1e-6) * 100.0),
        "burden_min_m": float(np.min(b)),
        "burden_max_m": float(np.max(b)),
        "relief_mean_m": float(np.mean(r)),
        "relief_min_m": float(np.min(r)),
    }


def audit_burden(holes: Sequence[Hole], nominal_burden: float) -> List[Dict[str, str]]:
    """Detecta taladros con burden excesivo o insuficiente."""
    out: List[Dict[str, str]] = []
    if not holes:
        return out

    b = np.array([h.burden_real_m for h in holes], float)
    tight = [h.hid for h in holes if h.burden_real_m < 0.65 * nominal_burden]
    heavy = [h.hid for h in holes if h.burden_real_m > 1.35 * nominal_burden]
    cv = float(np.std(b) / max(np.mean(b), 1e-6) * 100.0)

    if tight:
        out.append({"level": "error", "item": "Burden corto",
                    "message": f"{len(tight)} taladro(s) con burden < 65% del nominal "
                               f"({', '.join(tight[:8])}{'...' if len(tight) > 8 else ''}). "
                               "Riesgo alto de proyeccion y onda aerea."})
    if heavy:
        out.append({"level": "warn", "item": "Burden excesivo",
                    "message": f"{len(heavy)} taladro(s) con burden > 135% del nominal "
                               f"({', '.join(heavy[:8])}{'...' if len(heavy) > 8 else ''}). "
                               "Esperar bolones y lomos."})
    if cv > 20.0:
        out.append({"level": "warn", "item": "Uniformidad de malla",
                    "message": f"Coeficiente de variacion del burden = {cv:.1f}% (> 20%). "
                               "Fragmentacion heterogenea."})
    elif not tight and not heavy:
        out.append({"level": "ok", "item": "Uniformidad de malla",
                    "message": f"Burden uniforme (CV = {cv:.1f}%)."})
    return out
