"""Graficos analiticos con estilo claro coherente con la interfaz.

Cada grafico es un ``QWidget`` autonomo que se refresca con ``update_data``.
El estilo comun (rejilla tenue, sin marcos superfluos, series de la paleta del
tema) vive en :mod:`xblast.ui.chartstyle`, que no depende de Qt.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import matplotlib
matplotlib.use("QtAgg")

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QVBoxLayout, QWidget

from .chartstyle import style_axes
from .theme import C, SERIES
from .widgets import button


class ChartCanvas(QWidget):
    """Lienzo base con barra de exportacion opcional."""

    def __init__(self, height: float = 2.6, export: bool = True):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        self.figure = Figure(figsize=(5.0, height), dpi=100, facecolor=C["surface"])
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setStyleSheet(f"background-color:{C['surface']};")
        lay.addWidget(self.canvas, 1)

        if export:
            bar = QHBoxLayout()
            bar.setContentsMargins(0, 0, 0, 0)
            bar.addStretch(1)
            btn = button("Exportar PNG", "ghost", "camera")
            btn.clicked.connect(self._export)
            bar.addWidget(btn)
            lay.addLayout(bar)

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Exportar grafico", "grafico.png",
                                              "Imagen PNG (*.png)")
        if path:
            self.figure.savefig(path, dpi=200, facecolor=C["surface"], bbox_inches="tight")

    def clear(self):
        self.figure.clear()
        return self.figure


# ---------------------------------------------------------------------------
# Graficos concretos
# ---------------------------------------------------------------------------


class FragmentationChart(ChartCanvas):
    """Curva granulometrica acumulada con los percentiles de interes."""

    def __init__(self):
        super().__init__(height=3.0)
        self.update_data(None)

    def update_data(self, result, target_p80_cm: Optional[float] = None,
                    oversize_cm: float = 80.0) -> None:
        fig = self.clear()
        ax = fig.add_subplot(111)
        style_axes(ax, "Tamano de fragmento (cm)", "Pasante acumulado (%)",
                   "Distribucion granulometrica prevista")

        if result is None or result.x50_cm <= 0:
            ax.text(0.5, 0.5, "Sin datos de analisis", transform=ax.transAxes,
                    ha="center", va="center", color=C["text_muted"], fontsize=9)
            ax.set_xscale("log")
            fig.tight_layout()
            self.canvas.draw_idle()
            return

        ax.set_xscale("log")
        ax.plot(result.sizes_cm, result.passing_pct, color=SERIES[0], linewidth=2.2,
                label=f"Swebrec (KCO) · n = {result.n:.2f}")

        for pct, size, color, label in (
            (50, result.x50_cm, SERIES[1], f"X50 = {result.x50_cm:.1f} cm"),
            (80, result.p80_cm, SERIES[2], f"P80 = {result.p80_cm:.1f} cm"),
        ):
            ax.plot([size], [pct], "o", color=color, markersize=6, zorder=5)
            ax.annotate(label, (size, pct), textcoords="offset points", xytext=(8, -12),
                        fontsize=8, color=color, fontweight="bold")

        if target_p80_cm:
            ax.axvline(target_p80_cm, color=SERIES[3], linestyle="--", linewidth=1.3,
                       label=f"Objetivo P80 = {target_p80_cm:.0f} cm")
        ax.axvline(oversize_cm, color=C["error"], linestyle=":", linewidth=1.2,
                   label=f"Sobretamano > {oversize_cm:.0f} cm")

        ax.set_ylim(0, 100)
        ax.set_xlim(max(result.sizes_cm[0], 0.1), result.sizes_cm[-1])
        ax.legend(fontsize=7.5, frameon=False, loc="upper left", labelcolor=C["text_soft"])
        fig.tight_layout()
        self.canvas.draw_idle()


class VibrationChart(ChartCanvas):
    """Historia temporal de vibracion por superposicion de ondas."""

    def __init__(self):
        super().__init__(height=2.6)
        self.update_data(None, 0.0)

    def update_data(self, trace: Optional[Dict], limit_mm_s: float) -> None:
        fig = self.clear()
        ax = fig.add_subplot(111)
        style_axes(ax, "Tiempo (ms)", "PPV (mm/s)",
                   "Sismograma previsto en el receptor")

        if not trace or len(trace.get("t_ms", [])) < 2:
            ax.text(0.5, 0.5, "Sin datos de analisis", transform=ax.transAxes,
                    ha="center", va="center", color=C["text_muted"], fontsize=9)
            fig.tight_layout()
            self.canvas.draw_idle()
            return

        t = trace["t_ms"]
        v = trace["ppv_mm_s"]
        ax.plot(t, v, color=SERIES[0], linewidth=0.9)
        ax.fill_between(t, v, color=SERIES[0], alpha=0.14)

        peak = trace["ppv_max_mm_s"]
        ax.plot([trace["t_peak_ms"]], [peak if v[int(np.argmax(np.abs(v)))] > 0 else -peak],
                "o", color=C["error"], markersize=5, zorder=5)
        ax.annotate(f"Maximo {peak:.1f} mm/s", (trace["t_peak_ms"], peak),
                    textcoords="offset points", xytext=(6, 6), fontsize=8,
                    color=C["error"], fontweight="bold")

        if limit_mm_s > 0:
            for sign in (1, -1):
                ax.axhline(sign * limit_mm_s, color=C["warn"], linestyle="--", linewidth=1.2)
            ax.annotate(f"Limite {limit_mm_s:.1f} mm/s", (t[-1], limit_mm_s),
                        textcoords="offset points", xytext=(-8, 4), fontsize=7.5,
                        color=C["warn"], ha="right")
        fig.tight_layout()
        self.canvas.draw_idle()


class TimingChart(ChartCanvas):
    """Carga detonada por ventana temporal frente a la carga operante limite."""

    def __init__(self):
        super().__init__(height=2.4)
        self.update_data(np.array([]), np.array([]), 0.0)

    def update_data(self, edges: np.ndarray, weights: np.ndarray,
                    max_allowed_kg: float = 0.0, window_ms: float = 8.0) -> None:
        fig = self.clear()
        ax = fig.add_subplot(111)
        style_axes(ax, "Tiempo (ms)", "Carga detonada (kg)",
                   f"Carga por ventana de {window_ms:.0f} ms")

        if edges.size == 0:
            ax.text(0.5, 0.5, "Sin datos de secuencia", transform=ax.transAxes,
                    ha="center", va="center", color=C["text_muted"], fontsize=9)
            fig.tight_layout()
            self.canvas.draw_idle()
            return

        width = (edges[1] - edges[0]) * 0.85 if edges.size > 1 else window_ms
        colors = [C["error"] if (max_allowed_kg and w > max_allowed_kg) else SERIES[0]
                  for w in weights]
        ax.bar(edges, weights, width=width, color=colors, align="edge")

        if max_allowed_kg > 0:
            ax.axhline(max_allowed_kg, color=C["warn"], linestyle="--", linewidth=1.3)
            ax.annotate(f"Maxima admisible {max_allowed_kg:.0f} kg",
                        (edges[-1], max_allowed_kg), textcoords="offset points",
                        xytext=(-6, 5), fontsize=7.5, color=C["warn"], ha="right")
        fig.tight_layout()
        self.canvas.draw_idle()


class CostChart(ChartCanvas):
    """Desglose de costos y comparacion perforacion-voladura contra aguas abajo."""

    def __init__(self):
        super().__init__(height=2.8)
        self.update_data(None)

    def update_data(self, breakdown) -> None:
        fig = self.clear()
        if breakdown is None:
            ax = fig.add_subplot(111)
            style_axes(ax, title="Estructura de costos")
            ax.text(0.5, 0.5, "Sin datos de analisis", transform=ax.transAxes,
                    ha="center", va="center", color=C["text_muted"], fontsize=9)
            fig.tight_layout()
            self.canvas.draw_idle()
            return

        gs = fig.add_gridspec(1, 2, width_ratios=[1.5, 1], wspace=0.35)
        ax = fig.add_subplot(gs[0])
        style_axes(ax, "USD por tonelada", title="Estructura de costos")

        items = breakdown.as_dict()
        t = max(breakdown.tonnes, 1e-6)
        labels = list(items.keys())[::-1]
        values = [items[k] / t for k in labels]
        colors = [SERIES[i % len(SERIES)] for i in range(len(labels))][::-1]
        ax.barh(labels, values, color=colors, height=0.62)
        for i, v in enumerate(values):
            ax.text(v, i, f" {v:.3f}", va="center", fontsize=7.5, color=C["text_soft"])
        ax.tick_params(axis="y", labelsize=8)
        ax.grid(axis="y", visible=False)

        ax2 = fig.add_subplot(gs[1])
        ax2.set_facecolor(C["surface"])
        parts = [breakdown.db_usd, breakdown.downstream_usd]
        ax2.pie(parts, labels=["P&V", "Aguas\nabajo"], colors=[SERIES[0], SERIES[3]],
                autopct="%1.0f%%", startangle=90, textprops={"fontsize": 8, "color": C["text_soft"]},
                wedgeprops={"width": 0.42, "edgecolor": C["surface"], "linewidth": 2})
        ax2.set_title(f"{breakdown.total_usd_t:.2f} USD/t", fontsize=9.5,
                      color=C["text"], fontweight="bold")
        fig.tight_layout()
        self.canvas.draw_idle()


class ChargeProfileChart(ChartCanvas):
    """Perfil de carga y energia a lo largo de un taladro."""

    def __init__(self):
        super().__init__(height=3.2)
        self.update_data(None)

    def update_data(self, hole, profile: Optional[Tuple[np.ndarray, np.ndarray]] = None) -> None:
        fig = self.clear()
        ax = fig.add_subplot(111)
        style_axes(ax, "Densidad lineal (kg/m)", "Profundidad desde el collar (m)",
                   "Columna de carga")

        if hole is None or profile is None:
            ax.text(0.5, 0.5, "Seleccione un taladro", transform=ax.transAxes,
                    ha="center", va="center", color=C["text_muted"], fontsize=9)
            fig.tight_layout()
            self.canvas.draw_idle()
            return

        depth, q = profile
        ax.fill_betweenx(depth, 0, q, color=SERIES[0], alpha=0.75, step="mid")
        ax.plot(q, depth, color=SERIES[0], linewidth=1.2, drawstyle="steps-mid")
        ax.invert_yaxis()
        ax.set_xlim(0, max(float(np.max(q)) * 1.35, 1.0))

        # anotacion de plataformas
        for d in hole.decks:
            top = hole.length_m - (d.from_toe_m + d.length_m)
            mid = top + d.length_m / 2.0
            kind = d.kind.value if hasattr(d.kind, "value") else str(d.kind)
            label = d.explosive if d.is_charge else kind
            color = {"Taco": C["text_muted"], "Aire": C["info"]}.get(kind, C["text"])
            ax.axhline(top, color=C["divider"], linewidth=0.8)
            ax.text(ax.get_xlim()[1] * 0.97, mid, f"{label}  {d.length_m:.2f} m",
                    fontsize=7.5, color=color, ha="right", va="center")
        fig.tight_layout()
        self.canvas.draw_idle()


class OptimizationChart(ChartCanvas):
    """Costo por tonelada frente al factor de potencia, con el optimo marcado."""

    def __init__(self):
        super().__init__(height=2.9)
        self.update_data(None)

    def update_data(self, series: Optional[Dict[str, np.ndarray]],
                    best_pf: Optional[float] = None) -> None:
        fig = self.clear()
        ax = fig.add_subplot(111)
        style_axes(ax, "Factor de potencia (kg/m3)", "Costo (USD/t)",
                   "Optimo economico mina-planta")

        if not series or series.get("powder_factor") is None or len(series["powder_factor"]) < 2:
            ax.text(0.5, 0.5, "Ejecute la optimizacion", transform=ax.transAxes,
                    ha="center", va="center", color=C["text_muted"], fontsize=9)
            fig.tight_layout()
            self.canvas.draw_idle()
            return

        pf = series["powder_factor"]
        order = np.argsort(pf)
        pf = pf[order]
        db = series["cost_db_usd_t"][order]
        total = series["cost_total_usd_t"][order]

        ax.plot(pf, db, color=SERIES[0], linewidth=1.8, marker="o", markersize=3.5,
                label="Perforacion y voladura")
        ax.plot(pf, total - db, color=SERIES[3], linewidth=1.8, marker="o", markersize=3.5,
                label="Aguas abajo")
        ax.plot(pf, total, color=SERIES[1], linewidth=2.4, marker="o", markersize=4,
                label="Costo total")

        if best_pf:
            ax.axvline(best_pf, color=SERIES[2], linestyle="--", linewidth=1.4)
            ax.annotate(f"Optimo {best_pf:.3f}", (best_pf, float(np.min(total))),
                        textcoords="offset points", xytext=(6, 10), fontsize=8,
                        color=SERIES[2], fontweight="bold")

        ax.legend(fontsize=7.5, frameon=False, labelcolor=C["text_soft"])
        fig.tight_layout()
        self.canvas.draw_idle()


class BurdenChart(ChartCanvas):
    """Distribucion del burden real frente al nominal."""

    def __init__(self):
        super().__init__(height=2.4)
        self.update_data([], 0.0)

    def update_data(self, burdens: Sequence[float], nominal: float) -> None:
        fig = self.clear()
        ax = fig.add_subplot(111)
        style_axes(ax, "Burden real (m)", "Taladros",
                   "Dispersion del burden en la malla")

        b = np.asarray(list(burdens), float)
        if b.size == 0:
            ax.text(0.5, 0.5, "Sin datos de analisis", transform=ax.transAxes,
                    ha="center", va="center", color=C["text_muted"], fontsize=9)
            fig.tight_layout()
            self.canvas.draw_idle()
            return

        ax.hist(b, bins=min(18, max(5, b.size // 3)), color=SERIES[0], alpha=0.85,
                edgecolor=C["surface"], linewidth=0.8)
        if nominal > 0:
            ax.axvline(nominal, color=SERIES[1], linestyle="--", linewidth=1.5)
            ax.annotate(f"Nominal {nominal:.2f} m", (nominal, ax.get_ylim()[1] * 0.92),
                        textcoords="offset points", xytext=(6, 0), fontsize=8,
                        color=SERIES[1], fontweight="bold")
        fig.tight_layout()
        self.canvas.draw_idle()
