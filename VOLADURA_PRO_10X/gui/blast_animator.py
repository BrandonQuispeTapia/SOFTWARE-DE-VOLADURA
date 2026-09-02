import numpy as np
import pyvista as pv
from PySide6.QtCore import QTimer, QObject, Signal
from typing import List
import math


class BlastHole:
    def __init__(self, hole_id, collar, toe, radius, detonation_time_ms, charge_mass_kg, hole_type="PRODUCCION", row=0, col=0):
        self.hole_id = str(hole_id)
        self.collar = np.array(collar, dtype=np.float64)
        self.toe = np.array(toe, dtype=np.float64)
        self.radius = float(radius)
        self.detonation_time_ms = float(detonation_time_ms)
        self.charge_mass_kg = float(charge_mass_kg)
        self.hole_type = hole_type
        self.row = row
        self.col = col
        diff = self.toe - self.collar
        norm = np.linalg.norm(diff)
        self.direction = diff / norm if norm > 1e-9 else np.array([0, 0, -1])
        self.length = float(norm)
        self.state = "standby"
        self.actor = None
        self.stem_actor = None
        self.label_actor = None


def _set_actor(actor, r, g, b, opacity=1.0):
    try:
        actor.GetProperty().SetColor(r, g, b)
        actor.GetProperty().SetOpacity(opacity)
    except Exception:
        pass


class FragmentationMuckpile:
    def __init__(self, holes, burden, spacing, p80_mm=500.0, n=1.5):
        self.holes = holes
        self.burden = burden
        self.spacing = spacing
        self.p80 = p80_mm
        self.n = n
        self.coords = self._generate()
        self.colors = self._fragment_colors()
        self.displacements = np.zeros_like(self.coords)

    def _generate(self):
        pts = []
        for h in self.holes:
            xy = h.collar[:2]
            for i in range(30):
                a = 2 * np.pi * i / 30 + np.random.uniform(-0.2, 0.2)
                d = self.burden * (0.3 + np.random.uniform(0.0, 1.2))
                x = xy[0] + d * np.cos(a)
                y = xy[1] + d * np.sin(a) + self.burden * 0.5
                z = h.collar[2] + np.random.uniform(-1.0, 0.5)
                pts.append([x, y, z])
        return np.array(pts) if pts else np.zeros((0, 3))

    def _fragment_colors(self):
        if self.coords.size == 0:
            return np.zeros((0, 3))
        colors = np.zeros((len(self.coords), 3))
        for i, pt in enumerate(self.coords):
            dist = np.sqrt((pt[0] - self.holes[0].collar[0])**2 + (pt[1] - self.holes[0].collar[1])**2)
            max_dist = self.burden * 3
            t = min(dist / max_dist, 1.0)
            size_ratio = 1.0 - t * 0.5
            if size_ratio > 0.8:
                colors[i] = [0.8, 0.2, 0.2]
            elif size_ratio > 0.5:
                colors[i] = [0.9, 0.6, 0.1]
            elif size_ratio > 0.3:
                colors[i] = [0.2, 0.7, 0.3]
            else:
                colors[i] = [0.2, 0.4, 0.9]
        return colors

    def get_displaced(self, hole, max_disp=4.0):
        if self.coords.size == 0:
            return np.zeros((0, 3))
        xy = hole.collar[:2]
        dists = np.linalg.norm(self.coords[:, :2] - xy, axis=1)
        safe = np.maximum(dists, 0.1)
        energy = 1.0 / (safe ** 1.2)
        energy /= (energy.max() + 1e-6)
        dirs = np.zeros_like(self.coords)
        m = dists > 0.01
        dirs[m, :2] = (self.coords[m, :2] - xy) / dists[m, np.newaxis]
        disp = dirs * (energy[:, np.newaxis] * max_disp)
        disp[:, 2] += energy * max_disp * 0.3
        disp[:, 2] -= energy * max_disp * 0.6
        return disp


