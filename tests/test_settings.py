"""Pruebas del esquema de preferencias y del tema configurable.

No requieren interfaz grafica: el almacen y la paleta son objetos normales.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# El almacen de preferencias se apoya en las senales de Qt; sin PySide6 no hay
# nada que probar aqui, pero el motor sigue siendo verificable.
pytest.importorskip("PySide6", reason="las preferencias requieren PySide6")

from xblast.ui import settings as S
from xblast.ui import theme


@pytest.fixture
def store(tmp_path: Path) -> S.Settings:
    return S.Settings(path=tmp_path / "prefs.json")


# ---------------------------------------------------------------------------
# Esquema
# ---------------------------------------------------------------------------


def test_schema_keys_are_unique():
    keys = [s.key for s in S.iter_settings()]
    assert len(keys) == len(set(keys))


def test_every_key_is_namespaced_by_its_page():
    for page in S.SCHEMA:
        for group in page.groups:
            for setting in group.settings:
                assert setting.key.startswith(f"{page.key}."), setting.key


def test_defaults_are_consistent_with_their_type():
    for s in S.iter_settings():
        if s.kind == "bool":
            assert isinstance(s.default, bool)
        elif s.kind == "int":
            assert isinstance(s.default, int) and s.minimum <= s.default <= s.maximum
        elif s.kind == "float":
            assert isinstance(s.default, (int, float))
            assert s.minimum <= s.default <= s.maximum
        elif s.kind == "choice":
            assert s.options and s.default in s.options, s.key
        elif s.kind == "color":
            assert isinstance(s.default, str) and s.default.startswith("#")
            assert len(s.default) == 7, s.key


def test_theme_presets_cover_every_option():
    options = S.BY_KEY["appearance.theme"].options
    for name in options:
        assert name in theme.PRESETS, name
        assert theme.preset_values(name)


def test_nav_modes_match_the_viewer():
    from xblast.ui.viewer3d import NavMode
    assert S.BY_KEY["interaction.nav_mode"].options == tuple(m.value for m in NavMode)


def test_hole_color_options_cover_every_type():
    from xblast.core.models import HoleType
    for t in HoleType:
        assert f"hole_colors.{t.value}" in S.DEFAULTS


# ---------------------------------------------------------------------------
# Almacen
# ---------------------------------------------------------------------------


def test_get_falls_back_to_the_default(store: S.Settings):
    assert store.get("appearance.accent") == "#1668b3"
    assert store.get("clave.inexistente", "x") == "x"


def test_set_reports_only_real_changes(store: S.Settings):
    assert store.set("appearance.radius", 9)
    assert not store.set("appearance.radius", 9)
    assert store.set("appearance.radius", 9, force=True)
    assert not store.set("clave.inexistente", 1)


def test_update_emits_once_for_the_whole_batch(store: S.Settings):
    lotes = []
    store.bulk_changed.connect(lotes.append)
    touched = store.update({"appearance.radius": 8, "appearance.icon_size": 22})
    assert sorted(touched) == ["appearance.icon_size", "appearance.radius"]
    assert len(lotes) == 1 and sorted(lotes[0]) == sorted(touched)


def test_reset_page_only_touches_that_page(store: S.Settings):
    store.set("appearance.radius", 11)
    store.set("costs.drilling_usd_m", 20.0)
    store.reset_page("appearance")
    assert store.is_default("appearance.radius")
    assert store.get("costs.drilling_usd_m") == 20.0


def test_save_writes_only_the_differences(tmp_path: Path):
    path = tmp_path / "prefs.json"
    store = S.Settings(path=path)
    store.set("appearance.accent", "#ff0000")
    store.save()

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["format"] == "xblast-settings"
    assert raw["settings"] == {"appearance.accent": "#ff0000"}

    restored = S.Settings(path=path)
    assert restored.get("appearance.accent") == "#ff0000"
    assert restored.get("appearance.radius") == S.DEFAULTS["appearance.radius"]


def test_unknown_keys_in_the_file_are_ignored(tmp_path: Path):
    path = tmp_path / "prefs.json"
    path.write_text(json.dumps({"settings": {"algo.viejo": 1,
                                             "appearance.radius": 7}}), encoding="utf-8")
    store = S.Settings(path=path)
    assert store.get("appearance.radius") == 7
    assert "algo.viejo" not in store.as_dict()


def test_export_and_import_roundtrip(tmp_path: Path, store: S.Settings):
    store.set("charts.line_width", 3.5)
    out = store.export_to(tmp_path / "copia")

    otro = S.Settings(path=tmp_path / "otro.json")
    otro.import_from(out)
    assert otro.get("charts.line_width") == 3.5


def test_search_finds_by_label_and_help(store: S.Settings):
    assert any(s.key == "interaction.select_mode" for _p, _g, s in S.search("clic"))
    assert any(s.key.startswith("costs.") for _p, _g, s in S.search("chancado"))
    assert S.search("   ") == []


# ---------------------------------------------------------------------------
# Tema
# ---------------------------------------------------------------------------


def test_theme_follows_the_settings(store: S.Settings):
    store.set("appearance.accent", "#b06818")
    store.set("appearance.radius", 10)
    store.set("appearance.density", "Amplia")
    theme.apply_settings(store)
    try:
        assert theme.C["accent"] == "#b06818"
        assert theme.METRICS["radius"] == 10
        assert theme.METRICS["row_height"] == theme.DENSITIES["Amplia"][1]
        assert "border-radius: 10px" in theme.stylesheet()
    finally:
        theme.apply_settings(S.Settings(path=Path("/no/existe.json")))


def test_derived_tones_follow_the_accent(store: S.Settings):
    store.set("appearance.accent", "#000000")
    theme.apply_settings(store)
    try:
        assert theme.C["accent_hover"] != theme.C["accent"]
        assert theme.C["accent_press"] == "#000000"      # no baja de cero
    finally:
        theme.apply_settings(S.Settings(path=Path("/no/existe.json")))


def test_color_helpers_clamp_and_mix():
    assert theme._shift("#ffffff", 50) == "#ffffff"
    assert theme._shift("#000000", -50) == "#000000"
    assert theme._mix("#000000", "#ffffff", 0.5) == "#808080"
    assert theme._mix("#000000", "#ffffff", 0.0) == "#000000"
    assert theme._rgb("#abc") == (0xaa, 0xbb, 0xcc)
