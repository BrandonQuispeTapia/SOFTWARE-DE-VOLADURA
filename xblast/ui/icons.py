"""Iconografia vectorial dibujada en tiempo de ejecucion.

Evita depender de archivos externos: cada icono se dibuja con ``QPainter`` a
partir de una descripcion de trazos, lo que garantiza nitidez en cualquier
factor de escala y permite recolorearlos segun el tema.
"""

from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

from .theme import C

# Cada icono es una lista de primitivas sobre un lienzo normalizado 0..24.
#   ("line", x1, y1, x2, y2)
#   ("rect", x, y, w, h, radio)
#   ("circle", cx, cy, r)
#   ("poly", [(x, y), ...], cerrado)
_SHAPES: Dict[str, List[tuple]] = {
    "new": [("rect", 5, 3, 14, 18, 2), ("line", 8, 9, 16, 9), ("line", 8, 13, 16, 13),
            ("line", 8, 17, 13, 17)],
    "open": [("poly", [(3, 7), (10, 7), (12, 9.5), (21, 9.5), (21, 19), (3, 19)], True)],
    "save": [("poly", [(4, 4), (17, 4), (20, 7), (20, 20), (4, 20)], True),
             ("rect", 8, 4, 8, 6, 1), ("rect", 7, 13, 10, 7, 1)],
    "import": [("line", 12, 3, 12, 14), ("poly", [(8, 10), (12, 14), (16, 10)], False),
               ("poly", [(4, 17), (4, 21), (20, 21), (20, 17)], False)],
    "export": [("line", 12, 14, 12, 3), ("poly", [(8, 7), (12, 3), (16, 7)], False),
               ("poly", [(4, 17), (4, 21), (20, 21), (20, 17)], False)],
    "grid": [("rect", 3, 3, 18, 18, 2), ("line", 9, 3, 9, 21), ("line", 15, 3, 15, 21),
             ("line", 3, 9, 21, 9), ("line", 3, 15, 21, 15)],
    "pattern": [("circle", 6, 6, 1.8), ("circle", 12, 6, 1.8), ("circle", 18, 6, 1.8),
                ("circle", 9, 12, 1.8), ("circle", 15, 12, 1.8),
                ("circle", 6, 18, 1.8), ("circle", 12, 18, 1.8), ("circle", 18, 18, 1.8)],
    "charge": [("rect", 9, 3, 6, 18, 1), ("line", 9, 9, 15, 9), ("line", 9, 15, 15, 15),
               ("circle", 12, 18, 1.4)],
    "timing": [("circle", 12, 13, 8), ("line", 12, 13, 12, 8), ("line", 12, 13, 16, 13),
               ("line", 9, 3, 15, 3)],
    "rock": [("poly", [(3, 19), (8, 8), (14, 12), (18, 5), (21, 19)], True),
             ("line", 8, 8, 14, 12)],
    "analysis": [("line", 3, 21, 21, 21), ("rect", 5, 13, 3.5, 8, 1),
                 ("rect", 10.5, 8, 3.5, 13, 1), ("rect", 16, 4, 3.5, 17, 1)],
    "fragment": [("poly", [(4, 12), (9, 5), (14, 9), (11, 16)], True),
                 ("poly", [(13, 14), (19, 11), (21, 18), (15, 20)], True)],
    "vibration": [("poly", [(2, 12), (5, 12), (7, 5), (10, 19), (13, 8), (16, 15), (18, 12), (22, 12)], False)],
    "energy": [("poly", [(13, 2), (6, 13), (11, 13), (10, 22), (18, 10), (13, 10)], True)],
    "cost": [("circle", 12, 12, 9), ("line", 12, 7, 12, 17),
             ("poly", [(15, 9.5), (9, 9.5), (9, 12), (15, 12), (15, 14.5), (9, 14.5)], False)],
    "optimize": [("line", 3, 20, 21, 20), ("poly", [(4, 17), (9, 9), (14, 13), (20, 4)], False),
                 ("circle", 14, 13, 1.6)],
    "report": [("rect", 5, 3, 14, 18, 2), ("line", 9, 8, 15, 8), ("line", 9, 12, 15, 12),
               ("line", 9, 16, 12, 16)],
    "run": [("poly", [(8, 5), (19, 12), (8, 19)], True)],
    "topo": [("poly", [(2, 18), (8, 9), (12, 14), (17, 6), (22, 18)], False),
             ("poly", [(5, 21), (10, 14), (13, 17), (18, 11), (22, 21)], False)],
    "layers": [("poly", [(12, 3), (21, 8), (12, 13), (3, 8)], True),
               ("poly", [(4, 12), (12, 16.5), (20, 12)], False),
               ("poly", [(4, 16), (12, 20.5), (20, 16)], False)],
    "measure": [("rect", 2, 8, 20, 8, 1), ("line", 7, 8, 7, 12), ("line", 12, 8, 12, 13),
                ("line", 17, 8, 17, 12)],
    "zoom": [("circle", 10.5, 10.5, 6.5), ("line", 15.5, 15.5, 21, 21)],
    "camera": [("rect", 3, 7, 18, 13, 2), ("circle", 12, 13.5, 4),
               ("poly", [(8, 7), (9.5, 4), (14.5, 4), (16, 7)], False)],
    "settings": [("circle", 12, 12, 3.2), ("circle", 12, 12, 8)],
    "info": [("circle", 12, 12, 9), ("line", 12, 11, 12, 16.5), ("circle", 12, 7.8, 0.6)],
    "warning": [("poly", [(12, 3), (22, 20), (2, 20)], True), ("line", 12, 9, 12, 15),
                ("circle", 12, 17.5, 0.6)],
    "check": [("poly", [(4, 12.5), (9.5, 18), (20, 6)], False)],
    "table": [("rect", 3, 4, 18, 16, 2), ("line", 3, 9, 21, 9), ("line", 9, 9, 9, 20),
              ("line", 15, 9, 15, 20)],
    "console": [("rect", 3, 4, 18, 16, 2), ("poly", [(7, 10), (10, 13), (7, 16)], False),
                ("line", 12, 16, 17, 16)],
    "reset": [("poly", [(20, 12), (20, 6)], False),
              ("circle", 12, 12, 8), ("poly", [(20, 12), (17, 9)], False)],
    "hole": [("line", 12, 2, 12, 22), ("circle", 12, 4, 2.4), ("rect", 10, 9, 4, 11, 1)],
    "home": [("poly", [(3, 12), (12, 4), (21, 12)], False),
             ("rect", 6, 12, 12, 9, 1), ("rect", 10, 15, 4, 6, 0.5)],
    "doc": [("poly", [(4, 3), (15, 3), (20, 8), (20, 21), (4, 21)], True),
            ("line", 15, 3, 15, 8), ("line", 15, 8, 20, 8),
            ("line", 8, 12, 16, 12), ("line", 8, 16, 14, 16)],
    "cube": [("poly", [(12, 3), (21, 8), (12, 13), (3, 8)], True),
             ("line", 12, 13, 12, 22), ("line", 3, 8, 3, 17), ("line", 21, 8, 21, 17),
             ("line", 3, 17, 12, 22), ("line", 12, 22, 21, 17)],
    "arrow_right": [("line", 5, 12, 19, 12), ("poly", [(13, 6), (19, 12), (13, 18)], False)],
    "star": [("poly", [(12, 2), (15, 8.5), (22, 9.5), (17, 14.5), (18.5, 21.5), (12, 18), (5.5, 21.5), (7, 14.5), (2, 9.5), (9, 8.5)], True)],
    "search": [("circle", 10, 10, 6), ("line", 14.5, 14.5, 20, 20)],
    "left": [("poly", [(15, 5), (8, 12), (15, 19)], False)],
    "right": [("poly", [(9, 5), (16, 12), (9, 19)], False)],
    "up": [("poly", [(5, 15), (12, 8), (19, 15)], False)],
    "down": [("poly", [(5, 9), (12, 16), (19, 9)], False)],
    "close": [("line", 6, 6, 18, 18), ("line", 18, 6, 6, 18)],
    "zoom_in": [("circle", 10.5, 10.5, 6.5), ("line", 15.5, 15.5, 21, 21),
                ("line", 7.5, 10.5, 13.5, 10.5), ("line", 10.5, 7.5, 10.5, 13.5)],
    "zoom_out": [("circle", 10.5, 10.5, 6.5), ("line", 15.5, 15.5, 21, 21),
                 ("line", 7.5, 10.5, 13.5, 10.5)],
    "rotate_ccw": [("poly", [(4, 12), (4, 6)], False), ("circle", 12, 12, 8),
                   ("poly", [(4, 12), (7, 9)], False)],
    "rotate_cw": [("poly", [(20, 12), (20, 6)], False), ("circle", 12, 12, 8),
                  ("poly", [(20, 12), (17, 9)], False)],
}


