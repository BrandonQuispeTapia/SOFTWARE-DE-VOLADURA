"""Paneles de la interfaz, uno por area funcional del flujo de trabajo."""

from .charge import ChargePanel
from .console import ConsolePanel, HoleTablePanel
from .design import DesignPanel
from .explorer import ExplorerPanel
from .optimize import OptimizePanel
from .properties import PropertiesPanel
from .results import ResultsPanel
from .timing import TimingPanel

__all__ = [
    "ChargePanel", "ConsolePanel", "HoleTablePanel", "DesignPanel",
    "ExplorerPanel", "OptimizePanel", "PropertiesPanel", "ResultsPanel",
    "TimingPanel",
]
