import sys, math, numpy as np, pyvista as pv
from pyvistaqt import QtInteractor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QFormLayout, QTreeWidget, QTreeWidgetItem, QScrollArea, QGroupBox,
    QLabel, QPushButton, QToolBar, QStatusBar, QTextEdit, QLineEdit,
    QDoubleSpinBox, QComboBox, QMessageBox, QFrame
)
from PySide6.QtCore import Qt, Signal, QTimer, QObject, QSize
from PySide6.QtGui import QIcon, QFont
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple
from datetime import datetime


@dataclass
class RockMass:
    ucs_mpa: float = 120.0
    rqd_pct: float = 65.0
    densidad_tm3: float = 2.6
    resistencia_traccion_mpa: float = 8.0
    modulo_young_gpa: float = 25.0


@dataclass
class Explosive:
    nombre: str = "ANFO Pesado (HA 46)"
    densidad_gcc: float = 1.15
    vod_ms: float = 5200.0
    presion_detonacion_gpa: float = 8.5
    acoplamiento_fc: float = 1.0
    energia_choque_pct: float = 45.0
    energia_gas_pct: float = 55.0


@dataclass
class Deck:
    explosive: str = "ANFO Pesado (HA 46)"
    start_depth_m: float = 0.0
    end_depth_m: float = 5.0
    stemming_intermedio_m: float = 1.5


@dataclass
class Drillhole:
    id: str = "T-01"
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    diametro_mm: float = 102.0
    longitud_total_m: float = 13.0
    inclinacion_deg: float = 0.0
    azimut_deg: float = 0.0
    burden_real_m: float = 4.5
    espaciamiento_m: float = 5.0
    taco_m: float = 3.0
    subperforacion_m: float = 1.0
    decks: List[Deck] = field(default_factory=list)
    booster_type: str = "Pentolita 150g"
    booster_z: float = 0.0
    row: int = 0
    col: int = 0
    delay_ms: float = 0.0
    charge_mass_kg: float = 0.0
    hole_type: str = "PRODUCCION"
    rock: RockMass = field(default_factory=RockMass)
    explosive: Explosive = field(default_factory=Explosive)
    actor: Optional[object] = field(default=None, repr=False)
    stem_actor: Optional[object] = field(default=None, repr=False)

    @property
    def collar(self) -> np.ndarray:
        return np.array([self.x, self.y, self.z], dtype=np.float64)

    @property
    def toe(self) -> np.ndarray:
        return np.array([self.x, self.y, self.z - self.longitud_total_m], dtype=np.float64)

    @property
    def charge_length_m(self) -> float:
        return max(0.0, self.longitud_total_m - self.taco_m - self.subperforacion_m)

    def distance_to_point(self, pt: np.ndarray) -> float:
        return float(np.linalg.norm(np.asarray(pt[:3], dtype=np.float64) - self.collar))


@dataclass
class ProjectMetadata:
    nombre: str = "TAJO PRINCIPAL - BANCO 2425"
    ingeniero: str = "Ing. Felix Fernando Bautista Layme"
    fecha: str = datetime.now().strftime("%Y-%m-%d %H:%M")
    labor: str = "Nivel 2425 - Zona Norte"
    tipo_mineria: str = "Surface"


