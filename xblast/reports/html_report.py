"""Reporte tecnico en HTML.

Genera un documento autocontenido — sin recursos externos — con la memoria de
calculo de la voladura: geometria, carga, secuencia, fragmentacion, control
ambiental, costos y la revision automatica del diseno. Los graficos se
incrustan como PNG en base64 para que el archivo pueda enviarse tal cual.
"""

from __future__ import annotations

import base64
import io
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from .. import __appname__, __version__
from ..core.analysis import BlastAnalysis
from ..core.timing import timing_histogram

_ACCENT = "#1668b3"
_TEXT = "#1f2733"
_SOFT = "#5a6673"
_BORDER = "#d8dee4"
_LEVEL = {"error": ("#c0392b", "#fdecea", "Critico"),
          "warn": ("#b26a00", "#fdf3e2", "Aviso"),
          "ok": ("#1a7f4b", "#e6f4ec", "Conforme")}


# ---------------------------------------------------------------------------
# Graficos incrustados
# ---------------------------------------------------------------------------


def _figure_to_data_uri(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=140, bbox_inches="tight", facecolor="#ffffff")
    buf.seek(0)
    return "data:image/png;base64," + base64.b64encode(buf.read()).decode("ascii")


def _charts(a: BlastAnalysis) -> Dict[str, str]:
    """Renderiza los graficos del reporte y los devuelve como data URI."""
    from matplotlib.figure import Figure

    from ..ui.chartstyle import SERIES, style_axes

    out: Dict[str, str] = {}

    # Granulometria
    f = a.fragmentation
    if f is not None and f.x50_cm > 0:
        fig = Figure(figsize=(7.2, 3.4), facecolor="#ffffff")
        ax = fig.add_subplot(111)
        style_axes(ax, "Tamano de fragmento (cm)", "Pasante acumulado (%)",
                   "Distribucion granulometrica prevista")
        ax.set_xscale("log")
        ax.plot(f.sizes_cm, f.passing_pct, color=SERIES[0], linewidth=2.2)
        for pct, size, color in ((50, f.x50_cm, SERIES[1]), (80, f.p80_cm, SERIES[2])):
            ax.plot([size], [pct], "o", color=color, markersize=6)
            ax.annotate(f"{'X50' if pct == 50 else 'P80'} = {size:.1f} cm", (size, pct),
                        textcoords="offset points", xytext=(8, -12), fontsize=8, color=color)
        ax.set_ylim(0, 100)
        fig.tight_layout()
        out["fragmentacion"] = _figure_to_data_uri(fig)

    # Sismograma
    if a.vibration.get("t_ms") is not None and len(a.vibration["t_ms"]) > 2:
        fig = Figure(figsize=(7.2, 2.8), facecolor="#ffffff")
        ax = fig.add_subplot(111)
        style_axes(ax, "Tiempo (ms)", "PPV (mm/s)", "Sismograma previsto en el receptor")
        ax.plot(a.vibration["t_ms"], a.vibration["ppv_mm_s"], color=SERIES[0], linewidth=0.9)
        limit = a.design.constraints.ppv_limit_mm_s
        for sign in (1, -1):
            ax.axhline(sign * limit, color="#b26a00", linestyle="--", linewidth=1.1)
        fig.tight_layout()
        out["vibracion"] = _figure_to_data_uri(fig)

    # Carga por ventana
    edges, weights = timing_histogram(a.design.holes,
                                      a.design.timing.cooperation_window_ms)
    if edges.size:
        fig = Figure(figsize=(7.2, 2.6), facecolor="#ffffff")
        ax = fig.add_subplot(111)
        style_axes(ax, "Tiempo (ms)", "Carga detonada (kg)",
                   f"Carga por ventana de {a.design.timing.cooperation_window_ms:.0f} ms")
        width = (edges[1] - edges[0]) * 0.85 if edges.size > 1 else 8.0
        ax.bar(edges, weights, width=width, color=SERIES[0], align="edge")
        fig.tight_layout()
        out["secuencia"] = _figure_to_data_uri(fig)

    # Costos
    if a.cost is not None:
        fig = Figure(figsize=(7.2, 3.0), facecolor="#ffffff")
        ax = fig.add_subplot(111)
        style_axes(ax, "USD por tonelada", title="Estructura de costos")
        items = a.cost.as_dict()
        t = max(a.cost.tonnes, 1e-6)
        labels = list(items)[::-1]
        values = [items[k] / t for k in labels]
        ax.barh(labels, values, color=[SERIES[i % len(SERIES)] for i in range(len(labels))][::-1],
                height=0.6)
        for i, v in enumerate(values):
            ax.text(v, i, f" {v:.3f}", va="center", fontsize=8, color=_SOFT)
        ax.grid(axis="y", visible=False)
        fig.tight_layout()
        out["costos"] = _figure_to_data_uri(fig)

    return out


