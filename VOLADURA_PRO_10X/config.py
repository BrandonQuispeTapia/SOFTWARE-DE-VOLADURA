"""
config.py — Configuración Global de VOLADURA_PRO_10X

Este archivo centraliza todas las constantes y configuraciones
de la aplicación, permitiendo personalización sin tocar el código.
"""

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN DE INTERFAZ
# ══════════════════════════════════════════════════════════════════════════════

# Tema Oscuro
THEME_COLORS = {
    "background": "#0b0f19",
    "text_primary": "#e2e8f0",
    "text_secondary": "#94a3b8",
    "accent_primary": "#3b82f6",
    "accent_secondary": "#06b6d4",
    "border": "#1e293b",
    "button": "#334155",
    "button_hover": "#475569",
    "success": "#22c55e",
    "warning": "#f59e0b",
    "error": "#ef4444",
    "info": "#06b6d4",
}

# Dimensiones
WINDOW_WIDTH = 1600
WINDOW_HEIGHT = 900
TAB_WIDGET_WIDTH_RATIO = 0.33  # 33% para tabs, 67% para 3D

# Fuentes
FONT_FAMILY = "Segoe UI"
FONT_SIZE_NORMAL = 10
FONT_SIZE_TITLE = 12
FONT_SIZE_HEADER = 14

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN DE SIMULACIÓN
# ══════════════════════════════════════════════════════════════════════════════

# Frame Rate de animación
ANIMATION_FPS = 30
ANIMATION_FRAME_MS = 1000 // ANIMATION_FPS  # ~33ms

# Duración de estados
STATE_FIRED_DURATION_MS = 100    # Cuánto tiempo brilla la detonación
STATE_EMPTY_DURATION_MS = 100    # Cuánto tarda en desvanecerse

# Colores de estados
STATE_COLORS = {
    "standby": (0.2, 0.8, 0.2),      # Verde
    "fired": (1.0, 0.9, 0.2),        # Amarillo brillante
    "empty": (0.0, 0.0, 0.0, 0.0),   # Transparente
}

# Opacidad de estados
STATE_OPACITY = {
    "standby": 0.7,
    "fired": 0.9,
    "empty": 0.0,
}

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN DE GEOMETRÍA
# ══════════════════════════════════════════════════════════════════════════════

# Parámetros por defecto
DEFAULT_GRID_PARAMS = {
    "burden_m": 4.5,
    "spacing_m": 5.0,
    "diameter_mm": 102.0,
    "bench_height_m": 12.0,
    "subdrilling_m": 1.0,
    "angle_deg": 0.0,
}

# Rangos de validación
GRID_RANGES = {
    "burden_m": (1.0, 20.0),
    "spacing_m": (1.0, 25.0),
    "diameter_mm": (50.0, 500.0),
    "bench_height_m": (2.0, 50.0),
    "subdrilling_m": (0.0, 10.0),
    "angle_deg": (0.0, 30.0),
}

# Número de taladros en malla
GRID_ROWS = 5
GRID_COLS = 8

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN DE CARGA/EXPLOSIVOS
# ══════════════════════════════════════════════════════════════════════════════

EXPLOSIVES_COLUMN = [
    "ANFO Pesado (HA 46)",
    "Emulsión Bombeable",
    "ANFO Estándar",
    "PowerGel",
]

EXPLOSIVES_BOOSTER = [
    "Dinamita (50 g)",
    "Dinamita (100 g)",
    "Pentolita (500 g)",
    "RDX/TNT (1000 g)",
]

BOOSTER_POSITIONS = [
    "Fondo del Taladro",
    "Medio de Taladro",
    "Superficie (Collar)",
]

STEMMING_MATERIALS = [
    "Arena Seca",
    "Grava",
    "Polvillo",
    "Material Triturado",
]

# Parámetros por defecto
DEFAULT_LOADING_CONFIG = {
    "column_explosive": "ANFO Pesado (HA 46)",
    "column_length_m": 8.0,
    "booster_type": "Dinamita (100 g)",
    "booster_position": "Fondo del Taladro",
    "num_boosters": 1,
    "stemming_material": "Arena Seca",
    "stemming_length_m": 3.0,
    "use_decking": False,
}

# Rangos de validación
LOADING_RANGES = {
    "column_length_m": (0.1, 50.0),
    "stemming_length_m": (0.5, 10.0),
    "num_boosters": (1, 5),
}

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN DE SECUENCIA
# ══════════════════════════════════════════════════════════════════════════════

SURFACE_DELAYS = [
    "Milisegundos (MS) - 25 ms",
    "Milisegundos (MS) - 42 ms",
    "Milisegundos (MS) - 67 ms",
    "Detonadores Electrónicos - 1 ms",
]

BOTTOM_DELAYS = [
    "Retardo Corto (NONEL) - 9 ms",
    "Retardo Largo (NONEL) - 17 ms",
    "Retardo Extendido (NONEL) - 25 ms",
    "Electrónico Sincronizado - 1 ms",
]

