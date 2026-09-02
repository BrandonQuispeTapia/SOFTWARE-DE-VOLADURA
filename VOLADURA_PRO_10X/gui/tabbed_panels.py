import math
from PySide6.QtWidgets import (
    QTabWidget, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QGroupBox, QDoubleSpinBox, QSpinBox, QComboBox, QPushButton,
    QLabel, QLineEdit, QDateTimeEdit, QTextEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QCheckBox, QScrollArea, QFrame,
    QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QDateTime
from PySide6.QtGui import QFont

SS = """
QDoubleSpinBox, QSpinBox {
    background-color: #0F172A;
    border: 1px solid #334155;
    border-radius: 5px;
    padding: 8px 10px;
    color: #F8FAFC;
    font-size: 10pt;
}
QDoubleSpinBox:hover, QSpinBox:hover { border: 1px solid #475569; }
QDoubleSpinBox:focus, QSpinBox:focus { border: 1px solid #00F0FF; }
"""
CS = """
QComboBox {
    background-color: #0F172A;
    border: 1px solid #334155;
    border-radius: 5px;
    padding: 8px 10px;
    color: #F8FAFC;
    font-size: 10pt;
}
QComboBox:hover { border: 1px solid #475569; }
QComboBox:focus { border: 1px solid #00F0FF; }
"""
GS = """
QGroupBox {
    border: 1px solid #1E293B;
    border-radius: 8px;
    margin-top: 14px;
    font-weight: 600;
    color: #94A3B8;
    padding-top: 18px;
    background-color: rgba(15, 23, 42, 140);
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
    color: #38BDF8;
    font-size: 9pt;
    letter-spacing: 1px;
}
"""
LE = """
QLineEdit {
    background-color: #0F172A;
    border: 1px solid #334155;
    border-radius: 5px;
    padding: 8px 10px;
    color: #F8FAFC;
    font-size: 10pt;
}
QLineEdit:hover { border: 1px solid #475569; }
QLineEdit:focus { border: 1px solid #00F0FF; }
"""

def _mspin(mn, mx, d, st, sfx, dec=1):
    s = QDoubleSpinBox(); s.setRange(mn, mx); s.setValue(d); s.setSingleStep(st); s.setDecimals(dec); s.setSuffix(sfx); s.setStyleSheet(SS); return s

def _combo(items):
    c = QComboBox(); c.addItems(items); c.setStyleSheet(CS); return c

def _line(ph=""):
    e = QLineEdit(); e.setPlaceholderText(ph); e.setStyleSheet(LE); return e


class ProjectMetadataTab(QWidget):
    metadata_changed = Signal(dict)
    def __init__(self):
        super().__init__()
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        content = QWidget(); layout = QVBoxLayout(content); layout.setSpacing(10); layout.setContentsMargins(4,4,4,20)

        t = QLabel("DATOS DEL PROYECTO"); t.setStyleSheet("color:#00f0ff;font-size:13pt;font-weight:bold;padding:4px;"); layout.addWidget(t)

        f = QFormLayout(); f.setSpacing(10)
        self.proj = _line("Nombre del proyecto/disparo"); self.proj.setText("TAJO PRINCIPAL - BANCO 2425")
        self.company = _line("Razon social"); self.company.setText("Minera UNA Puno S.A.")
        self.mine = _line("Nombre de la mina/sector"); self.mine.setText("Mina Puno - Sector Norte")
        self.resp = _line("Ingeniero responsable"); self.resp.setText("Ing. Felix Fernando Bautista Layme")
        self.ops = _line("Operador(es) de voladura"); self.ops.setText("Op. Juan Perez, Op. Carlos Lopez")
        self.labor = _line("Labor / Nivel / Zona"); self.labor.setText("Nivel 2425 - Zona Norte")
        self.shift = _combo(["Diurno (06:00-18:00)", "Nocturno (18:00-06:00)", "Continuo (24h)"])
        self.date = QDateTimeEdit(QDateTime.currentDateTime()); self.date.setDisplayFormat("yyyy-MM-dd HH:mm"); self.date.setCalendarPopup(True)
        self.coord_e = _mspin(100000, 999999, 580000.0, 1, " mE", 0); self.coord_e.setPrefix("E: ")
        self.coord_n = _mspin(8000000, 9999999, 8520000.0, 1, " mN", 0); self.coord_n.setPrefix("N: ")
        self.coord_z = _mspin(3000, 5000, 4250.0, 1, " m", 0); self.coord_z.setPrefix("Z: ")
        self.geom_type = _combo(["Cuadrada", "Rectangular", "Tresbolillo", "Escalonada"])
        self.hole_type = _combo(["Produccion", "Precorte", "Corte", "Descabezado", "Horizontal"])
        self.mrw = _line("Mineral / Rocca / Relleno"); self.mrw.setText("Diorita - RMR 65")
        self.license = _line("Nro. Licencia / Permisos"); self.license.setText("LPV-2026-001")
        self.weather = _combo(["Seco", "Lluvioso", "Humedo", "Congelado"])
        self.obs = QTextEdit(); self.obs.setMaximumHeight(60); self.obs.setPlaceholderText("Observaciones adicionales...")

        for lbl, w in [("Proyecto:", self.proj), ("Compania:", self.company), ("Mina/Sector:", self.mine),
                       ("Ingeniero:", self.resp), ("Operadores:", self.ops), ("Labor/Nivel:", self.labor),
                       ("Turno:", self.shift), ("Fecha Disparo:", self.date),
                       ("Coordenada E:", self.coord_e), ("Coordenada N:", self.coord_n), ("Elevacion Z:", self.coord_z),
                       ("Tipo Malla:", self.geom_type), ("Tipo Taladro:", self.hole_type),
                       ("Mineral/Roca:", self.mrw), ("Licencia:", self.license),
                       ("Clima:", self.weather), ("Observaciones:", self.obs)]:
            f.addRow(lbl, w)
        g = QGroupBox("Metadatos del Disparo"); g.setLayout(f); g.setStyleSheet(GS); layout.addWidget(g)
        self.status = QLabel("DATOS OBLIGATORIOS PARA REPORTE PDF"); self.status.setStyleSheet("color:#f59e0b;font-style:italic;padding:4px;")
        layout.addWidget(self.status)

        for w in [self.proj, self.company, self.mine, self.resp, self.ops, self.labor, self.mrw, self.license]:
            w.textChanged.connect(self._emit)
        scroll.setWidget(content)
        sl = QVBoxLayout(self); sl.setContentsMargins(0,0,0,0); sl.addWidget(scroll)
        # Emitir metadata inicial
        self._emit()

    def _emit(self): self.metadata_changed.emit(self.get_metadata())
    def get_metadata(self):
        return {"project": self.proj.text(), "company": self.company.text(), "mine": self.mine.text(),
                "responsable": self.resp.text(), "operators": self.ops.text(), "labor": self.labor.text(),
                "shift": self.shift.currentText(), "date": self.date.dateTime().toString("yyyy-MM-dd HH:mm"),
                "coord_e": self.coord_e.value(), "coord_n": self.coord_n.value(), "coord_z": self.coord_z.value(),
                "geom_type": self.geom_type.currentText(), "hole_type": self.hole_type.currentText(),
                "mineral": self.mrw.text(), "license": self.license.text(),
                "weather": self.weather.currentText(), "obs": self.obs.toPlainText()}


class GeometryTab(QWidget):
    parameters_changed = Signal(dict)
    topo_loaded = Signal(object)
    coords_loaded = Signal(object)

    def __init__(self):
        super().__init__()
        self.topo_file = ""
        self.coords_file = ""
        self.turpo_file = ""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        content = QWidget(); layout = QVBoxLayout(content); layout.setSpacing(10); layout.setContentsMargins(4,4,4,12)

        t = QLabel("GEOMETRIA DE MALLA"); t.setStyleSheet("color:#00f0ff;font-size:13pt;font-weight:bold;padding:4px;"); layout.addWidget(t)

        f = QFormLayout(); f.setSpacing(10)
        self.burden = _mspin(1, 25, 4.5, 0.1, " m")
        self.spacing = _mspin(1, 25, 5.0, 0.1, " m")
        self.diameter = _mspin(50, 500, 102, 1, " mm", 0)
        self.bench = _mspin(2, 50, 12, 0.5, " m")
        self.subdrill = _mspin(0, 10, 1, 0.1, " m")
        self.angle = _mspin(0, 45, 0, 1, " \u00b0", 0)
        self.azimuth = _mspin(0, 360, 0, 5, " \u00b0", 0)
        self.rows = QSpinBox(); self.rows.setRange(1, 50); self.rows.setValue(5); self.rows.setSuffix(" filas"); self.rows.setStyleSheet(SS)
        self.cols = QSpinBox(); self.cols.setRange(1, 80); self.cols.setValue(8); self.cols.setSuffix(" cols"); self.cols.setStyleSheet(SS)
        self.area_w = _mspin(10, 500, 50, 1, " m"); self.area_h = _mspin(10, 500, 80, 1, " m")

        for lbl, w in [("Burden (B):", self.burden), ("Espaciamiento (S):", self.spacing),
                       ("Diametro Taladro:", self.diameter), ("Altura Banco:", self.bench),
                       ("Subperforacion:", self.subdrill), ("Angulo Inclinacion:", self.angle),
                       ("Azimuth Cara Libre:", self.azimuth), ("Filas:", self.rows), ("Columnas:", self.cols),
                       ("Ancho Area (m):", self.area_w), ("Largo Area (m):", self.area_h)]:
            f.addRow(lbl, w)
        g1 = QGroupBox("Parametros Geometricos"); g1.setLayout(f); g1.setStyleSheet(GS); layout.addWidget(g1)

        self.btn_konya = QPushButton("CALCULAR B/S AUTOMATICO (Konya-Ash)"); self.btn_konya.setMinimumHeight(36)
        self.btn_konya.setStyleSheet("QPushButton{background-color:#6366f1;color:white;font-weight:bold;border-radius:5px;}QPushButton:hover{background-color:#818cf8;}")
        self.btn_konya.clicked.connect(self._konya)
        layout.addWidget(self.btn_konya)
        self.kinfo = QLabel(""); self.kinfo.setStyleSheet("color:#00ff41;font-family:'Courier New';font-size:9pt;padding:4px;"); layout.addWidget(self.kinfo)

        q_box = QGroupBox("CARGA RÁPIDA DE PROYECTOS"); q_box.setStyleSheet(GS)
        qv = QVBoxLayout()
        self.btn_load_turpo = QPushButton("⭐ CARGAR PROYECTO TURPO (228 TALADROS)")
        self.btn_load_turpo.setStyleSheet("QPushButton{background-color:#1e3a8a;color:#38bdf8;border:1px solid #3b82f6;border-radius:5px;padding:8px;font-weight:bold;}QPushButton:hover{background-color:#1d4ed8;color:white;}")
        self.btn_load_topo_mine = QPushButton("🏔️ CARGAR TOPOGRAFÍA Y TALADROS MINA")
        self.btn_load_topo_mine.setStyleSheet("QPushButton{background-color:#064e3b;color:#34d399;border:1px solid #10b981;border-radius:5px;padding:8px;font-weight:bold;}QPushButton:hover{background-color:#047857;color:white;}")
        self.btn_clear_to_parametric = QPushButton("📐 RESTABLECER MALLA PARAMÉTRICA")
        self.btn_clear_to_parametric.setStyleSheet("QPushButton{background-color:#334155;color:#e2e8f0;border-radius:5px;padding:6px;font-size:9pt;}QPushButton:hover{background-color:#475569;}")
        qv.addWidget(self.btn_load_turpo)
        qv.addWidget(self.btn_load_topo_mine)
        qv.addWidget(self.btn_clear_to_parametric)
        q_box.setLayout(qv)
        layout.addWidget(q_box)

        self.btn_load_turpo.clicked.connect(self._quick_load_turpo)
        self.btn_load_topo_mine.clicked.connect(self._quick_load_topo_mine)
        self.btn_clear_to_parametric.clicked.connect(self._reset_to_parametric)

        imp = QGroupBox("IMPORTAR MANUALMENTE CSV / DXF"); imp.setStyleSheet(GS)
        iv = QHBoxLayout()
        self.btn_topo = QPushButton("TOPOGRAFIA"); self.btn_coords = QPushButton("COORDENADAS")
        self.btn_taladros = QPushButton("TALADROS (TURPO)"); self.btn_dxf = QPushButton("DXF")
        for b in [self.btn_topo, self.btn_coords, self.btn_taladros, self.btn_dxf]:
            b.setStyleSheet("QPushButton{background-color:#0d9488;color:white;border-radius:4px;padding:8px;font-weight:bold;}QPushButton:hover{background-color:#14b8a6;}")
            iv.addWidget(b)
        imp.setLayout(iv); layout.addWidget(imp)
        self.btn_topo.clicked.connect(self._import_topo)
        self.btn_coords.clicked.connect(self._import_coords)
        self.btn_taladros.clicked.connect(self._import_turpo)

        og = QGroupBox("ORIGEN DE MALLA"); og.setStyleSheet(GS); of = QFormLayout()
        self.origin_x = _mspin(-999999, 999999, 0, 1, " m", 0)
        self.origin_y = _mspin(-999999, 999999, 0, 1, " m", 0)
        of.addRow("Origen X:", self.origin_x); of.addRow("Origen Y:", self.origin_y)
        og.setLayout(of); layout.addWidget(og)

        status_row = QHBoxLayout()
        self.status_topo = QLabel("TOPOGRAFIA: Sin cargar")
        self.status_topo.setStyleSheet("color:#f59e0b;font-style:italic;padding:4px;")
        self.status_coords = QLabel("COORDENADAS: Sin cargar")
        self.status_coords.setStyleSheet("color:#f59e0b;font-style:italic;padding:4px;")
        status_row.addWidget(self.status_topo)
        status_row.addWidget(self.status_coords)
        layout.addLayout(status_row)

        for w in [self.burden, self.spacing, self.diameter, self.bench, self.subdrill, self.angle, self.azimuth, self.rows, self.cols, self.area_w, self.area_h]:
            try: w.valueChanged.connect(self._emit)
            except: pass
        scroll.setWidget(content)

        main_layout.addWidget(scroll, 1)

        self.btn_render = QPushButton("GENERAR MALLA 3D"); self.btn_render.setMinimumHeight(44)
        self.btn_render.setStyleSheet("QPushButton{background-color:#00a8ff;color:#09090b;font-weight:bold;font-size:11pt;border-radius:6px;border:none;}QPushButton:hover{background-color:#00f0ff;}")
        main_layout.addWidget(self.btn_render)

    def _quick_load_turpo(self):
        from pathlib import Path
        for cand in [Path("datos TURPO.csv"), Path("data/datos TURPO.csv"), Path("../data/datos TURPO.csv"), Path("../datos TURPO.csv")]:
            if cand.exists():
                self.turpo_file = str(cand.resolve())
                self.coords_file = ""
                self.status_coords.setText(f"TURPO OK: {cand.name}")
                self.status_coords.setStyleSheet("color:#22c55e;font-weight:bold;padding:4px;")
                self.coords_loaded.emit(self.turpo_file)
                self.btn_render.click()
                return
        self._import_turpo()

    def _quick_load_topo_mine(self):
        from pathlib import Path
        for cand in [Path("Topografia.csv"), Path("data/Topografia.csv"), Path("../data/Topografia.csv"), Path("../Topografia.csv")]:
            if cand.exists():
                self.topo_file = str(cand.resolve())
                self.status_topo.setText(f"TOPO OK: {cand.name}")
                self.status_topo.setStyleSheet("color:#22c55e;font-weight:bold;padding:4px;")
                self.topo_loaded.emit(self.topo_file)
                break
        for cand in [Path("Coordenadas.csv"), Path("data/Coordenadas.csv"), Path("../data/Coordenadas.csv"), Path("../Coordenadas.csv")]:
            if cand.exists():
                self.coords_file = str(cand.resolve())
                self.turpo_file = ""
                self.status_coords.setText(f"COORDS OK: {cand.name}")
                self.status_coords.setStyleSheet("color:#22c55e;font-weight:bold;padding:4px;")
                self.coords_loaded.emit(self.coords_file)
                break
        self.btn_render.click()

    def _reset_to_parametric(self):
        self.turpo_file = ""
        self.coords_file = ""
        self.topo_file = ""
        self.status_coords.setText("COORDENADAS: Sin cargar")
        self.status_coords.setStyleSheet("color:#f59e0b;font-style:italic;padding:4px;")
        self.status_topo.setText("TOPOGRAFIA: Sin cargar")
        self.status_topo.setStyleSheet("color:#f59e0b;font-style:italic;padding:4px;")
        self.btn_render.click()

    def _konya(self):
        de = self.diameter.value()
        B = 0.012 * (2.0 * 1.15 / 2.6 + 1.5) * de
        S = B * 1.25
        self.burden.setValue(round(B, 2)); self.spacing.setValue(round(S, 2))
        self.kinfo.setText(f"Konya: B={B:.2f}m S={S:.2f}m (rho_exp=1.15, rho_rock=2.6)")

    def _import_turpo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Importar Taladros TURPO", "",
            "CSV TURPO (*.csv);;Todos (*)"
        )
        if path:
            self.turpo_file = path
            self.coords_file = ""
            self.status_coords.setText(f"TURPO OK: {path.split('/')[-1].split(chr(92))[-1]}")
            self.status_coords.setStyleSheet("color:#22c55e;font-weight:bold;padding:4px;")
            self.coords_loaded.emit(path)
            self.btn_render.click()

    def _import_topo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Importar Topografia CSV", "",
            "CSV Topografia (*.csv);;Todos (*)"
        )
        if path:
            self.topo_file = path
            self.status_topo.setText(f"TOPO OK: {path.split('/')[-1].split(chr(92))[-1]}")
            self.status_topo.setStyleSheet("color:#22c55e;font-weight:bold;padding:4px;")
            self.topo_loaded.emit(path)
            self.btn_render.click()

    def _import_coords(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Importar Coordenadas de Taladros", "",
            "CSV Coordenadas (*.csv);;Todos (*)"
        )
        if path:
            self.coords_file = path
            self.turpo_file = ""
            self.status_coords.setText(f"COORDS OK: {path.split('/')[-1].split(chr(92))[-1]}")
            self.status_coords.setStyleSheet("color:#22c55e;font-weight:bold;padding:4px;")
            self.coords_loaded.emit(path)
            self.btn_render.click()

    def _emit(self): self.parameters_changed.emit(self.get_params())
    def get_params(self):
        return {"burden_m": self.burden.value(), "spacing_m": self.spacing.value(), "diameter_mm": self.diameter.value(),
                "bench_height_m": self.bench.value(), "subdrilling_m": self.subdrill.value(), "angle_deg": self.angle.value(),
                "azimuth": self.azimuth.value(), "num_rows": self.rows.value(), "num_cols": self.cols.value(),
                "area_w": self.area_w.value(), "area_h": self.area_h.value(),
                "topo_file": self.topo_file, "coords_file": self.coords_file,
                "turpo_file": self.turpo_file,
                "mesh_origin_x": self.origin_x.value(), "mesh_origin_y": self.origin_y.value()}


