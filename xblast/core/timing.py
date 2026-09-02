"""Secuencia de salida, amarre y analisis temporal.

Tres formas de temporizar una voladura, todas intercambiables:

* **Patron de amarre** clasico, con retardo entre taladros y entre filas.
* **Vector de direccion**, el metodo habitual con detonadores electronicos: se
  dibuja una flecha sobre la malla y el retardo sale de la posicion de cada
  taladro respecto de ella, a razon de tantos ms por metro de avance y tantos
  por metro transversal.
* **Punto central**, con la salida abriendose radialmente desde un punto.

Ademas se reparten los retardos entre plataformas de un mismo taladro, se
calcula la carga operante por ventana de cooperacion a nivel de plataforma, se
generan las isocronas del disparo y se valida el programa contra los limites
del detonador elegido.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import detonators as detdb
from .models import DeckKind, DirectionVector, Hole, InitiationSystem, TimingParams

#: Patrones de amarre soportados.
TIE_PATTERNS = ["Fila por fila", "V (cuna)", "Diagonal (echelon)", "Eco / caja", "Punto central"]

#: Formas de generar la secuencia.
TIMING_MODES = ["Patron de amarre", "Vector de direccion", "Punto central"]


# ---------------------------------------------------------------------------
# Asignacion de tiempos
# ---------------------------------------------------------------------------


def assign_delays(holes: Sequence[Hole], params: TimingParams,
                  face_azimuth_deg: float = 180.0,
                  vector: Optional[DirectionVector] = None) -> None:
    """Genera la secuencia con el metodo indicado en ``params.mode``.

    Es el unico punto de entrada: el resto del programa no necesita saber si
    los tiempos vienen de un patron, de un vector o de un punto de salida.
    """
    if not holes:
        return

    if params.mode == "Vector de direccion" and vector is not None:
        assign_delays_from_vector(holes, vector)
    elif params.mode == "Punto central" and vector is not None:
        assign_delays_from_point(holes, vector.origin, params.radial_ms_m)
    else:
        assign_delays_from_pattern(holes, params, face_azimuth_deg)

    apply_deck_delays(holes, params)
    if params.snap_to_increment:
        snap_to_detonator(holes, params.detonator)
    simulate_scatter(holes, params)


def assign_delays_from_pattern(holes: Sequence[Hole], params: TimingParams,
                               face_azimuth_deg: float = 180.0) -> None:
    """Asigna ``delay_ms`` a cada taladro segun el patron de amarre."""
    if not holes:
        return

    az = math.radians(face_azimuth_deg)
    v = np.array([math.sin(az), math.cos(az)])   # hacia la cara libre
    u = np.array([v[1], -v[0]])                  # a lo largo de la fila

    pts = np.array([[h.easting, h.northing] for h in holes], float)
    origin = pts.mean(axis=0)
    local = pts - origin
    s_row = local @ u          # posicion a lo largo de la fila
    s_burden = -(local @ v)    # profundidad hacia el interior (0 en la cara)

    s_row = s_row - s_row.min()
    s_burden = s_burden - s_burden.min()

    pattern = params.pattern
    hd, rd = params.hole_delay_ms, params.row_delay_ms

    if pattern == "Fila por fila":
        t = s_burden * (rd / max(_median_step(s_burden), 1e-6)) + s_row * (hd / max(_median_step(s_row), 1e-6))

    elif pattern == "V (cuna)":
        center = s_row.mean()
        t = (np.abs(s_row - center) * (hd / max(_median_step(s_row), 1e-6))
             + s_burden * (rd / max(_median_step(s_burden), 1e-6)))

    elif pattern == "Diagonal (echelon)":
        ang = math.radians(params.echelon_deg)
        proj = s_row * math.cos(ang) + s_burden * math.sin(ang)
        t = proj * (hd / max(_median_step(s_row), 1e-6))

    elif pattern == "Eco / caja":
        t = (s_burden * (rd / max(_median_step(s_burden), 1e-6))
             + (s_row % max(_median_step(s_row), 1e-6)) * hd)
        order = np.argsort(s_row)
        t[order] += np.arange(len(order)) * hd * 0.15

    else:  # "Punto central"
        d = np.linalg.norm(local, axis=1)
        t = d * (hd / max(_median_step(s_row), 1e-6))

    t = t - t.min()
    for h, ti in zip(holes, t):
        # Un retardo fijado a mano manda sobre el amarre automatico.
        if getattr(h, 'delay_locked', False):
            continue
        h.delay_ms = float(round(ti, 1)) + params.in_hole_delay_ms


def _median_step(values: np.ndarray) -> float:
    """Paso caracteristico de una coordenada discretizada (espaciamiento medio)."""
    u = np.unique(np.round(values, 2))
    if u.size < 2:
        return 1.0
    return float(np.median(np.diff(u)))


def simulate_scatter(holes: Sequence[Hole], params: TimingParams,
                     seed: Optional[int] = 42) -> None:
    """Aplica la dispersion real del detonador a los tiempos nominales.

    La precision la marca el modelo elegido, no el tipo generico de sistema:
    entre un electronico de 0.005% y un pirotecnico de 3% hay dos ordenes de
    magnitud, y eso decide si la secuencia se respeta o se solapa.
    """
    det = detdb.get(params.detonator)
    rng = np.random.default_rng(seed)
    for h in holes:
        h.delay_actual_ms = float(h.delay_ms + rng.normal(0.0, det.scatter_ms(h.delay_ms)))


def assign_delays_from_vector(holes: Sequence[Hole],
                              vector: DirectionVector) -> None:
    """Reparte los retardos segun la posicion respecto del vector.

    Para cada taladro se mide cuanto ha avanzado la voladura en la direccion
    de la flecha y cuanto se ha separado de su eje; el retardo es la suma de
    ambas distancias multiplicadas por su tiempo por metro. El origen se
    desplaza para que el primer taladro salga en cero.
    """
    if not holes:
        return

    origin = vector.origin
    forward = vector.direction
    across = vector.transverse

    times: List[float] = []
    for h in holes:
        offset = h.collar - origin
        along = float(offset @ forward)
        sideways = abs(float(offset @ across))
        times.append(vector.brb_ms_m * along + vector.brs_ms_m * sideways)

    base = min(times)
    for h, t in zip(holes, times):
        if getattr(h, "delay_locked", False):
            continue
        h.delay_ms = round(t - base, 2)


def assign_delays_from_point(holes: Sequence[Hole], origin,
                             ms_per_m: float = 3.0,
                             plan_only: bool = True) -> None:
    """Salida radial desde un punto: el retardo crece con la distancia.

    Es la temporizacion de una rainura o de un disparo que abre desde el
    centro hacia afuera.
    """
    if not holes:
        return
    center = np.asarray(origin, float)
    times = []
    for h in holes:
        offset = h.collar - center
        d = float(np.linalg.norm(offset[:2] if plan_only else offset))
        times.append(ms_per_m * d)

    base = min(times)
    for h, t in zip(holes, times):
        if getattr(h, "delay_locked", False):
            continue
        h.delay_ms = round(t - base, 2)


def default_vector(holes: Sequence[Hole], face_azimuth_deg: float = 180.0,
                   params: Optional[TimingParams] = None) -> DirectionVector:
    """Vector razonable para empezar, sin que el usuario tenga que dibujarlo.

    Se apoya en el borde de la malla mas cercano a la cara libre y apunta hacia
    el interior siguiendo el azimut de salida, con una longitud que cubre todo
    el disparo.
    """
    brb = params.hole_delay_ms / 5.0 if params else 3.0
    if not holes:
        return DirectionVector(azimuth_deg=face_azimuth_deg, brb_ms_m=brb)

    az = math.radians(face_azimuth_deg)
    forward = np.array([math.sin(az), math.cos(az)])
    across = np.array([forward[1], -forward[0]])
    pts = np.array([[h.easting, h.northing] for h in holes], float)

    depth = pts @ forward
    side = pts @ across
    span = float(depth.max() - depth.min())
    margin = max(span * 0.12, 3.0)

    # Detras del borde por donde arranca el disparo y centrado en el ancho de
    # la malla, que es donde la flecha se lee sin taparla.
    origin = forward * (depth.min() - margin) + across * float(side.mean())
    z = float(np.mean([h.collar_z for h in holes]))

    return DirectionVector(
        origin_x=float(origin[0]), origin_y=float(origin[1]), origin_z=z,
        azimuth_deg=face_azimuth_deg, angle_deg=90.0,
        brb_ms_m=round(brb, 2), brs_ms_m=0.0,
        length_m=round(span + 2 * margin, 1))


def apply_deck_delays(holes: Sequence[Hole], params: TimingParams) -> None:
    """Reparte el retardo dentro del taladro entre sus plataformas.

    Cada plataforma de carga sale ``deck_delay_ms`` despues de la anterior,
    contando desde el fondo, y los cebos de una misma plataforma se separan
    ``inner_delay_ms``. Es lo que convierte un taladro con varias cargas en
    varios eventos sismicos independientes.
    """
    from .charging import charge_units

    for h in holes:
        for deck in h.decks:
            deck.delay_ms = 0.0
        for index, unit in enumerate(charge_units(h)):
            inner = params.inner_delay_ms * max(int(unit["primers"]) - 1, 0)
            delay = round(index * params.deck_delay_ms + inner, 2)
            unit["delay_ms"] = delay
            for deck in unit["decks"]:
                deck.delay_ms = delay


def snap_to_detonator(holes: Sequence[Hole], detonator_name: str) -> int:
    """Ajusta los retardos al incremento programable del detonador.

    Returns:
        Numero de taladros cuyo tiempo hubo que redondear.
    """
    det = detdb.get(detonator_name)
    changed = 0
    for h in holes:
        snapped = det.snap(h.delay_ms)
        if abs(snapped - h.delay_ms) > 1e-9:
            h.delay_ms = snapped
            changed += 1
        for deck in h.decks:
            if deck.is_charge:
                deck.delay_ms = det.snap(deck.delay_ms)
    return changed


def clear_delay_locks(holes: Sequence[Hole]) -> int:
    """Devuelve los retardos fijados a mano al control del amarre automatico."""
    n = sum(1 for h in holes if getattr(h, 'delay_locked', False))
    for h in holes:
        h.delay_locked = False
    return n


# ---------------------------------------------------------------------------
# Analisis
# ---------------------------------------------------------------------------


def charge_events(holes: Sequence[Hole],
                  use_actual: bool = True) -> List[Tuple[float, float, str]]:
    """Eventos de detonacion como ``(tiempo, masa, etiqueta)``.

    Un taladro con varias plataformas retardadas no es una sola carga: son
    varios eventos separados en el tiempo, y esa es justamente la razon de
    seccionar la columna. Se devuelven al detalle de plataforma para que la
    carga operante refleje lo que de verdad detona junto.
    """
    from .charging import charge_units

    events: List[Tuple[float, float, str]] = []
    for h in holes:
        base = h.delay_actual_ms if use_actual else h.delay_ms
        units = charge_units(h)
        if len(units) <= 1:
            if h.charge_kg > 0:
                events.append((base, h.charge_kg, h.hid))
            continue
        for i, unit in enumerate(units, start=1):
            events.append((base + float(unit["delay_ms"]),
                           float(unit["mass_kg"]), f"{h.hid}/{i}"))
    events.sort(key=lambda e: e[0])
    return events


def cooperating_charge(holes: Sequence[Hole], window_ms: float = 8.0,
                       use_actual: bool = True) -> Dict[str, object]:
    """Carga operante maxima (MIC) dentro de una ventana deslizante.

    La regla de 8 ms de la USBM considera que cargas que detonan dentro de esa
    ventana cooperan sismicamente y deben sumarse para predecir vibraciones.
    El recuento va por plataforma: seccionar la columna solo sirve si el
    calculo lo reconoce.
    """
    events = charge_events(holes, use_actual)
    if not events:
        return {"mic_kg": 0.0, "window_ms": window_ms, "t_start_ms": 0.0,
                "n_cooperating": 0, "holes": []}

    t = np.array([e[0] for e in events], float)
    w = np.array([e[1] for e in events], float)
    labels = [e[2] for e in events]

    best, best_i, best_j = 0.0, 0, 0
    j = 0
    run = 0.0
    for i in range(len(t)):
        while j < len(t) and t[j] - t[i] <= window_ms:
            run += w[j]
            j += 1
        if run > best:
            best, best_i, best_j = run, i, j
        run -= w[i]

    ids = labels[best_i:best_j]
    return {
        "mic_kg": float(best),
        "window_ms": window_ms,
        "t_start_ms": float(t[best_i]) if len(t) else 0.0,
        "n_cooperating": len(ids),
        "holes": ids,
        "n_events": len(events),
    }


def relief_time_analysis(holes: Sequence[Hole], params: TimingParams) -> Dict[str, object]:
    """Tiempo de alivio por metro de burden y deteccion de secuencias criticas.

    Criterio practico: 3-6 ms/m entre taladros de una fila y 10-30 ms/m entre
    filas. Menos de 3 ms/m no da tiempo al movimiento del burden (confinamiento
    excesivo, vibracion alta); mas de 30 ms/m rompe la cooperacion entre cargas.
    """
    if not holes:
        return {}

    b = float(np.mean([h.burden_real_m for h in holes if h.burden_real_m > 0] or [1.0]))
    s = float(np.mean([h.spacing_real_m for h in holes if h.spacing_real_m > 0] or [1.0]))

    hole_ms_m = params.hole_delay_ms / max(s, 1e-6)
    row_ms_m = params.row_delay_ms / max(b, 1e-6)

    times = sorted(h.delay_ms for h in holes)
    total = times[-1] - times[0] if len(times) > 1 else 0.0
    gaps = np.diff(times) if len(times) > 1 else np.array([0.0])

    return {
        "hole_relief_ms_m": hole_ms_m,
        "row_relief_ms_m": row_ms_m,
        "total_duration_ms": total,
        "min_gap_ms": float(np.min(gaps)) if gaps.size else 0.0,
        "mean_gap_ms": float(np.mean(gaps)) if gaps.size else 0.0,
        "simultaneous_pairs": int(np.sum(gaps < 1.0)),
    }


def overlap_probability(holes: Sequence[Hole], params: TimingParams,
                        n_sim: int = 400, threshold_ms: float = 1.0,
                        seed: Optional[int] = 7) -> Dict[str, float]:
    """Probabilidad de solape por dispersion (Monte Carlo).

    Cada realizacion perturba los retardos nominales con el CV del sistema y
    cuenta cuantos pares consecutivos quedan a menos de ``threshold_ms``.
    """
    if len(holes) < 2:
        return {"p_overlap_pct": 0.0, "mean_overlaps": 0.0,
                "p_out_of_sequence_pct": 0.0, "scatter_cv_pct": 0.0}

    det = detdb.get(params.detonator)
    nominal = np.sort(np.array([h.delay_ms for h in holes], float))
    sigma = np.array([det.scatter_ms(t) for t in nominal], float)

    # Los taladros que comparten tiempo salen juntos a proposito: ni se solapan
    # por dispersion ni pueden invertir su orden. Solo se miden las parejas que
    # el diseno separo de verdad.
    separadas = np.diff(nominal) > 1e-9
    if not separadas.any():
        return {"p_overlap_pct": 0.0, "mean_overlaps": 0.0,
                "p_out_of_sequence_pct": 0.0,
                "scatter_cv_pct": det.accuracy_pct * 100.0}

    rng = np.random.default_rng(seed)
    overlaps = np.zeros(n_sim)
    out_of_seq = np.zeros(n_sim, bool)

    for k in range(n_sim):
        real = np.diff(nominal + rng.normal(0.0, sigma))[separadas]
        overlaps[k] = int(np.sum(real < threshold_ms))
        out_of_seq[k] = bool(np.any(real < 0.0))

    return {
        "p_overlap_pct": float(np.mean(overlaps > 0) * 100.0),
        "mean_overlaps": float(np.mean(overlaps)),
        "p_out_of_sequence_pct": float(np.mean(out_of_seq) * 100.0),
        "scatter_cv_pct": det.accuracy_pct * 100.0,
    }


def timing_histogram(holes: Sequence[Hole], bin_ms: float = 8.0) -> Tuple[np.ndarray, np.ndarray]:
    """Histograma de carga detonada por ventana temporal."""
    events = charge_events(holes)
    if not events:
        return np.array([0.0]), np.array([0.0])
    t = np.array([e[0] for e in events], float)
    w = np.array([e[1] for e in events], float)
    edges = np.arange(t.min(), t.max() + bin_ms * 1.5, bin_ms)
    hist, _ = np.histogram(t, bins=edges, weights=w)
    return edges[:-1], hist


# ---------------------------------------------------------------------------
# Representacion de la secuencia
# ---------------------------------------------------------------------------


def firing_path(holes: Sequence[Hole]) -> np.ndarray:
    """Recorrido del disparo: collares ordenados por tiempo de salida.

    Returns:
        Array ``(N, 3)`` listo para dibujar como polilinea, o vacio.
    """
    if len(holes) < 2:
        return np.empty((0, 3))
    ordered = sorted(holes, key=lambda h: h.delay_ms)
    return np.array([h.collar for h in ordered], float)


def isochrones(holes: Sequence[Hole], interval_ms: float = 100.0,
               resolution: int = 140,
               margin: float = 0.05) -> List[Tuple[float, List[np.ndarray]]]:
    """Isocronas del disparo: curvas de igual tiempo de detonacion.

    Se interpola el tiempo sobre una rejilla en planta y se extraen las curvas
    de nivel cada ``interval_ms``. Es la lectura mas directa de como avanza el
    frente: si las curvas se apretan, ahi la salida es lenta y el burden queda
    confinado; si se abren, la voladura corre.

    Returns:
        Lista de ``(tiempo, [polilineas (M, 3)])``.
    """
    if len(holes) < 4 or interval_ms <= 0:
        return []
    try:
        from contourpy import contour_generator
        from scipy.interpolate import LinearNDInterpolator, NearestNDInterpolator
    except ImportError:
        return []

    pts = np.array([[h.easting, h.northing] for h in holes], float)
    times = np.array([h.delay_ms for h in holes], float)
    if float(times.max() - times.min()) < interval_ms:
        return []

    span = pts.max(axis=0) - pts.min(axis=0)
    pad = np.maximum(span * margin, 1.0)
    lo = pts.min(axis=0) - pad
    hi = pts.max(axis=0) + pad
    xs = np.linspace(lo[0], hi[0], resolution)
    ys = np.linspace(lo[1], hi[1], resolution)
    grid_x, grid_y = np.meshgrid(xs, ys)

    try:
        linear = LinearNDInterpolator(pts, times)
        nearest = NearestNDInterpolator(pts, times)
    except Exception:
        return []
    values = linear(grid_x, grid_y)
    holes_in_grid = ~np.isfinite(values)
    if holes_in_grid.any():
        values[holes_in_grid] = nearest(grid_x[holes_in_grid], grid_y[holes_in_grid])

    z = float(np.mean([h.collar_z for h in holes])) + 0.5
    generator = contour_generator(x=grid_x, y=grid_y, z=values)

    first = math.ceil(times.min() / interval_ms) * interval_ms
    levels = np.arange(first, times.max(), interval_ms)
    out: List[Tuple[float, List[np.ndarray]]] = []
    for level in levels:
        try:
            lines = generator.lines(float(level))
        except Exception:
            continue
        polylines = [np.column_stack([seg, np.full(len(seg), z)])
                     for seg in _as_segments(lines) if len(seg) >= 2]
        if polylines:
            out.append((float(level), polylines))
    return out


def _as_segments(lines) -> List[np.ndarray]:
    """Normaliza la salida de contourpy, que varia segun su modo de relleno."""
    if lines is None:
        return []
    if isinstance(lines, tuple):          # (puntos, desplazamientos)
        points, offsets = lines[0], lines[1]
        if points is None or offsets is None:
            return []
        return [np.asarray(points[offsets[i]:offsets[i + 1]], float)
                for i in range(len(offsets) - 1)]
    return [np.asarray(seg, float) for seg in lines if seg is not None]


def check_sequence(holes: Sequence[Hole], params: TimingParams) -> List[Dict[str, str]]:
    """Valida el programa de tiempos contra los limites del detonador.

    Es la comprobacion que se hace antes de bajar la secuencia a la maquina:
    tiempos fuera de rango, valores que el detonador no puede programar,
    unidades por encima del maximo del sistema y cargas que salen juntas sin
    querer.
    """
    out: List[Dict[str, str]] = []
    if not holes:
        return out

    det = detdb.get(params.detonator)
    delays = [h.delay_ms for h in holes]
    units = sum(max(h.n_primers, 1) for h in holes)

    fuera = [h.hid for h in holes if not det.in_range(h.delay_ms)]
    if fuera:
        muestra = ", ".join(fuera[:8]) + ("..." if len(fuera) > 8 else "")
        out.append({"level": "error", "item": "Retardo fuera de rango",
                    "message": f"{len(fuera)} taladro(s) fuera del rango del "
                               f"{det.name} ({det.min_delay_ms:,.0f} a "
                               f"{det.max_delay_ms:,.0f} ms): {muestra}"})
    else:
        out.append({"level": "ok", "item": "Rango de retardos",
                    "message": f"{min(delays):,.0f} a {max(delays):,.0f} ms, dentro "
                               f"del rango del {det.name}."})

    desalineados = [h.hid for h in holes if not det.on_grid(h.delay_ms)]
    if desalineados:
        out.append({"level": "warn", "item": "Incremento programable",
                    "message": f"{len(desalineados)} taladro(s) con tiempos que no son "
                               f"multiplo de {det.increment_ms:g} ms. Active el ajuste "
                               "automatico o corrijalos a mano."})

    if units > det.max_units_per_blast:
        out.append({"level": "error", "item": "Unidades por disparo",
                    "message": f"{units:,} detonadores superan el maximo de "
                               f"{det.max_units_per_blast:,} del {det.name}. Divida el disparo."})
    else:
        out.append({"level": "ok", "item": "Unidades por disparo",
                    "message": f"{units:,} detonadores de {det.max_units_per_blast:,} admitidos."})

    sin_cebo = [h.hid for h in holes if h.charge_kg > 0 and h.n_primers == 0]
    if sin_cebo:
        out.append({"level": "error", "item": "Taladros sin iniciar",
                    "message": f"{len(sin_cebo)} taladro(s) con carga y sin cebo asignado."})

    conteo: Dict[float, int] = {}
    for d in delays:
        conteo[d] = conteo.get(d, 0) + 1
    grupos = [n for n in conteo.values() if n > 1]
    if grupos:
        # Que salgan juntos no es un fallo en si: con BRS = 0 una fila entera sale
        # a la vez a proposito. Lo que preocupa es que el grupo sea grande, porque
        # toda esa carga suma como una sola en el calculo de vibraciones.
        mayor = max(grupos)
        nivel = "error" if mayor >= max(len(holes) * 0.3, 3) else "warn"
        out.append({"level": nivel, "item": "Salidas simultaneas",
                    "message": f"{sum(grupos)} taladro(s) en {len(grupos)} grupo(s) comparten "
                               f"tiempo exacto; el mayor reune {mayor}. Su carga suma como una "
                               "sola en la prediccion de vibraciones."})

    decked = [h for h in holes if h.is_decked]
    if decked:
        out.append({"level": "ok", "item": "Plataformas retardadas",
                    "message": f"{len(decked)} taladro(s) seccionados con "
                               f"{params.deck_delay_ms:g} ms entre plataformas."})

    return out


def audit_timing(holes: Sequence[Hole], params: TimingParams) -> List[Dict[str, str]]:
    """Revision de la secuencia contra criterios de buena practica."""
    out: List[Dict[str, str]] = []
    if not holes:
        return out

    rel = relief_time_analysis(holes, params)
    h_ms = rel.get("hole_relief_ms_m", 0.0)
    r_ms = rel.get("row_relief_ms_m", 0.0)

    if h_ms < 2.5:
        out.append({"level": "error", "item": "Retardo entre taladros",
                    "message": f"{h_ms:.1f} ms/m (< 2.5). Cargas practicamente simultaneas: "
                               "vibracion elevada y fragmentacion pobre."})
    elif h_ms > 10.0:
        out.append({"level": "warn", "item": "Retardo entre taladros",
                    "message": f"{h_ms:.1f} ms/m (> 10). Se pierde la interaccion entre cargas vecinas."})
    else:
        out.append({"level": "ok", "item": "Retardo entre taladros",
                    "message": f"{h_ms:.1f} ms/m — dentro de 3-6 ms/m recomendado."})

    if r_ms < 8.0:
        out.append({"level": "error", "item": "Retardo entre filas",
                    "message": f"{r_ms:.1f} ms/m (< 8). El burden de la fila previa no alcanza a moverse: "
                               "confinamiento, sobre-rotura y riesgo de tiros soplados."})
    elif r_ms > 35.0:
        out.append({"level": "warn", "item": "Retardo entre filas",
                    "message": f"{r_ms:.1f} ms/m (> 35). Secuencia muy lenta; puede producirse corte de linea."})
    else:
        out.append({"level": "ok", "item": "Retardo entre filas",
                    "message": f"{r_ms:.1f} ms/m — dentro de 10-30 ms/m recomendado."})

    ov = overlap_probability(holes, params)
    if ov["p_overlap_pct"] > 25.0:
        out.append({"level": "warn", "item": "Dispersion de retardos",
                    "message": f"Probabilidad de solape {ov['p_overlap_pct']:.0f}% con "
                               f"CV = {ov['scatter_cv_pct']:.1f}%. Considere iniciacion electronica."})
    if ov["p_out_of_sequence_pct"] > 5.0:
        out.append({"level": "error", "item": "Salida fuera de secuencia",
                    "message": f"{ov['p_out_of_sequence_pct']:.0f}% de las simulaciones invierten el orden de salida."})

    return out
