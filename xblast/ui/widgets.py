"""Componentes de interfaz reutilizables.

Piezas pequenas y consistentes con las que se arman todos los paneles: campos
de formulario etiquetados, tarjetas de indicador, listas de hallazgos, tablas
de solo lectura y cabeceras de seccion.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QFrame,
    QGridLayout, QHBoxLayout, QHeaderView, QLabel, QPushButton, QScrollArea,
    QSizePolicy, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from . import icons
from .theme import C, FONT_MONO, FONT_SIZE_SMALL, level_colors

# ---------------------------------------------------------------------------
# Primitivas
# ---------------------------------------------------------------------------


def hline() -> QFrame:
    """Separador horizontal de 1 px."""
    f = QFrame()
    f.setProperty("role", "hline")
    f.setFixedHeight(1)
    return f


def caption(text: str) -> QLabel:
    """Texto auxiliar en gris."""
    lbl = QLabel(text)
    lbl.setProperty("role", "caption")
    lbl.setWordWrap(True)
    return lbl


def title(text: str, level: int = 1) -> QLabel:
    lbl = QLabel(text)
    lbl.setProperty("role", f"h{level}")
    return lbl


def spin(minimum: float, maximum: float, value: float, step: float = 0.1,
         suffix: str = "", decimals: int = 2) -> QDoubleSpinBox:
    """Campo numerico decimal con rango, paso y sufijo de unidad."""
    w = QDoubleSpinBox()
    w.setRange(minimum, maximum)
    w.setSingleStep(step)
    w.setDecimals(decimals)
    w.setValue(value)
    if suffix:
        w.setSuffix(f" {suffix}")
    w.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    w.setKeyboardTracking(False)
    return w


def int_spin(minimum: int, maximum: int, value: int, suffix: str = "") -> QSpinBox:
    w = QSpinBox()
    w.setRange(minimum, maximum)
    w.setValue(value)
    if suffix:
        w.setSuffix(f" {suffix}")
    w.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    w.setKeyboardTracking(False)
    return w


def combo(items: Sequence[str], current: str = "") -> QComboBox:
    w = QComboBox()
    w.addItems(list(items))
    if current and current in items:
        w.setCurrentText(current)
    return w


def button(text: str, variant: str = "", icon_name: str = "") -> QPushButton:
    """Boton con variante de estilo (``primary``, ``ghost``, ``danger``)."""
    b = QPushButton(text)
    if variant:
        b.setProperty("variant", variant)
        # Qt no reevalua los selectores por propiedad de un widget ya estilizado:
        # sin este repintado la variante se aplica a medias.
        b.style().unpolish(b)
        b.style().polish(b)
    if icon_name:
        color = C["text_on_accent"] if variant == "primary" else None
        b.setIcon(icons.icon(icon_name, 16, color))
    return b


# ---------------------------------------------------------------------------
# Contenedores
# ---------------------------------------------------------------------------


class Section(QWidget):
    """Bloque de formulario con titulo, descripcion opcional y filas."""

    def __init__(self, heading: str, description: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        head = QLabel(heading.upper())
        head.setStyleSheet(
            f"color:{C['text_muted']}; font-size:{FONT_SIZE_SMALL}pt;"
            "font-weight:700; letter-spacing:0.7px;")
        lay.addWidget(head)
        if description:
            lay.addWidget(caption(description))

        self.form = QFormLayout()
        self.form.setContentsMargins(0, 2, 0, 0)
        self.form.setSpacing(7)
        self.form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        lay.addLayout(self.form)

    #: Ancho de la columna de etiquetas, comun a todas las secciones.
    LABEL_WIDTH = 138

    def row(self, label: str, widget: QWidget, tooltip: str = "") -> QWidget:
        lbl = QLabel(label)
        lbl.setMinimumWidth(self.LABEL_WIDTH)
        lbl.setWordWrap(True)
        if tooltip:
            lbl.setToolTip(tooltip)
            widget.setToolTip(tooltip)
        self.form.addRow(lbl, widget)
        return widget

    def add(self, widget: QWidget) -> QWidget:
        self.form.addRow(widget)
        return widget


class ScrollPanel(QScrollArea):
    """Panel lateral con desplazamiento vertical y margenes uniformes."""

    def __init__(self, spacing: int = 14, margins: Tuple[int, int, int, int] = (12, 12, 12, 12)):
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._content = QWidget()
        self.body = QVBoxLayout(self._content)
        self.body.setContentsMargins(*margins)
        self.body.setSpacing(spacing)
        self.setWidget(self._content)

    def add(self, widget: QWidget) -> QWidget:
        self.body.addWidget(widget)
        return widget

    def add_layout(self, layout) -> None:
        self.body.addLayout(layout)

    def finish(self) -> None:
        """Empuja el contenido hacia arriba."""
        self.body.addStretch(1)


# ---------------------------------------------------------------------------
# Indicadores
# ---------------------------------------------------------------------------


class MetricTile(QFrame):
    """Tarjeta compacta de indicador: valor, unidad, etiqueta y estado."""

    def __init__(self, label: str, unit: str = "", tooltip: str = ""):
        super().__init__()
        self.setProperty("role", "card")
        self.setMinimumHeight(70)
        # Ignored en horizontal: la tarjeta se adapta al ancho que le de la
        # rejilla en vez de imponer el de su texto mas largo.
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        if tooltip:
            self.setToolTip(tooltip)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(11, 8, 11, 9)
        lay.setSpacing(1)

        self._label = QLabel(label.upper())
        self._label.setWordWrap(True)
        self._label.setMinimumWidth(1)
        self._label.setStyleSheet(
            f"color:{C['text_muted']}; font-size:{FONT_SIZE_SMALL}pt;"
            "font-weight:700; letter-spacing:0.5px; background:transparent;")

        row = QHBoxLayout()
        row.setSpacing(4)
        row.setContentsMargins(0, 0, 0, 0)
        self._value = QLabel("—")
        self._value.setStyleSheet(
            f"color:{C['text']}; font-size:15pt; font-weight:600; background:transparent;")
        self._unit = QLabel(unit)
        self._unit.setStyleSheet(
            f"color:{C['text_muted']}; font-size:{FONT_SIZE_SMALL}pt; background:transparent;")
        row.addWidget(self._value)
        row.addWidget(self._unit, 0, Qt.AlignmentFlag.AlignBottom)
        row.addStretch(1)

        lay.addWidget(self._label)
        lay.addLayout(row)

    def set_value(self, value: Any, level: str = "") -> None:
        """Actualiza el valor; ``level`` tine el numero segun el estado."""
        if isinstance(value, float):
            text = f"{value:,.2f}" if abs(value) < 1000 else f"{value:,.0f}"
        else:
            text = str(value)
        self._value.setText(text)
        color = level_colors(level)[0] if level else C["text"]
        self._value.setStyleSheet(
            f"color:{color}; font-size:15pt; font-weight:600; background:transparent;")


class MetricGrid(QWidget):
    """Rejilla de :class:`MetricTile` que se reordena segun el ancho disponible.

    El numero de columnas se recalcula en cada cambio de tamano a partir del
    ancho minimo de tarjeta, de modo que el tablero se adapta al panel sin
    desbordarlo cuando el usuario reduce el area de resultados.
    """

    MIN_TILE_WIDTH = 148

    def __init__(self, columns: int = 4):
        super().__init__()
        self._max_columns = columns
        self._columns = columns
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(8)
        self._tiles: Dict[str, MetricTile] = {}

    def add_tile(self, key: str, label: str, unit: str = "", tooltip: str = "") -> MetricTile:
        tile = MetricTile(label, unit, tooltip)
        self._tiles[key] = tile
        self._relayout()
        return tile

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout()

    def _available_width(self) -> int:
        """Ancho util real.

        Dentro de un area de desplazamiento el contenido adopta su propio ancho
        minimo, que aqui seria circular; por eso se mide el viewport.
        """
        node = self.parentWidget()
        while node is not None:
            if isinstance(node, QScrollArea):
                return node.viewport().width() - 26
            node = node.parentWidget()
        return self.width()

    def _relayout(self) -> None:
        """Reparte las tarjetas en tantas columnas como quepan."""
        width = max(self._available_width(), self.MIN_TILE_WIDTH)
        columns = max(1, min(self._max_columns,
                             (width + self._grid.spacing()) //
                             (self.MIN_TILE_WIDTH + self._grid.spacing())))
        if columns == self._columns and self._grid.count() == len(self._tiles):
            return
        self._columns = int(columns)
        while self._grid.count():
            self._grid.takeAt(0)
        for n, tile in enumerate(self._tiles.values()):
            self._grid.addWidget(tile, n // self._columns, n % self._columns)

    def set(self, key: str, value: Any, level: str = "") -> None:
        if key in self._tiles:
            self._tiles[key].set_value(value, level)

    def tiles(self) -> Dict[str, MetricTile]:
        return self._tiles


class StatusChip(QLabel):
    """Etiqueta compacta de estado con color semantico."""

    def __init__(self, text: str = "", level: str = "info"):
        super().__init__(text)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_status(text, level)

    def set_status(self, text: str, level: str = "info") -> None:
        fg, bg = level_colors(level)
        self.setText(text)
        self.setStyleSheet(
            f"color:{fg}; background-color:{bg}; border-radius:9px;"
            f"padding:3px 10px; font-size:{FONT_SIZE_SMALL}pt; font-weight:700;")


# ---------------------------------------------------------------------------
# Hallazgos
# ---------------------------------------------------------------------------


class FindingsList(QWidget):
    """Lista de hallazgos del analisis agrupados por severidad."""

    def __init__(self):
        super().__init__()
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(6)
        self._empty = caption("Ejecute el analisis para ver la revision del diseno.")
        self._lay.addWidget(self._empty)

    def set_findings(self, findings: Sequence[Dict[str, str]], show_ok: bool = True) -> None:
        while self._lay.count():
            item = self._lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        order = {"error": 0, "warn": 1, "ok": 2}
        items = [f for f in findings if show_ok or f.get("level") != "ok"]
        items.sort(key=lambda f: order.get(f.get("level", "ok"), 3))

        if not items:
            self._lay.addWidget(caption("Sin observaciones."))
            return

        for f in items:
            self._lay.addWidget(_FindingCard(f))
        self._lay.addStretch(1)


class _FindingCard(QFrame):
    """Tarjeta individual de hallazgo."""

    _ICONS = {"error": "warning", "warn": "warning", "ok": "check"}

    def __init__(self, finding: Dict[str, str]):
        super().__init__()
        level = finding.get("level", "ok")
        fg, bg = level_colors(level)
        self.setStyleSheet(
            f"QFrame{{background-color:{bg}; border:none;"
            f"border-left:3px solid {fg}; border-radius:4px;}}")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(9, 7, 9, 7)
        lay.setSpacing(8)

        ico = QLabel()
        ico.setPixmap(icons.pixmap(self._ICONS.get(level, "info"), 15, fg))
        ico.setFixedWidth(17)
        ico.setStyleSheet("background:transparent;")
        ico.setAlignment(Qt.AlignmentFlag.AlignTop)
        lay.addWidget(ico)

        text = QVBoxLayout()
        text.setSpacing(1)
        head = QLabel(finding.get("item", ""))
        head.setStyleSheet(f"color:{fg}; font-weight:700; background:transparent;")
        body = QLabel(finding.get("message", ""))
        body.setWordWrap(True)
        body.setStyleSheet(f"color:{C['text_soft']}; background:transparent;")
        text.addWidget(head)
        text.addWidget(body)
        lay.addLayout(text, 1)


# ---------------------------------------------------------------------------
# Tablas
# ---------------------------------------------------------------------------


class DataTable(QTableWidget):
    """Tabla de solo lectura con cabeceras fijas y ordenamiento."""

    def __init__(self, headers: Sequence[str] = ()):
        super().__init__()
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSortingEnabled(True)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(24)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setHighlightSections(False)
        if headers:
            self.set_headers(headers)

    def set_headers(self, headers: Sequence[str]) -> None:
        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(list(headers))
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

    def set_rows(self, rows: Sequence[Sequence[Any]],
                 highlight: Optional[Dict[int, str]] = None) -> None:
        """Rellena la tabla; ``highlight`` tine filas por indice y nivel."""
        self.setSortingEnabled(False)
        self.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                item = QTableWidgetItem()
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    item.setData(Qt.ItemDataRole.DisplayRole, value)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                else:
                    item.setText(str(value))
                if highlight and r in highlight:
                    item.setForeground(QColor(level_colors(highlight[r])[0]))
                self.setItem(r, c, item)
        self.setSortingEnabled(True)

    def set_dict_rows(self, rows: Sequence[Dict[str, Any]]) -> None:
        """Rellena a partir de diccionarios, usando sus claves como cabecera."""
        if not rows:
            self.setRowCount(0)
            return
        headers = list(rows[0].keys())
        self.set_headers(headers)
        self.set_rows([[r.get(h, "") for h in headers] for r in rows])


class KeyValueTable(QTableWidget):
    """Tabla de dos columnas para listas de propiedades."""

    def __init__(self):
        super().__init__()
        self.setColumnCount(2)
        self.setHorizontalHeaderLabels(["Propiedad", "Valor"])
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(23)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setAlternatingRowColors(True)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setHighlightSections(False)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def set_items(self, items: Sequence[Tuple[str, Any]]) -> None:
        """Rellena la tabla y la ajusta a su contenido.

        La tabla crece hasta mostrar todas sus filas: el desplazamiento lo hace
        el panel que la contiene, no la tabla, de modo que no aparezcan barras
        anidadas dentro de una ficha.
        """
        self.setRowCount(len(items))
        mono = QFont(FONT_MONO)
        mono.setPointSize(9)
        for r, (k, v) in enumerate(items):
            self.setItem(r, 0, QTableWidgetItem(str(k)))
            item = QTableWidgetItem(str(v))
            item.setFont(mono)
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.setItem(r, 1, item)
        self._fit_height(len(items))

    def _fit_height(self, rows: int) -> None:
        height = (self.horizontalHeader().height()
                  + rows * self.verticalHeader().defaultSectionSize() + 4)
        self.setFixedHeight(max(height, 40))
