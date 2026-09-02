"""Punto de entrada de la aplicacion X-BLAST."""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_package_on_path() -> None:
    """Permite ejecutar ``python xblast/app.py`` sin instalar el paquete."""
    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def main() -> int:
    _ensure_package_on_path()

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    from xblast import __appname__, __version__
    from xblast.ui import icons
    from xblast.ui.main_window import MainWindow
    from xblast.ui.theme import FONT_FAMILY, FONT_SIZE, stylesheet

    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
    app = QApplication(sys.argv)
    app.setApplicationName(__appname__)
    app.setApplicationVersion(__version__)
    app.setOrganizationName("UNA Puno - FIM")
    app.setStyle("Fusion")
    app.setFont(QFont(FONT_FAMILY, FONT_SIZE))
    app.setStyleSheet(stylesheet())
    app.setWindowIcon(icons.app_icon())

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