# Parámetros por defecto
DEFAULT_SEQUENCE_CONFIG = {
    "surface_delay": "Milisegundos (MS) - 42 ms",
    "bottom_delay": "Retardo Largo (NONEL) - 17 ms",
    "hole_interval_ms": 25.0,
}

# Rangos de validación
SEQUENCE_RANGES = {
    "hole_interval_ms": (5.0, 200.0),
}

# Parámetros de análisis de tiros cortados
MIN_DELAY_INTERVAL_MS = 8.0  # Intervalo mínimo entre tiros
TOLERANCE_OVERLAP_MS = 0.03  # Coeficiente de variación

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN DE VISOR 3D (PyVista)
# ══════════════════════════════════════════════════════════════════════════════

PYVISTA_BACKGROUND_COLOR = "#0f172a"
PYVISTA_AXES_COLOR = "white"
PYVISTA_AXES_X_COLOR = "#ef4444"
PYVISTA_AXES_Y_COLOR = "#22c55e"
PYVISTA_AXES_Z_COLOR = "#3b82f6"

# Tamaño de malla de taco
STEMMING_CYLINDER_RESOLUTION = 12
# Tamaño de malla de carga
CHARGE_CYLINDER_RESOLUTION = 12

# Transparencia
STEMMING_OPACITY = 0.8
CHARGE_OPACITY = 0.85
FREEFACE_OPACITY = 0.2

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN DE ESCOMBRERA (MUCKPILE)
# ══════════════════════════════════════════════════════════════════════════════

# Número de partículas por taladro
PARTICLES_PER_HOLE = 20

# Factor de gravedad (0-1)
GRAVITY_FACTOR = 0.4

# Desplazamiento máximo en metros
MAX_DISPLACEMENT_M = 5.0

# Color de escombrera
MUCKPILE_COLOR = (0.8, 0.6, 0.2)  # Amarillo ocre
MUCKPILE_OPACITY = 0.6
MUCKPILE_POINT_SIZE = 5.0

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN DE FÍSICA/CÁLCULOS
# ══════════════════════════════════════════════════════════════════════════════

# Constantes de Holmberg-Persson
HPM_K_FACTOR = 500.0
HPM_ALPHA = 0.7
HPM_BETA = 1.5

# Constante de Kuz-Ram
KUZ_RAM_ROCK_FACTOR = 8.0

# Factor de acoplamiento asumido
DECOUPLING_RATIO_DEFAULT = 0.5

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN DE ARCHIVOS
# ══════════════════════════════════════════════════════════════════════════════

# Nombre del archivo PDF de salida
PDF_OUTPUT_FILENAME = "Reporte_Voladura.pdf"

# Directorio de salida
PDF_OUTPUT_DIRECTORY = "./reports_output"

# Formato de fecha en reportes
DATE_FORMAT = "%d-%m-%Y %H:%M:%S"

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN DE MENSAJES
# ══════════════════════════════════════════════════════════════════════════════

MESSAGES = {
    "grid_success": "✓ Malla renderizada: {count} taladros\n  B={burden}m, S={spacing}m, D={diameter}mm",
    "loading_valid": "✓ Configuración Válida\n  Explosivo: {explosive}\n  Cebo: {booster}\n  Posición: {position}\n  Taco: {stemming}m",
    "cut_shot_low_risk": "🟢 BAJO",
    "cut_shot_medium_risk": "🟡 MEDIO",
    "cut_shot_high_risk": "🔴 ALTO",
    "animation_started": "▶ Animación de voladura iniciada",
    "animation_finished": "✓ Animación completada",
    "error_no_grid": "Configure primero los parámetros de malla.",
    "error_no_loading": "Configure primero los explosivos.",
}

# ══════════════════════════════════════════════════════════════════════════════
# DATOS DE EXPLOSIVOS (Banco de datos)
# ══════════════════════════════════════════════════════════════════════════════

EXPLOSIVES_DATABASE = {
    "ANFO Pesado (HA 46)": {
        "density_kg_m3": 1250.0,
        "vod_m_s": 5200.0,
        "rbs": 100.0,  # Relative Bulk Strength
    },
    "Emulsión Bombeable": {
        "density_kg_m3": 1150.0,
        "vod_m_s": 5500.0,
        "rbs": 105.0,
    },
    "ANFO Estándar": {
        "density_kg_m3": 850.0,
        "vod_m_s": 4500.0,
        "rbs": 85.0,
    },
    "PowerGel": {
        "density_kg_m3": 1050.0,
        "vod_m_s": 5000.0,
        "rbs": 90.0,
    },
    "Dinamita (50 g)": {
        "density_kg_m3": 1500.0,
        "vod_m_s": 6800.0,
        "rbs": 130.0,
    },
    "Dinamita (100 g)": {
        "density_kg_m3": 1550.0,
        "vod_m_s": 7000.0,
        "rbs": 135.0,
    },
}
