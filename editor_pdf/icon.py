"""Icono de PDFácil (SVG dibujado con Qt, sin archivos externos).

Fondo redondeado con degradado coral → rojo, hoja blanca con la esquina doblada, un check («fácil»)
y un destello. En tamaños pequeños se simplifica (sin destello y con trazos más gruesos) para que se lea bien.
"""
from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_DEFS = """
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#FF7A45"/><stop offset="0.55" stop-color="#F0443A"/><stop offset="1" stop-color="#C81E4B"/>
  </linearGradient>
  <linearGradient id="shine" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#FFFFFF" stop-opacity="0.28"/><stop offset="0.5" stop-color="#FFFFFF" stop-opacity="0"/>
  </linearGradient>
  <linearGradient id="check" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#FF6A3D"/><stop offset="1" stop-color="#D3264A"/>
  </linearGradient>
  <linearGradient id="paper" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#FFFFFF"/><stop offset="1" stop-color="#FFF1EE"/>
  </linearGradient>
</defs>"""

SVG_FULL = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">{_DEFS}
  <rect x="12" y="12" width="232" height="232" rx="58" fill="url(#bg)"/>
  <rect x="12" y="12" width="232" height="232" rx="58" fill="url(#shine)"/>
  <path d="M84 52h62l36 36v108a14 14 0 0 1-14 14H84a14 14 0 0 1-14-14V66a14 14 0 0 1 14-14z" fill="#8E1233" opacity="0.28" transform="translate(5 7)"/>
  <path d="M84 52h62l36 36v108a14 14 0 0 1-14 14H84a14 14 0 0 1-14-14V66a14 14 0 0 1 14-14z" fill="url(#paper)"/>
  <path d="M146 52v24a12 12 0 0 0 12 12h24z" fill="#FFC9BE"/>
  <path d="M94 146l22 22 42-46" fill="none" stroke="url(#check)" stroke-width="17" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M206 40c2.5 13 6 16.5 19 19-13 2.5-16.5 6-19 19-2.5-13-6-16.5-19-19 13-2.5 16.5-6 19-19z" fill="#FFFFFF"/>
  <circle cx="222" cy="92" r="5" fill="#FFFFFF" opacity="0.85"/>
</svg>"""

SVG_SMALL = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">{_DEFS}
  <rect x="8" y="8" width="240" height="240" rx="56" fill="url(#bg)"/>
  <path d="M74 40h76l42 42v126a12 12 0 0 1-12 12H74a12 12 0 0 1-12-12V52a12 12 0 0 1 12-12z" fill="#FFFFFF"/>
  <path d="M150 40v30a12 12 0 0 0 12 12h30z" fill="#FFC1B4"/>
  <path d="M88 146l26 26 50-56" fill="none" stroke="#E5323F" stroke-width="26" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""


def render(size, small=None):
    """QImage del icono a `size` píxeles (usa el diseño simplificado por debajo de 48 px)."""
    svg = SVG_SMALL if (small if small is not None else size < 48) else SVG_FULL
    img = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    QSvgRenderer(QByteArray(svg.encode())).render(p, QRectF(0, 0, size, size))
    p.end()
    return img


def make_pixmap(size=256):
    return QPixmap.fromImage(render(size))


def make_icon():
    icon = QIcon()
    for sz in (16, 20, 24, 32, 40, 48, 64, 128, 256):
        icon.addPixmap(QPixmap.fromImage(render(sz)))
    return icon
