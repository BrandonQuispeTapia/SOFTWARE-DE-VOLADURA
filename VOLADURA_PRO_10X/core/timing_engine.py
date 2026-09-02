"""
core/timing_engine.py
=====================
Secuenciador topológico de detonación basado en grafos dirigidos.

Modela la red de iniciación como un grafo NetworkX donde:
    - Nodos = Taladros (Drillhole) con atributo downhole_delay_ms
    - Aristas dirigidas = conexiones de superficie con peso surface_delay_ms

Funcionalidades:
    1. Cálculo de tiempos absolutos de detonación.
    2. Dispersión estocástica (Nonel ±3%, Electrónico ±0.01%).
    3. Detección de riesgos de cut-off por falta de cara libre.

Bibliografía:
    - Lownds, C.M. (1983). Computer Modelling of Fragmentation
      from an Idealised Blast. Proc. 1st Int. Symp. Rock Fragmentation.
    - Cunningham, C.V.B. (2005). The Kuz-Ram fragmentation model —
      20 years on. Brighton Conference Proceedings, 201-210.
    - ISEE Blasters' Handbook (2011), Chapter 12: Delay Timing.

Autor: Félix Fernando Bautista Layme — UNA Puno, Ingeniería de Minas.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    import networkx as nx
except ImportError:
    raise ImportError("NetworkX requerido: pip install networkx")

from core.geometry import Drillhole, Point3D

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Resultado de disparo
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class FiringResult:
    """Resultado de disparo de un taladro individual.

    Attributes:
        hole_id: Identificador del taladro.
        nominal_time_ms: Tiempo nominal de detonación [ms].
        actual_time_ms: Tiempo real con dispersión estocástica [ms].
        charge_kg: Masa de explosivo en el taladro [kg].
        collar: Coordenada 3D del collar.
        row: Fila en el patrón.
        col: Columna en el patrón.
    """
    hole_id: str
    nominal_time_ms: float
    actual_time_ms: float
    charge_kg: float
    collar: Point3D
    row: int = 0
    col: int = 0


@dataclass
class CutoffWarning:
    """Advertencia de riesgo de tiro cortado (cut-off).

    Attributes:
        source_hole_id: Taladro que detona primero.
        target_hole_id: Taladro en riesgo de perder señal.
        source_time_ms: Tiempo de detonación del origen [ms].
        target_time_ms: Tiempo de detonación del destino [ms].
        surface_delay_ms: Retardo del conector de superficie [ms].
        risk_delta_ms: Margen negativo (< 0 = riesgo real) [ms].
        severity: 'CRITICAL' si delta < -5ms, 'WARNING' si < 0ms.
    """
    source_hole_id: str
    target_hole_id: str
    source_time_ms: float
    target_time_ms: float
    surface_delay_ms: float
    risk_delta_ms: float
    severity: str = "WARNING"


# ══════════════════════════════════════════════════════════════════════════════
# Clase TimingGraph
# ══════════════════════════════════════════════════════════════════════════════

class TimingGraph:
    """Grafo dirigido de la red de iniciación de una voladura.

    Usa NetworkX para modelar las dependencias temporales y detectar
    anomalías topológicas (cut-offs, circuitos redundantes).

    Attributes:
        graph: nx.DiGraph con nodos=taladros y aristas=conexiones.
        firing_results: Lista de FiringResult tras simulación.
        rng: Generador numpy para reproducibilidad.

    Example:
        >>> tg = TimingGraph(seed=42)
        >>> tg.add_hole("H-001", downhole_delay_ms=100, charge_kg=120,
        ...             collar=Point3D(0,0,4000), row=1, col=1)
        >>> tg.add_hole("H-002", downhole_delay_ms=100, charge_kg=120,
        ...             collar=Point3D(4,0,4000), row=1, col=2)
        >>> tg.add_connection("H-001", "H-002", surface_delay_ms=42)
        >>> results = tg.simulate_firing_times("NONEL")
    """

    # Dispersión estocástica por tipo de detonador (coef. de variación)
    SCATTER_CV: Dict[str, float] = {
        "NONEL": 0.03,        # ±3% (ISEE Handbook, 2011)
        "ELECTRONIC": 0.0001, # ±0.01%
        "ELECTRIC": 0.01,     # ±1%
    }

    # Velocidad típica de quema de manguera Nonel [m/ms]
    NONEL_BURN_VELOCITY_M_MS: float = 2.0  # ~2000 m/s = 2 m/ms

    def __init__(self, seed: Optional[int] = None) -> None:
        self.graph: nx.DiGraph = nx.DiGraph()
        self.firing_results: List[FiringResult] = []
        self.rng = np.random.default_rng(seed)

    # ─── Construcción del grafo ───────────────────────────────────────────

    def add_hole(
        self,
        hole_id: str,
        downhole_delay_ms: float,
        charge_kg: float,
        collar: Point3D,
        row: int = 0,
        col: int = 0,
    ) -> None:
        """Agrega un taladro como nodo del grafo.

        Args:
            hole_id: ID único del taladro.
            downhole_delay_ms: Retardo del detonador de fondo [ms].
            charge_kg: Masa de explosivo [kg].
            collar: Coordenada 3D del collar.
            row: Fila en el patrón.
            col: Columna en el patrón.
        """
        self.graph.add_node(
            hole_id,
            downhole_delay_ms=downhole_delay_ms,
            charge_kg=charge_kg,
            collar=collar,
            row=row,
            col=col,
        )

    def add_connection(
        self,
        source_id: str,
        target_id: str,
        surface_delay_ms: float,
    ) -> None:
        """Agrega una conexión de superficie (arista dirigida).

        Args:
            source_id: Taladro de origen (señal sale).
            target_id: Taladro de destino (señal llega).
            surface_delay_ms: Retardo del relé de superficie [ms].
        """
        if source_id not in self.graph:
            raise ValueError(f"Nodo origen '{source_id}' no existe.")
        if target_id not in self.graph:
            raise ValueError(f"Nodo destino '{target_id}' no existe.")

        # Distancia 3D entre collares (para cálculo de tiempo de quema)
        src_collar: Point3D = self.graph.nodes[source_id]["collar"]
        tgt_collar: Point3D = self.graph.nodes[target_id]["collar"]
        distance_m = src_collar.distance_to(tgt_collar)

        self.graph.add_edge(
            source_id, target_id,
            surface_delay_ms=surface_delay_ms,
            distance_m=distance_m,
        )

    def add_holes_from_pattern(
        self,
        holes: List[Drillhole],
        downhole_delay_ms: float,
        surface_delay_ms: float,
        connect_mode: str = "row_sequential",
    ) -> None:
        """Agrega todos los taladros de un BlastPattern y los conecta.

        Args:
            holes: Lista de Drillhole del patrón.
            downhole_delay_ms: Retardo de fondo común [ms].
            surface_delay_ms: Retardo de superficie entre taladros [ms].
            connect_mode: Modo de conexión.
                'row_sequential': fila por fila, col a col.
                'row_to_row': conectar último de fila N al primero de fila N+1.
        """
        for h in holes:
            self.add_hole(
                h.hole_id,
                downhole_delay_ms=downhole_delay_ms,
                charge_kg=h.total_charge_kg,
                collar=h.collar,
                row=h.row,
                col=h.col,
            )

        # Organizar por fila y columna
        rows_dict: Dict[int, List[Drillhole]] = {}
        for h in holes:
            rows_dict.setdefault(h.row, []).append(h)
        for row_holes in rows_dict.values():
            row_holes.sort(key=lambda x: x.col)

        sorted_rows = sorted(rows_dict.keys())

        for row_idx in sorted_rows:
            row_holes = rows_dict[row_idx]
            # Conectar secuencialmente dentro de la fila
            for i in range(len(row_holes) - 1):
                self.add_connection(
                    row_holes[i].hole_id,
                    row_holes[i + 1].hole_id,
                    surface_delay_ms=surface_delay_ms,
                )

        # Conectar filas entre sí
        if connect_mode == "row_to_row":
            for i in range(len(sorted_rows) - 1):
                last_in_row = rows_dict[sorted_rows[i]][-1]
                first_in_next = rows_dict[sorted_rows[i + 1]][0]
                self.add_connection(
                    last_in_row.hole_id,
                    first_in_next.hole_id,
                    surface_delay_ms=surface_delay_ms,
                )

    # ─── Simulación de tiempos ────────────────────────────────────────────

    def simulate_firing_times(
        self, detonator_type: str = "NONEL"
    ) -> List[FiringResult]:
        """Simula los tiempos absolutos de detonación con dispersión.

        Algoritmo:
            1. Para cada nodo, calcular el tiempo nominal acumulado
               (suma de surface_delays desde el inicio + downhole_delay).
            2. Aplicar scatter gaussiano según tipo de detonador.

        Args:
            detonator_type: 'NONEL', 'ELECTRONIC' o 'ELECTRIC'.

        Returns:
            Lista de FiringResult ordenada por tiempo de detonación.
        """
        cv = self.SCATTER_CV.get(detonator_type.upper(), 0.03)
        results: List[FiringResult] = []

        # Calcular tiempos nominales via caminos más cortos desde raíces
        nominal_times = self._calculate_nominal_times()

        for hole_id, nominal_ms in nominal_times.items():
            node = self.graph.nodes[hole_id]
            # Dispersión estocástica: σ = cv * t_nominal
            sigma = cv * nominal_ms if nominal_ms > 0 else 0.0
            actual_ms = float(self.rng.normal(nominal_ms, sigma))
            actual_ms = max(0.0, actual_ms)

            results.append(FiringResult(
                hole_id=hole_id,
                nominal_time_ms=nominal_ms,
                actual_time_ms=actual_ms,
                charge_kg=node["charge_kg"],
                collar=node["collar"],
                row=node.get("row", 0),
                col=node.get("col", 0),
            ))

        results.sort(key=lambda r: r.actual_time_ms)
        self.firing_results = results
        return results

    def _calculate_nominal_times(self) -> Dict[str, float]:
        """Calcula tiempos nominales acumulados para cada nodo.

        Para nodos raíz (sin predecesores): t = downhole_delay.
        Para nodos con predecesores: t = max(t_pred + surface_delay) + downhole.

        Returns:
            Dict {hole_id: tiempo_nominal_ms}.
        """
        times: Dict[str, float] = {}

        # Orden topológico (si es DAG) o por fila/col
        try:
            order = list(nx.topological_sort(self.graph))
        except nx.NetworkXUnfeasible:
            # Grafo con ciclos: ordenar por (row, col)
            order = sorted(
                self.graph.nodes,
                key=lambda n: (
                    self.graph.nodes[n].get("row", 0),
                    self.graph.nodes[n].get("col", 0),
                ),
            )

        for node_id in order:
            node = self.graph.nodes[node_id]
            downhole = node["downhole_delay_ms"]
            preds = list(self.graph.predecessors(node_id))

            if not preds:
                times[node_id] = downhole
            else:
                max_arrival = 0.0
                for pred_id in preds:
                    edge = self.graph.edges[pred_id, node_id]
                    arrival = times.get(pred_id, 0) + edge["surface_delay_ms"]
                    max_arrival = max(max_arrival, arrival)
                times[node_id] = max_arrival + downhole

        return times

    # ─── Detección de cut-offs ────────────────────────────────────────────

    def detect_cutoff_risks(
        self,
        rock_displacement_time_ms: float = 15.0,
    ) -> List[CutoffWarning]:
        """Detecta riesgos de tiro cortado (cut-off) en la secuencia.

        Regla de negocio (ISEE, 2011):
            Si el Taladro A detona y la onda de choque / desplazamiento
            de roca puede alcanzar el conector de superficie hacia B
            ANTES de que la señal del conector llegue a B, entonces
            la manguera se cortará y B no detonará.

            Riesgo si: t_detonación_A + t_desplazamiento < t_llegada_señal_B

        Args:
            rock_displacement_time_ms: Tiempo estimado para que la roca
                desplazada alcance la manguera de superficie [ms].
                Típicamente 10-20ms para burden 3-5m.

        Returns:
            Lista de CutoffWarning con cada riesgo detectado.
        """
        if not self.firing_results:
            self.simulate_firing_times()

        times_map = {r.hole_id: r.actual_time_ms for r in self.firing_results}
        warnings: List[CutoffWarning] = []

        for src, tgt, edge_data in self.graph.edges(data=True):
            t_src = times_map.get(src, 0)
            t_tgt = times_map.get(tgt, 0)
            surf_delay = edge_data["surface_delay_ms"]
            distance_m = edge_data.get("distance_m", 0)

            # Tiempo que tarda la señal Nonel en recorrer la manguera
            burn_time_ms = distance_m / self.NONEL_BURN_VELOCITY_M_MS

            # Tiempo en que la roca de A podría cortar la manguera
            rock_cut_time = t_src + rock_displacement_time_ms

            # Tiempo en que la señal llegaría a B (desde A, vía superficie)
            signal_arrival = t_src + surf_delay + burn_time_ms

            # Delta: positivo = seguro, negativo = riesgo
            delta = signal_arrival - rock_cut_time

            if delta < 0:
                severity = "CRITICAL" if delta < -5.0 else "WARNING"
                warnings.append(CutoffWarning(
                    source_hole_id=src,
                    target_hole_id=tgt,
                    source_time_ms=t_src,
                    target_time_ms=t_tgt,
                    surface_delay_ms=surf_delay,
                    risk_delta_ms=round(delta, 2),
                    severity=severity,
                ))
                logger.warning(
                    f"CUT-OFF {severity}: {src}->{tgt} "
                    f"delta={delta:.1f}ms"
                )

        return warnings

    # ─── Utilidades ───────────────────────────────────────────────────────

    def get_firing_order(self) -> List[str]:
        """Retorna IDs de taladros en orden de disparo."""
        return [r.hole_id for r in self.firing_results]

    def get_max_charge_per_delay(self, window_ms: float = 8.0) -> float:
        """Carga máxima cooperante dentro de una ventana temporal.

        Delegado a vibration.py pero expuesto aquí por conveniencia.

        Args:
            window_ms: Ancho de la ventana [ms]. Default 8ms (ISEE).

        Returns:
            Carga máxima cooperante [kg].
        """
        if not self.firing_results:
            return 0.0

        sorted_r = sorted(self.firing_results, key=lambda r: r.actual_time_ms)
        max_charge = 0.0
        n = len(sorted_r)

        for i in range(n):
            window_charge = 0.0
            t_start = sorted_r[i].actual_time_ms
            for j in range(i, n):
                if sorted_r[j].actual_time_ms - t_start <= window_ms:
                    window_charge += sorted_r[j].charge_kg
                else:
                    break
            max_charge = max(max_charge, window_charge)

        return max_charge

    @property
    def total_nodes(self) -> int:
        return self.graph.number_of_nodes()

    @property
    def total_edges(self) -> int:
        return self.graph.number_of_edges()

    def summary(self) -> Dict[str, Any]:
        """Resumen del grafo de detonación."""
        times = [r.actual_time_ms for r in self.firing_results]
        return {
            "total_holes": self.total_nodes,
            "total_connections": self.total_edges,
            "min_time_ms": min(times) if times else 0,
            "max_time_ms": max(times) if times else 0,
            "duration_s": (max(times) - min(times)) / 1000 if times else 0,
            "unique_delays": len(set(round(t, 1) for t in times)),
        }