class BlastAnimator(QObject):
    frame_updated = Signal(int)
    animation_finished = Signal()
    row_detonated = Signal(int, float)

    def __init__(self, plotter, holes: List[BlastHole], burden=4.5, spacing=5.0):
        super().__init__()
        self.plotter = plotter
        self.holes = sorted(holes, key=lambda h: h.detonation_time_ms)
        self.burden = burden
        self.spacing = spacing
        self.timeline = np.array([h.detonation_time_ms for h in self.holes])
        self.total_ms = float(self.timeline.max()) + 1000 if len(self.timeline) > 0 else 1000.0
        self.is_playing = False
        self.t = 0.0
        self.interval = 40
        self.timer = QTimer()
        self.timer.timeout.connect(self._tick)
        self.fired_rows = set()
        self.boom_actors = []
        self.shockwave_actors = []
        self.muckpile = None
        self.muckpile_actor = None

    def start(self):
        self.is_playing = True
        self.t = 0.0
        self.fired_rows = set()
        self.boom_actors = []
        self.shockwave_actors = []
        self.fired_rows = set()
        for h in self.holes:
            h.state = "standby"
            _set_actor(h.actor, 0.2, 0.8, 0.2, 0.85)
            if h.stem_actor:
                _set_actor(h.stem_actor, 0.35, 0.35, 0.35, 0.9)

        p80 = 500.0
        vol = self.burden * self.spacing * 12
        pf = 1.15 * 9 / vol if vol > 0 else 0.1
        x50 = 8.0 * (vol ** 0.167) / (pf ** 0.8)
        p80 = x50 * 15.0
        self.muckpile = FragmentationMuckpile(self.holes, self.burden, self.spacing, p80)
        if self.muckpile.coords.size > 0:
            pd = pv.PolyData(self.muckpile.coords)
            self.muckpile_actor = self.plotter.add_mesh(
                pd, scalars=self.muckpile.colors, rgb=True,
                point_size=4.0, opacity=0.0, name="muckpile",
                render_points_as_spheres=True
            )
        self.timer.start(self.interval)

    def _tick(self):
        self.t += self.interval
        for h in self.holes:
            dt = self.t - h.detonation_time_ms
            if h.state == "standby" and dt >= 0:
                h.state = "fired"
                self._on_fire(h)
                row = h.row
                if row not in self.fired_rows:
                    self.fired_rows.add(row)
                    self.row_detonated.emit(row, self.t)
            elif h.state == "fired" and dt >= 180:
                h.state = "empty"
                self._on_empty(h)

        self._update_shockwaves()
        self._update_muckpile()
        self.frame_updated.emit(int(self.t))

        if self.t >= self.total_ms + 800:
            self.stop()
            self.animation_finished.emit()

    def _on_fire(self, h):
        _set_actor(h.actor, 1.0, 0.85, 0.0, 1.0)
        sphere = pv.Sphere(radius=self.burden * 0.3, center=h.collar)
        a = self.plotter.add_mesh(sphere, color=(1.0, 0.4, 0.0), opacity=0.8, name=f"boom_{h.hole_id}_{int(self.t)}")
        self.boom_actors.append(a)

        ring = pv.Cylinder(center=h.collar, direction=(0, 0, 1), radius=self.burden * 0.8, height=0.1, resolution=24)
        wa = self.plotter.add_mesh(ring, color=(1.0, 0.6, 0.0), opacity=0.6, name=f"wave_{h.hole_id}_{int(self.t)}")
        self.shockwave_actors.append((wa, self.t, h.collar.copy()))

    def _on_empty(self, h):
        _set_actor(h.actor, 0.25, 0.25, 0.25, 0.2)
        if h.stem_actor:
            _set_actor(h.stem_actor, 0.25, 0.25, 0.25, 0.15)

    def _update_shockwaves(self):
        new_actors = []
        for actor, birth, center in self.shockwave_actors:
            age = self.t - birth
            if age > 400:
                try:
                    self.plotter.remove_actor(actor)
                except Exception:
                    pass
                continue
            try:
                radius = self.burden * 0.3 + age * 0.015
                opacity = max(0, 0.6 - age * 0.002)
                actor.GetProperty().SetOpacity(opacity)
            except Exception:
                pass
            new_actors.append((actor, birth, center))
        self.shockwave_actors = new_actors

    def _update_muckpile(self):
        if self.muckpile is None or self.muckpile_actor is None or self.muckpile.coords.size == 0:
            return
        try:
            total = np.zeros_like(self.muckpile.coords)
            n_fired = 0
            for h in self.holes:
                if h.state in ("fired", "empty"):
                    total += self.muckpile.get_displaced(h, max_disp=3.5)
                    n_fired += 1
            progress = min(n_fired / max(len(self.holes), 1), 1.0)
            new_coords = self.muckpile.coords + total * progress
            self.muckpile_actor.GetMapper().GetInput().Points = new_coords
            self.muckpile_actor.GetMapper().GetInput().Modified()
        except Exception:
            pass

    def stop(self):
        self.is_playing = False
        self.timer.stop()

    def pause(self):
        if self.is_playing:
            self.timer.stop()
            self.is_playing = False

    def resume(self):
        if not self.is_playing:
            self.timer.start(self.interval)
            self.is_playing = True

    def reset(self):
        self.stop()
        self.t = 0.0
        for h in self.holes:
            h.state = "standby"
            _set_actor(h.actor, 0.2, 0.8, 0.2, 0.85)
