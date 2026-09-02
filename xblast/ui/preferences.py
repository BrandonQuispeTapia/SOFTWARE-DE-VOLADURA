"""Diálogo de preferencias.

La ventana se construye entera a partir de :data:`xblast.ui.settings.SCHEMA`,
así que refleja automáticamente cualquier opción que se agregue al esquema. Los
cambios se aplican en caliente: cada control escribe en el almacén y este avisa
a quien corresponda.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDialog, QDoubleSpinBox, QFileDialog,
    QFontComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QScrollArea, QSpinBox,
    QStackedWidget, QVBoxLayout, QWidget,
)

from . import icons
from . import widgets as W
from .settings import SCHEMA, Group, Page, Setting, Settings, search
from .theme import C, FONT_SIZE_SMALL


class ColorButton(QPushButton):
    """Botón que muestra y elige un color."""

    color_changed = Signal(str)

    def __init__(self, value: str):
        super().__init__()
        self._value = value
        self.setFixedSize(QSize(78, 26))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(self._pick)
        self._refresh()

    def value(self) -> str:
        return self._value

    def set_value(self, value: str) -> None:
        self._value = value
        self._refresh()

    def _refresh(self) -> None:
        color = QColor(self._value)
        text_color = "#ffffff" if color.lightnessF() < 0.55 else "#1f2733"
        self.setText(self._value.upper())
        self.setStyleSheet(
            f"QPushButton {{ background-color:{self._value}; color:{text_color};"
            f"border:1px solid {C['border_strong']}; border-radius:4px;"
            f"font-family:Consolas, monospace; font-size:{FONT_SIZE_SMALL}pt; }}"
            f"QPushButton:hover {{ border:1px solid {C['accent']}; }}")

    def _pick(self) -> None:
        chosen = QColorDialog.getColor(QColor(self._value), self, "Elegir color")
        if chosen.isValid():
            self.set_value(chosen.name())
            self.color_changed.emit(self._value)


class PreferencesDialog(QDialog):
    """Ventana de preferencias con todas las opciones de la aplicación."""

    def __init__(self, store: Settings, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.store = store
        self._editors: Dict[str, QWidget] = {}
        self._page_index: Dict[str, int] = {}
        self._restart_pending = False

        self.setWindowTitle("Preferencias de X-BLAST")
        self.setMinimumSize(1000, 680)
        self.resize(1120, 760)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._build_sidebar())
        body.addWidget(self._build_pages(), 1)
        root.addLayout(body, 1)
        root.addWidget(self._build_footer())

        self.category_list.setCurrentRow(0)
        # Un cambio hecho fuera del dialogo —una paleta base, por ejemplo—
        # tiene que reflejarse en los controles.
        self.store.bulk_changed.connect(self._on_bulk_changed)

    # ------------------------------------------------------------------
    # Construcción
    # ------------------------------------------------------------------
    def _build_sidebar(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(238)
        panel.setStyleSheet(
            f"background-color:{C['surface_alt']};"
            f"border-right:1px solid {C['border']};")

        lay = QVBoxLayout(panel)
        lay.setContentsMargins(10, 12, 10, 12)
        lay.setSpacing(8)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Buscar una opción…")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.textChanged.connect(self._on_search)
        lay.addWidget(self.search_box)

        self.category_list = QListWidget()
        self.category_list.setFrameShape(QFrame.Shape.NoFrame)
        self.category_list.setStyleSheet(
            f"QListWidget {{ background:transparent; border:none; }}"
            f"QListWidget::item {{ padding:7px 8px; border-radius:5px; }}"
            f"QListWidget::item:selected {{ background-color:{C['accent_soft']};"
            f"color:{C['accent']}; }}")
        for page in SCHEMA:
            item = QListWidgetItem(icons.icon(page.icon, 17), page.title)
            item.setData(Qt.ItemDataRole.UserRole, page.key)
            self.category_list.addItem(item)
        self.category_list.currentRowChanged.connect(self._on_category)
        lay.addWidget(self.category_list, 1)

        self.counter = W.caption("")
        total = sum(len(g.settings) for p in SCHEMA for g in p.groups)
        self.counter.setText(f"{total} opciones en {len(SCHEMA)} categorías")
        lay.addWidget(self.counter)
        return panel

    def _build_pages(self) -> QWidget:
        self.stack = QStackedWidget()
        for i, page in enumerate(SCHEMA):
            self.stack.addWidget(self._build_page(page))
            self._page_index[page.key] = i

        self.results_page = QWidget()
        self._results_layout = QVBoxLayout(self.results_page)
        self._results_layout.setContentsMargins(0, 0, 0, 0)
        self.stack.addWidget(self.results_page)
        self._results_index = self.stack.count() - 1
        return self.stack

    def _build_page(self, page: Page) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(24, 20, 24, 24)
        lay.setSpacing(18)

        header = QVBoxLayout()
        header.setSpacing(3)
        header.addWidget(W.title(page.title, 1))
        if page.help:
            header.addWidget(W.caption(page.help))
        lay.addLayout(header)
        lay.addWidget(W.hline())

        for group in page.groups:
            lay.addWidget(self._build_group(group))

        lay.addStretch(1)
        scroll.setWidget(content)
        return scroll

    def _build_group(self, group: Group) -> QWidget:
        section = W.Section(group.title, group.help)
        for setting in group.settings:
            editor = self._build_editor(setting)
            self._editors[setting.key] = editor
            label = setting.label + (" *" if setting.restart else "")
            tip = setting.help
            if setting.restart:
                tip = (tip + "\n\n" if tip else "") + "* requiere reiniciar la aplicación."
            section.row(label, self._wrap_editor(setting, editor), tip)
        return section

    def _wrap_editor(self, setting: Setting, editor: QWidget) -> QWidget:
        """Editor con su botón de restablecer al valor por defecto."""
        holder = QWidget()
        lay = QHBoxLayout(holder)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        lay.addWidget(editor, 1)

        reset = QPushButton()
        reset.setIcon(icons.icon("reset", 14))
        reset.setFixedSize(24, 24)
        reset.setToolTip("Restablecer el valor por defecto")
        reset.setProperty("variant", "ghost")
        reset.clicked.connect(lambda _c=False, k=setting.key: self._reset_one(k))
        lay.addWidget(reset)
        return holder

    def _build_editor(self, s: Setting) -> QWidget:
        value = self.store.get(s.key)

        if s.kind == "bool":
            w = QCheckBox()
            w.setChecked(bool(value))
            w.toggled.connect(lambda v, k=s.key: self._commit(k, bool(v)))
            return w

        if s.kind == "int":
            w = QSpinBox()
            w.setRange(int(s.minimum), int(s.maximum))
            w.setSingleStep(max(int(s.step), 1))
            w.setValue(int(value))
            if s.suffix:
                w.setSuffix(f" {s.suffix}")
            w.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            w.setKeyboardTracking(False)
            w.valueChanged.connect(lambda v, k=s.key: self._commit(k, int(v)))
            return w

        if s.kind == "float":
            w = QDoubleSpinBox()
            w.setRange(float(s.minimum), float(s.maximum))
            w.setSingleStep(float(s.step))
            w.setDecimals(int(s.decimals))
            w.setValue(float(value))
            if s.suffix:
                w.setSuffix(f" {s.suffix}")
            w.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            w.setKeyboardTracking(False)
            w.valueChanged.connect(lambda v, k=s.key: self._commit(k, float(v)))
            return w

        if s.kind == "choice":
            w = QComboBox()
            w.addItems(list(s.options))
            if value in s.options:
                w.setCurrentText(str(value))
            w.currentTextChanged.connect(lambda v, k=s.key: self._commit(k, v))
            return w

        if s.kind == "color":
            w = ColorButton(str(value))
            w.color_changed.connect(lambda v, k=s.key: self._commit(k, v))
            return w

        if s.kind == "font":
            w = QFontComboBox()
            w.setCurrentText(str(value))
            w.setEditable(False)
            w.currentTextChanged.connect(lambda v, k=s.key: self._commit(k, v))
            return w

        w = QLineEdit(str(value))
        w.editingFinished.connect(lambda k=s.key, e=w: self._commit(k, e.text()))
        return w

    def _build_footer(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet(
            f"background-color:{C['surface']}; border-top:1px solid {C['border']};")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(14, 9, 14, 9)
        lay.setSpacing(7)

        self.restart_note = QLabel("")
        self.restart_note.setStyleSheet(f"color:{C['warn']}; font-size:{FONT_SIZE_SMALL}pt;")
        lay.addWidget(self.restart_note)
        lay.addStretch(1)

        for text, variant, icon, slot in (
            ("Importar", "", "import", self._import),
            ("Exportar", "", "export", self._export),
            ("Restablecer categoría", "", "reset", self._reset_page),
            ("Restablecer todo", "danger", "reset", self._reset_all),
        ):
            btn = W.button(text, variant, icon)
            btn.clicked.connect(slot)
            lay.addWidget(btn)

        close = W.button("Cerrar", "primary", "check")
        close.clicked.connect(self.accept)
        lay.addWidget(close)
        return bar

    # ------------------------------------------------------------------
    # Eventos
    # ------------------------------------------------------------------
    def _commit(self, key: str, value: Any) -> None:
        # La paleta base se reaplica aunque se vuelva a elegir la misma, para
        # descartar los retoques de color que el usuario hizo despues.
        self.store.set(key, value, force=(key == "appearance.theme"))
        from .settings import BY_KEY
        if BY_KEY[key].restart and not self._restart_pending:
            self._restart_pending = True
            self.restart_note.setText(
                "Algunos cambios se aplicarán al reiniciar la aplicación.")

    def _reload_editor(self, key: str) -> None:
        """Refresca un control con el valor vigente sin reemitir señales."""
        holder = self._editors.get(key)
        if holder is None:
            return
        value = self.store.get(key)
        holder.blockSignals(True)
        if isinstance(holder, QCheckBox):
            holder.setChecked(bool(value))
        elif isinstance(holder, (QSpinBox, QDoubleSpinBox)):
            holder.setValue(value)
        elif isinstance(holder, ColorButton):
            holder.set_value(str(value))
        elif isinstance(holder, QComboBox):
            holder.setCurrentText(str(value))
        elif isinstance(holder, QLineEdit):
            holder.setText(str(value))
        holder.blockSignals(False)

    def _reload_all(self) -> None:
        for key in list(self._editors):
            self._reload_editor(key)

    def _on_bulk_changed(self, keys: List[str]) -> None:
        for key in keys:
            self._reload_editor(key)

    def _reset_one(self, key: str) -> None:
        self.store.reset(key)
        self._reload_editor(key)

    def _reset_page(self) -> None:
        row = self.category_list.currentRow()
        if not 0 <= row < len(SCHEMA):
            return
        page = SCHEMA[row]
        if QMessageBox.question(
                self, "Restablecer categoría",
                f"¿Restablecer todas las opciones de «{page.title}» "
                "a sus valores por defecto?") != QMessageBox.StandardButton.Yes:
            return
        for key in self.store.reset_page(page.key):
            self._reload_editor(key)

    def _reset_all(self) -> None:
        if QMessageBox.question(
                self, "Restablecer todo",
                "¿Restablecer las 229 opciones de la aplicación a sus valores "
                "por defecto? Esta acción no se puede deshacer.") != QMessageBox.StandardButton.Yes:
            return
        self.store.reset_all()
        self._reload_all()

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar preferencias", "preferencias_xblast.json",
            "Archivo JSON (*.json)")
        if path:
            out = self.store.export_to(path)
            QMessageBox.information(self, "Preferencias exportadas",
                                    f"Se guardaron en:\n{out}")

    def _import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Importar preferencias", "", "Archivo JSON (*.json)")
        if not path:
            return
        try:
            changed = self.store.import_from(path)
        except Exception as exc:
            QMessageBox.critical(self, "No se pudo importar", str(exc))
            return
        self._reload_all()
        QMessageBox.information(self, "Preferencias importadas",
                                f"Se aplicaron {len(changed)} opciones.")

    def _on_category(self, row: int) -> None:
        if 0 <= row < len(SCHEMA):
            self.stack.setCurrentIndex(self._page_index[SCHEMA[row].key])

    def _on_search(self, query: str) -> None:
        """Muestra los resultados de la búsqueda como una página propia."""
        if not query.strip():
            self._on_category(self.category_list.currentRow())
            return

        while self._results_layout.count():
            item = self._results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        hits = search(query)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(24, 20, 24, 24)
        lay.setSpacing(14)

        lay.addWidget(W.title(f"{len(hits)} resultados para «{query}»", 1))
        lay.addWidget(W.hline())

        if not hits:
            lay.addWidget(W.caption("Ninguna opción coincide con la búsqueda."))
        else:
            by_page: Dict[str, List] = {}
            for page, group, setting in hits:
                by_page.setdefault(f"{page.title} · {group.title}", []).append(setting)
            for title, found in by_page.items():
                section = W.Section(title, "")
                for setting in found:
                    editor = self._build_editor(setting)
                    self._editors[setting.key] = editor
                    section.row(setting.label, self._wrap_editor(setting, editor),
                                setting.help)
                lay.addWidget(section)

        lay.addStretch(1)
        scroll.setWidget(content)
        self._results_layout.addWidget(scroll)
        self.stack.setCurrentIndex(self._results_index)

    def go_to(self, page_key: str) -> None:
        """Abre el diálogo en una categoría concreta."""
        for row, page in enumerate(SCHEMA):
            if page.key == page_key:
                self.category_list.setCurrentRow(row)
                return

    def accept(self) -> None:
        self.store.save()
        super().accept()

    def reject(self) -> None:
        self.store.save()
        super().reject()
