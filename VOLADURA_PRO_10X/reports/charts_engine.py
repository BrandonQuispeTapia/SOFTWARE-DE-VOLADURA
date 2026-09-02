"""
reports/charts_engine.py
========================
Generador de Gráficos Headless para VOLADURA_PRO_10X.

Renderiza gráficos usando matplotlib en backend 'Agg' (memoria) y los 
convierte a cadenas Base64 para inyección directa en plantillas HTML/Jinja2.

Autor: Félix Fernando Bautista Layme — UNA Puno.
"""

import io
import base64
from typing import Dict, List, Any

# Configurar backend Headless antes de importar pyplot
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


class HeadlessChartGenerator:
    """Generador de gráficos estadísticos en Base64."""
    
    @staticmethod
    def _fig_to_base64(fig: plt.Figure) -> str:
        """Convierte una figura Matplotlib a cadena Base64 (PNG)."""
        buf = io.BytesIO()
        fig.savefig(buf, format='png', bbox_inches='tight', dpi=150)
        buf.seek(0)
        img_str = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig) # Liberar memoria
        return img_str

    def generate_kpi_pie_chart(self, costs_dict: Dict[str, float]) -> str:
        """Genera un gráfico de torta (Pie Chart) de la distribución de costos.
        
        Args:
            costs_dict: Diccionario con los costos (ej. Perforación, Explosivos, Accesorios).
            
        Returns:
            String Base64 de la imagen PNG.
        """
        labels = [
            "Perforación", 
            "Explosivos", 
            "Accesorios"
        ]
        sizes = [
            costs_dict.get("drilling_cost_usd", 0),
            costs_dict.get("explosives_cost_usd", 0),
            costs_dict.get("accessories_cost_usd", 0)
        ]
        
        # Filtrar ceros para no arruinar el gráfico
        filtered_labels = []
        filtered_sizes = []
        for l, s in zip(labels, sizes):
            if s > 0:
                filtered_labels.append(l)
                filtered_sizes.append(s)
                
        if not filtered_sizes:
            filtered_sizes = [1]
            filtered_labels = ["Sin Datos"]

        fig, ax = plt.subplots(figsize=(5, 4))
        colors = ['#f59e0b', '#3b82f6', '#10b981']
        
        wedges, texts, autotexts = ax.pie(
            filtered_sizes, 
            labels=filtered_labels, 
            autopct='%1.1f%%',
            startangle=90,
            colors=colors,
            textprops=dict(color="w")
        )
        
        # Estilizar
        plt.setp(autotexts, size=10, weight="bold")
        plt.setp(texts, size=9, color="#1a1a2e")
        ax.set_title("Distribución de Costos D&B", color="#1a1a2e", fontweight="bold")
        
        # Fondo transparente
        fig.patch.set_alpha(0.0)
        ax.patch.set_alpha(0.0)

        return self._fig_to_base64(fig)

    def generate_kuzram_curve(self, sizes_mm: List[float], passing_pct: List[float]) -> str:
        """Genera la curva de fragmentación Kuz-Ram.
        
        Args:
            sizes_mm: Lista de tamaños de malla en mm.
            passing_pct: Lista de porcentajes pasantes [0-100].
            
        Returns:
            String Base64 de la imagen PNG.
        """
        fig, ax = plt.subplots(figsize=(6, 4))
        
        ax.plot(sizes_mm, passing_pct, color='#f59e0b', linewidth=2.5, marker='o', markersize=4)
        
        ax.set_title('Curva Granulométrica (Modelo Kuz-Ram)', fontweight="bold")
        ax.set_xlabel('Tamaño de malla (mm)')
        ax.set_ylabel('Porcentaje Pasante (%)')
        ax.grid(True, linestyle='--', alpha=0.7)
        
        # Ajustar límites
        ax.set_ylim(0, 100)
        if sizes_mm:
            ax.set_xlim(0, max(sizes_mm))

        return self._fig_to_base64(fig)