QSS_ENTERPRISE = """
QMainWindow, QWidget {
    background-color: #0B0F19;
    color: #E2E8F0;
    font-family: 'Segoe UI', 'Roboto', sans-serif;
    font-size: 10pt;
}
QDockWidget {
    background-color: #1E293B;
    color: #E2E8F0;
    titlebar-close-icon: url(none);
    titlebar-normal-icon: url(none);
}
QDockWidget::title {
    background-color: #0F172A;
    padding: 8px 12px;
    color: #00F0FF;
    font-weight: bold;
    font-size: 9pt;
    letter-spacing: 1px;
    border-bottom: 1px solid #334155;
}
QGroupBox {
    border: 1px solid #1E293B;
    border-radius: 6px;
    margin-top: 14px;
    font-weight: 600;
    color: #94A3B8;
    padding-top: 18px;
    background-color: rgba(15, 23, 42, 160);
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
    color: #38BDF8;
    font-size: 9pt;
    letter-spacing: 1px;
}
QToolBar {
    background-color: #0F172A;
    border-bottom: 1px solid #1E293B;
    padding: 4px 8px;
    spacing: 6px;
}
QPushButton {
    background-color: #1E293B;
    color: #CBD5E1;
    border: 1px solid #334155;
    border-radius: 5px;
    padding: 8px 18px;
    font-weight: 600;
    font-size: 9pt;
}
QPushButton:hover {
    background-color: #334155;
    border-color: #475569;
    color: #F1F5F9;
}
QPushButton:pressed { background-color: #0F172A; }
QPushButton:disabled {
    background-color: #1E293B;
    color: #475569;
    border-color: #1E293B;
}
QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox {
    background-color: #0F172A;
    border: 1px solid #334155;
    border-radius: 5px;
    padding: 8px 10px;
    color: #F8FAFC;
    selection-background-color: #1E40AF;
    font-size: 10pt;
}
QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid #00F0FF;
}
QLineEdit:hover, QDoubleSpinBox:hover, QSpinBox:hover, QComboBox:hover {
    border: 1px solid #475569;
}
QComboBox::drop-down {
    border: none;
    background-color: #1E293B;
    width: 26px;
    border-top-right-radius: 5px;
    border-bottom-right-radius: 5px;
}
QComboBox QAbstractItemView {
    background-color: #0F172A;
    color: #F1F5F9;
    selection-background-color: #1E3A5F;
    selection-color: #00F0FF;
    border: 1px solid #334155;
    padding: 4px;
    outline: none;
}
QTextEdit {
    background-color: #0B0F19;
    color: #00FF41;
    border: 1px solid #1E293B;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 9pt;
    padding: 6px;
    border-radius: 4px;
}
QTreeWidget {
    background-color: #0F172A;
    color: #E2E8F0;
    border: 1px solid #1E293B;
    border-radius: 4px;
    font-size: 9pt;
    outline: none;
}
QTreeWidget::item {
    padding: 6px 8px;
    border-bottom: 1px solid #1E293B;
}
QTreeWidget::item:selected {
    background-color: #1E3A5F;
    color: #00F0FF;
}
QTreeWidget::item:hover {
    background-color: #1E293B;
}
QScrollArea { border: none; }
QScrollBar:vertical {
    background-color: #0F172A;
    width: 8px;
    border-radius: 4px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background-color: #334155;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover { background-color: #475569; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background-color: #0F172A;
    height: 8px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal {
    background-color: #334155;
    border-radius: 4px;
    min-width: 30px;
}
QStatusBar {
    background-color: #0B0F19;
    color: #64748B;
    border-top: 1px solid #1E293B;
    font-size: 8pt;
    padding: 2px 8px;
}
QSplitter::handle { background-color: #1E293B; width: 1px; }
"""


class CollapsibleGroupBox(QGroupBox):
    toggled = Signal(bool)
    def __init__(self, title: str, collapsed: bool = False):
        super().__init__(title)
        self.setCheckable(True)
        self.setChecked(not collapsed)
        self.setStyleSheet("""
            QGroupBox {
                border: 1px solid #1E293B;
                border-radius: 6px;
                margin-top: 14px;
                font-weight: 600;
                color: #94A3B8;
                padding-top: 18px;
                background-color: rgba(15, 23, 42, 160);
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 6px;
                color: #38BDF8;
                font-size: 9pt;
                letter-spacing: 1px;
            }
            QGroupBox::indicator {
                width: 14px;
                height: 14px;
            }
        """)
        self.toggled.connect(self._on_toggle)
        self._content_visible = not collapsed

    def _on_toggle(self, checked: bool):
        self._content_visible = checked
        for child in self.findChildren(QWidget):
            if child != self:
                child.setVisible(checked)

    def show_content(self, visible: bool):
        self._content_visible = visible
        self.setChecked(visible)


