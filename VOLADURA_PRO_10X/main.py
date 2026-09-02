import sys, time
import math
import numpy as np
import pyvista as pv
from pyvistaqt import QtInteractor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QMessageBox, QLabel, QMenu, QDockWidget, QTreeWidget,
    QTreeWidgetItem, QScrollArea, QGroupBox, QFormLayout,
    QPushButton, QTextEdit, QFileDialog, QComboBox
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtGui import QIcon, QAction, QFont, QKeySequence, QPixmap
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List
import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from config import WINDOW_WIDTH, WINDOW_HEIGHT, DEFAULT_GRID_PARAMS, GRID_ROWS, GRID_COLS, PYVISTA_BACKGROUND_COLOR, PDF_OUTPUT_DIRECTORY, PDF_OUTPUT_FILENAME
from gui.tabbed_panels import SciFiTabWidget
from gui.cad_toolbar import CADToolBar, ToolMode
from gui.console_log import ConsoleLog


def find_asset(name: str) -> Optional[Path]:
    """Busca recursos gráficos en el directorio local o en la carpeta assets."""
    for base in [
        Path(__file__).resolve().parent,
        Path(__file__).resolve().parent / "assets",
        Path(__file__).resolve().parent.parent / "assets",
        Path("assets"),
        Path("../assets")
    ]:
        candidate = base / name
        if candidate.exists():
            return candidate
    return None


@dataclass
class Drillhole:
    id: str
    x: float
    y: float
    z: float
    burden: float = 0.0
    espaciamiento: float = 0.0
    longitud: float = 0.0
    taco: float = 0.0
    tipo_explosivo: str = "ANFO"
    cebo: str = "Pentolita 150g"
    row: int = 0
    col: int = 0
    delay_ms: float = 0.0
    charge_mass_kg: float = 0.0
    hole_type: str = "PRODUCCION"
    actor: Optional[object] = field(default=None, repr=False)
    stem_actor: Optional[object] = field(default=None, repr=False)
    selected: bool = False
    diametro_mm: float = 102.0
    burden_real_m: float = 4.5
    espaciamiento_m: float = 5.0
    inclinacion_deg: float = 0.0
    azimut_deg: float = 0.0
    subperforacion_m: float = 1.0
    p80_mm: float = 0.0
    x50_cm: float = 0.0
    vol_kg: float = 0.0

    @property
    def collar(self) -> np.ndarray:
        return np.array([self.x, self.y, self.z], dtype=np.float64)

    @property
    def toe(self) -> np.ndarray:
        return np.array([self.x, self.y, self.z - self.longitud], dtype=np.float64)

    def distance_to_point(self, point: np.ndarray) -> float:
        pt = np.asarray(point[:3], dtype=np.float64)
        return float(np.linalg.norm(pt - self.collar))


QSS = """
QMainWindow, QWidget {
    background-color: #0B0F19;
    color: #F1F5F9;
    font-family: 'Segoe UI', 'Inter', sans-serif;
    font-size: 10pt;
}

QDockWidget {
    background-color: #1E293B;
    color: #E2E8F0;
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
    border-radius: 8px;
    margin-top: 14px;
    font-weight: 600;
    color: #94A3B8;
    padding-top: 18px;
    background-color: rgba(15, 23, 42, 180);
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
    color: #38BDF8;
    font-size: 9pt;
    letter-spacing: 1px;
}

QTabWidget::pane {
    border: 1px solid #1E293B;
    background-color: #0B0F19;
    border-radius: 4px;
}
QTabBar::tab {
    background-color: #1E293B;
    color: #64748B;
    border: 1px solid transparent;
    border-bottom: 2px solid transparent;
    padding: 9px 16px;
    margin-right: 1px;
    font-weight: 600;
    font-size: 9pt;
    letter-spacing: 0.5px;
}
QTabBar::tab:selected {
    background-color: #0F172A;
    color: #00F0FF;
    border-bottom: 2px solid #00F0FF;
}
QTabBar::tab:hover {
    background-color: #334155;
    color: #E2E8F0;
}

QDoubleSpinBox, QSpinBox, QComboBox, QLineEdit, QDateTimeEdit {
    background-color: #0F172A;
    border: 1px solid #334155;
    border-radius: 5px;
    padding: 8px 10px;
    color: #F8FAFC;
    selection-background-color: #1E40AF;
    font-size: 10pt;
}
QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus, QLineEdit:focus, QDateTimeEdit:focus {
    border: 1px solid #00F0FF;
}
QDoubleSpinBox:hover, QSpinBox:hover, QComboBox:hover, QLineEdit:hover, QDateTimeEdit:hover {
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
QPushButton:pressed {
    background-color: #0F172A;
}
QPushButton:disabled {
    background-color: #1E293B;
    color: #475569;
    border-color: #1E293B;
}

QTextEdit {
    background-color: #0B0F19;
    color: #00FF41;
    border: 1px solid #1E293B;
    font-family: 'Cascadia Code', 'Fira Code', 'Courier New', monospace;
    font-size: 9pt;
    padding: 6px;
    border-radius: 4px;
}

QTableWidget {
    background-color: #0F172A;
    color: #E2E8F0;
    border: 1px solid #1E293B;
    gridline-color: #1E293B;
    selection-background-color: #1E3A5F;
    selection-color: #00F0FF;
    border-radius: 4px;
    font-size: 9pt;
}
QTableWidget::item {
    padding: 4px 6px;
}
QTableWidget::item:selected {
    background-color: #1E3A5F;
}
QHeaderView::section {
    background-color: #1E293B;
    color: #94A3B8;
    border: 1px solid #1E293B;
    padding: 6px 8px;
    font-weight: 600;
    font-size: 8pt;
    letter-spacing: 0.5px;
}
QHeaderView::section:hover {
    background-color: #334155;
    color: #E2E8F0;
}

QSplitter::handle {
    background-color: #1E293B;
    width: 1px;
}

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
QScrollBar::handle:vertical:hover {
    background-color: #475569;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
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

QMenuBar {
    background-color: #0F172A;
    color: #94A3B8;
    border-bottom: 1px solid #1E293B;
    padding: 2px 4px;
    font-size: 9pt;
}
QMenuBar::item {
    padding: 4px 12px;
    border-radius: 3px;
}
QMenuBar::item:selected {
    background-color: #1E293B;
    color: #00F0FF;
}
QMenu {
    background-color: #0F172A;
    color: #E2E8F0;
    border: 1px solid #334155;
    padding: 4px;
}
QMenu::item {
    padding: 6px 24px 6px 12px;
    border-radius: 3px;
}
QMenu::item:selected {
    background-color: #1E3A5F;
    color: #00F0FF;
}
QMenu::separator {
    height: 1px;
    background-color: #334155;
    margin: 4px 8px;
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
"""


TYPE_COLORS_3D = {
    "PRODUCCION": ((0.85, 0.2, 0.2), "Prod"),
    "ARRANQUE": ((0.85, 0.2, 0.2), "Arranque"),
    "AYUDA": ((0.9, 0.55, 0.1), "Ayuda"),
    "CUADRADOR": ((0.1, 0.6, 0.85), "Cuadrador"),
    "CORONA": ((0.65, 0.1, 0.65), "Corona"),
    "ARRASTRE": ((0.1, 0.7, 0.3), "Arrastre"),
    "ALIVIO": ((0.5, 0.5, 0.5), "Alivio"),
    "PRECORTE": ((0.1, 0.6, 0.85), "Precorte"),
    "CORTE": ((0.9, 0.55, 0.1), "Corte"),
    "DESCABEZADO": ((0.65, 0.1, 0.65), "Descabezado"),
}


