"""X-BLAST — Plataforma de diseno, simulacion y optimizacion de voladura de rocas.

Paquete raiz. Expone la version y el punto de entrada de la aplicacion.

Estructura:
    xblast.core     Motor de ingenieria (geometria, fragmentacion, vibracion, costos).
    xblast.dataio   Importacion / exportacion de datos y proyectos.
    xblast.ui       Interfaz grafica (PySide6 + PyVista).
    xblast.reports  Generacion de reportes tecnicos.
"""

__version__ = "3.0.0"
__appname__ = "X-BLAST"
__tagline__ = "Blast Design & Optimization Suite"

__all__ = ["__version__", "__appname__", "__tagline__"]
