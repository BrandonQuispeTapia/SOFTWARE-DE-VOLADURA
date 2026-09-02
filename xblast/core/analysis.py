"""Orquestador del analisis completo de una voladura.

Encadena geometria -> carguio -> burden real -> secuencia -> fragmentacion ->
vibracion -> onda aerea -> proyeccion -> energia -> costos, y consolida los
indicadores y hallazgos en un unico objeto consumible por la interfaz y por los
reportes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from . import airblast, burden, charging, costs, energy, explosives as exdb
from . import fragmentation as frag
from . import pattern as pattern_mod
from . import timing as timing_mod
from . import vibration as vib
from .models import BlastDesign, Hole


@dataclass
class BlastAnalysis:
    """Resultado consolidado del analisis de un diseno."""

    design: BlastDesign
    kpis: Dict[str, Any] = field(default_factory=dict)
    fragmentation: Optional[frag.FragmentationResult] = None
    per_hole_frag: List[frag.FragmentationResult] = field(default_factory=list)
    burden_stats: Dict[str, float] = field(default_factory=dict)
    timing_stats: Dict[str, Any] = field(default_factory=dict)
    cooperation: Dict[str, Any] = field(default_factory=dict)
    overlap: Dict[str, float] = field(default_factory=dict)
    vibration: Dict[str, Any] = field(default_factory=dict)
    vibration_compliance: Dict[str, Any] = field(default_factory=dict)
    near_field: Dict[str, float] = field(default_factory=dict)
    airblast: Dict[str, float] = field(default_factory=dict)
    flyrock: Dict[str, Any] = field(default_factory=dict)
    energy_field: Optional[energy.EnergyField] = None
    energy_coverage: Dict[str, float] = field(default_factory=dict)
    cost: Optional[costs.CostBreakdown] = None
    findings: List[Dict[str, str]] = field(default_factory=list)

    # -- utilidades ---------------------------------------------------------
    @property
    def errors(self) -> List[Dict[str, str]]:
        return [f for f in self.findings if f["level"] == "error"]

    @property
    def warnings(self) -> List[Dict[str, str]]:
        return [f for f in self.findings if f["level"] == "warn"]

    @property
    def score(self) -> int:
        """Puntaje de calidad del diseno 0-100 penalizado por hallazgos."""
        return int(max(0, 100 - 14 * len(self.errors) - 5 * len(self.warnings)))

    def kpi(self, key: str, default: Any = 0.0) -> Any:
        return self.kpis.get(key, default)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def analyze(
    design: BlastDesign,
    compute_energy: bool = True,
    target_p80_cm: float = 50.0,
    drilling_accuracy_m: float = 0.25,
    energy_cell_size: float = 1.2,
) -> BlastAnalysis:
    """Ejecuta el analisis completo del diseno y devuelve el paquete de resultados."""
    holes = design.holes
    res = BlastAnalysis(design=design)
    if not holes:
        return res

    p = design.pattern
    rock = design.rock
    cons = design.constraints

    # 1) Carga -------------------------------------------------------------
    for h in holes:
        charging.refresh_hole_charge(h)

    # 2) Geometria real ----------------------------------------------------
    free_face = design.free_face
    if free_face is None:
        free_face = pattern_mod.free_face_from_pattern(p)
    burden.compute_true_burden(holes, free_face, p.burden_m, p.spacing_m,
                               p.face_azimuth_deg)
    burden.assign_volumes(holes, p.area_per_hole_m2)

    # 3) Secuencia ---------------------------------------------------------
    timing_mod.assign_delays(holes, design.timing, p.face_azimuth_deg)
    burden.compute_relief_burden(holes)
    res.timing_stats = timing_mod.relief_time_analysis(holes, design.timing)
    res.cooperation = timing_mod.cooperating_charge(holes, design.timing.cooperation_window_ms)
    res.overlap = timing_mod.overlap_probability(holes, design.timing)

    # 4) Factores por taladro ---------------------------------------------
    for h in holes:
        h.powder_factor = h.charge_kg / max(h.volume_m3, 1e-6)
        tonnes = max(h.volume_m3 * rock.density_t_m3, 1e-6)
        h.energy_factor = h.energy_mj / tonnes

    # 5) Fragmentacion -----------------------------------------------------
    rws = exdb.get(design.column_explosive).rws
    relief_ms_m = float(res.timing_stats.get("hole_relief_ms_m", 4.0))
    staggered = p.pattern.startswith("Tres")
    global_frag, per_hole = frag.predict_blast(
        holes, rock, rws, relief_ms_m, drilling_accuracy_m,
        staggered=staggered, oversize_cm=design.costs.oversize_threshold_cm)
    res.fragmentation = global_frag
    res.per_hole_frag = per_hole

    # 6) Burden ------------------------------------------------------------
    res.burden_stats = burden.burden_statistics(holes)

    # 7) Vibraciones -------------------------------------------------------
    receptor = np.array([cons.receptor_easting, cons.receptor_northing, cons.receptor_elev], float)
    res.vibration = vib.superpose(holes, receptor, cons)
    res.vibration_compliance = vib.compliance(
        float(res.vibration["ppv_max_mm_s"]), float(res.vibration["freq_hz"]), cons)

    ref = max(holes, key=lambda h: h.charge_kg)
    lin = ref.charge_kg / max(ref.charge_length_m, 1e-6)
    crit = vib.critical_ppv(rock.ucs_mpa, rock.young_gpa, rock.p_wave_m_s)
    res.near_field = {
        **crit,
        "ppv_1m_mm_s": vib.ppv_holmberg_persson(cons.k_site, cons.alpha_site, cons.beta_site,
                                                lin, ref.charge_length_m, 1.0),
        "damage_radius_m": vib.damage_radius(cons.k_site, cons.alpha_site, cons.beta_site,
                                             lin, ref.charge_length_m,
                                             crit["ppv_fisuras_mm_s"]),
        "linear_charge_kg_m": lin,
    }

    dist_receptor = float(np.linalg.norm(
        np.array([[h.easting, h.northing, h.collar_z] for h in holes]) - receptor, axis=1).min())

    # 8) Onda aerea y flyrock ---------------------------------------------
    mic = float(res.cooperation.get("mic_kg", 0.0))
    stem_avg = float(np.mean([h.collar_stemming_m for h in holes]))
    res.airblast = airblast.predict_airblast(
        dist_receptor, mic, stem_avg, p.diameter_mm,
        exdb.stemming_factor(design.stemming_material))
    res.flyrock = airblast.predict_flyrock(holes)

    # 9) Campo de energia --------------------------------------------------
    target_e = energy.target_energy_mj_m3(
        design.powder_factor, exdb.get(design.column_explosive).energy_mj_kg)
    if compute_energy:
        res.energy_field = energy.compute_energy_field(holes, cell_size=energy_cell_size)
        if res.energy_field is not None:
            res.energy_coverage = res.energy_field.coverage(target_e)

    # 10) Costos -----------------------------------------------------------
    res.cost = costs.compute_costs(
        holes, design.costs, rock.density_t_m3,
        global_frag.x50_cm, global_frag.oversize_pct, design.primer_type)

    # 11) KPIs -------------------------------------------------------------
    res.kpis = _build_kpis(design, res, dist_receptor, target_e)

    # 12) Hallazgos --------------------------------------------------------
    findings: List[Dict[str, str]] = []
    findings += pattern_mod.audit_geometry(p)
    findings += burden.audit_burden(holes, p.burden_m)
    findings += charging.audit_charge(holes[0], design.stemming_material)
    findings += timing_mod.audit_timing(holes, design.timing)
    findings += frag.audit_fragmentation(global_frag, target_p80_cm,
                                         design.costs.oversize_threshold_cm)
    findings += vib.audit_vibration(res.vibration, cons, mic, dist_receptor)
    findings += airblast.audit_airblast(res.airblast, cons.airblast_limit_db)
    findings += airblast.audit_flyrock(res.flyrock, cons.exclusion_radius_m)
    findings += energy.audit_energy(res.energy_field, target_e)
    res.findings = findings

    return res


def _build_kpis(design: BlastDesign, res: BlastAnalysis,
                dist_receptor: float, target_energy: float) -> Dict[str, Any]:
    """Consolida los indicadores presentados en el tablero y los reportes."""
    holes = design.holes
    p = design.pattern
    f = res.fragmentation
    c = res.cost

    volume = design.total_volume_m3
    tonnes = design.total_tonnes
    charge = design.total_charge_kg
    drilled = design.total_drilled_m
    energy_mj = sum(h.energy_mj for h in holes)

    return {
        # produccion
        "n_holes": len(holes),
        "volume_m3": volume,
        "tonnes": tonnes,
        "drilled_m": drilled,
        "charge_kg": charge,
        "energy_mj": energy_mj,
        "powder_factor": charge / max(volume, 1e-6),
        "specific_charge_kg_t": charge / max(tonnes, 1e-6),
        "drill_factor_m_m3": drilled / max(volume, 1e-6),
        "energy_factor_mj_t": energy_mj / max(tonnes, 1e-6),
        "tonnes_per_hole": tonnes / max(len(holes), 1),
        # geometria
        "burden_m": p.burden_m,
        "spacing_m": p.spacing_m,
        "diameter_mm": p.diameter_mm,
        "bench_height_m": p.bench_height_m,
        "stiffness_ratio": p.stiffness_ratio,
        "s_b_ratio": p.s_b_ratio,
        "burden_cv_pct": res.burden_stats.get("burden_cv_pct", 0.0),
        # fragmentacion
        "x50_cm": f.x50_cm if f else 0.0,
        "p80_cm": f.p80_cm if f else 0.0,
        "p20_cm": f.p20_cm if f else 0.0,
        "uniformity_n": f.n if f else 0.0,
        "fines_pct": f.fines_pct if f else 0.0,
        "oversize_pct": f.oversize_pct if f else 0.0,
        # secuencia
        "total_duration_ms": res.timing_stats.get("total_duration_ms", 0.0),
        "hole_relief_ms_m": res.timing_stats.get("hole_relief_ms_m", 0.0),
        "row_relief_ms_m": res.timing_stats.get("row_relief_ms_m", 0.0),
        "mic_kg": res.cooperation.get("mic_kg", 0.0),
        "p_overlap_pct": res.overlap.get("p_overlap_pct", 0.0),
        # ambiental
        "ppv_mm_s": res.vibration.get("ppv_max_mm_s", 0.0),
        "ppv_limit_mm_s": design.constraints.ppv_limit_mm_s,
        "ppv_utilization_pct": res.vibration_compliance.get("utilization_pct", 0.0),
        "airblast_db": res.airblast.get("airblast_db", 0.0),
        "flyrock_m": res.flyrock.get("max_throw_m", 0.0),
        "safe_distance_m": res.flyrock.get("safe_distance_m", 0.0),
        "receptor_distance_m": dist_receptor,
        "damage_radius_m": res.near_field.get("damage_radius_m", 0.0),
        # energia
        "target_energy_mj_m3": target_energy,
        "energy_in_range_pct": res.energy_coverage.get("in_range_pct", 0.0),
        # costos
        "cost_db_usd": c.db_usd if c else 0.0,
        "cost_db_usd_t": c.db_usd_t if c else 0.0,
        "cost_total_usd": c.total_usd if c else 0.0,
        "cost_total_usd_t": c.total_usd_t if c else 0.0,
        "cost_drilling_usd": c.drilling_usd if c else 0.0,
        "cost_explosive_usd": c.explosive_usd if c else 0.0,
    }
