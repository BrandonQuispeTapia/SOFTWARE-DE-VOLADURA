"""
gui/main_window.py
==================
Orquestador principal de la Interfaz Gráfica (MainWindow).

Integra el visor 3D, los paneles de control y maneja la ejecución
multihilo (QThread) para no bloquear la UI durante simulaciones pesadas.

Autor: Félix Fernando Bautista Layme — UNA Puno.
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, 
    QSplitter, QProgressBar, QTextEdit, QMessageBox,
    QDockWidget
)
from PySide6.QtCore import Qt, QThread, Signal
import traceback
import sys
import os

from gui.views_3d import BlastViewer3D
from gui.widgets.input_panels import DesignPanel, ExecutionPanel

from core.geometry import BlastPattern, Point3D, PatternType
from core.rock_mass import RockProperties
from optimization.cost_engine import CostParameters
from optimization.montecarlo import MineToMillOptimizer
from reports.report_generator import PDFReportBuilder


# =====================================================================
# Trabajadores Multihilo (Workers)
# =====================================================================

class MontecarloWorker(QThread):
    """Ejecuta la optimización Montecarlo en segundo plano."""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, params: dict, rock: RockProperties, iterations: int = 1000):
        super().__init__()
        self.params = params
        self.rock = rock
        self.iterations = iterations

    def run(self):
        try:
            optimizer = MineToMillOptimizer(self.rock, CostParameters())
            results = optimizer.run_simulation(
                base_burden=self.params["burden"],
                base_spacing=self.params["spacing"],
                hole_diameter_mm=self.params["diameter_mm"],
                bench_height=self.params["bench_height"],
                iterations=self.iterations
            )
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(f"Error en Montecarlo: {str(e)}\n{traceback.format_exc()}")


class ReportWorker(QThread):
    """Genera el reporte PDF de manera asíncrona."""
    finished = Signal(str)  # Emite el path del PDF
    error = Signal(str)

    def __init__(self, pattern: BlastPattern, rock: RockProperties):
        super().__init__()
        self.pattern = pattern
        self.rock = rock

    def run(self):
        try:
            builder = PDFReportBuilder()
            
            # Simulamos una curva granulométrica para el reporte
            sizes = [10, 50, 100, 200, 500]
            passing = [5, 20, 50, 80, 100]
            
            output_path = builder.build_executive_report(
                self.pattern, self.rock, sizes, passing
            )
            self.finished.emit(str(output_path))
        except Exception as e:
            self.error.emit(f"Error generando reporte: {str(e)}\n{traceback.format_exc()}")


# =====================================================================
# Ventana Principal
# =====================================================================

class MainWindow(QMainWindow):
    """Ventana principal de VOLADURA_PRO_10X."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("VOLADURA PRO 10X — Gemelo Digital D&B")
        self.resize(1280, 720)
        
        self.current_pattern = None
        self.base_rock = RockProperties("Andesita (Por defecto)", 2.6, 120.0, 8.0)
        
        self._setup_ui()
        self._apply_dark_theme()
        
    def _setup_ui(self):
        # Widget Central (Splitter para dividir pantalla)
        main_splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(main_splitter)
        
        # 1. Panel Izquierdo (Controles)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        self.design_panel = DesignPanel()
        self.execution_panel = ExecutionPanel()
        
        left_layout.addWidget(self.design_panel)
        left_layout.addWidget(self.execution_panel)
        left_layout.addStretch()
        
        # 2. Panel Central (Visor 3D)
        self.viewer_3d = BlastViewer3D()
        
        # 3. Panel Derecho (Consola / Logs)
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setPlaceholderText("Consola del sistema...")
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        
        right_layout.addWidget(self.console)
        right_layout.addWidget(self.progress_bar)
        
        # Ensamblar Splitter
        main_splitter.addWidget(left_widget)
        main_splitter.addWidget(self.viewer_3d)
        main_splitter.addWidget(right_widget)
        
        # Proporciones (Izquierda: 20%, Centro: 60%, Derecha: 20%)
        main_splitter.setSizes([250, 780, 250])
        
        # --- Conectar Señales ---
        self.execution_panel.generate_mesh_requested.connect(self._generate_mesh)
        self.execution_panel.run_montecarlo_requested.connect(self._run_montecarlo)
        self.execution_panel.generate_report_requested.connect(self._generate_report)
        self.viewer_3d.signals.hole_picked.connect(self._on_hole_selected)
        
        self.log("VOLADURA PRO 10X Inicializado.")
        
    def log(self, message: str):
        """Imprime un mensaje en la consola de la UI."""
        self.console.append(f"> {message}")

    def _generate_mesh(self):
        """Genera la malla 3D y la envía al visor."""
        params = self.design_panel.get_parameters()
        self.log(f"Generando malla con Burden {params['burden']}m y Espaciamiento {params['spacing']}m...")
        
        pattern = BlastPattern(
            pattern_id="PROD_001",
            origin=Point3D(0, 0, 0),
            burden=params["burden"],
            spacing=params["spacing"],
            bench_height=params["bench_height"],
            subdrill=params["subdrill"],
            stemming=params["stemming"],
            num_rows=4,
            holes_per_row=6,
            pattern_type=PatternType.STAGGERED
        )
        pattern.generate_grid(diameter_mm=params["diameter_mm"])
        
        self.current_pattern = pattern
        self.viewer_3d.draw_drillholes(pattern)
        self.log(f"Malla generada con éxito: {pattern.total_holes} taladros.")
        
    def _run_montecarlo(self):
        """Inicia el worker de simulación estocástica."""
        params = self.design_panel.get_parameters()
        
        self.execution_panel.btn_montecarlo.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Modo Indeterminado
        self.log("Iniciando Simulación Montecarlo (1000 iteraciones)...")
        
        self.montecarlo_worker = MontecarloWorker(params, self.base_rock, iterations=1000)
        self.montecarlo_worker.finished.connect(self._on_montecarlo_finished)
        self.montecarlo_worker.error.connect(self._on_worker_error)
        self.montecarlo_worker.start()
        
    def _on_montecarlo_finished(self, results: dict):
        self.execution_panel.btn_montecarlo.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        best = results["best_scenario"]
        self.log("\n--- RESULTADO MONTECARLO ---")
        self.log(f"Burden Óptimo: {best['optimal_burden_m']} m")
        self.log(f"Spacing Óptimo: {best['optimal_spacing_m']} m")
        self.log(f"Costo Total (D&B+Crushing): ${best['min_total_cost_usd_t']}/t")
        self.log(f"P80 Proyectado: {best['predicted_p80_mm']} mm")
        self.log("----------------------------\n")
        
    def _generate_report(self):
        """Inicia el worker de generación de PDF."""
        if not self.current_pattern:
            QMessageBox.warning(self, "Atención", "Debe generar la malla 3D primero.")
            return
            
        self.execution_panel.btn_report.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.log("Ensamblando Reporte Ejecutivo...")
        
        self.report_worker = ReportWorker(self.current_pattern, self.base_rock)
        self.report_worker.finished.connect(self._on_report_finished)
        self.report_worker.error.connect(self._on_worker_error)
        self.report_worker.start()
        
    def _on_report_finished(self, pdf_path: str):
        self.execution_panel.btn_report.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.log(f"Reporte generado exitosamente:\n{pdf_path}")
        
    def _on_worker_error(self, err_msg: str):
        self.execution_panel.btn_montecarlo.setEnabled(True)
        self.execution_panel.btn_report.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.log(f"[ERROR]: {err_msg}")
        QMessageBox.critical(self, "Error Interno", err_msg)
        
    def _on_hole_selected(self, hole_id: str):
        """Se ejecuta al hacer clic en un taladro en el visor 3D."""
        if self.current_pattern:
            hole = next((h for h in self.current_pattern.holes if h.hole_id == hole_id), None)
            if hole:
                self.log(f"Taladro Seleccionado: {hole_id}")
                self.log(f" -> Carga: {hole.charge_length:.1f}m | Taco: {hole.stemming:.1f}m")

    def _apply_dark_theme(self):
        """Aplica un QSS Dark Theme corporativo Premium."""
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #0d0f12;
                color: #e2e8f0;
                font-family: 'Inter', 'Segoe UI', Roboto, sans-serif;
                font-size: 10pt;
            }
            QSplitter::handle {
                background-color: #1e293b;
                width: 2px;
            }
            QGroupBox {
                border: 1px solid #334155;
                border-radius: 8px;
                margin-top: 2ex;
                background-color: #15181e;
                font-weight: 600;
                color: #94a3b8;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
                color: #38bdf8;
            }
            QDoubleSpinBox {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 5px;
                color: #f8fafc;
                selection-background-color: #0284c7;
            }
            QDoubleSpinBox:focus {
                border: 1px solid #38bdf8;
            }
            QPushButton {
                background-color: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                                                  stop: 0 #0ea5e9, stop: 1 #2563eb);
                border: none;
                border-radius: 6px;
                padding: 10px 15px;
                color: white;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                                                  stop: 0 #38bdf8, stop: 1 #3b82f6);
            }
            QPushButton:pressed {
                background-color: #1d4ed8;
            }
            QPushButton:disabled {
                background-color: #334155;
                color: #94a3b8;
            }
            QTextEdit {
                background-color: #0b0d10;
                border: 1px solid #1e293b;
                border-radius: 6px;
                color: #10b981;
                font-family: 'Fira Code', Consolas, monospace;
                padding: 5px;
            }
            QProgressBar {
                border: 1px solid #334155;
                border-radius: 4px;
                background-color: #0f172a;
                text-align: center;
                color: transparent;
            }
            QProgressBar::chunk {
                background-color: #38bdf8;
                border-radius: 3px;
            }
        """)
