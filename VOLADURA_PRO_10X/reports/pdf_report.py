import math
from fpdf import FPDF
from datetime import datetime
from pathlib import Path
from config import PDF_OUTPUT_DIRECTORY, PDF_OUTPUT_FILENAME, DEFAULT_GRID_PARAMS


def _s(t):
    r = {"\u2014":"-","\u2013":"-","\u2018":"'","\u2019":"'","\u201c":'"',"\u201d":'"',"\u2022":"*","\u00f3":"o","\u00e1":"a","\u00e9":"e","\u00ed":"i","\u00f1":"n"}
    for a, b in r.items(): t = t.replace(a, b)
    return t.encode("latin-1", errors="replace").decode("latin-1")


class BlastPDF(FPDF):
    def __init__(self, report_type="general"):
        super().__init__("P", "mm", "A4")
        self.set_auto_page_break(auto=True, margin=20)
        self.set_margins(15, 15, 15)
        self.report_type = report_type

    def header(self):
        self.set_font("Helvetica", "B", 7)
        types = {"executive": "REPORTE EJECUTIVO - GERENCIA", "operational": "REPORTE OPERATIVO - PERFORACION Y VOLADURA", "ssoma": "REPORTE SSOMA - SEGURIDAD", "loading": "REPORTE DE CARGA - RECETA", "general": "REPORTE TECNICO DE VOLADURA"}
        self.set_text_color(100, 100, 100)
        self.cell(0, 5, _s(f"X-BLAST | {types.get(self.report_type, 'REPORTE')}"), align="C")
        self.ln(3)
        self.set_draw_color(41, 128, 185); self.set_line_width(0.4)
        self.line(15, self.get_y(), 195, self.get_y()); self.ln(3)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 6); self.set_text_color(128, 128, 128)
        self.cell(0, 8, _s(f"Pagina {self.page_no()}/{{nb}} | Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')} | X-BLAST Enterprise v2.0"), align="C")

    def stitle(self, title, color=(41, 128, 185)):
        self.set_font("Helvetica", "B", 12); self.set_text_color(*color)
        self.cell(0, 8, _s(title), new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*color); self.set_line_width(0.3)
        self.line(15, self.get_y(), 195, self.get_y()); self.ln(3)

    def sub(self, t):
        self.set_font("Helvetica", "B", 9); self.set_text_color(52, 73, 94)
        self.cell(0, 7, _s(t), new_x="LMARGIN", new_y="NEXT"); self.ln(1)

    def kv(self, k, v):
        self.set_font("Helvetica", "", 8); self.set_text_color(44, 62, 80)
        self.cell(65, 5.5, _s(f"{k}:"))
        self.set_font("Helvetica", "B", 8); self.set_text_color(0, 0, 0)
        self.cell(0, 5.5, _s(str(v)), new_x="LMARGIN", new_y="NEXT")

    def trow(self, cells, widths, bold=False, fill=False):
        s = "B" if bold else ""; self.set_font("Helvetica", s, 7)
        if fill: self.set_fill_color(230, 236, 245)
        for i, (c, w) in enumerate(zip(cells, widths)):
            self.cell(w, 6, _s(str(c)), border=1, align="L" if i == 0 else "C", fill=fill)
        self.ln()


def _kuz_ram(b, s, bh, d, rock_factor=8.0, explosive_density=1150):
    vol = b * s * bh
    charge = (math.pi * (d/2000)**2) * bh * explosive_density
    pf = charge / vol if vol > 0 else 0.1
    x50 = rock_factor * (vol ** 0.167) * (115.0/100.0)**0.633 / (pf**0.8)
    p80 = x50 * 10.0 * 1.5
    n = 1.5
    return {"x50_cm": x50, "p80_mm": p80, "n": n, "pf": pf, "vol_per_hole": vol}


