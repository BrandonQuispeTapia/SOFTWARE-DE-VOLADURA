"""Estilo comun de los graficos, independiente de la interfaz.

Se mantiene separado de :mod:`xblast.ui.charts` porque los reportes tambien lo
usan y deben poder generarse sin PySide6 instalado (por ejemplo en integracion
continua o desde un script de servidor).
"""

from __future__ import annotations

from .theme import C, SERIES

__all__ = ["style_axes", "SERIES", "C"]


def style_axes(ax, xlabel: str = "", ylabel: str = "", title: str = "") -> None:
    """Aplica el estilo claro de la aplicacion a un eje de matplotlib."""
    ax.set_facecolor(C["surface"])
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(C["border_strong"])
        ax.spines[side].set_linewidth(0.8)
    ax.tick_params(colors=C["text_soft"], labelsize=8, length=3, width=0.8)
    ax.grid(True, color=C["divider"], linewidth=0.7, alpha=0.9)
    ax.set_axisbelow(True)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=8.5, color=C["text_soft"])
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=8.5, color=C["text_soft"])
    if title:
        ax.set_title(title, fontsize=9.5, color=C["text"], fontweight="bold",
                     loc="left", pad=8)