class PrimerLoadingTab(QWidget):
    loading_config_changed = Signal(dict)
    def __init__(self):
        super().__init__()
        self.selected_hole = None
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        content = QWidget(); layout = QVBoxLayout(content); layout.setSpacing(8)

        self.hl = QLabel("NINGUN TALADRO SELECCIONADO"); self.hl.setStyleSheet("color:#ff8800;font-weight:bold;font-size:11pt;padding:4px;")
        layout.addWidget(self.hl)

        tg = QGroupBox("TIPO DE TALADRO"); tg.setStyleSheet(GS); tf = QFormLayout()
        self.hole_type = _combo(["PRODUCCION", "PRECORTE", "CORTE", "DESCABEZADO", "HORIZONTAL", "ARRANQUE", "AYUDA", "CUADRADOR", "CORONA", "ARRASTRE", "ALIVIO"])
        tf.addRow("Tipo:", self.hole_type); tg.setLayout(tf); layout.addWidget(tg)

        bg = QGroupBox("CEBO / BOOSTER / INICIACION"); bg.setStyleSheet(GS); bf = QFormLayout()
        self.boost_type = _combo(["Pentolita 150g", "Pentolita 450g", "Pentolita 600g", "Dinamita 50g", "Dinamita 100g", "Dinamita 200g", "RDX/TNT 500g", "RDX/TNT 1000g", "PRIMER 25g", "PRIMER 100g", "PowerGel Magnum 400g", "PowerGel Magnum 800g", "Emulex 500g", "Emulex 1000g"])
        self.boost_pos = _combo(["Fondo del Taladro", "Medio del Taladro", "Superficie (Collar)", "Posicion Custom"])
        self.boost_depth = _mspin(0, 50, 0, 0.5, " m")
        self.init_system = _combo(["NONEL (Detonador No-Electrico)", "Detonador Electronico", "Mecha Lenta", "Mecha Rapida", "Cordel Detonante", "Sistema Inalambrico"])
        self.init_delay = _combo(["Instantaneo (0 ms)", "MicroRetardo (25 ms)", "Retardo Corto (100 ms)", "Retardo Largo (500 ms)", "Programable (1-1000 ms)"])
        bf.addRow("Tipo Cebo:", self.boost_type); bf.addRow("Posicion:", self.boost_pos)
        bf.addRow("Profundidad Cebo:", self.boost_depth)
        bf.addRow("Sistema Iniciacion:", self.init_system); bf.addRow("Retardo Iniciador:", self.init_delay)
        bg.setLayout(bf); layout.addWidget(bg)

        cg = QGroupBox("CARGA DE COLUMNA"); cg.setStyleSheet(GS); cf = QFormLayout()
        self.col_exp = _combo(["ANFO Pesado (HA 46)", "ANFO Estandar", "ANFO + Emulsion 50/50", "Emulsion Bombeable", "Emulsion Sensibilizada", "Emulsion a Granel", "PowerGel / Gelatina", "Slurry", "Dynamite Emulsionada", "Emulsion Cebada (Deck Charge)", "ANFO Aluminizado", "Emulsion Heavy ANFO", "Hidrogel", "Black Powder"])
        self.col_len = _mspin(0.1, 50, 8, 0.1, " m")
        self.stem_mat = _combo(["Arena Seca", "Grava", "Polvillo", "Material Triturado", "Crusher Dust", "Clay", "Hormigon", "Chips de Roca"])
        self.stem_len = _mspin(0.5, 15, 3, 0.1, " m")
        self.density = _mspin(0.5, 2.0, 1.15, 0.01, " g/cc")
        self.vod = _mspin(2000, 8000, 5200, 100, " m/s", 0)
        self.rws = QSpinBox(); self.rws.setRange(60, 150); self.rws.setValue(100); self.rws.setSuffix(" %"); self.rws.setStyleSheet(SS)
        cf.addRow("Explosivo:", self.col_exp); cf.addRow("Longitud Columna:", self.col_len)
        cf.addRow("Material Taco:", self.stem_mat); cf.addRow("Longitud Taco:", self.stem_len)
        cf.addRow("Densidad:", self.density); cf.addRow("VOD:", self.vod); cf.addRow("RWS:", self.rws)
        cg.setLayout(cf); layout.addWidget(cg)

        dg = QGroupBox("DECKS (Cargas Espaciadas)"); dg.setStyleSheet(GS)
        dv = QVBoxLayout()
        self.deck_table = QTableWidget(0, 6); self.deck_table.setHorizontalHeaderLabels(["#", "Explosivo", "Inicio (m)", "Fin (m)", "Taco (m)", "Kg"])
        self.deck_table.horizontalHeader().setStretchLastSection(True); self.deck_table.setMaximumHeight(150)
        dv.addWidget(self.deck_table)
        dh_btns = QHBoxLayout()
        self.btn_add = QPushButton("+ Deck"); self.btn_rm = QPushButton("- Deck")
        for b in [self.btn_add, self.btn_rm]: b.setStyleSheet("QPushButton{background-color:#1e293b;color:#94a3b8;border:1px solid #334155;border-radius:4px;padding:6px;}QPushButton:hover{border-color:#00f0ff;color:#00f0ff;}")
        self.btn_add.clicked.connect(self._add_deck); self.btn_rm.clicked.connect(self._rm_deck)
        dh_btns.addWidget(self.btn_add); dh_btns.addWidget(self.btn_rm); dv.addLayout(dh_btns)
        dg.setLayout(dv); layout.addWidget(dg)

        self.btn_preview = QPushButton("VISTA PREVIA DE CARGA"); self.btn_preview.setStyleSheet("QPushButton{background-color:#0ea5e9;color:white;font-weight:bold;border-radius:5px;}QPushButton:hover{background-color:#38bdf8;}")
        layout.addWidget(self.btn_preview)
        self.preview_label = QLabel(""); self.preview_label.setStyleSheet("color:#00ff41;font-family:'Courier New';font-size:9pt;white-space:pre;"); layout.addWidget(self.preview_label)
        self.btn_preview.clicked.connect(self._update_preview)

        scroll.setWidget(content)
        sl = QVBoxLayout(self); sl.setContentsMargins(0,0,0,0); sl.setSpacing(0)
        sl.addWidget(scroll, 1)

        self.btn_aplicar = QPushButton("APLICAR CARGA AL TALADRO"); self.btn_aplicar.setMinimumHeight(44)
        self.btn_aplicar.setStyleSheet("QPushButton{background-color:#059669;color:white;font-weight:bold;border-radius:6px;}QPushButton:hover{background-color:#10b981;}")
        sl.addWidget(self.btn_aplicar)
        self.btn_aplicar.clicked.connect(self._emit)

    def _add_deck(self):
        r = self.deck_table.rowCount(); self.deck_table.insertRow(r)
        for c, txt in enumerate([str(r+1), "ANFO Pesado", "0.0", "5.0", "1.5", "12.5"]):
            self.deck_table.setItem(r, c, QTableWidgetItem(txt))
        self._update_preview()

    def _rm_deck(self):
        if self.deck_table.rowCount() > 0: self.deck_table.removeRow(self.deck_table.rowCount() - 1)

    def _update_preview(self):
        exp = self.col_exp.currentText()[:15]
        cl = self.col_len.value(); sl = self.stem_len.value()
        hd = self.hole_type.currentText()
        bt = self.boost_type.currentText()[:12]
        lines = [f"  TALADRO [{hd}]  Explosivo: {exp}", f"  {'='*45}", f"  Superficie  |  TACO {sl:.1f}m [{self.stem_mat.currentText()}]"]
        depth = sl
        for r in range(self.deck_table.rowCount()):
            ini = float(self.deck_table.item(r, 2).text()) if self.deck_table.item(r, 2) else 0
            fin = float(self.deck_table.item(r, 3).text()) if self.deck_table.item(r, 3) else 5
            stk = float(self.deck_table.item(r, 4).text()) if self.deck_table.item(r, 4) else 1.5
            lines.append(f"  {'-'*45}")
            lines.append(f"  Carga {r+1}: {fin-ini:.1f}m [{self.deck_table.item(r,1).text()[:15]}]")
            lines.append(f"  {'='*45}")
            lines.append(f"  TACO INTERMEDIO {stk:.1f}m")
        lines.append(f"  {'='*45}")
        lines.append(f"  Carga Col: {cl:.1f}m [{exp}]")
        lines.append(f"  Cebo: {bt} @ {self.boost_pos.currentText()}")
        lines.append(f"  Fondo  |  {self.hole_type.currentText()}")
        self.preview_label.setText("\n".join(lines))

    def select_hole(self, hole_id):
        self.selected_hole = hole_id
        self.hl.setText(f"TALADRO #{hole_id} - EDITANDO CARGA")
        self.hl.setStyleSheet("color:#00f0ff;font-weight:bold;font-size:11pt;padding:4px;")

    def _emit(self): self.loading_config_changed.emit(self.get_config())
    def get_config(self):
        decks = []
        for r in range(self.deck_table.rowCount()):
            decks.append({"explosive": self.deck_table.item(r,1).text() if self.deck_table.item(r,1) else "",
                          "start": self.deck_table.item(r,2).text() if self.deck_table.item(r,2) else "0",
                          "end": self.deck_table.item(r,3).text() if self.deck_table.item(r,3) else "5",
                          "stemming": self.deck_table.item(r,4).text() if self.deck_table.item(r,4) else "1.5",
                          "kg": self.deck_table.item(r,5).text() if self.deck_table.item(r,5) else "0"})
        return {"selected_hole": self.selected_hole, "hole_type": self.hole_type.currentText(),
                "booster_type": self.boost_type.currentText(), "booster_position": self.boost_pos.currentText(),
                "booster_depth_m": self.boost_depth.value(),
                "initiation_system": self.init_system.currentText(), "initiation_delay": self.init_delay.currentText(),
                "column_explosive": self.col_exp.currentText(), "column_length_m": self.col_len.value(),
                "stemming_material": self.stem_mat.currentText(), "stemming_length_m": self.stem_len.value(),
                "density": self.density.value(), "vod": self.vod.value(), "rws": self.rws.value(),
                "decks": decks}


