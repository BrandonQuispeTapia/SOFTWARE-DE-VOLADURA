"""
reports/report_generator.py
===========================
Orquestador de Plantillas y PDF para VOLADURA_PRO_10X.

Combina la lógica de negocio (CostEngine), la generación de gráficos en 
memoria (HeadlessChartGenerator) y el motor de plantillas (Jinja2) 
para ensamblar documentos PDF corporativos vía WeasyPrint.

Autor: Félix Fernando Bautista Layme — UNA Puno.
"""

from __future__ import annotations

import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

try:
    import jinja2
except ImportError:
    raise ImportError("Jinja2 requerido: pip install Jinja2")

from core.geometry import BlastPattern
from core.rock_mass import RockProperties
from optimization.cost_engine import CostEngine, CostParameters
from reports.charts_engine import HeadlessChartGenerator


logger = logging.getLogger(__name__)
_TEMPLATES_DIR = Path(__file__).parent / "templates"


class PDFReportBuilder:
    """Constructor y Orquestador de Reportes Corporativos en PDF."""
    
    def __init__(
        self,
        templates_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None,
        company_name: str = "Minera UNA Puno S.A.",
        project_name: str = "Tajo Principal",
        responsable: str = "Félix Fernando Bautista Layme",
        cargo: str = "Ingeniero de Perforación y Voladura"
    ):
        self.templates_dir = templates_dir or _TEMPLATES_DIR
        self.output_dir = output_dir or Path("./reports_output")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.company_name = company_name
        self.project_name = project_name
        self.responsable = responsable
        self.cargo = cargo
        
        # Inicializar Motores
        self.cost_engine = CostEngine(CostParameters())
        self.chart_engine = HeadlessChartGenerator()
        
        # Inicializar Jinja2
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        self.jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(self.templates_dir)),
            autoescape=jinja2.select_autoescape(["html", "xml"])
        )
        # Filtros básicos
        self.jinja_env.filters["fmt_num"] = lambda v, d=2: f"{v:,.{d}f}" if v else "—"

    def _compile_pdf(self, html_string: str, output_filename: str) -> Path:
        """Compila el HTML a PDF usando WeasyPrint."""
        output_path = self.output_dir / output_filename
        
        try:
            from weasyprint import HTML
            HTML(string=html_string).write_pdf(str(output_path))
            logger.info(f"Reporte PDF generado exitosamente: {output_path}")
        except ImportError:
            # Fallback a HTML puro si weasyprint no está instalado
            fallback_path = output_path.with_suffix(".html")
            fallback_path.write_text(html_string, encoding="utf-8")
            logger.warning(
                f"WeasyPrint no encontrado. Guardando HTML fallback en: {fallback_path}"
            )
            return fallback_path
            
        return output_path

    def build_executive_report(
        self, 
        pattern: BlastPattern, 
        rock: RockProperties,
        fragmentation_sizes_mm: list[float] = None,
        fragmentation_passing_pct: list[float] = None
    ) -> Path:
        """Controlador para el Reporte Ejecutivo.
        
        Recopila datos, calcula KPIs económicos, renderiza gráficos en Base64
        y compila el documento PDF.
        """
        # 1. Calcular Costos
        kpis = self.cost_engine.calculate_kpis(pattern, rock.density_tm3)
        
        # 2. Generar Gráficos en Base64
        pie_chart_b64 = self.chart_engine.generate_kpi_pie_chart(kpis)
        
        kuzram_chart_b64 = ""
        if fragmentation_sizes_mm and fragmentation_passing_pct:
            kuzram_chart_b64 = self.chart_engine.generate_kuzram_curve(
                fragmentation_sizes_mm, fragmentation_passing_pct
            )

        # 3. Armar Contexto
        context = {
            "empresa": self.company_name,
            "proyecto": self.project_name,
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "responsable": self.responsable,
            "cargo": self.cargo,
            
            # Datos Geométricos
            "burden_m": pattern.burden,
            "spacing_m": pattern.spacing,
            "bench_height_m": pattern.bench_height,
            "total_holes": pattern.total_holes,
            "total_charge_kg": pattern.total_charge_kg,
            "rock_name": rock.name,
            
            # KPIs
            "kpis": kpis,
            
            # Imágenes Base64
            "pie_chart_b64": pie_chart_b64,
            "kuzram_chart_b64": kuzram_chart_b64
        }
        
        # 4. Renderizar Plantilla
        template = self.jinja_env.get_template("executive.html")
        html_out = template.render(**context)
        
        # 5. Compilar a PDF
        filename = f"Reporte_Ejecutivo_{pattern.pattern_id}_{datetime.now().strftime('%Y%m%d%H%M')}.pdf"
        return self._compile_pdf(html_out, filename)
