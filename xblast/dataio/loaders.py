"""Importacion de datos de campo.

Lectores tolerantes para los formatos que llegan de la mina: CSV de collares,
archivos de perforacion tipo TURPO y nubes de puntos topograficas. El
delimitador, la codificacion y los nombres de columna se detectan solos, de
modo que el usuario no tenga que editar el archivo antes de cargarlo.
"""

from __future__ import annotations

import csv
import math
import re
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..core.models import Hole, HoleType

# Sinonimos aceptados por columna (normalizados a minusculas sin acentos).
_ALIASES: Dict[str, Sequence[str]] = {
    "id": ("id", "bhid", "hole", "hole_id", "holeid", "taladro", "nombre", "name", "pozo"),
    "x": ("x", "xp", "east", "easting", "xcollar", "este", "x_collar", "coord_x"),
    "y": ("y", "yp", "north", "northing", "ycollar", "norte", "y_collar", "coord_y"),
    "z": ("z", "zp", "elev", "elevation", "zcollar", "cota", "elev collar", "elevcollar",
          "z_collar", "collar_z"),
    "z_toe": ("elev toe", "elevtoe", "ztoe", "z_toe", "toe", "cota fondo", "elev_toe"),
    "length": ("length", "long", "longitud", "depth", "prof", "profundidad", "largo"),
    "azimuth": ("az", "azimuth", "azimut", "bearing", "rumbo"),
    "dip": ("dip", "inclinacion", "inclination", "buzamiento"),
    "diameter": ("diam", "diameter", "diametro", "dia_mm", "d"),
    "material": ("material", "tipo", "type", "litologia", "rock"),
}


def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ñ", "n")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s)


def _sniff(path: Path) -> Tuple[str, str]:
    """Detecta delimitador y codificacion probables."""
    for enc in ("utf-8-sig", "latin-1"):
        try:
            with open(path, "r", encoding=enc) as f:
                head = f.read(4096)
            counts = {d: head.count(d) for d in (";", ",", "\t", "|")}
            delim = max(counts, key=counts.get)
            return (delim if counts[delim] > 0 else ","), enc
        except UnicodeDecodeError:
            continue
    return ",", "latin-1"


def _map_columns(fieldnames: Sequence[str]) -> Dict[str, str]:
    """Mapea claves canonicas -> nombre real de columna del archivo."""
    norm = {_norm(fn): fn for fn in fieldnames if fn}
    out: Dict[str, str] = {}
    for key, aliases in _ALIASES.items():
        for a in aliases:
            if a in norm:
                out[key] = norm[a]
                break
    return out


def _num(value: str, default: float = 0.0) -> float:
    if value is None:
        return default
    v = str(value).strip().replace(",", ".")
    if not v:
        return default
    try:
        return float(v)
    except ValueError:
        return default


# ---------------------------------------------------------------------------
# Taladros
# ---------------------------------------------------------------------------


