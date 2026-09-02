"""Tema visual de X-BLAST.

Un solo lugar define color, tipografia y espaciado. La hoja de estilo sigue la
linea de las suites tecnicas de escritorio (QGIS, ArcGIS Pro): fondo claro,
superficies blancas, bordes de 1 px, acento reservado para la accion primaria
y color semantico solo donde comunica estado.

La paleta ``C``, la lista ``SERIES`` y las metricas tipograficas son mutables:
:func:`apply_settings` las reescribe en sitio con lo que el usuario haya
elegido en Preferencias, de modo que los modulos que hicieron
``from .theme import C`` ven el cambio sin reimportar.
"""

from __future__ import annotations

from typing import Dict, Tuple

# ---------------------------------------------------------------------------
# Paleta
# ---------------------------------------------------------------------------

C: Dict[str, str] = {
    # superficies
    "app": "#f4f6f8",          # fondo de la ventana
    "surface": "#ffffff",      # paneles y tarjetas
    "surface_alt": "#fafbfc",  # filas alternas, cabeceras suaves
    "sunken": "#eef1f4",       # campos y zonas hundidas
    # lineas
    "border": "#d8dee4",
    "border_strong": "#c2cad2",
    "divider": "#e7ebef",
    # texto
    "text": "#1f2733",
    "text_soft": "#5a6673",
    "text_muted": "#8b96a3",
    "text_on_accent": "#ffffff",
    # acento
    "accent": "#1668b3",
    "accent_hover": "#1a7bd0",
    "accent_press": "#12558f",
    "accent_soft": "#e8f1fa",
    # semantico
    "ok": "#1a7f4b",
    "ok_soft": "#e6f4ec",
    "warn": "#b26a00",
    "warn_soft": "#fdf3e2",
    "error": "#c0392b",
    "error_soft": "#fdecea",
    "info": "#0e7490",
    "info_soft": "#e4f4f7",
    # visor
    "viewport": "#eceff2",
    "grid": "#c8d0d8",
}

#: Colores de series para graficos (accesibles y consistentes con la UI).
SERIES = ["#1668b3", "#c0392b", "#1a7f4b", "#b26a00", "#6b4fa8", "#0e7490",
          "#a0522d", "#4a5568"]

FONT_FAMILY = "Segoe UI"
FONT_MONO = "Consolas"
FONT_SIZE = 9
FONT_SIZE_SMALL = 8
FONT_SIZE_TITLE = 11

#: Metricas de forma y densidad, reescritas por :func:`apply_settings`.
METRICS: Dict[str, int] = {
    "radius": 5,
    "pad_v": 5,       # relleno vertical de campos y botones
    "pad_h": 8,
    "row_height": 24,
    "spacing": 7,
}

#: Densidades disponibles: relleno vertical, alto de fila y espaciado.
DENSITIES: Dict[str, Tuple[int, int, int]] = {
    "Compacta": (3, 21, 5),
    "Normal": (5, 24, 7),
    "Amplia": (8, 30, 11),
}

#: Paletas base. El usuario puede retocar cualquier color por separado.
PRESETS: Dict[str, Dict[str, str]] = {
    "Claro": {
        "accent": "#1668b3", "accent_soft": "#e8f1fa", "surface": "#ffffff",
        "app": "#f4f6f8", "border": "#d8dee4", "text": "#1f2733",
        "text_soft": "#5a6673",
    },
    "Claro cálido": {
        "accent": "#b06818", "accent_soft": "#fbf1e6", "surface": "#fffdfa",
        "app": "#f7f4ef", "border": "#e2dbd0", "text": "#2b2620",
        "text_soft": "#6b6156",
    },
    "Gris técnico": {
        "accent": "#3f6b8a", "accent_soft": "#eaf0f4", "surface": "#fbfcfd",
        "app": "#eef1f3", "border": "#d2d8dd", "text": "#22282e",
        "text_soft": "#5c666f",
    },
    "Alto contraste": {
        "accent": "#0b4f9c", "accent_soft": "#dce9f7", "surface": "#ffffff",
        "app": "#ffffff", "border": "#4a5560", "text": "#000000",
        "text_soft": "#2c3540",
    },
}

