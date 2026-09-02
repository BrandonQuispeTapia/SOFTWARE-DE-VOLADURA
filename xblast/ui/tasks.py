"""Ejecucion en segundo plano de los calculos pesados.

El analisis completo y el barrido de optimizacion se ejecutan fuera del hilo de
interfaz para que la ventana siga respondiendo. Cada trabajador emite su
resultado o el error ocurrido, nunca ambos.
"""

from __future__ import annotations

import traceback
from typing import Any, Callable, Dict, Optional

from PySide6.QtCore import QObject, QThread, Signal

from ..core.analysis import BlastAnalysis, analyze
from ..core.charging import ChargeRule
from ..core.models import BlastDesign
from ..core.optimizer import OptimizationResult, optimize


class _Worker(QObject):
    """Ejecuta una funcion y publica su resultado."""

    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, fn: Callable[[], Any]):
        super().__init__()
        self._fn = fn

    def run(self) -> None:
        try:
            self.finished.emit(self._fn())
        except Exception:
            self.failed.emit(traceback.format_exc(limit=6))


class BackgroundTask(QObject):
    """Envoltura de un trabajador con su hilo, con limpieza automatica."""

    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, fn: Callable[[], Any], parent: Optional[QObject] = None):
        super().__init__(parent)
        self._thread = QThread()
        self._worker = _Worker(fn)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)

    def start(self) -> None:
        self._thread.start()

    def _on_finished(self, result: Any) -> None:
        self._cleanup()
        self.finished.emit(result)

    def _on_failed(self, message: str) -> None:
        self._cleanup()
        self.failed.emit(message)

    def _cleanup(self) -> None:
        self._thread.quit()
        self._thread.wait(3000)
        self._worker.deleteLater()


def analysis_task(design: BlastDesign, target_p80_cm: float,
                  compute_energy: bool, parent: Optional[QObject] = None) -> BackgroundTask:
    """Tarea de analisis completo del diseno."""
    return BackgroundTask(
        lambda: analyze(design, compute_energy=compute_energy, target_p80_cm=target_p80_cm),
        parent)


def optimization_task(design: BlastDesign, rule: ChargeRule, settings: Dict,
                      progress: Optional[Callable[[int, int], None]] = None,
                      parent: Optional[QObject] = None) -> BackgroundTask:
    """Tarea de barrido de escenarios."""
    return BackgroundTask(
        lambda: optimize(
            design, rule,
            burden_range=settings["burden_range"],
            n_steps=settings["n_steps"],
            sb_ratios=settings["sb_ratios"],
            target_p80_cm=settings["target_p80_cm"],
            progress=progress),
        parent)
