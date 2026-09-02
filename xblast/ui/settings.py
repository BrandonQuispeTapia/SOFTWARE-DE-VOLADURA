"""Preferencias de la aplicación: esquema, almacén y persistencia.

Todo lo configurable de X-BLAST está declarado aquí en un único esquema. El
diálogo de preferencias se construye a partir de él, de modo que agregar una
opción nueva es agregar una línea: no hay que tocar la interfaz.

Cada opción se identifica por una clave con espacio de nombres
(``viewer.background_top``) y se guarda en ``~/.xblast/settings.json``. El
almacén emite :attr:`Settings.changed` con la clave y el valor nuevo, y los
consumidores deciden si se aplican en caliente o en el próximo arranque.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

from PySide6.QtCore import QObject, Signal

from ..core import explosives as exdb
from ..core.models import HoleType, InitiationSystem, PatternType
from ..core.timing import TIE_PATTERNS

CONFIG_DIR = Path.home() / ".xblast"
CONFIG_FILE = CONFIG_DIR / "settings.json"


# ---------------------------------------------------------------------------
# Esquema
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Setting:
    """Una opción configurable."""

    key: str
    label: str
    kind: str                       # bool | int | float | choice | color | text | font
    default: Any
    minimum: float = 0.0
    maximum: float = 100.0
    step: float = 1.0
    decimals: int = 2
    options: Tuple[str, ...] = ()
    suffix: str = ""
    help: str = ""
    restart: bool = False           # necesita reiniciar para verse


@dataclass(frozen=True)
class Group:
    """Bloque de opciones afines dentro de una página."""

    title: str
    settings: Tuple[Setting, ...]
    help: str = ""


@dataclass(frozen=True)
class Page:
    """Una página del diálogo de preferencias."""

    key: str
    title: str
    icon: str
    groups: Tuple[Group, ...]
    help: str = ""


def _s(*args, **kwargs) -> Setting:
    return Setting(*args, **kwargs)


_EXPLOSIVES = tuple(exdb.names())
_PRIMERS = tuple(exdb.primer_names())
_STEMMING = tuple(exdb.STEMMING_MATERIALS)
_HOLE_TYPES = tuple(t.value for t in HoleType)

#: Modos de navegación; se declara aquí para no importar el visor.
NAV_MODES = ("Tornamesa (sin volteo)", "Orbita libre", "Terreno (Z arriba)",
             "Joystick", "Planta 2D")

COLORMAPS = ("viridis", "plasma", "inferno", "magma", "cividis", "turbo",
             "coolwarm", "RdYlGn_r", "jet")


SCHEMA: Tuple[Page, ...] = (

    # ------------------------------------------------------------------
    Page("appearance", "Apariencia", "settings", help=(
        "Color, tipografía y densidad de la interfaz. Los cambios se aplican "
        "al instante sobre toda la aplicación."), groups=(
        Group("Tema", (
            _s("appearance.theme", "Tema", "choice", "Claro",
               options=("Claro", "Claro cálido", "Gris técnico", "Alto contraste")),
            _s("appearance.accent", "Color de acento", "color", "#1668b3",
               help="Se usa en la acción primaria, pestañas activas y resaltados."),
            _s("appearance.accent_soft", "Fondo del acento", "color", "#e8f1fa"),
            _s("appearance.surface", "Color de panel", "color", "#ffffff"),
            _s("appearance.app_background", "Fondo de la ventana", "color", "#f4f6f8"),
            _s("appearance.border", "Color de borde", "color", "#d8dee4"),
            _s("appearance.text", "Color de texto", "color", "#1f2733"),
            _s("appearance.text_soft", "Texto secundario", "color", "#5a6673"),
        )),
        Group("Colores de estado", (
            _s("appearance.ok", "Conforme", "color", "#1a7f4b"),
            _s("appearance.warn", "Aviso", "color", "#b26a00"),
            _s("appearance.error", "Crítico", "color", "#c0392b"),
            _s("appearance.info", "Informativo", "color", "#0e7490"),
        )),
        Group("Tipografía", (
            _s("appearance.font_family", "Fuente de la interfaz", "font", "Segoe UI"),
            _s("appearance.font_size", "Tamaño base", "int", 9, 7, 16, 1, suffix="pt"),
            _s("appearance.font_size_small", "Tamaño de etiquetas", "int", 8, 6, 14, 1, suffix="pt"),
            _s("appearance.font_mono", "Fuente monoespaciada", "font", "Consolas"),
        )),
        Group("Densidad y forma", (
            _s("appearance.density", "Densidad", "choice", "Normal",
               options=("Compacta", "Normal", "Amplia"),
               help="Controla el alto de filas, el relleno de los campos y el espaciado."),
            _s("appearance.radius", "Radio de esquinas", "int", 5, 0, 12, 1, suffix="px"),
            _s("appearance.tile_min_width", "Ancho mínimo de tarjeta KPI", "int", 148, 110, 260, 2, suffix="px"),
            _s("appearance.label_width", "Ancho de etiquetas de formulario", "int", 138, 90, 240, 2, suffix="px"),
        )),
        Group("Barras e iconos", (
            _s("appearance.toolbar_style", "Barra de herramientas", "choice", "Icono y texto",
               options=("Solo icono", "Icono y texto", "Solo texto")),
            _s("appearance.icon_size", "Tamaño de icono", "int", 18, 12, 32, 1, suffix="px"),
            _s("appearance.icon_stroke", "Grosor del trazo", "float", 1.7, 1.0, 3.0, 0.1, 1, suffix="px"),
        )),
    )),

    # ------------------------------------------------------------------
    Page("viewer", "Visor 3D", "cube", help=(
        "Aspecto de la escena tridimensional."), groups=(
        Group("Fondo y rejilla", (
            _s("viewer.background_top", "Fondo superior", "color", "#ffffff"),
            _s("viewer.background_bottom", "Fondo inferior", "color", "#eceff2"),
            _s("viewer.gradient", "Fondo degradado", "bool", True),
            _s("viewer.show_grid", "Mostrar rejilla y ejes acotados", "bool", True),
            _s("viewer.grid_color", "Color de rejilla", "color", "#c8d0d8"),
            _s("viewer.grid_font_size", "Tamaño de rótulos", "int", 9, 6, 18, 1, suffix="pt"),
            _s("viewer.show_axes", "Mostrar tríada de orientación", "bool", True),
            _s("viewer.show_orientation_cube", "Mostrar cubo de orientación", "bool", False,
               help="Cubo interactivo de VTK para saltar a las vistas ortogonales."),
        )),
        Group("Calidad de imagen", (
            _s("viewer.antialiasing", "Suavizado", "choice", "FXAA",
               options=("Ninguno", "FXAA", "SSAA")),
            _s("viewer.smooth_shading", "Sombreado suave", "bool", True),
            _s("viewer.depth_peeling", "Transparencia por capas", "bool", False,
               help="Mejora el orden de las superficies transparentes; cuesta rendimiento."),
            _s("viewer.parallel_projection", "Proyección ortográfica por defecto", "bool", False),
            _s("viewer.z_exaggeration", "Exageración vertical inicial", "float", 1.0, 0.2, 5.0, 0.1, 1, suffix="x"),
        )),
        Group("Iluminación", (
            _s("viewer.ambient", "Luz ambiental", "float", 0.30, 0.0, 1.0, 0.05, 2),
            _s("viewer.diffuse", "Luz difusa", "float", 0.75, 0.0, 1.0, 0.05, 2),
            _s("viewer.specular", "Brillo especular", "float", 0.12, 0.0, 1.0, 0.05, 2),
        )),
    )),

    # ------------------------------------------------------------------
    Page("holes", "Taladros", "hole", help=(
        "Cómo se dibujan los taladros y sus columnas de carga."), groups=(
        Group("Geometría del dibujo", (
            _s("holes.radius_factor", "Factor de radio visual", "float", 3.0, 1.0, 10.0, 0.5, 1,
               help="Multiplica el radio real para que el taladro se vea a escala de banco."),
            _s("holes.radius_min", "Radio mínimo", "float", 0.16, 0.02, 1.0, 0.02, 2, suffix="m"),
            _s("holes.resolution", "Lados del cilindro", "int", 16, 6, 48, 2),
            _s("holes.charge_opacity", "Opacidad de la carga", "float", 1.0, 0.1, 1.0, 0.05, 2),
        )),
        Group("Taco, aire y collares", (
            _s("holes.stem_color", "Color del taco", "color", "#9aa5b1"),
            _s("holes.stem_opacity", "Opacidad del taco", "float", 0.90, 0.1, 1.0, 0.05, 2),
            _s("holes.air_color", "Color de la cámara de aire", "color", "#e8edf2"),
            _s("holes.air_opacity", "Opacidad de la cámara de aire", "float", 0.45, 0.05, 1.0, 0.05, 2),
            _s("holes.show_collars", "Mostrar collares", "bool", True),
            _s("holes.collar_color", "Color del collar", "color", "#1f2733"),
            _s("holes.collar_size", "Tamaño del collar", "int", 7, 2, 24, 1, suffix="px"),
        )),
        Group("Etiquetas", (
            _s("holes.labels_on_start", "Mostrar etiquetas al abrir", "bool", False),
            _s("holes.label_font_size", "Tamaño de etiqueta", "int", 11, 6, 24, 1, suffix="pt"),
            _s("holes.label_color", "Color de etiqueta", "color", "#1f2733"),
            _s("holes.label_offset", "Altura sobre el collar", "float", 1.2, 0.0, 8.0, 0.1, 1, suffix="m"),
            _s("holes.label_content", "Contenido", "choice", "Identificador",
               options=("Identificador", "Retardo", "Carga", "Identificador y retardo")),
        )),
        Group("Selección", (
            _s("holes.selection_color", "Color de selección", "color", "#f0a202"),
            _s("holes.selection_opacity", "Opacidad del resaltado", "float", 0.45, 0.05, 1.0, 0.05, 2),
            _s("holes.selection_scale", "Grosor del resaltado", "float", 1.55, 1.05, 4.0, 0.05, 2,
               help="Múltiplo del radio del taladro."),
        )),
    )),

    # ------------------------------------------------------------------
    Page("hole_colors", "Colores por tipo", "pattern", help=(
        "Color de cada clase de taladro en el visor, la tabla y los reportes."),
        groups=(
        Group("Tipos de taladro", tuple(
            _s(f"hole_colors.{t.value}", t.value, "color", t.color) for t in HoleType
        )),
    )),

    # ------------------------------------------------------------------
    Page("interaction", "Interacción", "measure", help=(
        "Cómo responde el visor al ratón y al teclado."), groups=(
        Group("Navegación", (
            _s("interaction.nav_mode", "Modo por defecto", "choice", NAV_MODES[0],
               options=NAV_MODES,
               help="Tornamesa mantiene el eje Z vertical y nunca deja el modelo de cabeza."),
            _s("interaction.max_elevation", "Elevación máxima", "float", 89.0, 30.0, 89.9, 1.0, 1,
               suffix="°", help="Límite del giro vertical en modo tornamesa."),
            _s("interaction.orbit_speed", "Velocidad de giro", "float", 1.0, 0.2, 4.0, 0.1, 1, suffix="x"),
            _s("interaction.invert_y", "Invertir el eje vertical", "bool", False),
            _s("interaction.zoom_speed", "Velocidad de zoom", "float", 1.0, 0.2, 4.0, 0.1, 1, suffix="x"),
            _s("interaction.orbit_step", "Paso de los botones de giro", "float", 12.0, 1.0, 45.0, 1.0, 0, suffix="°"),
            _s("interaction.spin_speed", "Velocidad de rotación automática", "float", 0.6, 0.1, 5.0, 0.1, 1,
               suffix="°/cuadro"),
        )),
        Group("Selección", (
            _s("interaction.select_mode", "Seleccionar con", "choice", "Doble clic",
               options=("Un clic", "Doble clic"),
               help="Con doble clic el botón izquierdo queda libre para girar sin seleccionar por error."),
            _s("interaction.pick_radius_px", "Radio de captura", "int", 16, 4, 60, 1, suffix="px",
               help="Distancia máxima en pantalla entre el cursor y el taladro."),
            _s("interaction.drag_tolerance_px", "Tolerancia de arrastre", "int", 6, 2, 30, 1, suffix="px",
               help="Movimiento por debajo del cual se considera un clic y no un giro."),
            _s("interaction.double_click_ms", "Intervalo de doble clic", "int", 450, 150, 1200, 25, suffix="ms"),
            _s("interaction.clear_on_empty", "Vaciar la selección al pulsar el fondo", "bool", True),
            _s("interaction.focus_on_select", "Centrar el giro al seleccionar", "bool", False,
               help="La cámara pasa a orbitar alrededor del taladro elegido."),
        )),
        Group("Comodidades", (
            _s("interaction.hover_highlight", "Resaltar bajo el cursor", "bool", True),
            _s("interaction.show_hint_bar", "Mostrar la ayuda de ratón en la barra de estado", "bool", True),
        )),
    )),

    # ------------------------------------------------------------------
    Page("layers", "Capas y terreno", "layers", help=(
        "Aspecto de la topografía, la cara libre y el piso de banco."), groups=(
        Group("Topografía", (
            _s("layers.topo_color", "Color de superficie", "color", "#c9d3c2"),
            _s("layers.topo_opacity", "Opacidad", "float", 0.55, 0.05, 1.0, 0.05, 2),
            _s("layers.topo_wireframe", "Mostrar malla de alambre", "bool", True),
            _s("layers.topo_wire_color", "Color de la malla", "color", "#9fae97"),
            _s("layers.topo_wire_opacity", "Opacidad de la malla", "float", 0.28, 0.0, 1.0, 0.02, 2),
        )),
        Group("Cara libre", (
            _s("layers.face_color", "Color", "color", "#1668b3"),
            _s("layers.face_opacity", "Opacidad", "float", 0.14, 0.0, 1.0, 0.02, 2),
            _s("layers.face_line_width", "Grosor del borde", "int", 3, 1, 10, 1, suffix="px"),
        )),
        Group("Piso de banco", (
            _s("layers.bench_color", "Color", "color", "#dfe4e8"),
            _s("layers.bench_opacity", "Opacidad", "float", 0.35, 0.0, 1.0, 0.05, 2),
            _s("layers.bench_margin", "Margen alrededor de la malla", "float", 8.0, 0.0, 60.0, 1.0, 1, suffix="m"),
        )),
    )),

    # ------------------------------------------------------------------
    Page("animation", "Animación", "run", help=(
        "Reproducción de la secuencia de salida."), groups=(
        Group("Reproducción", (
            _s("animation.fps", "Cuadros por segundo", "int", 30, 5, 60, 1),
            _s("animation.speed", "Velocidad", "float", 1.0, 0.05, 10.0, 0.05, 2, suffix="x",
               help="1.0 reproduce en tiempo real; por debajo, en cámara lenta."),
            _s("animation.flash_ms", "Duración del destello", "float", 120.0, 10.0, 600.0, 10.0, 0, suffix="ms"),
            _s("animation.tail_ms", "Margen tras el último taladro", "float", 220.0, 0.0, 2000.0, 20.0, 0, suffix="ms"),
        )),
        Group("Colores de estado", (
            _s("animation.color_pending", "Pendiente", "color", "#b4bdc6"),
            _s("animation.color_firing", "Detonando", "color", "#f0a202"),
            _s("animation.color_fired", "Ya disparado", "color", "#c0392b"),
        )),
    )),

    # ------------------------------------------------------------------
    Page("energy", "Campo de energía", "energy", help=(
        "Malla tridimensional de energía explosiva."), groups=(
        Group("Cálculo", (
            _s("energy.cell_size", "Tamaño de celda", "float", 1.2, 0.3, 6.0, 0.1, 2, suffix="m",
               help="Celdas más finas dan más detalle y tardan más."),
            _s("energy.influence_factor", "Radio de influencia", "float", 2.2, 0.5, 6.0, 0.1, 1,
               suffix="x burden"),
            _s("energy.max_cells", "Máximo de celdas", "int", 900000, 50000, 5000000, 50000),
            _s("energy.compute_on_analysis", "Calcular en cada análisis", "bool", True),
        )),
        Group("Representación", (
            _s("energy.contours", "Isosuperficies", "int", 6, 2, 20, 1),
            _s("energy.opacity", "Opacidad", "float", 0.35, 0.05, 1.0, 0.05, 2),
            _s("energy.colormap", "Mapa de color", "choice", "inferno", options=COLORMAPS),
            _s("energy.tolerance", "Tolerancia del rango objetivo", "float", 0.5, 0.1, 1.5, 0.05, 2,
               help="Fracción por encima y por debajo de la energía de diseño que se considera en rango."),
        )),
    )),

    # ------------------------------------------------------------------
    Page("charts", "Gráficos", "analysis", help=(
        "Estilo de las curvas y tableros analíticos."), groups=(
        Group("Trazado", (
            _s("charts.line_width", "Grosor de línea", "float", 2.2, 0.5, 6.0, 0.1, 1, suffix="px"),
            _s("charts.show_grid", "Mostrar rejilla", "bool", True),
            _s("charts.grid_alpha", "Opacidad de la rejilla", "float", 0.9, 0.0, 1.0, 0.05, 2),
            _s("charts.font_size", "Tamaño de fuente", "float", 8.0, 5.0, 16.0, 0.5, 1, suffix="pt"),
            _s("charts.export_dpi", "Resolución de exportación", "int", 200, 72, 600, 10, suffix="ppp"),
        )),
        Group("Paleta de series", tuple(
            _s(f"charts.series_{i}", f"Serie {i + 1}", "color", color)
            for i, color in enumerate(
                ("#1668b3", "#c0392b", "#1a7f4b", "#b26a00",
                 "#6b4fa8", "#0e7490", "#a0522d", "#4a5568"))
        )),
        Group("Fragmentación", (
            _s("charts.frag_log_scale", "Escala logarítmica de tamaños", "bool", True),
            _s("charts.frag_show_target", "Marcar el P80 objetivo", "bool", True),
            _s("charts.frag_show_oversize", "Marcar el umbral de sobretamaño", "bool", True),
        )),
    )),

    # ------------------------------------------------------------------
    Page("units", "Unidades y formato", "table", help=(
        "Cómo se presentan las magnitudes en toda la aplicación."), groups=(
        Group("Sistema", (
            _s("units.system", "Sistema de unidades", "choice", "Métrico",
               options=("Métrico", "Imperial"), restart=True,
               help="El imperial convierte la presentación; el cálculo interno sigue en SI."),
            _s("units.decimal_separator", "Separador decimal", "choice", "Punto",
               options=("Punto", "Coma")),
            _s("units.thousands_separator", "Separador de miles", "choice", "Coma",
               options=("Coma", "Punto", "Espacio", "Ninguno")),
        )),
        Group("Decimales", (
            _s("units.decimals_length", "Longitudes", "int", 2, 0, 4, 1),
            _s("units.decimals_mass", "Masas", "int", 1, 0, 4, 1),
            _s("units.decimals_factor", "Factores", "int", 3, 0, 5, 1),
            _s("units.decimals_cost", "Costos", "int", 3, 0, 5, 1),
            _s("units.decimals_time", "Tiempos", "int", 1, 0, 3, 1),
        )),
    )),

    # ------------------------------------------------------------------
    Page("design", "Diseño por defecto", "grid", help=(
        "Valores con los que arranca cada proyecto nuevo."), groups=(
        Group("Perforación", (
            _s("design.diameter_mm", "Diámetro", "float", 152.0, 50.0, 450.0, 1.0, 0, suffix="mm"),
            _s("design.bench_height_m", "Altura de banco", "float", 10.0, 2.0, 60.0, 0.5, 2, suffix="m"),
            _s("design.subdrill_m", "Subperforación", "float", 1.2, 0.0, 8.0, 0.1, 2, suffix="m"),
            _s("design.inclination_deg", "Inclinación", "float", 15.0, 0.0, 45.0, 1.0, 0, suffix="°"),
        )),
        Group("Malla", (
            _s("design.pattern", "Disposición", "choice", PatternType.TRESBOLILLO.value,
               options=tuple(t.value for t in PatternType)),
            _s("design.burden_m", "Burden", "float", 4.5, 0.5, 20.0, 0.1, 2, suffix="m"),
            _s("design.spacing_m", "Espaciamiento", "float", 5.2, 0.5, 25.0, 0.1, 2, suffix="m"),
            _s("design.rows", "Filas", "int", 6, 1, 60, 1),
            _s("design.cols", "Columnas", "int", 10, 1, 100, 1),
            _s("design.face_azimuth_deg", "Azimut de salida", "float", 180.0, 0.0, 360.0, 5.0, 0, suffix="°"),
            _s("design.hole_type", "Tipo de taladro", "choice", HoleType.PRODUCCION.value,
               options=_HOLE_TYPES),
        )),
        Group("Carguío", (
            _s("design.column_explosive", "Explosivo de columna", "choice", "ANFO", options=_EXPLOSIVES),
            _s("design.use_bottom_charge", "Usar carga de fondo", "bool", True),
            _s("design.bottom_explosive", "Explosivo de fondo", "choice",
               "Emulsion Gasificada 1.15", options=_EXPLOSIVES),
            _s("design.bottom_charge_m", "Longitud de la carga de fondo", "float", 2.5, 0.0, 15.0, 0.1, 2, suffix="m"),
            _s("design.stemming_m", "Taco de collar", "float", 3.5, 0.3, 12.0, 0.1, 2, suffix="m"),
            _s("design.stemming_material", "Material de taco", "choice",
               'Grava chancada 3/8"', options=_STEMMING),
            _s("design.coupling", "Acoplamiento", "float", 1.0, 0.2, 1.0, 0.05, 2),
            _s("design.n_decks", "Plataformas de carga", "int", 1, 1, 5, 1),
            _s("design.inter_deck_stem_m", "Taco intermedio", "float", 1.5, 0.0, 8.0, 0.1, 2, suffix="m"),
            _s("design.air_deck_m", "Cámara de aire", "float", 0.0, 0.0, 8.0, 0.1, 2, suffix="m"),
            _s("design.primer_type", "Cebo", "choice", "Booster Pentolita 450 g", options=_PRIMERS),
            _s("design.primer_per_deck", "Cebos por plataforma", "int", 1, 0, 4, 1),
        )),
        Group("Macizo rocoso", (
            _s("design.rock_name", "Litología", "text", "Andesita competente"),
            _s("design.rock_density", "Densidad", "float", 2.70, 1.2, 5.0, 0.05, 2, suffix="t/m3"),
            _s("design.rock_ucs", "Resistencia a compresión", "float", 150.0, 5.0, 400.0, 5.0, 0, suffix="MPa"),
            _s("design.rock_young", "Módulo de Young", "float", 60.0, 1.0, 150.0, 1.0, 0, suffix="GPa"),
            _s("design.rock_poisson", "Coeficiente de Poisson", "float", 0.25, 0.05, 0.45, 0.01, 2),
            _s("design.rock_vp", "Velocidad de onda P", "float", 4500.0, 500.0, 8000.0, 100.0, 0, suffix="m/s"),
            _s("design.rock_gsi", "GSI", "int", 60, 5, 100, 1),
            _s("design.rock_rmd", "Descripción del macizo (RMD)", "float", 25.0, 10.0, 50.0, 5.0, 0),
            _s("design.rock_jps", "Espaciamiento de juntas (JPS)", "float", 25.0, 10.0, 50.0, 5.0, 0),
            _s("design.rock_jpa", "Orientación de juntas (JPA)", "float", 30.0, 20.0, 40.0, 10.0, 0),
        )),
        Group("Secuencia", (
            _s("design.initiation", "Sistema de iniciación", "choice",
               InitiationSystem.ELECTRONICO.value,
               options=tuple(s.value for s in InitiationSystem)),
            _s("design.tie_pattern", "Patrón de amarre", "choice", TIE_PATTERNS[0],
               options=tuple(TIE_PATTERNS)),
            _s("design.hole_delay_ms", "Retardo entre taladros", "float", 17.0, 0.0, 200.0, 1.0, 0, suffix="ms"),
            _s("design.row_delay_ms", "Retardo entre filas", "float", 65.0, 0.0, 500.0, 5.0, 0, suffix="ms"),
            _s("design.in_hole_delay_ms", "Retardo de fondo", "float", 0.0, 0.0, 1000.0, 25.0, 0, suffix="ms"),
            _s("design.echelon_deg", "Ángulo de echelon", "float", 45.0, 15.0, 75.0, 5.0, 0, suffix="°"),
        )),
    )),

    # ------------------------------------------------------------------
    Page("analysis", "Análisis", "analysis", help=(
        "Parámetros del motor de cálculo."), groups=(
        Group("Objetivos", (
            _s("analysis.target_p80_cm", "P80 objetivo de planta", "float", 50.0, 5.0, 200.0, 1.0, 0, suffix="cm"),
            _s("analysis.oversize_cm", "Umbral de sobretamaño", "float", 80.0, 10.0, 300.0, 5.0, 0, suffix="cm"),
            _s("analysis.drilling_accuracy_m", "Desviación de perforación", "float", 0.25, 0.0, 2.0, 0.05, 2,
               suffix="m", help="Entra directamente en el índice de uniformidad de Cunningham."),
        )),
        Group("Secuencia y vibración", (
            _s("analysis.cooperation_window_ms", "Ventana de cooperación", "float", 8.0, 1.0, 50.0, 1.0, 0,
               suffix="ms", help="Regla de 8 ms de la USBM para la carga operante."),
            _s("analysis.monte_carlo_runs", "Simulaciones de dispersión", "int", 400, 50, 5000, 50),
            _s("analysis.seed_frequency_hz", "Frecuencia de la onda semilla", "float", 30.0, 2.0, 200.0, 1.0, 0,
               suffix="Hz"),
            _s("analysis.seed_damping", "Amortiguamiento de la onda semilla", "float", 22.0, 1.0, 100.0, 1.0, 0),
            _s("analysis.cube_root_scaling", "Distancia escalada por raíz cúbica", "bool", False,
               help="Por defecto se usa la raíz cuadrada, habitual en voladura de banco."),
        )),
        Group("Proyección de rocas", (
            _s("analysis.flyrock_k", "Constante k de Richards & Moore", "float", 13.5, 5.0, 30.0, 0.5, 1,
               help="13.5 en condiciones normales; hasta 27 en el peor caso."),
            _s("analysis.flyrock_safety", "Factor de seguridad", "float", 1.5, 1.0, 4.0, 0.1, 1, suffix="x"),
        )),
        Group("Onda aérea", (
            _s("analysis.airblast_k", "Constante de confinamiento", "float", 3.3, 0.05, 200.0, 0.05, 2,
               help="0.1 carga bien confinada, 3.3 producción normal, 185 carga al aire."),
            _s("analysis.temp_inversion", "Suponer inversión térmica", "bool", False),
            _s("analysis.wind_toward", "Viento hacia el receptor", "bool", False),
            _s("analysis.wind_speed", "Velocidad del viento", "float", 0.0, 0.0, 25.0, 0.5, 1, suffix="m/s"),
        )),
    )),

    # ------------------------------------------------------------------
    Page("limits", "Límites y normativa", "warning", help=(
        "Restricciones ambientales y de seguridad por defecto."), groups=(
        Group("Receptor", (
            _s("limits.receptor_easting", "Este", "float", 0.0, -1e7, 1e7, 10.0, 1, suffix="m"),
            _s("limits.receptor_northing", "Norte", "float", 500.0, -1e7, 1e7, 10.0, 1, suffix="m"),
            _s("limits.receptor_elev", "Cota", "float", 0.0, -5000.0, 9000.0, 1.0, 1, suffix="m"),
        )),
        Group("Umbrales", (
            _s("limits.ppv_limit", "PPV admisible", "float", 12.7, 0.5, 200.0, 0.1, 2, suffix="mm/s"),
            _s("limits.airblast_limit", "Onda aérea admisible", "float", 133.0, 90.0, 150.0, 1.0, 0, suffix="dBL"),
            _s("limits.exclusion_radius", "Radio de exclusión", "float", 300.0, 10.0, 2000.0, 10.0, 0, suffix="m"),
            _s("limits.structure", "Tipo de estructura (USBM)", "choice", "Vivienda drywall",
               options=("Vivienda drywall", "Vivienda yeso")),
            _s("limits.din_building", "Edificación (DIN 4150-3)", "choice", "Residencial",
               options=("Industrial", "Residencial", "Sensible / patrimonio")),
        )),
        Group("Constantes de sitio", (
            _s("limits.k_site", "K", "float", 1140.0, 50.0, 5000.0, 10.0, 0),
            _s("limits.beta_site", "beta", "float", 1.6, 0.8, 3.0, 0.05, 2),
            _s("limits.alpha_site", "alpha (campo cercano)", "float", 0.7, 0.3, 1.2, 0.05, 2),
        )),
    )),

    # ------------------------------------------------------------------
    Page("costs", "Costos", "cost", help=(
        "Costos unitarios del modelo mina-planta."), groups=(
        Group("Perforación y voladura", (
            _s("costs.drilling_usd_m", "Perforación", "float", 9.5, 0.0, 200.0, 0.5, 2, suffix="USD/m"),
            _s("costs.detonator_usd_unit", "Detonador", "float", 18.0, 0.0, 200.0, 0.5, 2, suffix="USD"),
            _s("costs.connector_usd_unit", "Conector de superficie", "float", 6.5, 0.0, 100.0, 0.5, 2, suffix="USD"),
            _s("costs.labor_usd_hole", "Mano de obra", "float", 4.0, 0.0, 100.0, 0.5, 2, suffix="USD/taladro"),
        )),
        Group("Aguas abajo", (
            _s("costs.loading_usd_t", "Carguío", "float", 0.42, 0.0, 20.0, 0.01, 3, suffix="USD/t"),
            _s("costs.hauling_usd_t", "Acarreo", "float", 0.85, 0.0, 20.0, 0.01, 3, suffix="USD/t"),
            _s("costs.crushing_usd_t", "Chancado", "float", 0.95, 0.0, 20.0, 0.01, 3, suffix="USD/t"),
            _s("costs.secondary_usd_t", "Voladura secundaria", "float", 3.20, 0.0, 50.0, 0.1, 2, suffix="USD/t"),
            _s("costs.reference_x50_cm", "X50 de referencia", "float", 25.0, 1.0, 200.0, 1.0, 1, suffix="cm",
               help="Tamaño para el que valen los costos declarados arriba."),
        )),
        Group("Sensibilidad al tamaño", (
            _s("costs.exp_loading", "Exponente de carguío", "float", 0.55, 0.0, 2.0, 0.05, 2),
            _s("costs.exp_hauling", "Exponente de acarreo", "float", 0.30, 0.0, 2.0, 0.05, 2),
            _s("costs.exp_crushing", "Exponente de chancado", "float", 0.75, 0.0, 2.0, 0.05, 2),
        )),
    )),

    # ------------------------------------------------------------------
    Page("optimizer", "Optimización", "optimize", help=(
        "Espacio de búsqueda del barrido de escenarios."), groups=(
        Group("Barrido", (
            _s("optimizer.burden_min", "Burden mínimo", "float", 0.80, 0.4, 1.0, 0.05, 2, suffix="x nominal"),
            _s("optimizer.burden_max", "Burden máximo", "float", 1.20, 1.0, 2.0, 0.05, 2, suffix="x nominal"),
            _s("optimizer.steps", "Pasos de burden", "int", 5, 2, 15, 1),
            _s("optimizer.sb_ratios", "Relaciones S/B", "choice", "1.00 / 1.15 / 1.30",
               options=("1.00 / 1.15 / 1.30", "1.00 / 1.25",
                        "0.90 / 1.00 / 1.15 / 1.30", "1.15")),
            _s("optimizer.keep_area", "Mantener el área volada", "bool", True,
               help="Ajusta filas y columnas para que los escenarios sean comparables."),
        )),
    )),

    # ------------------------------------------------------------------
    Page("reports", "Reportes", "report", help=(
        "Encabezado y contenido del reporte técnico."), groups=(
        Group("Identificación", (
            _s("reports.company", "Empresa u operación", "text", ""),
            _s("reports.author", "Responsable", "text", ""),
            _s("reports.position", "Cargo", "text", ""),
            _s("reports.footer_note", "Nota al pie", "text", ""),
        )),
        Group("Contenido", (
            _s("reports.include_findings", "Incluir la revisión del diseño", "bool", True),
            _s("reports.include_charts", "Incluir gráficos", "bool", True),
            _s("reports.include_hole_table", "Incluir el detalle de taladros", "bool", True),
            _s("reports.chart_dpi", "Resolución de los gráficos", "int", 140, 72, 400, 10, suffix="ppp"),
        )),
    )),

    # ------------------------------------------------------------------
    Page("behavior", "Comportamiento", "console", help=(
        "Cómo se comporta la aplicación en el día a día."), groups=(
        Group("Arranque", (
            _s("behavior.show_start_page", "Mostrar la página de inicio al abrir", "bool", True),
            _s("behavior.demo_on_start", "Generar una malla de ejemplo", "bool", True),
            _s("behavior.restore_layout", "Recordar la disposición de paneles", "bool", True),
            _s("behavior.max_recents", "Proyectos recientes", "int", 10, 0, 40, 1),
        )),
        Group("Cálculo", (
            _s("behavior.auto_analyze", "Analizar al cambiar el diseño", "bool", True,
               help="Al desactivarlo el análisis solo corre al pulsar Analizar (F6)."),
            _s("behavior.confirm_exit", "Confirmar al salir con cambios sin guardar", "bool", True),
            _s("behavior.autosave_minutes", "Guardado automático", "int", 0, 0, 60, 1, suffix="min",
               help="0 desactiva el guardado automático."),
        )),
        Group("Bitácora", (
            _s("behavior.log_level", "Detalle del registro", "choice", "Normal",
               options=("Mínimo", "Normal", "Detallado")),
            _s("behavior.log_max_lines", "Líneas conservadas", "int", 3000, 200, 50000, 100),
            _s("behavior.raise_log_on_error", "Traer la bitácora al frente ante un error", "bool", True),
        )),
    )),
)


# ---------------------------------------------------------------------------
# Almacén
# ---------------------------------------------------------------------------


def iter_settings() -> Iterator[Setting]:
    """Recorre todas las opciones declaradas en el esquema."""
    for page in SCHEMA:
        for group in page.groups:
            yield from group.settings


DEFAULTS: Dict[str, Any] = {s.key: s.default for s in iter_settings()}
BY_KEY: Dict[str, Setting] = {s.key: s for s in iter_settings()}


class Settings(QObject):
    """Almacén de preferencias con persistencia en disco."""

    changed = Signal(str, object)     # clave, valor
    bulk_changed = Signal(list)       # claves tocadas de una vez
    reloaded = Signal()

    def __init__(self, path: Optional[Path] = None):
        super().__init__()
        self._path = Path(path) if path else CONFIG_FILE
        self._values: Dict[str, Any] = dict(DEFAULTS)
        self.load()

    # -- acceso ------------------------------------------------------------
    def get(self, key: str, fallback: Any = None) -> Any:
        if key in self._values:
            return self._values[key]
        return DEFAULTS.get(key, fallback)

    def set(self, key: str, value: Any, notify: bool = True,
            force: bool = False) -> bool:
        """Guarda un valor; devuelve True si hubo cambio.

        Con ``force`` se avisa aunque el valor sea el mismo, que es lo que
        necesita una paleta base: volver a elegirla debe reaplicar sus colores
        aunque el nombre no haya cambiado.
        """
        if key not in DEFAULTS:
            return False
        if self._values.get(key) == value and not force:
            return False
        self._values[key] = value
        if notify:
            self.changed.emit(key, value)
        return True

    def update(self, values: Dict[str, Any], notify: bool = True) -> List[str]:
        """Aplica varios valores de una vez.

        Emite :attr:`bulk_changed` con las claves tocadas en lugar de una
        avalancha de :attr:`changed`, para que quien escuche pueda reaccionar
        una sola vez.

        Returns:
            Claves cuyo valor cambio.
        """
        touched = [k for k, v in values.items() if self.set(k, v, notify=False)]
        if touched and notify:
            self.bulk_changed.emit(touched)
        return touched

    def as_dict(self) -> Dict[str, Any]:
        return dict(self._values)

    def is_default(self, key: str) -> bool:
        return self._values.get(key) == DEFAULTS.get(key)

    # -- restablecer -------------------------------------------------------
    def reset(self, key: str) -> None:
        self.set(key, DEFAULTS[key])

    def reset_page(self, page_key: str) -> List[str]:
        page = next((p for p in SCHEMA if p.key == page_key), None)
        if page is None:
            return []
        keys = [s.key for g in page.groups for s in g.settings]
        return self.update({k: DEFAULTS[k] for k in keys})

    def reset_all(self) -> List[str]:
        return self.update(dict(DEFAULTS))

    # -- persistencia ------------------------------------------------------
    def load(self) -> bool:
        """Lee el archivo de preferencias; ignora claves desconocidas."""
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        if not isinstance(raw, dict):
            return False
        self._values = dict(DEFAULTS)
        self._values.update({k: v for k, v in raw.get("settings", raw).items()
                             if k in DEFAULTS})
        self.reloaded.emit()
        return True

    def save(self) -> Optional[Path]:
        """Escribe solo lo que difiere del valor por defecto."""
        diff = {k: v for k, v in self._values.items() if v != DEFAULTS.get(k)}
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps({"format": "xblast-settings", "settings": diff},
                           indent=1, ensure_ascii=False),
                encoding="utf-8")
        except OSError:
            return None
        return self._path

    def export_to(self, path: Path | str) -> Path:
        p = Path(path).with_suffix(".json")
        p.write_text(json.dumps({"format": "xblast-settings",
                                 "settings": self.as_dict()},
                                indent=1, ensure_ascii=False), encoding="utf-8")
        return p

    def import_from(self, path: Path | str) -> List[str]:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        data = raw.get("settings", raw)
        return self.update({k: v for k, v in data.items() if k in DEFAULTS})

    # -- utilidades --------------------------------------------------------
    def hole_colors(self) -> Dict[str, str]:
        """Color vigente de cada tipo de taladro."""
        return {t.value: self.get(f"hole_colors.{t.value}", t.color) for t in HoleType}

    def series_colors(self) -> List[str]:
        return [self.get(f"charts.series_{i}") for i in range(8)]

    def sb_ratios(self) -> Tuple[float, ...]:
        return tuple(float(x) for x in str(self.get("optimizer.sb_ratios")).split("/"))


#: Instancia compartida por toda la aplicación.
_INSTANCE: Optional[Settings] = None


def settings() -> Settings:
    """Almacén global de preferencias."""
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = Settings()
    return _INSTANCE


def search(query: str) -> List[Tuple[Page, Group, Setting]]:
    """Busca opciones por etiqueta, clave o texto de ayuda."""
    q = query.strip().lower()
    if not q:
        return []
    hits: List[Tuple[Page, Group, Setting]] = []
    for page in SCHEMA:
        for group in page.groups:
            for s in group.settings:
                haystack = f"{s.label} {s.key} {s.help} {group.title} {page.title}".lower()
                if q in haystack:
                    hits.append((page, group, s))
    return hits