class PropertiesPanel(QScrollArea):
    hole_type_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setMinimumWidth(260)
        content = QWidget()
        self.layout = QVBoxLayout(content)
        self.layout.setSpacing(6)
        self.layout.setContentsMargins(6, 6, 6, 6)

        self.empty_label = QLabel("\n  Seleccione un taladro\n  en el visor 3D\n  para ver sus propiedades.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet("color: #475569; font-size: 10pt; padding: 30px;")
        self.layout.addWidget(self.empty_label)

        self.geo_box = QGroupBox("GEOMETRIA")
        gf = QFormLayout()
        self.geo_id = QLabel("---"); self.geo_xy = QLabel("---"); self.geo_diam = QLabel("---")
        self.geo_long = QLabel("---"); self.geo_burden = QLabel("---"); self.geo_spacing = QLabel("---")
        self.geo_taco = QLabel("---"); self.geo_inclinacion = QLabel("---")
        for lbl, w in [("ID:", self.geo_id), ("Posicion:", self.geo_xy), ("Diametro:", self.geo_diam),
                       ("Longitud:", self.geo_long), ("Burden:", self.geo_burden), ("Espaciamiento:", self.geo_spacing),
                       ("Taco:", self.geo_taco), ("Inclinacion:", self.geo_inclinacion)]:
            w.setStyleSheet("color: #E2E8F0; font-weight: bold;")
            gf.addRow(lbl, w)
        self.geo_box.setLayout(gf)
        self.geo_box.setVisible(False)
        self.layout.addWidget(self.geo_box)

        self.type_box = QGroupBox("TIPO DE TALADRO")
        tf = QFormLayout()
        self.type_combo = QComboBox()
        self.type_combo.addItems(["PRODUCCION", "PRECORTE", "CORTE", "DESCABEZADO", "HORIZONTAL", "ARRANQUE", "AYUDA", "CUADRADOR", "CORONA", "ARRASTRE", "ALIVIO"])
        self.type_combo.setStyleSheet("QComboBox{background-color:#0F172A;border:1px solid #334155;border-radius:5px;padding:8px;color:#F8FAFC;}QComboBox:hover{border:1px solid #00F0FF;}")
        self.type_combo.currentTextChanged.connect(self._on_type_changed)
        tf.addRow("Tipo:", self.type_combo)
        self.type_box.setLayout(tf)
        self.type_box.setVisible(False)
        self.layout.addWidget(self.type_box)

        self.load_box = QGroupBox("CARGA / EXPLOSIVO")
        lf = QFormLayout()
        self.load_tipo = QLabel("---"); self.load_exp = QLabel("---")
        self.load_kg = QLabel("---"); self.load_cebo = QLabel("---")
        for lbl, w in [("Tipo:", self.load_tipo), ("Explosivo:", self.load_exp), ("Carga:", self.load_kg), ("Cebo:", self.load_cebo)]:
            w.setStyleSheet("color: #E2E8F0; font-weight: bold;")
            lf.addRow(lbl, w)
        self.load_box.setLayout(lf)
        self.load_box.setVisible(False)
        self.layout.addWidget(self.load_box)

        self.frag_box = QGroupBox("FRAGMENTACION")
        ff = QFormLayout()
        self.frag_p80 = QLabel("---"); self.frag_x50 = QLabel("---"); self.frag_pf = QLabel("---")
        for lbl, w in [("P80 (mm):", self.frag_p80), ("X50 (cm):", self.frag_x50), ("Powder Factor:", self.frag_pf)]:
            w.setStyleSheet("color: #00FF41; font-weight: bold;")
            ff.addRow(lbl, w)
        self.frag_box.setLayout(ff)
        self.frag_box.setVisible(False)
        self.layout.addWidget(self.frag_box)

        self.tie_box = QGroupBox("AMARRE")
        ttf = QFormLayout()
        self.tie_retardo = QLabel("---"); self.tie_fila = QLabel("---"); self.tie_col = QLabel("---")
        for lbl, w in [("Retardo:", self.tie_retardo), ("Fila:", self.tie_fila), ("Columna:", self.tie_col)]:
            w.setStyleSheet("color: #E2E8F0; font-weight: bold;")
            ttf.addRow(lbl, w)
        self.tie_box.setLayout(ttf)
        self.tie_box.setVisible(False)
        self.layout.addWidget(self.tie_box)

        self.layout.addStretch()
        self.setWidget(content)
        self.clear_panel()

    def clear_panel(self):
        self.empty_label.setVisible(True)
        self.geo_box.setVisible(False)
        self.type_box.setVisible(False)
        self.load_box.setVisible(False)
        self.frag_box.setVisible(False)
        self.tie_box.setVisible(False)

    def _on_type_changed(self, new_type):
        self.hole_type_changed.emit(new_type)

    def show_hole_properties(self, dh: Drillhole):
        self.empty_label.setVisible(False)
        self.geo_box.setVisible(True)
        self.type_box.setVisible(True)
        self.load_box.setVisible(True)
        self.frag_box.setVisible(True)
        self.tie_box.setVisible(True)

        self.type_combo.blockSignals(True)
        self.type_combo.setCurrentText(dh.hole_type)
        self.type_combo.blockSignals(False)

        self.geo_id.setText(dh.id)
        self.geo_xy.setText(f"X={dh.x:.1f}  Y={dh.y:.1f}  Z={dh.z:.1f}")
        self.geo_diam.setText(f"{dh.diametro_mm:.0f} mm")
        self.geo_long.setText(f"{dh.longitud:.2f} m")
        self.geo_burden.setText(f"{dh.burden_real_m:.2f} m")
        self.geo_spacing.setText(f"{dh.espaciamiento_m:.2f} m")
        self.geo_taco.setText(f"{dh.taco:.2f} m")
        self.geo_inclinacion.setText(f"{dh.inclinacion_deg:.1f} deg / Az {dh.azimut_deg:.1f} deg")

        self.load_tipo.setText(dh.hole_type)
        self.load_exp.setText(dh.tipo_explosivo)
        self.load_kg.setText(f"{dh.charge_mass_kg:.1f} kg")
        self.load_cebo.setText(dh.cebo)

        self.frag_p80.setText(f"{dh.p80_mm:.0f} mm")
        self.frag_x50.setText(f"{dh.x50_cm:.1f} cm")
        self.frag_pf.setText(f"{dh.charge_mass_kg / (dh.burden_real_m * dh.espaciamiento_m * dh.longitud) if dh.burden_real_m * dh.espaciamiento_m * dh.longitud > 0 else 0:.4f} kg/m3")

        self.tie_retardo.setText(f"{dh.delay_ms:.0f} ms")
        self.tie_fila.setText(str(dh.row + 1))
        self.tie_col.setText(str(dh.col + 1))


class ProjectExplorerTree(QTreeWidget):
    mesh_requested = Signal(int, int)
    file_open_requested = Signal(str)

    def __init__(self):
        super().__init__()
        self.setHeaderLabel("EXPLORADOR DEL PROYECTO")
        self.setAnimated(True)
        self.setIndentation(16)

        self.topo_root = QTreeWidgetItem(self, ["Topografia"])
        self.topo_root.setExpanded(True)
        self.topo_item = QTreeWidgetItem(self.topo_root, ["(sin cargar)"])
        self.topo_item.setForeground(0, QColor("#F59E0B"))

        self.coords_root = QTreeWidgetItem(self, ["Coordenadas de Taladros"])
        self.coords_root.setExpanded(True)
        self.coords_item = QTreeWidgetItem(self.coords_root, ["(sin cargar)"])
        self.coords_item.setForeground(0, QColor("#F59E0B"))

        self.mallas_root = QTreeWidgetItem(self, ["Mallas de Voladura"])
        self.mallas_root.setExpanded(True)
        self.item_malla_default = QTreeWidgetItem(self.mallas_root, ["Malla 3x5 (15 taladros)"])
        self.item_malla_40 = QTreeWidgetItem(self.mallas_root, ["Malla 5x8 (40 taladros)"])
        self.item_malla_personalizada = QTreeWidgetItem(self.mallas_root, ["Malla Personalizada (usar GEOMETRIA)"])

        self.taladros_root = QTreeWidgetItem(self, ["Taladros Individuales"])
        self.taladros_root.setExpanded(False)

        zonas = QTreeWidgetItem(self, ["Zonas de Exclusion"])
        QTreeWidgetItem(zonas, ["Falla Geologica"])

        self.itemClicked.connect(self._on_click)

    def update_topo_status(self, filepath):
        self.topo_item.setText(0, Path(filepath).name)
        self.topo_item.setForeground(0, QColor("#22C55E"))

    def update_coords_status(self, filepath):
        self.coords_item.setText(0, Path(filepath).name)
        self.coords_item.setForeground(0, QColor("#22C55E"))

    def populate_hole_list(self, taladros):
        self.taladros_root.takeChildren()
        for dh in taladros[:50]:
            item = QTreeWidgetItem(self.taladros_root, [f"{dh.id} ({dh.hole_type})"])
            item.setData(0, Qt.UserRole, dh.id)
            cd = TYPE_COLORS_3D.get(dh.hole_type, ((0.85, 0.2, 0.2), "Prod"))
            item.setForeground(0, QColor(*[int(c*255) for c in cd[0]]))

    def _on_click(self, item, col):
        if item == self.item_malla_default:
            self.mesh_requested.emit(3, 5)
        elif item == self.item_malla_40:
            self.mesh_requested.emit(5, 8)


class KpiDockWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        self.fig = Figure(figsize=(5, 7), facecolor="#09090B")
        self.canvas = FigureCanvas(self.fig)
        layout.addWidget(self.canvas)
        self._kpis = {}
        btn_export = QPushButton("EXPORTAR KPI (PNG)")
        btn_export.setStyleSheet("QPushButton{background-color:#1E293B;color:#00F0FF;border:1px solid #334155;border-radius:4px;padding:4px;font-size:8pt;}QPushButton:hover{background-color:#334155;}")
        btn_export.clicked.connect(self._export_png)
        layout.addWidget(btn_export)

    def _export_png(self):
        path, _ = QFileDialog.getSaveFileName(self, "Exportar KPI", "kpi_dashboard.png", "PNG (*.png)")
        if path:
            self.fig.savefig(path, dpi=150, facecolor="#09090B", bbox_inches="tight")

    def update_kpis(self, kpis: dict):
        self._kpis = kpis
        self.fig.clear()
        rows = 3; cols = 2
        gs = self.fig.add_gridspec(rows, cols, hspace=0.35, wspace=0.25, top=0.92, bottom=0.05, left=0.08, right=0.95)
        try:
            n_holes = int(kpis.get("Total Taladros", "0"))
            pf = float(kpis.get("Powder Factor (kg/m3)", "0").replace(",", ""))
            p80_avg = float(kpis.get("P80 Promedio (mm)", "0"))
            x50_avg = float(kpis.get("X50 Promedio (cm)", "0"))
            vol_total = float(kpis.get("Volumen Total (m3)", "0").replace(",", ""))
            ton = float(kpis.get("Toneladas Estimadas", "0").replace(",", "").replace(" t", ""))
            drill_cost = float(kpis.get("Costo Perforacion (USD)", "$0").replace("$", "").replace(",", ""))
            exp_cost = float(kpis.get("Costo Explosivos (USD)", "$0").replace("$", "").replace(",", ""))
            total_cost = float(kpis.get("Costo Total (USD)", "$0").replace("$", "").replace(",", ""))
        except Exception:
            n_holes = 0; pf = 0; p80_avg = 0; x50_avg = 0; vol_total = 0; ton = 0; drill_cost = 0; exp_cost = 0; total_cost = 0

        ax0 = self.fig.add_subplot(gs[0, :])
        ax0.axis("off")
        ax0.text(0.5, 0.65, "DASHBOARD DE KPIs", fontsize=14, fontweight="bold", color="#00F0FF", ha="center", va="center", fontfamily="monospace")
        ax0.text(0.5, 0.25, f"X-BLAST v2.0  |  {n_holes} Taladros", fontsize=9, color="#64748B", ha="center", va="center", fontfamily="monospace")

        ax1 = self.fig.add_subplot(gs[1, 0])
        bars = ax1.bar(["Volumen", "Toneladas", "PF"], [vol_total, ton, pf * 100], color=["#0EA5E9", "#22C55E", "#F59E0B"], width=0.5)
        ax1.set_title("Metricas Principales", fontsize=8, color="#94A3B8", fontfamily="monospace")
        ax1.tick_params(colors="#64748B", labelsize=7)
        ax1.set_facecolor("#0F172A")
        for spine in ax1.spines.values(): spine.set_color("#1E293B")
        for bar, val in zip(bars, [f"{vol_total:,.0f}", f"{ton:,.0f}", f"{pf:.3f}"]):
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height(), val, ha="center", va="bottom", fontsize=6, color="#CBD5E1", fontfamily="monospace")

        ax2 = self.fig.add_subplot(gs[1, 1])
        if total_cost > 0:
            sizes = [drill_cost, exp_cost, total_cost - drill_cost - exp_cost]
            labels = ["Perforacion", "Explosivos", "Otros"]
            colors_pie = ["#6366F1", "#EF4444", "#334155"]
            wedges, texts, autotexts = ax2.pie([s for s in sizes if s > 0], labels=[l for s, l in zip(sizes, labels) if s > 0],
                                                autopct="%1.0f%%", colors=[c for s, c in zip(sizes, colors_pie) if s > 0],
                                                textprops={"fontsize": 6, "color": "#CBD5E1", "fontfamily": "monospace"})
            ax2.set_title("Costos", fontsize=8, color="#94A3B8", fontfamily="monospace")

        ax3 = self.fig.add_subplot(gs[2, 0])
        frag_bars = ax3.bar(["P80", "X50"], [p80_avg, x50_avg * 10], color=["#00FF41", "#38BDF8"], width=0.4)
        ax3.set_title("Fragmentacion", fontsize=8, color="#94A3B8", fontfamily="monospace")
        ax3.tick_params(colors="#64748B", labelsize=7)
        ax3.set_facecolor("#0F172A")
        for spine in ax3.spines.values(): spine.set_color("#1E293B")
        for bar, val in zip(frag_bars, [f"{p80_avg:.0f} mm", f"{x50_avg:.1f} cm"]):
            ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height(), val, ha="center", va="bottom", fontsize=6, color="#CBD5E1", fontfamily="monospace")

        ax4 = self.fig.add_subplot(gs[2, 1])
        ax4.axis("off")
        keys_to_show = ["Burden (m)", "Espaciamiento (m)", "Diametro (mm)", "Altura Banco (m)", "Carga Total (kg)", "Tiempo Disparo (ms)"]
        y_pos = 0.9
        for k in keys_to_show:
            v = kpis.get(k, "---")
            ax4.text(0.1, y_pos, k, fontsize=7, color="#64748B", fontfamily="monospace", va="center")
            ax4.text(0.9, y_pos, str(v), fontsize=7, color="#38BDF8", fontfamily="monospace", va="center", ha="right")
            y_pos -= 0.14

        self.canvas.draw()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("X-BLAST v2.0 — Enterprise Mining Suite")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(QSS)
        for ico in ["X-BLAST.ico", "X-BLAST.PNG", "X-BLAST.png"]:
            p = find_asset(ico)
            if p and p.exists():
                self.setWindowIcon(QIcon(str(p)))
                break

        self.blast_holes = []
        self.taladros: List[Drillhole] = []
        self.selected_hole: Optional[Drillhole] = None
        self._ruler_points: List[np.ndarray] = []
        self.animator = None
        self._cad_actors = []
        self._label_actors = []
        self._setup_docks()
        self._setup_central()
        self._setup_menu()
        self._connect()
        self._log("X-BLAST v2.0 Enterprise iniciado", "SUCCESS")

    def _setup_docks(self):
        self.explorer_dock = QDockWidget("EXPLORADOR DE PROYECTOS", self)
        self.explorer_tree = ProjectExplorerTree()
        self.explorer_dock.setWidget(self.explorer_tree)
        self.explorer_dock.setMinimumWidth(200)
        self.explorer_dock.setFeatures(QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.explorer_dock)

        self.props_dock = QDockWidget("PROPIEDADES DE TALADROS", self)
        self.props_panel = PropertiesPanel()
        self.props_dock.setWidget(self.props_panel)
        self.props_dock.setMinimumWidth(260)
        self.props_dock.setFeatures(QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.props_dock)

        self.console_dock = QDockWidget("CONSOLA", self)
        self.console = ConsoleLog()
        self.console_dock.setWidget(self.console)
        self.console_dock.setMinimumHeight(120)
        self.console_dock.setFeatures(QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.console_dock)

        self.kpi_dock = QDockWidget("KPIs", self)
        self.kpi_widget = KpiDockWidget()
        self.kpi_dock.setWidget(self.kpi_widget)
        self.kpi_dock.setMinimumWidth(260)
        self.kpi_dock.setFeatures(QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.kpi_dock)

        self.tabs_dock = QDockWidget("CONTROLES", self)
        self.tabs = SciFiTabWidget()
        self.tabs_dock.setWidget(self.tabs)
        self.tabs_dock.setMinimumWidth(330)
        self.tabs_dock.setFeatures(QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.tabs_dock)
        self.tabifyDockWidget(self.explorer_dock, self.tabs_dock)
        self.explorer_dock.raise_()

    def _setup_menu(self):
        menu_bar = self.menuBar()
        view_menu = menu_bar.addMenu("&Ver")

        def _make_dock_action(dock, title):
            action = QAction(title, self)
            action.setCheckable(True)
            action.setChecked(dock.isVisible())
            action.triggered.connect(lambda checked, d=dock: d.setVisible(checked))
            dock.visibilityChanged.connect(action.setChecked)
            return action

        self.acc_explorer = _make_dock_action(self.explorer_dock, "&1. Explorador de Proyectos")
        self.acc_explorer.setShortcut(QKeySequence("Ctrl+1"))
        view_menu.addAction(self.acc_explorer)

        self.acc_tabs = _make_dock_action(self.tabs_dock, "&2. Controles")
        self.acc_tabs.setShortcut(QKeySequence("Ctrl+2"))
        view_menu.addAction(self.acc_tabs)

        self.acc_props = _make_dock_action(self.props_dock, "&3. Propiedades de Taladros")
        self.acc_props.setShortcut(QKeySequence("Ctrl+3"))
        view_menu.addAction(self.acc_props)

        self.acc_kpi = _make_dock_action(self.kpi_dock, "&4. KPIs")
        self.acc_kpi.setShortcut(QKeySequence("Ctrl+4"))
        view_menu.addAction(self.acc_kpi)

        self.acc_console = _make_dock_action(self.console_dock, "&5. Consola")
        self.acc_console.setShortcut(QKeySequence("Ctrl+5"))
        view_menu.addAction(self.acc_console)

        view_menu.addSeparator()
        reset_action = QAction("Restablecer Paneles", self)
        reset_action.triggered.connect(self._reset_docks)
        view_menu.addAction(reset_action)

    def _reset_docks(self):
        for dock in [self.explorer_dock, self.tabs_dock, self.console_dock, self.props_dock, self.kpi_dock]:
            dock.setVisible(True)
            if dock not in (self.console_dock,):
                dock.setFloating(False)
        self._log("Paneles restablecidos", "INFO")

    def _setup_central(self):
        central = QWidget()
        cl = QVBoxLayout(central)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)
        self.plotter = QtInteractor(central)
        self.plotter.set_background("#0F172A")
        self.plotter.add_axes(
            color="#CBD5E1",
            x_color="#EF4444",
            y_color="#22C55E",
            z_color="#3B82F6",
            line_width=1.5,
            labels_off=False,
        )
        self.cad = CADToolBar(self)
        cl.addWidget(self.cad)
        cl.addWidget(self.plotter.interactor)
        self.setCentralWidget(central)

    def _connect(self):
        self.tabs.geometry_tab.btn_render.clicked.connect(self._render_3d)
        self.tabs.reporting_tab.simulate_requested.connect(self._simulate)
        self.tabs.reporting_tab.pdf_requested.connect(self._export_all_reports)
        self.tabs.reporting_tab.report_executive.connect(lambda: self._export_pdf("executive"))
        self.tabs.reporting_tab.report_operational.connect(lambda: self._export_pdf("operational"))
        self.tabs.reporting_tab.report_ssoma.connect(lambda: self._export_pdf("ssoma"))
        self.tabs.reporting_tab.report_loading.connect(lambda: self._export_pdf("loading"))
        self.tabs.loading_tab.btn_preview.clicked.connect(self._preview_loading)
        self.cad.mode_changed.connect(self._on_cad_mode)
        self.explorer_tree.mesh_requested.connect(self._generate_mesh_from_tree)
        self.props_panel.hole_type_changed.connect(self._on_hole_type_changed)
        self.tabs.geometry_tab.topo_loaded.connect(self._on_topo_loaded)
        self.tabs.geometry_tab.coords_loaded.connect(self._on_coords_loaded)
        self.plotter.enable_point_picking(callback=self._on_pick, show_message=False, left_clicking=True)
        self._log("X-BLAST v2.0 iniciado", "SUCCESS")

    def _generate_mesh_from_tree(self, rows, cols):
        self.tabs.geometry_tab.rows.setValue(rows)
        self.tabs.geometry_tab.cols.setValue(cols)
        self._render_3d()

    def _log(self, t, l="INFO"):
        self.console.log(t, l)

    def _on_cad_mode(self, m):
        msgs = {
            "ruler": "MEDIR: Clic 2 pts",
            "ore_boundary": "LIMITE: Clic pts",
            "energy_heatmap": "HEATMAP activado",
            "profile": "PERFIL: Clic 2 pts",
            "grid": "CUADRICULA activada",
            "angle": "ANGULO: Clic 3 pts",
            "none": "CAD off",
        }
        self._log(msgs.get(m, ""), "CAD")
        if m == "energy_heatmap":
            self._heatmap()
        elif m == "grid":
            self._apply_grid_overlay()

    def _on_pick(self, point):
        if self.cad.mode in (ToolMode.RULER, ToolMode.ORE_BOUNDARY, ToolMode.PROFILE, ToolMode.ANGLE):
            self.cad.handle_click(point, self.plotter)
            return
        if not self.blast_holes:
            return
        dists = [np.linalg.norm(np.array(point[:2]) - np.array([h.collar[0], h.collar[1]])) for h in self.blast_holes]
        idx = int(np.argmin(dists))
        self.tabs.loading_tab.select_hole(str(self.blast_holes[idx].hole_id))
        self.tabs.setCurrentIndex(2)
        self._log(f"Taladro T-{self.blast_holes[idx].hole_id} seleccionado", "CAD")
        if idx < len(self.taladros):
            self._update_properties_panel(self.taladros[idx])

    def _on_topo_loaded(self, filepath):
        self.explorer_tree.update_topo_status(filepath)
        self._log(f"Topografia cargada: {Path(filepath).name}", "SUCCESS")

    def _on_coords_loaded(self, filepath):
        self.explorer_tree.update_coords_status(filepath)
        self._log(f"Coordenadas cargadas: {Path(filepath).name}", "SUCCESS")

    def _update_properties_panel(self, dh: Drillhole):
        self.selected_hole = dh
        self.props_panel.show_hole_properties(dh)
        coords = f"X={dh.x:.1f} Y={dh.y:.1f} Z={dh.z:.1f}"
        self.statusBar().showMessage(f"X-BLAST | Taladro: {dh.id} | {coords}")

    def _on_hole_type_changed(self, new_type):
        dh = self.selected_hole
        if dh is None:
            return
        dh.hole_type = new_type
        try:
            cd = TYPE_COLORS_3D.get(new_type, ((0.85, 0.2, 0.2), "Prod"))
            dh.actor.GetProperty().SetColor(*cd[0])
            self._log(f"Taladro {dh.id} tipo cambiado a {new_type}", "INFO")
        except Exception:
            pass
        self._update_properties_panel(dh)
        kpi_data = self._rebuild_kpis()
        if kpi_data:
            self.tabs.reporting_tab.update_kpis(kpi_data)
            self.kpi_widget.update_kpis(kpi_data)

    def _rebuild_kpis(self):
        if not self.taladros:
            return None
        p = self.tabs.geometry_tab.get_params()
        b = p["burden_m"]; s = p["spacing_m"]; bh = p["bench_height_m"]
        vol = len(self.taladros) * b * s * bh
        carga = sum(dh.charge_mass_kg for dh in self.taladros)
        pf = carga / vol if vol > 0 else 0
        avg_p80 = np.mean([dh.p80_mm for dh in self.taladros]) if self.taladros else 0
        avg_x50 = np.mean([dh.x50_cm for dh in self.taladros]) if self.taladros else 0
        min_p80 = min([dh.p80_mm for dh in self.taladros]) if self.taladros else 0
        max_p80 = max([dh.p80_mm for dh in self.taladros]) if self.taladros else 0
        total_cost_drill = len(self.taladros) * (bh + p["subdrilling_m"]) * 25
        total_cost_explosive = carga * 1.2
        drill_factor = (len(self.taladros) * (bh + p["subdrilling_m"])) / vol if vol > 0 else 0
        hole_types_present = {}
        for dh in self.taladros:
            hole_types_present[dh.hole_type] = hole_types_present.get(dh.hole_type, 0) + 1
        type_summary = " | ".join([f"{t}: {c}" for t, c in hole_types_present.items()])
        kpi_data = {
            "Total Taladros": f"{len(self.taladros)}",
            "Tipos": type_summary,
            "Burden (m)": f"{b:.2f}", "Espaciamiento (m)": f"{s:.2f}",
            "Diametro (mm)": f"{p['diameter_mm']:.0f}", "Altura Banco (m)": f"{bh:.1f}",
            "Volumen Total (m3)": f"{vol:,.0f}", "Toneladas Estimadas": f"{vol * 2.6:,.0f} t",
            "Carga Total (kg)": f"{carga:,.0f}", "Powder Factor (kg/m3)": f"{pf:.4f}",
            "Drill Factor (m/m3)": f"{drill_factor:.4f}",
            "P80 Promedio (mm)": f"{avg_p80:.0f}", "P80 Min-Max (mm)": f"{min_p80:.0f} - {max_p80:.0f}",
            "X50 Promedio (cm)": f"{avg_x50:.1f}",
            "Costo Perforacion (USD)": f"${total_cost_drill:,.0f}",
            "Costo Explosivos (USD)": f"${total_cost_explosive:,.0f}",
            "Costo Total (USD)": f"${total_cost_drill + total_cost_explosive:,.0f}",
        }
        return kpi_data

    def _preview_loading(self):
        self.tabs.loading_tab._update_preview()

    def _render_3d(self):
        from physics_engine import FragmentationModels
        self.plotter.clear()
        self._cad_actors = []
        self._label_actors = []
        self.blast_holes = []
        self.taladros = []
        self.selected_hole = None
        self.props_panel.clear_panel()
        p = self.tabs.geometry_tab.get_params()
        b = p["burden_m"]; s = p["spacing_m"]; d = p["diameter_mm"]
        bh = p["bench_height_m"]; sd = p["subdrilling_m"]
        rows = p["num_rows"]; cols = p["num_cols"]
        lc = self.tabs.loading_tab.get_config()
        stemming = lc["stemming_length_m"]; default_hole_type = lc["hole_type"]
        hole_len = bh + sd; charge_len = hole_len - stemming
        if charge_len <= 0:
            QMessageBox.critical(self, "Error", "Taco > banco"); return

        self.plotter.add_axes(
            color="#CBD5E1",
            x_color="#EF4444",
            y_color="#22C55E",
            z_color="#3B82F6",
            line_width=1.5,
        )
        self.plotter.show_grid(
            color="#334155",
            font_size=9,
            font_family="courier",
            location="outer",
            grid="back",
            all_edges=True,
        )

        topo_file = p.get("topo_file", "")
        if topo_file:
            self._render_topography(topo_file)

        coords_file = p.get("coords_file", "")
        if coords_file:
            self._render_drillhole_coords(coords_file, bh, sd, stemming, default_hole_type, charge_len, d)
        turpo_file = p.get("turpo_file", "")
        if turpo_file:
            self._render_drillhole_coords_turpo(turpo_file)

        mesh_x0 = p.get("mesh_origin_x", 0.0)
        mesh_y0 = p.get("mesh_origin_y", 0.0)

        extent_x = s * (cols + 1)
        extent_y = b * (rows + 1)
        ground = pv.Plane(
            center=(mesh_x0 + extent_x / 2, mesh_y0 + extent_y / 2, 0),
            direction=(0, 0, 1),
            i_size=extent_x * 1.2,
            j_size=extent_y * 1.2,
        )
        self.plotter.add_mesh(ground, color="#1A2332", opacity=0.25, name="ground_plane")

        freeface_y = mesh_y0 - b
        face = pv.Plane(
            center=(mesh_x0 + extent_x / 2, freeface_y, -bh / 2),
            direction=(0, 1, 0),
            i_size=extent_x * 1.3,
            j_size=bh * 2.5,
        )
        self.plotter.add_mesh(face, color="#1E3A5F", opacity=0.06, name="freeface")

        seq = self.tabs.sequence_tab.get_config()
        interval = seq.get("hole_interval_ms", 25)

        phys_rad = d / 2000.0
        vis_rad = max(phys_rad, 0.08)
        hole_num = 0
        for row in range(rows):
            for col in range(cols):
                hole_num += 1
                x = mesh_x0 + col * s + (s / 2 if row % 2 else 0)
                y = mesh_y0 + row * b
                collar = np.array([x, y, 0.0])

                ht = default_hole_type
                if ht not in TYPE_COLORS_3D:
                    ht = "PRODUCCION"
                cd = TYPE_COLORS_3D[ht]
                cc = cd[0]

                sc = pv.Cylinder(center=collar + np.array([0, 0, -stemming / 2]), direction=(0, 0, 1), radius=vis_rad * 1.2, height=stemming, resolution=20)
                sa = self.plotter.add_mesh(sc, color="#64748B", opacity=0.85, name=f"stem_{row}_{col}")

                cr = pv.Cylinder(center=collar + np.array([0, 0, -stemming - charge_len / 2]), direction=(0, 0, 1), radius=vis_rad, height=charge_len, resolution=20)
                ca = self.plotter.add_mesh(cr, color=cc, opacity=0.9, pickable=True, name=f"charge_{row}_{col}")

                delay = row * cols * interval + col * interval
                vol_hole = b * s * bh
                charge_kg = charge_len * 1.15 * math.pi * phys_rad**2 * lc.get("density", 1.15) * 1000
                pf_hole = charge_kg / vol_hole if vol_hole > 0 else 0.1

                try:
                    fm = FragmentationModels()
                    fm_r = fm.calcular_kuz_ram(A=7.0, volumen_roca=vol_hole, kg_explosivo=charge_kg, RWS=100.0)
                    x50_v = fm_r["x50_cm"]
                    p80_v = fm_r["p80_mm"]
                    frag_curve = fm_r["rosin_rammler"]
                except Exception:
                    x50_v = 8.0 * (vol_hole ** 0.167) * (115.0 / 100.0) ** 0.633 / (pf_hole ** 0.8)
                    p80_v = x50_v * 10.0 * 1.5
                    frag_curve = []

                from gui.blast_animator import BlastHole
                h = BlastHole(f"{row}_{col}", collar, collar + np.array([0, 0, -hole_len]), vis_rad, delay, charge_kg, ht, row, col)
                h.actor = ca; h.stem_actor = sa
                self.blast_holes.append(h)

                dh = Drillhole(
                    id=f"T-{hole_num:02d}",
                    x=x, y=y, z=0.0,
                    burden=b, espaciamiento=s,
                    longitud=hole_len, taco=stemming,
                    tipo_explosivo=lc.get("column_explosive", "ANFO"),
                    cebo=lc.get("booster_type", "Pentolita 150g"),
                    row=row, col=col,
                    delay_ms=delay,
                    charge_mass_kg=charge_kg,
                    hole_type=ht,
                    actor=ca,
                    stem_actor=sa,
                    diametro_mm=d,
                    burden_real_m=b,
                    espaciamiento_m=s,
                    p80_mm=p80_v,
                    x50_cm=x50_v,
                )
                self.taladros.append(dh)

        pts = np.array([h.collar for h in self.blast_holes])
        labels_data = [f"T-{i+1:02d}" for i in range(len(self.blast_holes))]
        self.plotter.add_point_labels(
            pts, labels_data,
            font_size=10,
            text_color="#FBBF24",
            bold=True,
            point_size=1,
            shape_opacity=0,
            name="hole_labels",
            always_visible=True,
            justification_horizontal="left",
        )

        self.plotter.reset_camera()
        vol = rows * cols * b * s * bh
        carga = len(self.blast_holes) * charge_len * 1.15
        pf = carga / vol if vol > 0 else 0

        avg_p80 = np.mean([dh.p80_mm for dh in self.taladros]) if self.taladros else 0
        avg_x50 = np.mean([dh.x50_cm for dh in self.taladros]) if self.taladros else 0
        min_p80 = min([dh.p80_mm for dh in self.taladros]) if self.taladros else 0
        max_p80 = max([dh.p80_mm for dh in self.taladros]) if self.taladros else 0

        total_cost_drill = len(self.blast_holes) * hole_len * 25
        total_cost_explosive = carga * 1.2
        drill_factor = (len(self.blast_holes) * hole_len) / vol if vol > 0 else 0

        hole_types_present = {}
        for dh in self.taladros:
            hole_types_present[dh.hole_type] = hole_types_present.get(dh.hole_type, 0) + 1
        type_summary = " | ".join([f"{t}: {c}" for t, c in hole_types_present.items()])

        kpi_data = {
            "Total Taladros": f"{len(self.blast_holes)}",
            "Tipos": type_summary,
            "Burden (m)": f"{b:.2f}",
            "Espaciamiento (m)": f"{s:.2f}",
            "Diametro (mm)": f"{d:.0f}",
            "Altura Banco (m)": f"{bh:.1f}",
            "Volumen Total (m3)": f"{vol:,.0f}",
            "Toneladas Estimadas": f"{vol * 2.6:,.0f} t",
            "Carga Total (kg)": f"{carga:,.0f}",
            "Powder Factor (kg/m3)": f"{pf:.4f}",
            "Drill Factor (m/m3)": f"{drill_factor:.4f}",
            "P80 Promedio (mm)": f"{avg_p80:.0f}",
            "P80 Min-Max (mm)": f"{min_p80:.0f} - {max_p80:.0f}",
            "X50 Promedio (cm)": f"{avg_x50:.1f}",
            "Tiempo Disparo (ms)": f"{(rows * cols - 1) * interval:.0f}",
            "Costo Perforacion (USD)": f"${total_cost_drill:,.0f}",
            "Costo Explosivos (USD)": f"${total_cost_explosive:,.0f}",
            "Costo Total (USD)": f"${total_cost_drill + total_cost_explosive:,.0f}",
        }
        self.tabs.reporting_tab.update_kpis(kpi_data)
        self.kpi_widget.update_kpis(kpi_data)
        QTimer.singleShot(400, lambda d=kpi_data: self.tabs.reporting_tab.update_kpis(d))
        QTimer.singleShot(400, lambda d=kpi_data: self.kpi_widget.update_kpis(d))
        self.explorer_tree.populate_hole_list(self.taladros)
        self._log(f"Malla 3D: {len(self.taladros)} taladros [{type_summary}] P80_avg={avg_p80:.0f}mm PF={pf:.4f}", "SUCCESS")

    def _render_topography(self, filepath):
        try:
            import csv as csvmod
            xp, yp, zp = [], [], []
            with open(filepath, 'r') as f:
                first_line = f.readline()
                sep = ";" if ";" in first_line else ","
                f.seek(0)
                reader = csvmod.reader(f, delimiter=sep)
                header = next(reader, None)
                for row in reader:
                    if len(row) >= 5:
                        xp.append(float(row[2]))
                        yp.append(float(row[3]))
                        zp.append(float(row[4]))
            if len(xp) < 3:
                self._log("Topografia: menos de 3 puntos", "WARN")
                return
            pts = np.column_stack([xp, yp, zp])
            cloud = pv.PolyData(pts)
            surface = cloud.delaunay_2d(alpha=max(np.std(xp), np.std(yp)) * 2)
            self.plotter.add_mesh(surface, color="#3D6B4F", opacity=0.30, name="topo_surface")
            self.plotter.add_mesh(surface, style="wireframe", color="#5A8A6A", opacity=0.10, name="topo_wire")
            self._log(f"Topografia: {len(xp)} puntos, superficie generada", "SUCCESS")
        except Exception as e:
            self._log(f"Error Topografia: {e}", "ERROR")

    def _render_drillhole_coords(self, filepath, bench_height, subdrill, stemming, hole_type, charge_len, diameter):
        try:
            import csv as csvmod
            ids, xc, yc, zc = [], [], [], []
            with open(filepath, 'r') as f:
                first_line = f.readline()
                sep = ";" if ";" in first_line else ","
                f.seek(0)
                reader = csvmod.reader(f, delimiter=sep)
                header = next(reader, None)
                for row in reader:
                    if len(row) >= 4:
                        ids.append(row[0])
                        xc.append(float(row[1]))
                        yc.append(float(row[2]))
                        zc.append(float(row[3]))
            if not ids:
                self._log("Coordenadas: sin datos", "WARN")
                return
            phys_rad = diameter / 2000.0
            vis_rad = max(phys_rad, 0.08)
            hole_len = bench_height + subdrill
            for i, (hid, x, y, z) in enumerate(zip(ids, xc, yc, zc)):
                collar = np.array([x, y, z])
                toe = collar + np.array([0, 0, -hole_len])
                color_data = TYPE_COLORS_3D.get(hole_type, ((0.85, 0.2, 0.2), "Prod"))
                cc = color_data[0]
                sc = pv.Cylinder(center=collar + np.array([0, 0, -stemming / 2]), direction=(0, 0, 1), radius=vis_rad * 1.2, height=stemming, resolution=16)
                self.plotter.add_mesh(sc, color="#64748B", opacity=0.8)
                cr = pv.Cylinder(center=collar + np.array([0, 0, -stemming - charge_len / 2]), direction=(0, 0, 1), radius=vis_rad, height=charge_len, resolution=16)
                ca = self.plotter.add_mesh(cr, color=cc, opacity=0.9, pickable=True)
                from gui.blast_animator import BlastHole
                h = BlastHole(hid, collar, toe, vis_rad, 0.0, charge_len * 1.15, hole_type, i, 0)
                h.actor = ca
                self.blast_holes.append(h)
            self.plotter.add_point_labels(
                np.array([np.array([float(x), float(y), float(z) + 1.5]) for x, y, z in zip(xc, yc, zc)]),
                [f"T-{hid}" for hid in ids],
                font_size=10, text_color="#FBBF24", bold=True, point_size=1, shape_opacity=0, name="coord_labels", always_visible=True
            )
            self._log(f"Coordenadas: {len(ids)} taladros cargados", "SUCCESS")
        except Exception as e:
            self._log(f"Error Coordenadas: {e}", "ERROR")

    def _render_drillhole_coords_turpo(self, filepath):
        """Renderiza taladros TURPO con cilindros inclinados verdaderos."""
        try:
            import csv as csvmod
            ids, xs, ys, z_toes, z_collars, lengths, azs, dips, mats = [], [], [], [], [], [], [], [], []

            # Parsear archivo TURPO
            with open(filepath, 'r', encoding='utf-8-sig') as f:
                first_line = f.readline().strip()
                sep = ";" if ";" in first_line else ","
                f.seek(0)
                reader = csvmod.reader(f, delimiter=sep)
                header = next(reader, None)

                for row_num, row in enumerate(reader):
                    if len(row) < 9:
                        continue
                    try:
                        ids.append(row[0].strip())
                        xs.append(float(row[1]))
                        ys.append(float(row[2]))
                        z_toes.append(float(row[3]))
                        z_collars.append(float(row[4]))

                        # Auto-calcular LENGTH si es 0
                        ln = float(row[5]) if (row[5].strip() and row[5].strip() != '0') else abs(float(row[4]) - float(row[3]))
                        lengths.append(max(ln, 1.0))  # Mínimo 1m

                        azs.append(float(row[6]) if row[6].strip() else 0.0)
                        dips.append(float(row[7]) if row[7].strip() else -90.0)
                        mats.append(row[8].strip().upper() if len(row) > 8 else "PRODUCCION")
                    except (ValueError, IndexError) as e:
                        self._log(f"Fila {row_num}: error parsing {e}", "WARN")
                        continue

            if not ids:
                self._log("TURPO: sin datos válidos", "WARN")
                return

            vis_rad = 0.08
            self._log(f"TURPO: Procesando {len(ids)} taladros...", "INFO")

            for i, (hid, x, y, zt, zc, ln, az_deg, dip_deg, mat) in enumerate(zip(ids, xs, ys, z_toes, z_collars, lengths, azs, dips, mats)):
                collar = np.array([float(x), float(y), float(zc)], dtype=np.float64)

                # Calcular toe usando azimuth y dip
                if abs(az_deg) > 0.1 or abs(dip_deg + 90.0) > 0.1:
                    az_rad = math.radians(float(az_deg))
                    dip_rad = math.radians(float(dip_deg))
                    dx = float(ln) * math.cos(dip_rad) * math.sin(az_rad)
                    dy = float(ln) * math.cos(dip_rad) * math.cos(az_rad)
                    dz = float(ln) * math.sin(dip_rad)
                    toe = collar + np.array([dx, dy, -dz], dtype=np.float64)
                else:
                    toe = np.array([float(x), float(y), float(zt)], dtype=np.float64)

                # Color según material
                cc = (0.85, 0.2, 0.2)  # Rojo por defecto
                mat_str = str(mat).upper()
                if "PRECORTE" in mat_str or "PRESPLIT" in mat_str:
                    cc = (0.1, 0.6, 0.85)  # Azul
                elif "CORTE" in mat_str or "CUT" in mat_str:
                    cc = (0.9, 0.55, 0.1)  # Amarillo

                # Vector de dirección
                h_vec = toe - collar
                h_len = float(np.linalg.norm(h_vec))
                if h_len < 0.1:
                    continue

                h_dir = h_vec / h_len
                center = (collar + toe) / 2.0

                # Cilindro inclinado
                cyl = pv.Cylinder(
                    center=center,
                    direction=h_dir,
                    radius=vis_rad,
                    height=h_len,
                    resolution=12
                )
                self.plotter.add_mesh(cyl, color=cc, opacity=0.85, pickable=True, name=f"turpo_hole_{i}")

                # Etiqueta
                label_pt = collar + np.array([0, 0, 1.5])
                self.plotter.add_point_labels(
                    np.array([label_pt]),
                    [f"T-{hid}"],
                    font_size=8, text_color="#FBBF24", bold=True, point_size=0.5, shape_opacity=0,
                    name=f"label_turpo_{i}", always_visible=True
                )

            self._log(f"TURPO: ✓ {len(ids)} taladros cargados", "SUCCESS")
        except Exception as e:
            import traceback
            self._log(f"Error TURPO: {str(e)}", "ERROR")
            traceback.print_exc()



    def _heatmap(self):
        if not self.blast_holes:
            return
        try:
            from core.blackboxes import VoronoiEnergyMapper
        except ImportError:
            self._log("Module core.blackboxes not found", "ERROR")
            return
        p = self.tabs.geometry_tab.get_params()
        vol = p["burden_m"] * p["spacing_m"] * p["bench_height_m"]
        coords = np.array([h.collar for h in self.blast_holes])
        pf_vals = np.array([h.charge_mass_kg / vol if vol > 0 else 0.1 for h in self.blast_holes])
        mapper = VoronoiEnergyMapper(grid_resolution=80)
        surface_mesh, cells = mapper.generate_energy_heatmap(coords, pf_vals, bench_elevation=0.0)
        if surface_mesh.n_points > 0 and "powder_factor" in surface_mesh.point_data:
            self.plotter.add_mesh(
                surface_mesh, scalars="powder_factor",
                cmap="jet", opacity=0.55, name="energy_heatmap",
                point_size=3, render_points_as_spheres=False,
                show_scalar_bar=True, scalar_bar_args={"title": "Powder Factor (kg/m3)", "color": "#CBD5E1", "font_family": "courier", "font_size": 9}
            )
            self._log(f"Heatmap Voronoi: {len(cells)} celdas", "SUCCESS")

    def _simulate(self):
        if not self.blast_holes:
            QMessageBox.warning(self, "Simulacion", "Genere malla 3D primero."); return
        if self.animator and self.animator.is_playing:
            return
        try:
            from gui.blast_animator import BlastAnimator
            p = self.tabs.geometry_tab.get_params()
            self.animator = BlastAnimator(self.plotter, self.blast_holes, p["burden_m"], p["spacing_m"])
            self.animator.animation_finished.connect(lambda: (self._log("Simulacion completada", "SUCCESS"), self.statusBar().showMessage("Simulacion completada"), self._post_blast_analysis()))
            self.animator.row_detonated.connect(self._on_row_detonated)
            self.animator.start()
            self._log("Simulacion 3D iniciada - detonacion fila por fila", "INFO")
            self.statusBar().showMessage("Simulando voladura en 3D...")
        except Exception as e:
            self._log(f"Error: {e}", "ERROR")

    def _on_row_detonated(self, row, time):
        self._log(f"Fila {row} detonada @ {time:.0f}ms", "INFO")

    def _post_blast_analysis(self):
        if not self.blast_holes:
            return
        try:
            from core.blackboxes import VoronoiEnergyMapper
            p = self.tabs.geometry_tab.get_params()
            vol = p["burden_m"] * p["spacing_m"] * p["bench_height_m"]
            coords = np.array([h.collar for h in self.blast_holes])
            center = np.mean(coords, axis=0)
            distances = np.linalg.norm(coords - center, axis=1)
            max_dist = float(np.max(distances)) * 1.5
            for radius_factor, color in [
                (0.3, (0.9, 0.15, 0.15)),
                (0.6, (0.9, 0.6, 0.1)),
                (1.0, (0.15, 0.75, 0.3)),
            ]:
                ring = pv.Cylinder(center=center, direction=(0, 0, 1), radius=max_dist * radius_factor, height=p["bench_height_m"], resolution=32)
                self.plotter.add_mesh(ring, color=color, opacity=0.10, name=f"vibzone_{radius_factor}")
            self._log("Analisis post-voladura: zonas de vibracion generadas", "SUCCESS")
        except Exception as e:
            self._log(f"Error analisis post: {e}", "ERROR")

    def _apply_grid_overlay(self):
        if not self.blast_holes:
            self._log("Genere malla primero para cuadricula", "WARN")
            return
        coords = np.array([h.collar for h in self.blast_holes])
        center = np.mean(coords[:, :2], axis=0)
        grid_size = 60.0; grid_step = 5.0
        x0 = center[0] - grid_size / 2; y0 = center[1] - grid_size / 2
        lines_list = []
        n_lines = int(grid_size / grid_step) + 1
        for i in range(n_lines):
            offset = i * grid_step
            lines_list.append(pv.Line(np.array([x0 + offset, y0, 0.0]), np.array([x0 + offset, y0 + grid_size, 0.0])))
            lines_list.append(pv.Line(np.array([x0, y0 + offset, 0.0]), np.array([x0 + grid_size, y0 + offset, 0.0])))
        grid_mesh = lines_list[0]
        for l in lines_list[1:]:
            grid_mesh = grid_mesh.merge(l)
        self.plotter.add_mesh(grid_mesh, color="#475569", line_width=1, opacity=0.3, name="grid_overlay")
        self._log(f"Cuadricula {grid_size:.0f}m aplicada", "SUCCESS")

    def habilitar_seleccion_taladros(self):
        try:
            self.plotter.enable_point_picking(
                callback=self._on_taladro_picked,
                show_message=False,
                left_clicking=True,
                picker="point",
            )
        except Exception:
            self.plotter.enable_point_picking(
                callback=self._on_taladro_picked,
                show_message=False,
                left_clicking=True,
            )

    def _on_taladro_picked(self, point):
        try:
            if point is None:
                return
            pt = np.asarray(point[:3], dtype=np.float64)
            if not self.taladros:
                if self.blast_holes:
                    dists = [np.linalg.norm(pt[:2] - np.array([h.collar[0], h.collar[1]])) for h in self.blast_holes]
                    idx = int(np.argmin(dists))
                    self.tabs.loading_tab.select_hole(str(self.blast_holes[idx].hole_id))
                    self.tabs.setCurrentIndex(2)
                    self._log(f"Taladro seleccionado: {self.blast_holes[idx].hole_id} | X: {self.blast_holes[idx].collar[0]:.1f} | Y: {self.blast_holes[idx].collar[1]:.1f}", "INFO")
                return

            if self.cad.mode not in (ToolMode.NONE, ""):
                return

            if self.selected_hole is not None:
                try:
                    self.selected_hole.actor.GetProperty().SetOpacity(0.9)
                except Exception:
                    pass

            dists = [dh.distance_to_point(pt) for dh in self.taladros]
            idx = int(np.argmin(dists))
            dh = self.taladros[idx]
            self.selected_hole = dh
            dh.selected = True

            try:
                dh.actor.GetProperty().SetOpacity(1.0)
                dh.actor.GetProperty().SetColor(1.0, 1.0, 0.0)
            except Exception:
                pass

            self.tabs.loading_tab.select_hole(dh.id)
            self.tabs.setCurrentIndex(2)
            self._update_properties_panel(dh)
            self._log(f"Taladro seleccionado: {dh.id} | X: {dh.x:.1f} | Y: {dh.y:.1f} | Carga: {dh.charge_mass_kg:.0f}kg", "INFO")
        except Exception as e:
            self._log(f"Error seleccion: {e}", "ERROR")

    def activar_medicion(self):
        self._ruler_points = []
        try:
            self.plotter.enable_point_picking(
                callback=self._on_punto_medicion_picked,
                show_message=False,
                left_clicking=True,
                picker="point",
            )
        except Exception:
            self.plotter.enable_point_picking(
                callback=self._on_punto_medicion_picked,
                show_message=False,
                left_clicking=True,
            )
        self._log("Medicion activada: seleccione 2 puntos", "CAD")

    def _on_punto_medicion_picked(self, point):
        try:
            if point is None:
                return
            pt = np.asarray(point[:3], dtype=np.float64)
            self._ruler_points.append(pt)

            try:
                sphere = pv.Sphere(radius=0.3, center=pt)
                name = f"ruler_pt_{len(self._ruler_points)}"
                self.plotter.add_mesh(sphere, color="#FBBF24", opacity=0.9, name=name)
            except Exception:
                pass

            if len(self._ruler_points) == 2:
                p1, p2 = self._ruler_points
                dist = float(np.linalg.norm(p2 - p1))

                line = pv.Line(p1, p2, resolution=2)
                self.plotter.add_mesh(line, color="#00F0FF", line_width=4, name="ruler_line")

                mid = (p1 + p2) / 2.0
                self.plotter.add_point_labels(
                    [mid], [f"  {dist:.3f} m  "],
                    font_size=14, text_color="#00F0FF",
                    bold=True, point_size=1, shape_opacity=0,
                    name="ruler_text", always_visible=True,
                )

                dx = float(p2[0] - p1[0])
                dy = float(p2[1] - p1[1])
                dz = float(p2[2] - p1[2])
                self._log(f"Distancia medida: {dist:.3f} m | dX={dx:.2f} dY={dy:.2f} dZ={dz:.2f}", "CAD")
                self._ruler_points = []
            elif len(self._ruler_points) == 1:
                self._log(f"Punto 1 registrado: ({pt[0]:.2f}, {pt[1]:.2f}, {pt[2]:.2f})", "CAD")
        except Exception as e:
            self._log(f"Error medicion: {e}", "ERROR")
            self._ruler_points = []

    def _clear_cad(self):
        for name in ["ruler_line", "ruler_text", "boundary", "profile_line", "profile_text", "angle_line1", "angle_line2", "angle_text", "grid_overlay"]:
            try:
                self.plotter.remove_actor(name)
            except Exception:
                pass
        self._log("Elementos CAD limpiados", "CAD")

    def _export_pdf(self, report_type="general"):
        try:
            from reports.pdf_report import generate_blast_report
            meta = self.tabs.metadata_tab.get_metadata()
            geo = self.tabs.geometry_tab.get_params()
            loading = self.tabs.loading_tab.get_config()
            seq = self.tabs.sequence_tab.get_config()
            output_dir = str(Path(__file__).parent / "reports_output")
            path = generate_blast_report(grid_params=geo, loading_config=loading, sequence_config=seq, metadata=meta, report_type=report_type, output_dir=output_dir, filename=PDF_OUTPUT_FILENAME)
            self._log(f"PDF [{report_type}]: {path}", "SUCCESS")
            return path
        except Exception as e:
            self._log(f"Error PDF [{report_type}]: {e}", "ERROR")
            return None

    def _export_all_reports(self):
        self._log("Generando TODOS los reportes PDF...", "INFO")
        paths = []
        for rtype in ["executive", "operational", "ssoma", "loading"]:
            p = self._export_pdf(rtype)
            if p:
                paths.append(p)
        if paths:
            msg = "Reportes generados:\n" + "\n".join(paths)
            QMessageBox.information(self, "X-BLAST", msg)
            self._log(f"Todos los reportes generados: {len(paths)} archivos", "SUCCESS")
        else:
            QMessageBox.warning(self, "X-BLAST", "No se generaron reportes. Verifique los parametros.")


