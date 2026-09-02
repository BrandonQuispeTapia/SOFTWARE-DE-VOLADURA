"""
core/topography_interpolator.py
==============================
Interpolador de topografía para obtener elevaciones en puntos específicos.

Utiliza triangulación de Delaunay para interpolar valores Z de una malla
topográfica de puntos irregulares.

Autor: Félix Fernando Bautista Layme — UNA Puno.
"""

import numpy as np
from typing import Optional, Tuple
from scipy.spatial import Delaunay
from scipy.interpolate import LinearNDInterpolator


class TopographyInterpolator:
    """Interpolador de elevaciones topográficas.

    Lee una malla de puntos topográficos (XP, YP, ZP) y proporciona
    interpolación lineal en cualquier punto (X, Y) dentro del dominio.
    """

    def __init__(self, topography_points: np.ndarray):
        """Inicializa el interpolador.

        Args:
            topography_points: Array de forma (N, 3) con [X, Y, Z] en metros.
                              N ≥ 3 para que sea válido.

        Raises:
            ValueError: Si hay menos de 3 puntos o si la malla es coplanar.
        """
        if topography_points.shape[0] < 3:
            raise ValueError(
                f"Se necesitan al menos 3 puntos para interpolar. "
                f"Recibidos: {topography_points.shape[0]}"
            )

        self.points = topography_points.astype(np.float64)
        xy = self.points[:, :2]
        z = self.points[:, 2]

        try:
            self.interpolator = LinearNDInterpolator(xy, z, fill_value=np.nan)
        except Exception as e:
            raise ValueError(
                f"Error creando interpolador: {e}. "
                f"Verifica que los puntos no sean coplanares."
            )

    def get_elevation(self, x: float, y: float, default: Optional[float] = None) -> float:
        """Obtiene la elevación interpolada en un punto (X, Y).

        Args:
            x: Coordenada Este [m].
            y: Coordenada Norte [m].
            default: Valor por defecto si el punto está fuera de la malla.
                    Si es None, retorna np.nan.

        Returns:
            Elevación Z [m]. Retorna `default` si está fuera del dominio.
        """
        try:
            z = self.interpolator(x, y)
            if np.isnan(z):
                if default is not None:
                    return default
                return np.nan
            return float(z)
        except Exception:
            if default is not None:
                return default
            return np.nan

    def get_elevations(self, points_xy: np.ndarray) -> np.ndarray:
        """Obtiene elevaciones para múltiples puntos.

        Args:
            points_xy: Array de forma (N, 2) con [X, Y] en metros.

        Returns:
            Array de forma (N,) con elevaciones Z [m].
        """
        return self.interpolator(points_xy[:, 0], points_xy[:, 1])

    def bounds(self) -> Tuple[float, float, float, float]:
        """Retorna los límites de la malla (min_x, max_x, min_y, max_y)."""
        xy = self.points[:, :2]
        return (
            float(np.min(xy[:, 0])),
            float(np.max(xy[:, 0])),
            float(np.min(xy[:, 1])),
            float(np.max(xy[:, 1])),
        )