def load_holes(
    path: str | Path,
    default_diameter_mm: float = 152.0,
    default_length_m: float = 12.0,
    default_subdrill_m: float = 1.0,
    hole_type: str = HoleType.PRODUCCION.value,
) -> Tuple[List[Hole], Dict[str, object]]:
    """Carga taladros desde CSV de collares o desde un archivo TURPO.

    Se aceptan indistintamente archivos con solo ``ID;X;Y;Z`` y archivos con
    geometria completa (``ELEV TOE``, ``LENGTH``, ``AZ``, ``DIP``). Cuando la
    longitud viene en cero se deduce de la diferencia de cotas, que es el caso
    habitual de las exportaciones de campo.

    Returns:
        ``(taladros, informe)`` donde el informe resume filas leidas,
        descartadas y campos deducidos.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"No se encontro el archivo: {p}")

    delim, enc = _sniff(p)
    holes: List[Hole] = []
    skipped = 0
    derived_length = 0

    with open(p, "r", encoding=enc, newline="") as f:
        reader = csv.DictReader(f, delimiter=delim)
        if not reader.fieldnames:
            raise ValueError("El archivo no tiene encabezado de columnas.")
        cols = _map_columns(reader.fieldnames)

        missing = [k for k in ("x", "y") if k not in cols]
        if missing:
            raise ValueError(
                "No se pudieron identificar las columnas de coordenadas. "
                f"Encabezados leidos: {', '.join(reader.fieldnames)}")

        for i, row in enumerate(reader, start=2):
            row = {k: (v or "").strip() for k, v in row.items() if k}
            x = _num(row.get(cols["x"], ""), math.nan)
            y = _num(row.get(cols["y"], ""), math.nan)
            if not (np.isfinite(x) and np.isfinite(y)):
                skipped += 1
                continue

            z = _num(row.get(cols.get("z", ""), ""), 0.0)
            z_toe = _num(row.get(cols.get("z_toe", ""), ""), math.nan)
            length = _num(row.get(cols.get("length", ""), ""), 0.0)
            dip = _num(row.get(cols.get("dip", ""), ""), -90.0)
            az = _num(row.get(cols.get("azimuth", ""), ""), 0.0)
            diam = _num(row.get(cols.get("diameter", ""), ""), default_diameter_mm)

            # DIP puede venir negativo (convencion de sondaje) o positivo.
            dip_pos = abs(dip) if dip != 0 else 90.0
            dip_pos = min(max(dip_pos, 1.0), 90.0)

            if length <= 0:
                if np.isfinite(z_toe) and abs(z - z_toe) > 0.01:
                    length = abs(z - z_toe) / max(math.sin(math.radians(dip_pos)), 0.15)
                    derived_length += 1
                else:
                    length = default_length_m

            bench = max(length - default_subdrill_m, 1.0) * math.sin(math.radians(dip_pos))
            hid = row.get(cols.get("id", ""), "") or f"H{i - 1:04d}"

            holes.append(Hole(
                hid=str(hid),
                easting=x, northing=y, collar_z=z,
                length_m=length,
                diameter_mm=diam if diam > 0 else default_diameter_mm,
                dip_deg=dip_pos,
                azimuth_deg=az % 360.0,
                subdrill_m=default_subdrill_m,
                bench_height_m=bench,
                hole_type=hole_type,
            ))

    _assign_grid_indices(holes)

    report = {
        "file": p.name,
        "rows_read": len(holes),
        "rows_skipped": skipped,
        "delimiter": delim,
        "encoding": enc,
        "columns": cols,
        "derived_length": derived_length,
        "has_geometry": "dip" in cols or "z_toe" in cols,
    }
    return holes, report


def _assign_grid_indices(holes: Sequence[Hole], tol: float = 0.35) -> None:
    """Deduce fila y columna agrupando collares por bandas de coordenadas."""
    if len(holes) < 2:
        return
    pts = np.array([[h.easting, h.northing] for h in holes], float)
    centered = pts - pts.mean(axis=0)

    # Direccion principal de la malla por analisis de componentes
    try:
        _, _, vt = np.linalg.svd(centered, full_matrices=False)
        main, cross = vt[0], vt[1]
    except np.linalg.LinAlgError:
        main, cross = np.array([1.0, 0.0]), np.array([0.0, 1.0])

    a = centered @ main
    b = centered @ cross
    step_a = _typical_step(a) or 1.0
    step_b = _typical_step(b) or 1.0

    for h, ai, bi in zip(holes, a, b):
        h.col = int(round((ai - a.min()) / (step_a * (1.0 + tol * 0)))) if step_a else 0
        h.row = int(round((bi - b.min()) / (step_b * (1.0 + tol * 0)))) if step_b else 0


def _typical_step(values: np.ndarray) -> float:
    v = np.sort(values)
    d = np.diff(v)
    d = d[d > 1e-3]
    return float(np.median(d)) if d.size else 1.0


# ---------------------------------------------------------------------------
# Topografia
# ---------------------------------------------------------------------------


def load_topography(path: str | Path) -> Tuple[np.ndarray, Dict[str, object]]:
    """Carga una nube de puntos topografica como array ``(N, 3)``.

    Acepta encabezados ``XP;YP;ZP``, ``X;Y;Z``, ``ESTE;NORTE;COTA`` y variantes.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"No se encontro el archivo: {p}")

    delim, enc = _sniff(p)
    pts: List[Tuple[float, float, float]] = []
    skipped = 0

    with open(p, "r", encoding=enc, newline="") as f:
        reader = csv.DictReader(f, delimiter=delim)
        if not reader.fieldnames:
            raise ValueError("El archivo no tiene encabezado de columnas.")
        cols = _map_columns(reader.fieldnames)
        if not all(k in cols for k in ("x", "y", "z")):
            raise ValueError(
                "No se identificaron las columnas X / Y / Z. "
                f"Encabezados leidos: {', '.join(reader.fieldnames)}")

        for row in reader:
            x = _num(row.get(cols["x"], ""), math.nan)
            y = _num(row.get(cols["y"], ""), math.nan)
            z = _num(row.get(cols["z"], ""), math.nan)
            if np.isfinite(x) and np.isfinite(y) and np.isfinite(z):
                pts.append((x, y, z))
            else:
                skipped += 1

    if len(pts) < 3:
        raise ValueError(f"Se requieren al menos 3 puntos validos; se leyeron {len(pts)}.")

    arr = np.array(pts, float)
    report = {
        "file": p.name,
        "points": len(arr),
        "skipped": skipped,
        "bounds": (float(arr[:, 0].min()), float(arr[:, 0].max()),
                   float(arr[:, 1].min()), float(arr[:, 1].max())),
        "z_range": (float(arr[:, 2].min()), float(arr[:, 2].max())),
    }
    return arr, report


