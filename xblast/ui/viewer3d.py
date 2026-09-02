"""Visor 3D de la voladura.

Envuelve el interactor de VTK/PyVista y concentra la construccion de la escena
—terreno, cara libre, columnas de carga, etiquetas, campo de energia— junto con
la navegacion de camara y la seleccion interactiva de taladros.

Sobre la interaccion: el picking se implementa con observadores propios sobre
el interactor de VTK en vez de con ``enable_point_picking``. La razon es que esa
funcion se apropia del boton izquierdo y deja la escena sin rotacion. Aqui el
boton izquierdo sigue perteneciendo al estilo de camara: se distingue un clic de
un arrastre midiendo el desplazamiento entre pulsar y soltar, de modo que rotar
y seleccionar conviven en el mismo boton.
"""

from __future__ import annotations

import math
import time
from enum import Enum
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import numpy as np
import pyvista as pv
import vtk
from pyvistaqt import QtInteractor
from PySide6.QtCore import QObject, QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ..core.models import HOLE_TYPE_COLORS, Hole
from .theme import C

#: Variables por las que se puede tematizar la malla.
THEMES: Dict[str, Tuple[str, str]] = {
    "Tipo de taladro": ("type", ""),
    "Retardo (ms)": ("delay_ms", "ms"),
    "Factor de potencia (kg/m3)": ("powder_factor", "kg/m3"),
    "Carga (kg)": ("charge_kg", "kg"),
    "Burden real (m)": ("burden_real_m", "m"),
    "Burden de alivio (m)": ("relief_burden_m", "m"),
    "X50 previsto (cm)": ("x50_cm", "cm"),
    "Confinamiento": ("confinement", ""),
}


class NavMode(str, Enum):
    """Estilo de interaccion de la camara."""

    ORBITA = "Orbita libre"
    TERRENO = "Terreno (Z arriba)"
    JOYSTICK = "Joystick"
    PLANTA = "Planta 2D"


#: Vistas normalizadas disponibles en la barra del visor.
STANDARD_VIEWS = {
    "Isometrica": "iso",
    "Planta": "top",
    "Norte": "north",
    "Sur": "south",
    "Este": "east",
    "Oeste": "west",
}

_CLICK_PIXEL_TOLERANCE = 6      # px de desplazamiento que aun cuentan como clic
_CLICK_TIME_TOLERANCE = 0.6     # s


# ---------------------------------------------------------------------------
# Superposicion para la seleccion por ventana
# ---------------------------------------------------------------------------


class _RubberBand(QWidget):
    """Capa transparente que dibuja el rectangulo de seleccion por ventana."""

    finished = Signal(QRect, bool, bool)   # (rect, aditiva, sustractiva)
    cancelled = Signal()

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._origin: Optional[QPoint] = None
        self._current: Optional[QPoint] = None
        self.hide()

    def mousePressEvent(self, event):
        if event.button() is Qt.MouseButton.LeftButton:
            self._origin = event.position().toPoint()
            self._current = self._origin
            self.update()

    def mouseMoveEvent(self, event):
        if self._origin is not None:
            self._current = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if self._origin is None:
            return
        rect = QRect(self._origin, event.position().toPoint()).normalized()
        additive = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        subtractive = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        self._origin = self._current = None
        self.update()
        if rect.width() > 3 and rect.height() > 3:
            self.finished.emit(rect, additive, subtractive)
        else:
            self.cancelled.emit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._origin = self._current = None
            self.update()
            self.cancelled.emit()

    def paintEvent(self, _event):
        if self._origin is None or self._current is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        rect = QRect(self._origin, self._current).normalized()
        painter.fillRect(rect, QColor(22, 104, 179, 38))
        painter.setPen(QPen(QColor(C["accent"]), 1, Qt.PenStyle.DashLine))
        painter.drawRect(rect)
        painter.end()


# ---------------------------------------------------------------------------
# Visor
# ---------------------------------------------------------------------------


