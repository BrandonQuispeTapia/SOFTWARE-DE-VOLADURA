"""Pruebas de importacion de datos y persistencia de proyectos."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from xblast.core import charging, pattern as pattern_mod
from xblast.core.charging import ChargeRule
from xblast.core.models import BlastDesign
from xblast.dataio import loaders, project

DATA = Path(__file__).resolve().parent.parent / "data"


@pytest.fixture
def design() -> BlastDesign:
    d = BlastDesign(name="Persistencia", site="Mina de prueba")
    d.holes = pattern_mod.generate_pattern(d.pattern)
    charging.apply_charge(d.holes, ChargeRule(stemming_m=d.pattern.stemming_m))
    return d


# ---------------------------------------------------------------------------
# Importadores
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not (DATA / "datos TURPO.csv").exists(), reason="dataset ausente")
def test_load_turpo_file():
    holes, report = loaders.load_holes(DATA / "datos TURPO.csv")
    assert report["rows_read"] == len(holes) > 0
    assert report["delimiter"] == ";"
    # El archivo trae LENGTH = 0: la longitud se deduce de las cotas.
    assert report["derived_length"] > 0
    assert all(h.length_m > 0 for h in holes)


@pytest.mark.skipif(not (DATA / "Coordenadas.csv").exists(), reason="dataset ausente")
def test_load_collar_file_without_geometry():
    holes, report = loaders.load_holes(DATA / "Coordenadas.csv", default_length_m=11.0)
    assert len(holes) > 0
    assert all(h.length_m == pytest.approx(11.0) for h in holes)
    assert holes[0].hid.startswith("DH")


@pytest.mark.skipif(not (DATA / "Topografia.csv").exists(), reason="dataset ausente")
def test_load_topography_and_interpolate():
    pts, report = loaders.load_topography(DATA / "Topografia.csv")
    assert pts.shape[1] == 3
    assert report["points"] == len(pts)

    f = loaders.elevation_interpolator(pts)
    x = float(np.mean(pts[:, 0]))
    y = float(np.mean(pts[:, 1]))
    z = f(x, y)
    assert np.isfinite(z)
    assert pts[:, 2].min() - 1 <= z <= pts[:, 2].max() + 1


def test_loader_reports_missing_file():
    with pytest.raises(FileNotFoundError):
        loaders.load_holes(DATA / "no_existe.csv")


def test_loader_detects_separator_and_aliases(tmp_path: Path):
    csv = tmp_path / "collares.csv"
    csv.write_text("BHID,ESTE,NORTE,COTA\nA1,100.5,200.5,3450.0\nA2,105,200.5,3450\n",
                   encoding="utf-8")
    holes, report = loaders.load_holes(csv)
    assert report["delimiter"] == ","
    assert len(holes) == 2
    assert holes[0].easting == pytest.approx(100.5)
    assert holes[0].collar_z == pytest.approx(3450.0)


def test_loader_skips_invalid_rows(tmp_path: Path):
    csv = tmp_path / "sucio.csv"
    csv.write_text("ID;X;Y;Z\nA1;10;20;30\nA2;;;\nA3;11;21;31\n", encoding="utf-8")
    holes, report = loaders.load_holes(csv)
    assert len(holes) == 2
    assert report["rows_skipped"] == 1


# ---------------------------------------------------------------------------
# Proyecto
# ---------------------------------------------------------------------------


def test_project_roundtrip(tmp_path: Path, design: BlastDesign):
    path = project.save(design, tmp_path / "proyecto")
    assert path.suffix == project.PROJECT_EXT

    restored = project.load(path)
    assert restored.name == design.name
    assert restored.site == design.site
    assert len(restored.holes) == len(design.holes)
    assert restored.pattern.burden_m == pytest.approx(design.pattern.burden_m)
    assert restored.rock.ucs_mpa == pytest.approx(design.rock.ucs_mpa)
    assert restored.total_charge_kg == pytest.approx(design.total_charge_kg, rel=1e-6)
    assert restored.holes[0].decks[0].kind == design.holes[0].decks[0].kind


def test_project_rejects_foreign_file(tmp_path: Path):
    bad = tmp_path / "otro.xbp"
    bad.write_text('{"format": "otra-cosa"}', encoding="utf-8")
    with pytest.raises(ValueError):
        project.load(bad)


def test_export_holes_csv(tmp_path: Path, design: BlastDesign):
    out = project.export_holes_csv(design.holes, tmp_path / "taladros")
    lines = out.read_text(encoding="utf-8-sig").strip().splitlines()
    assert len(lines) == len(design.holes) + 1
    assert lines[0].startswith("ID;ESTE;NORTE")


def test_html_report_is_selfcontained(tmp_path: Path, design: BlastDesign):
    from xblast.core.analysis import analyze
    from xblast.reports import build_report

    a = analyze(design, compute_energy=False)
    out = build_report(a, tmp_path / "reporte")
    html = out.read_text(encoding="utf-8")
    assert out.suffix == ".html"
    assert "Reporte tecnico de voladura" in html
    assert "data:image/png;base64," in html   # graficos incrustados
    assert "http://" not in html and "https://" not in html
