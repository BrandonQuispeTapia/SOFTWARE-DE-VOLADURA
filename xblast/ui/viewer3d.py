"""Visor 3D de la voladura.

Envuelve el interactor de PyVista y concentra toda la construccion de la
escena: terreno, cara libre, columnas de carga, etiquetas, tematizacion por
variable, campo de energia y animacion de la secuencia de salida.
"""

from __future__ import annotations

import math
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pyvista as pv
from pyvistaqt import QtInteractor
from PySide6.QtCore import QObject, QTimer, Signal

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


class Viewer3D(QObject):
    """Gestiona la escena 3D y expone operaciones de alto nivel."""

    hole_picked = Signal(str)
    frame_changed = Signal(float)
    animation_finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.plotter = QtInteractor(parent)
        self.widget = self.plotter.interactor

        self._holes: List[Hole] = []
        self._collars: np.ndarray = np.empty((0, 3))
        self._actors: Dict[str, object] = {}
        self._labels_visible = False
        self._theme = "Tipo de taladro"

        # animacion
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._anim_t = 0.0
        self._anim_speed = 1.0
        self._anim_end = 0.0

        self._setup_scene()

    # -- escena base -------------------------------------------------------
    def _setup_scene(self) -> None:
        p = self.plotter
        p.set_background(C["viewport"], top="#ffffff")
        p.enable_anti_aliasing("fxaa")
        try:
            p.enable_parallel_projection()
            p.disable_parallel_projection()
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

    # -- construccion ------------------------------------------------------
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
        """Plano de referencia del piso del banco bajo los taladros."""
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
        faces = []
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
        charge_blocks: List[pv.PolyData] = []
        charge_scalars: List[float] = []
        self._charge_index: List[int] = []

        for idx, h in enumerate(self._holes):
            r_hole = max(h.diameter_m / 2.0, 0.06)
            r_vis = max(r_hole * 3.0, 0.16)   # radio visual, legible a escala de banco

            for d in h.decks:
                p0 = h.point_from_toe(d.from_toe_m)
                p1 = h.point_from_toe(d.from_toe_m + d.length_m)
                center = (p0 + p1) / 2.0
                direction = h.axis
                cyl = pv.Cylinder(center=center, direction=direction,
                                  radius=r_vis, height=max(d.length_m, 0.05),
                                  resolution=14, capping=True)
                kind = d.kind.value if hasattr(d.kind, "value") else str(d.kind)
                if kind == "Carga":
                    charge_blocks.append(cyl)
                    charge_scalars.append(float(idx))
                    self._charge_index.append(idx)
                elif kind == "Aire":
                    air_blocks.append(cyl)
                else:
                    stem_blocks.append(cyl)

        if stem_blocks:
            mesh = _merge(stem_blocks)
            self._actors["stem"] = self.plotter.add_mesh(
                mesh, color="#9aa5b1", opacity=0.9, name="stemming", smooth_shading=True)
        if air_blocks:
            mesh = _merge(air_blocks)
            self._actors["air"] = self.plotter.add_mesh(
                mesh, color="#e8edf2", opacity=0.45, name="airdeck", smooth_shading=True)

        if charge_blocks:
            self._charge_meshes = charge_blocks
            self._charge_mesh = _merge(charge_blocks)
            self._actors["charge"] = self.plotter.add_mesh(
                self._charge_mesh, color=HOLE_TYPE_COLORS["Produccion"],
                name="charge", smooth_shading=True, pickable=True)

        # collares como puntos seleccionables
        cloud = pv.PolyData(self._collars)
        cloud["hid"] = np.arange(len(self._holes), dtype=float)
        self._actors["collars"] = self.plotter.add_mesh(
            cloud, color=C["text"], point_size=7, render_points_as_spheres=True,
            name="collars", pickable=True)

    def _add_grid(self) -> None:
        try:
            self.plotter.show_grid(
                color=C["grid"], font_size=9, location="outer", grid="back",
                xtitle="Este (m)", ytitle="Norte (m)", ztitle="Cota (m)",
                axes_ranges=None)
        except Exception:
            pass

    # -- tematizacion ------------------------------------------------------
    def set_theme(self, theme: str) -> None:
        """Colorea las cargas segun la variable seleccionada."""
        self._theme = theme if theme in THEMES else "Tipo de taladro"
        if not self._holes or "charge" not in self._actors:
            return

        attr, unit = THEMES[self._theme]
        self.plotter.remove_actor(self._actors["charge"], render=False)
        try:
            self.plotter.remove_scalar_bar()
        except Exception:
            pass

        if attr == "type":
            blocks: Dict[str, List[pv.PolyData]] = {}
            for mesh, idx in zip(self._charge_meshes, self._charge_index):
                blocks.setdefault(self._holes[idx].hole_type, []).append(mesh)
            self._type_actors = []
            for htype, meshes in blocks.items():
                color = HOLE_TYPE_COLORS.get(htype, "#c0392b")
                actor = self.plotter.add_mesh(
                    _merge(meshes), color=color, name=f"charge_{htype}",
                    smooth_shading=True, pickable=True)
                self._type_actors.append(actor)
            self._actors["charge"] = self._type_actors[0] if self._type_actors else None
        else:
            values = np.array([getattr(self._holes[i], attr, 0.0) for i in self._charge_index], float)
            mesh = _merge(self._charge_meshes, scalars=values, name=self._theme)
            self._actors["charge"] = self.plotter.add_mesh(
                mesh, scalars=self._theme, cmap="viridis", name="charge",
                smooth_shading=True, pickable=True,
                scalar_bar_args={
                    "title": f"{self._theme}", "color": C["text"], "n_labels": 5,
                    "vertical": True, "position_x": 0.88, "position_y": 0.12,
                    "width": 0.05, "height": 0.55, "title_font_size": 11,
                    "label_font_size": 10, "font_family": "arial",
                })
        self.plotter.render()

    def set_labels_visible(self, visible: bool) -> None:
        self._labels_visible = visible
        if "labels" in self._actors and self._actors["labels"] is not None:
            self.plotter.remove_actor(self._actors["labels"], render=False)
            self._actors["labels"] = None
        if visible and self._holes:
            offset = np.array([0.0, 0.0, 1.2])
            self._actors["labels"] = self.plotter.add_point_labels(
                self._collars + offset, [h.hid for h in self._holes],
                font_size=11, text_color=C["text"], shape=None, always_visible=True,
                point_size=1, name="labels", bold=False)
        self.plotter.render()

    # -- campo de energia --------------------------------------------------
    def show_energy_field(self, field, contours: int = 6, opacity: float = 0.35) -> None:
        """Superpone isosuperficies del campo de energia."""
        self.hide_energy_field()
        if field is None:
            return
        grid = pv.ImageData(dimensions=field.dims, spacing=(field.spacing,) * 3,
                            origin=tuple(field.origin))
        grid["Energia (MJ/m3)"] = field.flat
        vmax = float(np.percentile(field.values[field.values > 0], 97)) if np.any(field.values > 0) else 1.0
        levels = np.linspace(vmax * 0.15, vmax, contours)
        try:
            iso = grid.contour(isosurfaces=levels.tolist(), scalars="Energia (MJ/m3)")
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

    # -- animacion ---------------------------------------------------------
    def start_animation(self, speed: float = 1.0, fps: int = 30) -> None:
        """Reproduce la secuencia de salida coloreando los taladros disparados."""
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
        """Colorea segun el tiempo transcurrido desde la detonacion."""
        if "charge" not in self._actors or not hasattr(self, "_charge_meshes"):
            return
        state = np.empty(len(self._charge_index), float)
        for k, idx in enumerate(self._charge_index):
            dt = t_ms - self._holes[idx].delay_actual_ms
            if dt < 0:
                state[k] = 0.0            # pendiente
            elif dt < 120.0:
                state[k] = 1.0            # detonando
            else:
                state[k] = 0.5            # ya disparado
        mesh = _merge(self._charge_meshes, scalars=state, name="estado")
        try:
            self.plotter.remove_actor(self._actors["charge"], render=False)
            self.plotter.remove_scalar_bar()
        except Exception:
            pass
        self._actors["charge"] = self.plotter.add_mesh(
            mesh, scalars="estado", cmap=["#b4bdc6", "#f0a202", "#c0392b"],
            clim=[0.0, 1.0], name="charge", show_scalar_bar=False, smooth_shading=True)
        self.plotter.render()

    # -- camara ------------------------------------------------------------
    def reset_camera(self) -> None:
        self.plotter.reset_camera()
        self.plotter.render()

    def view_iso(self) -> None:
        self.plotter.view_isometric()
        self.plotter.render()

    def view_top(self) -> None:
        self.plotter.view_xy()
        self.plotter.render()

    def view_front(self) -> None:
        self.plotter.view_xz()
        self.plotter.render()

    def view_side(self) -> None:
        self.plotter.view_yz()
        self.plotter.render()

    def screenshot(self, path: str, scale: int = 2) -> None:
        self.plotter.screenshot(path, scale=scale)

    # -- seleccion ---------------------------------------------------------
    def enable_picking(self) -> None:
        def _cb(point, *_):
            if len(self._collars) == 0:
                return
            d = np.linalg.norm(self._collars[:, :2] - np.asarray(point)[:2], axis=1)
            i = int(np.argmin(d))
            self.hole_picked.emit(self._holes[i].hid)

        try:
            self.plotter.enable_point_picking(
                callback=_cb, show_message=False, left_clicking=True,
                show_point=False, use_picker=True)
        except Exception:
            pass

    def highlight(self, hid: str) -> None:
        """Marca visualmente el taladro seleccionado."""
        if self._actors.get("selection") is not None:
            self.plotter.remove_actor(self._actors["selection"], render=False)
            self._actors["selection"] = None
        for h in self._holes:
            if h.hid == hid:
                line = pv.Line(h.collar + np.array([0, 0, 1.5]), h.toe)
                self._actors["selection"] = self.plotter.add_mesh(
                    line, color="#f0a202", line_width=6, name="selection")
                break
        self.plotter.render()


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
