"""Panel de propiedades y edición del taladro activo.

No es una ficha de solo lectura: desde aquí se cambia el tipo de taladro, su
geometría, su retardo y su columna de carga completa, y se replican esos
cambios sobre toda la selección. Es el equivalente a intervenir un taladro
concreto sobre el plano de carguío.
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)

from ...core.models import HOLE_TYPE_COLORS, Hole, HoleType
from .. import widgets as W
from ..theme import C, FONT_SIZE_SMALL
from .deck_editor import DeckEditor


class PropertiesPanel(QWidget):
    """Ficha editable del taladro activo y acciones sobre la selección."""

    hole_edited = Signal(str)              # geometría, tipo o retardo
    charge_edited = Signal(str)            # columna de carga
    bulk_type_requested = Signal(str)      # aplicar tipo a la selección
    bulk_charge_requested = Signal(str)    # copiar la columna a la selección
    reset_charge_requested = Signal()      # devolver la selección a la regla global
    zoom_requested = Signal()

    def __init__(self):
        super().__init__()
        self._hole: Optional[Hole] = None
        self._selection: List[str] = []
        self._loading = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(9)

        header = QHBoxLayout()
        header.setSpacing(8)
        self.title = W.title("Sin selección", 1)
        self.chip = W.StatusChip("—", "info")
        header.addWidget(self.title)
        header.addStretch(1)
        header.addWidget(self.chip)
        lay.addLayout(header)

        self.selection_note = QLabel("")
        self.selection_note.setWordWrap(True)
        self.selection_note.setStyleSheet(
            f"color:{C['accent']}; background-color:{C['accent_soft']};"
            f"border-radius:4px; padding:6px 9px; font-size:{FONT_SIZE_SMALL}pt;")
        self.selection_note.setVisible(False)
        lay.addWidget(self.selection_note)

        self.empty = W.caption(
            "Haga clic en un taladro del visor 3D para editarlo.\n\n"
            "Ctrl + clic agrega a la selección, Shift + clic la alterna, y el botón "
            "de selección por ventana permite encerrar varios taladros a la vez.")
        lay.addWidget(self.empty)

        # -- cuerpo ------------------------------------------------------
        self.body = QWidget()
        body = QVBoxLayout(self.body)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(11)

        self._build_classification(body)
        self._build_geometry(body)
        self._build_timing(body)
        self._build_charge(body)
        self._build_results(body)
        body.addStretch(1)

        scroll = W.ScrollPanel(spacing=0, margins=(0, 0, 6, 0))
        scroll.add(self.body)
        lay.addWidget(scroll, 1)
        self.body.setVisible(False)

    # ------------------------------------------------------------------
    # Construcción
    # ------------------------------------------------------------------
    def _build_classification(self, body: QVBoxLayout) -> None:
        section = W.Section(
            "Clasificación",
            "Producción, precorte, recorte, amortiguado y alivio determinan el color "
            "en el visor y las reglas de revisión que se aplican.")
        self.type_combo = section.row("Tipo", W.combo([t.value for t in HoleType]))
        self.type_combo.currentTextChanged.connect(self._on_type_changed)

        row = QHBoxLayout()
        row.setSpacing(5)
        self.btn_type_selection = W.button("Aplicar tipo a la selección", "", "layers")
        self.btn_type_selection.clicked.connect(
            lambda: self.bulk_type_requested.emit(self.type_combo.currentText()))
        row.addWidget(self.btn_type_selection)
        self.btn_zoom = W.button("Encuadrar", "ghost", "zoom")
        self.btn_zoom.clicked.connect(self.zoom_requested)
        row.addWidget(self.btn_zoom)
        holder = QWidget()
        holder.setLayout(row)
        section.add(holder)
        body.addWidget(section)

    def _build_geometry(self, body: QVBoxLayout) -> None:
        section = W.Section("Geometría", "Valores del taladro seleccionado.")
        self.diameter = section.row("Diámetro", W.spin(50, 450, 152, 1, "mm", 0))
        self.length = section.row("Longitud", W.spin(0.5, 80, 11.5, 0.1, "m"))
        self.subdrill = section.row("Subperforación", W.spin(0, 8, 1.2, 0.1, "m"))
        self.dip = section.row("Inclinación", W.spin(0, 45, 15, 1, "° desde vertical", 0))
        self.azimuth = section.row("Azimut", W.spin(0, 360, 0, 5, "°", 0))
        self.collar_z = section.row("Cota de collar", W.spin(-5000, 9000, 0, 0.5, "m"))
        self.easting = section.row("Este", W.spin(-1e7, 1e7, 0, 0.5, "m"))
        self.northing = section.row("Norte", W.spin(-1e7, 1e7, 0, 0.5, "m"))
        for w in (self.diameter, self.length, self.subdrill, self.dip,
                  self.azimuth, self.collar_z, self.easting, self.northing):
            w.valueChanged.connect(self._on_geometry_changed)
        body.addWidget(section)

    def _build_timing(self, body: QVBoxLayout) -> None:
        section = W.Section(
            "Secuencia",
            "Al fijar el retardo, el amarre automático deja de recalcularlo.")
        self.delay = section.row("Retardo", W.spin(0, 20000, 0, 1, "ms", 1))
        self.delay.valueChanged.connect(self._on_delay_changed)
        self.delay_locked = QCheckBox("Retardo fijado a mano")
        self.delay_locked.toggled.connect(self._on_delay_lock)
        section.add(self.delay_locked)
        body.addWidget(section)

    def _build_charge(self, body: QVBoxLayout) -> None:
        section = W.Section(
            "Columna de carga",
            "Del collar hacia el fondo. Editarla desvincula el taladro de la regla "
            "global de carguío.")
        self.deck_editor = DeckEditor()
        self.deck_editor.changed.connect(self._on_charge_changed)
        section.add(self.deck_editor)

        row = QHBoxLayout()
        row.setSpacing(5)
        self.btn_copy_charge = W.button("Copiar a la selección", "", "export")
        self.btn_copy_charge.setToolTip(
            "Aplica esta misma columna a todos los taladros seleccionados")
        self.btn_copy_charge.clicked.connect(
            lambda: self.bulk_charge_requested.emit(self._hole.hid if self._hole else ""))
        row.addWidget(self.btn_copy_charge)

        self.btn_reset_charge = W.button("Volver a la regla global", "ghost", "reset")
        self.btn_reset_charge.setToolTip(
            "Descarta la carga manual y recarga con el panel de Carga")
        self.btn_reset_charge.clicked.connect(self.reset_charge_requested)
        row.addWidget(self.btn_reset_charge)
        holder = QWidget()
        holder.setLayout(row)
        section.add(holder)

        self.lock_note = QLabel("")
        self.lock_note.setWordWrap(True)
        self.lock_note.setStyleSheet(
            f"color:{C['warn']}; font-size:{FONT_SIZE_SMALL}pt;")
        self.lock_note.setVisible(False)
        section.add(self.lock_note)
        body.addWidget(section)

    def _build_results(self, body: QVBoxLayout) -> None:
        section = W.Section("Resultados del análisis")
        self.results = W.KeyValueTable()
        section.add(self.results)
        body.addWidget(section)

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------
    def show_hole(self, hole: Optional[Hole], selection: Optional[List[str]] = None) -> None:
        """Muestra el taladro activo y el tamaño de la selección."""
        self._selection = list(selection or ([hole.hid] if hole else []))
        self._hole = hole
        self.empty.setVisible(hole is None)
        self.body.setVisible(hole is not None)

        n = len(self._selection)
        self.selection_note.setVisible(n > 1)
        if n > 1:
            self.selection_note.setText(
                f"{n} taladros seleccionados. Los campos editan solo el taladro activo; "
                "los botones «Aplicar tipo a la selección» y «Copiar a la selección» "
                "replican el cambio sobre todos.")
        self.btn_type_selection.setEnabled(n > 1)
        self.btn_copy_charge.setEnabled(n > 1)

        if hole is None:
            self.title.setText("Sin selección")
            self.chip.set_status("—", "info")
            return

        self.title.setText(f"Taladro {hole.hid}")
        color = HOLE_TYPE_COLORS.get(hole.hole_type, C["text_soft"])
        self.chip.setText(hole.hole_type)
        self.chip.setStyleSheet(
            f"color:#ffffff; background-color:{color}; border-radius:9px;"
            f"padding:3px 10px; font-size:{FONT_SIZE_SMALL}pt; font-weight:700;")

        self._loading = True
        self.type_combo.setCurrentText(hole.hole_type)
        self.diameter.setValue(hole.diameter_mm)
        self.length.setValue(hole.length_m)
        self.subdrill.setValue(hole.subdrill_m)
        self.dip.setValue(hole.inclination_from_vertical_deg)
        self.azimuth.setValue(hole.azimuth_deg)
        self.collar_z.setValue(hole.collar_z)
        self.easting.setValue(hole.easting)
        self.northing.setValue(hole.northing)
        self.delay.setValue(hole.delay_ms)
        self.delay_locked.setChecked(hole.delay_locked)
        self.deck_editor.set_hole(hole)
        self._loading = False

        self.lock_note.setVisible(hole.charge_locked)
        if hole.charge_locked:
            self.lock_note.setText(
                "Carga manual: este taladro ya no sigue la regla global de carguío.")

        self.results.set_items([
            ("Cota de fondo", f"{hole.toe_z:,.2f} m"),
            ("Altura de banco", f"{hole.bench_height_m:.2f} m"),
            ("Fila / columna", f"{hole.row + 1} / {hole.col + 1}"),
            ("Carga total", f"{hole.charge_kg:,.1f} kg"),
            ("Energía", f"{hole.energy_mj:,.0f} MJ"),
            ("Longitud cargada", f"{hole.charge_length_m:.2f} m"),
            ("Taco de collar", f"{hole.collar_stemming_m:.2f} m"),
            ("Cebos", f"{hole.n_primers}"),
            ("Retardo con dispersión", f"{hole.delay_actual_ms:,.1f} ms"),
            ("Burden real", f"{hole.burden_real_m:.2f} m"),
            ("Burden de alivio", f"{hole.relief_burden_m:.2f} m"),
            ("Espaciamiento real", f"{hole.spacing_real_m:.2f} m"),
            ("Volumen de responsabilidad", f"{hole.volume_m3:,.1f} m3"),
            ("Factor de potencia", f"{hole.powder_factor:.3f} kg/m3"),
            ("Factor de energía", f"{hole.energy_factor:.2f} MJ/t"),
            ("X50 previsto", f"{hole.x50_cm:.1f} cm"),
            ("Índice de uniformidad", f"{hole.uniformity_n:.2f}"),
            ("Confinamiento", f"{hole.confinement:.2f}"),
        ])

    def current_hole(self) -> Optional[Hole]:
        return self._hole

    def pending_decks(self):
        """Columna tal como está en el editor, del fondo al collar."""
        return self.deck_editor.decks_bottom_up()

    # ------------------------------------------------------------------
    # Eventos
    # ------------------------------------------------------------------
    def _on_type_changed(self, new_type: str) -> None:
        if self._loading or self._hole is None or self._hole.hole_type == new_type:
            return
        self._hole.hole_type = new_type
        self.chip.setText(new_type)
        self.chip.setStyleSheet(
            f"color:#ffffff; background-color:{HOLE_TYPE_COLORS.get(new_type, C['text_soft'])};"
            f"border-radius:9px; padding:3px 10px; font-size:{FONT_SIZE_SMALL}pt; font-weight:700;")
        self.hole_edited.emit(self._hole.hid)

    def _on_geometry_changed(self, *_args) -> None:
        if self._loading or self._hole is None:
            return
        h = self._hole
        h.diameter_mm = self.diameter.value()
        h.length_m = self.length.value()
        h.subdrill_m = self.subdrill.value()
        h.dip_deg = 90.0 - self.dip.value()
        h.azimuth_deg = self.azimuth.value()
        h.collar_z = self.collar_z.value()
        h.easting = self.easting.value()
        h.northing = self.northing.value()
        h.bench_height_m = max(h.length_m - h.subdrill_m, 0.5)
        self.deck_editor.set_hole(h)
        self.hole_edited.emit(h.hid)

    def _on_delay_changed(self, value: float) -> None:
        if self._loading or self._hole is None:
            return
        self._hole.delay_ms = value
        self._hole.delay_actual_ms = value
        self._hole.delay_locked = True
        self.delay_locked.blockSignals(True)
        self.delay_locked.setChecked(True)
        self.delay_locked.blockSignals(False)
        self.hole_edited.emit(self._hole.hid)

    def _on_delay_lock(self, locked: bool) -> None:
        if self._loading or self._hole is None:
            return
        self._hole.delay_locked = locked
        self.hole_edited.emit(self._hole.hid)

    def _on_charge_changed(self) -> None:
        if self._loading or self._hole is None:
            return
        self.charge_edited.emit(self._hole.hid)
