"""Editor de la columna de carga de un taladro.

Permite armar la columna plataforma por plataforma —carga, taco o cámara de
aire— eligiendo producto, longitud, acoplamiento y número de cebos. Es el
equivalente a cargar el taladro en la mesa de diseño: se ve el orden real, del
fondo hacia el collar, y la suma disponible en todo momento.
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget,
)

from ...core import explosives as exdb
from ...core.models import Deck, DeckKind, Hole
from .. import icons
from .. import widgets as W
from ..theme import C, FONT_SIZE_SMALL

#: Color del indicador lateral de cada tipo de plataforma.
_KIND_COLOR = {
    DeckKind.CARGA: C["error"],
    DeckKind.TACO: "#9aa5b1",
    DeckKind.AIRE: C["info"],
}


class DeckRow(QFrame):
    """Una plataforma editable dentro de la columna."""

    changed = Signal()
    removed = Signal(object)
    moved = Signal(object, int)

    def __init__(self, deck: Deck, diameter_mm: float):
        super().__init__()
        self.deck = deck
        self.setProperty("role", "card")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 7)
        lay.setSpacing(5)

        top = QHBoxLayout()
        top.setSpacing(5)

        # Franja de color que identifica el tipo de plataforma de un vistazo.
        self._marker = QFrame()
        self._marker.setFixedWidth(4)
        self._marker.setMinimumHeight(20)
        top.addWidget(self._marker)

        self.kind = W.combo([k.value for k in DeckKind], _kind_value(deck.kind))
        self.kind.setFixedWidth(80)
        self.kind.currentTextChanged.connect(self._on_kind)
        top.addWidget(self.kind)

        self.length = W.spin(0.05, 60.0, deck.length_m, 0.1, "m")
        self.length.setFixedWidth(88)
        self.length.valueChanged.connect(self._emit)
        top.addWidget(self.length)

        top.addStretch(1)

        self.btn_up = _mini("up", "Subir la plataforma hacia el collar")
        self.btn_up.clicked.connect(lambda: self.moved.emit(self, +1))
        self.btn_down = _mini("down", "Bajar la plataforma hacia el fondo")
        self.btn_down.clicked.connect(lambda: self.moved.emit(self, -1))
        self.btn_del = _mini("close", "Eliminar la plataforma")
        self.btn_del.clicked.connect(lambda: self.removed.emit(self))
        for b in (self.btn_up, self.btn_down, self.btn_del):
            top.addWidget(b)
        lay.addLayout(top)

        self.detail = QWidget()
        det = QHBoxLayout(self.detail)
        det.setContentsMargins(13, 0, 0, 0)
        det.setSpacing(5)

        self.explosive = W.combo(exdb.suitable_for_diameter(diameter_mm),
                                 deck.explosive or "ANFO")
        self.explosive.setMinimumWidth(140)
        self.explosive.currentTextChanged.connect(self._emit)
        det.addWidget(self.explosive, 1)

        det.addWidget(_tiny("Acopl."))
        self.coupling = W.spin(0.2, 1.0, deck.coupling, 0.05, "", 2)
        self.coupling.setFixedWidth(62)
        self.coupling.setToolTip("Relacion diametro de carga / diametro de taladro")
        self.coupling.valueChanged.connect(self._emit)
        det.addWidget(self.coupling)

        det.addWidget(_tiny("Cebos"))
        self.primers = W.int_spin(0, 4, deck.primers)
        self.primers.setFixedWidth(50)
        self.primers.valueChanged.connect(self._emit)
        det.addWidget(self.primers)

        lay.addWidget(self.detail)

        self.summary = QLabel("")
        self.summary.setStyleSheet(
            f"color:{C['text_muted']}; font-size:{FONT_SIZE_SMALL}pt; background:transparent;")
        lay.addWidget(self.summary)

        self._diameter = diameter_mm
        self._refresh_kind_style()

    # -- API ---------------------------------------------------------------
    def to_deck(self) -> Deck:
        kind = DeckKind(self.kind.currentText())
        return Deck(
            kind=kind,
            length_m=self.length.value(),
            explosive=self.explosive.currentText() if kind is DeckKind.CARGA else None,
            coupling=self.coupling.value(),
            primers=self.primers.value() if kind is DeckKind.CARGA else 0,
        )

    def set_diameter(self, diameter_mm: float) -> None:
        self._diameter = diameter_mm
        current = self.explosive.currentText()
        self.explosive.blockSignals(True)
        self.explosive.clear()
        self.explosive.addItems(exdb.suitable_for_diameter(diameter_mm))
        if current:
            self.explosive.setCurrentText(current)
        self.explosive.blockSignals(False)
        self.refresh_summary()

    def refresh_summary(self) -> None:
        deck = self.to_deck()
        if deck.kind is DeckKind.CARGA and deck.explosive:
            exp = exdb.get(deck.explosive)
            lin = exp.linear_density_kg_m(self._diameter, deck.coupling)
            self.summary.setText(
                f"{lin:.2f} kg/m  ·  {lin * deck.length_m:,.1f} kg  ·  "
                f"{exp.borehole_pressure_gpa(deck.coupling) * 1000:,.0f} MPa en la pared")
        elif deck.kind is DeckKind.AIRE:
            self.summary.setText("Camara de aire: reduce consumo manteniendo la fragmentacion")
        else:
            self.summary.setText("Taco: confina los gases de la detonacion")

    # -- internos ----------------------------------------------------------
    def _on_kind(self, _text: str) -> None:
        self._refresh_kind_style()
        self._emit()

    def _refresh_kind_style(self) -> None:
        kind = DeckKind(self.kind.currentText())
        is_charge = kind is DeckKind.CARGA
        self.detail.setVisible(is_charge)
        self._marker.setStyleSheet(
            f"background-color:{_KIND_COLOR.get(kind, C['text_muted'])};"
            "border:none; border-radius:2px;")

    def _emit(self) -> None:
        self.refresh_summary()
        self.changed.emit()


class DeckEditor(QWidget):
    """Columna completa de un taladro, editable de fondo a collar."""

    changed = Signal()

    def __init__(self):
        super().__init__()
        self._hole: Optional[Hole] = None
        self._rows: List[DeckRow] = []
        self._blocked = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        bar = QHBoxLayout()
        bar.setSpacing(5)
        self.btn_charge = W.button("Carga", "", "charge")
        self.btn_charge.setToolTip("Agregar una plataforma de explosivo sobre las actuales")
        self.btn_charge.clicked.connect(lambda: self._add(DeckKind.CARGA))
        self.btn_stem = W.button("Taco", "", "layers")
        self.btn_stem.setToolTip("Agregar un taco intermedio o de collar")
        self.btn_stem.clicked.connect(lambda: self._add(DeckKind.TACO))
        self.btn_air = W.button("Aire", "", "energy")
        self.btn_air.setToolTip("Agregar una camara de aire")
        self.btn_air.clicked.connect(lambda: self._add(DeckKind.AIRE))
        for b in (self.btn_charge, self.btn_stem, self.btn_air):
            bar.addWidget(b)
        bar.addStretch(1)
        lay.addLayout(bar)

        self._rows_box = QVBoxLayout()
        self._rows_box.setSpacing(5)
        lay.addLayout(self._rows_box)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet(
            f"color:{C['text_muted']}; font-size:{FONT_SIZE_SMALL}pt;")
        lay.addWidget(self.status)

    # -- API ---------------------------------------------------------------
    def set_hole(self, hole: Optional[Hole]) -> None:
        """Carga la columna del taladro indicado, del collar hacia el fondo."""
        self._hole = hole
        self._blocked = True
        self._clear_rows()
        if hole is not None:
            for deck in reversed(hole.decks):          # se muestra de arriba hacia abajo
                self._append_row(Deck(deck.kind, deck.length_m, deck.explosive,
                                      deck.coupling, deck.primers))
        self._blocked = False
        self._refresh_status()

    def decks_bottom_up(self) -> List[Deck]:
        """Plataformas en el orden que espera el motor: del fondo al collar."""
        return [row.to_deck() for row in reversed(self._rows)]

    def set_enabled(self, enabled: bool) -> None:
        for w in (self.btn_charge, self.btn_stem, self.btn_air):
            w.setEnabled(enabled)
        for row in self._rows:
            row.setEnabled(enabled)

    # -- internos ----------------------------------------------------------
    def _clear_rows(self) -> None:
        while self._rows_box.count():
            item = self._rows_box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._rows = []

    def _append_row(self, deck: Deck) -> DeckRow:
        diameter = self._hole.diameter_mm if self._hole else 152.0
        row = DeckRow(deck, diameter)
        row.changed.connect(self._on_changed)
        row.removed.connect(self._remove_row)
        row.moved.connect(self._move_row)
        row.refresh_summary()
        self._rows_box.addWidget(row)
        self._rows.append(row)
        return row

    def _add(self, kind: DeckKind) -> None:
        if self._hole is None:
            return
        free = max(self._free_length(), 0.5)
        deck = Deck(kind, min(free, 2.0), "ANFO" if kind is DeckKind.CARGA else None,
                    1.0, 1 if kind is DeckKind.CARGA else 0)
        # Las plataformas nuevas entran por el collar, que es como se carga.
        self._blocked = True
        rows = [r.to_deck() for r in self._rows]
        self._clear_rows()
        self._append_row(deck)
        for d in rows:
            self._append_row(d)
        self._blocked = False
        self._on_changed()

    def _remove_row(self, row: DeckRow) -> None:
        if row not in self._rows:
            return
        self._rows.remove(row)
        self._rows_box.removeWidget(row)
        row.deleteLater()
        self._on_changed()

    def _move_row(self, row: DeckRow, direction: int) -> None:
        if row not in self._rows:
            return
        i = self._rows.index(row)
        j = i - direction                       # +1 sube en pantalla = hacia el collar
        if not (0 <= j < len(self._rows)):
            return
        self._blocked = True
        decks = [r.to_deck() for r in self._rows]
        decks[i], decks[j] = decks[j], decks[i]
        self._clear_rows()
        for d in decks:
            self._append_row(d)
        self._blocked = False
        self._on_changed()

    def _free_length(self) -> float:
        if self._hole is None:
            return 0.0
        used = sum(r.length.value() for r in self._rows)
        return self._hole.length_m - used

    def _on_changed(self) -> None:
        self._refresh_status()
        if not self._blocked:
            self.changed.emit()

    def _refresh_status(self) -> None:
        if self._hole is None:
            self.status.setText("")
            return
        used = sum(r.length.value() for r in self._rows)
        gap = self._hole.length_m - used
        charge = sum(r.length.value() for r in self._rows
                     if DeckKind(r.kind.currentText()) is DeckKind.CARGA)

        if abs(gap) <= 0.02:
            note = "la columna ocupa exactamente el taladro"
            color = C["ok"]
        elif gap > 0:
            note = f"faltan {gap:.2f} m, se completaran con taco de collar"
            color = C["warn"]
        else:
            note = f"sobran {-gap:.2f} m, se recortaran desde el collar"
            color = C["warn"]

        self.status.setText(
            f"Perforado {self._hole.length_m:.2f} m · cargado {charge:.2f} m · {note}")
        self.status.setStyleSheet(f"color:{color}; font-size:{FONT_SIZE_SMALL}pt;")


# ---------------------------------------------------------------------------


def _kind_value(kind) -> str:
    return kind.value if hasattr(kind, "value") else str(kind)


def _mini(icon_name: str, tip: str) -> QToolButton:
    """Boton compacto con icono vectorial."""
    btn = QToolButton()
    btn.setIcon(icons.icon(icon_name, 13))
    btn.setToolTip(tip)
    btn.setFixedSize(22, 22)
    return btn


def _tiny(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color:{C['text_muted']}; font-size:{FONT_SIZE_SMALL}pt;")
    return lbl
