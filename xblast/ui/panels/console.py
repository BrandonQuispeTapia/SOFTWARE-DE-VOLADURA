"""Registro de actividad y tabla de taladros del panel inferior."""

from __future__ import annotations

import time
from typing import Optional, Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QTextCursor
from PySide6.QtWidgets import (
    QHBoxLayout, QPlainTextEdit, QVBoxLayout, QWidget,
)

from ...core.models import Hole
from .. import widgets as W
from ..theme import C, FONT_MONO, level_colors


class ConsolePanel(QWidget):
    """Bitacora de la sesion con niveles de severidad."""

    _COLORS = {
        "INFO": C["text_soft"],
        "OK": C["ok"],
        "AVISO": C["warn"],
        "ERROR": C["error"],
        "CALCULO": C["accent"],
    }

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        bar = QHBoxLayout()
        bar.addWidget(W.caption("Registro de la sesion"))
        bar.addStretch(1)
        btn_clear = W.button("Limpiar", "ghost", "reset")
        btn_clear.clicked.connect(lambda: self.view.clear())
        bar.addWidget(btn_clear)
        lay.addLayout(bar)

        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setMaximumBlockCount(3000)
        self.view.setStyleSheet(
            f"QPlainTextEdit{{background-color:{C['surface']};"
            f"border:1px solid {C['border']}; border-radius:5px;"
            f"font-family:'{FONT_MONO}', monospace; font-size:9pt;"
            f"color:{C['text']}; padding:6px;}}")
        lay.addWidget(self.view, 1)

    def log(self, message: str, level: str = "INFO") -> None:
        color = self._COLORS.get(level, C["text_soft"])
        stamp = time.strftime("%H:%M:%S")
        self.view.appendHtml(
            f'<span style="color:{C["text_muted"]}">{stamp}</span>  '
            f'<span style="color:{color}; font-weight:600">{level:<8}</span>'
            f'<span style="color:{C["text"]}">{message}</span>')
        self.view.moveCursor(QTextCursor.MoveOperation.End)


class HoleTablePanel(QWidget):
    """Tabla completa de taladros, exportable al area de operaciones."""

    hole_selected = Signal(str)
    export_requested = Signal()

    HEADERS = ["ID", "Este", "Norte", "Cota", "Long. (m)", "Diam. (mm)", "Taco (m)",
               "Carga (kg)", "Retardo (ms)", "Burden (m)", "Espac. (m)",
               "Volumen (m3)", "FP (kg/m3)", "X50 (cm)", "Tipo"]

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        bar = QHBoxLayout()
        self.count = W.caption("Sin taladros")
        bar.addWidget(self.count)
        bar.addStretch(1)
        btn = W.button("Exportar CSV", "ghost", "export")
        btn.clicked.connect(self.export_requested)
        bar.addWidget(btn)
        lay.addLayout(bar)

        self.table = W.DataTable(self.HEADERS)
        self.table.itemSelectionChanged.connect(self._on_select)
        lay.addWidget(self.table, 1)

    def set_holes(self, holes: Sequence[Hole]) -> None:
        rows = [[
            h.hid, round(h.easting, 2), round(h.northing, 2), round(h.collar_z, 2),
            round(h.length_m, 2), round(h.diameter_mm, 0), round(h.collar_stemming_m, 2),
            round(h.charge_kg, 1), round(h.delay_ms, 1), round(h.burden_real_m, 2),
            round(h.spacing_real_m, 2), round(h.volume_m3, 1), round(h.powder_factor, 3),
            round(h.x50_cm, 1), h.hole_type,
        ] for h in holes]
        self.table.set_rows(rows)
        self.count.setText(f"{len(holes)} taladros")

    def _on_select(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if rows:
            item = self.table.item(rows[0].row(), 0)
            if item is not None:
                self.hole_selected.emit(item.text())
