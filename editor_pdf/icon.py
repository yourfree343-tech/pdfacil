"""Icono de la aplicación dibujado con Qt (sin archivos externos)."""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF


def make_pixmap(size=256):
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    s = size / 256.0
    # hoja
    page = QPainterPath()
    page.moveTo(40 * s, 16 * s)
    page.lineTo(170 * s, 16 * s)
    page.lineTo(216 * s, 62 * s)
    page.lineTo(216 * s, 240 * s)
    page.lineTo(40 * s, 240 * s)
    page.closeSubpath()
    p.setPen(QPen(QColor("#9aa1ab"), max(1.0, 6 * s)))
    p.setBrush(QColor("#fbfbfc"))
    p.drawPath(page)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#c9c9c9"))
    p.drawPolygon(QPolygonF([QPointF(170 * s, 16 * s), QPointF(216 * s, 62 * s), QPointF(170 * s, 62 * s)]))
    # banda roja
    p.setBrush(QColor("#d32f2f"))
    p.drawRoundedRect(QRectF(16 * s, 120 * s, 224 * s, 92 * s), 16 * s, 16 * s)
    f = QFont("Segoe UI", max(6, int(60 * s)))
    f.setBold(True)
    f.setPixelSize(max(6, int(66 * s)))
    p.setFont(f)
    p.setPen(Qt.white)
    p.drawText(QRectF(16 * s, 120 * s, 224 * s, 92 * s), Qt.AlignCenter, "PDF")
    p.end()
    return pm


def make_icon():
    icon = QIcon()
    for sz in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(make_pixmap(sz))
    return icon