class TieUpTab(QWidget):
    sequence_changed = Signal(dict)
    def __init__(self):
        super().__init__()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        content = QWidget(); layout = QVBoxLayout(content); layout.setSpacing(10)

        t = QLabel("AMARRE / SECUENCIA DE DETONACION"); t.setStyleSheet("color:#00f0ff;font-size:13pt;font-weight:bold;padding:4px;"); layout.addWidget(t)

        sg = QGroupBox("Retardos de Superficie"); sg.setStyleSheet(GS); sf = QFormLayout()
        self.surf_delay = _combo(["MS 17 ms", "MS 25 ms", "MS 42 ms", "MS 67 ms", "MS 100 ms", "MS 150 ms", "MS 250 ms", "Electronicos 1 ms (custom)"])
        self.surf_pattern = _combo(["Linea Recta", "V-shape", "Echelon (Escalonado)", "Chevron", "Fan (Abanico)", "Custom"])
        sf.addRow("Tipo Retardo:", self.surf_delay); sf.addRow("Patron Disparo:", self.surf_pattern)
        sg.setLayout(sf); layout.addWidget(sg)

        bg = QGroupBox("Retardos de Fondo (Downhole)"); bg.setStyleSheet(GS); bf = QFormLayout()
        self.btm_delay = _combo(["NONEL 9 ms", "NONEL 17 ms", "NONEL 25 ms", "NONEL 42 ms", "NONEL 67 ms", "Electronico 1 ms"])
        self.hole_int = _mspin(1, 200, 25, 5, " ms", 1)
        self.electronic = QCheckBox("Usar Detonadores Electronicos"); self.electronic.setStyleSheet("color:#e2e8f0;")
        bf.addRow("Tipo Retardo:", self.btm_delay); bf.addRow("Intervalo Taladros:", self.hole_int)
        bf.addRow("", self.electronic); bg.setLayout(bf); layout.addWidget(bg)

        pg = QGroupBox("CONFIGURACION DE AMARRE"); pg.setStyleSheet(GS)
        pv = QVBoxLayout()
        self.tie_table = QTableWidget(0, 5); self.tie_table.setHorizontalHeaderLabels(["Taladro", "Ret. Sup (ms)", "Ret. Fondo (ms)", "Total (ms)", "Estado"])
        self.tie_table.horizontalHeader().setStretchLastSection(True); self.tie_table.setMaximumHeight(200)
        pv.addWidget(self.tie_table)
        self.btn_gen = QPushButton("GENERAR AMARRE"); self.btn_gen.setStyleSheet("QPushButton{background-color:#7c3aed;color:white;font-weight:bold;border-radius:5px;}QPushButton:hover{background-color:#8b5cf8;}")
        self.btn_gen.clicked.connect(self._gen_tie)
        pv.addWidget(self.btn_gen); pg.setLayout(pv); layout.addWidget(pg)

        rg = QGroupBox("DIAGRAMA DE TIEMPOS"); rg.setStyleSheet(GS)
        self.diagram = QTextEdit(); self.diagram.setReadOnly(True); self.diagram.setMaximumHeight(160)
        self.diagram.setStyleSheet("QTextEdit{background-color:#0f172a;color:#00ff41;border:1px solid #334155;font-family:'Courier New';font-size:9pt;}")
        rv = QVBoxLayout(); rv.addWidget(self.diagram); rg.setLayout(rv); layout.addWidget(rg)

        scroll.setWidget(content)
        main_layout.addWidget(scroll, 1)

    def _gen_tie(self):
        iv = self.hole_int.value()
        self.tie_table.setRowCount(0)
        for i in range(1, 21):
            r = self.tie_table.rowCount(); self.tie_table.insertRow(r)
            sf_ms = i * iv; total = sf_ms + 17
            for c, txt in enumerate([str(i), f"{sf_ms:.0f}", "17", f"{total:.0f}", "LISTO"]):
                self.tie_table.setItem(r, c, QTableWidgetItem(txt))
        pat = self.surf_pattern.currentText()
        self.diagram.setText(f"Patron: {pat}\nRet. Superficie: {self.surf_delay.currentText()}\nRet. Fondo: {self.btm_delay.currentText()}\nIntervalo: {iv} ms\n\n{'Taladro':>10} {'Tiempo (ms)':>12} {'Barras'}\n{'-'*50}")
        lines = []
        for i in range(1, 21):
            t = i * iv
            bar = "#" * min(int(t / 10), 30)
            lines.append(f"  T-{i:02d}        {t:8.0f} ms   {bar}")
        self.diagram.setText(self.diagram.toPlainText() + "\n" + "\n".join(lines))
        self._emit()

    def _emit(self): self.sequence_changed.emit(self.get_config())
    def get_config(self):
        return {"surface_delay": self.surf_delay.currentText(), "bottom_delay": self.btm_delay.currentText(),
                "hole_interval_ms": self.hole_int.value(), "pattern": self.surf_pattern.currentText(),
                "electronic": self.electronic.isChecked()}


