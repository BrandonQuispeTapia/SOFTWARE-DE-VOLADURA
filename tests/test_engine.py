"""Pruebas del motor de ingenieria.

Verifican que las formulas devuelvan magnitudes coherentes con la practica de
perforacion y voladura y que el encadenamiento completo produzca un resultado
consistente, sin necesitar interfaz grafica.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from xblast.core import burden, charging, explosives as exdb
from xblast.core import fragmentation as frag
from xblast.core import pattern as pattern_mod
from xblast.core import timing as timing_mod
from xblast.core import airblast, vibration
from xblast.core.analysis import analyze
from xblast.core.charging import ChargeRule
from xblast.core.models import (
    BlastDesign, Deck, DeckKind, PatternParams, RockMass, TimingParams,
)


@pytest.fixture
def design() -> BlastDesign:
    d = BlastDesign(name="Prueba")
    d.holes = pattern_mod.generate_pattern(d.pattern)
    charging.apply_charge(d.holes, ChargeRule(stemming_m=d.pattern.stemming_m))
    return d


# ---------------------------------------------------------------------------
# Geometria
# ---------------------------------------------------------------------------


def test_pattern_dimensions(design: BlastDesign):
    p = design.pattern
    assert len(design.holes) == p.rows * p.cols
    assert all(h.diameter_mm == p.diameter_mm for h in design.holes)


def test_hole_axis_and_toe():
    p = PatternParams(inclination_deg=15.0, face_azimuth_deg=180.0, rows=1, cols=1)
    hole = pattern_mod.generate_pattern(p)[0]
    # El eje apunta hacia abajo y la caida vertical respeta la inclinacion.
    assert hole.axis[2] < 0
    drop = hole.collar_z - hole.toe_z
    assert drop == pytest.approx(hole.length_m * math.cos(math.radians(15.0)), rel=1e-6)
    assert np.linalg.norm(hole.axis) == pytest.approx(1.0)


def test_hole_length_grows_with_inclination():
    vertical = PatternParams(inclination_deg=0.0)
    inclined = PatternParams(inclination_deg=20.0)
    assert inclined.hole_length_m > vertical.hole_length_m


def test_staggered_pattern_offsets_alternate_rows():
    p = PatternParams(rows=2, cols=3, pattern="Tresbolillo")
    holes = pattern_mod.generate_pattern(p)
    row0 = [h for h in holes if h.row == 0]
    row1 = [h for h in holes if h.row == 1]
    d = np.linalg.norm(np.array([row1[0].easting, row1[0].northing])
                       - np.array([row0[0].easting, row0[0].northing]))
    assert d > p.burden_m  # desplazado media malla, no alineado


# ---------------------------------------------------------------------------
# Macizo rocoso
# ---------------------------------------------------------------------------


def test_rock_factor_within_kuz_ram_range():
    for ucs, e in ((40, 15), (120, 45), (250, 90)):
        rock = RockMass(ucs_mpa=ucs, young_gpa=e)
        assert 0.8 <= rock.rock_factor_a <= 22.0


def test_harder_rock_gives_higher_rock_factor():
    soft = RockMass(ucs_mpa=40, young_gpa=15, rmd=10, jps=10)
    hard = RockMass(ucs_mpa=250, young_gpa=90, rmd=50, jps=50)
    assert hard.rock_factor_a > soft.rock_factor_a


# ---------------------------------------------------------------------------
# Carga
# ---------------------------------------------------------------------------


def test_charge_column_fits_hole(design: BlastDesign):
    for h in design.holes:
        total = sum(d.length_m for d in h.decks)
        assert total == pytest.approx(h.length_m, abs=0.02)


def test_stemming_is_at_the_collar(design: BlastDesign):
    hole = design.holes[0]
    assert hole.decks[-1].kind is DeckKind.TACO
    assert hole.collar_stemming_m == pytest.approx(design.pattern.stemming_m, abs=0.05)


def test_linear_density_matches_geometry():
    anfo = exdb.get("ANFO")
    lin = anfo.linear_density_kg_m(152.0)
    expected = math.pi * 0.152 ** 2 / 4 * anfo.density_kg_m3
    assert lin == pytest.approx(expected, rel=1e-9)


def test_decoupling_reduces_charge_and_pressure():
    anfo = exdb.get("ANFO")
    assert anfo.linear_density_kg_m(152, 0.5) < anfo.linear_density_kg_m(152, 1.0)
    assert anfo.borehole_pressure_gpa(0.5) < anfo.borehole_pressure_gpa(1.0)


def test_multiple_decks_produce_separate_charges():
    p = PatternParams(rows=1, cols=1)
    hole = pattern_mod.generate_pattern(p)[0]
    hole.decks = charging.build_column(hole, ChargeRule(n_decks=2, inter_deck_stem_m=1.5))
    charging.refresh_hole_charge(hole)
    assert hole.is_decked
    assert sum(1 for d in hole.decks if d.kind is DeckKind.TACO) >= 2


# ---------------------------------------------------------------------------
# Burden y volumen
# ---------------------------------------------------------------------------


def test_true_burden_close_to_nominal(design: BlastDesign):
    face = pattern_mod.free_face_from_pattern(design.pattern)
    burden.compute_true_burden(design.holes, face, design.pattern.burden_m,
                               design.pattern.spacing_m, design.pattern.face_azimuth_deg)
    stats = burden.burden_statistics(design.holes)
    assert stats["burden_cv_pct"] < 15.0
    assert stats["burden_mean_m"] == pytest.approx(design.pattern.burden_m, rel=0.2)


def test_volume_sum_matches_pattern_area(design: BlastDesign):
    burden.assign_volumes(design.holes, design.pattern.area_per_hole_m2)
    expected = (len(design.holes) * design.pattern.area_per_hole_m2
                * design.pattern.bench_height_m)
    assert design.total_volume_m3 == pytest.approx(expected, rel=0.35)


# ---------------------------------------------------------------------------
# Secuencia
# ---------------------------------------------------------------------------


def test_delays_start_at_zero_and_increase(design: BlastDesign):
    timing_mod.assign_delays(design.holes, design.timing, design.pattern.face_azimuth_deg)
    delays = sorted(h.delay_ms for h in design.holes)
    assert delays[0] == pytest.approx(design.timing.in_hole_delay_ms, abs=0.2)
    assert delays[-1] > delays[0]


def test_first_row_fires_before_last(design: BlastDesign):
    timing_mod.assign_delays(design.holes, design.timing, design.pattern.face_azimuth_deg)
    first = np.mean([h.delay_ms for h in design.holes if h.row == 0])
    last = np.mean([h.delay_ms for h in design.holes if h.row == design.pattern.rows - 1])
    assert first < last


def test_cooperating_charge_never_exceeds_total(design: BlastDesign):
    timing_mod.assign_delays(design.holes, design.timing)
    coop = timing_mod.cooperating_charge(design.holes, 8.0)
    assert 0 < coop["mic_kg"] <= design.total_charge_kg + 1e-6


def test_electronic_detonator_has_less_scatter_than_nonel(design: BlastDesign):
    """La dispersion la marca el modelo de detonador, no una etiqueta generica."""
    params = TimingParams(mode="Vector de direccion")
    vector = timing_mod.default_vector(design.holes)
    vector.brs_ms_m = 2.0
    timing_mod.assign_delays(design.holes, params, 180.0, vector)

    electronico = timing_mod.overlap_probability(
        design.holes, TimingParams(detonator="i-kon II"))
    nonel = timing_mod.overlap_probability(
        design.holes, TimingParams(detonator="NONEL LP (fondo)"))
    assert electronico["scatter_cv_pct"] < nonel["scatter_cv_pct"]
    assert electronico["p_out_of_sequence_pct"] < nonel["p_out_of_sequence_pct"]


def test_simultaneous_holes_are_not_out_of_sequence(design: BlastDesign):
    """Los taladros que salen juntos por diseno no pueden invertir su orden."""
    params = TimingParams(mode="Vector de direccion", detonator="NONEL LP (fondo)")
    vector = timing_mod.default_vector(design.holes)
    vector.brs_ms_m = 0.0                    # cada fila entera sale a la vez
    timing_mod.assign_delays(design.holes, params, 180.0, vector)

    resultado = timing_mod.overlap_probability(design.holes, params)
    assert resultado["p_out_of_sequence_pct"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Fragmentacion
# ---------------------------------------------------------------------------


def test_kuznetsov_decreases_with_more_explosive():
    coarse = frag.kuznetsov_x50(6.0, 200.0, 100.0, 100.0)
    fine = frag.kuznetsov_x50(6.0, 200.0, 200.0, 100.0)
    assert fine < coarse


def test_swebrec_is_monotonic_and_bounded():
    sizes = frag.DEFAULT_SIEVE_CM
    p = frag.swebrec(sizes, 25.0, 120.0, 2.5)
    assert np.all(np.diff(p) >= -1e-9)
    assert p[0] >= 0.0 and p[-1] <= 100.0 + 1e-9


def test_uniformity_index_in_valid_range():
    n = frag.cunningham_n(4.0, 4.6, 152.0, 10.0, 8.0, 2.5, 5.5)
    assert 0.7 <= n <= 2.8


def test_blast_curve_percentiles_are_ordered(design: BlastDesign):
    a = analyze(design, compute_energy=False)
    f = a.fragmentation
    assert 0 < f.p20_cm < f.x50_cm < f.p80_cm < f.xmax_cm


# ---------------------------------------------------------------------------
# Vibracion, onda aerea y proyeccion
# ---------------------------------------------------------------------------


def test_ppv_decays_with_distance():
    near = vibration.ppv_scaled(100.0, 500.0)
    far = vibration.ppv_scaled(400.0, 500.0)
    assert far < near


def test_max_charge_matches_ppv_limit():
    limit = 12.7
    w = vibration.max_charge_for_ppv(300.0, limit)
    assert vibration.ppv_scaled(300.0, w) == pytest.approx(limit, rel=1e-6)


def test_holmberg_persson_decays_with_radius():
    args = (1140.0, 0.7, 1.6, 15.0, 8.0)
    assert vibration.ppv_holmberg_persson(*args, 10.0) < vibration.ppv_holmberg_persson(*args, 2.0)


def test_airblast_level_is_plausible():
    r = airblast.predict_airblast(500.0, 400.0, 3.5, 152.0)
    assert 90.0 < r["airblast_db"] < 145.0


def test_short_stemming_raises_airblast():
    good = airblast.predict_airblast(500.0, 400.0, 3.5, 152.0)
    poor = airblast.predict_airblast(500.0, 400.0, 1.0, 152.0)
    assert poor["airblast_db"] > good["airblast_db"]


def test_flyrock_grows_when_burden_shrinks(design: BlastDesign):
    a = analyze(design, compute_energy=False)
    base = a.flyrock["max_throw_m"]
    for h in design.holes:
        h.relief_burden_m = h.burden_real_m = max(h.burden_real_m * 0.5, 0.5)
    tight = airblast.predict_flyrock(design.holes)["max_throw_m"]
    assert tight > base


# ---------------------------------------------------------------------------
# Analisis completo
# ---------------------------------------------------------------------------


def test_analysis_kpis_are_coherent(design: BlastDesign):
    a = analyze(design, compute_energy=False)
    k = a.kpis
    assert k["n_holes"] == len(design.holes)
    assert k["charge_kg"] > 0
    assert 0.1 < k["powder_factor"] < 3.0
    assert k["tonnes"] == pytest.approx(k["volume_m3"] * design.rock.density_t_m3, rel=1e-6)
    assert k["cost_total_usd_t"] > k["cost_db_usd_t"]
    assert 0 <= a.score <= 100


def test_analysis_annotates_every_hole(design: BlastDesign):
    analyze(design, compute_energy=False)
    for h in design.holes:
        assert h.volume_m3 > 0
        assert h.powder_factor > 0
        assert h.x50_cm > 0


def test_energy_field_conserves_total_energy(design: BlastDesign):
    from xblast.core.energy import compute_energy_field
    a = analyze(design, compute_energy=False)
    field = compute_energy_field(design.holes, cell_size=1.5)
    assert field is not None
    total = float(field.values.sum()) * field.spacing ** 3
    expected = sum(h.energy_mj for h in design.holes)
    assert total == pytest.approx(expected, rel=0.05)


def test_empty_design_analysis_is_safe():
    a = analyze(BlastDesign())
    assert a.kpis == {}
    assert a.findings == []


# ---------------------------------------------------------------------------
# Edicion manual por taladro
# ---------------------------------------------------------------------------


def test_manual_column_fills_the_hole(design: BlastDesign):
    from xblast.core.models import Deck

    hole = design.holes[0]
    charging.set_column(hole, [
        Deck(DeckKind.CARGA, 4.0, "ANFO", 1.0, 1),
        Deck(DeckKind.AIRE, 1.0),
        Deck(DeckKind.CARGA, 2.0, "Emulsion Gasificada 1.15", 1.0, 1),
        Deck(DeckKind.TACO, 1.0),
    ])
    total = sum(d.length_m for d in hole.decks)
    assert total == pytest.approx(hole.length_m, abs=0.05)
    assert hole.decks[-1].kind is DeckKind.TACO       # el ajuste va al collar
    assert hole.charge_kg > 0
    assert hole.charge_locked


def test_manual_column_is_ordered_from_the_toe(design: BlastDesign):
    from xblast.core.models import Deck

    hole = design.holes[0]
    charging.set_column(hole, [Deck(DeckKind.CARGA, 5.0, "ANFO", 1.0, 1),
                               Deck(DeckKind.TACO, 3.0)])
    offsets = [d.from_toe_m for d in hole.decks]
    assert offsets == sorted(offsets)
    assert hole.decks[0].from_toe_m == pytest.approx(0.0)


def test_global_rule_respects_manual_charges(design: BlastDesign):
    rule = ChargeRule(stemming_m=design.pattern.stemming_m)
    manual = design.holes[3]
    charging.set_column(manual, [Deck(DeckKind.CARGA, 6.0, "ANFO", 1.0, 1)])
    manual_kg = manual.charge_kg

    recharged = charging.apply_charge(design.holes, rule)
    assert recharged == len(design.holes) - 1
    assert manual.charge_kg == pytest.approx(manual_kg)

    charging.apply_charge(design.holes, rule, force=True)
    assert not manual.charge_locked


def test_unlock_charge_returns_holes_to_the_rule(design: BlastDesign):
    from xblast.core.models import Deck

    rule = ChargeRule(stemming_m=design.pattern.stemming_m)
    hole = design.holes[5]
    charging.set_column(hole, [Deck(DeckKind.CARGA, 2.0, "ANFO", 1.0, 1)])
    assert hole.charge_locked

    charging.unlock_charge([hole], rule)
    assert not hole.charge_locked
    assert hole.collar_stemming_m == pytest.approx(rule.stemming_m, abs=0.05)


def test_locked_delay_survives_retiming(design: BlastDesign):
    hole = design.holes[7]
    hole.delay_ms = 999.0
    hole.delay_locked = True

    timing_mod.assign_delays(design.holes, design.timing,
                             design.pattern.face_azimuth_deg)
    assert hole.delay_ms == pytest.approx(999.0)
    assert any(h.delay_ms != 999.0 for h in design.holes if h is not hole)

    freed = timing_mod.clear_delay_locks(design.holes)
    assert freed == 1
    timing_mod.assign_delays(design.holes, design.timing,
                             design.pattern.face_azimuth_deg)
    assert hole.delay_ms != pytest.approx(999.0)


def test_manual_edits_survive_a_full_analysis(design: BlastDesign):
    from xblast.core.models import Deck

    hole = design.holes[9]
    charging.set_column(hole, [Deck(DeckKind.CARGA, 7.0, "ANFO", 1.0, 2)])
    hole.hole_type = "Precorte"
    expected = hole.charge_kg

    a = analyze(design, compute_energy=False)
    assert hole.charge_kg == pytest.approx(expected)
    assert hole.hole_type == "Precorte"
    assert a.kpis["charge_kg"] > 0


# ---------------------------------------------------------------------------
# Secuencia electronica
# ---------------------------------------------------------------------------


def test_detonator_limits():
    from xblast.core import detonators as detdb

    det = detdb.get("i-kon II")
    assert det.electronic
    assert det.snap(17.4) == pytest.approx(17.0)
    assert det.snap(17.6) == pytest.approx(18.0)
    assert det.in_range(0) and det.in_range(det.max_delay_ms)
    assert not det.in_range(det.max_delay_ms + 1)
    assert det.on_grid(25.0) and not det.on_grid(25.4)
    # La dispersion crece con el retardo pero nunca baja del suelo declarado.
    assert det.scatter_ms(0) == pytest.approx(det.accuracy_floor_ms)
    assert det.scatter_ms(20000) > det.scatter_ms(100)


def test_electronic_beats_pyrotechnic_scatter():
    from xblast.core import detonators as detdb

    electronico = detdb.get("i-kon II").scatter_ms(500)
    pirotecnico = detdb.get("NONEL LP (fondo)").scatter_ms(500)
    assert pirotecnico > electronico * 50


def test_direction_vector_geometry():
    from xblast.core.models import DirectionVector

    v = DirectionVector(azimuth_deg=180.0, angle_deg=90.0)
    assert v.direction == pytest.approx([0.0, -1.0, 0.0], abs=1e-9)
    assert v.transverse[2] == pytest.approx(0.0)
    assert float(v.direction @ v.transverse) == pytest.approx(0.0, abs=1e-9)

    reconstruido = DirectionVector.from_points((0, 0, 0), (0, -30, 0))
    assert reconstruido.azimuth_deg == pytest.approx(180.0)
    assert reconstruido.angle_deg == pytest.approx(90.0)
    assert reconstruido.length_m == pytest.approx(30.0)


def test_vector_timing_follows_brb_and_brs(design: BlastDesign):
    vector = timing_mod.default_vector(design.holes, design.pattern.face_azimuth_deg)
    vector.brb_ms_m, vector.brs_ms_m = 4.0, 0.0
    timing_mod.assign_delays_from_vector(design.holes, vector)

    # Con BRS nulo la salida solo depende del avance: cada fila comparte tiempo.
    por_fila = {h.row: round(h.delay_ms, 1) for h in design.holes}
    assert len(set(por_fila.values())) == design.pattern.rows
    assert min(h.delay_ms for h in design.holes) == pytest.approx(0.0)

    duracion_simple = max(h.delay_ms for h in design.holes)
    vector.brb_ms_m = 8.0
    timing_mod.assign_delays_from_vector(design.holes, vector)
    assert max(h.delay_ms for h in design.holes) == pytest.approx(duracion_simple * 2, rel=0.02)

    vector.brb_ms_m, vector.brs_ms_m = 4.0, 3.0
    timing_mod.assign_delays_from_vector(design.holes, vector)
    assert len({round(h.delay_ms, 1) for h in design.holes}) > design.pattern.rows


def test_radial_timing_grows_with_distance(design: BlastDesign):
    center = design.holes[0].collar
    timing_mod.assign_delays_from_point(design.holes, center, ms_per_m=5.0)

    cerca = design.holes[0]
    lejos = max(design.holes,
                key=lambda h: float(np.linalg.norm(h.collar[:2] - center[:2])))
    assert cerca.delay_ms == pytest.approx(0.0)
    assert lejos.delay_ms > cerca.delay_ms


def test_charge_units_merge_contiguous_decks(design: BlastDesign):
    from xblast.core.charging import charge_units

    hole = design.holes[0]
    # La carga de fondo y la de columna van pegadas: son una sola carga.
    assert sum(1 for d in hole.decks if d.is_charge) == 2
    assert len(charge_units(hole)) == 1
    assert not hole.is_decked
    assert charge_units(hole)[0]["mass_kg"] == pytest.approx(hole.charge_kg, rel=1e-9)

    charging.apply_charge(design.holes, ChargeRule(n_decks=2, inter_deck_stem_m=1.5))
    seccionado = design.holes[0]
    assert seccionado.is_decked
    assert len(charge_units(seccionado)) == 2


def test_deck_delays_split_the_operating_charge():
    """Seccionar la columna solo baja la carga operante si cada tramo se retarda."""
    p = PatternParams(rows=1, cols=1)
    holes = pattern_mod.generate_pattern(p)
    charging.apply_charge(holes, ChargeRule(n_decks=2, inter_deck_stem_m=1.5))
    total = holes[0].charge_kg

    params = TimingParams(mode="Patron de amarre", deck_delay_ms=0.0)
    timing_mod.assign_delays(holes, params)
    assert timing_mod.cooperating_charge(holes, 8.0)["mic_kg"] == pytest.approx(total, rel=1e-6)

    params.deck_delay_ms = 50.0
    timing_mod.assign_delays(holes, params)
    eventos = timing_mod.charge_events(holes)
    assert len(eventos) == 2
    mic = timing_mod.cooperating_charge(holes, 8.0)["mic_kg"]
    assert mic == pytest.approx(max(e[1] for e in eventos), rel=1e-6)
    assert mic < total


def test_delays_snap_to_the_detonator_increment(design: BlastDesign):
    from xblast.core import detonators as detdb

    params = TimingParams(mode="Vector de direccion", detonator="i-kon II",
                          snap_to_increment=True)
    vector = timing_mod.default_vector(design.holes)
    vector.brb_ms_m = 3.7
    timing_mod.assign_delays(design.holes, params, 180.0, vector)

    det = detdb.get("i-kon II")
    assert all(det.on_grid(h.delay_ms) for h in design.holes)


def test_locked_delay_survives_vector_timing(design: BlastDesign):
    design.holes[4].delay_ms = 777.0
    design.holes[4].delay_locked = True
    vector = timing_mod.default_vector(design.holes)
    timing_mod.assign_delays_from_vector(design.holes, vector)
    assert design.holes[4].delay_ms == pytest.approx(777.0)


def test_sequence_check_flags_an_undersized_detonator(design: BlastDesign):
    params = TimingParams(mode="Vector de direccion", detonator="HotShot")
    vector = timing_mod.default_vector(design.holes)
    vector.brb_ms_m = 2000.0                      # duracion absurda a proposito
    timing_mod.assign_delays(design.holes, params, 180.0, vector)

    hallazgos = timing_mod.check_sequence(design.holes, params)
    assert any(f["level"] == "error" and "rango" in f["item"].lower() for f in hallazgos)


def test_isochrones_and_firing_path(design: BlastDesign):
    params = TimingParams(mode="Vector de direccion")
    vector = timing_mod.default_vector(design.holes)
    vector.brs_ms_m = 2.0
    timing_mod.assign_delays(design.holes, params, 180.0, vector)

    curvas = timing_mod.isochrones(design.holes, interval_ms=20.0)
    assert curvas
    niveles = [nivel for nivel, _ in curvas]
    assert niveles == sorted(niveles)
    assert all(line.shape[1] == 3 for _n, lines in curvas for line in lines)

    # Un intervalo mayor que la duracion no produce ninguna curva.
    assert timing_mod.isochrones(design.holes, interval_ms=100000.0) == []

    camino = timing_mod.firing_path(design.holes)
    assert camino.shape == (len(design.holes), 3)
