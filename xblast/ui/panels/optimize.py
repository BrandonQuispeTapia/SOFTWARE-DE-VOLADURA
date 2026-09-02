"""Panel de optimizacion y analisis de escenarios.

Explora variaciones de burden y relacion S/B alrededor del diseno vigente,
descarta las que incumplen las restricciones ambientales y propone la de menor
costo total por tonelada.
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from ...core.optimizer import OptimizationResult, Scenario, sensitivity
from .. import widgets as W
from ..charts import OptimizationChart
from ..theme import C


class OptimizePanel(QWidget):
    """Barrido de escenarios con recomendacion economica."""

    run_requested = Signal(dict)
    apply_requested = Signal(object)

    def __init__(self):
        super().__init__()
        self._result: Optional[OptimizationResult] = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(12)

        lay.addWidget(W.title("Optimizacion del diseno", 2))
        lay.addWidget(W.caption(
            "Cada escenario se evalua con el motor completo — geometria, carga, "
            "secuencia, fragmentacion, vibracion y costos — manteniendo constante el "
            "area volada para que la comparacion sea valida."))

        controls = W.Section("Espacio de busqueda")
        self.b_min = controls.row("Burden minimo", W.spin(0.5, 1.0, 0.80, 0.05, "x nominal", 2))
        self.b_max = controls.row("Burden maximo", W.spin(1.0, 1.6, 1.20, 0.05, "x nominal", 2))
        self.steps = controls.row("Pasos de burden", W.int_spin(3, 12, 5))
        self.sb_ratios = controls.row("Relaciones S/B", W.combo(
            ["1.00 / 1.15 / 1.30", "1.00 / 1.25", "0.90 / 1.00 / 1.15 / 1.30", "1.15"],
            "1.00 / 1.15 / 1.30"))
        self.target_p80 = controls.row("P80 objetivo de planta", W.spin(5, 200, 50, 1, "cm", 0))
        lay.addWidget(controls)

        run_row = QHBoxLayout()
        self.btn_run = W.button("Ejecutar optimizacion", "primary", "optimize")
        self.btn_run.setMinimumHeight(30)
        self.btn_run.clicked.connect(self._emit_run)
        self.btn_apply = W.button("Aplicar mejor escenario", "", "check")
        self.btn_apply.setEnabled(False)
        self.btn_apply.clicked.connect(self._apply_best)
        run_row.addWidget(self.btn_run)
        run_row.addWidget(self.btn_apply)
        run_row.addStretch(1)
        lay.addLayout(run_row)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        lay.addWidget(self.progress)

        self.verdict = QLabel("")
        self.verdict.setWordWrap(True)
        self.verdict.setVisible(False)
        lay.addWidget(self.verdict)

        self.chart = OptimizationChart()
        self.chart.setMinimumHeight(280)
        lay.addWidget(self.chart)

        lay.addWidget(W.title("Escenarios evaluados", 2))
        self.table = W.DataTable()
        self.table.itemSelectionChanged.connect(self._on_select)
        lay.addWidget(self.table, 1)

        self.detail = W.caption("")
        lay.addWidget(self.detail)

    # -- API ---------------------------------------------------------------
    def settings(self) -> dict:
        ratios = [float(x) for x in self.sb_ratios.currentText().split("/")]
        return {
            "burden_range": (self.b_min.value(), self.b_max.value()),
            "n_steps": self.steps.value(),
            "sb_ratios": tuple(ratios),
            "target_p80_cm": self.target_p80.value(),
        }

    def set_running(self, running: bool, done: int = 0, total: int = 0) -> None:
        self.btn_run.setEnabled(not running)
        self.progress.setVisible(running)
        if running and total:
            self.progress.setRange(0, total)
            self.progress.setValue(done)

    def set_result(self, result: Optional[OptimizationResult]) -> None:
        self._result = result
        self.set_running(False)
        if result is None or not result.scenarios:
            self.btn_apply.setEnabled(False)
            self.verdict.setVisible(False)
            self.chart.update_data(None)
            self.table.setRowCount(0)
            return

        best = result.best
        self.btn_apply.setEnabled(best is not None)
        self.chart.update_data(sensitivity(result), best.powder_factor if best else None)
        self.table.set_dict_rows([s.as_row() for s in result.scenarios])

        if best:
            saving = result.savings_usd_t()
            trend = ("ahorra" if saving > 0 else "cuesta")
            fg, bg = ((C["ok"], C["ok_soft"]) if saving > 0 else (C["info"], C["info_soft"]))
            self.verdict.setStyleSheet(
                f"color:{fg}; background-color:{bg}; border-left:3px solid {fg};"
                "border-radius:4px; padding:9px 11px;")
            self.verdict.setText(
                f"Mejor escenario viable: B = {best.burden_m:.2f} m, S = {best.spacing_m:.2f} m, "
                f"taco = {best.stemming_m:.2f} m sobre {best.n_holes} taladros.\n"
                f"Factor de potencia {best.powder_factor:.3f} kg/m3 · P80 {best.p80_cm:.0f} cm · "
                f"PPV {best.ppv_mm_s:.1f} mm/s · costo total {best.cost_total_usd_t:.3f} USD/t "
                f"({trend} {abs(saving):.3f} USD/t frente al diseno actual).\n"
                f"{len(result.feasible)} de {len(result.scenarios)} escenarios cumplen todas las "
                "restricciones ambientales.")
            self.verdict.setVisible(True)

    # -- internos ----------------------------------------------------------
    def _emit_run(self) -> None:
        self.run_requested.emit(self.settings())

    def _apply_best(self) -> None:
        if self._result and self._result.best:
            self.apply_requested.emit(self._result.best)

    def _on_select(self) -> None:
        if not self._result:
            return
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        idx = rows[0].row()
        item = self.table.item(idx, 0)
        if item is None:
            return
        burden = float(item.text())
        match = next((s for s in self._result.scenarios if abs(s.burden_m - burden) < 1e-6), None)
        if match is None:
            self.detail.setText("")
        elif match.violations:
            self.detail.setText("Restricciones incumplidas: " + " · ".join(match.violations))
        else:
            self.detail.setText("Escenario viable: cumple todas las restricciones declaradas.")