class CyberSplash(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(780, 600)
        self.pct = 0
        self.msg_idx = 0
        self.messages = [
            "INICIALIZANDO MODULOS DEL SISTEMA...",
            "CARGANDO MOTOR GRAFICO 3D...",
            "PREPARANDO INTERFAZ DE USUARIO...",
            "CONECTANDO BASE DE DATOS...",
            "VERIFICANDO LICENCIAS...",
            "SISTEMA LISTO - BIENVENIDO",
        ]
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)
        self._timer.start(80)
        self._start_time = time.time()
        self.unap_pix = None
        self.fim_pix = None
        for f in ["unap.png", "UNAP.png", "unap .png"]:
            fp = find_asset(f)
            if fp and fp.exists():
                self.unap_pix = QPixmap(str(fp))
                break
        for f in ["fim.png", "FIM.png", "Insignia FIM.png"]:
            fp = find_asset(f)
            if fp and fp.exists():
                self.fim_pix = QPixmap(str(fp))
                break

    def paintEvent(self, event):
        from PySide6.QtGui import QPainter, QLinearGradient, QColor, QFont, QPen, QPixmap
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        grad = QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0.0, QColor("#05080F"))
        grad.setColorAt(0.5, QColor("#0B1428"))
        grad.setColorAt(1.0, QColor("#05080F"))
        p.fillRect(self.rect(), grad)

        pen = QPen(QColor("#00F0FF"), 2)
        p.setPen(pen)
        p.drawRoundedRect(8, 8, self.width() - 16, self.height() - 16, 12, 12)

        glow = QColor("#00F0FF")
        glow.setAlpha(12)
        p.setPen(QPen(glow, 1))
        p.drawRoundedRect(16, 16, self.width() - 32, self.height() - 32, 8, 8)

        logo_p = find_asset("X-BLAST.png")
        if logo_p and logo_p.exists():
            pix = QPixmap(str(logo_p))
            if not pix.isNull():
                logo = pix.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                p.drawPixmap(self.width() // 2 - 50, 18, logo)

        if self.unap_pix and not self.unap_pix.isNull():
            ul = self.unap_pix.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            p.drawPixmap(80, 170, ul)
        if self.fim_pix and not self.fim_pix.isNull():
            fl = self.fim_pix.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            p.drawPixmap(self.width() - 144, 170, fl)

        p.setPen(QColor("#00F0FF"))
        title_font = QFont("Segoe UI", 22, QFont.Weight.Bold)
        p.setFont(title_font)
        p.drawText(self.rect().adjusted(0, 110, 0, 0), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, "X-BLAST ENTERPRISE")

        p.setPen(QColor("#38BDF8"))
        sub_font = QFont("Segoe UI", 11)
        p.setFont(sub_font)
        p.drawText(self.rect().adjusted(0, 145, 0, 0), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, "GEMELO DIGITAL DE VOLADURA - v2.0")

        p.setPen(QColor("#94A3B8"))
        info_font = QFont("Segoe UI", 9)
        p.setFont(info_font)
        info_lines = [
            "Felix Fernando Bautista Layme",
            "Universidad Nacional del Altiplano - Puno",
            "Ingenieria de Minas - Facultad de Ingenieria de Minas",
            "Proyecto: X-BLAST Enterprise Mining Suite",
        ]
        y = 190
        for line in info_lines:
            p.drawText(self.rect().adjusted(180, y, -180, 0), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, line)
            y += 22

        bar_x, bar_y, bar_w, bar_h = 140, 370, 500, 16
        p.setPen(QPen(QColor("#1E293B"), 1))
        p.setBrush(QColor("#0F172A"))
        p.drawRoundedRect(bar_x, bar_y, bar_w, bar_h, 6, 6)

        fill_w = int(bar_w * self.pct / 100)
        if fill_w > 0:
            fill_grad = QLinearGradient(bar_x, bar_y, bar_x + bar_w, bar_y)
            fill_grad.setColorAt(0.0, QColor("#00F0FF"))
            fill_grad.setColorAt(0.5, QColor("#06B6D4"))
            fill_grad.setColorAt(1.0, QColor("#0891B2"))
            p.setBrush(fill_grad)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(bar_x, bar_y, fill_w, bar_h, 6, 6)

        p.setPen(QColor("#94A3B8"))
        pct_font = QFont("Segoe UI", 8)
        p.setFont(pct_font)
        p.drawText(bar_x, bar_y - 14, bar_w, 14, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom, f"{self.pct}%")

        p.setPen(QColor("#00FF41"))
        msg_font = QFont("Courier New", 9)
        p.setFont(msg_font)
        dots = "." * (int(time.time() * 3) % 4)
        msg = self.messages[min(self.msg_idx, len(self.messages) - 1)]
        p.drawText(self.rect().adjusted(0, 410, 0, 0), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, f">> {msg}{dots}")

        p.setPen(QColor("#334155"))
        ver_font = QFont("Segoe UI", 7)
        p.setFont(ver_font)
        p.drawText(self.rect().adjusted(0, -20, -20, 0), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom, "X-BLAST Enterprise v2.0 | PySide6 + PyVista")

        p.end()

    def _advance(self):
        self.pct += 1
        if self.pct % 17 == 0 and self.msg_idx < len(self.messages) - 1:
            self.msg_idx += 1
        self.update()
        if self.pct >= 100:
            self._timer.stop()

    def is_done(self):
        return self.pct >= 100


if __name__ == "__main__":
    import os, ctypes
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    myappid = "xblast.enterprise.v2.0"
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

    icon_p = find_asset("X-BLAST.ico") or find_asset("X-BLAST.PNG") or find_asset("X-BLAST.png")
    if icon_p and icon_p.exists():
        app_icon = QIcon(str(icon_p))
        app.setWindowIcon(app_icon)

    splash = CyberSplash()
    splash.show()
    app.processEvents()

    w = MainWindow()
    if icon_p.exists():
        w.setWindowIcon(QIcon(str(icon_p)))
    while not splash.is_done():
        app.processEvents()
        time.sleep(0.02)
    splash.close()
    w.show()
    if icon_p.exists():
        w.setWindowIcon(QIcon(str(icon_p)))
        app.setWindowIcon(QIcon(str(icon_p)))
    sys.exit(app.exec())
