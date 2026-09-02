"""Panel de diseno de la columna de carga.

Define la regla de carguio (carga de fondo, columna, plataformas, camara de
aire y taco) y muestra en vivo el resultado sobre un taladro representativo.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel

from ...core import explosives as exdb
from ...core.charging import ChargeRule, build_column, linear_charge_profile, refresh_hole_charge
from ...core.models import Hole
from .. import widgets as W
from ..charts import ChargeProfileChart
from ..theme import C


class ChargePanel(W.ScrollPanel):
    """Regla de carguio y vista previa de la columna."""

    changed = Signal()

    def __init__(self):
        super().__init__()
        rule = ChargeRule()
        names = exdb.names()

        col = W.Section(
            "Columna",
            "Explosivo principal que ocupa el cuerpo del taladro.")
        self.column_exp = col.row("Explosivo de columna", W.combo(names, rule.column_explosive))
        self.coupling = col.row("Acoplamiento", W.spin(0.2, 1.0, rule.coupling, 0.05, "d carga / d taladro", 2),
                                "1.00 es carga acoplada. Valores menores desacoplan la carga "
                                "y reducen la presion sobre la pared (voladura controlada).")
        self.add(col)

        bottom = W.Section(
            "Carga de fondo",
            "Carga de mayor densidad y energia para romper el pie del banco.")
        self.use_bottom = W.combo(["Si", "No"], "Si")
        bottom.row("Usar carga de fondo", self.use_bottom)
        self.bottom_exp = bottom.row("Explosivo de fondo", W.combo(names, rule.bottom_explosive))
        self.bottom_len = bottom.row("Longitud", W.spin(0, 15, rule.bottom_charge_m, 0.1, "m"))
        self.add(bottom)

        decks = W.Section(
            "Plataformas y taco",
            "Dividir la carga reduce la carga operante y mejora la distribucion "
            "de energia en bancos altos.")
        self.n_decks = decks.row("Plataformas de carga", W.int_spin(1, 5, rule.n_decks))
        self.inter_stem = decks.row("Taco intermedio", W.spin(0, 8, rule.inter_deck_stem_m, 0.1, "m"))
        self.air_deck = decks.row("Camara de aire", W.spin(0, 8, rule.air_deck_m, 0.1, "m"),
                                  "Reduce consumo de explosivo manteniendo la fragmentacion "
                                  "en la parte alta del banco.")
        self.stemming = decks.row("Taco de collar", W.spin(0.3, 12, rule.stemming_m, 0.1, "m"))
        self.stem_material = decks.row("Material de taco", W.combo(
            list(exdb.STEMMING_MATERIALS), rule.stemming_material))
        self.add(decks)

        init = W.Section("Iniciacion")
        self.primer_type = init.row("Cebo", W.combo(exdb.primer_names(), rule.primer_type))
        self.primers = init.row("Cebos por plataforma", W.int_spin(0, 4, rule.primer_per_deck))
        self.add(init)

        summary = W.Section("Resultado en el taladro tipo")
        self.out_charge = summary.row("Carga total", _value("—"))
        self.out_linear = summary.row("Densidad lineal", _value("—"))
        self.out_length = summary.row("Longitud cargada", _value("—"))
        self.out_energy = summary.row("Energia", _value("—"))
        self.out_pressure = summary.row("Presion de taladro", _value("—"))
        self.add(summary)

        self.preview = ChargeProfileChart()
        self.preview.setMinimumHeight(260)
        self.add(self.preview)
        self.finish()

        for w in (self.coupling, self.bottom_len, self.n_decks, self.inter_stem,
                  self.air_deck, self.stemming, self.primers):
            w.valueChanged.connect(self._on_change)
        for w in (self.column_exp, self.bottom_exp, self.use_bottom,
                  self.stem_material, self.primer_type):
            w.currentTextChanged.connect(self._on_change)

        self._reference: Optional[Hole] = None

    # -- API ---------------------------------------------------------------
    def rule(self) -> ChargeRule:
        return ChargeRule(
            column_explosive=self.column_exp.currentText(),
            bottom_explosive=(self.bottom_exp.currentText()
                              if self.use_bottom.currentText() == "Si" else None),
            bottom_charge_m=self.bottom_len.value(),
            stemming_m=self.stemming.value(),
            coupling=self.coupling.value(),
            n_decks=self.n_decks.value(),
            inter_deck_stem_m=self.inter_stem.value(),
            air_deck_m=self.air_deck.value(),
            primer_per_deck=self.primers.value(),
            primer_type=self.primer_type.currentText(),
            stemming_material=self.stem_material.currentText(),
        )

    def set_rule(self, rule: ChargeRule) -> None:
        widgets = (self.column_exp, self.bottom_exp, self.use_bottom, self.stem_material,
                   self.primer_type, self.coupling, self.bottom_len, self.n_decks,
                   self.inter_stem, self.air_deck, self.stemming, self.primers)
        for w in widgets:
            w.blockSignals(True)
        self.column_exp.setCurrentText(rule.column_explosive)
        self.use_bottom.setCurrentText("Si" if rule.bottom_explosive else "No")
        if rule.bottom_explosive:
            self.bottom_exp.setCurrentText(rule.bottom_explosive)
        self.bottom_len.setValue(rule.bottom_charge_m)
        self.stemming.setValue(rule.stemming_m)
        self.coupling.setValue(rule.coupling)
        self.n_decks.setValue(rule.n_decks)
        self.inter_stem.setValue(rule.inter_deck_stem_m)
        self.air_deck.setValue(rule.air_deck_m)
        self.primers.setValue(rule.primer_per_deck)
        self.primer_type.setCurrentText(rule.primer_type)
        self.stem_material.setCurrentText(rule.stemming_material)
        for w in widgets:
            w.blockSignals(False)

    def set_reference_hole(self, hole: Optional[Hole]) -> None:
        """Fija el taladro sobre el que se dibuja la vista previa."""
        self._reference = hole
        self.refresh_preview()

    def refresh_preview(self) -> None:
        """Recalcula la columna del taladro tipo y actualiza el resumen."""
        hole = self._reference
        if hole is None:
            self.preview.update_data(None)
            for lbl in (self.out_charge, self.out_linear, self.out_length,
                        self.out_energy, self.out_pressure):
                lbl.setText("—")
            return

        rule = self.rule()
        hole.decks = build_column(hole, rule)
        refresh_hole_charge(hole)

        exp = exdb.get(rule.column_explosive)
        lin = hole.charge_kg / max(hole.charge_length_m, 1e-6)
        self.out_charge.setText(f"{hole.charge_kg:,.1f} kg")
        self.out_linear.setText(f"{lin:,.2f} kg/m")
        self.out_length.setText(f"{hole.charge_length_m:.2f} m de {hole.length_m:.2f} m")
        self.out_energy.setText(f"{hole.energy_mj:,.0f} MJ")
        self.out_pressure.setText(f"{exp.borehole_pressure_gpa(rule.coupling) * 1000:,.0f} MPa")

        self.preview.update_data(hole, linear_charge_profile(hole))

    # -- internos ----------------------------------------------------------
    def _on_change(self, *_):
        has_bottom = self.use_bottom.currentText() == "Si"
        self.bottom_exp.setEnabled(has_bottom)
        self.bottom_len.setEnabled(has_bottom)
        self.inter_stem.setEnabled(self.n_decks.value() > 1)
        self.refresh_preview()
        self.changed.emit()


def _value(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    lbl.setStyleSheet(f"color:{C['text']}; font-weight:600;")
    return lbl