# ---------------------------------------------------------------------------
# Composicion del documento
# ---------------------------------------------------------------------------


def _table(rows: Sequence[Tuple[str, str]], head: Tuple[str, str] = ("Parametro", "Valor")) -> str:
    body = "".join(
        f"<tr><td>{k}</td><td class='num'>{v}</td></tr>" for k, v in rows if k)
    return (f"<table><thead><tr><th>{head[0]}</th><th>{head[1]}</th></tr></thead>"
            f"<tbody>{body}</tbody></table>")


def _findings_html(findings: Sequence[Dict[str, str]]) -> str:
    order = {"error": 0, "warn": 1, "ok": 2}
    items = sorted(findings, key=lambda f: order.get(f.get("level", "ok"), 3))
    blocks = []
    for f in items:
        color, bg, label = _LEVEL.get(f.get("level", "ok"), _LEVEL["ok"])
        blocks.append(
            f"<div class='finding' style='border-left-color:{color};background:{bg}'>"
            f"<div class='finding-head' style='color:{color}'>{label} · {f.get('item','')}</div>"
            f"<div class='finding-body'>{f.get('message','')}</div></div>")
    return "".join(blocks)


def build_report(a: BlastAnalysis, path: str | Path) -> Path:
    """Escribe el reporte tecnico y devuelve la ruta del archivo generado."""
    p = Path(path)
    if p.suffix.lower() not in (".html", ".htm"):
        p = p.with_suffix(".html")

    d = a.design
    k = a.kpis
    pat = d.pattern
    rock = d.rock
    cons = d.constraints
    charts = _charts(a)
    stamp = time.strftime("%d/%m/%Y %H:%M")

    score_color, score_bg, _ = (_LEVEL["ok"] if a.score >= 85 else
                                _LEVEL["warn"] if a.score >= 60 else _LEVEL["error"])

    kpi_cards = "".join(
        f"<div class='card'><div class='card-label'>{label}</div>"
        f"<div class='card-value'>{value}</div><div class='card-unit'>{unit}</div></div>"
        for label, value, unit in (
            ("Taladros", f"{k['n_holes']:,}", ""),
            ("Tonelaje", f"{k['tonnes']:,.0f}", "t"),
            ("Factor de potencia", f"{k['powder_factor']:.3f}", "kg/m3"),
            ("X50", f"{k['x50_cm']:.1f}", "cm"),
            ("P80", f"{k['p80_cm']:.1f}", "cm"),
            ("PPV en receptor", f"{k['ppv_mm_s']:.1f}", "mm/s"),
            ("Onda aerea", f"{k['airblast_db']:.0f}", "dBL"),
            ("Costo total", f"{k['cost_total_usd_t']:.3f}", "USD/t"),
        ))

    geometry = _table([
        ("Disposicion", pat.pattern),
        ("Burden nominal", f"{pat.burden_m:.2f} m"),
        ("Espaciamiento nominal", f"{pat.spacing_m:.2f} m"),
        ("Burden real medio", f"{a.burden_stats.get('burden_mean_m', 0):.2f} m"),
        ("Dispersion del burden", f"{a.burden_stats.get('burden_cv_pct', 0):.1f} %"),
        ("Diametro de taladro", f"{pat.diameter_mm:.0f} mm"),
        ("Altura de banco", f"{pat.bench_height_m:.2f} m"),
        ("Subperforacion", f"{pat.subdrill_m:.2f} m"),
        ("Taco de collar", f"{pat.stemming_m:.2f} m"),
        ("Inclinacion", f"{pat.inclination_deg:.0f}° desde la vertical"),
        ("Longitud de taladro", f"{pat.hole_length_m:.2f} m"),
        ("Relacion de rigidez H/B", f"{pat.stiffness_ratio:.2f}"),
        ("Relacion S/B", f"{pat.s_b_ratio:.2f}"),
        ("Filas x columnas", f"{pat.rows} x {pat.cols}"),
        ("Perforacion total", f"{k['drilled_m']:,.0f} m"),
        ("Factor de perforacion", f"{k['drill_factor_m_m3']:.4f} m/m3"),
    ])

    rock_table = _table([
        ("Litologia", rock.name),
        ("Densidad", f"{rock.density_t_m3:.2f} t/m3"),
        ("Resistencia a compresion", f"{rock.ucs_mpa:.0f} MPa"),
        ("Modulo de Young", f"{rock.young_gpa:.0f} GPa"),
        ("Velocidad de onda P", f"{rock.p_wave_m_s:,.0f} m/s"),
        ("GSI", f"{rock.gsi}"),
        ("Indice de volabilidad (Lilly)", f"{rock.blastability_index:.1f}"),
        ("Factor de roca A (Kuz-Ram)", f"{rock.rock_factor_a:.2f}"),
        ("Clasificacion", rock.classification),
    ])

    charge_table = _table([
        ("Explosivo de columna", d.column_explosive),
        ("Explosivo de fondo", d.bottom_explosive or "No usa"),
        ("Longitud de carga de fondo", f"{d.bottom_charge_m:.2f} m"),
        ("Cebo", d.primer_type),
        ("Material de taco", d.stemming_material),
        ("Explosivo total", f"{k['charge_kg']:,.0f} kg"),
        ("Energia total", f"{k['energy_mj']:,.0f} MJ"),
        ("Factor de energia", f"{k['energy_factor_mj_t']:.2f} MJ/t"),
        ("Carga especifica", f"{k['specific_charge_kg_t']:.3f} kg/t"),
    ])

    timing_table = _table([
        ("Sistema de iniciacion", d.timing.system),
        ("Patron de amarre", d.timing.pattern),
        ("Retardo entre taladros", f"{d.timing.hole_delay_ms:.0f} ms"),
        ("Retardo entre filas", f"{d.timing.row_delay_ms:.0f} ms"),
        ("Alivio entre taladros", f"{k['hole_relief_ms_m']:.1f} ms/m"),
        ("Alivio entre filas", f"{k['row_relief_ms_m']:.1f} ms/m"),
        ("Duracion del disparo", f"{k['total_duration_ms']:,.0f} ms"),
        ("Carga operante (MIC)", f"{k['mic_kg']:,.0f} kg"),
        ("Probabilidad de solape", f"{k['p_overlap_pct']:.0f} %"),
    ])

    frag = a.fragmentation
    frag_table = _table([
        ("Modelo", frag.model if frag else "—"),
        ("X50", f"{k['x50_cm']:.1f} cm"),
        ("P20", f"{k['p20_cm']:.1f} cm"),
        ("P80", f"{k['p80_cm']:.1f} cm"),
        ("Indice de uniformidad n", f"{k['uniformity_n']:.2f}"),
        ("Finos < 2.5 cm", f"{k['fines_pct']:.1f} %"),
        (f"Sobretamano > {d.costs.oversize_threshold_cm:.0f} cm", f"{k['oversize_pct']:.1f} %"),
    ])

    env_table = _table([
        ("Distancia al receptor", f"{k['receptor_distance_m']:,.0f} m"),
        ("PPV predicho", f"{k['ppv_mm_s']:.2f} mm/s"),
        ("Limite del proyecto", f"{cons.ppv_limit_mm_s:.2f} mm/s"),
        ("Uso del limite", f"{k['ppv_utilization_pct']:.0f} %"),
        ("Onda aerea predicha", f"{k['airblast_db']:.0f} dBL"),
        ("Limite de onda aerea", f"{cons.airblast_limit_db:.0f} dBL"),
        ("Alcance de proyeccion", f"{k['flyrock_m']:.0f} m"),
        ("Distancia segura recomendada", f"{k['safe_distance_m']:.0f} m"),
        ("Radio de exclusion declarado", f"{cons.exclusion_radius_m:.0f} m"),
        ("Radio de dano al talud", f"{k['damage_radius_m']:.1f} m"),
    ])

    cost = a.cost
    cost_rows = ([(name, f"{value:,.0f} USD") for name, value in cost.as_dict().items()]
                 if cost else [])
    if cost:
        cost_rows += [
            ("Perforacion y voladura", f"{cost.db_usd:,.0f} USD ({cost.db_usd_t:.3f} USD/t)"),
            ("Aguas abajo", f"{cost.downstream_usd:,.0f} USD"),
            ("Costo total", f"{cost.total_usd:,.0f} USD ({cost.total_usd_t:.3f} USD/t)"),
        ]
    cost_table = _table(cost_rows, ("Concepto", "Monto"))

    holes_rows = "".join(
        f"<tr><td>{h.hid}</td><td class='num'>{h.easting:,.2f}</td>"
        f"<td class='num'>{h.northing:,.2f}</td><td class='num'>{h.collar_z:,.2f}</td>"
        f"<td class='num'>{h.length_m:.2f}</td><td class='num'>{h.collar_stemming_m:.2f}</td>"
        f"<td class='num'>{h.charge_kg:,.1f}</td><td class='num'>{h.delay_ms:,.0f}</td>"
        f"<td class='num'>{h.burden_real_m:.2f}</td><td class='num'>{h.powder_factor:.3f}</td>"
        f"<td>{h.hole_type}</td></tr>"
        for h in d.holes)

    def img(key: str, caption: str) -> str:
        if key not in charts:
            return ""
        return (f"<figure><img src='{charts[key]}' alt='{caption}'/>"
                f"<figcaption>{caption}</figcaption></figure>")

    html = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<title>Reporte tecnico — {d.name}</title>