#: Claves de preferencias que alimentan la paleta.
_COLOR_KEYS = {
    "appearance.accent": "accent",
    "appearance.accent_soft": "accent_soft",
    "appearance.surface": "surface",
    "appearance.app_background": "app",
    "appearance.border": "border",
    "appearance.text": "text",
    "appearance.text_soft": "text_soft",
    "appearance.ok": "ok",
    "appearance.warn": "warn",
    "appearance.error": "error",
    "appearance.info": "info",
}


def preset_values(name: str) -> Dict[str, str]:
    """Colores de una paleta base, con las claves de Preferencias."""
    base = PRESETS.get(name) or PRESETS["Claro"]
    inverse = {v: k for k, v in _COLOR_KEYS.items()}
    return {inverse[k]: v for k, v in base.items() if k in inverse}


def apply_settings(store) -> None:
    """Reescribe la paleta y las metricas con las preferencias del usuario.

    Se muta en sitio para que los modulos que importaron ``C``, ``SERIES`` o
    ``METRICS`` vean los valores nuevos sin volver a importar.
    """
    global FONT_FAMILY, FONT_MONO, FONT_SIZE, FONT_SIZE_SMALL, FONT_SIZE_TITLE

    for key, slot in _COLOR_KEYS.items():
        C[slot] = str(store.get(key, C[slot]))

    # Tonos derivados, para que un acento nuevo arrastre sus variantes.
    C["accent_hover"] = _shift(C["accent"], 22)
    C["accent_press"] = _shift(C["accent"], -26)
    C["border_strong"] = _shift(C["border"], -22)
    C["divider"] = _shift(C["border"], 14)
    C["surface_alt"] = _mix(C["surface"], C["app"], 0.55)
    C["sunken"] = _mix(C["surface"], C["app"], 0.85)
    C["text_muted"] = _mix(C["text_soft"], C["surface"], 0.42)
    C["ok_soft"] = _mix(C["ok"], C["surface"], 0.88)
    C["warn_soft"] = _mix(C["warn"], C["surface"], 0.88)
    C["error_soft"] = _mix(C["error"], C["surface"], 0.88)
    C["info_soft"] = _mix(C["info"], C["surface"], 0.88)
    C["viewport"] = str(store.get("viewer.background_bottom", C["viewport"]))
    C["grid"] = str(store.get("viewer.grid_color", C["grid"]))

    SERIES[:] = [str(store.get(f"charts.series_{i}", SERIES[i])) for i in range(8)]

    FONT_FAMILY = str(store.get("appearance.font_family", FONT_FAMILY))
    FONT_MONO = str(store.get("appearance.font_mono", FONT_MONO))
    FONT_SIZE = int(store.get("appearance.font_size", FONT_SIZE))
    FONT_SIZE_SMALL = int(store.get("appearance.font_size_small", FONT_SIZE_SMALL))
    FONT_SIZE_TITLE = FONT_SIZE + 2

    pad_v, row_h, spacing = DENSITIES.get(
        str(store.get("appearance.density", "Normal")), DENSITIES["Normal"])
    METRICS.update({
        "radius": int(store.get("appearance.radius", 5)),
        "pad_v": pad_v,
        "pad_h": 8 if spacing < 11 else 11,
        "row_height": row_h,
        "spacing": spacing,
    })


def _clamp(v: float) -> int:
    return max(0, min(255, int(round(v))))


def _rgb(color: str) -> Tuple[int, int, int]:
    c = color.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    try:
        return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    except (ValueError, IndexError):
        return 0, 0, 0


def _shift(color: str, amount: int) -> str:
    """Aclara (amount > 0) u oscurece un color."""
    r, g, b = _rgb(color)
    return "#{:02x}{:02x}{:02x}".format(
        _clamp(r + amount), _clamp(g + amount), _clamp(b + amount))