def elevation_interpolator(points: np.ndarray):
    """Devuelve ``f(x, y) -> z`` por interpolacion lineal sobre la triangulacion.

    Fuera del dominio triangulado cae al vecino mas proximo, para que un collar
    ligeramente fuera de la nube no quede sin cota.
    """
    from scipy.interpolate import LinearNDInterpolator, NearestNDInterpolator

    xy = points[:, :2]
    z = points[:, 2]
    lin = LinearNDInterpolator(xy, z)
    near = NearestNDInterpolator(xy, z)

    def f(x: float, y: float) -> float:
        v = lin(x, y)
        v = float(v) if np.isfinite(v) else float(near(x, y))
        return v

    return f


# ---------------------------------------------------------------------------
# Cara libre
# ---------------------------------------------------------------------------


def load_free_face(path: str | Path) -> np.ndarray:
    """Carga la polilinea de la cara libre desde CSV de puntos ordenados."""
    pts, _ = load_topography(path)
    return pts


def free_face_from_holes(holes: Sequence[Hole], face_azimuth_deg: float,
                         offset_m: float = 3.0) -> np.ndarray:
    """Estima la cara libre como la envolvente frontal de los collares."""
    if not holes:
        return np.empty((0, 2))
    az = math.radians(face_azimuth_deg)
    v = np.array([math.sin(az), math.cos(az)])
    u = np.array([v[1], -v[0]])

    pts = np.array([[h.easting, h.northing] for h in holes], float)
    su = pts @ u
    sv = pts @ v
    front = sv.max()
    order = np.argsort(su)
    n = max(2, len(order) // 8)
    picks = order[:: max(1, len(order) // max(n, 2))]

    line = []
    for i in picks:
        line.append(u * su[i] + v * (front + offset_m))
    line.sort(key=lambda q: float(q @ u))
    return np.array(line) if len(line) >= 2 else np.array([
        u * su.min() + v * (front + offset_m),
        u * su.max() + v * (front + offset_m),
    ])
