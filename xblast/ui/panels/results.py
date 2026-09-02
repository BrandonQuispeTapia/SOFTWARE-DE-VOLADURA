"""Panel de resultados del analisis.

Presenta el tablero de indicadores, la revision automatica del diseno y los
graficos de fragmentacion, vibracion, burden y costos.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QTabWidget, QVBoxLayout, QWidget,
)

from ...core.analysis import BlastAnalysis
from .. import widgets as W
from ..charts import BurdenChart, CostChart, FragmentationChart, VibrationChart
from ..theme import C


class ResultsPanel(QTabWidget):
    """Pestanas de resumen, revision, fragmentacion, vibracion y costos."""

    def __init__(self):
        super().__init__()
        self.summary = SummaryTab()
        self.review = ReviewTab()
        self.fragmentation = FragmentationTab()
        self.environment = EnvironmentTab()
        self.economics = EconomicsTab()

        self.addTab(self.summary, "Resumen")
        self.addTab(self.review, "Revision")
        self.addTab(self.fragmentation, "Fragmentacion")
        self.addTab(self.environment, "Ambiental")
        self.addTab(self.economics, "Costos")

    def update_results(self, analysis: Optional[BlastAnalysis],
                       target_p80_cm: float = 50.0) -> None:
        self.summary.update_results(analysis)
        self.review.update_results(analysis)
        self.fragmentation.update_results(analysis, target_p80_cm)
        self.environment.update_results(analysis)
        self.economics.update_results(analysis)


# ---------------------------------------------------------------------------
# Resumen
# ---------------------------------------------------------------------------


class SummaryTab(W.ScrollPanel):
    """Tablero de indicadores clave de la voladura."""

    def __init__(self):
        super().__init__(spacing=12)

        header = QHBoxLayout()
        header.setSpacing(8)
        self.score = W.StatusChip("Sin analisis", "info")
        header.addWidget(W.title("Calidad del diseno", 2))
        header.addWidget(self.score)
        header.addStretch(1)
        self.add_layout(header)

        self.production = _grid(self, "Produccion", [
            ("n_holes", "Taladros", ""),
            ("tonnes", "Tonelaje", "t"),
            ("volume_m3", "Volumen", "m3"),
            ("drilled_m", "Perforacion", "m"),
        ])
        self.charge = _grid(self, "Carga y energia", [
            ("charge_kg", "Explosivo", "kg"),
            ("powder_factor", "Factor de potencia", "kg/m3"),
            ("energy_factor_mj_t", "Factor de energia", "MJ/t"),
            ("drill_factor_m_m3", "Factor de perforacion", "m/m3"),
        ])
        self.frag = _grid(self, "Fragmentacion prevista", [
            ("x50_cm", "X50", "cm"),
            ("p80_cm", "P80", "cm"),
            ("oversize_pct", "Sobretamano", "%"),
            ("uniformity_n", "Uniformidad n", ""),
        ])
        self.env = _grid(self, "Control ambiental", [
            ("ppv_mm_s", "PPV en receptor", "mm/s"),
            ("airblast_db", "Onda aerea", "dBL"),
            ("flyrock_m", "Alcance de proyeccion", "m"),
            ("mic_kg", "Carga operante", "kg"),
        ])
        self.econ = _grid(self, "Economia", [
            ("cost_db_usd_t", "Perforacion y voladura", "USD/t"),
            ("cost_total_usd_t", "Costo total mina-planta", "USD/t"),
            ("cost_total_usd", "Costo de la voladura", "USD"),
            ("tonnes_per_hole", "Tonelaje por taladro", "t"),
        ])
        self.finish()

    def update_results(self, a: Optional[BlastAnalysis]) -> None:
        if a is None or not a.kpis:
            self.score.set_status("Sin analisis", "info")
            for g in (self.production, self.charge, self.frag, self.env, self.econ):
                for key in g.tiles():
                    g.set(key, "—")
            return

        k = a.kpis
        level = "ok" if a.score >= 85 else ("warn" if a.score >= 60 else "error")
        self.score.set_status(
            f"{a.score} / 100  ·  {len(a.errors)} criticos, {len(a.warnings)} avisos", level)

        for g, keys in ((self.production, ("n_holes", "tonnes", "volume_m3", "drilled_m")),
                        (self.charge, ("charge_kg", "powder_factor", "energy_factor_mj_t",
                                       "drill_factor_m_m3")),
                        (self.econ, ("cost_db_usd_t", "cost_total_usd_t", "cost_total_usd",
                                     "tonnes_per_hole"))):
            for key in keys:
                g.set(key, _fmt(k.get(key, 0)))

        self.frag.set("x50_cm", _fmt(k["x50_cm"]))
        self.frag.set("p80_cm", _fmt(k["p80_cm"]))
        self.frag.set("oversize_pct", _fmt(k["oversize_pct"]),
                      "error" if k["oversize_pct"] > 12 else ("warn" if k["oversize_pct"] > 8 else "ok"))
        self.frag.set("uniformity_n", _fmt(k["uniformity_n"]),
                      "warn" if k["uniformity_n"] < 1.0 else "ok")

        util = k["ppv_utilization_pct"]
        self.env.set("ppv_mm_s", _fmt(k["ppv_mm_s"]),
                     "error" if util > 100 else ("warn" if util > 80 else "ok"))
        limit_db = k.get("airblast_db", 0)
        self.env.set("airblast_db", _fmt(limit_db),
                     "error" if limit_db > 133 else ("warn" if limit_db > 128 else "ok"))
        exclusion = a.design.constraints.exclusion_radius_m
        self.env.set("flyrock_m", _fmt(k["flyrock_m"]),
                     "error" if k["safe_distance_m"] > exclusion else "ok")
        self.env.set("mic_kg", _fmt(k["mic_kg"]))


def _grid(panel: W.ScrollPanel, heading: str, tiles) -> W.MetricGrid:
    section = W.Section(heading)
    grid = W.MetricGrid(4)
    for key, label, unit in tiles:
        grid.add_tile(key, label, unit)
    section.add(grid)
    panel.add(section)
    return grid


def _fmt(v) -> str:
    if isinstance(v, int):
        return f"{v:,}"
    if isinstance(v, float):
        if abs(v) >= 10000:
            return f"{v:,.0f}"
        if abs(v) >= 100:
            return f"{v:,.1f}"
        if abs(v) >= 1:
            return f"{v:,.2f}"
        return f"{v:,.3f}"
    return str(v)


# ---------------------------------------------------------------------------
# Revision
# ---------------------------------------------------------------------------


class ReviewTab(QWidget):
    """Hallazgos de la revision automatica del diseno."""

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        head = QHBoxLayout()
        head.addWidget(W.title("Revision automatica del diseno", 2))
        head.addStretch(1)
        self.counter = W.caption("")
        head.addWidget(self.counter)
        lay.addLayout(head)
        lay.addWidget(W.caption(
            "Cada regla contrasta el diseno con criterios de buena practica de "
            "perforacion y voladura. Los criticos deben corregirse antes de disparar."))

        scroll = W.ScrollPanel(spacing=6, margins=(0, 4, 6, 4))
        self.findings = W.FindingsList()
        scroll.add(self.findings)
        lay.addWidget(scroll, 1)

    def update_results(self, a: Optional[BlastAnalysis]) -> None:
        if a is None:
            self.findings.set_findings([])
            self.counter.setText("")
            return
        self.findings.set_findings(a.findings)
        self.counter.setText(
            f"{len(a.errors)} criticos · {len(a.warnings)} avisos · "
            f"{len(a.findings) - len(a.errors) - len(a.warnings)} conformes")


# ---------------------------------------------------------------------------
# Fragmentacion
# ---------------------------------------------------------------------------


class FragmentationTab(W.ScrollPanel):
    """Curva granulometrica y percentiles caracteristicos."""

    def __init__(self):
        super().__init__()
        self.chart = FragmentationChart()
        self.chart.setMinimumHeight(320)
        self.add(self.chart)

        self.table = W.KeyValueTable()
        section = W.Section("Percentiles y parametros del modelo")
        section.add(self.table)
        self.add(section)

        self.burden_chart = BurdenChart()
        self.burden_chart.setMinimumHeight(230)
        self.add(self.burden_chart)
        self.finish()

    def update_results(self, a: Optional[BlastAnalysis], target_p80_cm: float) -> None:
        if a is None or a.fragmentation is None:
            self.chart.update_data(None)
            self.table.set_items([])
            self.burden_chart.update_data([], 0.0)
            return

        f = a.fragmentation
        oversize = a.design.costs.oversize_threshold_cm
        self.chart.update_data(f, target_p80_cm, oversize)
        self.table.set_items([
            ("Modelo", f.model),
            ("X50 (tamano medio)", f"{f.x50_cm:.1f} cm"),
            ("P20", f"{f.p20_cm:.1f} cm"),
            ("P80", f"{f.p80_cm:.1f} cm"),
            ("Tamano maximo (xmax)", f"{f.xmax_cm:.0f} cm"),
            ("Indice de uniformidad n", f"{f.n:.2f}"),
            ("Ondulacion b (Swebrec)", f"{f.b_swebrec:.2f}"),
            ("Finos < 2.5 cm", f"{f.fines_pct:.1f} %"),
            (f"Sobretamano > {oversize:.0f} cm", f"{f.oversize_pct:.1f} %"),
            ("Factor de roca A", f"{a.design.rock.rock_factor_a:.2f}"),
            ("Indice de volabilidad", f"{a.design.rock.blastability_index:.1f}"),
        ])
        self.burden_chart.update_data(
            [h.burden_real_m for h in a.design.holes], a.design.pattern.burden_m)


# ---------------------------------------------------------------------------
# Ambiental
# ---------------------------------------------------------------------------


class EnvironmentTab(W.ScrollPanel):
    """Vibracion, onda aerea, proyeccion y dano al talud remanente."""

    def __init__(self):
        super().__init__()
        self.chart = VibrationChart()
        self.chart.setMinimumHeight(260)
        self.add(self.chart)

        vib = W.Section("Vibracion", "Superposicion de onda semilla en el receptor.")
        self.vib_table = W.KeyValueTable()
        vib.add(self.vib_table)
        self.add(vib)

        near = W.Section("Dano al talud remanente",
                         "Campo cercano por Holmberg-Persson y umbrales derivados "
                         "de la resistencia a la traccion de la roca.")
        self.near_table = W.KeyValueTable()
        near.add(self.near_table)
        self.add(near)

        other = W.Section("Onda aerea y proyeccion")
        self.other_table = W.KeyValueTable()
        other.add(self.other_table)
        self.add(other)
        self.finish()

    def update_results(self, a: Optional[BlastAnalysis]) -> None:
        if a is None:
            self.chart.update_data(None, 0.0)
            for t in (self.vib_table, self.near_table, self.other_table):
                t.set_items([])
            return

        cons = a.design.constraints
        self.chart.update_data(a.vibration, cons.ppv_limit_mm_s)

        comp = a.vibration_compliance
        self.vib_table.set_items([
            ("PPV maximo predicho", f"{comp.get('ppv_mm_s', 0):.2f} mm/s"),
            ("Frecuencia dominante", f"{a.vibration.get('freq_hz', 0):.0f} Hz"),
            ("Limite del proyecto", f"{comp.get('limit_project_mm_s', 0):.2f} mm/s"),
            ("Uso del limite", f"{comp.get('utilization_pct', 0):.0f} %"),
            ("Limite USBM RI8507", f"{comp.get('limit_usbm_mm_s', 0):.2f} mm/s"),
            ("Limite DIN 4150-3", f"{comp.get('limit_din_mm_s', 0):.2f} mm/s"),
            ("Distancia al receptor", f"{a.kpis.get('receptor_distance_m', 0):,.0f} m"),
            ("Carga operante (MIC)", f"{a.kpis.get('mic_kg', 0):,.0f} kg"),
            ("Cumple", "Si" if comp.get("compliant") else "No"),
        ])

        nf = a.near_field
        self.near_table.set_items([
            ("Densidad lineal de carga", f"{nf.get('linear_charge_kg_m', 0):.1f} kg/m"),
            ("PPV a 1 m de la carga", f"{nf.get('ppv_1m_mm_s', 0):,.0f} mm/s"),
            ("PPV de fisuracion", f"{nf.get('ppv_fisuras_mm_s', 0):,.0f} mm/s"),
            ("PPV de fracturamiento", f"{nf.get('ppv_fracturamiento_mm_s', 0):,.0f} mm/s"),
            ("Radio de dano", f"{nf.get('damage_radius_m', 0):.1f} m"),
            ("Resistencia a traccion", f"{nf.get('tensile_strength_mpa', 0):.1f} MPa"),
        ])

        ab, fly = a.airblast, a.flyrock
        self.other_table.set_items([
            ("Onda aerea predicha", f"{ab.get('airblast_db', 0):.0f} dBL"),
            ("  Nivel base", f"{ab.get('base_db', 0):.0f} dBL"),
            ("  Correccion por confinamiento", f"{ab.get('confinement_db', 0):+.1f} dB"),
            ("Limite del proyecto", f"{cons.airblast_limit_db:.0f} dBL"),
            ("Mecanismo de proyeccion", str(fly.get("mechanism", "—"))),
            ("Alcance maximo", f"{fly.get('max_throw_m', 0):.0f} m"),
            ("Distancia segura recomendada", f"{fly.get('safe_distance_m', 0):.0f} m"),
            ("Radio de exclusion declarado", f"{cons.exclusion_radius_m:.0f} m"),
            ("Taladros criticos", f"{fly.get('n_critical', 0)}"),
        ])


# ---------------------------------------------------------------------------
# Costos
# ---------------------------------------------------------------------------


class EconomicsTab(W.ScrollPanel):
    """Desglose de costos y comparacion con el gasto aguas abajo."""

    def __init__(self):
        super().__init__()
        self.chart = CostChart()
        self.chart.setMinimumHeight(300)
        self.add(self.chart)

        section = W.Section(
            "Desglose",
            "El costo aguas abajo escala con el tamano medio de fragmento: una malla "
            "mas cerrada encarece la voladura pero abarata carguio, acarreo y chancado.")
        self.table = W.KeyValueTable()
        section.add(self.table)
        self.add(section)
        self.finish()

    def update_results(self, a: Optional[BlastAnalysis]) -> None:
        if a is None or a.cost is None:
            self.chart.update_data(None)
            self.table.set_items([])
            return

        c = a.cost
        t = max(c.tonnes, 1e-6)
        self.chart.update_data(c)
        items = [(k, f"{v:,.0f} USD   ({v / t:.3f} USD/t)") for k, v in c.as_dict().items()]
        items += [
            ("", ""),
            ("Perforacion y voladura", f"{c.db_usd:,.0f} USD   ({c.db_usd_t:.3f} USD/t)"),
            ("Aguas abajo", f"{c.downstream_usd:,.0f} USD   ({c.downstream_usd / t:.3f} USD/t)"),
            ("Costo total", f"{c.total_usd:,.0f} USD   ({c.total_usd_t:.3f} USD/t)"),
            ("Tonelaje volado", f"{c.tonnes:,.0f} t"),
        ]
        self.table.set_items(items)
