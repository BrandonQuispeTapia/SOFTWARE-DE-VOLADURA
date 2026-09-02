"""Ventana principal de X-BLAST.

Organiza el area de trabajo — visor 3D al centro, paneles de diseno a la
izquierda, resultados a la derecha, bitacora abajo — y coordina el flujo
diseno -> analisis -> optimizacion -> reporte.
"""

from __future__ import annotations

import copy
import math
import time
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
from PySide6.QtCore import QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import (
    QComboBox, QDockWidget, QFileDialog, QLabel, QMainWindow, QMessageBox,
    QProgressBar, QTabBar, QToolBar, QWidget,
)

from .. import __appname__, __tagline__, __version__
from ..core import charging, explosives as exdb
from ..core import timing as timing_core
from ..core import pattern as pattern_mod
from ..core.analysis import BlastAnalysis
from ..core.charging import ChargeRule
from ..core.models import BlastDesign, Hole, HoleType
from ..core.optimizer import Scenario
from ..core.timing import timing_histogram
from ..core.vibration import max_charge_for_ppv
from ..dataio import loaders, project as project_io
from ..reports.html_report import build_report
from . import icons, tasks
from . import widgets as W
from .panels import (
    ChargePanel, ConsolePanel, DesignPanel, ExplorerPanel, HoleTablePanel,
    OptimizePanel, PropertiesPanel, ResultsPanel, TimingPanel,
)
from .theme import C
from .viewer3d import NavMode, THEMES, Viewer3D
from .viewer_bar import ViewerBar

DATA_DIRS = ("data", ".", "..", "../data")


