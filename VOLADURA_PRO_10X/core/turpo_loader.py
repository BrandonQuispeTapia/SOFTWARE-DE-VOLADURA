"""
core/turpo_loader.py
====================
Parser para archivos de taladros en formato TURPO.

Carga datos de perforación incluyendo coordenadas, elevación, azimuth y dip.

Formato esperado:
    ID; EAST; NORTH; ELEV TOE; ELEV COLLAR; LENGTH; AZ; DIP; MATERIAL

Autor: Félix Fernando Bautista Layme — UNA Puno.
"""

import csv
from pathlib import Path
import numpy as np
from typing import List, Dict, Tuple
from dataclasses import dataclass


@dataclass
class TurpoHole:
    """Representa un taladro cargado desde archivo TURPO."""
    hole_id: str
    east: float
    north: float
    elev_toe: float
    elev_collar: float
    length: float
    azimuth_deg: float
    dip_deg: float
    material: str

    @property
    def calculated_length(self) -> float:
        """Calcula la longitud si está mal registrada.

        Si LENGTH=0, calcula como diferencia de elevaciones.
        """
        if self.length > 0:
            return self.length
        return abs(self.elev_collar - self.elev_toe)


class TurpoLoader:
    """Parser de archivos TURPO."""

    @staticmethod
    def load_csv(filepath: str, auto_fix_length: bool = True) -> List[TurpoHole]:
        """Carga un archivo TURPO CSV.

        Args:
            filepath: Ruta al archivo CSV.
            auto_fix_length: Si True, calcula LENGTH si está a 0.

        Returns:
            Lista de TurpoHole.

        Raises:
            IOError: Si el archivo no existe.
            ValueError: Si el formato es incorrecto.
        """
        holes = []
        target = Path(filepath)
        if not target.exists():
            for candidate in [
                Path("data") / filepath,
                Path("../data") / filepath,
                Path(__file__).resolve().parent.parent.parent / "data" / filepath,
                Path(__file__).resolve().parent.parent / "data" / filepath
            ]:
                if candidate.exists():
                    target = candidate
                    break

        try:
            with open(target, 'r', encoding='utf-8-sig') as f:
                # Detectar separador
                first_line = f.readline()
                sep = ";" if ";" in first_line else ","
                f.seek(0)

                reader = csv.DictReader(f, delimiter=sep)
                if reader.fieldnames is None:
                    raise ValueError("Archivo CSV vacío o sin encabezado")

                # Normalizar nombres de columnas (quitar espacios)
                fieldnames = [fn.strip() if fn else "" for fn in reader.fieldnames]
                reader.fieldnames = fieldnames

                for row_num, row in enumerate(reader, start=2):  # start=2 porque la fila 1 es encabezado
                    try:
                        # Limpiar valores
                        row_clean = {k.strip(): v.strip() if v else "" for k, v in row.items()}

                        hole = TurpoHole(
                            hole_id=str(row_clean.get("ID", "")).strip(),
                            east=float(row_clean.get("EAST", 0)),
                            north=float(row_clean.get("NORTH", 0)),
                            elev_toe=float(row_clean.get("ELEV TOE", 0)),
                            elev_collar=float(row_clean.get("ELEV COLLAR", 0)),
                            length=float(row_clean.get("LENGTH", 0)),
                            azimuth_deg=float(row_clean.get("AZ", 0)),
                            dip_deg=float(row_clean.get("DIP", 0)),
                            material=str(row_clean.get("MATERIAL", "Blasthole")).strip(),
                        )

                        # Auto-corregir si LENGTH=0
                        if auto_fix_length and hole.length == 0:
                            hole.length = hole.calculated_length

                        holes.append(hole)
                    except (ValueError, KeyError) as e:
                        raise ValueError(f"Error en fila {row_num}: {e}")

        except IOError as e:
            raise IOError(f"No se pudo abrir archivo '{filepath}': {e}")

        return holes

    @staticmethod
    def to_collars_and_toes(holes: List[TurpoHole]) -> Tuple[np.ndarray, np.ndarray]:
        """Convierte lista de taladros a arrays de collares y fondos.

        Returns:
            (collars_array, toes_array) donde cada uno es (N, 3) con [X, Y, Z].
        """
        collars = []
        toes = []

        for hole in holes:
            # El collar está a la elevación ELEV_COLLAR
            collar = np.array([hole.east, hole.north, hole.elev_collar], dtype=np.float64)

            # El toe está a la elevación ELEV_TOE
            toe = np.array([hole.east, hole.north, hole.elev_toe], dtype=np.float64)

            collars.append(collar)
            toes.append(toe)

        return np.array(collars), np.array(toes)

    @staticmethod
    def summary(holes: List[TurpoHole]) -> Dict:
        """Genera un resumen estadístico de los taladros.

        Returns:
            Dict con KPIs.
        """
        if not holes:
            return {
                "total_holes": 0,
                "avg_length_m": 0,
                "min_elevation_m": 0,
                "max_elevation_m": 0,
            }

        lengths = [h.calculated_length for h in holes]
        elevations = [h.elev_collar for h in holes]

        return {
            "total_holes": len(holes),
            "avg_length_m": round(np.mean(lengths), 2),
            "min_length_m": round(np.min(lengths), 2),
            "max_length_m": round(np.max(lengths), 2),
            "min_elevation_m": round(np.min(elevations), 2),
            "max_elevation_m": round(np.max(elevations), 2),
        }
