from PySide6.QtWidgets import QTextEdit, QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QTextCursor
from datetime import datetime


class ConsoleLog(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("CONSOLA DE EVENTOS")
        header.setStyleSheet("""
            QLabel {
                color: #94A3B8;
                font-family: 'Courier New', monospace;
                font-size: 8pt;
                font-weight: bold;
                background-color: #0F172A;
                padding: 6px 10px;
                border-bottom: 1px solid #1E293B;
                letter-spacing: 2px;
            }
        """)
        layout.addWidget(header)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Cascadia Code", 8))
        self.console.setStyleSheet("""
            QTextEdit {
                background-color: #09090B;
                color: #94A3B8;
                border: none;
                padding: 6px;
                font-family: 'Cascadia Code', 'Fira Code', 'Courier New', monospace;
                font-size: 8pt;
                selection-background-color: #1E3A5F;
            }
        """)
        layout.addWidget(self.console)

        self._log_raw("X-BLAST v2.0 — Enterprise Mining Suite")
        self._log_raw("Sistema de Perforacion y Voladura profesional")
        self._log_raw("Consola iniciada. Listo para operar.")
        self._log_raw("-" * 48)

    def _log_raw(self, message: str):
        line = f"<span style='color:#334155;'>{message}</span>"
        self.console.append(line)

    def log(self, message: str, level: str = "INFO"):
        ts = datetime.now().strftime("%H:%M:%S")
        color_map = {
            "INFO": "#94A3B8",
            "WARN": "#FBBF24",
            "ERROR": "#F87171",
            "SUCCESS": "#34D399",
            "CAD": "#60A5FA",
        }
        color = color_map.get(level, "#94A3B8")
        prefix_map = {
            "INFO": ">>",
            "WARN": "!!",
            "ERROR": "XX",
            "SUCCESS": "OK",
            "CAD": ">>",
        }
        prefix = prefix_map.get(level, ">>")
        line = (
            f"<span style='color:#475569;'>[{ts}]</span> "
            f"<span style='color:{color}; font-weight:bold;'>{prefix} {level}</span> "
            f"<span style='color:#CBD5E1;'>{message}</span>"
        )
        self.console.append(line)
        cursor = self.console.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.console.setTextCursor(cursor)

    def clear(self):
        self.console.clear()
