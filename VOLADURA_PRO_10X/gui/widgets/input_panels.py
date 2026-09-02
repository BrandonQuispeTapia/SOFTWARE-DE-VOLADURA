"""
gui/widgets/input_panels.py
===========================
Componentes modulares de entrada de datos para la interfaz principal.
Construidos sobre PySide6 con tipado estricto.

Autor: Félix Fernando Bautista Layme — UNA Puno.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, 
    QLabel, QDoubleSpinBox, QPushButton, QGroupBox,
    QFrame
)
from PySide6.QtCore import Signal


class DesignPanel(QWidget):
    """Panel de diseño geométrico de la voladura."""
    
    # Señal emitida cuando cambian los parámetros de la malla
    parameters_changed = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        group = QGroupBox("Parámetros de Diseño (Geometría)")
        form = QFormLayout()
        
        # Helper para crear SpinBoxes consistentes
        def create_spinbox(val, min_val, max_val, step, suffix):
            sb = QDoubleSpinBox()
            sb.setRange(min_val, max_val)
            sb.setSingleStep(step)
            sb.setValue(val)
            sb.setSuffix(f" {suffix}")
            sb.valueChanged.connect(self._emit_parameters)
            return sb

        self.spin_burden = create_spinbox(3.5, 1.0, 15.0, 0.1, "m")
        self.spin_spacing = create_spinbox(4.0, 1.0, 20.0, 0.1, "m")
        self.spin_diameter = create_spinbox(165.0, 50.0, 311.0, 1.0, "mm")
        self.spin_bench = create_spinbox(10.0, 2.0, 30.0, 0.5, "m")
        self.spin_stemming = create_spinbox(2.5, 0.5, 10.0, 0.1, "m")
        self.spin_subdrill = create_spinbox(1.0, 0.0, 5.0, 0.1, "m")
        
        form.addRow("Burden (B):", self.spin_burden)
        form.addRow("Espaciamiento (S):", self.spin_spacing)
        form.addRow("Diámetro (D):", self.spin_diameter)
        form.addRow("Altura Banco (H):", self.spin_bench)
        form.addRow("Taco (T):", self.spin_stemming)
        form.addRow("Sobreperforación (J):", self.spin_subdrill)
        
        group.setLayout(form)
        layout.addWidget(group)
        layout.addStretch()

    def get_parameters(self) -> dict:
        """Retorna los parámetros actuales como diccionario."""
        return {
            "burden": self.spin_burden.value(),
            "spacing": self.spin_spacing.value(),
            "diameter_mm": self.spin_diameter.value(),
            "bench_height": self.spin_bench.value(),
            "stemming": self.spin_stemming.value(),
            "subdrill": self.spin_subdrill.value()
        }

    def _emit_parameters(self):
        """Emite la señal con los datos actualizados."""
        self.parameters_changed.emit(self.get_parameters())


class ExecutionPanel(QWidget):
    """Panel con los botones principales de acción."""
    
    # Señales hacia el MainWindow
    generate_mesh_requested = Signal()
    run_montecarlo_requested = Signal()
    generate_report_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        group = QGroupBox("Ejecución y Análisis")
        vbox = QVBoxLayout()
        
        # Botones
        self.btn_mesh = QPushButton("📐 Generar Malla 3D")
        self.btn_montecarlo = QPushButton("🎲 Optimización Estocástica (Montecarlo)")
        self.btn_report = QPushButton("📄 Generar Reporte Gerencial PDF")

        # Estilos específicos
        self.btn_montecarlo.setStyleSheet("""
            QPushButton {
                background-color: #2563eb; color: white; font-weight: bold; padding: 8px;
            }
            QPushButton:hover { background-color: #1d4ed8; }
            QPushButton:disabled { background-color: #374151; color: #9ca3af; }
        """)

        self.btn_report.setStyleSheet("""
            QPushButton {
                background-color: #059669; color: white; font-weight: bold; padding: 8px;
            }
            QPushButton:hover { background-color: #047857; }
        """)

        # Conexiones
        self.btn_mesh.clicked.connect(self.generate_mesh_requested.emit)
        self.btn_montecarlo.clicked.connect(self.run_montecarlo_requested.emit)
        self.btn_report.clicked.connect(self.generate_report_requested.emit)

        vbox.addWidget(self.btn_mesh)

        # Separador
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        vbox.addWidget(line)

        vbox.addWidget(self.btn_montecarlo)
        vbox.addWidget(self.btn_report)

        group.setLayout(vbox)
        layout.addWidget(group)
        layout.addStretch()


class TurpoDataPanel(QWidget):
    """Panel para cargar datos TURPO (taladros con coordenadas reales, azimuth, dip)."""

    turpo_file_selected = Signal(str)  # Emite ruta del archivo TURPO

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        group = QGroupBox("🗂️ Datos TURPO (Taladros con Coordenadas Reales)")
        vbox = QVBoxLayout()

        # Instrucciones
        info_label = QLabel(
            "Carga datos de taladros con coordenadas reales, elevaciones, azimuth y dip.\n"
            "Formato esperado: ID; EAST; NORTH; ELEV TOE; ELEV COLLAR; LENGTH; AZ; DIP; MATERIAL"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #94A3B8; font-size: 9pt;")
        vbox.addWidget(info_label)

        # Botón para seleccionar archivo
        self.btn_select_turpo = QPushButton("📁 Seleccionar archivo TURPO CSV...")
        self.btn_select_turpo.setStyleSheet("""
            QPushButton {
                background-color: #7C3AED; color: white; font-weight: bold; padding: 10px;
            }
            QPushButton:hover { background-color: #6D28D9; }
        """)
        self.turpo_file_path = ""
        self.btn_select_turpo.clicked.connect(self._browse_turpo)
        vbox.addWidget(self.btn_select_turpo)

        # Etiqueta de archivo seleccionado
        self.label_turpo_selected = QLabel("(Ningún archivo seleccionado)")
        self.label_turpo_selected.setStyleSheet("color: #FCA5A5; font-size: 9pt; font-style: italic;")
        vbox.addWidget(self.label_turpo_selected)

        # Botón para renderizar
        self.btn_render_turpo = QPushButton("🎬 Renderizar Taladros TURPO")
        self.btn_render_turpo.setEnabled(False)
        self.btn_render_turpo.setStyleSheet("""
            QPushButton {
                background-color: #0891B2; color: white; font-weight: bold; padding: 10px;
            }
            QPushButton:hover { background-color: #0E7490; }
            QPushButton:disabled { background-color: #374151; color: #9ca3af; }
        """)
        self.btn_render_turpo.clicked.connect(self._emit_render)
        vbox.addWidget(self.btn_render_turpo)

        group.setLayout(vbox)
        layout.addWidget(group)
        layout.addStretch()

    def _browse_turpo(self):
        """Abre diálogo para seleccionar archivo TURPO."""
        from PySide6.QtWidgets import QFileDialog
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar archivo TURPO",
            "",
            "CSV Files (*.csv);;Todos los archivos (*.*)"
        )
        if filepath:
            self.turpo_file_path = filepath
            filename = filepath.split("\\")[-1]
            self.label_turpo_selected.setText(f"✓ {filename}")
            self.label_turpo_selected.setStyleSheet("color: #86EFAC; font-size: 9pt;")
            self.btn_render_turpo.setEnabled(True)

    def _emit_render(self):
        """Emite señal con la ruta del archivo."""
        if self.turpo_file_path:
            self.turpo_file_selected.emit(self.turpo_file_path)