def _pen(color: QColor, width: float) -> QPen:
    p = QPen(color)
    p.setWidthF(width)
    p.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return p


def pixmap(name: str, size: int = 20, color: str | None = None,
           width: float = 1.7) -> QPixmap:
    """Dibuja un icono como ``QPixmap`` del tamano y color indicados."""
    shapes = _SHAPES.get(name)
    scale = size / 24.0
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    if not shapes:
        return pm

    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.scale(scale, scale)
    painter.setPen(_pen(QColor(color or C["text_soft"]), width))
    painter.setBrush(Qt.BrushStyle.NoBrush)

    for shape in shapes:
        kind = shape[0]
        if kind == "line":
            painter.drawLine(QPointF(shape[1], shape[2]), QPointF(shape[3], shape[4]))
        elif kind == "rect":
            painter.drawRoundedRect(QRectF(shape[1], shape[2], shape[3], shape[4]),
                                    shape[5], shape[5])
        elif kind == "circle":
            painter.drawEllipse(QPointF(shape[1], shape[2]), shape[3], shape[3])
        elif kind == "poly":
            path = QPainterPath()
            pts: Sequence[Tuple[float, float]] = shape[1]
            path.moveTo(QPointF(*pts[0]))
            for q in pts[1:]:
                path.lineTo(QPointF(*q))
            if shape[2]:
                path.closeSubpath()
            painter.drawPath(path)

    painter.end()
    return pm


