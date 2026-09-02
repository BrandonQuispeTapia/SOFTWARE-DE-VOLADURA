"""Visor 3D de la voladura.

Envuelve el interactor de VTK/PyVista y concentra la construccion de la escena
—terreno, cara libre, columnas de carga, campo de energia— junto con la
navegacion de camara y la seleccion interactiva de taladros.

Dos decisiones de interaccion merecen explicacion:

*Seleccion sin robar el boton izquierdo.* ``enable_point_picking`` de PyVista se
apropia del boton izquierdo y deja la escena sin rotacion. Aqui el picking son
observadores propios que no abortan el evento, de modo que el estilo de camara
lo sigue recibiendo. Un clic se distingue de un arrastre por el desplazamiento
del puntero, y el disparador —un clic o dos— es configurable.

El gesto se cierra escuchando ``EndInteractionEvent`` del estilo y no
``LeftButtonReleaseEvent`` del interactor: al empezar a rotar, el estilo de VTK
toma el foco de los eventos y el de soltar el boton ya no llega a observadores
externos.

*Camara de tornamesa.* El estilo de VTK gira libremente y, al pasar por encima
del cenit, el vector de vista queda invertido y el modelo aparece de cabeza.
En vez de reimplementar la navegacion, se corrige la camara despues de cada
interaccion: la elevacion se acota y el eje Z se fuerza hacia arriba, con lo que
el giro se comporta como una tornamesa y nunca se voltea.
"""

from __future__ import annotations

import math
import time
from enum import Enum
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pyvista as pv
import vtk
from pyvistaqt import QtInteractor
from PySide6.QtCore import QObject, QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ..core.models import HOLE_TYPE_COLORS, DirectionVector, Hole
from .settings import Settings, settings as global_settings
from .theme import C

#: Variables por las que se puede tematizar la malla.
THEMES: Dict[str, Tuple[str, str]] = {
    "Tipo de taladro": ("type", ""),
    "Retardo (ms)": ("delay_ms", "ms"),
    "Factor de potencia (kg/m3)": ("powder_factor", "kg/m3"),
    "Carga (kg)": ("charge_kg", "kg"),
    "Energia (MJ)": ("energy_mj", "MJ"),
    "Burden real (m)": ("burden_real_m", "m"),
    "Burden de alivio (m)": ("relief_burden_m", "m"),
    "Espaciamiento real (m)": ("spacing_real_m", "m"),
    "Volumen (m3)": ("volume_m3", "m3"),
    "X50 previsto (cm)": ("x50_cm", "cm"),
    "Uniformidad n": ("uniformity_n", ""),
    "Confinamiento": ("confinement", ""),
}


class NavMode(str, Enum):
    """Estilo de interaccion de la camara."""

    TORNAMESA = "Tornamesa (sin volteo)"
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

#: Contenido posible de las etiquetas de taladro.
_LABEL_BUILDERS: Dict[str, Callable[[Hole], str]] = {
    "Identificador": lambda h: h.hid,
    "Retardo": lambda h: f"{h.delay_ms:,.0f} ms",
    "Carga": lambda h: f"{h.charge_kg:,.0f} kg",
    "Identificador y retardo": lambda h: f"{h.hid}  {h.delay_ms:,.0f} ms",
}

#: Proporciones de la flecha del vector de direccion. En PyVista los radios son
#: fracciones del largo unitario, asi que la escala los multiplica junto con el
#: resto: darlos en metros produce una flecha desproporcionada.
_ARROW_SHAPE = {"tip_length": 0.16, "tip_radius": 0.035, "shaft_radius": 0.012,
                "tip_resolution": 24, "shaft_resolution": 24}


# ---------------------------------------------------------------------------
# Superposicion para la seleccion por ventana
# ---------------------------------------------------------------------------


