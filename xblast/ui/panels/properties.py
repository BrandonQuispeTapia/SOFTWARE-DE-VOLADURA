"""Panel de propiedades del taladro seleccionado.

Muestra geometria, columna de carga, secuencia y resultados de analisis del
taladro activo, y permite cambiar su tipo sin salir del visor.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ...core.models import HOLE_TYPE_COLORS, Hole, HoleType
from .. import widgets as W
from ..theme import C


class PropertiesPanel(QWidget):
    """Ficha del taladro activo."""

    hole_type_changed = Signal(str, str)   # (hid, nuevo tipo)

    def __init__(self):
        super().__init__()
        self._hole: Optional[Hole] = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(8)
        self.title = W.title("Sin seleccion", 1)
        self.chip = W.StatusChip("—", "info")
        header.addWidget(self.title)
        header.addStretch(1)
        header.addWidget(self.chip)
        lay.addLayout(header)

        self.empty = W.caption(
            "Haga clic en un taladro del visor 3D o seleccionelo en el explorador "
            "para ver su ficha completa.")
        lay.addWidget(self.empty)

        self.body = QWidget()
        body_lay = QVBoxLayout(self.body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(10)

        type_section = W.Section("Clasificacion")
        self.type_combo = type_section.row("Tipo", W.combo([t.value for t in HoleType]))
        self.type_combo.currentTextChanged.connect(self._on_type_changed)
        body_lay.addWidget(type_section)

        self.geometry = W.KeyValueTable()
        geo_section = W.Section("Geometria")
        geo_section.add(self.geometry)
        body_lay.addWidget(geo_section)

        self.charge = W.KeyValueTable()
        charge_section = W.Section("Carga")
        charge_section.add(self.charge)
        body_lay.addWidget(charge_section)

        self.decks = W.DataTable(["Plataforma", "Long. (m)", "Producto", "Cebos"])
        self.decks.setMinimumHeight(150)
        deck_section = W.Section("Columna, del fondo al collar")
        deck_section.add(self.decks)
        body_lay.addWidget(deck_section)

        self.results = W.KeyValueTable()
        res_section = W.Section("Resultados del analisis")
        res_section.add(self.results)
        body_lay.addWidget(res_section)
        body_lay.addStretch(1)

        scroll = W.ScrollPanel(spacing=0, margins=(0, 0, 4, 0))
        scroll.add(self.body)
        lay.addWidget(scroll, 1)
        self.body.setVisible(False)

    # -- API ---------------------------------------------------------------
    def show_hole(self, hole: Optional[Hole]) -> None:
        self._hole = hole
        self.empty.setVisible(hole is None)
        self.body.setVisible(hole is not None)
        if hole is None:
            self.title.setText("Sin seleccion")
            self.chip.set_status("—", "info")
            return

        self.title.setText(f"Taladro {hole.hid}")
        color = HOLE_TYPE_COLORS.get(hole.hole_type, C["text_soft"])
        self.chip.setText(hole.hole_type)
        self.chip.setStyleSheet(
            f"color:#ffffff; background-color:{color}; border-radius:9px;"
            "padding:3px 10px; font-size:8pt; font-weight:700;")

        self.type_combo.blockSignals(True)
        self.type_combo.setCurrentText(hole.hole_type)
        self.type_combo.blockSignals(False)

        self.geometry.set_items([
            ("Este", f"{hole.easting:,.2f} m"),
            ("Norte", f"{hole.northing:,.2f} m"),
            ("Cota de collar", f"{hole.collar_z:,.2f} m"),
            ("Cota de fondo", f"{hole.toe_z:,.2f} m"),
            ("Longitud", f"{hole.length_m:.2f} m"),
            ("Diametro", f"{hole.diameter_mm:.0f} mm"),
            ("Inclinacion", f"{hole.inclination_from_vertical_deg:.0f}° desde vertical"),
            ("Azimut", f"{hole.azimuth_deg:.0f}°"),
            ("Altura de banco", f"{hole.bench_height_m:.2f} m"),
            ("Subperforacion", f"{hole.subdrill_m:.2f} m"),
            ("Fila / columna", f"{hole.row + 1} / {hole.col + 1}"),
        ])

        lin = hole.charge_kg / max(hole.charge_length_m, 1e-6)
        self.charge.set_items([
            ("Carga total", f"{hole.charge_kg:,.1f} kg"),
            ("Energia", f"{hole.energy_mj:,.0f} MJ"),
            ("Longitud cargada", f"{hole.charge_length_m:.2f} m"),
            ("Densidad lineal", f"{lin:.2f} kg/m"),
            ("Taco de collar", f"{hole.collar_stemming_m:.2f} m"),
            ("Camara de aire", f"{hole.air_length_m:.2f} m"),
            ("Cebos", f"{hole.n_primers}"),
            ("Plataformas de carga", f"{sum(1 for d in hole.decks if d.is_charge)}"),
        ])

        rows = []
        for d in reversed(hole.decks):
            kind = d.kind.value if hasattr(d.kind, "value") else str(d.kind)
            rows.append([kind, round(d.length_m, 2), d.explosive or "—", d.primers])
        self.decks.set_rows(rows)

        self.results.set_items([
            ("Retardo nominal", f"{hole.delay_ms:,.1f} ms"),
            ("Retardo con dispersion", f"{hole.delay_actual_ms:,.1f} ms"),
            ("Burden real", f"{hole.burden_real_m:.2f} m"),
            ("Burden de alivio", f"{hole.relief_burden_m:.2f} m"),
            ("Espaciamiento real", f"{hole.spacing_real_m:.2f} m"),
            ("Volumen de responsabilidad", f"{hole.volume_m3:,.1f} m3"),
            ("Factor de potencia", f"{hole.powder_factor:.3f} kg/m3"),
            ("Factor de energia", f"{hole.energy_factor:.2f} MJ/t"),
            ("X50 previsto", f"{hole.x50_cm:.1f} cm"),
            ("Indice de uniformidad", f"{hole.uniformity_n:.2f}"),
            ("Confinamiento", f"{hole.confinement:.2f}"),
        ])

    def current_hole(self) -> Optional[Hole]:
        return self._hole

    # -- eventos -----------------------------------------------------------
    def _on_type_changed(self, new_type: str) -> None:
        if self._hole is not None:
            self.hole_type_changed.emit(self._hole.hid, new_type)
