import math
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QComboBox, QGroupBox
from PySide6.QtCore import Qt, Signal, QTimer, QPointF, QRectF
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QRadialGradient
import numpy as np


HOLE_COLORS = {
    "ALIVIO": QColor(100, 100, 100),
    "ARRANQUE": QColor(220, 40, 40),
    "AYUDA": QColor(255, 140, 0),
    "CUADRADOR": QColor(0, 150, 220),
    "CORONA": QColor(180, 0, 180),
    "ARRASTRE": QColor(0, 180, 60),
    "PRODUCCION": QColor(220, 40, 40),
    "PRECORTE": QColor(0, 150, 220),
    "CORTE": QColor(255, 140, 0),
    "DESCABEZADO": QColor(180, 0, 180),
}

HOLE_LABELS = {
    "ALIVIO": "Alivio", "ARRANQUE": "Arranque", "AYUDA": "Ayuda",
    "CUADRADOR": "Cuadrador", "CORONA": "Corona", "ARRASTRE": "Arrastre",
}


class BlastHole2D:
    def __init__(self, hole_id, x, y, hole_type="ARRANQUE", delay_ms=0, charge_kg=5.0):
        self.hole_id = hole_id
        self.x = x
        self.y = y
        self.hole_type = hole_type
        self.delay_ms = delay_ms
        self.charge_kg = charge_kg
        self.state = "standby"


class Blast2DView(QWidget):
    hole_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.holes = []
        self.burden = 4.5
        self.spacing = 5.0
        self.face_y = 0
        self.setMinimumSize(400, 300)
        self.scale = 20.0
        self.offset_x = 200
        self.offset_y = 250
        self.sim_time = 0
        self.simulating = False

    def set_data(self, holes, burden, spacing):
        self.holes = holes
        self.burden = burden
        self.spacing = spacing
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        bg = QColor(9, 9, 11)
        painter.fillRect(self.rect(), bg)

        self._draw_grid(painter)
        self._draw_face(painter)
        self._draw_holes(painter)

        if self.simulating:
            self._draw_blast_waves(painter)

        self._draw_legend(painter)
        painter.end()

    def _draw_grid(self, p):
        pen = QPen(QColor(30, 41, 59), 1, Qt.PenStyle.DotLine)
        p.setPen(pen)
        for x in range(0, self.width(), int(self.spacing * self.scale)):
            p.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), int(self.burden * self.scale)):
            p.drawLine(0, y, self.width(), y)

    def _draw_face(self, p):
        pen = QPen(QColor(0, 240, 255), 2, Qt.PenStyle.DashLine)
        p.setPen(pen)
        fy = self.offset_y - int(0.5 * self.scale)
        p.drawLine(50, fy, self.width() - 50, fy)
        p.setFont(QFont("Courier New", 9))
        p.setPen(QColor(0, 240, 255))
        p.drawText(self.width() - 120, fy - 5, "CARA LIBRE ->")

    def _draw_holes(self, p):
        r = 8
        for h in self.holes:
            x = self.offset_x + int(h.x * self.scale)
            y = self.offset_y + int(h.y * self.scale)
            color = HOLE_COLORS.get(h.hole_type, QColor(200, 200, 200))

            if h.state == "fired":
                grad = QRadialGradient(QPointF(x, y), 25)
                grad.setColorAt(0, QColor(255, 200, 50, 200))
                grad.setColorAt(0.5, QColor(255, 80, 0, 150))
                grad.setColorAt(1, QColor(255, 0, 0, 0))
                p.setBrush(QBrush(grad))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(x, y), 25, 25)
            elif h.state == "empty":
                p.setBrush(QBrush(QColor(30, 30, 30, 100)))
                p.setPen(QPen(QColor(60, 60, 60), 1))
                p.drawEllipse(QPointF(x, y), r, r)
            else:
                p.setBrush(QBrush(color))
                p.setPen(QPen(QColor(255, 255, 255, 80), 1))
                p.drawEllipse(QPointF(x, y), r, r)
                p.setPen(QColor(255, 255, 255))
                p.setFont(QFont("Courier New", 7))
                p.drawText(QRectF(x - 15, y + 10, 30, 12), Qt.AlignmentFlag.AlignCenter, str(h.hole_id))
                if h.delay_ms > 0:
                    p.setPen(QColor(200, 200, 200, 150))
                    p.setFont(QFont("Courier New", 6))
                    p.drawText(QRectF(x - 15, y - 18, 30, 10), Qt.AlignmentFlag.AlignCenter, f"{int(h.delay_ms)}ms")

    def _draw_blast_waves(self, p):
        for h in self.holes:
            if h.state == "fired":
                x = self.offset_x + int(h.x * self.scale)
                y = self.offset_y + int(h.y * self.scale)
                elapsed = self.sim_time - h.delay_ms
                radius = min(elapsed * 0.3, self.burden * self.scale * 1.5)
                alpha = max(0, 200 - int(elapsed * 2))
                p.setPen(QPen(QColor(255, 200, 50, alpha), 2))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QPointF(x, y), int(radius), int(radius))

    def _draw_legend(self, p):
        p.setFont(QFont("Courier New", 8))
        y = 10
        for ht, color in HOLE_COLORS.items():
            if ht in HOLE_LABELS:
                p.setBrush(QBrush(color))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(10, y + 2, 8, 8)
                p.setPen(QColor(200, 200, 200))
                p.drawText(22, y + 10, HOLE_LABELS.get(ht, ht))
                y += 16