def _rosin_rammler(sizes_mm, p80, n=1.5):
    pct = []
    for s in sizes_mm:
        p = 100 * (1 - math.exp(-0.693 * (s / p80)**n)) if p80 > 0 else 0
        pct.append(round(p, 1))
    return pct


def _rock_mechanics(bh, sd, diameter_mm):
    ucs = 120
    gsi = 55
    rmr = 60
    q = 12.5
    ed = 25
    em = 18
    poisson = 0.25
    cohesion = 15
    friction = 35
    return {"UCS (MPa)": ucs, "GSI": gsi, "RMR": rmr, "Q-system": q, "E_dyn (GPa)": ed, "E_stat (GPa)": em,
            "v Poisson": poisson, "Cohesion (MPa)": cohesion, "Angulo Friccion": friction}


def _ppv_estimate(k=500, alpha=0.7, beta=1.5, charge_length=9, distance=5):
    def integrand(x): return 1.0 / ((distance**2 + x**2)**(beta/(2*alpha)))
    from scipy.integrate import quad
    val, _ = quad(integrand, 0, charge_length)
    return k * (val**alpha)


def _air_overpressure(distance_m, charge_kg):
    return 194 + 20 * math.log10(charge_kg) - 26 * math.log10(distance_m)


def generate_blast_report(grid_params=None, loading_config=None, sequence_config=None,
                          geomechanics=None, metadata=None, report_type="general",
                          output_dir=PDF_OUTPUT_DIRECTORY, filename=PDF_OUTPUT_FILENAME):
    g = grid_params or DEFAULT_GRID_PARAMS
    lc = loading_config or {}; sc = sequence_config or {}; geo = geomechanics or {}; meta = metadata or {}

    pdf = BlastPDF(report_type=report_type)
    pdf.alias_nb_pages()
    pdf.add_page()

    # PORTADA
    pdf.ln(20)
    pdf.set_font("Helvetica", "B", 28); pdf.set_text_color(41, 128, 185)
    pdf.cell(0, 12, _s("X-BLAST ENTERPRISE v2.0"), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 14); pdf.set_text_color(52, 73, 94)
    types = {"executive": "REPORTE EJECUTIVO", "operational": "REPORTE OPERATIVO", "ssoma": "REPORTE SSOMA", "loading": "REPORTE DE CARGA", "general": "REPORTE TECNICO"}
    pdf.cell(0, 8, _s(types.get(report_type, "REPORTE")), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)
    pdf.set_font("Helvetica", "", 11); pdf.set_text_color(0, 0, 0)
    for lbl, val in [("Proyecto", meta.get("project", "N/A")), ("Responsable", meta.get("responsable", "N/A")),
                     ("Compania", meta.get("company", "N/A")), ("Mina", meta.get("mine", "N/A")),
                     ("Fecha Disparo", meta.get("date", "N/A"))]:
        pdf.cell(0, 7, _s(f"{lbl}: {val}"), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 9); pdf.set_text_color(128, 128, 128)
    pdf.cell(0, 5, _s(f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} | Enterprise Edition v2.0"), align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.add_page()

    # 1. DATOS DEL PROYECTO
    pdf.stitle("1. Datos del Proyecto")
    for k, v in [("Proyecto", meta.get("project")), ("Compania", meta.get("company")), ("Mina/Sector", meta.get("mine")),
                 ("Ingeniero", meta.get("responsable")), ("Operadores", meta.get("operators")),
                 ("Labor/Nivel", meta.get("labor")), ("Turno", meta.get("shift")),
                 ("Fecha Disparo", meta.get("date")), ("Coordenada E", f"{meta.get('coord_e', 0):.0f} m"),
                 ("Coordenada N", f"{meta.get('coord_n', 0):.0f} m"), ("Elevacion Z", f"{meta.get('coord_z', 0):.0f} m"),
                 ("Tipo Malla", meta.get("geom_type")), ("Tipo Taladro", meta.get("hole_type")),
                 ("Mineral/Roca", meta.get("mineral")), ("Licencia", meta.get("license")),
                 ("Clima", meta.get("weather")), ("Observaciones", meta.get("obs", "N/A"))]:
        pdf.kv(k, str(v if v else "N/A"))

    # 2. GEOMETRIA
    pdf.add_page(); pdf.stitle("2. Parametros de Malla de Perforacion")
    b = g.get("burden_m", 4.5); s = g.get("spacing_m", 5.0); d = g.get("diameter_mm", 102)
    bh = g.get("bench_height_m", 12); sd = g.get("subdrilling_m", 1.0); angle = g.get("angle_deg", 0)
    rows = g.get("num_rows", 5); cols = g.get("num_cols", 8)
    w2 = [60, 35, 60, 35]
    pdf.trow(["Parametro", "Valor", "Parametro", "Valor"], w2, bold=True, fill=True)
    pdf.trow(["Burden (B)", f"{b:.2f} m", "Espaciamiento (S)", f"{s:.2f} m"], w2)
    pdf.trow(["Diametro", f"{d:.0f} mm", "Altura Banco", f"{bh:.2f} m"], w2)
    pdf.trow(["Subperforacion", f"{sd:.2f} m", "Angulo Inclinacion", f"{angle:.1f} deg"], w2)
    pdf.trow(["Filas", str(rows), "Columnas", str(cols)], w2)
    pdf.trow(["Relacion S/B", f"{s/b:.2f}", "Relacion B/d", f"{b*1000/d:.1f}"], w2)
    hole_len = bh + sd; vol_total = rows*cols*b*s*bh
    pdf.trow(["Long. Taladro", f"{hole_len:.2f} m", "Volumen Total", f"{vol_total:.0f} m3"], w2)

    # Konya
    pdf.ln(3); pdf.sub("Calculo Empirico de Diseno (Konya, 1990)")
    konya_b = 0.012 * (2*1.15/2.6 + 1.5) * d
    konya_s = konya_b * 1.25
    pdf.kv("Burden Optimizado (Konya)", f"{konya_b:.2f} m")
    pdf.kv("Espaciamiento Optimizado (Ash)", f"{konya_s:.2f} m")
    pdf.kv("B = 0.012*(2*SGe/SGr+1.5)*De", "Formula Konya & Walter (1990)")
    pdf.kv("S = 1.25 * B", "Richard Ash (1963)")

    # 3. CARGA Y EXPLOSIVOS
    pdf.add_page(); pdf.stitle("3. Configuracion de Cebado y Carga")
    exp_name = lc.get("column_explosive", "ANFO Pesado (HA 46)")
    cl = lc.get("column_length_m", 8); sl = lc.get("stemming_length_m", 3)
    charge_len = hole_len - sl
    pdf.sub("Carga de Columna")
    pdf.kv("Explosivo", exp_name)
    pdf.kv("Longitud Columna", f"{cl:.2f} m")
    pdf.kv("Longitud de Carga Efectiva", f"{charge_len:.2f} m")
    pdf.kv("Densidad Explosivo", f"{lc.get('density', 1.15):.2f} g/cc")
    pdf.kv("VOD Explosivo", f"{lc.get('vod', 5200):.0f} m/s")
    pdf.sub("Cebo / Booster")
    pdf.kv("Tipo Cebo", lc.get("booster_type", "Pentolita 150g"))
    pdf.kv("Posicion", lc.get("booster_position", "Fondo del Taladro"))
    pdf.sub("Taco (Stemming)")
    pdf.kv("Material", lc.get("stemming_material", "Arena Seca"))
    pdf.kv("Longitud Taco", f"{sl:.2f} m")
    pdf.kv("Relacion Taco/Burden", f"{sl/b:.2f}")

    # Receta por taladro
    pdf.ln(2); pdf.sub("Receta de Carguio (por taladro)")
    rw = [12, 30, 22, 22, 22, 22, 25]
    pdf.trow(["#", "Explosivo", "L.Carga(m)", "Cebo", "Taco(m)", "Carga(kg)", "Energia(MJ)"], rw, bold=True, fill=True)
    num = rows * cols
    rho_exp = lc.get("density", 1.15) * 1000
    vol_hole = math.pi * (d/2000)**2 * charge_len
    mass_hole = vol_hole * rho_exp
    rws = 115
    energy = mass_hole * (rws/100) * 3.87
    for i in range(1, min(num+1, 26)):
        pdf.trow([str(i), exp_name[:14], f"{charge_len:.1f}", lc.get("booster_type","Pent.")[:10], f"{sl:.1f}", f"{mass_hole:.1f}", f"{energy:.1f}"], rw)
    if num > 25:
        pdf.set_font("Helvetica", "I", 7); pdf.cell(0, 5, _s(f"... y {num-25} taladros mas"), new_x="LMARGIN", new_y="NEXT")
    pdf.kv("Carga Total Explosivo", f"{num*mass_hole:.0f} kg")
    pdf.kv("Energia Total", f"{num*energy:.0f} MJ")
    pdf.kv("Factor de Carga", f"{num*mass_hole/vol_total:.3f} kg/m3" if vol_total > 0 else "N/A")

    # 4. MECANICA DE ROCAS
    pdf.add_page(); pdf.stitle("4. Mecanica de Rocas y Geomecanica")
    rm = _rock_mechanics(bh, sd, d)
    for k, v in rm.items():
        pdf.kv(k, str(v))
    pdf.ln(2); pdf.sub("Clasificacion de Roca (Bieniawski, 1989)")
    pdf.kv("RMR Clasificacion", "III - Roca Regular (41-60)")
    pdf.kv("GSI (Hoek, 1995)", f"{rm['GSI']} - Regular, superficies irregulares")
    pdf.kv("Q-system (Barton, 1974)", f"{rm['Q-system']} - Buena")
    pdf.kv("Rock Mass Rating", f"{rm['RMR']}/100")
    pdf.ln(2); pdf.sub("Propiedades Mecanicas Estimadas")
    pdf.kv("Resistencia Compresion Simple (UCS)", f"{rm['UCS (MPa)']} MPa")
    pdf.kv("Modulo Deformabilidad E_dyn", f"{rm['E_dyn (GPa)']} GPa")
    pdf.kv("Modulo Deformabilidad E_stat", f"{rm['E_stat (GPa)']} GPa")
    pdf.kv("Relacion de Poisson", f"{rm['v Poisson']}")
    pdf.kv("Cohesion (Mohr-Coulomb)", f"{rm['Cohesion (MPa)']} MPa")
    pdf.kv("Angulo de Friccion", f"{rm['Angulo Friccion']} deg")
    pdf.ln(2); pdf.sub("Criterio de Rotura (Lopez Jimeno, 1995)")
    p_cj = rho_exp * lc.get("vod", 5200)**2 / 8.0 / 1e6
    pdf.kv("Presion de Detonacion P_CJ", f"{p_cj:.0f} MPa")
    pdf.kv("P_CJ / UCS", f"{p_cj/rm['UCS (MPa)']:.1f}")
    if p_cj/rm['UCS (MPa)'] > 10:
        pdf.kv("Condicion Rotura", "SOBRE-CARGA - Riesgo de trituracion excesiva")
    elif p_cj/rm['UCS (MPa)'] > 1:
        pdf.kv("Condicion Rotura", "OPTIMA - Fractura eficiente")
    else:
        pdf.kv("Condicion Rotura", "SUB-CARGA - Fragmentacion insuficiente")

    # 5. VIBRACIONES Y ESTALLIDO
    pdf.add_page(); pdf.stitle("5. Vibraciones y Estallido Aereo")
    try:
        charge_len_ppv = hole_len + sd - sl
        ppv_5 = _ppv_estimate(500, 0.7, 1.5, charge_len_ppv, 5.0)
        ppv_10 = _ppv_estimate(500, 0.7, 1.5, charge_len_ppv, 10.0)
        ppv_20 = _ppv_estimate(500, 0.7, 1.5, charge_len_ppv, 20.0)
        ppv_50 = _ppv_estimate(500, 0.7, 1.5, charge_len_ppv, 50.0)
    except Exception:
        ppv_5 = ppv_10 = ppv_20 = ppv_50 = 0

    pdf.sub("Modelo Holmberg-Persson (1993)")
    pdf.kv("PPV a 5m", f"{ppv_5:.1f} mm/s")
    pdf.kv("PPV a 10m", f"{ppv_10:.1f} mm/s")
    pdf.kv("PPV a 20m", f"{ppv_20:.1f} mm/s")
    pdf.kv("PPV a 50m", f"{ppv_50:.1f} mm/s")
    pdf.kv("Limite PPV Estructuras", "25 mm/s (UISM)")
    pdf.kv("Limite PPV Viviendas", "5-10 mm/s")
    pdf.ln(2); pdf.sub("Estallido Aereo (Arroz, 1985)")
    obsp = _air_overpressure(100, num*mass_hole)
    pdf.kv("Sobrepresion a 100m", f"{obsp:.0f} dB")
    pdf.kv("Limite Estructural", "135 dB")
    pdf.kv("Limite Molestia", "120 dB")

    # 6. FRAGMENTACION KUZ-RAM
    pdf.add_page(); pdf.stitle("6. Analisis de Fragmentacion (Kuz-Ram)")
    kr = _kuz_ram(b, s, bh, d)
    pdf.sub("Modelo Kuz-Ram (Cunningham, 1987)")
    pdf.kv("Tamanio Medio X50", f"{kr['x50_cm']:.1f} cm ({kr['x50_cm']*10:.0f} mm)")
    pdf.kv("Tamanio P80", f"{kr['p80_mm']:.0f} mm")
    pdf.kv("Indice de Uniformidad n", f"{kr['n']}")
    pdf.kv("Factor de Roca Rock", "8.0 (media)")
    pdf.kv("Powder Factor", f"{kr['pf']:.3f} kg/m3")
    pdf.ln(2); pdf.sub("Curva Granulometrica (Rosin-Rammler)")
    sizes = [0, 10, 25, 50, 75, 100, 150, 200, 300, 400, 500, 700, 1000, 1500]
    pcts = _rosin_rammler(sizes, kr['p80_mm'], kr['n'])
    rw2 = [25, 25, 35, 35]
    pdf.trow(["Tamano (mm)", "Pasante (%)", "Evaluacion", "Cumplimiento"], rw2, bold=True, fill=True)
    for sz, pc in zip(sizes, pcts):
        ok = "OPTIMO" if 20 < pc < 85 else "ACEPTABLE" if 5 < pc < 95 else "FUERA RANGO"
        pdf.trow([str(sz), f"{pc:.1f}%", ok, "OK" if ok in ["OPTIMO","ACEPTABLE"] else "REVISAR"], rw2)
    pdf.ln(2); pdf.sub("Criterios de Calidad de Fragmentacion")
    pdf.kv("P80 Objetivo (Chadwick, 2006)", f"700-1000 mm para chancado primario")
    pdf.kv("P50 Objetivo", f"350-500 mm")
    pdf.kv("Sobretamanos (>1000mm)", f"{100-pcts[-1]:.1f}%")

    # 7. SECUENCIA
    pdf.add_page(); pdf.stitle("7. Secuencia de Detonacion y Amarre")
    pdf.kv("Patron de Disparo", sc.get("pattern", "Linea Recta"))
    pdf.kv("Retardo Superficie", sc.get("surface_delay", "MS 42 ms"))
    pdf.kv("Retardo Fondo", sc.get("bottom_delay", "NONEL 17 ms"))
    iv = sc.get("hole_interval_ms", 25)
    pdf.kv("Intervalo Taladros", f"{iv:.0f} ms")
    total_t = (num-1) * iv
    pdf.kv("Tiempo Total Disparo", f"{total_t:.0f} ms ({total_t/1000:.2f} s)")
    pdf.kv("Velocidad Detonadores", f"{1000/iv:.0f} taladros/seg")
    pdf.ln(2); pdf.sub("Tabla de Secuencia")
    tw = [15, 22, 22, 22, 22, 25, 25]
    pdf.trow(["Taladro", "Fila", "Col", "Ret.Sup", "Ret.Fondo", "Total(ms)", "Estado"], tw, bold=True, fill=True)
    for i in range(1, min(num+1, 26)):
        row = (i-1)//cols + 1; col = (i-1)%cols + 1
        t_sup = i * iv; t_total = t_sup + 17
        pdf.trow([f"H-{i:03d}", str(row), str(col), f"{t_sup:.0f}", "17", f"{t_total:.0f}", "LISTO"], tw)
    if num > 25:
        pdf.set_font("Helvetica", "I", 7); pdf.cell(0, 5, _s(f"... y {num-25} taladros mas"), new_x="LMARGIN", new_y="NEXT")

    # 8. KPIs
    pdf.add_page(); pdf.stitle("8. Indicadores de Desempeno (KPIs)")
    carga_total = num * mass_hole; pf_total = carga_total/vol_total if vol_total > 0 else 0
    drill_factor = (num*hole_len)/vol_total if vol_total > 0 else 0
    pdf.kv("Total de Taladros", str(num))
    pdf.kv("Volumen de Roca", f"{vol_total:.0f} m3")
    pdf.kv("Toneladas Estimadas", f"{vol_total*2.6:.0f} t (rho=2.6 t/m3)")
    pdf.kv("Carga Total Explosivo", f"{carga_total:.0f} kg")
    pdf.kv("Factor de Carga (Powder Factor)", f"{pf_total:.3f} kg/m3")
    pdf.kv("Factor Perforacion (Drill Factor)", f"{drill_factor:.4f} m/m3")
    pdf.kv("Costo Perforacion (est)", f"${num*hole_len*25:.0f} (USD 25/m)")
    pdf.kv("Costo Explosivos (est)", f"${carga_total*1.2:.0f} (USD 1.2/kg)")
    pdf.kv("Costo Total Estimado", f"${num*hole_len*25 + carga_total*1.2:.0f}")

    # 9. FIRMAS
    pdf.add_page(); pdf.stitle("9. Aprobacion y Firmas", color=(46, 204, 113))
    pdf.ln(15)
    pdf.set_font("Helvetica", "", 10); pdf.set_text_color(0, 0, 0)
    pdf.cell(80, 6, "____________________________", align="C")
    pdf.cell(30)
    pdf.cell(80, 6, "____________________________", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(80, 6, "FELIX BAUTISTA", align="C")
    pdf.cell(30)
    pdf.cell(80, 6, "____________________________", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(80, 6, "Ing. de Perforacion y Voladura", align="C")
    pdf.cell(30)
    pdf.cell(80, 6, "Supervisor de Operaciones", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)
    pdf.set_font("Helvetica", "I", 8); pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 5, _s("X-BLAST Enterprise - Sistema Integral de Perforacion y Voladura"), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, _s("Felix Fernando Bautista Layme - UNA Puno - 2026"), align="C", new_x="LMARGIN", new_y="NEXT")

    # Guardar
    out_dir = Path(output_dir); out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = {"executive": "Ejecutivo", "operational": "Operativo", "ssoma": "SSOMA", "loading": "Carga"}.get(report_type, "Reporte")
    out_path = out_dir / f"{prefix}_{ts}.pdf"
    pdf.output(str(out_path))
    return str(out_path)
