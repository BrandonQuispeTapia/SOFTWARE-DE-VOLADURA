"""Panel de diseno geometrico, macizo rocoso y entorno.

Reune los parametros que definen la malla, la caracterizacion geomecanica que
alimenta el factor de roca y las restricciones ambientales del sitio.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QTabWidget, QWidget

from ...core import explosives as exdb
from ...core import pattern as pattern_mod
from ...core.models import (
    HoleType, PatternParams, PatternType, RockMass, SiteConstraints,
)
from .. import widgets as W
from ..theme import C


class DesignPanel(QTabWidget):
    """Pestanas de geometria, macizo y entorno."""

    changed = Signal()
    generate_requested = Signal()

    def __init__(self):
        super().__init__()
        self.geometry = GeometryTab()
        self.rock = RockTab()
        self.site = SiteTab()

        self.addTab(self.geometry, "Geometria")
        self.addTab(self.rock, "Macizo")
        self.addTab(self.site, "Entorno")

        # La geometria necesita el macizo vigente para el dimensionamiento
        # automatico; se lo entrega el panel, sin buscar por el arbol de widgets.
        self.geometry.rock_provider = self.rock.rock

        for tab in (self.geometry, self.rock, self.site):
            tab.changed.connect(self.changed)
        self.geometry.generate_requested.connect(self.generate_requested)


# ---------------------------------------------------------------------------
# Geometria
# ---------------------------------------------------------------------------


class GeometryTab(W.ScrollPanel):
    """Parametros de la malla y ayuda de dimensionamiento automatico."""

    changed = Signal()
    generate_requested = Signal()

    #: Devuelve el macizo vigente; lo inyecta :class:`DesignPanel`.
    rock_provider = None

    def __init__(self):
        super().__init__()
        p = PatternParams()

        drill = W.Section(
            "Perforacion",
            "Diametro y geometria del taladro. La longitud se deduce de la altura "
            "de banco, la inclinacion y la subperforacion.")
        self.diameter = drill.row("Diametro", W.spin(50, 450, p.diameter_mm, 1, "mm", 0),
                                  "Diametro nominal de la broca.")
        self.bench = drill.row("Altura de banco", W.spin(2, 60, p.bench_height_m, 0.5, "m"))
        self.subdrill = drill.row("Subperforacion", W.spin(0, 6, p.subdrill_m, 0.1, "m"),
                                  "Perforacion bajo el piso; 0.2-0.4 B evita lomos.")
        self.inclination = drill.row("Inclinacion", W.spin(0, 35, p.inclination_deg, 1, "° desde vertical", 0),
                                     "Taladros inclinados mejoran la rotura del pie y reducen sobre-rotura.")
        self.length = drill.row("Longitud resultante", _readonly("—"))
        self.add(drill)

        mesh = W.Section("Malla", "Distribucion de los taladros en planta.")
        self.pattern_type = mesh.row("Disposicion", W.combo(
            [t.value for t in PatternType], p.pattern))
        self.burden = mesh.row("Burden (B)", W.spin(0.5, 20, p.burden_m, 0.1, "m"),
                               "Distancia perpendicular del taladro a la cara libre.")
        self.spacing = mesh.row("Espaciamiento (S)", W.spin(0.5, 25, p.spacing_m, 0.1, "m"))
        self.rows = mesh.row("Filas", W.int_spin(1, 60, p.rows))
        self.cols = mesh.row("Columnas", W.int_spin(1, 100, p.cols))
        self.azimuth = mesh.row("Azimut de salida", W.spin(0, 360, p.face_azimuth_deg, 5, "°", 0),
                                "Direccion hacia la cara libre; ordena la secuencia y el burden real.")
        self.hole_type = mesh.row("Tipo de taladro", W.combo([t.value for t in HoleType]))
        self.add(mesh)

        origin = W.Section("Origen", "Coordenada del primer collar de la malla.")
        self.origin_x = origin.row("Este", W.spin(-1e7, 1e7, p.origin_x, 1, "m", 2))
        self.origin_y = origin.row("Norte", W.spin(-1e7, 1e7, p.origin_y, 1, "m", 2))
        self.origin_z = origin.row("Cota", W.spin(-5000, 9000, p.origin_z, 1, "m", 2))
        self.add(origin)

        ratios = W.Section("Verificacion", "Relaciones que gobiernan la calidad del diseno.")
        self.ratio_hb = ratios.row("Rigidez H/B", _readonly("—"))
        self.ratio_sb = ratios.row("Relacion S/B", _readonly("—"))
        self.ratio_tb = ratios.row("Relacion T/B", _readonly("—"))
        self.ratio_bd = ratios.row("Relacion B/D", _readonly("—"))
        self.add(ratios)

        auto = W.Section(
            "Dimensionamiento automatico",
            "Promedia Konya-Walter, Langefors-Kihlstrom, Ash y Pearse, y corrige "
            "por relacion de rigidez.")
        self.btn_auto = W.button("Calcular B, S, taco y subperforacion", "", "optimize")
        self.btn_auto.clicked.connect(self._auto_size)
        auto.add(self.btn_auto)
        self.auto_info = W.caption("")
        auto.add(self.auto_info)
        self.add(auto)

        self.btn_generate = W.button("Generar malla", "primary", "pattern")
        self.btn_generate.setMinimumHeight(32)
        self.btn_generate.clicked.connect(self.generate_requested)
        self.add(self.btn_generate)
        self.finish()

        for w in (self.diameter, self.bench, self.subdrill, self.inclination,
                  self.burden, self.spacing, self.rows, self.cols, self.azimuth,
                  self.origin_x, self.origin_y, self.origin_z):
            w.valueChanged.connect(self._on_change)
        for w in (self.pattern_type, self.hole_type):
            w.currentTextChanged.connect(self._on_change)

        self._refresh_derived()

    # -- API ---------------------------------------------------------------
    def params(self) -> PatternParams:
        return PatternParams(
            burden_m=self.burden.value(),
            spacing_m=self.spacing.value(),
            diameter_mm=self.diameter.value(),
            bench_height_m=self.bench.value(),
            subdrill_m=self.subdrill.value(),
            stemming_m=self._stemming,
            inclination_deg=self.inclination.value(),
            face_azimuth_deg=self.azimuth.value(),
            rows=self.rows.value(),
            cols=self.cols.value(),
            pattern=self.pattern_type.currentText(),
            origin_x=self.origin_x.value(),
            origin_y=self.origin_y.value(),
            origin_z=self.origin_z.value(),
        )

    def set_params(self, p: PatternParams) -> None:
        for w in (self.diameter, self.bench, self.subdrill, self.inclination,
                  self.burden, self.spacing, self.rows, self.cols, self.azimuth,
                  self.origin_x, self.origin_y, self.origin_z,
                  self.pattern_type, self.hole_type):
            w.blockSignals(True)
        self.diameter.setValue(p.diameter_mm)
        self.bench.setValue(p.bench_height_m)
        self.subdrill.setValue(p.subdrill_m)
        self.inclination.setValue(p.inclination_deg)
        self.burden.setValue(p.burden_m)
        self.spacing.setValue(p.spacing_m)
        self.rows.setValue(p.rows)
        self.cols.setValue(p.cols)
        self.azimuth.setValue(p.face_azimuth_deg)
        self.origin_x.setValue(p.origin_x)
        self.origin_y.setValue(p.origin_y)
        self.origin_z.setValue(p.origin_z)
        self.pattern_type.setCurrentText(p.pattern)
        for w in (self.diameter, self.bench, self.subdrill, self.inclination,
                  self.burden, self.spacing, self.rows, self.cols, self.azimuth,
                  self.origin_x, self.origin_y, self.origin_z,
                  self.pattern_type, self.hole_type):
            w.blockSignals(False)
        self._stemming = p.stemming_m
        self._refresh_derived()

    #: taco vigente, sincronizado desde el panel de carga
    _stemming: float = PatternParams().stemming_m

    def set_stemming(self, value: float) -> None:
        self._stemming = value
        self._refresh_derived()

    # -- internos ----------------------------------------------------------
    def _on_change(self, *_):
        self._refresh_derived()
        self.changed.emit()

    def _refresh_derived(self) -> None:
        p = self.params()
        self.length.setText(f"{p.hole_length_m:.2f} m")
        _set_ratio(self.ratio_hb, p.stiffness_ratio, 2.0, 3.0, 6.0)
        _set_ratio(self.ratio_sb, p.s_b_ratio, 1.0, 1.05, 1.8)
        _set_ratio(self.ratio_tb, self._stemming / max(p.burden_m, 1e-6), 0.5, 0.55, 1.2)
        _set_ratio(self.ratio_bd, p.burden_m / max(p.diameter_mm / 1000.0, 1e-6), 20, 22, 40, "{:.0f}")

    def _auto_size(self) -> None:
        rock = self.rock_provider() if self.rock_provider else RockMass()
        rec = pattern_mod.recommend_geometry(
            self.diameter.value(), rock, "ANFO", self.bench.value(),
            self.pattern_type.currentText())

        self.burden.setValue(rec["burden_m"])
        self.spacing.setValue(rec["spacing_m"])
        self.subdrill.setValue(rec["subdrill_m"])
        self._stemming = rec["stemming_m"]

        detail = "  ·  ".join(f"{k}: {v:.2f} m" for k, v in rec["candidates"].items())
        self.auto_info.setText(
            f"Factor de roca A = {rec['rock_factor_a']:.1f} "
            f"(indice de volabilidad {rec['blastability_index']:.0f}). "
            f"Taco recomendado {rec['stemming_m']:.2f} m.\n{detail}")
        self._refresh_derived()
        self.changed.emit()


# ---------------------------------------------------------------------------
# Macizo rocoso
# ---------------------------------------------------------------------------


class RockTab(W.ScrollPanel):
    """Caracterizacion geomecanica que alimenta el factor de roca de Kuz-Ram."""

    changed = Signal()

    _RMD = {"Pulverulento / friable": 10.0, "Diaclasado en bloques": 20.0,
            "Diaclasado vertical": 25.0, "Masivo": 50.0}
    _JPS = {"Muy junteado (< 0.1 m)": 10.0, "Junteado (0.1 - 0.3 m)": 20.0,
            "Espaciado (0.3 - 1.0 m)": 25.0, "Muy espaciado (> 1.0 m)": 50.0}
    _JPA = {"Buza hacia fuera de la cara": 40.0, "Rumbo perpendicular a la cara": 30.0,
            "Buza hacia dentro de la cara": 20.0}

    def __init__(self):
        super().__init__()
        r = RockMass()

        ident = W.Section("Identificacion")
        self.name = ident.row("Litologia", W.combo(
            ["Andesita competente", "Caliza", "Cuarcita", "Diorita", "Granito",
             "Riolita", "Skarn", "Toba volcanica", "Marga", "Mineral oxidado"],
            r.name))
        self.name.setEditable(True)
        self.add(ident)

        props = W.Section("Propiedades fisicas")
        self.density = props.row("Densidad", W.spin(1.2, 5.0, r.density_t_m3, 0.05, "t/m3"))
        self.ucs = props.row("Resistencia a compresion", W.spin(5, 400, r.ucs_mpa, 5, "MPa", 0))
        self.young = props.row("Modulo de Young", W.spin(1, 150, r.young_gpa, 1, "GPa", 0))
        self.poisson = props.row("Coeficiente de Poisson", W.spin(0.05, 0.45, r.poisson, 0.01, "", 2))
        self.vp = props.row("Velocidad de onda P", W.spin(500, 8000, r.p_wave_m_s, 100, "m/s", 0))
        self.gsi = props.row("GSI", W.int_spin(5, 100, r.gsi))
        self.add(props)

        struct = W.Section(
            "Estructura (indice de Lilly)",
            "Describe el macizo tal como se ve en la cara; determina el factor de "
            "roca A que gobierna la fragmentacion.")
        self.rmd = struct.row("Descripcion del macizo", W.combo(list(self._RMD), "Diaclasado vertical"))
        self.jps = struct.row("Espaciamiento de juntas", W.combo(list(self._JPS), "Espaciado (0.3 - 1.0 m)"))
        self.jpa = struct.row("Orientacion de juntas", W.combo(list(self._JPA), "Rumbo perpendicular a la cara"))
        self.add(struct)

        derived = W.Section("Resultado")
        self.bi = derived.row("Indice de volabilidad", _readonly("—"))
        self.factor_a = derived.row("Factor de roca A", _readonly("—"))
        self.classification = derived.row("Clasificacion", _readonly("—"))
        self.add(derived)
        self.finish()

        for w in (self.density, self.ucs, self.young, self.poisson, self.vp, self.gsi):
            w.valueChanged.connect(self._on_change)
        for w in (self.name, self.rmd, self.jps, self.jpa):
            w.currentTextChanged.connect(self._on_change)
        self._refresh()

    def rock(self) -> RockMass:
        return RockMass(
            name=self.name.currentText(),
            density_t_m3=self.density.value(),
            ucs_mpa=self.ucs.value(),
            young_gpa=self.young.value(),
            poisson=self.poisson.value(),
            gsi=self.gsi.value(),
            p_wave_m_s=self.vp.value(),
            rmd=self._RMD[self.rmd.currentText()],
            jps=self._JPS[self.jps.currentText()],
            jpa=self._JPA[self.jpa.currentText()],
        )

    def set_rock(self, r: RockMass) -> None:
        for w in (self.density, self.ucs, self.young, self.poisson, self.vp, self.gsi, self.name):
            w.blockSignals(True)
        self.name.setCurrentText(r.name)
        self.density.setValue(r.density_t_m3)
        self.ucs.setValue(r.ucs_mpa)
        self.young.setValue(r.young_gpa)
        self.poisson.setValue(r.poisson)
        self.vp.setValue(r.p_wave_m_s)
        self.gsi.setValue(r.gsi)
        for w in (self.density, self.ucs, self.young, self.poisson, self.vp, self.gsi, self.name):
            w.blockSignals(False)
        self._refresh()

    def _on_change(self, *_):
        self._refresh()
        self.changed.emit()

    def _refresh(self) -> None:
        r = self.rock()
        self.bi.setText(f"{r.blastability_index:.1f}")
        self.factor_a.setText(f"{r.rock_factor_a:.2f}")
        self.classification.setText(r.classification)


# ---------------------------------------------------------------------------
# Entorno
# ---------------------------------------------------------------------------


class SiteTab(W.ScrollPanel):
    """Receptor sensible, limites normativos y constantes de sitio."""

    changed = Signal()

    def __init__(self):
        super().__init__()
        c = SiteConstraints()

        rec = W.Section(
            "Receptor sensible",
            "Punto de control donde se evalua el cumplimiento de vibracion y onda aerea.")
        self.rx = rec.row("Este", W.spin(-1e7, 1e7, c.receptor_easting, 10, "m", 1))
        self.ry = rec.row("Norte", W.spin(-1e7, 1e7, c.receptor_northing, 10, "m", 1))
        self.rz = rec.row("Cota", W.spin(-5000, 9000, c.receptor_elev, 1, "m", 1))
        self.add(rec)

        lim = W.Section("Limites", "Umbrales que el analisis usa para declarar incumplimiento.")
        self.ppv_limit = lim.row("PPV admisible", W.spin(0.5, 200, c.ppv_limit_mm_s, 0.1, "mm/s"),
                                 "12.7 mm/s corresponde a vivienda con acabado de yeso segun USBM RI8507.")
        self.airblast_limit = lim.row("Onda aerea admisible", W.spin(90, 150, c.airblast_limit_db, 1, "dBL", 0))
        self.exclusion = lim.row("Radio de exclusion", W.spin(10, 2000, c.exclusion_radius_m, 10, "m", 0))
        self.add(lim)

        site = W.Section(
            "Constantes de sitio",
            "Parametros de la ley de atenuacion PPV = K · SD^-beta, calibrados con "
            "monitoreo de campo.")
        self.k_site = site.row("K", W.spin(50, 5000, c.k_site, 10, "", 0))
        self.beta = site.row("beta", W.spin(0.8, 3.0, c.beta_site, 0.05, "", 2))
        self.alpha = site.row("alpha (campo cercano)", W.spin(0.3, 1.2, c.alpha_site, 0.05, "", 2))
        self.add(site)
        self.finish()

        for w in (self.rx, self.ry, self.rz, self.ppv_limit, self.airblast_limit,
                  self.exclusion, self.k_site, self.beta, self.alpha):
            w.valueChanged.connect(lambda *_: self.changed.emit())

    def constraints(self) -> SiteConstraints:
        return SiteConstraints(
            receptor_easting=self.rx.value(),
            receptor_northing=self.ry.value(),
            receptor_elev=self.rz.value(),
            ppv_limit_mm_s=self.ppv_limit.value(),
            airblast_limit_db=self.airblast_limit.value(),
            exclusion_radius_m=self.exclusion.value(),
            k_site=self.k_site.value(),
            beta_site=self.beta.value(),
            alpha_site=self.alpha.value(),
        )

    def set_constraints(self, c: SiteConstraints) -> None:
        for w, v in ((self.rx, c.receptor_easting), (self.ry, c.receptor_northing),
                     (self.rz, c.receptor_elev), (self.ppv_limit, c.ppv_limit_mm_s),
                     (self.airblast_limit, c.airblast_limit_db),
                     (self.exclusion, c.exclusion_radius_m), (self.k_site, c.k_site),
                     (self.beta, c.beta_site), (self.alpha, c.alpha_site)):
            w.blockSignals(True)
            w.setValue(v)
            w.blockSignals(False)


# ---------------------------------------------------------------------------
# Utilidades locales
# ---------------------------------------------------------------------------


def _readonly(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setProperty("role", "mono")
    lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    lbl.setStyleSheet(f"color:{C['text']}; font-weight:600;")
    return lbl


def _set_ratio(label: QLabel, value: float, hard_min: float, soft_min: float,
               soft_max: float, fmt: str = "{:.2f}") -> None:
    """Escribe un ratio y lo tine segun este dentro del rango recomendado."""
    if value < hard_min:
        color = C["error"]
    elif value < soft_min or value > soft_max:
        color = C["warn"]
    else:
        color = C["ok"]
    label.setText(fmt.format(value))
    label.setStyleSheet(f"color:{color}; font-weight:600;")
