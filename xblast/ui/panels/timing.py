"""Panel de secuencia de salida.

Configura el amarre y los retardos, y muestra el diagnostico temporal:
tiempo de alivio por metro, carga operante por ventana de cooperacion y
probabilidad de solape por dispersion del sistema de iniciacion.
"""

from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel

from ...core.models import InitiationSystem, TimingParams
from ...core.timing import TIE_PATTERNS
from .. import widgets as W
from ..charts import TimingChart
from ..theme import C


class TimingPanel(W.ScrollPanel):
    """Amarre, retardos y su verificacion."""

    changed = Signal()
    animate_requested = Signal()

    def __init__(self):
        super().__init__()
        t = TimingParams()

        system = W.Section(
            "Sistema de iniciacion",
            "Determina la dispersion de los retardos y, con ella, el riesgo de "
            "solape y de salida fuera de secuencia.")
        self.system = system.row("Sistema", W.combo([s.value for s in InitiationSystem], t.system))
        self.scatter = system.row("Dispersion tipica", _value("—"))
        self.add(system)

        tie = W.Section("Amarre", "Geometria de propagacion del disparo.")
        self.pattern = tie.row("Patron", W.combo(TIE_PATTERNS, t.pattern))
        self.echelon = tie.row("Angulo de echelon", W.spin(15, 75, t.echelon_deg, 5, "°", 0))
        self.add(tie)

        delays = W.Section("Retardos")
        self.hole_delay = delays.row("Entre taladros", W.spin(0, 200, t.hole_delay_ms, 1, "ms", 0),
                                     "Controla la interaccion entre cargas vecinas de una misma fila.")
        self.row_delay = delays.row("Entre filas", W.spin(0, 500, t.row_delay_ms, 5, "ms", 0),
                                    "Debe dar tiempo al burden de la fila previa para desplazarse.")
        self.in_hole = delays.row("Retardo de fondo", W.spin(0, 1000, t.in_hole_delay_ms, 25, "ms", 0))
        self.window = delays.row("Ventana de cooperacion", W.spin(2, 50, t.cooperation_window_ms, 1, "ms", 0),
                                 "Cargas que detonan dentro de esta ventana suman su efecto "
                                 "sismico (regla de 8 ms de la USBM).")
        self.add(delays)

        check = W.Section("Verificacion temporal")
        self.out_hole_relief = check.row("Alivio entre taladros", _value("—"))
        self.out_row_relief = check.row("Alivio entre filas", _value("—"))
        self.out_duration = check.row("Duracion del disparo", _value("—"))
        self.out_mic = check.row("Carga operante (MIC)", _value("—"))
        self.out_overlap = check.row("Probabilidad de solape", _value("—"))
        self.add(check)

        self.chart = TimingChart()
        self.chart.setMinimumHeight(220)
        self.add(self.chart)

        self.btn_animate = W.button("Animar secuencia", "primary", "run")
        self.btn_animate.setMinimumHeight(30)
        self.btn_animate.clicked.connect(self.animate_requested)
        self.add(self.btn_animate)
        self.finish()

        for w in (self.hole_delay, self.row_delay, self.in_hole, self.window, self.echelon):
            w.valueChanged.connect(self._on_change)
        for w in (self.system, self.pattern):
            w.currentTextChanged.connect(self._on_change)
        self._on_change()

    # -- API ---------------------------------------------------------------
    def params(self) -> TimingParams:
        return TimingParams(
            system=self.system.currentText(),
            hole_delay_ms=self.hole_delay.value(),
            row_delay_ms=self.row_delay.value(),
            in_hole_delay_ms=self.in_hole.value(),
            pattern=self.pattern.currentText(),
            echelon_deg=self.echelon.value(),
            cooperation_window_ms=self.window.value(),
        )

    def set_params(self, t: TimingParams) -> None:
        widgets = (self.system, self.pattern, self.hole_delay, self.row_delay,
                   self.in_hole, self.window, self.echelon)
        for w in widgets:
            w.blockSignals(True)
        self.system.setCurrentText(t.system)
        self.pattern.setCurrentText(t.pattern)
        self.hole_delay.setValue(t.hole_delay_ms)
        self.row_delay.setValue(t.row_delay_ms)
        self.in_hole.setValue(t.in_hole_delay_ms)
        self.window.setValue(t.cooperation_window_ms)
        self.echelon.setValue(t.echelon_deg)
        for w in widgets:
            w.blockSignals(False)
        self._update_scatter()

    def update_results(self, stats: Dict, cooperation: Dict, overlap: Dict,
                       edges, weights, max_allowed_kg: float = 0.0) -> None:
        """Refleja el diagnostico temporal calculado por el motor."""
        self.out_hole_relief.setText(f"{stats.get('hole_relief_ms_m', 0):.1f} ms/m")
        _tint(self.out_hole_relief, stats.get("hole_relief_ms_m", 0), 2.5, 3.0, 10.0)

        self.out_row_relief.setText(f"{stats.get('row_relief_ms_m', 0):.1f} ms/m")
        _tint(self.out_row_relief, stats.get("row_relief_ms_m", 0), 8.0, 10.0, 35.0)

        self.out_duration.setText(f"{stats.get('total_duration_ms', 0):,.0f} ms")
        mic = cooperation.get("mic_kg", 0.0)
        self.out_mic.setText(f"{mic:,.0f} kg  ({cooperation.get('n_cooperating', 0)} taladros)")

        p_ov = overlap.get("p_overlap_pct", 0.0)
        self.out_overlap.setText(f"{p_ov:.0f} %")
        _tint(self.out_overlap, 100.0 - p_ov, 55.0, 75.0, 101.0)

        self.chart.update_data(edges, weights, max_allowed_kg, self.window.value())

    def set_animating(self, running: bool) -> None:
        self.btn_animate.setText("Detener animacion" if running else "Animar secuencia")

    # -- internos ----------------------------------------------------------
    def _on_change(self, *_):
        self.echelon.setEnabled(self.pattern.currentText() == "Diagonal (echelon)")
        self._update_scatter()
        self.changed.emit()

    def _update_scatter(self) -> None:
        try:
            cv = InitiationSystem(self.system.currentText()).scatter_pct
        except ValueError:
            cv = 0.03
        self.scatter.setText(f"{cv * 100:.2f} % del retardo nominal")


def _value(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    lbl.setStyleSheet(f"color:{C['text']}; font-weight:600;")
    return lbl


def _tint(label: QLabel, value: float, hard_min: float, soft_min: float, soft_max: float) -> None:
    if value < hard_min:
        color = C["error"]
    elif value < soft_min or value > soft_max:
        color = C["warn"]
    else:
        color = C["ok"]
    label.setStyleSheet(f"color:{color}; font-weight:600;")
