"""Panel de secuencia de salida y detonadores electrónicos.

Reúne las tres formas de temporizar —patrón de amarre, vector de dirección y
punto central—, los límites del detonador elegido, el reparto de tiempos entre
plataformas y la simulación del disparo.

El vector de dirección está pensado para colocarse sin fricción: hay un botón
que lo dibuja con dos clics en el visor, otro que lo deduce de la cara libre, y
los campos numéricos quedan sincronizados con lo que se dibuje.
"""

from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QWidget

from ...core import detonators as detdb
from ...core.models import DirectionVector, InitiationSystem, TimingParams
from ...core.timing import TIE_PATTERNS, TIMING_MODES
from .. import widgets as W
from ..charts import TimingChart
from ..theme import C, FONT_SIZE_SMALL


class TimingPanel(W.ScrollPanel):
    """Amarre, detonador, plataformas y simulación."""

    changed = Signal()
    animate_requested = Signal()
    place_vector_requested = Signal()
    auto_vector_requested = Signal()
    vector_changed = Signal(object)          # DirectionVector
    check_requested = Signal()
    export_requested = Signal()
    overlay_changed = Signal()               # isolíneas o recorrido

    def __init__(self):
        super().__init__()
        t = TimingParams()
        self._vector: Optional[DirectionVector] = None
        self._loading = False

        self._build_mode(t)
        self._build_vector()
        self._build_pattern(t)
        self._build_detonator(t)
        self._build_decks(t)
        self._build_check()
        self._build_simulation()
        self.finish()

        self._connect()
        self._on_change()

    # ------------------------------------------------------------------
    # Construcción
    # ------------------------------------------------------------------
    def _build_mode(self, t: TimingParams) -> None:
        section = W.Section(
            "Método de secuencia",
            "Cómo se reparten los tiempos entre los taladros.")
        self.mode = section.row("Método", W.combo(TIMING_MODES, t.mode),
                                "El vector de dirección es la forma habitual con "
                                "detonadores electrónicos: los tiempos salen de la "
                                "posición de cada taladro respecto de una flecha.")
        self.add(section)

    def _build_vector(self) -> None:
        self.vector_section = W.Section(
            "Vector de dirección",
            "Marca de dónde arranca el disparo y hacia dónde avanza.")

        row = QHBoxLayout()
        row.setSpacing(5)
        self.btn_place = W.button("Colocar en el visor", "primary", "measure")
        self.btn_place.setToolTip(
            "Dibuje la flecha con dos clics: primero el origen, luego la punta")
        self.btn_place.setMinimumHeight(30)
        row.addWidget(self.btn_place, 1)
        self.btn_auto = W.button("Automático", "", "optimize")
        self.btn_auto.setToolTip(
            "Deduce el vector de la cara libre y del tamaño de la malla")
        row.addWidget(self.btn_auto)
        holder = QWidget()
        holder.setLayout(row)
        self.vector_section.add(holder)

        self.azimuth = self.vector_section.row(
            "Azimut", W.spin(0, 360, 180, 5, "°", 0),
            "Dirección de avance en planta; 0 es el norte.")
        self.angle = self.vector_section.row(
            "Ángulo", W.spin(0, 180, 90, 5, "°", 0),
            "Medido desde la vertical. 90° deja la flecha horizontal, que es lo "
            "normal en banco; por debajo, la secuencia progresa hacia abajo.")
        self.brb = self.vector_section.row(
            "BRB", W.spin(0, 60, 3.0, 0.1, "ms/m"),
            "Tiempo por metro en la dirección de avance: el alivio del burden. "
            "3 a 6 ms/m es el rango habitual.")
        self.brs = self.vector_section.row(
            "BRS", W.spin(0, 60, 0.0, 0.1, "ms/m"),
            "Tiempo por metro en el sentido transversal. En cero, cada fila sale "
            "entera a la vez; al subirlo, la salida se abre en abanico.")
        self.length = self.vector_section.row(
            "Longitud", W.spin(1, 2000, 30, 1, "m", 1))

        row2 = QHBoxLayout()
        row2.setSpacing(5)
        self.btn_invert = W.button("Invertir sentido", "ghost", "reset")
        row2.addWidget(self.btn_invert)
        row2.addStretch(1)
        holder2 = QWidget()
        holder2.setLayout(row2)
        self.vector_section.add(holder2)

        self.origin_label = W.caption("")
        self.vector_section.add(self.origin_label)
        self.add(self.vector_section)

    def _build_pattern(self, t: TimingParams) -> None:
        self.pattern_section = W.Section("Amarre", "Geometría de propagación del disparo.")
        self.pattern = self.pattern_section.row("Patrón", W.combo(TIE_PATTERNS, t.pattern))
        self.echelon = self.pattern_section.row(
            "Ángulo de echelon", W.spin(15, 75, t.echelon_deg, 5, "°", 0))
        self.hole_delay = self.pattern_section.row(
            "Entre taladros", W.spin(0, 200, t.hole_delay_ms, 1, "ms", 0),
            "Controla la interacción entre cargas vecinas de una misma fila.")
        self.row_delay = self.pattern_section.row(
            "Entre filas", W.spin(0, 500, t.row_delay_ms, 5, "ms", 0),
            "Debe dar tiempo al burden de la fila previa para desplazarse.")
        self.radial = self.pattern_section.row(
            "Salida radial", W.spin(0.1, 60, t.radial_ms_m, 0.1, "ms/m"),
            "Tiempo por metro desde el punto de arranque, en el método de punto central.")
        self.add(self.pattern_section)

    def _build_detonator(self, t: TimingParams) -> None:
        section = W.Section(
            "Detonador",
            "Marca el rango de tiempos programables, el incremento mínimo y la "
            "precisión real del disparo.")
        self.detonator = section.row("Modelo", W.combo(detdb.names(), t.detonator))
        self.det_summary = W.caption("")
        section.add(self.det_summary)
        self.snap = QCheckBox("Ajustar los tiempos al incremento programable")
        self.snap.setChecked(t.snap_to_increment)
        section.add(self.snap)
        self.in_hole = section.row(
            "Retardo de fondo", W.spin(0, 2000, t.in_hole_delay_ms, 25, "ms", 0))
        self.add(section)

    def _build_decks(self, t: TimingParams) -> None:
        section = W.Section(
            "Plataformas",
            "Seccionar la columna solo baja la vibración si cada plataforma sale "
            "en un instante distinto.")
        self.deck_delay = section.row(
            "Entre plataformas", W.spin(0, 500, t.deck_delay_ms, 1, "ms", 0),
            "Retardo entre plataformas de carga del mismo taladro, del fondo al collar.")
        self.inner_delay = section.row(
            "Entre cebos", W.spin(0, 200, t.inner_delay_ms, 1, "ms", 0),
            "Separación entre cebos dentro de una misma plataforma.")
        self.window = section.row(
            "Ventana de cooperación", W.spin(2, 50, t.cooperation_window_ms, 1, "ms", 0),
            "Cargas que detonan dentro de esta ventana suman su efecto sísmico "
            "(regla de 8 ms de la USBM).")
        self.add(section)

    def _build_check(self) -> None:
        section = W.Section("Verificación temporal")
        self.out_hole_relief = section.row("Alivio entre taladros", _value("—"))
        self.out_row_relief = section.row("Alivio entre filas", _value("—"))
        self.out_duration = section.row("Duración del disparo", _value("—"))
        self.out_mic = section.row("Carga operante (MIC)", _value("—"))
        self.out_overlap = section.row("Probabilidad de solape", _value("—"))

        row = QHBoxLayout()
        row.setSpacing(5)
        self.btn_check = W.button("Comprobar secuencia", "", "check")
        self.btn_check.setToolTip(
            "Valida los tiempos contra los límites del detonador antes de bajarlos a la máquina")
        row.addWidget(self.btn_check)
        self.btn_export = W.button("Exportar a máquina", "", "export")
        row.addWidget(self.btn_export)
        holder = QWidget()
        holder.setLayout(row)
        section.add(holder)

        self.findings = W.FindingsList()
        section.add(self.findings)
        self.add(section)

    def _build_simulation(self) -> None:
        section = W.Section("Simulación")
        self.chart = TimingChart()
        self.chart.setMinimumHeight(210)
        section.add(self.chart)

        self.speed = section.row(
            "Velocidad", W.combo(["0.05x", "0.1x", "0.25x", "0.5x", "1x", "2x", "5x"], "0.25x"),
            "Por debajo de 1x el disparo se ve en cámara lenta.")
        self.show_isolines = QCheckBox("Mostrar isócronas en el visor")
        section.add(self.show_isolines)
        self.isoline_interval = section.row(
            "Intervalo de isócronas", W.spin(5, 2000, 100, 5, "ms", 0),
            "Curvas de igual tiempo de detonación sobre la malla.")
        self.show_path = QCheckBox("Mostrar el recorrido del disparo")
        section.add(self.show_path)

        self.btn_animate = W.button("Animar secuencia", "primary", "run")
        self.btn_animate.setMinimumHeight(30)
        section.add(self.btn_animate)
        self.add(section)

    def _connect(self) -> None:
        for w in (self.hole_delay, self.row_delay, self.in_hole, self.window,
                  self.echelon, self.deck_delay, self.inner_delay, self.radial):
            w.valueChanged.connect(self._on_change)
        for w in (self.mode, self.pattern, self.detonator):
            w.currentTextChanged.connect(self._on_change)
        self.snap.toggled.connect(self._on_change)

        for w in (self.azimuth, self.angle, self.brb, self.brs, self.length):
            w.valueChanged.connect(self._on_vector_edited)

        self.btn_place.clicked.connect(self.place_vector_requested)
        self.btn_auto.clicked.connect(self.auto_vector_requested)
        self.btn_invert.clicked.connect(self._invert_vector)
        self.btn_animate.clicked.connect(self.animate_requested)
        self.btn_check.clicked.connect(self.check_requested)
        self.btn_export.clicked.connect(self.export_requested)

        self.show_isolines.toggled.connect(lambda _v: self.overlay_changed.emit())
        self.show_path.toggled.connect(lambda _v: self.overlay_changed.emit())
        self.isoline_interval.valueChanged.connect(lambda _v: self.overlay_changed.emit())

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------
    def params(self) -> TimingParams:
        return TimingParams(
            system=InitiationSystem.ELECTRONICO.value,
            hole_delay_ms=self.hole_delay.value(),
            row_delay_ms=self.row_delay.value(),
            in_hole_delay_ms=self.in_hole.value(),
            pattern=self.pattern.currentText(),
            echelon_deg=self.echelon.value(),
            cooperation_window_ms=self.window.value(),
            mode=self.mode.currentText(),
            detonator=self.detonator.currentText(),
            deck_delay_ms=self.deck_delay.value(),
            inner_delay_ms=self.inner_delay.value(),
            snap_to_increment=self.snap.isChecked(),
            radial_ms_m=self.radial.value(),
        )

    def set_params(self, t: TimingParams) -> None:
        widgets = (self.mode, self.pattern, self.detonator, self.hole_delay,
                   self.row_delay, self.in_hole, self.window, self.echelon,
                   self.deck_delay, self.inner_delay, self.radial, self.snap)
        for w in widgets:
            w.blockSignals(True)
        self.mode.setCurrentText(t.mode)
        self.pattern.setCurrentText(t.pattern)
        self.detonator.setCurrentText(t.detonator)
        self.hole_delay.setValue(t.hole_delay_ms)
        self.row_delay.setValue(t.row_delay_ms)
        self.in_hole.setValue(t.in_hole_delay_ms)
        self.window.setValue(t.cooperation_window_ms)
        self.echelon.setValue(t.echelon_deg)
        self.deck_delay.setValue(t.deck_delay_ms)
        self.inner_delay.setValue(t.inner_delay_ms)
        self.radial.setValue(t.radial_ms_m)
        self.snap.setChecked(t.snap_to_increment)
        for w in widgets:
            w.blockSignals(False)
        self._refresh_visibility()
        self._refresh_detonator()

    def vector(self) -> Optional[DirectionVector]:
        return self._vector

    def set_vector(self, vector: Optional[DirectionVector], notify: bool = False) -> None:
        """Refleja en los campos el vector vigente."""
        self._vector = vector
        if vector is None:
            self.origin_label.setText("Sin vector definido.")
            return

        self._loading = True
        for w, value in ((self.azimuth, vector.azimuth_deg), (self.angle, vector.angle_deg),
                         (self.brb, vector.brb_ms_m), (self.brs, vector.brs_ms_m),
                         (self.length, vector.length_m)):
            w.blockSignals(True)
            w.setValue(value)
            w.blockSignals(False)
        self._loading = False

        self.origin_label.setText(
            f"Origen en Este {vector.origin_x:,.1f} · Norte {vector.origin_y:,.1f} · "
            f"cota {vector.origin_z:,.1f} m")
        if notify:
            self.vector_changed.emit(vector)

    def set_placing(self, placing: bool) -> None:
        self.btn_place.setText("Cancelar colocación" if placing else "Colocar en el visor")

    def animation_speed(self) -> float:
        return float(self.speed.currentText().rstrip("x"))

    def isolines_enabled(self) -> bool:
        return self.show_isolines.isChecked()

    def isolines_interval(self) -> float:
        return self.isoline_interval.value()

    def path_enabled(self) -> bool:
        return self.show_path.isChecked()

    def set_findings(self, findings) -> None:
        self.findings.set_findings(findings)

    def update_results(self, stats: Dict, cooperation: Dict, overlap: Dict,
                       edges, weights, max_allowed_kg: float = 0.0) -> None:
        """Refleja el diagnóstico temporal calculado por el motor."""
        self.out_hole_relief.setText(f"{stats.get('hole_relief_ms_m', 0):.1f} ms/m")
        _tint(self.out_hole_relief, stats.get("hole_relief_ms_m", 0), 2.5, 3.0, 10.0)

        self.out_row_relief.setText(f"{stats.get('row_relief_ms_m', 0):.1f} ms/m")
        _tint(self.out_row_relief, stats.get("row_relief_ms_m", 0), 8.0, 10.0, 35.0)

        self.out_duration.setText(f"{stats.get('total_duration_ms', 0):,.0f} ms")
        eventos = cooperation.get("n_events", 0)
        self.out_mic.setText(
            f"{cooperation.get('mic_kg', 0):,.0f} kg  "
            f"({cooperation.get('n_cooperating', 0)} de {eventos} eventos)")

        p_ov = overlap.get("p_overlap_pct", 0.0)
        self.out_overlap.setText(f"{p_ov:.0f} %")
        _tint(self.out_overlap, 100.0 - p_ov, 55.0, 75.0, 101.0)

        self.chart.update_data(edges, weights, max_allowed_kg, self.window.value())

    def set_animating(self, running: bool) -> None:
        self.btn_animate.setText("Detener animación" if running else "Animar secuencia")

    # ------------------------------------------------------------------
    # Eventos
    # ------------------------------------------------------------------
    def _on_change(self, *_args) -> None:
        self._refresh_visibility()
        self._refresh_detonator()
        self.changed.emit()

    def _refresh_visibility(self) -> None:
        mode = self.mode.currentText()
        is_vector = mode == "Vector de direccion"
        is_point = mode == "Punto central"

        self.vector_section.setVisible(is_vector or is_point)
        self.pattern_section.setVisible(not is_vector)

        # En salida radial la flecha solo marca el punto de arranque.
        for w in (self.brb, self.brs, self.angle, self.length):
            w.setEnabled(is_vector)
        self.azimuth.setEnabled(is_vector)
        self.radial.setEnabled(is_point)
        self.pattern.setEnabled(not is_vector and not is_point)
        self.echelon.setEnabled(self.pattern.currentText() == "Diagonal (echelon)"
                                and not is_vector and not is_point)
        self.hole_delay.setEnabled(not is_vector and not is_point)
        self.row_delay.setEnabled(not is_vector and not is_point)
        self.btn_place.setText(
            "Colocar punto de arranque" if is_point else "Colocar en el visor")

    def _refresh_detonator(self) -> None:
        det = detdb.get(self.detonator.currentText())
        self.det_summary.setText(f"{det.manufacturer} · {det.summary}")

    def _on_vector_edited(self, *_args) -> None:
        if self._loading or self._vector is None:
            return
        self._vector.azimuth_deg = self.azimuth.value()
        self._vector.angle_deg = self.angle.value()
        self._vector.brb_ms_m = self.brb.value()
        self._vector.brs_ms_m = self.brs.value()
        self._vector.length_m = self.length.value()
        self.vector_changed.emit(self._vector)

    def _invert_vector(self) -> None:
        if self._vector is None:
            return
        # Se gira media vuelta y el origen pasa a la punta: la voladura sale por
        # el lado contrario sin tener que volver a dibujarla.
        tip = self._vector.tip
        self._vector.origin_x = float(tip[0])
        self._vector.origin_y = float(tip[1])
        self._vector.origin_z = float(tip[2])
        self._vector.azimuth_deg = (self._vector.azimuth_deg + 180.0) % 360.0
        self._vector.angle_deg = 180.0 - self._vector.angle_deg
        self.set_vector(self._vector, notify=True)


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