def icon(name: str, size: int = 20, color: str | None = None) -> QIcon:
    """Icono listo para acciones y botones, con variante deshabilitada."""
    ico = QIcon()
    ico.addPixmap(pixmap(name, size, color), QIcon.Mode.Normal)
    ico.addPixmap(pixmap(name, size, color or C["accent"]), QIcon.Mode.Active)
    ico.addPixmap(pixmap(name, size, C["text_muted"]), QIcon.Mode.Disabled)
    return ico


def app_icon(size: int = 64) -> QIcon:
    """Marca de la aplicacion: malla de taladros con destello de detonacion."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    s = size / 64.0

    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(C["accent"]))
    p.drawRoundedRect(QRectF(2 * s, 2 * s, 60 * s, 60 * s), 13 * s, 13 * s)

    p.setBrush(QColor("#ffffff"))
    for row, cols in enumerate(((14, 32, 50), (23, 41), (14, 32, 50))):
        for cx in cols:
            p.drawEllipse(QPointF(cx * s, (20 + row * 12) * s), 3.1 * s, 3.1 * s)

    p.setPen(_pen(QColor("#ffd166"), 2.6 * s))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QPointF(32 * s, 32 * s), 10.5 * s, 10.5 * s)
    p.end()
    return QIcon(pm)