class PropertiesPanel(QScrollArea):
    hole_selected_from_panel = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setMinimumWidth(280)
        content = QWidget()
        self.layout = QVBoxLayout(content)
        self.layout.setSpacing(6)
        self.layout.setContentsMargins(6, 6, 6, 6)

        self.empty_label = QLabel("\n  Seleccione un taladro\n  en el visor 3D\n  para ver sus propiedades.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet("color: #475569; font-size: 10pt; padding: 30px;")
        self.layout.addWidget(self.empty_label)

        self.geo_box = CollapsibleGroupBox("GEOMETRIA")
        self.geo_form = QFormLayout()
        self.geo_id = QLabel("---")
        self.geo_xy = QLabel("---")
        self.geo_diam = QLabel("---")
        self.geo_long = QLabel("---")
        self.geo_burden = QLabel("---")
        self.geo_spacing = QLabel("---")
        self.geo_taco = QLabel("---")
        self.geo_inclinacion = QLabel("---")
        for lbl, w in [("ID:", self.geo_id), ("Posicion:", self.geo_xy), ("Diametro:", self.geo_diam),
                       ("Longitud:", self.geo_long), ("Burden:", self.geo_burden), ("Espaciamiento:", self.geo_spacing),
                       ("Taco:", self.geo_taco), ("Inclinacion:", self.geo_inclinacion)]:
            w.setStyleSheet("color: #E2E8F0; font-weight: bold;")
            self.geo_form.addRow(lbl, w)
        self.geo_box.setLayout(self.geo_form)
        self.layout.addWidget(self.geo_box)

        self.rock_box = CollapsibleGroupBox("GEOMECANICA")
        self.rock_form = QFormLayout()
        self.rock_ucs = QLabel("---")
        self.rock_rqd = QLabel("---")
        self.rock_dens = QLabel("---")
        self.rock_trac = QLabel("---")
        self.rock_young = QLabel("---")
        for lbl, w in [("UCS:", self.rock_ucs), ("RQD:", self.rock_rqd), ("Densidad:", self.rock_dens),
                       ("Traccion:", self.rock_trac), ("Young:", self.rock_young)]:
            w.setStyleSheet("color: #E2E8F0; font-weight: bold;")
            self.rock_form.addRow(lbl, w)
        self.rock_box.setLayout(self.rock_form)
        self.layout.addWidget(self.rock_box)

        self.exp_box = CollapsibleGroupBox("EXPLOSIVO")
        self.exp_form = QFormLayout()
        self.exp_nombre = QLabel("---")
        self.exp_dens = QLabel("---")
        self.exp_vod = QLabel("---")
        self.exp_presion = QLabel("---")
        self.exp_choque = QLabel("---")
        self.exp_gas = QLabel("---")
        for lbl, w in [("Tipo:", self.exp_nombre), ("Densidad:", self.exp_dens), ("VOD:", self.exp_vod),
                       ("P. Detonacion:", self.exp_presion), ("En. Choque:", self.exp_choque), ("En. Gas:", self.exp_gas)]:
            w.setStyleSheet("color: #E2E8F0; font-weight: bold;")
            self.exp_form.addRow(lbl, w)
        self.exp_box.setLayout(self.exp_form)
        self.layout.addWidget(self.exp_box)

        self.tie_box = CollapsibleGroupBox("AMARRE")
        self.tie_form = QFormLayout()
        self.tie_retardo = QLabel("---")
        self.tie_row = QLabel("---")
        self.tie_col = QLabel("---")
        self.tie_booster = QLabel("---")
        for lbl, w in [("Retardo:", self.tie_retardo), ("Fila:", self.tie_row), ("Columna:", self.tie_col),
                       ("Booster:", self.tie_booster)]:
            w.setStyleSheet("color: #E2E8F0; font-weight: bold;")
            self.tie_form.addRow(lbl, w)
        self.tie_box.setLayout(self.tie_form)
        self.layout.addWidget(self.tie_box)

        self.deck_box = CollapsibleGroupBox("DECKS DE CARGA")
        self.deck_label = QLabel("  Sin decks configurados.")
        self.deck_label.setStyleSheet("color: #64748B;")
        self.deck_label.setWordWrap(True)
        dl = QVBoxLayout()
        dl.addWidget(self.deck_label)
        self.deck_box.setLayout(dl)
        self.layout.addWidget(self.deck_box)

        self.layout.addStretch()
        self.setWidget(content)
        self.clear_panel()

    def clear_panel(self):
        self.empty_label.setVisible(True)
        self.geo_box.setVisible(False)
        self.rock_box.setVisible(False)
        self.exp_box.setVisible(False)
        self.tie_box.setVisible(False)
        self.deck_box.setVisible(False)

    def show_hole_properties(self, dh: Drillhole):
        self.empty_label.setVisible(False)
        self.geo_box.setVisible(True)
        self.rock_box.setVisible(True)
        self.exp_box.setVisible(True)
        self.tie_box.setVisible(True)
        self.deck_box.setVisible(True)

        self.geo_id.setText(dh.id)
        self.geo_xy.setText(f"X={dh.x:.1f}  Y={dh.y:.1f}  Z={dh.z:.1f}")
        self.geo_diam.setText(f"{dh.diametro_mm:.0f} mm")
        self.geo_long.setText(f"{dh.longitud_total_m:.2f} m")
        self.geo_burden.setText(f"{dh.burden_real_m:.2f} m")
        self.geo_spacing.setText(f"{dh.espaciamiento_m:.2f} m")
        self.geo_taco.setText(f"{dh.taco_m:.2f} m")
        self.geo_inclinacion.setText(f"{dh.inclinacion_deg:.1f} deg / Az {dh.azimut_deg:.1f} deg")

        self.rock_ucs.setText(f"{dh.rock.ucs_mpa:.0f} MPa")
        self.rock_rqd.setText(f"{dh.rock.rqd_pct:.0f} %")
        self.rock_dens.setText(f"{dh.rock.densidad_tm3:.2f} t/m3")
        self.rock_trac.setText(f"{dh.rock.resistencia_traccion_mpa:.1f} MPa")
        self.rock_young.setText(f"{dh.rock.modulo_young_gpa:.0f} GPa")

        self.exp_nombre.setText(dh.explosive.nombre)
        self.exp_dens.setText(f"{dh.explosive.densidad_gcc:.2f} g/cc")
        self.exp_vod.setText(f"{dh.explosive.vod_ms:.0f} m/s")
        self.exp_presion.setText(f"{dh.explosive.presion_detonacion_gpa:.1f} GPa")
        self.exp_choque.setText(f"{dh.explosive.energia_choque_pct:.0f} %")
        self.exp_gas.setText(f"{dh.explosive.energia_gas_pct:.0f} %")

        self.tie_retardo.setText(f"{dh.delay_ms:.0f} ms")
        self.tie_row.setText(str(dh.row + 1))
        self.tie_col.setText(str(dh.col + 1))
        self.tie_booster.setText(f"{dh.booster_type} @ Z={dh.booster_z:.1f} m")

        if dh.decks:
            lines = []
            for i, dk in enumerate(dh.decks):
                lines.append(f"  Deck {i+1}: {dk.explosive[:20]}")
                lines.append(f"    {dk.start_depth_m:.1f} - {dk.end_depth_m:.1f} m")
                lines.append(f"    Taco: {dk.stemming_intermedio_m:.1f} m")
            self.deck_label.setText("\n".join(lines))
        else:
            self.deck_label.setText("  Carga simple (sin decks).")


class ProjectExplorer(QTreeWidget):
    def __init__(self):
        super().__init__()
        self.setHeaderLabel("EXPLORADOR DEL PROYECTO")
        self.setAnimated(True)
        self.setIndentation(16)

        topo = QTreeWidgetItem(self, ["Topografia"])
        topo.setExpanded(True)
        QTreeWidgetItem(topo, ["Topografia.csv"])
        QTreeWidgetItem(topo, ["Superficie DXF"])

        bloques = QTreeWidgetItem(self, ["Modelo de Bloques"])
        bloques.setExpanded(True)
        QTreeWidgetItem(bloques, ["Bloques_UCS.csv"])
        QTreeWidgetItem(bloques, ["Kriging 3D"])

        mallas = QTreeWidgetItem(self, ["Mallas de Voladura"])
        mallas.setExpanded(True)
        QTreeWidgetItem(mallas, ["Malla 3x5 (15 taladros)"])
        QTreeWidgetItem(mallas, ["Malla 5x8 (40 taladros)"])

        zonas = QTreeWidgetItem(self, ["Zonas de Exclusion"])
        QTreeWidgetItem(zonas, ["Falla Geologica"])
        QTreeWidgetItem(zonas, ["Buffer Talud"])

        self.itemClicked.connect(self._on_item_click)

    def _on_item_click(self, item, col):
        parent = item.parent()
        if parent and parent.text(0) == "Mallas de Voladura":
            main = self.window()
            if hasattr(main, 'generate_parametric_mesh'):
                if "15" in item.text(0):
                    main.generate_parametric_mesh(3, 5)
                elif "40" in item.text(0):
                    main.generate_parametric_mesh(5, 8)


class ConsolePanel(QTextEdit):
    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.setPlaceholderText("Consola del sistema...")

    def log(self, message: str, level: str = "INFO"):
        ts = datetime.now().strftime("%H:%M:%S")
        prefix_map = {"INFO": "[>>]", "OK": "[OK]", "WARN": "[!!]", "ERROR": "[XX]", "CAD": "[CA]"}
        prefix = prefix_map.get(level, "[>>]")
        color_map = {"INFO": "#94A3B8", "OK": "#22C55E", "WARN": "#F59E0B", "ERROR": "#EF4444", "CAD": "#00F0FF"}
        color = color_map.get(level, "#94A3B8")
        html = f'<span style="color:#475569;">[{ts}]</span> <span style="color:{color};font-weight:bold;">{prefix}</span> <span style="color:#E2E8F0;">{message}</span><br>'
        self.insertHtml(html)
        scroll = self.verticalScrollBar()
        if scroll:
            scroll.setValue(scroll.maximum())


class RibbonToolBar(QToolBar):
    action_triggered = Signal(str)

    def __init__(self):
        super().__init__("Ribbon")
        self.setMovable(False)
        self.setIconSize(QSize(16, 16))

        tools = [
            ("MEDIR 3D", "ruler"), ("POLIGONO", "polygon"), ("MALLA", "mesh"),
            ("AUTO-CARGUIO", "autoload"), ("TIE-UP", "tieup"),
            ("HEAVE", "heave"), ("REPORTE", "report")
        ]
        for label, action_id in tools:
            btn = QPushButton(f"  {label}  ")
            btn.setFlat(True)
            btn.setMinimumHeight(32)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #64748B;
                    border: 1px solid transparent;
                    border-radius: 4px;
                    padding: 4px 14px;
                    font-size: 9pt;
                    font-weight: 600;
                    font-family: 'Courier New', monospace;
                }
                QPushButton:hover {
                    background-color: #1E293B;
                    color: #E2E8F0;
                    border: 1px solid #334155;
                }
                QPushButton:pressed {
                    background-color: #1E3A5F;
                    color: #00F0FF;
                    border: 1px solid #00F0FF;
                }
            """)
            btn.clicked.connect(lambda checked, aid=action_id: self.action_triggered.emit(aid))
            self.addWidget(btn)

        self.addSeparator()
        self.info = QLabel("  X-BLAST Enterprise v2.0  ")
        self.info.setStyleSheet("color: #475569; font-family: 'Courier New'; font-size: 8pt; letter-spacing: 1px;")
        self.addWidget(self.info)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("X-BLAST Enterprise v2.0 — Gemelo Digital D&B")
        self.resize(1600, 900)
        self.setStyleSheet(QSS_ENTERPRISE)

        icon_p = Path(__file__).parent / "X-BLAST.png"
        if icon_p.exists():
            self.setWindowIcon(QIcon(str(icon_p)))

        self.taladros: List[Drillhole] = []
        self.selected_hole: Optional[Drillhole] = None
        self._cad_actors: List[object] = []
        self._label_actors: List[object] = []

        self._setup_docks()
        self._setup_central()
        self._setup_ribbon()
        self._connect_signals()

        self.console.log("X-BLAST Enterprise v2.0 inicializado", "OK")
        self.statusBar().showMessage("X-BLIST Enterprise | Listo | Coord: (0, 0, 0)")

    def _setup_ribbon(self):
        self.ribbon = RibbonToolBar()
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.ribbon)

    def _setup_docks(self):
        self.explorer_dock = QDockWidget("EXPLORADOR DEL PROYECTO", self)
        self.explorer_dock.setWidget(ProjectExplorer())
        self.explorer_dock.setMinimumWidth(220)
        self.explorer_dock.setFeatures(QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.explorer_dock)

        self.props_dock = QDockWidget("PROPIEDADES DEL TALADRO", self)
        self.props_panel = PropertiesPanel()
        self.props_dock.setWidget(self.props_panel)
        self.props_dock.setMinimumWidth(280)
        self.props_dock.setFeatures(QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.props_dock)

        self.console_dock = QDockWidget("CONSOLA", self)
        self.console = ConsolePanel()
        self.console_dock.setWidget(self.console)
        self.console_dock.setMinimumHeight(120)
        self.console_dock.setFeatures(QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.console_dock)

    def _setup_central(self):
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.plotter = QtInteractor(central)
        self.plotter.set_background("#111111")
        self.plotter.add_axes(
            color="#CBD5E1", x_color="#EF4444", y_color="#22C55E", z_color="#3B82F6",
            line_width=1.5, labels_off=False,
        )
        self.plotter.show_grid(
            color="#334155", font_size=9, font_family="courier",
            location="outer", grid="back", all_edges=True,
        )
        layout.addWidget(self.plotter.interactor)
        self.setCentralWidget(central)

    def _connect_signals(self):
        self.ribbon.action_triggered.connect(self._on_ribbon_action)
        self.plotter.enable_cell_picking(
            callback=self._on_cell_picked,
            show=False, show_message=False, color="#00F0FF",
        )

    def _on_ribbon_action(self, action_id: str):
        msgs = {
            "ruler": "MEDIR 3D: Seleccione 2 puntos en el visor",
            "polygon": "POLIGONO: Trace puntos para delimitar zona",
            "mesh": "Generando malla parametrica...",
            "autoload": "Auto-Carguio: Asignando explosivos por estrato...",
            "tieup": "Tie-Up: Configure el amarre en el panel",
            "heave": "Simulacion Heave: Deformando cara libre...",
            "report": "Generando Reporte PDF..."
        }
        self.console.log(msgs.get(action_id, f"Accion: {action_id}"), "CAD" if action_id in ("ruler", "polygon") else "INFO")

        if action_id == "mesh":
            self.generate_parametric_mesh(3, 5)
        elif action_id == "report":
            self._generate_report()

    def _on_cell_picked(self, mesh):
        if mesh is None:
            return
        try:
            if "hole_id" in mesh.cell_data:
                hid = str(mesh.cell_data["hole_id"][0])
                dh = next((h for h in self.taladros if h.id == hid), None)
                if dh:
                    self._select_hole(dh)
        except Exception:
            pass

    def _select_hole(self, dh: Drillhole):
        if self.selected_hole is not None:
            try:
                if self.selected_hole.actor:
                    self.selected_hole.actor.GetProperty().SetColor(
                        self.selected_hole.actor_color[0],
                        self.selected_hole.actor_color[1],
                        self.selected_hole.actor_color[2],
                    )
                    self.selected_hole.actor.GetProperty().SetOpacity(0.9)
            except Exception:
                pass
        self.selected_hole = dh
        try:
            dh.actor.GetProperty().SetColor(1.0, 1.0, 0.0)
            dh.actor.GetProperty().SetOpacity(1.0)
        except Exception:
            pass
        self.props_panel.show_hole_properties(dh)
        coords = f"X={dh.x:.1f} Y={dh.y:.1f} Z={dh.z:.1f}"
        self.statusBar().showMessage(f"X-BLAST | Taladro: {dh.id} | {coords}")
        self.console.log(f"Taladro seleccionado: {dh.id} | Carga: {dh.charge_mass_kg:.1f} kg | Delay: {dh.delay_ms:.0f} ms", "CAD")

    def _generate_report(self):
        try:
            from reports.pdf_report import generate_blast_report
            meta = {"project": "Tajo Principal", "responsable": "Felix Bautista", "company": "Minera UNA Puno", "mine": "Sector Norte", "labor": "Nivel 2425", "date": datetime.now().strftime("%Y-%m-%d")}
            geo = {"burden_m": 4.5, "spacing_m": 5.0, "diameter_mm": 102, "bench_height_m": 12, "subdrilling_m": 1.0, "num_rows": 3, "num_cols": 5}
            lc = {"column_explosive": "ANFO Pesado (HA 46)", "stemming_length_m": 3.0, "density": 1.15, "vod": 5200, "booster_type": "Pentolita 150g", "booster_position": "Fondo"}
            sc = {"surface_delay": "MS 42 ms", "bottom_delay": "NONEL 17 ms", "hole_interval_ms": 25}
            output_dir = str(Path(__file__).parent / "reports_output")
            path = generate_blast_report(grid_params=geo, loading_config=lc, sequence_config=sc, metadata=meta, report_type="executive", output_dir=output_dir)
            self.console.log(f"PDF generado: {path}", "OK")
        except Exception as e:
            self.console.log(f"Error PDF: {e}", "ERROR")

    def generate_parametric_mesh(self, rows: int = 3, cols: int = 5):
        self.plotter.clear()
        self._cad_actors = []
        self._label_actors = []
        self.taladros = []
        self.selected_hole = None
        self.props_panel.clear_panel()

        b = 4.5
        s = 5.0
        d = 102.0
        bh = 12.0
        sd = 1.0
        stemming = 3.0
        hole_len = bh + sd
        charge_len = hole_len - stemming
        if charge_len <= 0:
            QMessageBox.critical(self, "Error", "Taco > banco")
            return

        self.plotter.add_axes(
            color="#CBD5E1", x_color="#EF4444", y_color="#22C55E", z_color="#3B82F6",
            line_width=1.5,
        )
        self.plotter.show_grid(
            color="#334155", font_size=9, font_family="courier",
            location="outer", grid="back", all_edges=True,
        )

        extent_x = s * (cols + 1)
        extent_y = b * (rows + 1)

        ground = pv.Plane(
            center=(extent_x / 2, extent_y / 2, 0),
            direction=(0, 0, 1),
            i_size=extent_x * 1.2,
            j_size=extent_y * 1.2,
        )
        self.plotter.add_mesh(ground, color="#1A2332", opacity=0.25, name="ground")

        freeface_y = -b
        face = pv.Plane(
            center=(extent_x / 2, freeface_y, -bh / 2),
            direction=(0, 1, 0),
            i_size=extent_x * 1.3,
            j_size=bh * 2.5,
        )
        self.plotter.add_mesh(face, color="#1E3A5F", opacity=0.06, name="freeface")

        rad = d / 2000.0
        interval = 25
        hole_num = 0

        TYPE_COLORS = {
            "PRODUCCION": ((0.85, 0.2, 0.2), "Prod"),
            "ARRANQUE": ((0.85, 0.2, 0.2), "Arr"),
            "AYUDA": ((0.9, 0.55, 0.1), "Ayu"),
            "CUADRADOR": ((0.1, 0.6, 0.85), "Cua"),
        }

        for row in range(rows):
            for col in range(cols):
                hole_num += 1
                x = col * s + (s / 2 if row % 2 else 0)
                y = row * b
                hid = f"T-{hole_num:02d}"
                cc = TYPE_COLORS.get("PRODUCCION", ((0.85, 0.2, 0.2), "Prod"))[0]

                sc = pv.Cylinder(center=np.array([x, y, -stemming / 2]), direction=(0, 0, 1), radius=rad * 1.05, height=stemming, resolution=16)
                sa = self.plotter.add_mesh(sc, color="#64748B", opacity=0.85, name=f"stem_{row}_{col}")
                sc.cell_data["hole_id"] = [hid] * sc.n_cells

                cr = pv.Cylinder(center=np.array([x, y, -stemming - charge_len / 2]), direction=(0, 0, 1), radius=rad, height=charge_len, resolution=16)
                ca = self.plotter.add_mesh(cr, color=cc, opacity=0.9, pickable=True, name=f"charge_{row}_{col}")
                cr.cell_data["hole_id"] = [hid] * cr.n_cells

                delay = row * cols * interval + col * interval
                charge_kg = charge_len * 1.15 * math.pi * rad**2 * 1.15 * 1000

                rock = RockMass(ucs_mpa=80 + row * 15, rqd_pct=55 + col * 5, densidad_tm3=2.6, resistencia_traccion_mpa=6 + row * 2, modulo_young_gpa=20 + row * 3)
                explosive = Explosive(nombre="ANFO Pesado (HA 46)", densidad_gcc=1.15, vod_ms=5200, presion_detonacion_gpa=8.5)

                dh = Drillhole(
                    id=hid, x=x, y=y, z=0.0, diametro_mm=d, longitud_total_m=hole_len,
                    inclinacion_deg=0.0, azimut_deg=0.0, burden_real_m=b, espaciamiento_m=s,
                    taco_m=stemming, subperforacion_m=sd, row=row, col=col,
                    delay_ms=delay, charge_mass_kg=charge_kg, hole_type="PRODUCCION",
                    rock=rock, explosive=explosive, actor=ca, stem_actor=sa,
                    booster_type="Pentolita 150g", booster_z=0.0,
                )
                dh.actor_color = cc
                self.taladros.append(dh)

        pts = np.array([dh.collar for dh in self.taladros])
        labels = [dh.id for dh in self.taladros]
        self.plotter.add_point_labels(
            pts, labels, font_size=10, text_color="#FBBF24",
            bold=True, point_size=1, shape_opacity=0,
            name="hole_labels", always_visible=True,
        )

        self.plotter.reset_camera()
        vol = rows * cols * b * s * bh
        carga_total = len(self.taladros) * charge_kg
        pf = carga_total / vol if vol > 0 else 0
        p80 = 8.0 * (b * s * bh)**0.167 * (115.0 / 100.0)**0.633 / (pf**0.8) * 15.0 if pf > 0 else 0

        self.console.log(f"Malla generada: {len(self.taladros)} taladros | PF={pf:.3f} kg/m3 | P80={p80:.0f} mm", "OK")
        self.statusBar().showMessage(f"X-BLAST | {len(self.taladros)} taladros | PF={pf:.3f} | P80={p80:.0f}mm")

    def _clear_cad(self):
        for name in ["ruler_line", "ruler_text", "boundary", "profile_line", "profile_text", "angle_line1", "angle_line2", "angle_text", "grid_overlay"]:
            try:
                self.plotter.remove_actor(name)
            except Exception:
                pass


if __name__ == "__main__":
    import os
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    icon_p = Path(__file__).parent / "X-BLAST.png"
    if icon_p.exists():
        app.setWindowIcon(QIcon(str(icon_p)))
    w = MainWindow()
    w.show()
    w.generate_parametric_mesh(3, 5)
    sys.exit(app.exec())

# ESPERANDO COMANDO "EJECUTA FASE 2" PARA PROGRAMAR LOS 5 MOTORES BLACKBOX.
