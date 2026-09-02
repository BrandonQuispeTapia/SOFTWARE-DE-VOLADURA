"""Página de inicio minimalista y profesional de X-BLAST.

Inspirada en las interfaces de bienvenida de ArcGIS Pro, Datamine Studio y
Microsoft Word / Office: diseño limpio en tono blanco, barra lateral de
navegación, plantillas de voladura (malla paramétrica, TURPO 228 taladros,
topografía de mina), lista de proyectos recientes y centro de documentación.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QFrame, QFileDialog, QGridLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPushButton, QScrollArea, QSizePolicy, QSpacerItem, QStackedWidget,
    QTableWidget, QTableWidgetItem, QTextBrowser, QVBoxLayout, QWidget,
)

from .. import __appname__, __tagline__, __version__
from ..dataio import project as project_io
from . import icons
from .theme import C, FONT_FAMILY, FONT_SIZE

DATA_SEARCH_PATHS = [
    Path(__file__).resolve().parent.parent.parent / "data",
    Path(__file__).resolve().parent.parent.parent,
    Path("data"),
    Path("."),
    Path("../data"),
    Path(".."),
]


def find_data_file(name: str) -> Optional[Path]:
    """Busca un archivo de datos en las rutas estándar del proyecto."""
    for base in DATA_SEARCH_PATHS:
        candidate = base / name
        if candidate.exists():
            return candidate.resolve()
    return None


class RecentProjectsManager:
    """Administra la lista persistente de proyectos y archivos recientes."""

    SETTINGS_KEY = "RecentProjects"

    @classmethod
    def get_recent(cls) -> List[dict]:
        settings = QSettings("UNA_Puno_FIM", "X-BLAST")
        raw_list = settings.value(cls.SETTINGS_KEY, [])
        if isinstance(raw_list, str):
            raw_list = [raw_list] if raw_list else []
        elif not isinstance(raw_list, list):
            raw_list = []

        valid_entries = []
        seen = set()

        for item in raw_list:
            p = Path(str(item))
            if p.exists() and str(p.resolve()) not in seen:
                seen.add(str(p.resolve()))
                valid_entries.append(cls._make_entry(p))

        # Si hay menos de 3, sembrar con los datos de ejemplo del repositorio
        seed_candidates = ["datos TURPO.csv", "Topografia.csv", "Coordenadas.csv"]
        for sc in seed_candidates:
            cand = find_data_file(sc)
            if cand and cand.exists() and str(cand.resolve()) not in seen:
                seen.add(str(cand.resolve()))
                valid_entries.append(cls._make_entry(cand, is_sample=True))

        return valid_entries

    @classmethod
    def add_recent(cls, path: Path | str) -> None:
        p = Path(path).resolve()
        if not p.exists():
            return
        settings = QSettings("UNA_Puno_FIM", "X-BLAST")
        raw_list = settings.value(cls.SETTINGS_KEY, [])
        if not isinstance(raw_list, list):
            raw_list = []

        str_path = str(p)
        raw_list = [x for x in raw_list if x != str_path]
        raw_list.insert(0, str_path)
        raw_list = raw_list[:15]  # Conservar los 15 más recientes
        settings.setValue(cls.SETTINGS_KEY, raw_list)

    @staticmethod
    def _make_entry(path: Path, is_sample: bool = False) -> dict:
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime).strftime("%d/%m/%Y %H:%M")
            size_kb = path.stat().st_size / 1024.0
            size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024.0:.2f} MB"
        except Exception:
            mtime = "Reciente"
            size_str = "--"

        ext = path.suffix.lower()
        kind = "Proyecto X-BLAST" if ext == ".xbp" else "Archivo CSV / Datos"
        if "turpo" in path.name.lower():
            kind = "Taladros TURPO (228 tal.)"
        elif "topo" in path.name.lower():
            kind = "Nube Topográfica 3D"
        elif "coord" in path.name.lower():
            kind = "Collares de Taladro"

        return {
            "path": str(path),
            "name": path.name,
            "dir": str(path.parent),
            "date": mtime,
            "size": size_str,
            "kind": kind,
            "is_sample": is_sample,
        }


class TemplateCard(QFrame):
    """Tarjeta interactiva para seleccionar una plantilla de voladura."""

    clicked = Signal()

    def __init__(self, icon_name: str, badge_color: str, tag: str, title: str,
                 subtitle: str, description: str, parent=None):
        super().__init__(parent)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # Alto minimo en vez de fijo: las descripciones se ajustan solas y no
        # quedan cortadas a media frase.
        self.setMinimumHeight(196)

        self.setStyleSheet(f"""
            QFrame {{
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 10px;
            }}
            QFrame:hover {{
                background-color: #FAFCFF;
                border: 1.5px solid #0284C7;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        # Fila superior: Icono en pastilla y tag
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        icon_box = QLabel()
        icon_box.setFixedSize(36, 36)
        icon_box.setStyleSheet(f"""
            background-color: {badge_color};
            border-radius: 8px;
            border: none;
        """)
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_box.setPixmap(icons.pixmap(icon_name, 20, color="#0F172A"))
        top_row.addWidget(icon_box)

        top_row.addStretch(1)

        tag_lbl = QLabel(tag)
        tag_lbl.setStyleSheet("""
            background-color: #F1F5F9;
            color: #475569;
            font-size: 8pt;
            font-weight: 600;
            padding: 3px 8px;
            border-radius: 4px;
            border: 1px solid #E2E8F0;
        """)
        top_row.addWidget(tag_lbl)
        layout.addLayout(top_row)

        # Título y subtítulo
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("""
            color: #0F172A;
            font-size: 11pt;
            font-weight: bold;
            border: none;
            background: transparent;
        """)
        layout.addWidget(title_lbl)

        sub_lbl = QLabel(subtitle)
        sub_lbl.setStyleSheet("""
            color: #0284C7;
            font-size: 8.5pt;
            font-weight: 600;
            border: none;
            background: transparent;
        """)
        layout.addWidget(sub_lbl)

        # Descripción
        desc_lbl = QLabel(description)
        desc_lbl.setWordWrap(True)
        desc_lbl.setSizePolicy(QSizePolicy.Policy.Preferred,
                               QSizePolicy.Policy.MinimumExpanding)
        desc_lbl.setStyleSheet("""
            color: #64748B;
            font-size: 8.5pt;
            border: none;
            background: transparent;
        """)
        # La descripcion se queda con el espacio sobrante: un estirador al final
        # la dejaria con su alto minimo y el texto salia cortado.
        layout.addWidget(desc_lbl, 1)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class StartWindow(QMainWindow):
    """Ventana de inicio minimalista estilo ArcGIS Pro / Datamine / Word."""

    project_selected = Signal(str, str)  # (mode, path)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Inicio — {__appname__} {__version__}")
        self.setWindowIcon(icons.app_icon())
        self.resize(1180, 750)
        self.setMinimumSize(980, 640)

        # Estilo global minimalista en tono blanco
        self.setStyleSheet("""
            QMainWindow {
                background-color: #FFFFFF;
            }
            QWidget {
                font-family: 'Segoe UI', 'Inter', -apple-system, sans-serif;
                color: #0F172A;
            }
            QScrollBar:vertical {
                border: none;
                background: #F8FAFC;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #CBD5E1;
                border-radius: 4px;
                min-height: 25px;
            }
            QScrollBar::handle:vertical:hover {
                background: #94A3B8;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        self._build_ui()
        self._load_recents()
        self._center_on_screen()

    def _center_on_screen(self):
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = (geo.width() - self.width()) // 2
            y = (geo.height() - self.height()) // 2
            self.move(x, y)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_lay = QHBoxLayout(central)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        # 1. Barra lateral izquierda (Navigation Rail)
        sidebar = self._build_sidebar()
        root_lay.addWidget(sidebar)

        # 2. Área central con páginas (Stack)
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background-color: #FFFFFF;")

        self.page_home = self._build_home_page()
        self.page_docs = self._build_docs_page()
        self.page_about = self._build_about_page()

        self.stack.addWidget(self.page_home)
        self.stack.addWidget(self.page_docs)
        self.stack.addWidget(self.page_about)

        root_lay.addWidget(self.stack, 1)

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setFixedWidth(260)
        sidebar.setStyleSheet("""
            QWidget {
                background-color: #F8FAFC;
                border-right: 1px solid #E2E8F0;
            }
        """)

        lay = QVBoxLayout(sidebar)
        lay.setContentsMargins(18, 24, 18, 20)
        lay.setSpacing(12)

        # Branding
        brand_row = QHBoxLayout()
        brand_row.setSpacing(12)

        logo_lbl = QLabel()
        logo_lbl.setFixedSize(40, 40)
        logo_lbl.setStyleSheet("""
            background-color: #0284C7;
            border-radius: 8px;
        """)
        logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_lbl.setPixmap(icons.pixmap("pattern", 24, color="#FFFFFF"))
        brand_row.addWidget(logo_lbl)

        brand_text_lay = QVBoxLayout()
        brand_text_lay.setSpacing(0)
        app_name_lbl = QLabel(__appname__)
        app_name_lbl.setStyleSheet("font-size: 14pt; font-weight: 800; color: #0F172A; letter-spacing: 0.5px;")
        app_sub_lbl = QLabel(f"ENTERPRISE v{__version__}")
        app_sub_lbl.setStyleSheet("font-size: 7.5pt; font-weight: 700; color: #0284C7; letter-spacing: 1px;")
        brand_text_lay.addWidget(app_name_lbl)
        brand_text_lay.addWidget(app_sub_lbl)
        brand_row.addLayout(brand_text_lay)
        lay.addLayout(brand_row)

        lay.addSpacing(16)

        # Botones de navegación
        self.nav_buttons = []

        self.btn_nav_home = self._make_nav_button("home", "Inicio", True)
        self.btn_nav_new = self._make_nav_button("new", "Nuevo Proyecto", False)
        self.btn_nav_open = self._make_nav_button("open", "Abrir Archivo...", False)
        self.btn_nav_docs = self._make_nav_button("doc", "Guía de Usuario", False)
        self.btn_nav_about = self._make_nav_button("info", "Acerca de", False)

        self.btn_nav_home.clicked.connect(lambda: self._set_nav_page(0, self.btn_nav_home))
        self.btn_nav_new.clicked.connect(self._on_new_parametric)
        self.btn_nav_open.clicked.connect(self._on_browse_file)
        self.btn_nav_docs.clicked.connect(lambda: self._set_nav_page(1, self.btn_nav_docs))
        self.btn_nav_about.clicked.connect(lambda: self._set_nav_page(2, self.btn_nav_about))

        for btn in [self.btn_nav_home, self.btn_nav_new, self.btn_nav_open, self.btn_nav_docs, self.btn_nav_about]:
            lay.addWidget(btn)
            self.nav_buttons.append(btn)

        lay.addStretch(1)

        # Sección institucional inferior
        inst_box = QFrame()
        inst_box.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        inst_lay = QVBoxLayout(inst_box)
        inst_lay.setContentsMargins(8, 8, 8, 8)
        inst_lay.setSpacing(3)

        inst_title = QLabel("UNA Puno")
        inst_title.setStyleSheet("font-size: 8.5pt; font-weight: bold; color: #0F172A;")
        inst_sub = QLabel("Facultad de Ingeniería de Minas")
        inst_sub.setStyleSheet("font-size: 7.5pt; color: #64748B;")
        inst_author = QLabel("Félix Fernando Bautista Layme")
        inst_author.setStyleSheet("font-size: 7pt; color: #94A3B8; font-style: italic;")

        inst_lay.addWidget(inst_title)
        inst_lay.addWidget(inst_sub)
        inst_lay.addWidget(inst_author)
        lay.addWidget(inst_box)

        return sidebar

    def _make_nav_button(self, icon_name: str, text: str, active: bool = False) -> QPushButton:
        btn = QPushButton(f"   {text}")
        btn.setIcon(icons.icon(icon_name, 18, color="#0284C7" if active else "#64748B"))
        btn.setIconSize(btn.iconSize())
        btn.setFixedHeight(40)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._apply_nav_style(btn, active)
        return btn

    def _apply_nav_style(self, btn: QPushButton, active: bool):
        if active:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #FFFFFF;
                    color: #0F172A;
                    font-size: 9.5pt;
                    font-weight: 700;
                    text-align: left;
                    padding-left: 14px;
                    border: 1px solid #E2E8F0;
                    border-left: 4px solid #0284C7;
                    border-radius: 6px;
                }
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #475569;
                    font-size: 9.5pt;
                    font-weight: 500;
                    text-align: left;
                    padding-left: 14px;
                    border: none;
                    border-left: 4px solid transparent;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #F1F5F9;
                    color: #0F172A;
                }
            """)

    def _set_nav_page(self, index: int, active_btn: QPushButton):
        self.stack.setCurrentIndex(index)
        for btn in self.nav_buttons:
            self._apply_nav_style(btn, btn == active_btn)

    def _build_home_page(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: #FFFFFF; }")

        content = QWidget()
        content.setStyleSheet("background: #FFFFFF;")
        lay = QVBoxLayout(content)
        lay.setContentsMargins(40, 32, 40, 32)
        lay.setSpacing(24)

        # 1. Cabecera de bienvenida
        header_lay = QVBoxLayout()
        header_lay.setSpacing(4)
        welcome_lbl = QLabel(f"Bienvenido a {__appname__}")
        welcome_lbl.setStyleSheet("font-size: 20pt; font-weight: 800; color: #0F172A;")
        sub_lbl = QLabel("Seleccione una plantilla de inicio o continúe con un proyecto existente.")
        sub_lbl.setStyleSheet("font-size: 10pt; color: #64748B;")
        header_lay.addWidget(welcome_lbl)
        header_lay.addWidget(sub_lbl)
        lay.addLayout(header_lay)

        # 2. Sección: Plantillas
        sec1_title = QLabel("PLANTILLAS Y MODELOS DE VOLADURA")
        sec1_title.setStyleSheet("font-size: 8.5pt; font-weight: 700; color: #64748B; letter-spacing: 1px;")
        lay.addWidget(sec1_title)

        grid = QGridLayout()
        grid.setSpacing(16)

        # Card 1: Paramétrica
        self.card_param = TemplateCard(
            icon_name="grid",
            badge_color="#E0F2FE",
            tag="Nuevo",
            title="Malla Paramétrica",
            subtitle="Banco Estándar",
            description="Diseño regular de voladura con burden, espaciamiento, subperforación y cálculo de Konya."
        )
        self.card_param.clicked.connect(self._on_new_parametric)
        grid.addWidget(self.card_param, 0, 0)

        # Card 2: TURPO
        self.card_turpo = TemplateCard(
            icon_name="cube",
            badge_color="#DCFCE7",
            tag="228 Taladros",
            title="Malla Real TURPO",
            subtitle="Mina en Producción",
            description="Dataset real de 228 taladros en coordenadas UTM con geometría inclinada (Azimuth y Dip)."
        )
        self.card_turpo.clicked.connect(self._on_load_turpo)
        grid.addWidget(self.card_turpo, 0, 1)

        # Card 3: Topo + Mina
        self.card_topo = TemplateCard(
            icon_name="topo",
            badge_color="#FEF3C7",
            tag="3D Delaunay",
            title="Topografía y Mina",
            subtitle="Superficie + Collares",
            description="Malla de terreno 3D triangulada combinada con taladros de perforación en banco."
        )
        self.card_topo.clicked.connect(self._on_load_topo_mine)
        grid.addWidget(self.card_topo, 0, 2)

        # Card 4: Importar
        self.card_import = TemplateCard(
            icon_name="import",
            badge_color="#EDE9FE",
            tag="CSV / TXT",
            title="Importar Archivo",
            subtitle="Datos Externos",
            description="Examinar y cargar archivos externos de coordenadas, collares o levantamientos de mina."
        )
        self.card_import.clicked.connect(self._on_browse_file)
        grid.addWidget(self.card_import, 0, 3)

        lay.addLayout(grid)

        lay.addSpacing(8)

        # 3. Sección: Proyectos Recientes
        recents_header = QHBoxLayout()
        sec2_title = QLabel("ARCHIVOS Y PROYECTOS RECIENTES")
        sec2_title.setStyleSheet("font-size: 8.5pt; font-weight: 700; color: #64748B; letter-spacing: 1px;")
        recents_header.addWidget(sec2_title)
        recents_header.addStretch(1)

        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filtrar archivos recientes...")
        self.filter_input.setFixedWidth(240)
        self.filter_input.setStyleSheet("""
            QLineEdit {
                background-color: #F8FAFC;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 5px 10px;
                font-size: 8.5pt;
            }
            QLineEdit:focus {
                border: 1px solid #0284C7;
                background-color: #FFFFFF;
            }
        """)
        self.filter_input.textChanged.connect(self._filter_recents)
        recents_header.addWidget(self.filter_input)

        btn_browse_recents = QPushButton("Examinar...")
        btn_browse_recents.setStyleSheet("""
            QPushButton {
                background-color: #F1F5F9;
                color: #0F172A;
                font-size: 8.5pt;
                font-weight: 600;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 5px 14px;
            }
            QPushButton:hover {
                background-color: #E2E8F0;
            }
        """)
        btn_browse_recents.clicked.connect(self._on_browse_file)
        recents_header.addWidget(btn_browse_recents)

        lay.addLayout(recents_header)

        # Tabla de recientes estilo Word / ArcGIS
        self.recents_table = QTableWidget()
        self.recents_table.setColumnCount(4)
        self.recents_table.setHorizontalHeaderLabels(["Nombre del Archivo", "Tipo", "Ubicación", "Última Modificación"])
        self.recents_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.recents_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.recents_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.recents_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.recents_table.verticalHeader().setVisible(False)
        self.recents_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.recents_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.recents_table.setShowGrid(False)
        self.recents_table.setAlternatingRowColors(True)
        self.recents_table.setMinimumHeight(240)
        self.recents_table.setStyleSheet("""
            QTableWidget {
                background-color: #FFFFFF;
                alternate-background-color: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                font-size: 9pt;
            }
            QTableWidget::item {
                padding: 10px;
                border-bottom: 1px solid #F1F5F9;
            }
            QTableWidget::item:hover {
                background-color: #F0F9FF;
            }
            QTableWidget::item:selected {
                background-color: #E0F2FE;
                color: #0369A1;
            }
            QHeaderView::section {
                background-color: #F8FAFC;
                color: #64748B;
                font-size: 8pt;
                font-weight: bold;
                border: none;
                border-bottom: 1px solid #CBD5E1;
                padding: 8px 10px;
            }
        """)
        self.recents_table.itemDoubleClicked.connect(self._on_recent_double_clicked)
        lay.addWidget(self.recents_table)

        # 4. Sección inferior: Consejos y Novedades
        tips_row = QHBoxLayout()
        tips_row.setSpacing(16)

        tip1 = self._make_tip_box(
            "cube", "Navegación 3D",
            "Arrastre con el botón izquierdo para girar, rueda para acercar y doble clic para seleccionar un taladro.")
        tip2 = self._make_tip_box(
            "charge", "Carga por plataformas",
            "Editor de columna taladro por taladro: taco, carga de fondo, cámaras de aire y cebado.")
        tip3 = self._make_tip_box(
            "analysis", "Análisis completo",
            "Fragmentación Kuz-Ram y Swebrec, vibraciones, onda aérea, proyección y costo por tonelada.")

        tips_row.addWidget(tip1)
        tips_row.addWidget(tip2)
        tips_row.addWidget(tip3)
        lay.addLayout(tips_row)

        scroll.setWidget(content)
        return scroll

    def _make_tip_box(self, icon_name: str, title: str, text: str) -> QWidget:
        """Tarjeta de consejo con icono vectorial, sin depender de emojis."""
        box = QFrame()
        box.setStyleSheet("""
            QFrame {
                background-color: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(5)

        head = QHBoxLayout()
        head.setSpacing(7)
        glyph = QLabel()
        glyph.setPixmap(icons.pixmap(icon_name, 17, "#1668b3"))
        glyph.setFixedWidth(19)
        glyph.setStyleSheet("background: transparent; border: none;")
        head.addWidget(glyph)

        t = QLabel(title)
        t.setStyleSheet("font-size: 8.5pt; font-weight: bold; color: #0F172A; background: transparent; border: none;")
        head.addWidget(t)
        head.addStretch(1)
        lay.addLayout(head)

        d = QLabel(text)
        d.setWordWrap(True)
        d.setStyleSheet("font-size: 8pt; color: #64748B; background: transparent; border: none;")
        lay.addWidget(d)
        return box

    def _build_docs_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(40, 32, 40, 32)
        lay.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel("Guía de Usuario y Documentación Técnica")
        title.setStyleSheet("font-size: 18pt; font-weight: bold; color: #0F172A;")
        header.addWidget(title)
        header.addStretch(1)

        btn_back = QPushButton("Volver a Inicio")
        btn_back.setIcon(icons.icon("left", 15))
        btn_back.setStyleSheet("""
            QPushButton {
                background-color: #F1F5F9;
                color: #0F172A;
                font-weight: 600;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 6px 14px;
            }
            QPushButton:hover { background-color: #E2E8F0; }
        """)
        btn_back.clicked.connect(lambda: self._set_nav_page(0, self.btn_nav_home))
        header.addWidget(btn_back)
        lay.addLayout(header)

        browser = QTextBrowser()
        browser.setStyleSheet("""
            QTextBrowser {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                padding: 20px;
                font-size: 9.5pt;
                line-height: 1.5;
            }
        """)

        doc_path = Path(__file__).resolve().parent.parent.parent / "docs" / "GUIA_USUARIO.md"
        if doc_path.exists():
            try:
                browser.setMarkdown(doc_path.read_text(encoding="utf-8"))
            except Exception:
                browser.setPlainText(doc_path.read_text(encoding="utf-8", errors="ignore"))
        else:
            browser.setHtml("""
                <h2>X-BLAST Suite v3.0</h2>
                <p>Software para diseño, simulación y optimización de voladuras de rocas.</p>
                <h3>Flujo de Trabajo:</h3>
                <ol>
                    <li><b>Diseño Geométrico:</b> Establecer burden, espaciamiento, subperforación y diámetro.</li>
                    <li><b>Carguío de Explosivos:</b> Definir columnas, tacos y cebado.</li>
                    <li><b>Secuencia y Tiempos:</b> Asignar retardos electrónicos y simular detonación.</li>
                    <li><b>Análisis Físico:</b> Obtener curva granulométrica Kuz-Ram, vibraciones USBM y costos.</li>
                </ol>
            """)
        lay.addWidget(browser)
        return page

    def _build_about_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(60, 48, 60, 48)
        lay.setSpacing(20)

        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 12px;
                padding: 32px;
            }
        """)
        clay = QVBoxLayout(card)
        clay.setSpacing(14)

        title = QLabel(f"{__appname__} Enterprise v{__version__}")
        title.setStyleSheet("font-size: 20pt; font-weight: 800; color: #0F172A;")
        clay.addWidget(title)

        sub = QLabel(__tagline__)
        sub.setStyleSheet("font-size: 11pt; color: #0284C7; font-weight: 600;")
        clay.addWidget(sub)

        clay.addSpacing(10)

        details = QLabel("""
            <b>Institución:</b> Universidad Nacional del Altiplano - Puno (UNA Puno)<br>
            <b>Facultad:</b> Facultad de Ingeniería de Minas (FIM)<br>
            <b>Autor Principal:</b> Félix Fernando Bautista Layme<br>
            <b>Tecnologías:</b> Python 3.10+, PySide6 (Qt 6), PyVista / VTK 3D Engine, NumPy, SciPy, Matplotlib.<br>
            <b>Licencia:</b> Académica / Profesional - Minería e Ingeniería Civil.
        """)
        details.setStyleSheet("font-size: 10pt; color: #475569; line-height: 1.8;")
        clay.addWidget(details)

        clay.addSpacing(16)

        btn_row = QHBoxLayout()
        btn_back = QPushButton("Volver a Inicio")
        btn_back.setStyleSheet("""
            QPushButton {
                background-color: #0284C7;
                color: #FFFFFF;
                font-size: 9.5pt;
                font-weight: 700;
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
            }
            QPushButton:hover { background-color: #0369A1; }
        """)
        btn_back.clicked.connect(lambda: self._set_nav_page(0, self.btn_nav_home))
        btn_row.addWidget(btn_back)
        btn_row.addStretch(1)
        clay.addLayout(btn_row)

        lay.addWidget(card)
        lay.addStretch(1)
        return page

    def _load_recents(self):
        recents = RecentProjectsManager.get_recent()
        self._all_recents = recents
        self._populate_recents_table(recents)

    def _populate_recents_table(self, items: List[dict]):
        self.recents_table.setRowCount(len(items))
        for row, item in enumerate(items):
            # Nombre
            icon_name = "cube" if "turpo" in item["name"].lower() else ("topo" if "topo" in item["name"].lower() else "doc")
            name_item = QTableWidgetItem(item["name"])
            name_item.setIcon(icons.icon(icon_name, 16, color="#0284C7"))
            font = name_item.font()
            font.setBold(True)
            name_item.setFont(font)
            name_item.setData(Qt.ItemDataRole.UserRole, item["path"])

            # Tipo
            kind_item = QTableWidgetItem(item["kind"])
            kind_item.setForeground(QColor("#64748B"))

            # Ruta
            dir_item = QTableWidgetItem(item["dir"])
            dir_item.setForeground(QColor("#94A3B8"))

            # Fecha
            date_item = QTableWidgetItem(item["date"])
            date_item.setForeground(QColor("#64748B"))

            self.recents_table.setItem(row, 0, name_item)
            self.recents_table.setItem(row, 1, kind_item)
            self.recents_table.setItem(row, 2, dir_item)
            self.recents_table.setItem(row, 3, date_item)

    def _filter_recents(self, query: str):
        query = query.strip().lower()
        if not query:
            self._populate_recents_table(self._all_recents)
            return
        filtered = [x for x in self._all_recents if query in x["name"].lower() or query in x["path"].lower() or query in x["kind"].lower()]
        self._populate_recents_table(filtered)

    def _on_recent_double_clicked(self, item: QTableWidgetItem):
        row = item.row()
        name_item = self.recents_table.item(row, 0)
        if name_item:
            file_path = name_item.data(Qt.ItemDataRole.UserRole)
            if file_path and Path(file_path).exists():
                self.project_selected.emit("file", str(file_path))

    def _on_new_parametric(self):
        self.project_selected.emit("parametric", "")

    def _on_load_turpo(self):
        self.project_selected.emit("turpo", "")

    def _on_load_topo_mine(self):
        self.project_selected.emit("topo_mine", "")

    def _on_browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir Proyecto o Archivo de Voladura", "",
            "Archivos de Voladura (*.xbp *.csv *.txt);;Proyectos X-BLAST (*.xbp);;Archivos CSV (*.csv);;Todos (*)"
        )
        if path:
            RecentProjectsManager.add_recent(path)
            self.project_selected.emit("file", path)