class MainWindow(QMainWindow):
    """Ventana principal de la aplicacion."""

    def __init__(self, initial_mode: str = "parametric",
                 initial_path: Optional[Path | str] = None, parent=None):
        super().__init__(parent)
        self.initial_mode = initial_mode
        self.initial_path = Path(initial_path) if initial_path else None
        self.start_window = None

        self.setWindowTitle(f"{__appname__} {__version__} — {__tagline__}")
        self.setWindowIcon(icons.app_icon())
        self.resize(1680, 980)
        self.setDockOptions(
            QMainWindow.DockOption.AllowNestedDocks
            | QMainWindow.DockOption.AllowTabbedDocks
            | QMainWindow.DockOption.AnimatedDocks)

        self.design = BlastDesign(name="Voladura sin titulo")
        self.analysis: Optional[BlastAnalysis] = None
        self.project_path: Optional[Path] = None
        self._task = None
        self._dirty = False
        self._busy = False
        self._analysis_queued = False
        self._refreshing = False
        self._syncing_selection = False

        self._build_viewer()
        self._build_panels()
        self._build_actions()
        self._build_toolbar()
        self._build_menu()
        self._build_statusbar()
        self._connect()

        QTimer.singleShot(120, self._bootstrap)

    # ------------------------------------------------------------------
    # Construccion
    # ------------------------------------------------------------------
    def _build_viewer(self) -> None:
        """Visor 3D con su barra de camara y seleccion."""
        from PySide6.QtWidgets import QVBoxLayout

        container = QWidget()
        self.viewer = Viewer3D(container)
        self.viewer_bar = ViewerBar(container)

        lay = QVBoxLayout(container)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.viewer_bar)
        lay.addWidget(self.viewer.widget, 1)
        self.setCentralWidget(container)

    def _build_panels(self) -> None:
        self.explorer = ExplorerPanel()
        self.design_panel = DesignPanel()
        self.charge_panel = ChargePanel()
        self.timing_panel = TimingPanel()
        self.results_panel = ResultsPanel()
        self.properties_panel = PropertiesPanel()
        self.optimize_panel = OptimizePanel()
        self.console = ConsolePanel()
        self.holes_table = HoleTablePanel()

        self.dock_explorer = self._dock("Explorador", self.explorer,
                                        Qt.DockWidgetArea.LeftDockWidgetArea, 270)
        self.dock_design = self._dock("Diseno", self.design_panel,
                                      Qt.DockWidgetArea.LeftDockWidgetArea, 340)
        self.dock_charge = self._dock("Carga", self.charge_panel,
                                      Qt.DockWidgetArea.LeftDockWidgetArea, 340)
        self.dock_timing = self._dock("Secuencia", self.timing_panel,
                                      Qt.DockWidgetArea.LeftDockWidgetArea, 340)
        self.tabifyDockWidget(self.dock_design, self.dock_charge)
        self.tabifyDockWidget(self.dock_charge, self.dock_timing)
        self.dock_design.raise_()

        self.dock_results = self._dock("Resultados", self.results_panel,
                                       Qt.DockWidgetArea.RightDockWidgetArea, 460)
        self.dock_properties = self._dock("Propiedades", self.properties_panel,
                                          Qt.DockWidgetArea.RightDockWidgetArea, 400)
        self.dock_optimize = self._dock("Optimizacion", self.optimize_panel,
                                        Qt.DockWidgetArea.RightDockWidgetArea, 520)
        self.tabifyDockWidget(self.dock_results, self.dock_properties)
        self.tabifyDockWidget(self.dock_properties, self.dock_optimize)
        self.dock_results.raise_()

        self.dock_console = self._dock("Bitacora", self.console,
                                       Qt.DockWidgetArea.BottomDockWidgetArea, 0, 170)
        self.dock_holes = self._dock("Taladros", self.holes_table,
                                     Qt.DockWidgetArea.BottomDockWidgetArea, 0, 170)
        self.tabifyDockWidget(self.dock_console, self.dock_holes)
        self.dock_console.raise_()
        self._fix_dock_tabs()

    def _fix_dock_tabs(self) -> None:
        """Evita que Qt recorte los nombres de las pestanas de los paneles."""
        for bar in self.findChildren(QTabBar):
            bar.setElideMode(Qt.TextElideMode.ElideNone)
            bar.setUsesScrollButtons(True)
            bar.setExpanding(False)

    def _dock(self, title: str, widget: QWidget, area, min_width: int = 0,
              min_height: int = 0) -> QDockWidget:
        dock = QDockWidget(title, self)
        dock.setObjectName(f"dock_{title.lower()}")
        dock.setWidget(widget)
        dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable
                         | QDockWidget.DockWidgetFeature.DockWidgetFloatable
                         | QDockWidget.DockWidgetFeature.DockWidgetClosable)
        if min_width:
            dock.setMinimumWidth(min_width)
        if min_height:
            dock.setMinimumHeight(min_height)
        self.addDockWidget(area, dock)
        return dock

    def _build_actions(self) -> None:
        def act(name: str, text: str, icon: str = "", shortcut: str = "",
                tip: str = "", checkable: bool = False) -> QAction:
            a = QAction(text, self)
            if icon:
                a.setIcon(icons.icon(icon, 18))
            if shortcut:
                a.setShortcut(QKeySequence(shortcut))
            a.setToolTip(tip or text)
            a.setStatusTip(tip or text)
            a.setCheckable(checkable)
            setattr(self, f"act_{name}", a)
            return a

        act("home", "Página de inicio", "home", "Ctrl+H",
            "Volver a la pantalla de bienvenida y proyectos recientes")
        act("new", "Nuevo proyecto", "new", "Ctrl+N", "Empezar un diseno en blanco")
        act("open", "Abrir proyecto", "open", "Ctrl+O", "Abrir un proyecto .xbp")
        act("save", "Guardar", "save", "Ctrl+S", "Guardar el proyecto")
        act("save_as", "Guardar como…", "save", "Ctrl+Shift+S")
        act("import_holes", "Importar taladros", "import", "Ctrl+I",
            "Cargar collares o archivo TURPO desde CSV")
        act("import_topo", "Importar topografia", "topo", "",
            "Cargar nube de puntos topografica")
        act("export_holes", "Exportar taladros", "export", "",
            "Exportar la tabla de taladros a CSV")
        act("export_report", "Reporte tecnico", "report", "Ctrl+R",
            "Generar el reporte tecnico completo en HTML")
        act("screenshot", "Captura del visor", "camera", "", "Guardar la vista 3D como PNG")

        act("generate", "Generar malla", "pattern", "F5",
            "Construir la malla con los parametros actuales")
        act("analyze", "Analizar", "analysis", "F6",
            "Ejecutar el analisis completo del diseno")
        act("optimize", "Optimizar", "optimize", "F7",
            "Explorar escenarios y proponer el de menor costo por tonelada")
        act("animate", "Animar secuencia", "run", "F8",
            "Reproducir la secuencia de salida en el visor")

        act("labels", "Etiquetas", "table", "", "Mostrar el identificador de cada taladro", True)
        act("select_all", "Seleccionar todo", "layers", "Ctrl+A")
        act("select_none", "Quitar la seleccion", "new", "Ctrl+D")
        act("invert_selection", "Invertir la seleccion", "import", "Ctrl+Shift+I")
        act("box_selection", "Seleccion por ventana", "grid", "B",
            "Encerrar varios taladros con un rectangulo", True)
        act("reset_charge", "Recargar con la regla global", "reset", "",
            "Descarta la carga manual de los taladros seleccionados")
        act("reset_delays", "Liberar retardos fijados", "timing", "",
            "Devuelve los retardos manuales al amarre automatico")
        act("energy", "Campo de energia", "energy", "",
            "Superponer las isosuperficies de energia", True)
        act("view_iso", "Vista isometrica", "zoom", "Ctrl+1")
        act("view_top", "Planta", "zoom", "Ctrl+2")
        act("view_front", "Perfil frontal", "zoom", "Ctrl+3")
        act("view_side", "Perfil lateral", "zoom", "Ctrl+4")
        act("reset_view", "Encuadrar", "reset", "Ctrl+0")
        act("reset_layout", "Restablecer paneles", "layers")
        act("about", "Acerca de X-BLAST", "info")

    def _build_toolbar(self) -> None:
        tb = QToolBar("Principal")
        tb.setObjectName("toolbar_main")
        tb.setIconSize(tb.iconSize() * 0.95)
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        tb.setMovable(False)
        self.addToolBar(tb)

        tb.addAction(self.act_home)
        tb.addSeparator()
        for a in (self.act_new, self.act_open, self.act_save):
            tb.addAction(a)
        tb.addSeparator()
        tb.addAction(self.act_import_holes)
        tb.addAction(self.act_import_topo)
        tb.addSeparator()
        tb.addAction(self.act_generate)
        tb.addAction(self.act_analyze)
        tb.addAction(self.act_optimize)
        tb.addAction(self.act_animate)
        tb.addSeparator()

        tb.addWidget(QLabel("  Tematizar por  "))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(list(THEMES))
        self.theme_combo.setMinimumWidth(190)
        tb.addWidget(self.theme_combo)

        tb.addAction(self.act_labels)
        tb.addAction(self.act_energy)
        tb.addSeparator()

        tb.addWidget(QLabel("  Asignar tipo  "))
        self.type_combo = QComboBox()
        self.type_combo.addItems([t.value for t in HoleType])
        self.type_combo.setMinimumWidth(130)
        self.type_combo.setToolTip(
            "Tipo que se asignara a los taladros seleccionados")
        tb.addWidget(self.type_combo)
        self.act_assign_type = QAction(icons.icon("check", 18), "Asignar", self)
        self.act_assign_type.setToolTip(
            "Asignar el tipo elegido a los taladros seleccionados")
        self.act_assign_type.triggered.connect(
            lambda: self.assign_type_to_selection(self.type_combo.currentText()))
        tb.addAction(self.act_assign_type)
        tb.addAction(self.act_box_selection)
        tb.addSeparator()
        tb.addAction(self.act_view_iso)
        tb.addAction(self.act_view_top)
        tb.addAction(self.act_reset_view)
        tb.addSeparator()
        tb.addAction(self.act_export_report)

        spacer = QWidget()
        spacer.setSizePolicy(spacer.sizePolicy().horizontalPolicy().Expanding,
                             spacer.sizePolicy().verticalPolicy().Preferred)
        tb.addWidget(spacer)

    def _build_menu(self) -> None:
        m = self.menuBar()

        f = m.addMenu("&Archivo")
        f.addAction(self.act_home)
        f.addSeparator()
        for a in (self.act_new, self.act_open, self.act_save, self.act_save_as):
            f.addAction(a)
        f.addSeparator()
        f.addAction(self.act_import_holes)
        f.addAction(self.act_import_topo)
        f.addSeparator()
        f.addAction(self.act_export_holes)
        f.addAction(self.act_export_report)
        f.addAction(self.act_screenshot)
        f.addSeparator()
        quit_action = QAction("Salir", self)
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.triggered.connect(self.close)
        f.addAction(quit_action)

        d = m.addMenu("&Diseno")
        d.addAction(self.act_generate)
        d.addSeparator()
        d.addAction(self.act_analyze)
        d.addAction(self.act_optimize)
        d.addAction(self.act_animate)

        sel = m.addMenu("&Seleccion")
        for a in (self.act_select_all, self.act_select_none,
                  self.act_invert_selection, self.act_box_selection):
            sel.addAction(a)
        sel.addSeparator()
        self.menu_select_type = sel.addMenu("Seleccionar por tipo")
        for t in HoleType:
            action = QAction(t.value, self)
            action.triggered.connect(
                lambda _c=False, v=t.value: self.select_by_type(v))
            self.menu_select_type.addAction(action)
        sel.addSeparator()
        sel.addAction(self.act_reset_charge)
        sel.addAction(self.act_reset_delays)

        v = m.addMenu("&Ver")
        for a in (self.act_view_iso, self.act_view_top, self.act_view_front,
                  self.act_view_side, self.act_reset_view):
            v.addAction(a)
        v.addSeparator()
        v.addAction(self.act_labels)
        v.addAction(self.act_energy)
        v.addSeparator()
        for dock, key in ((self.dock_explorer, "Ctrl+Alt+1"), (self.dock_design, "Ctrl+Alt+2"),
                          (self.dock_charge, "Ctrl+Alt+3"), (self.dock_timing, "Ctrl+Alt+4"),
                          (self.dock_results, "Ctrl+Alt+5"), (self.dock_properties, "Ctrl+Alt+6"),
                          (self.dock_optimize, "Ctrl+Alt+7"), (self.dock_console, "Ctrl+Alt+8"),
                          (self.dock_holes, "Ctrl+Alt+9")):
            a = dock.toggleViewAction()
            a.setShortcut(QKeySequence(key))
            v.addAction(a)
        v.addSeparator()
        v.addAction(self.act_reset_layout)

        h = m.addMenu("A&yuda")
        h.addAction(self.act_about)

    def _build_statusbar(self) -> None:
        sb = self.statusBar()
        self.status_message = QLabel("Listo")
        self.status_holes = QLabel("—")
        self.status_pf = QLabel("—")
        self.status_ppv = QLabel("—")
        self.status_score = W.StatusChip("Sin analisis", "info")
        self.status_progress = QProgressBar()
        self.status_progress.setFixedWidth(140)
        self.status_progress.setVisible(False)

        self.status_hint = QLabel(
            "Izq: girar · Rueda: zoom · Centro o Shift+Izq: desplazar · Ctrl+Izq: rotar encuadre · Clic: seleccionar")
        self.status_hint.setStyleSheet(
            f"color:{C['text_muted']}; padding:0 10px;")
        sb.addWidget(self.status_message, 1)
        sb.addWidget(self.status_hint)
        sb.addPermanentWidget(self.status_progress)
        for w in (self.status_holes, self.status_pf, self.status_ppv):
            w.setStyleSheet(f"color:{C['text_soft']}; padding:0 10px;"
                            f"border-left:1px solid {C['divider']};")
            sb.addPermanentWidget(w)
        sb.addPermanentWidget(self.status_score)

    def _connect(self) -> None:
        self.act_home.triggered.connect(self.open_start_page)
        self.act_new.triggered.connect(self.new_project)
        self.act_open.triggered.connect(self.open_project)
        self.act_save.triggered.connect(self.save_project)
        self.act_save_as.triggered.connect(lambda: self.save_project(True))
        self.act_import_holes.triggered.connect(lambda: self.import_data("holes"))
        self.act_import_topo.triggered.connect(lambda: self.import_data("topography"))
        self.act_export_holes.triggered.connect(self.export_holes)
        self.act_export_report.triggered.connect(self.export_report)
        self.act_screenshot.triggered.connect(self.save_screenshot)

        self.act_generate.triggered.connect(self.generate_mesh)
        self.act_analyze.triggered.connect(self.run_analysis)
        self.act_optimize.triggered.connect(lambda: self._start_optimization(
            self.optimize_panel.settings()))
        self.act_animate.triggered.connect(self.toggle_animation)

        self.act_labels.toggled.connect(self.viewer.set_labels_visible)
        self.act_energy.toggled.connect(self._toggle_energy)
        self.act_view_iso.triggered.connect(self.viewer.view_iso)
        self.act_view_top.triggered.connect(self.viewer.view_top)
        self.act_view_front.triggered.connect(lambda: self.viewer.view_side("north"))
        self.act_view_side.triggered.connect(lambda: self.viewer.view_side("east"))
        self.act_reset_view.triggered.connect(self.viewer.reset_camera)
        self.act_reset_layout.triggered.connect(self._reset_layout)
        self.act_about.triggered.connect(self._show_about)

        self.theme_combo.currentTextChanged.connect(self.viewer.set_theme)

        self.design_panel.generate_requested.connect(self.generate_mesh)
        self.design_panel.changed.connect(self._on_design_changed)
        self.charge_panel.changed.connect(self._on_charge_changed)
        self.timing_panel.changed.connect(self._on_timing_changed)
        self.timing_panel.animate_requested.connect(self.toggle_animation)

        self.explorer.import_requested.connect(self.import_data)
        self.explorer.hole_selected.connect(self.select_hole)
        self.explorer.layer_toggled.connect(self._on_layer_toggled)
        self.holes_table.selection_changed.connect(self._on_table_selection)
        self.holes_table.export_requested.connect(self.export_holes)

        self.properties_panel.hole_edited.connect(self._on_hole_edited)
        self.properties_panel.charge_edited.connect(self._on_charge_edited)
        self.properties_panel.bulk_type_requested.connect(self.assign_type_to_selection)
        self.properties_panel.bulk_charge_requested.connect(self.copy_charge_to_selection)
        self.properties_panel.reset_charge_requested.connect(self.reset_selection_charge)
        self.properties_panel.zoom_requested.connect(self.viewer.zoom_to_selection)

        self.act_select_all.triggered.connect(self.viewer.select_all)
        self.act_select_none.triggered.connect(self.viewer.clear_selection)
        self.act_invert_selection.triggered.connect(self.viewer.invert_selection)
        self.act_box_selection.toggled.connect(self._on_box_selection)
        self.act_reset_charge.triggered.connect(self.reset_selection_charge)
        self.act_reset_delays.triggered.connect(self.reset_selection_delays)

        self._connect_viewer_bar()

        self.optimize_panel.run_requested.connect(self._start_optimization)
        self.optimize_panel.apply_requested.connect(self._apply_scenario)

        self.viewer.selection_changed.connect(self._on_viewer_selection)
        self.viewer.hole_activated.connect(self._on_hole_activated)
        self.viewer.status_message.connect(self.status_message.setText)
        self.viewer.animation_finished.connect(lambda: self.timing_panel.set_animating(False))

    def _connect_viewer_bar(self) -> None:
        """Enlaza la barra del visor con la camara y la seleccion."""
        bar, viewer = self.viewer_bar, self.viewer
        bar.nav_mode_changed.connect(viewer.set_nav_mode)
        bar.view_requested.connect(viewer.set_standard_view)
        bar.orbit_requested.connect(viewer.orbit)
        bar.roll_requested.connect(viewer.roll)
        bar.dolly_requested.connect(viewer.dolly)
        bar.spin_toggled.connect(viewer.set_spin)
        bar.focus_requested.connect(viewer.focus_on_selection)
        bar.zoom_selection_requested.connect(viewer.zoom_to_selection)
        bar.fit_requested.connect(viewer.reset_camera)
        bar.projection_toggled.connect(self._toggle_projection)
        bar.z_scale_changed.connect(viewer.set_z_exaggeration)
        bar.select_all_requested.connect(viewer.select_all)
        bar.invert_selection_requested.connect(viewer.invert_selection)
        bar.clear_selection_requested.connect(viewer.clear_selection)
        bar.box_selection_toggled.connect(self.act_box_selection.setChecked)

    # ------------------------------------------------------------------
    # Navegación y Arranque
    # ------------------------------------------------------------------
    def open_start_page(self) -> None:
        """Regresa a la página de inicio minimalista."""
        if not self._confirm_discard():
            return
        from .start_page import StartWindow
        self.start_window = StartWindow()
        self.start_window.project_selected.connect(self._on_start_page_project_selected)
        self.start_window.show()
        self.close()

    def _on_start_page_project_selected(self, mode: str, path: str) -> None:
        new_win = MainWindow(initial_mode=mode, initial_path=path)
        new_win.show()

    def _bootstrap(self) -> None:
        """Inicializa la sesión según el modo seleccionado en la página de inicio."""
        self.log(f"{__appname__} {__version__} iniciado.", "OK")
        self._fix_dock_tabs()

        from .start_page import RecentProjectsManager, find_data_file

        if self.initial_mode == "turpo":
            turpo = find_data_file("datos TURPO.csv")
            if turpo:
                self._import_holes(turpo)
                RecentProjectsManager.add_recent(turpo)
            else:
                self.generate_mesh(announce=False)
        elif self.initial_mode == "topo_mine":
            topo = find_data_file("Topografia.csv")
            coords = find_data_file("Coordenadas.csv")
            if topo:
                self._import_topography(topo)
                RecentProjectsManager.add_recent(topo)
            if coords:
                self._import_holes(coords)
                RecentProjectsManager.add_recent(coords)
            if not topo and not coords:
                self.generate_mesh(announce=False)
        elif (self.initial_mode == "file" or self.initial_mode == "open_file") and self.initial_path:
            p = self.initial_path
            if p.suffix.lower() == project_io.PROJECT_EXT:
                self.load_project_file(p)
            elif "topo" in p.stem.lower():
                self._import_topography(p)
            else:
                self._import_holes(p)
            RecentProjectsManager.add_recent(p)
        else:
            self.generate_mesh(announce=False)

        self.viewer.view_iso()
        self._report_selection([])
        self.log(
            "Visor: arrastrar con el botón izquierdo gira, la rueda acerca, el botón central o Shift+izquierdo desplaza y Ctrl+izquierdo rota el encuadre. Un clic sin arrastrar selecciona el taladro.", "INFO")
        self._dirty = False

    # ------------------------------------------------------------------
    # Diseno
    # ------------------------------------------------------------------
    def _collect_design(self) -> BlastDesign:
        """Actualiza el modelo con lo que muestran los paneles."""
        self.design.pattern = self.design_panel.geometry.params()
        self.design.rock = self.design_panel.rock.rock()
        self.design.constraints = self.design_panel.site.constraints()
        self.design.timing = self.timing_panel.params()

        rule = self.charge_panel.rule()
        self.design.pattern.stemming_m = rule.stemming_m
        self.design.column_explosive = rule.column_explosive
        self.design.bottom_explosive = rule.bottom_explosive
        self.design.bottom_charge_m = rule.bottom_charge_m
        self.design.primer_type = rule.primer_type
        self.design.stemming_material = rule.stemming_material
        self.design_panel.geometry.set_stemming(rule.stemming_m)
        return self.design

    def generate_mesh(self, announce: bool = True) -> None:
        """Construye la malla parametrica y la carga en el visor."""
        d = self._collect_design()
        elevation = None
        if d.topography is not None and len(d.topography) >= 3:
            elevation = loaders.elevation_interpolator(d.topography)

        d.holes = pattern_mod.generate_pattern(
            d.pattern, self.design_panel.geometry.hole_type.currentText(), elevation)
        d.free_face = pattern_mod.free_face_from_pattern(d.pattern)
        charging.apply_charge(d.holes, self.charge_panel.rule())

        self._refresh_scene(reset_camera=True)
        if announce:
            self.log(f"Malla generada: {len(d.holes)} taladros "
                     f"(B = {d.pattern.burden_m:.2f} m, S = {d.pattern.spacing_m:.2f} m, "
                     f"{d.pattern.pattern.lower()}).", "OK")
        self._dirty = True
        self.run_analysis()

    def _refresh_scene(self, reset_camera: bool = False) -> None:
        """Reconstruye la escena 3D y los paneles que dependen de la malla.

        El refresco toca el explorador de capas, cuyas senales podrian volver a
        pedir un refresco; el guardia corta esa realimentacion.
        """
        if self._refreshing:
            return
        self._refreshing = True
        try:
            self._rebuild_scene(reset_camera)
        finally:
            self._refreshing = False

    def _rebuild_scene(self, reset_camera: bool) -> None:
        d = self.design
        self.viewer.build(
            d.holes,
            topography=d.topography if self.explorer.layer_state("topography") else None,
            free_face=d.free_face if self.explorer.layer_state("free_face") else None,
            show_labels=self.act_labels.isChecked(),
            show_bench=self.explorer.layer_state("bench"),
            reset_camera=reset_camera)
        self.viewer.set_theme(self.theme_combo.currentText())

        self.explorer.set_holes(d.holes)
        self.explorer.set_layer_available("topography", d.topography is not None)
        self.holes_table.set_holes(d.holes)
        if d.holes:
            self.charge_panel.set_reference_hole(copy.deepcopy(d.holes[len(d.holes) // 2]))
        self.status_holes.setText(f"{len(d.holes)} taladros")

    # ------------------------------------------------------------------
    # Analisis
    # ------------------------------------------------------------------
    def run_analysis(self) -> None:
        """Lanza el analisis en segundo plano sobre una copia del diseno.

        El motor anota resultados en los propios taladros, asi que el hilo
        trabaja sobre una copia y la interfaz adopta esos taladros al terminar:
        nunca hay dos calculos escribiendo el mismo objeto. Si ya hay uno en
        curso se encola uno solo, que se dispara al finalizar.
        """
        d = self._collect_design()
        if not d.holes:
            return
        if self._busy:
            self._analysis_queued = True
            return

        charging.apply_charge(d.holes, self.charge_panel.rule())
        self._set_busy(True, "Analizando el diseno…")
        target = self.optimize_panel.target_p80.value()
        self._task = tasks.analysis_task(copy.deepcopy(d), target,
                                        compute_energy=True, parent=self)
        self._task.finished.connect(self._on_analysis_done)
        self._task.failed.connect(self._on_task_failed)
        self._task.start()

    def _on_analysis_done(self, analysis: BlastAnalysis) -> None:
        self._set_busy(False)
        self.analysis = analysis
        # El hilo trabajo sobre una copia: adoptamos sus taladros, que ya traen
        # burden real, retardos, volumenes y fragmentacion por taladro.
        self.design.holes = analysis.design.holes
        self.design.free_face = analysis.design.free_face
        target = self.optimize_panel.target_p80.value()

        self.results_panel.update_results(analysis, target)
        self.holes_table.set_holes(self.design.holes)
        self.explorer.set_holes(self.design.holes)

        k = analysis.kpis
        edges, weights = timing_histogram(self.design.holes,
                                          self.design.timing.cooperation_window_ms)
        w_max = max_charge_for_ppv(
            k.get("receptor_distance_m", 100.0), self.design.constraints.ppv_limit_mm_s,
            self.design.constraints.k_site, self.design.constraints.beta_site)
        self.timing_panel.update_results(
            analysis.timing_stats, analysis.cooperation, analysis.overlap,
            edges, weights, w_max)

        self.viewer.set_theme(self.theme_combo.currentText())
        if self.act_energy.isChecked():
            self.viewer.show_energy_field(analysis.energy_field)

        level = "ok" if analysis.score >= 85 else ("warn" if analysis.score >= 60 else "error")
        self.status_score.set_status(f"Calidad {analysis.score}/100", level)
        self.status_pf.setText(f"FP {k['powder_factor']:.3f} kg/m3")
        self.status_ppv.setText(f"PPV {k['ppv_mm_s']:.1f} mm/s")
        self.explorer.set_summary(
            f"{k['n_holes']} taladros · {k['tonnes']:,.0f} t · "
            f"X50 {k['x50_cm']:.0f} cm · {k['cost_total_usd_t']:.2f} USD/t")

        self.log(f"Analisis completo: X50 {k['x50_cm']:.1f} cm, "
                 f"P80 {k['p80_cm']:.1f} cm, PPV {k['ppv_mm_s']:.1f} mm/s, "
                 f"costo total {k['cost_total_usd_t']:.3f} USD/t. "
                 f"Calidad {analysis.score}/100 "
                 f"({len(analysis.errors)} criticos, {len(analysis.warnings)} avisos).",
                 "CALCULO")
        for f in analysis.errors:
            self.log(f"{f['item']}: {f['message']}", "ERROR")

        selection = self.viewer.selection()
        if selection:
            active = next((h for h in self.design.holes if h.hid == selection[0]), None)
            self.properties_panel.show_hole(active, selection)
            self.holes_table.set_selection(selection)

        if self._analysis_queued:
            self._analysis_queued = False
            QTimer.singleShot(0, self.run_analysis)

    # ------------------------------------------------------------------
    # Optimizacion
    # ------------------------------------------------------------------
    def _start_optimization(self, settings: Dict) -> None:
        d = self._collect_design()
        if not d.holes:
            return
        n = settings["n_steps"] * len(settings["sb_ratios"])
        self.optimize_panel.set_running(True, 0, n)
        self.dock_optimize.raise_()
        self._set_busy(True, f"Evaluando {n} escenarios…")

        self._task = tasks.optimization_task(d, self.charge_panel.rule(), settings, parent=self)
        self._task.finished.connect(self._on_optimization_done)
        self._task.failed.connect(self._on_task_failed)
        self._task.start()

    def _on_optimization_done(self, result) -> None:
        self._set_busy(False)
        self.optimize_panel.set_result(result)
        best = result.best
        if best:
            self.log(f"Optimizacion: {len(result.feasible)}/{len(result.scenarios)} escenarios "
                     f"viables. Mejor: B = {best.burden_m:.2f} m, S = {best.spacing_m:.2f} m, "
                     f"{best.cost_total_usd_t:.3f} USD/t "
                     f"({result.savings_usd_t():+.3f} USD/t frente al diseno actual).", "CALCULO")

    def _apply_scenario(self, scenario: Scenario) -> None:
        """Lleva al diseno los parametros del escenario elegido."""
        p = self.design_panel.geometry.params()
        p.burden_m = scenario.burden_m
        p.spacing_m = scenario.spacing_m
        p.stemming_m = scenario.stemming_m
        p.subdrill_m = pattern_mod.konya_subdrill(scenario.burden_m)
        area_x = self.design.pattern.spacing_m * self.design.pattern.cols
        area_y = self.design.pattern.burden_m * self.design.pattern.rows
        p.rows = max(1, int(round(area_y / p.burden_m)))
        p.cols = max(1, int(round(area_x / p.spacing_m)))

        self.design_panel.geometry.set_params(p)
        rule = self.charge_panel.rule()
        rule.stemming_m = scenario.stemming_m
        self.charge_panel.set_rule(rule)

        self.log(f"Escenario aplicado: B = {p.burden_m:.2f} m, S = {p.spacing_m:.2f} m, "
                 f"taco = {p.stemming_m:.2f} m.", "OK")
        self.generate_mesh()

    # ------------------------------------------------------------------
    # Datos
    # ------------------------------------------------------------------
    def import_data(self, kind: str) -> None:
        titles = {"holes": "Importar taladros (collares o TURPO)",
                  "topography": "Importar topografia"}
        start = _first_existing_dir()
        path, _ = QFileDialog.getOpenFileName(
            self, titles.get(kind, "Importar"), str(start),
            "Archivos CSV (*.csv *.txt);;Todos los archivos (*)")
        if not path:
            return

        try:
            if kind == "holes":
                self._import_holes(Path(path))
            else:
                self._import_topography(Path(path))
        except Exception as exc:
            QMessageBox.critical(self, "No se pudo importar", str(exc))
            self.log(f"Error al importar {Path(path).name}: {exc}", "ERROR")

    def _import_holes(self, path: Path) -> None:
        p = self.design_panel.geometry.params()
        holes, report = loaders.load_holes(
            path, default_diameter_mm=p.diameter_mm,
            default_length_m=p.hole_length_m, default_subdrill_m=p.subdrill_m,
            hole_type=self.design_panel.geometry.hole_type.currentText())
        if not holes:
            raise ValueError("El archivo no contiene taladros validos.")

        d = self.design
        d.holes = holes
        if d.topography is not None:
            elevation = loaders.elevation_interpolator(d.topography)
            for h in d.holes:
                z = elevation(h.easting, h.northing)
                if np.isfinite(z):
                    h.collar_z = float(z)

        d.free_face = loaders.free_face_from_holes(holes, p.face_azimuth_deg)
        charging.apply_charge(d.holes, self.charge_panel.rule())

        # Encuadra el origen de la malla parametrica sobre los datos importados
        p.origin_x = float(np.mean([h.easting for h in holes]))
        p.origin_y = float(np.mean([h.northing for h in holes]))
        p.origin_z = float(np.mean([h.collar_z for h in holes]))
        self.design_panel.geometry.set_params(p)

        self._refresh_scene(reset_camera=True)
        self.log(f"Taladros importados desde {report['file']}: {report['rows_read']} filas"
                 + (f", {report['rows_skipped']} descartadas" if report["rows_skipped"] else "")
                 + (f", longitud deducida en {report['derived_length']}"
                    if report["derived_length"] else "") + ".", "OK")
        from .start_page import RecentProjectsManager
        RecentProjectsManager.add_recent(path)
        self.run_analysis()

    def _import_topography(self, path: Path) -> None:
        pts, report = loaders.load_topography(path)
        self.design.topography = pts
        self.explorer.set_layer_available("topography", True)
        self.explorer.set_layer_state("topography", True)

        if self.design.holes:
            elevation = loaders.elevation_interpolator(pts)
            pattern_mod.apply_topography(self.design.holes, elevation)
            charging.apply_charge(self.design.holes, self.charge_panel.rule())

        self._refresh_scene(reset_camera=True)
        z0, z1 = report["z_range"]
        self.log(f"Topografia importada desde {report['file']}: {report['points']} puntos, "
                 f"cotas {z0:.1f} a {z1:.1f} m.", "OK")
        from .start_page import RecentProjectsManager
        RecentProjectsManager.add_recent(path)
        self.run_analysis()

    def export_holes(self) -> None:
        if not self.design.holes:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar taladros", f"taladros_{_slug(self.design.name)}.csv",
            "Archivo CSV (*.csv)")
        if path:
            out = project_io.export_holes_csv(self.design.holes, path)
            self.log(f"Taladros exportados a {out.name}.", "OK")

    def export_report(self) -> None:
        if self.analysis is None:
            QMessageBox.information(self, "Reporte", "Ejecute primero el analisis.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar reporte tecnico", f"reporte_{_slug(self.design.name)}.html",
            "Documento HTML (*.html)")
        if not path:
            return
        out = build_report(self.analysis, Path(path))
        self.log(f"Reporte generado: {out.name}", "OK")
        QMessageBox.information(
            self, "Reporte generado",
            f"El reporte se guardo en:\n{out}\n\nAbralo con el navegador; desde alli "
            "puede imprimirlo o exportarlo a PDF.")

    def save_screenshot(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar captura", f"vista_{_slug(self.design.name)}.png",
            "Imagen PNG (*.png)")
        if path:
            self.viewer.screenshot(path)
            self.log(f"Captura guardada: {Path(path).name}", "OK")

    # ------------------------------------------------------------------
    # Proyecto
    # ------------------------------------------------------------------
    def new_project(self) -> None:
        if not self._confirm_discard():
            return
        self.design = BlastDesign(name="Voladura sin titulo")
        self.analysis = None
        self.project_path = None
        self.results_panel.update_results(None)
        self.properties_panel.show_hole(None)
        self.optimize_panel.set_result(None)
        self.generate_mesh()
        self.log("Proyecto nuevo.", "INFO")

    def load_project_file(self, path: Path) -> bool:
        """Carga un archivo de proyecto .xbp y actualiza la interfaz."""
        try:
            self.design = project_io.load(path)
        except Exception as exc:
            QMessageBox.critical(self, "No se pudo abrir", str(exc))
            return False

        self.project_path = Path(path)
        self.design_panel.geometry.set_params(self.design.pattern)
        self.design_panel.rock.set_rock(self.design.rock)
        self.design_panel.site.set_constraints(self.design.constraints)
        self.timing_panel.set_params(self.design.timing)
        self.charge_panel.set_rule(ChargeRule(
            column_explosive=self.design.column_explosive,
            bottom_explosive=self.design.bottom_explosive,
            bottom_charge_m=self.design.bottom_charge_m,
            stemming_m=self.design.pattern.stemming_m,
            primer_type=self.design.primer_type,
            stemming_material=self.design.stemming_material))

        self._refresh_scene(reset_camera=True)
        self._dirty = False
        self.setWindowTitle(f"{__appname__} {__version__} — {self.design.name}")
        self.log(f"Proyecto abierto: {self.project_path.name} "
                 f"({len(self.design.holes)} taladros).", "OK")
        from .start_page import RecentProjectsManager
        RecentProjectsManager.add_recent(self.project_path)
        self.run_analysis()
        return True

    def open_project(self) -> None:
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir proyecto", "", f"Proyecto X-BLAST (*{project_io.PROJECT_EXT})")
        if not path:
            return
        self.load_project_file(Path(path))

    def save_project(self, ask_path: bool = False) -> None:
        path = self.project_path
        if ask_path or path is None:
            chosen, _ = QFileDialog.getSaveFileName(
                self, "Guardar proyecto", f"{_slug(self.design.name)}{project_io.PROJECT_EXT}",
                f"Proyecto X-BLAST (*{project_io.PROJECT_EXT})")
            if not chosen:
                return
            path = Path(chosen)

        self._collect_design()
        self.project_path = project_io.save(self.design, path)
        self._dirty = False
        self.setWindowTitle(f"{__appname__} {__version__} — {self.project_path.stem}")
        self.log(f"Proyecto guardado en {self.project_path.name}.", "OK")
        from .start_page import RecentProjectsManager
        RecentProjectsManager.add_recent(self.project_path)

    def _confirm_discard(self) -> bool:
        if not self._dirty:
            return True
        answer = QMessageBox.question(
            self, "Cambios sin guardar",
            "El proyecto tiene cambios sin guardar. ¿Desea continuar y descartarlos?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        return answer == QMessageBox.StandardButton.Yes

    def closeEvent(self, event) -> None:
        if self._confirm_discard():
            event.accept()
        else:
            event.ignore()

    # ------------------------------------------------------------------
    # Interaccion
    # ------------------------------------------------------------------
    def select_hole(self, hid: str) -> None:
        """Selecciona un unico taladro desde el explorador o la bitacora."""
        self.viewer.set_selection([hid])

    def selected_holes(self) -> List[Hole]:
        """Taladros del diseno actualmente seleccionados en el visor."""
        chosen = set(self.viewer.selection())
        return [h for h in self.design.holes if h.hid in chosen]

    def _on_viewer_selection(self, hids: List[str]) -> None:
        """Propaga al resto de la interfaz la seleccion hecha en el visor."""
        if self._syncing_selection:
            return
        self._syncing_selection = True
        try:
            self.holes_table.set_selection(hids)
            active = next((h for h in self.design.holes if h.hid == hids[0]), None) \
                if hids else None
            self.properties_panel.show_hole(active, hids)
        finally:
            self._syncing_selection = False
        self._report_selection(hids)

    def _on_table_selection(self, hids: List[str]) -> None:
        """Selecciona en el visor lo que se marca en la tabla de taladros."""
        if self._syncing_selection:
            return
        self._syncing_selection = True
        try:
            self.viewer.set_selection(hids, notify=False)
            active = next((h for h in self.design.holes if h.hid == hids[0]), None) \
                if hids else None
            self.properties_panel.show_hole(active, hids)
        finally:
            self._syncing_selection = False
        self._report_selection(hids)

    def _report_selection(self, hids: List[str]) -> None:
        holes = self.selected_holes()
        for action in (self.act_reset_charge, self.act_reset_delays,
                       self.act_assign_type):
            action.setEnabled(bool(holes))
        if not holes:
            self.status_message.setText("Listo")
            return
        if len(holes) == 1:
            h = holes[0]
            self.status_message.setText(
                f"Taladro {h.hid} · {h.hole_type} · {h.charge_kg:,.1f} kg · "
                f"{h.delay_ms:,.0f} ms · burden {h.burden_real_m:.2f} m")
            self.dock_properties.raise_()
        else:
            carga = sum(h.charge_kg for h in holes)
            self.status_message.setText(
                f"{len(holes)} taladros seleccionados · {carga:,.0f} kg de explosivo")

    def _on_hole_activated(self, hid: str) -> None:
        """Doble clic sobre un taladro: lo encuadra y abre su ficha."""
        self.viewer.set_selection([hid])
        self.viewer.focus_on_selection()
        self.dock_properties.raise_()

    def select_by_type(self, hole_type: str) -> None:
        self.viewer.select_by(lambda h: h.hole_type == hole_type)

    def _on_box_selection(self, enabled: bool) -> None:
        self.viewer.set_box_selection(enabled)
        self.viewer_bar.set_box_checked(enabled)

    def _toggle_projection(self) -> None:
        self.viewer.toggle_parallel_projection()
        self.viewer_bar.set_projection_checked(self.viewer.is_parallel_projection())

    # ------------------------------------------------------------------
    # Edicion de taladros
    # ------------------------------------------------------------------
    def _on_hole_edited(self, hid: str) -> None:
        """Un taladro cambio de tipo, geometria o retardo."""
        self._dirty = True
        self._refresh_scene()
        self.viewer.set_selection(self.viewer.selection(), notify=False)
        self.run_analysis()

    def _on_charge_edited(self, hid: str) -> None:
        """Se edito la columna de carga del taladro activo."""
        hole = next((h for h in self.design.holes if h.hid == hid), None)
        if hole is None:
            return
        charging.set_column(hole, self.properties_panel.pending_decks())
        self._dirty = True
        self._refresh_scene()
        self.log(f"Carga manual en el taladro {hid}: "
                 f"{hole.charge_kg:,.1f} kg en {hole.charge_length_m:.2f} m.", "INFO")
        self.run_analysis()

    def assign_type_to_selection(self, hole_type: str) -> None:
        """Reclasifica todos los taladros seleccionados."""
        holes = self.selected_holes()
        if not holes:
            self.log("No hay taladros seleccionados.", "AVISO")
            return
        for h in holes:
            h.hole_type = hole_type
        self._dirty = True
        self._refresh_scene()
        self.viewer.set_selection([h.hid for h in holes], notify=False)
        self.log(f"{len(holes)} taladro(s) reclasificados como {hole_type}.", "OK")
        self.run_analysis()

    def copy_charge_to_selection(self, source_hid: str) -> None:
        """Replica la columna del taladro activo sobre toda la seleccion."""
        source = next((h for h in self.design.holes if h.hid == source_hid), None)
        holes = [h for h in self.selected_holes() if h.hid != source_hid]
        if source is None or not holes:
            return
        import copy as _copy
        for h in holes:
            charging.set_column(h, [_copy.deepcopy(d) for d in source.decks])
        self._dirty = True
        self._refresh_scene()
        self.log(f"Columna de {source_hid} copiada a {len(holes)} taladro(s).", "OK")
        self.run_analysis()

    def reset_selection_charge(self) -> None:
        """Devuelve la seleccion a la regla global de carguio."""
        holes = self.selected_holes() or self.design.holes
        n = charging.unlock_charge(holes, self.charge_panel.rule())
        self._dirty = True
        self._refresh_scene()
        self.log(f"{n} taladro(s) recargados con la regla global.", "OK")
        self.run_analysis()

    def reset_selection_delays(self) -> None:
        """Libera los retardos fijados a mano."""
        holes = self.selected_holes() or self.design.holes
        n = timing_core.clear_delay_locks(holes)
        self._dirty = True
        self.log(f"{n} retardo(s) devueltos al amarre automatico.", "OK")
        self.run_analysis()

    def toggle_animation(self) -> None:
        if self.viewer.is_animating():
            self.viewer.stop_animation()
            self.timing_panel.set_animating(False)
            self.log("Animacion detenida.", "INFO")
        else:
            self.viewer.start_animation()
            self.timing_panel.set_animating(True)
            self.log(f"Reproduciendo la secuencia: "
                     f"{self.design.timing.pattern}, "
                     f"{self.analysis.kpis['total_duration_ms']:,.0f} ms de duracion."
                     if self.analysis else "Reproduciendo la secuencia.", "INFO")

    def _toggle_energy(self, enabled: bool) -> None:
        if enabled and self.analysis is not None:
            self.viewer.show_energy_field(self.analysis.energy_field)
            cov = self.analysis.energy_coverage
            if cov:
                self.log(f"Campo de energia: {cov.get('in_range_pct', 0):.0f}% del volumen "
                         f"dentro del rango objetivo, {cov.get('under_pct', 0):.0f}% por debajo, "
                         f"{cov.get('over_pct', 0):.0f}% por encima.", "CALCULO")
        else:
            self.viewer.hide_energy_field()

    def _on_layer_toggled(self, key: str, visible: bool) -> None:
        if key == "labels":
            self.act_labels.setChecked(visible)
        elif key == "energy":
            self.act_energy.setChecked(visible)
        else:
            self._refresh_scene()

    def _on_design_changed(self) -> None:
        self._dirty = True
        self.status_message.setText("Parametros modificados — pulse Generar malla (F5).")

    def _on_charge_changed(self) -> None:
        self._dirty = True
        self.design_panel.geometry.set_stemming(self.charge_panel.rule().stemming_m)
        if self.design.holes:
            charging.apply_charge(self.design.holes, self.charge_panel.rule())
            self._refresh_scene()
            self.run_analysis()

    def _on_timing_changed(self) -> None:
        self._dirty = True
        if self.design.holes:
            self.run_analysis()

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    def log(self, message: str, level: str = "INFO") -> None:
        self.console.log(message, level)
        if level in ("ERROR", "AVISO"):
            self.dock_console.raise_()

    def _set_busy(self, busy: bool, message: str = "") -> None:
        self._busy = busy
        self.status_progress.setVisible(busy)
        self.status_progress.setRange(0, 0 if busy else 1)
        self.status_message.setText(message or "Listo")
        for a in (self.act_analyze, self.act_optimize, self.act_generate):
            a.setEnabled(not busy)

    def _on_task_failed(self, message: str) -> None:
        self._set_busy(False)
        self._analysis_queued = False
        self.optimize_panel.set_running(False)
        self.log("El calculo fallo:\n" + message.strip().splitlines()[-1], "ERROR")
        QMessageBox.critical(self, "Error durante el calculo", message)

    def _reset_layout(self) -> None:
        for dock in (self.dock_explorer, self.dock_design, self.dock_charge,
                     self.dock_timing, self.dock_results, self.dock_properties,
                     self.dock_optimize, self.dock_console, self.dock_holes):
            dock.setFloating(False)
            dock.setVisible(True)
        self.dock_design.raise_()
        self.dock_results.raise_()
        self.dock_console.raise_()
        self.log("Disposicion de paneles restablecida.", "INFO")

    def _show_about(self) -> None:
        QMessageBox.about(
            self, f"Acerca de {__appname__}",
            f"<h3>{__appname__} {__version__}</h3>"
            f"<p>{__tagline__}</p>"
            "<p>Plataforma de diseno, simulacion y optimizacion de voladura de rocas: "
            "geometria 3D de mallas, columna de carga por plataformas, secuencia de "
            "salida, fragmentacion Kuz-Ram / Swebrec, vibraciones por superposicion, "
            "onda aerea, proyeccion, campo de energia y optimizacion economica "
            "mina-planta.</p>"
            "<p style='color:#5a6673'>Facultad de Ingenieria de Minas · "
            "Universidad Nacional del Altiplano — Puno</p>")


def _first_existing_dir() -> Path:
    base = Path(__file__).resolve().parents[2]
    for name in DATA_DIRS:
        candidate = (base / name).resolve()
        if candidate.is_dir():
            return candidate
    return base


def _slug(text: str) -> str:
    keep = [c if c.isalnum() else "_" for c in text.strip().lower()]
    return "".join(keep).strip("_") or "voladura"
