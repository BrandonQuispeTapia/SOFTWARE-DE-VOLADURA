import numpy as np
import pyvista as pv
from PySide6.QtWidgets import QToolBar, QPushButton, QLabel, QWidget
from PySide6.QtCore import Signal


class ToolMode:
    NONE = "none"
    RULER = "ruler"
    ORE_BOUNDARY = "ore_boundary"
    ENERGY_HEATMAP = "energy_heatmap"
    PROFILE = "profile"
    GRID = "grid"
    ANGLE = "angle"


class CADToolBar(QToolBar):
    mode_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__("CAD", parent)
        self.setMovable(False)
        self.setStyleSheet("""
            QToolBar {
                background-color: #0F172A;
                border-bottom: 1px solid #1E293B;
                padding: 3px 6px;
                spacing: 4px;
            }
        """)

        self.mode = ToolMode.NONE
        self.ruler_points = []
        self.boundary_points = []
        self.angle_points = []

        def _make_btn(text, mode):
            btn = QPushButton(f"[ {text} ]")
            btn.setCheckable(True)
            btn.setFlat(True)
            btn.setMinimumHeight(30)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #64748B;
                    border: 1px solid transparent;
                    border-radius: 3px;
                    padding: 4px 12px;
                    font-size: 9pt;
                    font-weight: 600;
                    font-family: 'Courier New', monospace;
                    letter-spacing: 0.5px;
                }
                QPushButton:hover {
                    background-color: #1E293B;
                    color: #E2E8F0;
                    border: 1px solid #334155;
                }
                QPushButton:checked {
                    background-color: #1E3A5F;
                    color: #00F0FF;
                    border: 1px solid #00F0FF;
                }
            """)
            btn.clicked.connect(lambda: self._set(mode))
            return btn

        self.btn_ruler = _make_btn("MEDIR", ToolMode.RULER)
        self.btn_boundary = _make_btn("LIMITE", ToolMode.ORE_BOUNDARY)
        self.btn_heatmap = _make_btn("HEATMAP", ToolMode.ENERGY_HEATMAP)
        self.btn_profile = _make_btn("PERFIL", ToolMode.PROFILE)
        self.btn_grid = _make_btn("CUADRICULA", ToolMode.GRID)
        self.btn_angle = _make_btn("ANGULO", ToolMode.ANGLE)

        self.btn_clear = QPushButton("[ LIMPIAR ]")
        self.btn_clear.setFlat(True)
        self.btn_clear.setMinimumHeight(30)
        self.btn_clear.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #64748B;
                border: 1px solid transparent;
                border-radius: 3px;
                padding: 4px 12px;
                font-size: 9pt;
                font-weight: 600;
                font-family: 'Courier New', monospace;
            }
            QPushButton:hover {
                background-color: #7F1D1D;
                color: #FCA5A5;
                border: 1px solid #DC2626;
            }
        """)
        self.btn_clear.clicked.connect(self._clear)

        sep_label = QLabel("|")
        sep_label.setStyleSheet("color:#334155; font-size:11pt; padding:0 2px;")

        self.info = QLabel("RDY")
        self.info.setStyleSheet("""
            color: #475569;
            font-family: 'Courier New', monospace;
            font-size: 8pt;
            font-weight: bold;
            padding: 0 8px;
            letter-spacing: 1px;
        """)

        self.addWidget(QLabel("CAD:"))
        self.addWidget(self.btn_ruler)
        self.addWidget(self.btn_boundary)
        self.addWidget(self.btn_heatmap)
        self.addWidget(self.btn_profile)
        self.addWidget(self.btn_grid)
        self.addWidget(self.btn_angle)
        self.addWidget(sep_label)
        self.addWidget(self.btn_clear)
        self.addWidget(QWidget())
        self.addWidget(self.info)

    def _set(self, mode):
        if self.mode == mode:
            mode = ToolMode.NONE
        self.btn_ruler.setChecked(mode == ToolMode.RULER)
        self.btn_boundary.setChecked(mode == ToolMode.ORE_BOUNDARY)
        self.btn_heatmap.setChecked(mode == ToolMode.ENERGY_HEATMAP)
        self.btn_profile.setChecked(mode == ToolMode.PROFILE)
        self.btn_grid.setChecked(mode == ToolMode.GRID)
        self.btn_angle.setChecked(mode == ToolMode.ANGLE)
        self.mode = mode
        self.ruler_points = []
        self.boundary_points = []
        self.angle_points = []
        msgs = {
            ToolMode.RULER: "MEDIR: 2 pts",
            ToolMode.ORE_BOUNDARY: "LIMITE: pts",
            ToolMode.ENERGY_HEATMAP: "HEATMAP ON",
            ToolMode.PROFILE: "PERFIL: 2 pts",
            ToolMode.GRID: "GRID ON",
            ToolMode.ANGLE: "ANGULO: 3 pts",
            ToolMode.NONE: "RDY",
        }
        self.info.setText(msgs.get(mode, "RDY"))
        self.mode_changed.emit(mode)

    def _clear(self):
        self._set(ToolMode.NONE)
        self.info.setText("RDY")
        p = self.parent()
        if hasattr(p, '_clear_cad'):
            p._clear_cad()

    def handle_click(self, point, plotter, holes=None):
        pt = np.array(point[:3])
        if self.mode == ToolMode.RULER:
            self.ruler_points.append(pt)
            if len(self.ruler_points) == 2:
                p1, p2 = self.ruler_points
                dist = float(np.linalg.norm(p2 - p1))
                line = pv.Line(p1, p2, resolution=2)
                plotter.add_mesh(line, color="#FBBF24", line_width=3, name="ruler_line")
                mid = (p1 + p2) / 2.0
                plotter.add_point_labels([mid], [f"  {dist:.2f} m  "], font_size=14, text_color="#FBBF24", point_size=1, shape_opacity=0, name="ruler_text", always_visible=True)
                self.info.setText(f"{dist:.2f}m")
                self.ruler_points = []
                return True
        elif self.mode == ToolMode.ORE_BOUNDARY:
            self.boundary_points.append(pt)
            if len(self.boundary_points) > 1:
                pts = np.array(self.boundary_points)
                n = len(pts)
                lines_np = np.array([[2, i, (i + 1) % n] for i in range(n)])
                pd = pv.PolyData(pts, lines_np)
                plotter.add_mesh(pd, color="#FBBF24", line_width=3, name="boundary")
                self.info.setText(f"LIM: {n}pts")
                return True
        elif self.mode == ToolMode.PROFILE:
            self.ruler_points.append(pt)
            if len(self.ruler_points) == 2:
                p1, p2 = self.ruler_points
                dist = float(np.linalg.norm(p2 - p1))
                line = pv.Line(p1, p2, resolution=50)
                plotter.add_mesh(line, color="#22D3EE", line_width=3, name="profile_line")
                mid = (p1 + p2) / 2.0
                plotter.add_point_labels([mid], [f"  PERFIL {dist:.1f}m  "], font_size=12, text_color="#22D3EE", point_size=1, shape_opacity=0, name="profile_text", always_visible=True)
                self.info.setText(f"PRF {dist:.1f}m")
                self.ruler_points = []
                return True
        elif self.mode == ToolMode.GRID:
            center = pt.copy()
            grid_size = 50.0; grid_step = 5.0
            x0 = center[0] - grid_size / 2; y0 = center[1] - grid_size / 2
            lines = []
            for i in range(int(grid_size / grid_step) + 1):
                offset = i * grid_step
                lines.append(pv.Line(np.array([x0 + offset, y0, 0]), np.array([x0 + offset, y0 + grid_size, 0])))
                lines.append(pv.Line(np.array([x0, y0 + offset, 0]), np.array([x0 + grid_size, y0 + offset, 0])))
            grid_mesh = lines[0]
            for l in lines[1:]:
                grid_mesh = grid_mesh.merge(l)
            plotter.add_mesh(grid_mesh, color="#475569", line_width=1, opacity=0.3, name="grid_overlay")
            self.info.setText(f"GRID {grid_size:.0f}m")
            return True
        elif self.mode == ToolMode.ANGLE:
            self.angle_points.append(pt)
            if len(self.angle_points) == 3:
                a, b, c = self.angle_points
                v1 = a - b; v2 = c - b
                norm1 = np.linalg.norm(v1); norm2 = np.linalg.norm(v2)
                if norm1 > 1e-9 and norm2 > 1e-9:
                    cos_angle = np.clip(np.dot(v1, v2) / (norm1 * norm2), -1.0, 1.0)
                    angle_deg = float(np.degrees(np.arccos(cos_angle)))
                    line1 = pv.Line(b, a, resolution=2)
                    line2 = pv.Line(b, c, resolution=2)
                    plotter.add_mesh(line1, color="#FB923C", line_width=3, name="angle_line1")
                    plotter.add_mesh(line2, color="#FB923C", line_width=3, name="angle_line2")
                    mid = b + (v1 + v2) / 2.0 * 0.3
                    plotter.add_point_labels([mid], [f"  {angle_deg:.1f} deg  "], font_size=14, text_color="#FB923C", point_size=1, shape_opacity=0, name="angle_text", always_visible=True)
                    self.info.setText(f"{angle_deg:.1f}deg")
                else:
                    self.info.setText("ERR")
                self.angle_points = []
                return True
        return False