class Viewer3D(QObject):
    """Gestiona la escena 3D, la camara y la seleccion."""

    selection_changed = Signal(list)     # lista de identificadores
    hole_activated = Signal(str)         # doble clic sobre un taladro
    frame_changed = Signal(float)
    animation_finished = Signal()
    status_message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.plotter = QtInteractor(parent)
        self.widget = self.plotter.interactor

        self._holes: List[Hole] = []
        self._collars: np.ndarray = np.empty((0, 3))
        self._actors: Dict[str, object] = {}
        self._charge_meshes: List[pv.PolyData] = []
        self._charge_index: List[int] = []
        self._labels_visible = False
        self._theme = "Tipo de taladro"
        self._selection: List[str] = []
        self._z_scale = 1.0
        self._nav_mode = NavMode.ORBITA
        self._user_parallel = False   # proyeccion elegida por el usuario

        # deteccion de clic frente a arrastre
        self._press_pos: Tuple[int, int] = (0, 0)
        self._press_time = 0.0
        self._last_click_time = 0.0
        self._last_click_hid: Optional[str] = None

        # animaciones
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._anim_t = 0.0
        self._anim_speed = 1.0
        self._anim_end = 0.0

        self._spin_timer = QTimer(self)
        self._spin_timer.timeout.connect(self._spin_step)

        self._band = _RubberBand(self.widget)
        self._band.finished.connect(self._on_band_finished)
        self._band.cancelled.connect(lambda: self.set_box_selection(False))

        self._setup_scene()
        self._install_interaction()

    # ------------------------------------------------------------------
    # Escena
    # ------------------------------------------------------------------
    def _setup_scene(self) -> None:
        p = self.plotter
        p.set_background(C["viewport"], top="#ffffff")
        try:
            p.enable_anti_aliasing("fxaa")
        except Exception:
            pass
        self._add_orientation()

    def _add_orientation(self) -> None:
        try:
            self.plotter.add_axes(
                color=C["text_soft"], x_color="#c0392b", y_color="#1a7f4b",
                z_color="#1668b3", line_width=2, labels_off=False)
        except Exception:
            pass

    def clear(self) -> None:
        self.plotter.clear()
        self._actors.clear()
        self._add_orientation()

    def build(
        self,
        holes: Sequence[Hole],
        topography: Optional[np.ndarray] = None,
        free_face: Optional[np.ndarray] = None,
        show_labels: bool = False,
        show_bench: bool = True,
        reset_camera: bool = True,
    ) -> None:
        """Reconstruye la escena completa a partir del diseno."""
        keep = list(self._selection)
        self.clear()
        self._holes = list(holes)
        if not self._holes:
            self.plotter.render()
            return

        self._collars = np.array([h.collar for h in self._holes], float)

        if topography is not None and len(topography) >= 3:
            self._add_topography(topography)
        if show_bench:
            self._add_bench_reference()
        if free_face is not None and len(free_face) >= 2:
            self._add_free_face(free_face)

        self._add_holes()
        self.set_theme(self._theme)
        self.set_labels_visible(show_labels)
        self._add_grid()

        # Conserva la seleccion que siga existiendo tras regenerar la malla.
        alive = {h.hid for h in self._holes}
        self._selection = [hid for hid in keep if hid in alive]
        self._draw_selection()

        if reset_camera:
            self.reset_camera()
        self.plotter.render()

    def _add_topography(self, points: np.ndarray) -> None:
        cloud = pv.PolyData(np.asarray(points, float))
        try:
            surf = cloud.delaunay_2d(alpha=0.0)
        except Exception:
            return
        self._actors["topo"] = self.plotter.add_mesh(
            surf, color="#c9d3c2", opacity=0.55, smooth_shading=True,
            show_edges=False, name="topo", ambient=0.35, diffuse=0.7)
        self._actors["topo_wire"] = self.plotter.add_mesh(
            surf, style="wireframe", color="#9fae97", opacity=0.28,
            line_width=1, name="topo_wire")

    def _add_bench_reference(self) -> None:
        toes = np.array([h.toe for h in self._holes], float)
        z = float(np.percentile(toes[:, 2], 50))
        lo = self._collars.min(axis=0) - 8.0
        hi = self._collars.max(axis=0) + 8.0
        plane = pv.Plane(center=((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, z),
                         direction=(0, 0, 1),
                         i_size=(hi[0] - lo[0]), j_size=(hi[1] - lo[1]))
        self._actors["bench"] = self.plotter.add_mesh(
            plane, color="#dfe4e8", opacity=0.35, name="bench", show_edges=False)

    def _add_free_face(self, face: np.ndarray) -> None:
        pts = np.asarray(face, float)
        if pts.shape[1] == 2:
            z_top = float(self._collars[:, 2].max())
            pts = np.column_stack([pts, np.full(len(pts), z_top)])

        toes = np.array([h.toe for h in self._holes], float)
        z_bot = float(toes[:, 2].min())
        bottom = pts.copy()
        bottom[:, 2] = z_bot

        verts = np.vstack([pts, bottom])
        n = len(pts)
        faces: List[int] = []
        for i in range(n - 1):
            faces += [4, i, i + 1, n + i + 1, n + i]
        if faces:
            mesh = pv.PolyData(verts, np.array(faces))
            self._actors["face"] = self.plotter.add_mesh(
                mesh, color=C["accent"], opacity=0.14, name="free_face", show_edges=False)
            self._actors["face_edge"] = self.plotter.add_mesh(
                pv.lines_from_points(pts), color=C["accent"], line_width=3, name="face_edge")

    def _add_holes(self) -> None:
        """Dibuja taco, aire y cada plataforma de carga de todos los taladros."""
        stem_blocks: List[pv.PolyData] = []
        air_blocks: List[pv.PolyData] = []
        self._charge_meshes = []
        self._charge_index = []

        for idx, h in enumerate(self._holes):
            r_vis = self._hole_radius(h)
            for d in h.decks:
                p0 = h.point_from_toe(d.from_toe_m)
                p1 = h.point_from_toe(d.from_toe_m + d.length_m)
                cyl = pv.Cylinder(center=(p0 + p1) / 2.0, direction=h.axis,
                                  radius=r_vis, height=max(d.length_m, 0.05),
                                  resolution=16, capping=True)
                kind = d.kind.value if hasattr(d.kind, "value") else str(d.kind)
                if kind == "Carga":
                    self._charge_meshes.append(cyl)
                    self._charge_index.append(idx)
                elif kind == "Aire":
                    air_blocks.append(cyl)
                else:
                    stem_blocks.append(cyl)

        if stem_blocks:
            self._actors["stem"] = self.plotter.add_mesh(
                _merge(stem_blocks), color="#9aa5b1", opacity=0.9,
                name="stemming", smooth_shading=True)
        if air_blocks:
            self._actors["air"] = self.plotter.add_mesh(
                _merge(air_blocks), color="#e8edf2", opacity=0.45,
                name="airdeck", smooth_shading=True)

        cloud = pv.PolyData(self._collars)
        self._actors["collars"] = self.plotter.add_mesh(
            cloud, color=C["text"], point_size=7, render_points_as_spheres=True,
            name="collars")

    def _hole_radius(self, hole: Hole) -> float:
        return max(hole.diameter_m / 2.0 * 3.0, 0.16)

    def _add_grid(self) -> None:
        try:
            self.plotter.show_grid(
                color=C["grid"], font_size=9, location="outer", grid="back",
                xtitle="Este (m)", ytitle="Norte (m)", ztitle="Cota (m)")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Tematizacion
    # ------------------------------------------------------------------
    def set_theme(self, theme: str) -> None:
        """Colorea las cargas segun la variable seleccionada."""
        self._theme = theme if theme in THEMES else "Tipo de taladro"
        if not self._holes or not self._charge_meshes:
            return

        for key in list(self._actors):
            if key.startswith("charge"):
                self.plotter.remove_actor(self._actors[key], render=False)
                del self._actors[key]
        try:
            self.plotter.remove_scalar_bar()
        except Exception:
            pass

        attr, _unit = THEMES[self._theme]
        if attr == "type":
            blocks: Dict[str, List[pv.PolyData]] = {}
            for mesh, idx in zip(self._charge_meshes, self._charge_index):
                blocks.setdefault(self._holes[idx].hole_type, []).append(mesh)
            for htype, meshes in blocks.items():
                self._actors[f"charge_{htype}"] = self.plotter.add_mesh(
                    _merge(meshes), color=HOLE_TYPE_COLORS.get(htype, "#c0392b"),
                    name=f"charge_{htype}", smooth_shading=True)
        else:
            values = np.array([getattr(self._holes[i], attr, 0.0)
                               for i in self._charge_index], float)
            mesh = _merge(self._charge_meshes, scalars=values, name=self._theme)
            self._actors["charge"] = self.plotter.add_mesh(
                mesh, scalars=self._theme, cmap="viridis", name="charge",
                smooth_shading=True,
                scalar_bar_args={
                    "title": self._theme, "color": C["text"], "n_labels": 5,
                    "vertical": True, "position_x": 0.88, "position_y": 0.12,
                    "width": 0.05, "height": 0.55, "title_font_size": 11,
                    "label_font_size": 10, "font_family": "arial",
                })
        self.plotter.render()

    def set_labels_visible(self, visible: bool) -> None:
        self._labels_visible = visible
        if self._actors.get("labels") is not None:
            self.plotter.remove_actor(self._actors["labels"], render=False)
            self._actors["labels"] = None
        if visible and self._holes:
            self._actors["labels"] = self.plotter.add_point_labels(
                self._collars + np.array([0.0, 0.0, 1.2]),
                [h.hid for h in self._holes], font_size=11, text_color=C["text"],
                shape=None, always_visible=True, point_size=1, name="labels", bold=False)
        self.plotter.render()

    def set_z_exaggeration(self, factor: float) -> None:
        """Exagera la escala vertical, util en bancos bajos y taludes tendidos."""
        self._z_scale = max(0.2, float(factor))
        try:
            self.plotter.set_scale(1.0, 1.0, self._z_scale)
            self.plotter.render()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Campo de energia
    # ------------------------------------------------------------------
    def show_energy_field(self, field, contours: int = 6, opacity: float = 0.35) -> None:
        self.hide_energy_field()
        if field is None:
            return
        grid = pv.ImageData(dimensions=field.dims, spacing=(field.spacing,) * 3,
                            origin=tuple(field.origin))
        grid["Energia (MJ/m3)"] = field.flat
        active = field.values[field.values > 0]
        if active.size == 0:
            return
        vmax = float(np.percentile(active, 97))
        try:
            iso = grid.contour(isosurfaces=np.linspace(vmax * 0.15, vmax, contours).tolist(),
                               scalars="Energia (MJ/m3)")
        except Exception:
            return
        if iso.n_points == 0:
            return
        self._actors["energy"] = self.plotter.add_mesh(
            iso, scalars="Energia (MJ/m3)", cmap="inferno", opacity=opacity,
            name="energy_field", smooth_shading=True,
            scalar_bar_args={"title": "Energia (MJ/m3)", "color": C["text"],
                             "vertical": True, "position_x": 0.02, "position_y": 0.12,
                             "width": 0.05, "height": 0.55, "n_labels": 5,
                             "title_font_size": 11, "label_font_size": 10})
        self.plotter.render()

    def hide_energy_field(self) -> None:
        if self._actors.get("energy") is not None:
            self.plotter.remove_actor(self._actors["energy"], render=False)
            self._actors["energy"] = None
            self.plotter.render()

    # ------------------------------------------------------------------
    # Interaccion
    # ------------------------------------------------------------------
    def _install_interaction(self) -> None:
        """Observadores de raton y teclado sobre el interactor de VTK."""
        iren = self._interactor()
        if iren is None:
            return

        # Prioridad alta pero sin abortar el evento: el estilo de camara lo
        # sigue recibiendo, de modo que arrastrar con el izquierdo rota.
        iren.AddObserver("LeftButtonPressEvent", self._on_left_press, 10.0)
        iren.AddObserver("LeftButtonReleaseEvent", self._on_left_release, 10.0)

        self.set_nav_mode(NavMode.ORBITA)
        self._install_keys()

    def _interactor(self):
        try:
            return self.plotter.iren.interactor
        except Exception:
            return None

    def _install_keys(self) -> None:
        """Atajos de camara sobre el propio visor."""
        bindings: Dict[str, Callable[[], None]] = {
            "Up": lambda: self.orbit(0.0, 8.0),
            "Down": lambda: self.orbit(0.0, -8.0),
            "Left": lambda: self.orbit(-8.0, 0.0),
            "Right": lambda: self.orbit(8.0, 0.0),
            "plus": lambda: self.dolly(1.15),
            "minus": lambda: self.dolly(1 / 1.15),
            "f": self.focus_on_selection,
            "r": self.reset_camera,
            "1": self.view_iso,
            "2": self.view_top,
            "3": lambda: self.view_side("north"),
            "4": lambda: self.view_side("east"),
            "p": self.toggle_parallel_projection,
            "Escape": self.clear_selection,
        }
        for key, fn in bindings.items():
            try:
                self.plotter.add_key_event(key, fn)
            except Exception:
                pass

    # -- estilo de navegacion ---------------------------------------------
    def set_nav_mode(self, mode: NavMode | str) -> None:
        """Cambia el estilo de interaccion de la camara."""
        mode = NavMode(mode) if not isinstance(mode, NavMode) else mode
        self._nav_mode = mode
        p = self.plotter
        try:
            if mode is NavMode.TERRENO:
                p.enable_terrain_style(mouse_wheel_zooms=True, shift_pans=True)
            elif mode is NavMode.JOYSTICK:
                p.enable_joystick_style()
            elif mode is NavMode.PLANTA:
                p.enable_image_style()
                p.enable_parallel_projection()
                self.view_top()
            else:
                p.enable_trackball_style()
            # Solo la vista en planta impone proyeccion ortografica; al salir
            # de ella se recupera la que el usuario tenia elegida.
            if mode is not NavMode.PLANTA:
                if self._user_parallel:
                    p.enable_parallel_projection()
                else:
                    p.disable_parallel_projection()
        except Exception:
            pass
        self.status_message.emit(f"Navegacion: {mode.value}")

    def nav_mode(self) -> NavMode:
        return self._nav_mode

    def toggle_parallel_projection(self) -> None:
        if self.is_parallel_projection():
            self.plotter.disable_parallel_projection()
            self._user_parallel = False
            self.status_message.emit("Proyeccion en perspectiva")
        else:
            self.plotter.enable_parallel_projection()
            self._user_parallel = True
            self.status_message.emit("Proyeccion paralela (ortografica)")
        self.plotter.render()

    def is_parallel_projection(self) -> bool:
        try:
            return bool(self.plotter.renderer.camera.GetParallelProjection())
        except Exception:
            return False

    # -- movimientos de camara --------------------------------------------
    def orbit(self, azimuth_deg: float = 0.0, elevation_deg: float = 0.0) -> None:
        """Gira la camara alrededor del punto focal, sin desplazarlo."""
        cam = self.plotter.camera
        if azimuth_deg:
            cam.Azimuth(azimuth_deg)
        if elevation_deg:
            cam.Elevation(elevation_deg)
            cam.OrthogonalizeViewUp()
        self.plotter.renderer.ResetCameraClippingRange()
        self.plotter.render()

    def roll(self, degrees: float) -> None:
        self.plotter.camera.Roll(degrees)
        self.plotter.render()

    def dolly(self, factor: float) -> None:
        """Acerca o aleja manteniendo el punto focal."""
        self.plotter.camera.Zoom(factor)
        self.plotter.renderer.ResetCameraClippingRange()
        self.plotter.render()

    def set_spin(self, running: bool, speed_deg: float = 0.6) -> None:
        """Rotacion automatica continua alrededor del punto focal."""
        self._spin_speed = speed_deg
        if running:
            self._spin_timer.start(33)
            self.status_message.emit("Rotacion automatica activada")
        else:
            self._spin_timer.stop()

    def is_spinning(self) -> bool:
        return self._spin_timer.isActive()

    def _spin_step(self) -> None:
        self.plotter.camera.Azimuth(getattr(self, "_spin_speed", 0.6))
        self.plotter.render()

    def focus_on_selection(self) -> None:
        """Centra la camara en la seleccion para orbitar alrededor de ella."""
        holes = self.selected_holes()
        if not holes:
            self.reset_camera()
            return
        pts = np.vstack([[h.collar, h.toe] for h in holes]).reshape(-1, 3)
        center = pts.mean(axis=0)
        radius = max(float(np.linalg.norm(pts - center, axis=1).max()), 3.0)

        cam = self.plotter.camera
        pos = np.array(cam.GetPosition(), float)
        focal = np.array(cam.GetFocalPoint(), float)
        direction = pos - focal
        norm = np.linalg.norm(direction)
        direction = direction / norm if norm > 1e-6 else np.array([1.0, -1.0, 0.8])

        cam.SetFocalPoint(*center)
        cam.SetPosition(*(center + direction * radius * 3.2))
        self.plotter.renderer.ResetCameraClippingRange()
        self.plotter.render()
        self.status_message.emit(
            f"Camara centrada en {len(holes)} taladro(s); el giro ocurre alrededor de la seleccion")

    def reset_camera(self) -> None:
        self.plotter.reset_camera()
        self.plotter.render()

    def view_iso(self) -> None:
        self.plotter.view_isometric()
        self.plotter.render()

    def view_top(self) -> None:
        self.plotter.view_xy()
        self.plotter.render()

    def view_side(self, side: str = "north") -> None:
        """Vistas ortogonales nombradas por el punto cardinal desde el que se mira."""
        actions = {
            "north": self.plotter.view_yz,
            "south": lambda: self.plotter.view_yz(negative=True),
            "east": self.plotter.view_xz,
            "west": lambda: self.plotter.view_xz(negative=True),
        }
        actions.get(side, self.plotter.view_xz)()
        self.plotter.render()

    def set_standard_view(self, name: str) -> None:
        key = STANDARD_VIEWS.get(name, "iso")
        if key == "iso":
            self.view_iso()
        elif key == "top":
            self.view_top()
        else:
            self.view_side(key)

    def zoom_to_selection(self) -> None:
        holes = self.selected_holes()
        if not holes:
            self.reset_camera()
            return
        pts = np.vstack([[h.collar, h.toe] for h in holes]).reshape(-1, 3)
        pad = 4.0
        bounds = (pts[:, 0].min() - pad, pts[:, 0].max() + pad,
                  pts[:, 1].min() - pad, pts[:, 1].max() + pad,
                  pts[:, 2].min() - pad, pts[:, 2].max() + pad)
        self.plotter.reset_camera(bounds=bounds)
        self.plotter.render()

    def screenshot(self, path: str, scale: int = 2) -> None:
        self.plotter.screenshot(path, scale=scale)

    # ------------------------------------------------------------------
    # Seleccion
    # ------------------------------------------------------------------
    def _on_left_press(self, _obj, _event) -> None:
        iren = self._interactor()
        if iren is None:
            return
        self._press_pos = tuple(iren.GetEventPosition())
        self._press_time = time.monotonic()

    def _on_left_release(self, _obj, _event) -> None:
        iren = self._interactor()
        if iren is None or not self._holes:
            return
        x, y = iren.GetEventPosition()
        dx = x - self._press_pos[0]
        dy = y - self._press_pos[1]

        # Si el puntero se movio, fue una rotacion: no se toca la seleccion.
        if (dx * dx + dy * dy) > _CLICK_PIXEL_TOLERANCE ** 2:
            return
        if time.monotonic() - self._press_time > _CLICK_TIME_TOLERANCE:
            return

        hid = self._pick_hole_at(x, y)
        additive = bool(iren.GetControlKey())
        toggle = bool(iren.GetShiftKey())

        if hid is None:
            if not additive and not toggle:
                self.clear_selection()
            return

        now = time.monotonic()
        if hid == self._last_click_hid and (now - self._last_click_time) < 0.35:
            self.hole_activated.emit(hid)          # doble clic
        self._last_click_hid = hid
        self._last_click_time = now

        if toggle:
            selection = list(self._selection)
            selection.remove(hid) if hid in selection else selection.append(hid)
        elif additive:
            selection = list(self._selection)
            if hid not in selection:
                selection.append(hid)
        else:
            selection = [hid]
        self.set_selection(selection)

    def _pick_hole_at(self, x: int, y: int) -> Optional[str]:
        """Taladro bajo el cursor, o ``None`` si se hizo clic en el vacio."""
        picker = vtk.vtkCellPicker()
        picker.SetTolerance(0.006)
        picker.Pick(x, y, 0, self.plotter.renderer)
        if picker.GetActor() is None:
            return None
        point = np.array(picker.GetPickPosition(), float)
        return self._nearest_hole(point)

    def _nearest_hole(self, point: np.ndarray, max_distance: float = 4.0) -> Optional[str]:
        """Taladro cuyo eje pasa mas cerca del punto indicado."""
        best_hid, best_d = None, float("inf")
        for h in self._holes:
            d = _point_segment_distance(point, h.collar, h.toe)
            if d < best_d:
                best_hid, best_d = h.hid, d
        return best_hid if best_d <= max_distance else None

    def set_selection(self, hids: Sequence[str], notify: bool = True) -> None:
        alive = {h.hid for h in self._holes}
        self._selection = [hid for hid in dict.fromkeys(hids) if hid in alive]
        self._draw_selection()
        if notify:
            self.selection_changed.emit(list(self._selection))

    def clear_selection(self) -> None:
        self.set_selection([])

    def select_all(self) -> None:
        self.set_selection([h.hid for h in self._holes])

    def invert_selection(self) -> None:
        current = set(self._selection)
        self.set_selection([h.hid for h in self._holes if h.hid not in current])

    def select_by(self, predicate: Callable[[Hole], bool]) -> None:
        self.set_selection([h.hid for h in self._holes if predicate(h)])

    def selection(self) -> List[str]:
        return list(self._selection)

    def selected_holes(self) -> List[Hole]:
        chosen = set(self._selection)
        return [h for h in self._holes if h.hid in chosen]

    def highlight(self, hid: str) -> None:
        """Selecciona un unico taladro (llamada desde otros paneles)."""
        self.set_selection([hid], notify=False)

    def _draw_selection(self) -> None:
        """Dibuja el resaltado de los taladros seleccionados."""
        for key in ("selection", "selection_pts"):
            if self._actors.get(key) is not None:
                self.plotter.remove_actor(self._actors[key], render=False)
                self._actors[key] = None
        if not self._selection:
            self.plotter.render()
            return

        holes = self.selected_holes()
        lines = [pv.Tube(pointa=h.collar + np.array([0.0, 0.0, 1.8]), pointb=h.toe,
                         radius=self._hole_radius(h) * 1.55, n_sides=18)
                 for h in holes]
        if lines:
            self._actors["selection"] = self.plotter.add_mesh(
                _merge(lines), color="#f0a202", opacity=0.45, name="selection",
                smooth_shading=True)
        tops = np.array([h.collar for h in holes], float)
        self._actors["selection_pts"] = self.plotter.add_mesh(
            pv.PolyData(tops), color="#f0a202", point_size=13,
            render_points_as_spheres=True, name="selection_pts")
        self.plotter.render()

    # -- seleccion por ventana --------------------------------------------
    def set_box_selection(self, enabled: bool) -> None:
        """Activa el rectangulo de seleccion sobre el visor."""
        if enabled:
            self._band.setGeometry(self.widget.rect())
            self._band.show()
            self._band.raise_()
            self._band.setFocus()
            self.status_message.emit(
                "Seleccion por ventana: arrastre un rectangulo. "
                "Ctrl agrega, Shift quita, Esc cancela.")
        else:
            self._band.hide()

    def is_box_selection(self) -> bool:
        return self._band.isVisible()

    def _on_band_finished(self, rect: QRect, additive: bool, subtractive: bool) -> None:
        inside = self._holes_in_screen_rect(rect)
        if additive:
            selection = list(dict.fromkeys(self._selection + inside))
        elif subtractive:
            drop = set(inside)
            selection = [hid for hid in self._selection if hid not in drop]
        else:
            selection = inside
        self.set_selection(selection)
        self.set_box_selection(False)
        self.status_message.emit(f"{len(selection)} taladro(s) seleccionados")

    def _holes_in_screen_rect(self, rect: QRect) -> List[str]:
        """Proyecta collares y fondos a pantalla y devuelve los del rectangulo."""
        renderer = self.plotter.renderer
        height = self.widget.height()
        found: List[str] = []
        for h in self._holes:
            for world in (h.collar, (h.collar + h.toe) / 2.0):
                renderer.SetWorldPoint(world[0], world[1], world[2], 1.0)
                renderer.WorldToDisplay()
                dx, dy, _dz = renderer.GetDisplayPoint()
                # VTK mide desde abajo; Qt desde arriba.
                if rect.contains(QPoint(int(dx), int(height - dy))):
                    found.append(h.hid)
                    break
        return found

    # ------------------------------------------------------------------
    # Animacion de la secuencia
    # ------------------------------------------------------------------
    def start_animation(self, speed: float = 1.0, fps: int = 30) -> None:
        if not self._holes:
            return
        self._anim_speed = max(speed, 0.01)
        self._anim_end = max(h.delay_actual_ms for h in self._holes) + 220.0
        self._anim_t = 0.0
        self._anim_step = 1000.0 / max(fps, 1) * self._anim_speed
        self._timer.start(int(1000 / max(fps, 1)))

    def stop_animation(self) -> None:
        self._timer.stop()
        self.set_theme(self._theme)
        self._draw_selection()

    def is_animating(self) -> bool:
        return self._timer.isActive()

    def _tick(self) -> None:
        self._anim_t += self._anim_step
        self.frame_changed.emit(self._anim_t)
        self._paint_fired(self._anim_t)
        if self._anim_t >= self._anim_end:
            self._timer.stop()
            self.animation_finished.emit()

    def _paint_fired(self, t_ms: float) -> None:
        if not self._charge_meshes:
            return
        state = np.empty(len(self._charge_index), float)
        for k, idx in enumerate(self._charge_index):
            dt = t_ms - self._holes[idx].delay_actual_ms
            state[k] = 0.0 if dt < 0 else (1.0 if dt < 120.0 else 0.5)

        for key in list(self._actors):
            if key.startswith("charge"):
                self.plotter.remove_actor(self._actors[key], render=False)
                del self._actors[key]
        try:
            self.plotter.remove_scalar_bar()
        except Exception:
            pass

        mesh = _merge(self._charge_meshes, scalars=state, name="estado")
        self._actors["charge"] = self.plotter.add_mesh(
            mesh, scalars="estado", cmap=["#b4bdc6", "#f0a202", "#c0392b"],
            clim=[0.0, 1.0], name="charge", show_scalar_bar=False, smooth_shading=True)
        self.plotter.render()


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def _point_segment_distance(p: np.ndarray, a: np.ndarray, b: np.ndarray) -> float:
    """Distancia de un punto al segmento ``ab``."""
    ab = b - a
    denom = float(ab @ ab)
    if denom < 1e-12:
        return float(np.linalg.norm(p - a))
    t = float(np.clip((p - a) @ ab / denom, 0.0, 1.0))
    return float(np.linalg.norm(p - (a + t * ab)))


def _merge(meshes: Sequence[pv.PolyData], scalars: Optional[np.ndarray] = None,
           name: str = "valor") -> pv.PolyData:
    """Une mallas en una sola, propagando un escalar por bloque si se indica."""
    if scalars is not None:
        blocks = []
        for mesh, value in zip(meshes, scalars):
            m = mesh.copy()
            m[name] = np.full(m.n_points, float(value))
            blocks.append(m)
        meshes = blocks
    out = meshes[0].copy()
    for m in meshes[1:]:
        out = out.merge(m)
    return out