class Sim2DWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        controls = QHBoxLayout()
        self.btn_play = QPushButton("PLAY")
        self.btn_play.setStyleSheet("QPushButton{background:#dc2626;color:white;font-weight:bold;border-radius:4px;padding:6px 16px;}")
        self.btn_play.clicked.connect(self.toggle_sim)
        self.btn_reset = QPushButton("RESET")
        self.btn_reset.setStyleSheet("QPushButton{background:#334155;color:#e2e8f0;border-radius:4px;padding:6px 12px;}")
        self.btn_reset.clicked.connect(self.reset_sim)
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["0.5x", "1x", "2x", "4x"])
        self.speed_combo.setStyleSheet("QComboBox{background:#1e293b;color:#e2e8f0;border:1px solid #334155;border-radius:4px;padding:4px;}")
        self.time_label = QLabel("T = 0 ms")
        self.time_label.setStyleSheet("color:#00f0ff;font-family:'Courier New';font-weight:bold;font-size:10pt;")
        controls.addWidget(self.btn_play)
        controls.addWidget(self.btn_reset)
        controls.addWidget(QLabel("Velocidad:"))
        controls.addWidget(self.speed_combo)
        controls.addStretch()
        controls.addWidget(self.time_label)
        layout.addLayout(controls)

        self.view = Blast2DView()
        layout.addWidget(self.view)

        self.timer = QTimer()
        self.timer.timeout.connect(self._tick)
        self.sim_time = 0
        self.speed = 1.0
        self.total_ms = 1000

    def set_data(self, holes, burden, spacing, total_ms):
        self.view.set_data(holes, burden, spacing)
        self.total_ms = total_ms

    def toggle_sim(self):
        if self.view.simulating:
            self.pause_sim()
        else:
            self.start_sim()

    def start_sim(self):
        self.view.simulating = True
        self.sim_time = 0
        self.speed = float(self.speed_combo.currentText().replace("x", ""))
        for h in self.view.holes:
            h.state = "standby"
        self.timer.start(33)
        self.btn_play.setText("PAUSE")

    def pause_sim(self):
        self.view.simulating = False
        self.timer.stop()
        self.btn_play.setText("PLAY")

    def reset_sim(self):
        self.pause_sim()
        self.sim_time = 0
        for h in self.view.holes:
            h.state = "standby"
        self.time_label.setText("T = 0 ms")
        self.view.update()

    def _tick(self):
        self.sim_time += 33 * self.speed
        for h in self.view.holes:
            if h.state == "standby" and self.sim_time >= h.delay_ms:
                h.state = "fired"
            elif h.state == "fired" and self.sim_time >= h.delay_ms + 200:
                h.state = "empty"
        self.view.sim_time = self.sim_time
        self.time_label.setText(f"T = {int(self.sim_time)} ms")
        self.view.update()
        if self.sim_time >= self.total_ms + 500:
            self.pause_sim()


class TieUpVisualWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows_data = []
        self.setMinimumHeight(200)

    def set_data(self, rows_data):
        self.rows_data = rows_data
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(9, 9, 11))
        if not self.rows_data:
            painter.setPen(QColor(100, 100, 100))
            painter.setFont(QFont("Courier New", 10))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Genere la malla para ver el diagrama de amarre")
            painter.end()
            return
        max_time = max(r["time"] for r in self.rows_data) if self.rows_data else 1
        bar_h = max(12, min(30, (self.height() - 40) / max(len(self.rows_data), 1)))
        colors = [QColor(220, 40, 40), QColor(255, 140, 0), QColor(0, 150, 220), QColor(180, 0, 180), QColor(0, 180, 60), QColor(100, 100, 100)]
        for i, row in enumerate(self.rows_data):
            y = 10 + i * (bar_h + 4)
            color = colors[i % len(colors)]
            bar_w = (row["time"] / max_time * (self.width() - 200)) if max_time > 0 else 0
            painter.setPen(QPen(color, 1))
            painter.setBrush(QBrush(color))
            painter.drawRoundedRect(QRectF(100, y, bar_w, bar_h), 3, 3)
            painter.setPen(QColor(200, 200, 200))
            painter.setFont(QFont("Courier New", 8))
            painter.drawText(QRectF(0, y, 95, bar_h), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"Fila {row['row']}")
            painter.drawText(QRectF(100 + bar_w + 5, y, 80, bar_h), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"{row['time']:.0f}ms | {row['holes']} taladros")
            painter.setPen(QColor(0, 240, 255))
            for j in range(row["holes"]):
                cx = 100 + bar_w * (j + 0.5) / row["holes"]
                painter.drawEllipse(QPointF(cx, y + bar_h / 2), 3, 3)
        painter.end()
