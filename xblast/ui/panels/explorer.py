"""Explorador de capas y elementos del proyecto.

Arbol de estilo SIG: cada capa se muestra, se oculta y expone sus datos.
Tambien concentra los accesos rapidos de importacion.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from ...core.models import HOLE_TYPE_COLORS, Hole
from .. import icons
from .. import widgets as W
from ..theme import C

#: Capas visibles y su icono.
LAYERS = [
    ("holes", "Taladros", "hole"),
    ("charges", "Columnas de carga", "charge"),
    ("labels", "Etiquetas de taladro", "table"),
    ("topography", "Topografia", "topo"),
    ("free_face", "Cara libre", "measure"),
    ("bench", "Piso de banco", "layers"),
    ("energy", "Campo de energia", "energy"),
]


class ExplorerPanel(QWidget):
    """Arbol de capas con control de visibilidad y resumen del proyecto."""

    layer_toggled = Signal(str, bool)
    hole_selected = Signal(str)
    import_requested = Signal(str)

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)

        row = QHBoxLayout()
        row.setSpacing(6)
        for key, label, icon_name in (("holes", "Taladros", "import"),
                                      ("topography", "Topografia", "topo")):
            btn = W.button(label, "", icon_name)
            btn.setToolTip(f"Importar {label.lower()} desde CSV")
            btn.clicked.connect(lambda _=False, k=key: self.import_requested.emit(k))
            row.addWidget(btn)
        lay.addLayout(row)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(14)
        self.tree.setRootIsDecorated(True)
        self.tree.setAnimated(True)
        self.tree.itemChanged.connect(self._on_item_changed)
        self.tree.itemClicked.connect(self._on_item_clicked)
        lay.addWidget(self.tree, 1)

        self._layer_items: Dict[str, QTreeWidgetItem] = {}
        self._layer_state: Dict[str, bool] = {}
        self._build_layers()

        self.stats = W.caption("Sin malla generada.")
        lay.addWidget(self.stats)

    # -- construccion ------------------------------------------------------
    def _build_layers(self) -> None:
        root = QTreeWidgetItem(self.tree, ["Capas"])
        root.setExpanded(True)
        root.setFlags(root.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)

        for key, label, icon_name in LAYERS:
            item = QTreeWidgetItem(root, [label])
            item.setIcon(0, icons.icon(icon_name, 16))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(0, Qt.CheckState.Checked if key in
                               ("holes", "charges", "topography", "free_face", "bench")
                               else Qt.CheckState.Unchecked)
            item.setData(0, Qt.ItemDataRole.UserRole, f"layer:{key}")
            self._layer_items[key] = item
            self._layer_state[key] = item.checkState(0) == Qt.CheckState.Checked

        self.types_root = QTreeWidgetItem(self.tree, ["Tipos de taladro"])
        self.types_root.setExpanded(True)
        self.holes_root = QTreeWidgetItem(self.tree, ["Taladros"])
        self.holes_root.setExpanded(False)

    # -- API ---------------------------------------------------------------
    def set_holes(self, holes: Sequence[Hole]) -> None:
        """Refresca el resumen por tipo y la lista de taladros."""
        self.types_root.takeChildren()
        self.holes_root.takeChildren()

        counts: Dict[str, int] = {}
        for h in holes:
            counts[h.hole_type] = counts.get(h.hole_type, 0) + 1

        for htype, n in sorted(counts.items()):
            item = QTreeWidgetItem(self.types_root, [f"{htype}  ({n})"])
            item.setIcon(0, icons.icon("hole", 15, HOLE_TYPE_COLORS.get(htype, C["text_soft"])))

        for h in holes[:500]:
            item = QTreeWidgetItem(
                self.holes_root,
                [f"{h.hid}   {h.charge_kg:,.0f} kg   {h.delay_ms:,.0f} ms"])
            item.setData(0, Qt.ItemDataRole.UserRole, f"hole:{h.hid}")
            item.setIcon(0, icons.icon("hole", 15, HOLE_TYPE_COLORS.get(h.hole_type, C["text_soft"])))

        self.holes_root.setText(0, f"Taladros ({len(holes)})")
        if len(holes) > 500:
            QTreeWidgetItem(self.holes_root, [f"… {len(holes) - 500} taladros mas"])

    def set_summary(self, text: str) -> None:
        self.stats.setText(text)

    def set_layer_available(self, key: str, available: bool) -> None:
        """Habilita o deshabilita una capa sin emitir cambios de visibilidad."""
        item = self._layer_items.get(key)
        if item is None:
            return
        blocked = self.tree.blockSignals(True)
        item.setDisabled(not available)
        self.tree.blockSignals(blocked)

    def layer_state(self, key: str) -> bool:
        item = self._layer_items.get(key)
        return bool(item and item.checkState(0) == Qt.CheckState.Checked)

    def set_layer_state(self, key: str, checked: bool, emit: bool = False) -> None:
        """Fija la visibilidad de una capa; por defecto sin reemitir la senal."""
        item = self._layer_items.get(key)
        if item is None or self._layer_state.get(key) == checked:
            return
        blocked = self.tree.blockSignals(not emit)
        item.setCheckState(0, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        self.tree.blockSignals(blocked)
        self._layer_state[key] = checked

    # -- eventos -----------------------------------------------------------
    def _on_item_changed(self, item: QTreeWidgetItem, _column: int) -> None:
        """Solo propaga cambios reales de visibilidad.

        ``itemChanged`` tambien se dispara al habilitar o renombrar un nodo; sin
        este filtro un refresco de escena volveria a disparar el refresco.
        """
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not (isinstance(data, str) and data.startswith("layer:")):
            return
        key = data.split(":", 1)[1]
        checked = item.checkState(0) == Qt.CheckState.Checked
        if self._layer_state.get(key) == checked:
            return
        self._layer_state[key] = checked
        self.layer_toggled.emit(key, checked)

    def _on_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(data, str) and data.startswith("hole:"):
            self.hole_selected.emit(data.split(":", 1)[1])
