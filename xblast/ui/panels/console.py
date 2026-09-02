"""Registro de actividad y tabla de taladros del panel inferior."""

from __future__ import annotations

import time
from typing import Optional, Sequence

from PySide6.QtCore import QItemSelection, QItemSelectionModel, Qt, Signal
from PySide6.QtGui import QColor, QTextCursor
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QPlainTextEdit, QVBoxLayout, QWidget,
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
    """Tabla completa de taladros, sincronizada con la seleccion del visor."""

    selection_changed = Signal(list)
    export_requested = Signal()

    HEADERS = ["ID", "Este", "Norte", "Cota", "Long. (m)", "Diam. (mm)", "Taco (m)",
               "Carga (kg)", "Retardo (ms)", "Burden (m)", "Espac. (m)",
               "Volumen (m3)", "FP (kg/m3)", "X50 (cm)", "Tipo", "Carga manual"]

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
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.itemSelectionChanged.connect(self._on_select)
        lay.addWidget(self.table, 1)
        self._syncing = False

    def set_holes(self, holes: Sequence[Hole]) -> None:
        rows = [[
            h.hid, round(h.easting, 2), round(h.northing, 2), round(h.collar_z, 2),
            round(h.length_m, 2), round(h.diameter_mm, 0), round(h.collar_stemming_m, 2),
            round(h.charge_kg, 1), round(h.delay_ms, 1), round(h.burden_real_m, 2),
            round(h.spacing_real_m, 2), round(h.volume_m3, 1), round(h.powder_factor, 3),
            round(h.x50_cm, 1), h.hole_type,
            "Si" if getattr(h, 'charge_locked', False) else "",
        ] for h in holes]
        self._syncing = True
        self.table.set_rows(rows)
        self._syncing = False
        self.count.setText(f"{len(holes)} taladros")

    def set_selection(self, hids: Sequence[str]) -> None:
        """Refleja en la tabla la seleccion hecha en el visor.

        Las filas se marcan de una sola vez: ``selectRow`` en bucle iria
        reemplazando la seleccion anterior y solo quedaria la ultima.
        """
        wanted = set(hids)
        model = self.table.model()
        last_col = max(self.table.columnCount() - 1, 0)
        selection = QItemSelection()
        first = None
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item is not None and item.text() in wanted:
                selection.merge(
                    QItemSelection(model.index(r, 0), model.index(r, last_col)),
                    QItemSelectionModel.SelectionFlag.Select)
                first = r if first is None else first

        self._syncing = True
        self.table.selectionModel().select(
            selection,
            QItemSelectionModel.SelectionFlag.ClearAndSelect
            | QItemSelectionModel.SelectionFlag.Rows)
        if first is not None:
            self.table.scrollToItem(self.table.item(first, 0))
        self._syncing = False

    def _on_select(self) -> None:
        if self._syncing:
            return
        hids = []
        for index in self.table.selectionModel().selectedRows():
            item = self.table.item(index.row(), 0)
            if item is not None:
                hids.append(item.text())
        self.selection_changed.emit(hids)