class ReportingTab(QWidget):
    pdf_requested = Signal()
    simulate_requested = Signal()
    report_executive = Signal()
    report_operational = Signal()
    report_ssoma = Signal()
    report_loading = Signal()
    def __init__(self):
        super().__init__()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        content = QWidget(); layout = QVBoxLayout(content); layout.setSpacing(8)

        t = QLabel("REPORTES Y RESULTADOS"); t.setStyleSheet("color:#F1F5F9;font-size:13pt;font-weight:bold;padding:4px;letter-spacing:1px;"); layout.addWidget(t)

        kg = QGroupBox("DASHBOARD DE KPIs"); kg.setStyleSheet(GS)
        self.kpi = QLabel()
        self.kpi.setWordWrap(True)
        self.kpi.setMinimumHeight(260)
        self.kpi.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.kpi.setStyleSheet("""
            QLabel{
                background-color: #09090B;
                color: #00F0FF;
                border: 1px solid #1E293B;
                border-radius: 6px;
                font-family: 'Cascadia Code', 'Fira Code', 'Courier New', monospace;
                font-size: 9pt;
                padding: 10px;
            }
        """)
        self.kpi.setText("  Genere la malla 3D para ver KPIs.")
        kv = QVBoxLayout(); kv.addWidget(self.kpi); kg.setLayout(kv); layout.addWidget(kg)

        scroll.setWidget(content)
        main_layout.addWidget(scroll, 1)

        sg = QGroupBox("SIMULACION DE VOLADURA"); sg.setStyleSheet(GS); sv = QVBoxLayout()
        self.btn_sim = QPushButton("SIMULAR VOLADURA"); self.btn_sim.setMinimumHeight(48)
        self.btn_sim.setStyleSheet("QPushButton{background-color:#991B1B;color:white;font-weight:bold;font-size:12pt;border-radius:6px;border:1px solid #DC2626;}QPushButton:hover{background-color:#B91C1C;}")
        sv.addWidget(self.btn_sim); sg.setLayout(sv); main_layout.addWidget(sg)

        pg = QGroupBox("TIPOS DE REPORTE"); pg.setStyleSheet(GS); pv = QVBoxLayout()
        self.btn_exec = QPushButton("REPORTE EJECUTIVO (Gerencia)"); self.btn_exec.setStyleSheet("QPushButton{background-color:#9A3412;color:white;font-weight:bold;border-radius:5px;border:1px solid #EA580C;}QPushButton:hover{background-color:#C2410C;}")
        self.btn_oper = QPushButton("REPORTE OPERATIVO (P&V)"); self.btn_oper.setStyleSheet("QPushButton{background-color:#0C4A6E;color:white;font-weight:bold;border-radius:5px;border:1px solid #0EA5E9;}QPushButton:hover{background-color:#075985;}")
        self.btn_ssoma = QPushButton("REPORTE SSOMA (Seguridad)"); self.btn_ssoma.setStyleSheet("QPushButton{background-color:#14532D;color:white;font-weight:bold;border-radius:5px;border:1px solid #16A34A;}QPushButton:hover{background-color:#166534;}")
        self.btn_load = QPushButton("REPORTE DE CARGA (Receta)"); self.btn_load.setStyleSheet("QPushButton{background-color:#4C1D95;color:white;font-weight:bold;border-radius:5px;border:1px solid #7C3AED;}QPushButton:hover{background-color:#5B21B6;}")
        self.btn_all = QPushButton("GENERAR TODOS LOS REPORTES PDF"); self.btn_all.setStyleSheet("QPushButton{background-color:#0F172A;color:#00F0FF;font-weight:bold;font-size:10pt;border:1px solid #00F0FF;border-radius:6px;}QPushButton:hover{background-color:#1E293B;border-color:#38BDF8;}")
        for b in [self.btn_exec, self.btn_oper, self.btn_ssoma, self.btn_load, self.btn_all]: pv.addWidget(b)
        pg.setLayout(pv); main_layout.addWidget(pg)

        self.btn_sim.clicked.connect(self.simulate_requested.emit)
        self.btn_all.clicked.connect(self.pdf_requested.emit)
        self.btn_exec.clicked.connect(self.report_executive.emit)
        self.btn_oper.clicked.connect(self.report_operational.emit)
        self.btn_ssoma.clicked.connect(self.report_ssoma.emit)
        self.btn_load.clicked.connect(self.report_loading.emit)

    def update_kpis(self, kpis):
        lines = []
        lines.append("<pre style='margin:0; line-height:1.5;'>")
        lines.append('<span style="color:#F1F5F9; font-size:10pt; font-weight:bold;">')
        lines.append("  ═══════════════════════════════════════════════════")
        lines.append("  DASHBOARD DE KPIs - X-BLAST v2.0")
        lines.append("  ═══════════════════════════════════════════════════")
        lines.append("</span>")
        lines.append("")
        items = list(kpis.items())
        for i, (k, v) in enumerate(items):
            lines.append(f'  <span style="color:#64748B;">{k}</span>')
            lines.append(f'  <span style="color:#38BDF8; font-weight:bold;">    {v}</span>')
            lines.append("")
        lines.append('<span style="color:#334155;">')
        lines.append("  ═══════════════════════════════════════════════════")
        lines.append("</span>")
        lines.append("</pre>")
        self.kpi.setText("\n".join(lines))


class SciFiTabWidget(QTabWidget):
    def __init__(self):
        super().__init__()
        self.metadata_tab = ProjectMetadataTab()
        self.geometry_tab = GeometryTab()
        self.loading_tab = PrimerLoadingTab()
        self.sequence_tab = TieUpTab()
        self.reporting_tab = ReportingTab()
        self.addTab(self.metadata_tab, "PROYECTO")
        self.addTab(self.geometry_tab, "GEOMETRIA")
        self.addTab(self.loading_tab, "CEBADO/CARGA")
        self.addTab(self.sequence_tab, "AMARRE")
        self.addTab(self.reporting_tab, "REPORTES")
