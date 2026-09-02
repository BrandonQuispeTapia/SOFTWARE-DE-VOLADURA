"""
core/ore_control.py
===================
Predictor Cinemático de Dilución (Heave) para VOLADURA_PRO_10X.

Este módulo proyecta el desplazamiento del centro de masas (Heave) 
condicionado por la secuencia temporal y el factor de carga, 
permitiendo predecir la dilución y pérdida de mineral (Ore Loss).

Autor: Félix Fernando Bautista Layme — UNA Puno.
"""

from dataclasses import dataclass
from typing import Tuple

from core.geometry import Point3D, Vector3D


@dataclass
class HeaveDisplacement:
    """Vector de desplazamiento de Heave.
    
    Attributes:
        dx: Desplazamiento en Este [m].
        dy: Desplazamiento en Norte [m].
        dz: Desplazamiento en Elevación [m].
    """
    dx: float
    dy: float
    dz: float


@dataclass
class HeaveModel:
    """Modelo de predicción de desplazamiento del centro de masas.

    Attributes:
        heave_proportionality_constant: Constante empírica (k_heave) que 
            relaciona el factor de carga con el desplazamiento.
            Dependerá del tipo de roca y confinamiento.
    """
    heave_proportionality_constant: float = 2.5  # Ejemplo: 2.5 m por cada kg/m3

    def calculate_mass_center_displacement(
        self,
        centroid: Point3D,
        free_face_normal: Vector3D,
        powder_factor_kg_m3: float
    ) -> HeaveDisplacement:
        """Calcula el vector de traslación 3D del centroide del bloque.

        El desplazamiento ocurre predominantemente en la dirección de la
        cara libre (free_face_normal) y su magnitud es proporcional
        al factor de carga (Powder Factor).

        Args:
            centroid: Coordenada 3D original del centro de masas del polígono de mineral.
            free_face_normal: Vector normal 3D apuntando hacia la cara libre.
            powder_factor_kg_m3: Factor de carga (Densidad de energía) [kg/m³].

        Returns:
            Objeto HeaveDisplacement con las componentes (dx, dy, dz).
        """
        # Normalizamos la cara libre por seguridad
        normal = free_face_normal.normalize()

        # Módulo del desplazamiento = k * Factor de Carga
        displacement_magnitude = self.heave_proportionality_constant * powder_factor_kg_m3

        # Vector de desplazamiento = magnitud * normal
        displacement_vector = normal.scale(displacement_magnitude)

        return HeaveDisplacement(
            dx=displacement_vector.x,
            dy=displacement_vector.y,
            dz=displacement_vector.z
        )