<style>
  :root {{ color-scheme: light; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; background:#f4f6f8; color:{_TEXT};
         font-family:'Segoe UI',system-ui,sans-serif; font-size:14px; line-height:1.55; }}
  .sheet {{ max-width:1080px; margin:0 auto; background:#fff; padding:44px 52px 64px;
            box-shadow:0 1px 3px rgba(0,0,0,.07); }}
  header {{ border-bottom:3px solid {_ACCENT}; padding-bottom:18px; margin-bottom:28px; }}
  h1 {{ margin:0 0 4px; font-size:26px; letter-spacing:-.3px; }}
  h2 {{ margin:38px 0 12px; font-size:17px; padding-bottom:7px;
        border-bottom:1px solid {_BORDER}; }}
  h3 {{ margin:22px 0 8px; font-size:14px; color:{_SOFT};
        text-transform:uppercase; letter-spacing:.6px; }}
  .meta {{ color:{_SOFT}; font-size:13px; }}
  .meta strong {{ color:{_TEXT}; }}
  .score {{ display:inline-block; padding:5px 14px; border-radius:14px; font-weight:700;
            color:{score_color}; background:{score_bg}; }}
  .cards {{ display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin:22px 0 8px; }}
  .card {{ border:1px solid {_BORDER}; border-radius:7px; padding:11px 13px; }}
  .card-label {{ font-size:10.5px; font-weight:700; letter-spacing:.5px;
                 text-transform:uppercase; color:{_SOFT}; }}
  .card-value {{ font-size:21px; font-weight:600; margin-top:2px; }}
  .card-unit {{ font-size:11px; color:{_SOFT}; }}
  .cols {{ display:grid; grid-template-columns:1fr 1fr; gap:26px; }}
  table {{ width:100%; border-collapse:collapse; margin:8px 0 4px; font-size:13px; }}
  th {{ text-align:left; background:#fafbfc; color:{_SOFT}; font-size:11px;
        text-transform:uppercase; letter-spacing:.4px; padding:7px 9px;
        border-bottom:1px solid {_BORDER}; }}
  td {{ padding:6px 9px; border-bottom:1px solid #eef1f4; }}
  td.num {{ text-align:right; font-variant-numeric:tabular-nums; font-weight:500; }}
  tbody tr:nth-child(even) {{ background:#fafbfc; }}
  figure {{ margin:18px 0; }}
  figure img {{ width:100%; border:1px solid {_BORDER}; border-radius:6px; }}
  figcaption {{ font-size:12px; color:{_SOFT}; margin-top:6px; }}
  .finding {{ border-left:3px solid; border-radius:4px; padding:9px 12px; margin-bottom:7px; }}
  .finding-head {{ font-weight:700; font-size:13px; }}
  .finding-body {{ color:{_SOFT}; font-size:13px; }}
  .holes {{ font-size:11.5px; }}
  footer {{ margin-top:44px; padding-top:16px; border-top:1px solid {_BORDER};
            color:{_SOFT}; font-size:12px; }}
  @media print {{
    body {{ background:#fff; }}
    .sheet {{ box-shadow:none; padding:0; max-width:none; }}
    h2 {{ page-break-after:avoid; }}
    figure, table {{ page-break-inside:avoid; }}
  }}
</style>
</head>
<body>
<div class="sheet">
  <header>
    <h1>Reporte tecnico de voladura</h1>
    <p class="meta"><strong>{d.name}</strong> · {d.site or 'Sin ubicacion declarada'}
       · Emitido el {stamp}</p>
    <p class="meta">Calidad del diseno: <span class="score">{a.score} / 100</span>
       &nbsp; {len(a.errors)} hallazgos criticos, {len(a.warnings)} avisos</p>
  </header>

  <h2>1. Resumen ejecutivo</h2>
  <div class="cards">{kpi_cards}</div>
  <p class="meta">La voladura mueve {k['volume_m3']:,.0f} m3 ({k['tonnes']:,.0f} t) con
     {k['charge_kg']:,.0f} kg de explosivo distribuidos en {k['n_holes']} taladros y
     {k['drilled_m']:,.0f} m de perforacion. El costo de perforacion y voladura asciende a
     {k['cost_db_usd_t']:.3f} USD/t y el costo total incluyendo el efecto de la fragmentacion
     sobre carguio, acarreo y chancado a {k['cost_total_usd_t']:.3f} USD/t.</p>

  <h2>2. Revision del diseno</h2>
  {_findings_html(a.findings)}

  <h2>3. Geometria y macizo rocoso</h2>
  <div class="cols">
    <div><h3>Malla</h3>{geometry}</div>
    <div><h3>Macizo rocoso</h3>{rock_table}</div>
  </div>

  <h2>4. Diseno de carga</h2>
  {charge_table}

  <h2>5. Secuencia de salida</h2>
  {timing_table}
  {img('secuencia', 'Carga detonada por ventana de cooperacion.')}

  <h2>6. Fragmentacion prevista</h2>
  {frag_table}
  {img('fragmentacion', 'Curva granulometrica por el modelo de Swebrec (KCO) sobre Kuz-Ram.')}

  <h2>7. Control ambiental y seguridad</h2>
  {env_table}
  {img('vibracion', 'Sismograma previsto por superposicion de onda semilla en el receptor.')}

  <h2>8. Analisis economico</h2>
  {cost_table}
  {img('costos', 'Estructura de costos por tonelada volada.')}

  <h2>9. Detalle de taladros</h2>
  <table class="holes">
    <thead><tr><th>ID</th><th>Este</th><th>Norte</th><th>Cota</th><th>Long. (m)</th>
      <th>Taco (m)</th><th>Carga (kg)</th><th>Retardo (ms)</th><th>Burden (m)</th>
      <th>FP (kg/m3)</th><th>Tipo</th></tr></thead>
    <tbody>{holes_rows}</tbody>
  </table>

  <footer>
    Generado por {__appname__} {__version__}. Los modelos empleados —
    Kuznetsov-Cunningham, Swebrec (KCO), Holmberg-Persson, distancia escalada USBM,
    Richards &amp; Moore y Lilly — son predictivos y deben calibrarse con mediciones
    de campo antes de usarse como base de decision operativa.
  </footer>
</div>
</body>
</html>"""

    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(html, encoding="utf-8")
    return p