def _mix(color: str, other: str, weight: float) -> str:
    """Mezcla dos colores; ``weight`` es el peso de ``other``."""
    r1, g1, b1 = _rgb(color)
    r2, g2, b2 = _rgb(other)
    w = max(0.0, min(1.0, weight))
    return "#{:02x}{:02x}{:02x}".format(
        _clamp(r1 * (1 - w) + r2 * w),
        _clamp(g1 * (1 - w) + g2 * w),
        _clamp(b1 * (1 - w) + b2 * w))


def level_colors(level: str) -> tuple[str, str]:
    """Par ``(color, fondo)`` para un nivel de hallazgo."""
    return {
        "ok": (C["ok"], C["ok_soft"]),
        "warn": (C["warn"], C["warn_soft"]),
        "error": (C["error"], C["error_soft"]),
    }.get(level, (C["info"], C["info_soft"]))


# ---------------------------------------------------------------------------
# Hoja de estilo
# ---------------------------------------------------------------------------


def stylesheet() -> str:
    """Hoja de estilo global, generada con la paleta y metricas vigentes."""
    radius = METRICS["radius"]
    radius_sm = max(radius - 1, 0)
    radius_lg = radius + 1
    pad_v = METRICS["pad_v"]
    pad_h = METRICS["pad_h"]
    row_height = METRICS["row_height"]
    return f"""
/* ---------- base ---------- */
QWidget {{
    background-color: {C['app']};
    color: {C['text']};
    font-family: '{FONT_FAMILY}', 'Inter', sans-serif;
    font-size: {FONT_SIZE}pt;
}}
QMainWindow, QDialog {{ background-color: {C['app']}; }}
QToolTip {{
    background-color: {C['text']};
    color: #ffffff;
    border: none;
    padding: 5px 8px;
    font-size: {FONT_SIZE_SMALL}pt;
}}

/* ---------- barra de menu ---------- */
QMenuBar {{
    background-color: {C['surface']};
    border-bottom: 1px solid {C['border']};
    padding: 2px 4px;
}}
QMenuBar::item {{ padding: 5px 10px; background: transparent; border-radius: {radius_sm}px; }}
QMenuBar::item:selected {{ background-color: {C['accent_soft']}; color: {C['accent']}; }}
QMenu {{
    background-color: {C['surface']};
    border: 1px solid {C['border']};
    padding: 5px;
}}
QMenu::item {{ padding: 6px 26px 6px 22px; border-radius: {radius_sm}px; }}
QMenu::item:selected {{ background-color: {C['accent_soft']}; color: {C['accent']}; }}
QMenu::separator {{ height: 1px; background: {C['divider']}; margin: 5px 8px; }}

/* ---------- barra de herramientas ---------- */
QToolBar {{
    background-color: {C['surface']};
    border: none;
    border-bottom: 1px solid {C['border']};
    padding: 4px 6px;
    spacing: 3px;
}}
QToolBar::separator {{ width: 1px; background: {C['divider']}; margin: 5px 6px; }}
QToolButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: {radius}px;
    padding: 5px 9px;
    color: {C['text_soft']};
}}
QToolButton:hover {{ background-color: {C['sunken']}; color: {C['text']}; }}
QToolButton:pressed, QToolButton:checked {{
    background-color: {C['accent_soft']};
    border-color: #c5ddf1;
    color: {C['accent']};
}}
QToolButton::menu-indicator {{ image: none; }}

/* ---------- paneles acoplables ---------- */
QDockWidget {{
    color: {C['text_soft']};
    titlebar-close-icon: none;
    titlebar-normal-icon: none;
}}
QDockWidget::title {{
    background-color: {C['surface_alt']};
    border: 1px solid {C['border']};
    border-bottom: none;
    padding: 6px 10px;
    font-size: {FONT_SIZE_SMALL}pt;
    font-weight: 600;
    letter-spacing: 0.6px;
    text-transform: uppercase;
    color: {C['text_soft']};
}}
QDockWidget > QWidget {{
    background-color: {C['surface']};
    border: 1px solid {C['border']};
}}

/* ---------- pestanas ---------- */
QTabWidget::pane {{
    background-color: {C['surface']};
    border: 1px solid {C['border']};
    border-radius: 0px;
    top: -1px;
}}
QTabBar {{ qproperty-drawBase: 0; background: transparent; }}
QTabBar::tab {{
    background: transparent;
    color: {C['text_muted']};
    padding: 7px 14px;
    margin-right: 2px;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: {FONT_SIZE_SMALL}pt;
    font-weight: 600;
}}
QTabBar::tab:hover {{ color: {C['text']}; }}
QTabBar::tab:selected {{ color: {C['accent']}; border-bottom-color: {C['accent']}; }}

/* ---------- grupos ---------- */
QGroupBox {{
    background-color: {C['surface']};
    border: 1px solid {C['border']};
    border-radius: {radius_lg}px;
    margin-top: 16px;
    padding: 10px 10px 8px 10px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 8px;
    padding: 0 4px;
    color: {C['text_soft']};
    font-size: {FONT_SIZE_SMALL}pt;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}}

/* ---------- botones ---------- */
QPushButton {{
    background-color: {C['surface']};
    color: {C['text']};
    border: 1px solid {C['border_strong']};
    border-radius: {radius}px;
    padding: {pad_v + 1}px {pad_h + 6}px;
    min-height: {row_height - 6}px;
}}
QPushButton:hover {{ background-color: {C['sunken']}; border-color: {C['text_muted']}; }}
QPushButton:pressed {{ background-color: {C['border']}; }}
QPushButton:disabled {{ color: {C['text_muted']}; background-color: {C['sunken']}; border-color: {C['border']}; }}
QPushButton[variant="primary"] {{
    background-color: {C['accent']};
    color: {C['text_on_accent']};
    border: 1px solid {C['accent']};
    font-weight: 600;
}}
QPushButton[variant="primary"]:hover {{ background-color: {C['accent_hover']}; border-color: {C['accent_hover']}; }}
QPushButton[variant="primary"]:pressed {{ background-color: {C['accent_press']}; }}
QPushButton[variant="primary"]:disabled {{
    background-color: #b9ccdd; border-color: #b9ccdd; color: #eef3f8;
}}
QPushButton[variant="ghost"] {{
    background: transparent; border: 1px solid transparent; color: {C['accent']}; padding: 4px 8px;
}}
QPushButton[variant="ghost"]:hover {{ background-color: {C['accent_soft']}; }}
QPushButton[variant="danger"] {{
    background-color: {C['surface']}; color: {C['error']}; border-color: #e6b4ae;
}}
QPushButton[variant="danger"]:hover {{ background-color: {C['error_soft']}; }}

/* ---------- campos ---------- */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit, QDateEdit {{
    background-color: {C['surface']};
    color: {C['text']};
    border: 1px solid {C['border_strong']};
    border-radius: {radius}px;
    padding: {pad_v}px {pad_h}px;
    selection-background-color: {C['accent']};
    selection-color: #ffffff;
}}
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover {{
    border-color: {C['text_muted']};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus,
QPlainTextEdit:focus, QTextEdit:focus {{
    border-color: {C['accent']};
}}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{
    background-color: {C['sunken']}; color: {C['text_muted']};
}}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    background-color: {C['surface_alt']};
    border-left: 1px solid {C['border']};
    width: 16px;
}}
QSpinBox::up-button, QDoubleSpinBox::up-button {{ border-top-right-radius: 4px; }}
QSpinBox::down-button, QDoubleSpinBox::down-button {{ border-bottom-right-radius: 4px; }}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{ background-color: {C['sunken']}; }}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: none; width: 0; height: 0;
    border-left: 3px solid transparent; border-right: 3px solid transparent;
    border-bottom: 4px solid {C['text_soft']};
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: none; width: 0; height: 0;
    border-left: 3px solid transparent; border-right: 3px solid transparent;
    border-top: 4px solid {C['text_soft']};
}}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox::down-arrow {{
    image: none; width: 0; height: 0;
    border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-top: 5px solid {C['text_soft']};
    margin-right: 6px;
}}
QComboBox QAbstractItemView {{
    background-color: {C['surface']};
    border: 1px solid {C['border']};
    selection-background-color: {C['accent_soft']};
    selection-color: {C['accent']};
    outline: none;
    padding: 3px;
}}

/* ---------- casillas ---------- */
QCheckBox, QRadioButton {{ spacing: 7px; background: transparent; }}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 15px; height: 15px;
    border: 1px solid {C['border_strong']};
    background-color: {C['surface']};
}}
QCheckBox::indicator {{ border-radius: 3px; }}
QRadioButton::indicator {{ border-radius: 8px; }}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{ border-color: {C['accent']}; }}
QCheckBox::indicator:checked {{
    background-color: {C['accent']}; border-color: {C['accent']};
    image: url(:/qt-project.org/styles/commonstyle/images/standardbutton-apply-16.png);
}}
QRadioButton::indicator:checked {{
    background-color: {C['surface']};
    border: 4px solid {C['accent']};
}}

/* ---------- tablas ---------- */
QTableWidget, QTableView, QTreeWidget, QTreeView, QListWidget, QListView {{
    background-color: {C['surface']};
    alternate-background-color: {C['surface_alt']};
    border: 1px solid {C['border']};
    border-radius: {radius}px;
    gridline-color: {C['divider']};
    selection-background-color: {C['accent_soft']};
    selection-color: {C['text']};
    outline: none;
}}
QTableWidget::item, QTableView::item {{ padding: 4px 6px; border: none; }}
QTreeWidget::item, QTreeView::item, QListWidget::item {{ padding: 4px 4px; border: none; }}
QTreeWidget::item:hover, QTableWidget::item:hover, QListWidget::item:hover {{
    background-color: {C['sunken']};
}}
QHeaderView {{ background-color: {C['surface_alt']}; }}
QHeaderView::section {{
    background-color: {C['surface_alt']};
    color: {C['text_soft']};
    border: none;
    border-right: 1px solid {C['divider']};
    border-bottom: 1px solid {C['border']};
    padding: 6px 7px;
    font-size: {FONT_SIZE_SMALL}pt;
    font-weight: 600;
}}
QHeaderView::section:hover {{ background-color: {C['sunken']}; }}
QTableCornerButton::section {{ background-color: {C['surface_alt']}; border: none; }}

/* ---------- barras de desplazamiento ---------- */
QScrollBar:vertical {{ background: transparent; width: 11px; margin: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 11px; margin: 0; }}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
    background: #c3ccd5; border-radius: {radius}px; min-height: 28px; min-width: 28px;
}}
QScrollBar::handle:hover {{ background: {C['text_muted']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ---------- progreso y separadores ---------- */
QProgressBar {{
    background-color: {C['sunken']};
    border: none;
    border-radius: {radius_sm}px;
    height: 6px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{ background-color: {C['accent']}; border-radius: {radius_sm}px; }}
QSplitter::handle {{ background-color: {C['border']}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}
QSplitter::handle:hover {{ background-color: {C['accent']}; }}

/* ---------- barra de estado ---------- */
QStatusBar {{
    background-color: {C['surface']};
    border-top: 1px solid {C['border']};
    color: {C['text_soft']};
    font-size: {FONT_SIZE_SMALL}pt;
}}
QStatusBar::item {{ border: none; }}
QStatusBar QLabel {{ padding: 0 8px; background: transparent; }}

/* ---------- desplazamiento de formularios ---------- */
QScrollArea {{ background-color: {C['surface']}; border: none; }}
QScrollArea > QWidget > QWidget {{ background-color: {C['surface']}; }}

/* ---------- clases utilitarias ---------- */
QLabel[role="h1"] {{ font-size: {FONT_SIZE_TITLE}pt; font-weight: 600; color: {C['text']}; }}
QLabel[role="h2"] {{ font-size: {FONT_SIZE}pt; font-weight: 600; color: {C['text']}; }}
QLabel[role="caption"] {{ color: {C['text_muted']}; font-size: {FONT_SIZE_SMALL}pt; }}
QLabel[role="mono"] {{ font-family: '{FONT_MONO}', monospace; color: {C['text']}; }}
QFrame[role="hline"] {{ background-color: {C['divider']}; max-height: 1px; border: none; }}
QFrame[role="card"] {{
    background-color: {C['surface']};
    border: 1px solid {C['border']};
    border-radius: {radius_lg}px;
}}
"""
