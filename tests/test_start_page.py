from pathlib import Path
import pytest
from PySide6.QtWidgets import QApplication
import pyvista as pv

pv.OFF_SCREEN = True

from xblast.ui.start_page import RecentProjectsManager, StartWindow, find_data_file
from xblast.ui.main_window import MainWindow

@pytest.fixture(scope="module")
def app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app

def test_find_data_file():
    turpo = find_data_file("datos TURPO.csv")
    assert turpo is not None
    assert turpo.exists()
    topo = find_data_file("Topografia.csv")
    assert topo is not None
    assert topo.exists()

def test_recent_projects_manager(tmp_path):
    f = tmp_path / "test_project.xbp"
    f.write_text("dummy")
    RecentProjectsManager.add_recent(f)
    recents = RecentProjectsManager.get_recent()
    assert any(r["path"] == str(f.resolve()) for r in recents)

def test_start_window_creation(app):
    win = StartWindow()
    assert win.windowTitle().startswith("Inicio")
    assert win.recents_table.columnCount() == 4
    win.close()

def test_start_window_signals(app):
    win = StartWindow()
    received = []
    win.project_selected.connect(lambda mode, path: received.append((mode, path)))
    win._on_new_parametric()
    assert received == [("parametric", "")]
    win._on_load_turpo()
    assert received[-1] == ("turpo", "")
    win._on_load_topo_mine()
    assert received[-1] == ("topo_mine", "")
    win.close()
