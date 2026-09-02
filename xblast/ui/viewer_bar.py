"""Barra de control del visor 3D.

Concentra todo lo que se hace con la camara y con la seleccion sin salir del
visor: estilo de navegacion, vistas normalizadas, giro alrededor del punto
focal, rotacion automatica, encuadres, exageracion vertical y las herramientas
de seleccion por ventana.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QScrollArea, QSizePolicy, QSlider,
    QToolButton, QVBoxLayout, QWidget,
)

from . import icons
from .theme import C, FONT_SIZE_SMALL
from .settings import settings as global_settings
from .viewer3d import NavMode, STANDARD_VIEWS


class ViewerBar(QFrame):
    """Controles de camara y seleccion situados sobre el visor."""

    nav_mode_changed = Signal(str)
    view_requested = Signal(str)
    orbit_requested = Signal(float, float)
    roll_requested = Signal(float)
    dolly_requested = Signal(float)
    spin_toggled = Signal(bool)
    box_selection_toggled = Signal(bool)
    focus_requested = Signal()
    zoom_selection_requested = Signal()
    fit_requested = Signal()
    projection_toggled = Signal()
    z_scale_changed = Signal(float)
    select_all_requested = Signal()
    invert_selection_requested = Signal()
    clear_selection_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("viewerBar")
        self.setStyleSheet(
            f"#viewerBar {{ background-color:{C['surface']};"
            f"border-bottom:1px solid {C['border']}; }}")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFixedHeight(42)
        outer.addWidget(scroll)

        content = QWidget()
        content.setStyleSheet(f"background-color:{C['surface']};")
        scroll.setWidget(content)

        lay = QHBoxLayout(content)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(4)

        # -- estilo de navegacion ----------------------------------------
        lay.addWidget(_label("Navegacion"))
        self.nav_combo = QComboBox()
        self.nav_combo.addItems([m.value for m in NavMode])
        self.nav_combo.setCurrentText(
            str(global_settings().get("interaction.nav_mode")))
        self.nav_combo.setMinimumWidth(150)
        self.nav_combo.setToolTip(
            "Tornamesa: gira alrededor del eje vertical sin que el modelo se voltee.\n"
            "Orbita libre: giro esferico sin restriccion, permite rotar el encuadre.\n"
            "Terreno: estilo de VTK para relieve, con la vertical anclada.\n"
            "Joystick: el movimiento continua mientras el boton siga pulsado.\n"
            "Planta 2D: desplazamiento y zoom sin giro, con proyeccion ortografica.")
        self.nav_combo.currentTextChanged.connect(self.nav_mode_changed)
        lay.addWidget(self.nav_combo)

        lay.addWidget(_separator())

        # -- vistas normalizadas -----------------------------------------
        lay.addWidget(_label("Vista"))
        self.view_combo = QComboBox()
        self.view_combo.addItems(list(STANDARD_VIEWS))
        self.view_combo.setMinimumWidth(120)
        self.view_combo.activated.connect(
            lambda _i: self.view_requested.emit(self.view_combo.currentText()))
        lay.addWidget(self.view_combo)

        self.btn_projection = _tool("settings", "Proyeccion paralela / perspectiva",
                                    checkable=True)
        self.btn_projection.clicked.connect(lambda: self.projection_toggled.emit())
        lay.addWidget(self.btn_projection)

        lay.addWidget(_separator())

        # -- giro alrededor del punto focal ------------------------------
        lay.addWidget(_label("Girar"))
        for icon, tip, az, el in (("left", "Girar a la izquierda", -1.0, 0.0),
                                  ("right", "Girar a la derecha", 1.0, 0.0),
                                  ("up", "Elevar la camara", 0.0, 1.0),
                                  ("down", "Bajar la camara", 0.0, -1.0)):
            btn = _tool(icon, f"{tip} alrededor del punto focal")
            btn.setAutoRepeat(True)
            btn.setAutoRepeatInterval(60)
            btn.clicked.connect(
                lambda _c=False, a=az, e=el: self.orbit_requested.emit(a, e))
            lay.addWidget(btn)

        for icon, tip, deg in (("rotate_ccw", "Rotar el encuadre a la izquierda", -10.0),
                               ("rotate_cw", "Rotar el encuadre a la derecha", 10.0)):
            btn = _tool(icon, tip)
            btn.setAutoRepeat(True)
            btn.clicked.connect(lambda _c=False, d=deg: self.roll_requested.emit(d))
            lay.addWidget(btn)

        self.btn_spin = _tool("reset", "Rotacion automatica continua", checkable=True)
        self.btn_spin.toggled.connect(self.spin_toggled)
        lay.addWidget(self.btn_spin)

        lay.addWidget(_separator())

        # -- encuadres ----------------------------------------------------
        for icon, tip, factor in (("zoom_in", "Acercar", 1.15),
                                  ("zoom_out", "Alejar", 1 / 1.15)):
            btn = _tool(icon, tip)
            btn.setAutoRepeat(True)
            btn.clicked.connect(lambda _c=False, f=factor: self.dolly_requested.emit(f))
            lay.addWidget(btn)

        self.btn_fit = _tool("zoom", "Encuadrar todo  (R)")
        self.btn_fit.clicked.connect(self.fit_requested)
        lay.addWidget(self.btn_fit)

        self.btn_zoom_sel = _tool("measure", "Encuadrar la seleccion")
        self.btn_zoom_sel.clicked.connect(self.zoom_selection_requested)
        lay.addWidget(self.btn_zoom_sel)

        self.btn_focus = _tool("pattern", "Centrar el giro en la seleccion  (F)")
        self.btn_focus.clicked.connect(self.focus_requested)
        lay.addWidget(self.btn_focus)

        lay.addWidget(_separator())

        # -- seleccion ----------------------------------------------------
        lay.addWidget(_label("Seleccion"))
        self.btn_box = _tool("grid", "Seleccionar por ventana", checkable=True)
        self.btn_box.toggled.connect(self.box_selection_toggled)
        lay.addWidget(self.btn_box)

        self.btn_all = _tool("layers", "Seleccionar todos los taladros")
        self.btn_all.clicked.connect(self.select_all_requested)
        lay.addWidget(self.btn_all)

        self.btn_invert = _tool("import", "Invertir la seleccion")
        self.btn_invert.clicked.connect(self.invert_selection_requested)
        lay.addWidget(self.btn_invert)

        self.btn_none = _tool("new", "Quitar la seleccion  (Esc)")
        self.btn_none.clicked.connect(self.clear_selection_requested)
        lay.addWidget(self.btn_none)

        # -- exageracion vertical ----------------------------------------
        lay.addWidget(_label("Escala Z"))
        self.z_slider = QSlider(Qt.Orientation.Horizontal)
        self.z_slider.setRange(10, 50)
        self.z_slider.setValue(
            int(float(global_settings().get("viewer.z_exaggeration")) * 10))
        self.z_slider.setFixedWidth(90)
        self.z_slider.setToolTip("Exageracion vertical del modelo")
        self.z_slider.valueChanged.connect(
            lambda v: (self.z_label.setText(f"{v / 10:.1f}x"),
                       self.z_scale_changed.emit(v / 10.0)))
        lay.addWidget(self.z_slider)
        self.z_label = _label("1.0x")
        self.z_label.setFixedWidth(32)
        lay.addWidget(self.z_label)
        lay.addStretch(1)

    # -- API ---------------------------------------------------------------

    def set_box_checked(self, checked: bool) -> None:
        self.btn_box.blockSignals(True)
        self.btn_box.setChecked(checked)
        self.btn_box.blockSignals(False)

    def set_spin_checked(self, checked: bool) -> None:
        self.btn_spin.blockSignals(True)
        self.btn_spin.setChecked(checked)
        self.btn_spin.blockSignals(False)

    def set_projection_checked(self, checked: bool) -> None:
        self.btn_projection.blockSignals(True)
        self.btn_projection.setChecked(checked)
        self.btn_projection.blockSignals(False)


# ---------------------------------------------------------------------------


def _label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color:{C['text_muted']}; font-size:{FONT_SIZE_SMALL}pt; padding:0 3px;")
    return lbl


def _separator() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.VLine)
    f.setStyleSheet(f"color:{C['divider']}; background-color:{C['divider']}; max-width:1px;")
    f.setFixedWidth(1)
    return f


def _tool(icon: str, tip: str, checkable: bool = False) -> QToolButton:
    btn = QToolButton()
    btn.setIcon(icons.icon(icon, 17))
    btn.setToolTip(tip)
    btn.setCheckable(checkable)
    return btn
