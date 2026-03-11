"""
Caluza Triangle visual indicator widget.
Draws a triangle with three colored vertices representing:
  - Leg 1: Current Diagnosis (bottom-left)
  - Leg 2: In-Service Event (bottom-right)
  - Leg 3: Medical Nexus (top)
"""
import math
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QPainter, QColor, QPolygonF, QPen, QFont, QBrush


class TriangleWidget(QWidget):
    """
    Visual Caluza Triangle.

    Usage:
        widget = TriangleWidget()
        widget.set_state(diagnosis=True, inservice=True, nexus=False)
    """

    COLOR_COMPLETE = QColor("#1a7a4a")    # green
    COLOR_MISSING   = QColor("#c0392b")   # red
    COLOR_PARTIAL   = QColor("#b8610a")   # orange (not used per-vertex, but useful)
    COLOR_BG        = QColor("#f0f2f5")
    COLOR_EDGE      = QColor("#aab4c0")

    def __init__(self, parent=None, size: int = 120):
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size, int(size * 0.9))
        self._diagnosis = False
        self._inservice = False
        self._nexus = False

    def set_state(self, diagnosis: bool, inservice: bool, nexus: bool):
        self._diagnosis = diagnosis
        self._inservice = inservice
        self._nexus = nexus
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        margin = 18

        # Triangle vertices
        top    = QPointF(w / 2, margin)           # Nexus
        bl     = QPointF(margin, h - margin)       # Diagnosis
        br     = QPointF(w - margin, h - margin)   # In-Service

        # Draw filled triangle (light background)
        poly = QPolygonF([top, bl, br])
        painter.setPen(QPen(self.COLOR_EDGE, 1.5))
        painter.setBrush(QBrush(QColor("#e8edf2")))
        painter.drawPolygon(poly)

        # Draw colored dots at each vertex
        dot_r = 10
        for pt, filled in [(top, self._nexus), (bl, self._diagnosis), (br, self._inservice)]:
            color = self.COLOR_COMPLETE if filled else self.COLOR_MISSING
            painter.setPen(QPen(color.darker(120), 1))
            painter.setBrush(QBrush(color))
            painter.drawEllipse(pt, dot_r, dot_r)
            # Checkmark or X
            painter.setPen(QPen(QColor("#ffffff"), 1.5))
            painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
            mark = "✓" if filled else "✗"
            rect = QRectF(pt.x() - dot_r, pt.y() - dot_r, dot_r * 2, dot_r * 2)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, mark)

        # Labels
        painter.setPen(QPen(QColor("#555e6e")))
        painter.setFont(QFont("Segoe UI", 8))
        # Nexus (above top vertex)
        painter.drawText(QRectF(top.x() - 40, 0, 80, 14), Qt.AlignmentFlag.AlignCenter, "Nexus")
        # Diagnosis (below bottom-left)
        painter.drawText(QRectF(0, h - 14, 70, 14), Qt.AlignmentFlag.AlignCenter, "Diagnosis")
        # In-Service (below bottom-right)
        painter.drawText(QRectF(w - 70, h - 14, 70, 14), Qt.AlignmentFlag.AlignCenter, "In-Service")

        painter.end()