class _RubberBand(QWidget):
    """Capa transparente que dibuja el rectangulo de seleccion por ventana."""

    finished = Signal(QRect, bool, bool)   # (rect, aditiva, sustractiva)
    cancelled = Signal()

    def __init__(self, parent: QWidget):
        super().__init__(parent)
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
        rect = QRect(self._origin, self._current).normalized()
        accent = QColor(C["accent"])
        fill = QColor(accent)
        fill.setAlpha(38)
        painter.fillRect(rect, fill)
        painter.setPen(QPen(accent, 1, Qt.PenStyle.DashLine))
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
    scene_rebuild_requested = Signal()
    direction_vector_placed = Signal(object)   # DirectionVector
    placement_changed = Signal(bool)

    def __init__(self, parent=None, store: Optional[Settings] = None):
        super().__init__(parent)
        self.cfg = store or global_settings()
        self.plotter = QtInteractor(parent)
        self.widget = self.plotter.interactor

        self._holes: List[Hole] = []
        self._collars: np.ndarray = np.empty((0, 3))
        self._actors: Dict[str, object] = {}
        self._charge_meshes: List[pv.PolyData] = []
        self._charge_index: List[int] = []
        self._labels_visible = bool(self.cfg.get("holes.labels_on_start"))
        self._theme = "Tipo de taladro"
        self._selection: List[str] = []
        self._z_scale = float(self.cfg.get("viewer.z_exaggeration"))
        self._nav_mode = NavMode(self.cfg.get("interaction.nav_mode"))
        self._user_parallel = bool(self.cfg.get("viewer.parallel_projection"))
        self._turntable = True

        # deteccion de clic frente a arrastre
        self._press_pos: Tuple[int, int] = (0, 0)
        self._press_time = 0.0
        self._left_down = False
        self._last_click_time = 0.0
        self._last_click_pos: Tuple[int, int] = (0, 0)
        self._last_select_time = 0.0

        # colocacion interactiva del vector de direccion
        self._placement_stage = 0          # 0 inactivo, 1 origen, 2 punta
        self._placement_origin: Optional[np.ndarray] = None
        self._placement_observer = None

        # animaciones
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._anim_t = 0.0
        self._anim_step = 1.0
        self._anim_end = 0.0

        self._spin_timer = QTimer(self)
        self._spin_timer.timeout.connect(self._spin_step)

        self._band = _RubberBand(self.widget)
        self._band.finished.connect(self._on_band_finished)
        self._band.cancelled.connect(lambda: self.set_box_selection(False))

        self._setup_scene()
        self._install_interaction()
        self.cfg.changed.connect(self._on_setting_changed)

    # ------------------------------------------------------------------
    # Escena
    # ------------------------------------------------------------------
    def _setup_scene(self) -> None:
        p = self.plotter
        cfg = self.cfg
        bottom = str(cfg.get("viewer.background_bottom"))
        top = str(cfg.get("viewer.background_top"))
        p.set_background(bottom, top=top if cfg.get("viewer.gradient") else None)

        aa = str(cfg.get("viewer.antialiasing"))
        try:
            if aa == "Ninguno":
                p.disable_anti_aliasing()
            else:
                p.enable_anti_aliasing(aa.lower())
        except Exception:
            pass
        if cfg.get("viewer.depth_peeling"):
            try:
                p.enable_depth_peeling()
            except Exception:
                pass
        if self._user_parallel:
            try:
                p.enable_parallel_projection()
            except Exception:
                pass
        self._add_orientation()

    def _add_orientation(self) -> None:
        if not self.cfg.get("viewer.show_axes"):
            return
        try:
            self.plotter.add_axes(
                color=C["text_soft"], x_color="#c0392b", y_color="#1a7f4b",
                z_color="#1668b3", line_width=2, labels_off=False)
        except Exception:
            pass
        if self.cfg.get("viewer.show_orientation_cube"):
            try:
                self.plotter.add_camera_orientation_widget()
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
        show_labels: Optional[bool] = None,
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
        self.set_labels_visible(self._labels_visible if show_labels is None else show_labels)
        self._add_grid()

        # Conserva la seleccion que siga existiendo tras regenerar la malla.
        alive = {h.hid for h in self._holes}
        self._selection = [hid for hid in keep if hid in alive]
        self._draw_selection()

        if reset_camera:
            self.reset_camera()
        self.plotter.render()

    def _add_topography(self, points: np.ndarray) -> None:
        cfg = self.cfg
        cloud = pv.PolyData(np.asarray(points, float))
        try:
            surf = cloud.delaunay_2d(alpha=0.0)
        except Exception:
            return
        self._actors["topo"] = self.plotter.add_mesh(
            surf, color=str(cfg.get("layers.topo_color")),
            opacity=float(cfg.get("layers.topo_opacity")),
            smooth_shading=bool(cfg.get("viewer.smooth_shading")),
            show_edges=False, name="topo", pickable=False,
            ambient=float(cfg.get("viewer.ambient")),
            diffuse=float(cfg.get("viewer.diffuse")))
        if cfg.get("layers.topo_wireframe"):
            self._actors["topo_wire"] = self.plotter.add_mesh(
                surf, style="wireframe", color=str(cfg.get("layers.topo_wire_color")),
                opacity=float(cfg.get("layers.topo_wire_opacity")),
                line_width=1, name="topo_wire", pickable=False)

    def _add_bench_reference(self) -> None:
        margin = float(self.cfg.get("layers.bench_margin"))
        toes = np.array([h.toe for h in self._holes], float)
        z = float(np.percentile(toes[:, 2], 50))
        lo = self._collars.min(axis=0) - margin
        hi = self._collars.max(axis=0) + margin
        plane = pv.Plane(center=((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, z),
                         direction=(0, 0, 1),
                         i_size=(hi[0] - lo[0]), j_size=(hi[1] - lo[1]))
        self._actors["bench"] = self.plotter.add_mesh(
            plane, color=str(self.cfg.get("layers.bench_color")),
            opacity=float(self.cfg.get("layers.bench_opacity")),
            name="bench", show_edges=False, pickable=False)

    def _add_free_face(self, face: np.ndarray) -> None:
        cfg = self.cfg
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
        if not faces:
            return
        color = str(cfg.get("layers.face_color"))
        self._actors["face"] = self.plotter.add_mesh(
            pv.PolyData(verts, np.array(faces)), color=color,
            opacity=float(cfg.get("layers.face_opacity")),
            name="free_face", show_edges=False, pickable=False)
        self._actors["face_edge"] = self.plotter.add_mesh(
            pv.lines_from_points(pts), color=color,
            line_width=int(cfg.get("layers.face_line_width")), name="face_edge",
            pickable=False)

    def _add_holes(self) -> None:
        """Dibuja taco, aire y cada plataforma de carga de todos los taladros."""
        cfg = self.cfg
        resolution = int(cfg.get("holes.resolution"))
        smooth = bool(cfg.get("viewer.smooth_shading"))

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
                                  resolution=resolution, capping=True)
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
                _merge(stem_blocks), color=str(cfg.get("holes.stem_color")),
                opacity=float(cfg.get("holes.stem_opacity")),
                name="stemming", smooth_shading=smooth)
        if air_blocks:
            self._actors["air"] = self.plotter.add_mesh(
                _merge(air_blocks), color=str(cfg.get("holes.air_color")),
                opacity=float(cfg.get("holes.air_opacity")),
                name="airdeck", smooth_shading=smooth)

        if cfg.get("holes.show_collars"):
            self._actors["collars"] = self.plotter.add_mesh(
                pv.PolyData(self._collars), color=str(cfg.get("holes.collar_color")),
                point_size=int(cfg.get("holes.collar_size")),
                render_points_as_spheres=True, name="collars")

    def _hole_radius(self, hole: Hole) -> float:
        factor = float(self.cfg.get("holes.radius_factor"))
        minimum = float(self.cfg.get("holes.radius_min"))
        return max(hole.diameter_m / 2.0 * factor, minimum)

    def _add_grid(self) -> None:
        if not self.cfg.get("viewer.show_grid"):
            return
        try:
            self.plotter.show_grid(
                color=str(self.cfg.get("viewer.grid_color")),
                font_size=int(self.cfg.get("viewer.grid_font_size")),
                location="outer", grid="back",
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

        self._remove_charge_actors()
        attr, _unit = THEMES[self._theme]
        smooth = bool(self.cfg.get("viewer.smooth_shading"))
        opacity = float(self.cfg.get("holes.charge_opacity"))
        colors = self.cfg.hole_colors()

        if attr == "type":
            blocks: Dict[str, List[pv.PolyData]] = {}
            for mesh, idx in zip(self._charge_meshes, self._charge_index):
                blocks.setdefault(self._holes[idx].hole_type, []).append(mesh)
            for htype, meshes in blocks.items():
                self._actors[f"charge_{htype}"] = self.plotter.add_mesh(
                    _merge(meshes),
                    color=colors.get(htype, HOLE_TYPE_COLORS.get(htype, "#c0392b")),
                    name=f"charge_{htype}", smooth_shading=smooth, opacity=opacity)
        else:
            values = np.array([getattr(self._holes[i], attr, 0.0)
                               for i in self._charge_index], float)
            mesh = _merge(self._charge_meshes, scalars=values, name=self._theme)
            self._actors["charge"] = self.plotter.add_mesh(
                mesh, scalars=self._theme, cmap="viridis", name="charge",
                smooth_shading=smooth, opacity=opacity,
                scalar_bar_args={
                    "title": self._theme, "color": C["text"], "n_labels": 5,
                    "vertical": True, "position_x": 0.88, "position_y": 0.12,
                    "width": 0.05, "height": 0.55, "title_font_size": 11,
                    "label_font_size": 10, "font_family": "arial",
                })
        self.plotter.render()

    def _remove_charge_actors(self) -> None:
        for key in [k for k in self._actors if k.startswith("charge")]:
            self.plotter.remove_actor(self._actors[key], render=False)
            del self._actors[key]
        try:
            self.plotter.remove_scalar_bar()
        except Exception:
            pass

    def set_labels_visible(self, visible: bool) -> None:
        self._labels_visible = visible
        if self._actors.get("labels") is not None:
            self.plotter.remove_actor(self._actors["labels"], render=False)
            self._actors["labels"] = None
        if visible and self._holes:
            cfg = self.cfg
            builder = _LABEL_BUILDERS.get(str(cfg.get("holes.label_content")),
                                          _LABEL_BUILDERS["Identificador"])
            offset = np.array([0.0, 0.0, float(cfg.get("holes.label_offset"))])
            self._actors["labels"] = self.plotter.add_point_labels(
                self._collars + offset, [builder(h) for h in self._holes],
                font_size=int(cfg.get("holes.label_font_size")),
                text_color=str(cfg.get("holes.label_color")),
                shape=None, always_visible=True, point_size=1,
                name="labels", bold=False)
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
    def show_energy_field(self, field) -> None:
        self.hide_energy_field()
        if field is None:
            return
        cfg = self.cfg
        grid = pv.ImageData(dimensions=field.dims, spacing=(field.spacing,) * 3,
                            origin=tuple(field.origin))
        grid["Energia (MJ/m3)"] = field.flat
        active = field.values[field.values > 0]
        if active.size == 0:
            return
        vmax = float(np.percentile(active, 97))
        levels = np.linspace(vmax * 0.15, vmax, int(cfg.get("energy.contours")))
        try:
            iso = grid.contour(isosurfaces=levels.tolist(), scalars="Energia (MJ/m3)")
        except Exception:
            return
        if iso.n_points == 0:
            return
        self._actors["energy"] = self.plotter.add_mesh(
            iso, scalars="Energia (MJ/m3)", cmap=str(cfg.get("energy.colormap")),
            opacity=float(cfg.get("energy.opacity")), name="energy_field",
            smooth_shading=bool(cfg.get("viewer.smooth_shading")), pickable=False,
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
        # Respaldo para los estilos que no capturan el foco del raton.
        iren.AddObserver("LeftButtonReleaseEvent", self._on_left_release, 10.0)

        self.set_nav_mode(self._nav_mode)
        self._install_keys()

    def _interactor(self):
        try:
            return self.plotter.iren.interactor
        except Exception:
            return None

    def _install_keys(self) -> None:
        """Atajos de camara sobre el propio visor."""
        step = lambda: float(self.cfg.get("interaction.orbit_step"))
        bindings: Dict[str, Callable[[], None]] = {
            "Up": lambda: self.orbit(0.0, step()),
            "Down": lambda: self.orbit(0.0, -step()),
            "Left": lambda: self.orbit(-step(), 0.0),
            "Right": lambda: self.orbit(step(), 0.0),
            "plus": lambda: self.dolly(1.15),
            "minus": lambda: self.dolly(1 / 1.15),
            "f": self.focus_on_selection,
            "r": self.reset_camera,
            "1": self.view_iso,
            "2": self.view_top,
            "3": lambda: self.view_side("north"),
            "4": lambda: self.view_side("east"),
            "p": self.toggle_parallel_projection,
            "Escape": self._on_escape,
        }
        for key, fn in bindings.items():
            try:
                self.plotter.add_key_event(key, fn)
            except Exception:
                pass

    def _on_escape(self) -> None:
        """Escape cancela lo que este en curso antes de vaciar la seleccion."""
        if self._placement_stage > 0:
            self.cancel_vector_placement()
        elif self.is_box_selection():
            self.set_box_selection(False)
        else:
            self.clear_selection()

    # -- restriccion de tornamesa -----------------------------------------
    def _constrain_camera(self, *_args) -> None:
        """Mantiene el eje Z arriba y acota la elevacion tras cada interaccion.

        Sin esto, el estilo de VTK deja pasar la camara por encima del cenit y
        el vector de vista se invierte: el modelo aparece de cabeza. Acotando la
        elevacion y reanclando el eje Z, el giro se comporta como una tornamesa.
        """
        if not self._turntable:
            return
        try:
            cam = self.plotter.renderer.camera
        except Exception:
            return

        focal = np.array(cam.GetFocalPoint(), float)
        pos = np.array(cam.GetPosition(), float)
        d = pos - focal
        radius = float(np.linalg.norm(d))
        if radius < 1e-9:
            return

        limit = float(self.cfg.get("interaction.max_elevation"))
        elevation = math.degrees(math.asin(float(np.clip(d[2] / radius, -1.0, 1.0))))
        if abs(elevation) > limit:
            target = math.copysign(limit, elevation)
            horizontal = d[:2]
            norm = float(np.linalg.norm(horizontal))
            direction = horizontal / norm if norm > 1e-9 else np.array([0.0, -1.0])
            cam.SetPosition(*(focal + np.array([
                direction[0] * radius * math.cos(math.radians(target)),
                direction[1] * radius * math.cos(math.radians(target)),
                radius * math.sin(math.radians(target)),
            ])))

        # El vector de vista se calcula explicitamente en lugar de delegar en
        # OrthogonalizeViewUp: VTK lo deja pendiente hasta la siguiente
        # operacion de camara, y esa correccion diferida hacia saltar la imagen
        # en cuanto el usuario tocaba la escena.
        view = np.array(cam.GetFocalPoint(), float) - np.array(cam.GetPosition(), float)
        length = float(np.linalg.norm(view))
        if length < 1e-9:
            return
        view /= length
        up = np.array([0.0, 0.0, 1.0]) - view * float(view[2])
        norm_up = float(np.linalg.norm(up))
        if norm_up < 1e-6:                       # mirando justo al cenit
            up = np.array([0.0, 1.0, 0.0]) - view * float(view[1])
            norm_up = float(np.linalg.norm(up)) or 1.0
        cam.SetViewUp(*(up / norm_up))

    # -- estilo de navegacion ---------------------------------------------
    def set_nav_mode(self, mode: NavMode | str) -> None:
        """Cambia el estilo de interaccion de la camara."""
        try:
            mode = NavMode(mode) if not isinstance(mode, NavMode) else mode
        except ValueError:
            mode = NavMode.TORNAMESA
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

            # Solo la vista en planta impone proyeccion ortografica; al salir de
            # ella se recupera la que el usuario tenia elegida.
            if mode is not NavMode.PLANTA:
                if self._user_parallel:
                    p.enable_parallel_projection()
                else:
                    p.disable_parallel_projection()
        except Exception:
            pass

        # La tornamesa es el estilo esferico con la camara reanclada tras cada
        # movimiento; el terreno tambien conserva la vertical.
        self._turntable = mode in (NavMode.TORNAMESA, NavMode.TERRENO)
        self._attach_constraint()
        if self._turntable:
            self._constrain_camera()
            self.plotter.render()
        self.status_message.emit(f"Navegacion: {mode.value}")

    def _attach_constraint(self) -> None:
        """Engancha al estilo vigente el corrector de camara y el fin de gesto.

        Cambiar de modo de navegacion sustituye el estilo de VTK, asi que los
        observadores hay que volver a colocarlos sobre el nuevo.
        """
        try:
            style = self.plotter.iren.interactor.GetInteractorStyle()
        except Exception:
            return
        if style is None or getattr(self, "_constraint_style", None) is style:
            return
        try:
            style.AddObserver("InteractionEvent", self._constrain_camera, 5.0)
            style.AddObserver("EndInteractionEvent", self._on_gesture_end, 5.0)
            self._constraint_style = style
        except Exception:
            pass

    def _on_gesture_end(self, _obj=None, _event=None) -> None:
        """Cierra el gesto: resuelve el clic pendiente y luego corrige la camara.

        El orden importa: la seleccion tiene que resolverse contra la vista que
        el usuario tenia delante al pulsar, no contra la que quede despues de
        reanclar la camara.
        """
        if self._left_down:
            self._on_left_release()
        self._constrain_camera()

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
        speed = float(self.cfg.get("interaction.orbit_speed"))
        if self.cfg.get("interaction.invert_y"):
            elevation_deg = -elevation_deg
        cam = self.plotter.camera
        if azimuth_deg:
            cam.Azimuth(azimuth_deg * speed)
        if elevation_deg:
            cam.Elevation(elevation_deg * speed)
        self._constrain_camera()
        if not self._turntable:
            cam.OrthogonalizeViewUp()
        self.plotter.renderer.ResetCameraClippingRange()
        self.plotter.render()

    def roll(self, degrees: float) -> None:
        if self._turntable:
            self.status_message.emit(
                "En modo tornamesa el encuadre queda anclado; use «Orbita libre» para rotarlo.")
            return
        self.plotter.camera.Roll(degrees)
        self.plotter.render()

    def dolly(self, factor: float) -> None:
        """Acerca o aleja manteniendo el punto focal."""
        speed = float(self.cfg.get("interaction.zoom_speed"))
        self.plotter.camera.Zoom(1.0 + (factor - 1.0) * speed)
        self.plotter.renderer.ResetCameraClippingRange()
        self.plotter.render()

    def set_spin(self, running: bool) -> None:
        """Rotacion automatica continua alrededor del punto focal."""
        if running:
            self._spin_timer.start(33)
            self.status_message.emit("Rotacion automatica activada")
        else:
            self._spin_timer.stop()

    def is_spinning(self) -> bool:
        return self._spin_timer.isActive()

    def _spin_step(self) -> None:
        self.plotter.camera.Azimuth(float(self.cfg.get("interaction.spin_speed")))
        self._constrain_camera()
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
        direction = np.array(cam.GetPosition(), float) - np.array(cam.GetFocalPoint(), float)
        norm = np.linalg.norm(direction)
        direction = direction / norm if norm > 1e-6 else np.array([1.0, -1.0, 0.8])

        cam.SetFocalPoint(*center)
        cam.SetPosition(*(center + direction * radius * 3.2))
        self._constrain_camera()
        self.plotter.renderer.ResetCameraClippingRange()
        self.plotter.render()
        self.status_message.emit(
            f"Camara centrada en {len(holes)} taladro(s); el giro ocurre alrededor de la seleccion")

    def reset_camera(self) -> None:
        self.plotter.reset_camera()
        self._constrain_camera()
        self.plotter.render()

    def view_iso(self) -> None:
        self.plotter.view_isometric()
        self._constrain_camera()
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
        self.plotter.reset_camera(bounds=(
            pts[:, 0].min() - pad, pts[:, 0].max() + pad,
            pts[:, 1].min() - pad, pts[:, 1].max() + pad,
            pts[:, 2].min() - pad, pts[:, 2].max() + pad))
        self._constrain_camera()
        self.plotter.render()

    def screenshot(self, path: str, scale: int = 2) -> None:
        self.plotter.screenshot(path, scale=scale)

    # ------------------------------------------------------------------
    # Seleccion
    # ------------------------------------------------------------------
    def _on_left_press(self, _obj=None, _event=None) -> None:
        iren = self._interactor()
        if iren is None:
            return
        self._press_pos = tuple(iren.GetEventPosition())
        self._press_time = time.monotonic()
        self._left_down = True

    def _on_left_release(self, _obj=None, _event=None) -> None:
        """Decide si el gesto fue un giro o una seleccion."""
        if not self._left_down:
            return
        self._left_down = False

        iren = self._interactor()
        if iren is None or not self._holes:
            return
        x, y = iren.GetEventPosition()
        tolerance = int(self.cfg.get("interaction.drag_tolerance_px"))
        dx, dy = x - self._press_pos[0], y - self._press_pos[1]

        # Si el puntero se movio, fue una rotacion: no se toca la seleccion.
        if (dx * dx + dy * dy) > tolerance * tolerance:
            self._last_click_time = 0.0
            return

        # Colocar el vector manda sobre seleccionar, y basta un clic.
        if self._placement_stage > 0:
            self._handle_placement_click(x, y)
            return

        now = time.monotonic()
        gap_ms = (now - self._last_click_time) * 1000.0
        near = (abs(x - self._last_click_pos[0]) <= tolerance * 2
                and abs(y - self._last_click_pos[1]) <= tolerance * 2)
        window_ms = float(self.cfg.get("interaction.double_click_ms"))
        is_double = near and gap_ms <= window_ms
        self._last_click_time = now
        self._last_click_pos = (x, y)

        needs_double = str(self.cfg.get("interaction.select_mode")) == "Doble clic"
        if needs_double and not is_double:
            return

        if is_double:
            # El doble clic ya quedo resuelto: se corta la cadena para que la
            # pulsacion que lo cierra no vuelva a evaluarse y deshaga lo hecho.
            self._last_click_time = 0.0

        hid = self._pick_hole_at(x, y)
        additive = bool(iren.GetControlKey())
        toggle = bool(iren.GetShiftKey())

        if hid is None:
            just_selected = (now - self._last_select_time) * 1000.0 < window_ms
            if (not additive and not toggle and not just_selected
                    and self.cfg.get("interaction.clear_on_empty")):
                self.clear_selection()
            return

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
        self._last_select_time = now

        if is_double:
            self.hole_activated.emit(hid)
        elif self.cfg.get("interaction.focus_on_select"):
            self.focus_on_selection()

    def _pick_hole_at(self, x: int, y: int) -> Optional[str]:
        """Taladro bajo el cursor, o ``None`` si se hizo clic en el vacio.

        Primero se prueba el picker de VTK sobre la geometria; si el cursor cayo
        junto al taladro y no encima —los cilindros son delgados—, se recurre a
        la distancia en pantalla, que es lo que hace que la seleccion se sienta
        precisa sin exigir punteria.
        """
        # Los adornos de la escena estan marcados como no seleccionables, asi
        # que lo que devuelva el picker pertenece siempre a un taladro.
        picker = vtk.vtkCellPicker()
        picker.SetTolerance(0.006)
        picker.Pick(x, y, 0, self.plotter.renderer)
        if picker.GetActor() is not None:
            hid = self._nearest_hole(np.array(picker.GetPickPosition(), float))
            if hid is not None:
                return hid
        return self._nearest_hole_on_screen(x, y)

    def _nearest_hole(self, point: np.ndarray, max_distance: float = 4.0) -> Optional[str]:
        """Taladro cuyo eje pasa mas cerca del punto indicado."""
        best_hid, best_d = None, float("inf")
        for h in self._holes:
            d = _point_segment_distance(point, h.collar, h.toe)
            if d < best_d:
                best_hid, best_d = h.hid, d
        return best_hid if best_d <= max_distance else None

    def _nearest_hole_on_screen(self, x: int, y: int) -> Optional[str]:
        """Taladro mas proximo al cursor medido en pixeles de pantalla.

        Solo se consideran los puntos que estan delante de la camara: los de
        detras se proyectan igualmente, pero a posiciones especulares que
        seleccionarian un taladro que el usuario no puede ni ver.
        """
        radius = int(self.cfg.get("interaction.pick_radius_px"))
        renderer = self.plotter.renderer
        best_hid, best_d2 = None, float(radius * radius)

        for h in self._holes:
            for world in (h.collar, (h.collar + h.toe) / 2.0, h.toe):
                renderer.SetWorldPoint(world[0], world[1], world[2], 1.0)
                renderer.WorldToDisplay()
                dx_, dy_, dz_ = renderer.GetDisplayPoint()
                if not 0.0 <= dz_ <= 1.0:
                    continue
                d2 = (dx_ - x) ** 2 + (dy_ - y) ** 2
                if d2 < best_d2:
                    best_hid, best_d2 = h.hid, d2
        return best_hid

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

        cfg = self.cfg
        color = str(cfg.get("holes.selection_color"))
        scale = float(cfg.get("holes.selection_scale"))
        holes = self.selected_holes()

        tubes = [pv.Tube(pointa=h.collar + np.array([0.0, 0.0, 1.8]), pointb=h.toe,
                         radius=self._hole_radius(h) * scale, n_sides=18)
                 for h in holes]
        if tubes:
            self._actors["selection"] = self.plotter.add_mesh(
                _merge(tubes), color=color,
                opacity=float(cfg.get("holes.selection_opacity")),
                name="selection", pickable=False,
                smooth_shading=bool(cfg.get("viewer.smooth_shading")))
        self._actors["selection_pts"] = self.plotter.add_mesh(
            pv.PolyData(np.array([h.collar for h in holes], float)), color=color,
            point_size=int(cfg.get("holes.collar_size")) + 6,
            render_points_as_spheres=True, name="selection_pts", pickable=False)
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
                dx, dy, dz = renderer.GetDisplayPoint()
                if not 0.0 <= dz <= 1.0:
                    continue          # detras de la camara
                # VTK mide desde abajo; Qt desde arriba.
                if rect.contains(QPoint(int(dx), int(height - dy))):
                    found.append(h.hid)
                    break
        return found

    # ------------------------------------------------------------------
    # Vector de direccion
    # ------------------------------------------------------------------
    def show_direction_vector(self, vector: Optional[DirectionVector]) -> None:
        """Dibuja la flecha que marca hacia donde avanza el disparo."""
        self.hide_direction_vector()
        if vector is None or not self._holes:
            return

        color = str(self.cfg.get("holes.selection_color"))
        scale = max(vector.length_m, 1.0)
        try:
            arrow = pv.Arrow(start=vector.origin, direction=vector.direction,
                             **_ARROW_SHAPE, scale=scale)
        except Exception:
            return
        self._actors["vector"] = self.plotter.add_mesh(
            arrow, color=color, name="direction_vector", pickable=False,
            smooth_shading=bool(self.cfg.get("viewer.smooth_shading")))

        # Marca del origen: es el punto que fija el cero de la secuencia.
        self._actors["vector_origin"] = self.plotter.add_mesh(
            pv.Sphere(radius=scale * 0.022, center=vector.origin), color=color,
            name="direction_origin", pickable=False)
        self.plotter.render()

    def hide_direction_vector(self) -> None:
        for key in ("vector", "vector_origin", "vector_preview"):
            if self._actors.get(key) is not None:
                self.plotter.remove_actor(self._actors[key], render=False)
                self._actors[key] = None

    # -- colocacion interactiva -------------------------------------------
    def start_vector_placement(self) -> None:
        """Activa la colocacion del vector con dos clics sobre el visor.

        El primero fija de donde arranca la voladura y el segundo hacia donde
        avanza; entre ambos se dibuja una flecha que sigue al cursor. Los puntos
        se resuelven sobre el plano de los collares, que es donde el usuario
        esta viendo la malla.
        """
        if not self._holes:
            return
        self._placement_stage = 1
        self._placement_origin = None
        self.widget.setCursor(Qt.CursorShape.CrossCursor)
        self._attach_placement_preview()
        self.placement_changed.emit(True)
        self.status_message.emit(
            "Vector de direccion: haga clic donde arranca el disparo, "
            "luego hacia donde avanza. Esc cancela.")

    def cancel_vector_placement(self) -> None:
        if self._placement_stage == 0:
            return
        self._placement_stage = 0
        self._placement_origin = None
        self.widget.unsetCursor()
        if self._actors.get("vector_preview") is not None:
            self.plotter.remove_actor(self._actors["vector_preview"], render=False)
            self._actors["vector_preview"] = None
        self.placement_changed.emit(False)
        self.status_message.emit("Colocacion del vector cancelada")
        self.plotter.render()

    def is_placing_vector(self) -> bool:
        return self._placement_stage > 0

    def _attach_placement_preview(self) -> None:
        if self._placement_observer is not None:
            return
        iren = self._interactor()
        if iren is None:
            return
        self._placement_observer = iren.AddObserver(
            "MouseMoveEvent", self._on_placement_move, 12.0)

    def _on_placement_move(self, _obj=None, _event=None) -> None:
        """Flecha provisional que sigue al cursor mientras se coloca."""
        if self._placement_stage != 2 or self._placement_origin is None:
            return
        iren = self._interactor()
        if iren is None:
            return
        point = self._screen_to_bench(*iren.GetEventPosition())
        if point is None:
            return
        span = float(np.linalg.norm(point - self._placement_origin))
        if span < 0.5:
            return

        if self._actors.get("vector_preview") is not None:
            self.plotter.remove_actor(self._actors["vector_preview"], render=False)
        try:
            arrow = pv.Arrow(start=self._placement_origin,
                             direction=point - self._placement_origin,
                             **_ARROW_SHAPE, scale=span)
        except Exception:
            return
        self._actors["vector_preview"] = self.plotter.add_mesh(
            arrow, color=str(self.cfg.get("holes.selection_color")), opacity=0.55,
            name="vector_preview", pickable=False)
        self.plotter.render()

    def _handle_placement_click(self, x: int, y: int) -> bool:
        """Consume el clic cuando se esta colocando el vector."""
        point = self._screen_to_bench(x, y)
        if point is None:
            return True

        if self._placement_stage == 1:
            self._placement_origin = point
            self._placement_stage = 2
            self.status_message.emit(
                "Origen fijado. Ahora marque hacia donde avanza el disparo.")
            return True

        origin = self._placement_origin
        self.cancel_vector_placement()
        if origin is None or float(np.linalg.norm(point - origin)) < 1.0:
            self.status_message.emit("Vector demasiado corto; vuelva a intentarlo.")
            return True
        self.direction_vector_placed.emit(DirectionVector.from_points(origin, point))
        return True

    def _screen_to_bench(self, x: int, y: int) -> Optional[np.ndarray]:
        """Punto del plano de los collares que corresponde a un pixel.

        Se lanza el rayo de la camara a traves del pixel y se corta contra el
        plano horizontal de la malla; asi el usuario puede marcar tambien sobre
        zona vacia, fuera de los taladros.
        """
        if not self._holes:
            return None
        renderer = self.plotter.renderer
        near, far = [], []
        for depth, target in ((0.0, near), (1.0, far)):
            renderer.SetDisplayPoint(float(x), float(y), depth)
            renderer.DisplayToWorld()
            w = renderer.GetWorldPoint()
            scale = w[3] if abs(w[3]) > 1e-12 else 1.0
            target.extend([w[0] / scale, w[1] / scale, w[2] / scale])

        p0 = np.array(near, float)
        p1 = np.array(far, float)
        z_plane = float(np.mean([h.collar_z for h in self._holes]))
        dz = p1[2] - p0[2]
        if abs(dz) < 1e-9:               # camara mirando en horizontal
            return None
        t = (z_plane - p0[2]) / dz
        if not -0.5 <= t <= 1.5:
            return None
        return p0 + t * (p1 - p0)

    # ------------------------------------------------------------------
    # Isocronas y recorrido del disparo
    # ------------------------------------------------------------------
    def show_isochrones(self, curves, show_labels: bool = True) -> None:
        """Dibuja las curvas de igual tiempo de detonacion."""
        self.hide_isochrones()
        if not curves:
            return

        blocks, labels, positions = [], [], []
        for level, polylines in curves:
            for line in polylines:
                if len(line) >= 2:
                    blocks.append(pv.lines_from_points(np.asarray(line, float)))
            if polylines and show_labels:
                longest = max(polylines, key=len)
                positions.append(longest[len(longest) // 2])
                labels.append(f"{level:,.0f} ms")
        if not blocks:
            return

        merged = blocks[0].copy()
        for b in blocks[1:]:
            merged = merged.merge(b)
        self._actors["isochrones"] = self.plotter.add_mesh(
            merged, color=C["accent"], line_width=2, name="isochrones",
            pickable=False)
        if labels:
            self._actors["isochrone_labels"] = self.plotter.add_point_labels(
                np.array(positions, float), labels, font_size=10,
                text_color=C["accent"], shape=None, always_visible=True,
                point_size=1, name="isochrone_labels", bold=False)
        self.plotter.render()

    def hide_isochrones(self) -> None:
        for key in ("isochrones", "isochrone_labels"):
            if self._actors.get(key) is not None:
                self.plotter.remove_actor(self._actors[key], render=False)
                self._actors[key] = None

    def show_firing_path(self, points) -> None:
        """Traza el recorrido del disparo uniendo los collares por orden de salida."""
        self.hide_firing_path()
        points = np.asarray(points, float)
        if len(points) < 2:
            return
        offset = points + np.array([0.0, 0.0, 0.8])
        self._actors["path"] = self.plotter.add_mesh(
            pv.lines_from_points(offset), color=C["ok"], line_width=2,
            name="firing_path", pickable=False)
        self.plotter.render()

    def hide_firing_path(self) -> None:
        if self._actors.get("path") is not None:
            self.plotter.remove_actor(self._actors["path"], render=False)
            self._actors["path"] = None

    # ------------------------------------------------------------------
    # Animacion de la secuencia
    # ------------------------------------------------------------------
    def start_animation(self, speed: Optional[float] = None) -> None:
        if not self._holes:
            return
        cfg = self.cfg
        fps = max(int(cfg.get("animation.fps")), 1)
        rate = float(speed if speed is not None else cfg.get("animation.speed"))
        self._anim_end = (max(h.delay_actual_ms for h in self._holes)
                          + float(cfg.get("animation.tail_ms")))
        self._anim_t = 0.0
        self._anim_step = 1000.0 / fps * max(rate, 0.01)
        self._timer.start(int(1000 / fps))

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
        flash = float(self.cfg.get("animation.flash_ms"))
        state = np.empty(len(self._charge_index), float)
        for k, idx in enumerate(self._charge_index):
            dt = t_ms - self._holes[idx].delay_actual_ms
            state[k] = 0.0 if dt < 0 else (1.0 if dt < flash else 0.5)

        self._remove_charge_actors()
        palette = [str(self.cfg.get("animation.color_pending")),
                   str(self.cfg.get("animation.color_firing")),
                   str(self.cfg.get("animation.color_fired"))]
        self._actors["charge"] = self.plotter.add_mesh(
            _merge(self._charge_meshes, scalars=state, name="estado"),
            scalars="estado", cmap=palette, clim=[0.0, 1.0], name="charge",
            show_scalar_bar=False,
            smooth_shading=bool(self.cfg.get("viewer.smooth_shading")))
        self.plotter.render()

    # ------------------------------------------------------------------
    # Preferencias
    # ------------------------------------------------------------------
    #: Prefijos que obligan a reconstruir la escena entera.
    _REBUILD_PREFIXES = ("holes.", "layers.", "viewer.")

    def _on_setting_changed(self, key: str, value) -> None:
        """Aplica en caliente los cambios de Preferencias que afectan al visor."""
        if key == "interaction.nav_mode":
            self.set_nav_mode(str(value))
        elif key == "viewer.z_exaggeration":
            self.set_z_exaggeration(float(value))
        elif key.startswith("hole_colors."):
            self.set_theme(self._theme)
        elif key in ("viewer.background_top", "viewer.background_bottom", "viewer.gradient"):
            self._setup_scene()
            self.plotter.render()
        elif key.startswith(self._REBUILD_PREFIXES):
            self.rebuild()

    def rebuild(self) -> None:
        """Pide a la ventana que vuelva a dibujar la escena.

        El visor no conoce la topografia ni la cara libre del proyecto, asi que
        no puede reconstruirse solo: avisa y la ventana principal se encarga.
        """
        if self._holes:
            self.scene_rebuild_requested.emit()


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
