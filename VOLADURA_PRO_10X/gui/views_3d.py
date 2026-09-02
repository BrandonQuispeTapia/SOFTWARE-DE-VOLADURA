"""
gui/views_3d.py
===============
Visor 3D Interactivo para VOLADURA_PRO_10X.

Utiliza PyVista y PyVistaQt para renderizar la topografía y los 
cilindros representativos de los taladros en 3D real.

Autor: Félix Fernando Bautista Layme — UNA Puno.
"""

import numpy as np
import pyvista as pv
from pyvistaqt import QtInteractor
from PySide6.QtCore import Signal, QObject
from PySide6.QtWidgets import QVBoxLayout, QWidget
import math

from core.geometry import BlastPattern


class ViewerSignals(QObject):
    """Señales emitidas por el visor 3D."""
    hole_picked = Signal(str)  # Emite el ID del taladro seleccionado


class BlastViewer3D(QWidget):
    """Widget contenedor del visor 3D de PyVista."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.signals = ViewerSignals()

        # Layout del widget
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Crear el interactor de PyVista Qt
        self.plotter = QtInteractor(self)
        layout.addWidget(self.plotter.interactor)

        self._setup_plotter()
        self.current_actors = []

    def _setup_plotter(self):
        self.plotter.set_background("#111115") # Dark mode theme
        self.plotter.add_axes(
            color="white",
            x_color="#ef4444", 
            y_color="#22c55e", 
            z_color="#3b82f6"
        )

    @staticmethod
    def create_inclined_cylinder(
        collar: np.ndarray,
        toe: np.ndarray,
        radius: float,
        length_segment: float,
        start_depth: float = 0.0,
        resolution: int = 20
    ) -> pv.Cylinder:
        """Crea un cilindro inclinado verdadero.

        Args:
            collar: Punto de inicio [X, Y, Z] en metros.
            toe: Punto final [X, Y, Z] en metros.
            radius: Radio del cilindro [m].
            length_segment: Longitud del segmento de cilindro [m].
            start_depth: Profundidad desde collar donde comienza este segmento [m].
            resolution: Resolución angular del cilindro (número de caras).

        Returns:
            Objeto pv.Cylinder alineado entre collar y toe.
        """
        # Vector dirección desde collar a toe
        direction = toe - collar
        total_length = np.linalg.norm(direction)

        if total_length < 1e-9:
            raise ValueError("Collar y toe no pueden ser iguales")

        # Vector unitario
        direction_unit = direction / total_length

        # Centro del segmento en el espacio 3D
        segment_center = collar + direction_unit * (start_depth + length_segment / 2.0)

        # Crear cilindro con la dirección correcta
        cylinder = pv.Cylinder(
            center=segment_center,
            direction=direction_unit,
            radius=radius,
            height=length_segment,
            resolution=resolution
        )

        return cylinder

    def load_topography(self, mesh_data: pv.DataSet):
        """Carga y renderiza una superficie topográfica.

        Args:
            mesh_data: Objeto de malla de PyVista (ej. PolyData o StructuredGrid).
        """
        self.plotter.add_mesh(
            mesh_data, 
            cmap="terrain", 
            show_edges=True, 
            edge_color="gray", 
            name="topography"
        )
        self.plotter.reset_camera()

    def draw_drillholes(self, pattern: BlastPattern):
        """Dibuja los taladros como cilindros 3D segmentados (taco y carga).

        Args:
            pattern: Instancia de BlastPattern con la malla calculada.
        """
        # Limpiar actores previos de taladros
        for actor in self.current_actors:
            self.plotter.remove_actor(actor)
        self.current_actors.clear()

        if not pattern.holes:
            return

        for hole in pattern.holes:
            # Propiedades geométricas
            radius = hole.radius_m
            collar = hole.collar.as_array()
            toe = hole.toe.as_array()

            # --- Cilindro de Taco (Stemming) ---
            stemming_length = hole.stemming
            if stemming_length > 0:
                stemming_cylinder = self.create_inclined_cylinder(
                    collar=collar,
                    toe=toe,
                    radius=radius,
                    length_segment=stemming_length,
                    start_depth=0.0,
                    resolution=20
                )

                # Asignar ID al mesh para picking
                stemming_cylinder.cell_data["hole_id"] = [hole.hole_id] * stemming_cylinder.n_cells

                actor_stemming = self.plotter.add_mesh(
                    stemming_cylinder, 
                    color="#9ca3af",
                    pickable=True,
                    name=f"stemming_{hole.hole_id}"
                )
                self.current_actors.append(actor_stemming)

            # --- Cilindro de Explosivo ---
            charge_length = hole.charge_length
            if charge_length > 0:
                charge_cylinder = self.create_inclined_cylinder(
                    collar=collar,
                    toe=toe,
                    radius=radius,
                    length_segment=charge_length,
                    start_depth=stemming_length,
                    resolution=20
                )

                # Asignar ID al mesh para picking
                charge_cylinder.cell_data["hole_id"] = [hole.hole_id] * charge_cylinder.n_cells

                actor_charge = self.plotter.add_mesh(
                    charge_cylinder, 
                    color="#ef4444",
                    pickable=True,
                    name=f"charge_{hole.hole_id}"
                )
                self.current_actors.append(actor_charge)

        # Configurar picking
        self.plotter.enable_cell_picking(
            callback=self._on_hole_picked,
            show=True,
            show_message=False,
            color="#3b82f6"
        )

        # Ajustar cámara
        self.plotter.reset_camera()

    def _on_hole_picked(self, mesh):
        """Callback ejecutado cuando el usuario hace clic en un taladro."""
        if mesh and "hole_id" in mesh.cell_data:
            # Obtener el ID del primer array (todo el cilindro tiene el mismo ID)
            hole_id = mesh.cell_data["hole_id"][0]
            self.signals.hole_picked.emit(str(hole_id))
