"""Persistencia de proyectos y exportacion de resultados.

El proyecto se guarda como JSON (extension ``.xbp``): legible, versionable y
facil de diffear, con la topografia opcionalmente incrustada.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, fields, is_dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from .. import __version__
from ..core.models import (
    BlastDesign, CostParams, Deck, DeckKind, Hole, PatternParams, RockMass,
    SiteConstraints, TimingParams,
)

PROJECT_EXT = ".xbp"
_FORMAT = "xblast-project"


# ---------------------------------------------------------------------------
# Serializacion
# ---------------------------------------------------------------------------


def _dump_dataclass(obj: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for f in fields(obj):
        v = getattr(obj, f.name)
        out[f.name] = v.value if hasattr(v, "value") else v
    return out


def design_to_dict(design: BlastDesign) -> Dict[str, Any]:
    """Convierte el diseno a un diccionario serializable."""
    return {
        "format": _FORMAT,
        "version": __version__,
        "name": design.name,
        "site": design.site,
        "author": design.author,
        "pattern": _dump_dataclass(design.pattern),
        "rock": _dump_dataclass(design.rock),
        "timing": _dump_dataclass(design.timing),
        "constraints": _dump_dataclass(design.constraints),
        "costs": _dump_dataclass(design.costs),
        "column_explosive": design.column_explosive,
        "bottom_explosive": design.bottom_explosive,
        "bottom_charge_m": design.bottom_charge_m,
        "primer_type": design.primer_type,
        "stemming_material": design.stemming_material,
        "holes": [h.to_dict() for h in design.holes],
        "topography": design.topography.tolist() if design.topography is not None else None,
        "free_face": design.free_face.tolist() if design.free_face is not None else None,
    }


def dict_to_design(data: Dict[str, Any]) -> BlastDesign:
    """Reconstruye el diseno desde el diccionario leido del archivo."""
    if data.get("format") != _FORMAT:
        raise ValueError("El archivo no es un proyecto de X-BLAST.")

    def build(cls, key):
        raw = data.get(key, {}) or {}
        valid = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in raw.items() if k in valid})

    design = BlastDesign(
        name=data.get("name", "Proyecto"),
        site=data.get("site", ""),
        author=data.get("author", ""),
        pattern=build(PatternParams, "pattern"),
        rock=build(RockMass, "rock"),
        timing=build(TimingParams, "timing"),
        constraints=build(SiteConstraints, "constraints"),
        costs=build(CostParams, "costs"),
        column_explosive=data.get("column_explosive", "ANFO"),
        bottom_explosive=data.get("bottom_explosive"),
        bottom_charge_m=data.get("bottom_charge_m", 2.5),
        primer_type=data.get("primer_type", "Booster Pentolita 450 g"),
        stemming_material=data.get("stemming_material", "Grava chancada 3/8\""),
    )

    hole_fields = {f.name for f in fields(Hole)} - {"decks"}
    deck_fields = {f.name for f in fields(Deck)} - {"kind"}
    for hd in data.get("holes", []):
        h = Hole(**{k: v for k, v in hd.items() if k in hole_fields})
        h.decks = [
            Deck(kind=DeckKind(d.get("kind", "Carga")),
                 **{k: v for k, v in d.items() if k in deck_fields})
            for d in hd.get("decks", [])
        ]
        design.holes.append(h)

    if data.get("topography"):
        design.topography = np.array(data["topography"], float)
    if data.get("free_face"):
        design.free_face = np.array(data["free_face"], float)
    return design


# ---------------------------------------------------------------------------
# Archivo
# ---------------------------------------------------------------------------


def save(design: BlastDesign, path: str | Path, embed_topography: bool = True) -> Path:
    """Guarda el proyecto en disco y devuelve la ruta escrita."""
    p = Path(path)
    if p.suffix.lower() != PROJECT_EXT:
        p = p.with_suffix(PROJECT_EXT)
    data = design_to_dict(design)
    if not embed_topography:
        data["topography"] = None
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    return p


def load(path: str | Path) -> BlastDesign:
    """Abre un proyecto guardado."""
    p = Path(path)
    return dict_to_design(json.loads(p.read_text(encoding="utf-8")))


# ---------------------------------------------------------------------------
# Exportaciones
# ---------------------------------------------------------------------------


def export_holes_csv(holes: Sequence[Hole], path: str | Path) -> Path:
    """Exporta la tabla de taladros lista para el area de operaciones."""
    p = Path(path).with_suffix(".csv")
    cols = ["ID", "ESTE", "NORTE", "COTA_COLLAR", "COTA_FONDO", "LONGITUD_M",
            "DIAMETRO_MM", "DIP", "AZIMUT", "TACO_M", "CARGA_KG", "EXPLOSIVO",
            "CEBOS", "RETARDO_MS", "BURDEN_M", "ESPACIAMIENTO_M", "VOLUMEN_M3",
            "FACTOR_POTENCIA", "X50_CM", "TIPO"]
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(cols)
        for h in holes:
            main = next((d.explosive for d in h.decks if d.is_charge), "")
            w.writerow([
                h.hid, f"{h.easting:.3f}", f"{h.northing:.3f}", f"{h.collar_z:.2f}",
                f"{h.toe_z:.2f}", f"{h.length_m:.2f}", f"{h.diameter_mm:.0f}",
                f"{h.dip_deg:.1f}", f"{h.azimuth_deg:.1f}", f"{h.collar_stemming_m:.2f}",
                f"{h.charge_kg:.1f}", main, h.n_primers, f"{h.delay_ms:.1f}",
                f"{h.burden_real_m:.2f}", f"{h.spacing_real_m:.2f}", f"{h.volume_m3:.1f}",
                f"{h.powder_factor:.3f}", f"{h.x50_cm:.1f}", h.hole_type,
            ])
    return p


def export_kpis_csv(kpis: Dict[str, Any], path: str | Path) -> Path:
    """Exporta los indicadores del analisis."""
    p = Path(path).with_suffix(".csv")
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Indicador", "Valor"])
        for k, v in kpis.items():
            w.writerow([k, f"{v:.4f}" if isinstance(v, float) else v])
    return p


def export_fragmentation_csv(sizes_cm: np.ndarray, passing_pct: np.ndarray,
                             path: str | Path) -> Path:
    """Exporta la curva granulometrica predicha."""
    p = Path(path).with_suffix(".csv")
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Tamano_cm", "Pasante_pct"])
        for s, q in zip(sizes_cm, passing_pct):
            w.writerow([f"{s:.2f}", f"{q:.2f}"])
    return p
