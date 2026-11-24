"""Iconos de línea propios (SVG 24×24) que se colorean según el tema."""
from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

ICONS = {
    "open": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h7a2 2 0 0 1 2 2v1.5"/><path d="M3 7v11a2 2 0 0 0 2 2h12.4a2 2 0 0 0 1.9-1.4L21.8 12a1 1 0 0 0-1-1.3H7.6a2 2 0 0 0-1.9 1.4L3.4 19.5"/>',
    "save": '<path d="M5 3h11l5 5v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/><path d="M7 3v5h8V3"/><path d="M7 21v-7a1 1 0 0 1 1-1h8a1 1 0 0 1 1 1v7"/>',
    "print": '<path d="M7 9V3h10v6"/><path d="M7 18H5a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="7" y="14" width="10" height="7" rx="1"/>',
    "undo": '<path d="M9 14 4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/>',
    "redo": '<path d="m15 14 5-5-5-5"/><path d="M20 9H9.5a5.5 5.5 0 0 0 0 11H13"/>',
    "zoom_in": '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5M11 8v6M8 11h6"/>',
    "zoom_out": '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5M8 11h6"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    "left": '<path d="m15 18-6-6 6-6"/>',
    "right": '<path d="m9 18 6-6-6-6"/>',
    "up": '<path d="m18 15-6-6-6 6"/>',
    "down": '<path d="m6 9 6 6 6-6"/>',
    "close": '<path d="M18 6 6 18M6 6l12 12"/>',
    "hand": '<path d="M8 13V5.5a1.5 1.5 0 0 1 3 0V12"/><path d="M11 11.5V4.5a1.5 1.5 0 0 1 3 0V12"/><path d="M14 11.5V6.5a1.5 1.5 0 0 1 3 0V12"/><path d="M17 9.5a1.5 1.5 0 0 1 3 0V15a6 6 0 0 1-6 6h-1.6c-2.2 0-3.6-1-4.9-2.6L4.1 13.7a1.6 1.6 0 0 1 2.3-2.3L8 13"/>',
    "select": '<path d="M4.5 3.5 11.5 20l2.4-6.6 6.6-2.4z"/><path d="m14 14 5.5 5.5"/>',
    "textsel": '<path d="M8 4h1.5A2.5 2.5 0 0 1 12 6.5v11A2.5 2.5 0 0 1 9.5 20H8M16 4h-1.5A2.5 2.5 0 0 0 12 6.5v11a2.5 2.5 0 0 0 2.5 2.5H16M9.5 12h5"/>',
    "edit": '<path d="M4 6h9M4 11h6M4 16h4"/><path d="M14 20.5 20.3 14a1.9 1.9 0 0 0-2.7-2.7L11.3 17.8 11 20.8z"/>',
    "text": '<path d="M5 7V5h14v2M12 5v14M9 19h6"/>',
    "note": '<path d="M20 14.5V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h9.5z"/><path d="M14 20v-4.5a1 1 0 0 1 1-1h5"/><path d="M8 9h8M8 13h4"/>',
    "highlight": '<path d="m9.5 10.5-5 5V19h3.5l5-5"/><path d="m9.5 10.5 6-6a1.4 1.4 0 0 1 2 0l2 2a1.4 1.4 0 0 1 0 2l-6 6z"/><path d="M14 21h7"/>',
    "underline": '<path d="M7 4v6a5 5 0 0 0 10 0V4"/><path d="M5 20h14"/>',
    "strike": '<path d="M16 7c-.7-1.8-2.2-3-4.3-3C9.4 4 7.8 5.3 7.8 7.2c0 1.4.9 2.3 2.4 2.8"/><path d="M4 12h16"/><path d="M8 17c.6 1.8 2.2 3 4.3 3 2.4 0 4-1.3 4-3.2 0-.6-.2-1.2-.5-1.6"/>',
    "ink": '<path d="M3 17.5c2.6-5.5 4.6-9 6.6-9 2.6 0-.8 9 2.2 9 1.9 0 2.8-3.6 4.8-3.6 1.6 0 1.9 2.6 4.4 2.6"/>',
    "rect": '<rect x="4" y="5" width="16" height="14" rx="2"/>',
    "ellipse": '<ellipse cx="12" cy="12" rx="9" ry="7"/>',
    "arrow": '<path d="M5 19 19 5M9 5h10v10"/>',
    "line": '<path d="M5 19 19 5"/>',
    "image": '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="m21 16-4.6-4.6a1 1 0 0 0-1.4 0L6 20"/>',
    "sign": '<path d="M3 16.5c2.2-1.2 3.6-6 5-9.7.8-2 2.4-1.6 2 .5-.7 3.7-2.4 8.4-1.4 8.9 1 .4 2.4-3.1 3.5-3.1s.6 2.6 1.7 2.6 1.6-1.5 2.7-1.5c.8 0 1.4.8 2.5.8"/><path d="M3 21h18"/>',
    "whiteout": '<path d="M7.5 20.5 3.6 16.6a1.6 1.6 0 0 1 0-2.2L13.4 4.6a1.6 1.6 0 0 1 2.2 0l4.8 4.8a1.6 1.6 0 0 1 0 2.2l-8.9 8.9"/><path d="M7.5 20.5H20M8.6 9.4l6 6"/>',
    "digsign": '<path d="M12 3 4.5 6v5.5c0 4.7 3.2 8 7.5 9.5 4.3-1.5 7.5-4.8 7.5-9.5V6z"/><path d="m8.8 12 2.2 2.2 4.4-4.4"/>',
    "panel_left": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16"/>',
    "panel_right": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M15 4v16"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M2.5 12h2M19.5 12h2M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4"/>',
    "moon": '<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/>',
    "file": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>',
    "file_plus": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M12 11v6M9 14h6"/>',
    "images": '<rect x="3" y="6" width="14" height="14" rx="2"/><path d="M7 3h12a2 2 0 0 1 2 2v12"/><circle cx="8" cy="11" r="1.5"/><path d="m17 17-3.5-3.5L7 20"/>',
    "merge": '<rect x="3" y="3" width="10" height="13" rx="1.5"/><path d="M13 8h6.5A1.5 1.5 0 0 1 21 9.5v10a1.5 1.5 0 0 1-1.5 1.5h-7A1.5 1.5 0 0 1 11 19.5V16"/>',
    "fit": '<path d="M3 12h18M7 8l-4 4 4 4M17 8l4 4-4 4"/>',
    "form": '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/>',
    "pages": '<rect x="4" y="3" width="11" height="14" rx="1.5"/><path d="M9 21h9.5a1.5 1.5 0 0 0 1.5-1.5V8"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
    "update": '<path d="M21 12a9 9 0 1 1-2.6-6.4"/><path d="M21 4v5h-5"/><path d="M12 8v5l3 2"/>',
    "drop": '<path d="M12 15V4M7.5 8.5 12 4l4.5 4.5"/><path d="M4 14v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4"/>',
}

_cache = {}


def pixmap(name, color, size=20):
    dpr = QGuiApplication.primaryScreen().devicePixelRatio() if QGuiApplication.primaryScreen() else 1.0
    key = (name, color, size, dpr)
    if key in _cache:
        return _cache[key]
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" '
           f'stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</svg>')
    px = int(round(size * dpr))
    pm = QPixmap(px, px)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    QSvgRenderer(QByteArray(svg.encode())).render(p, QRectF(0, 0, px, px))
    p.end()
    pm.setDevicePixelRatio(dpr)
    _cache[key] = pm
    return pm


def icon(name, pal, size=20):
    """Icono con colores para normal, desactivado y activado (herramienta seleccionada)."""
    ic = QIcon()
    ic.addPixmap(pixmap(name, pal["text"], size), QIcon.Normal, QIcon.Off)
    ic.addPixmap(pixmap(name, pal["accent"], size), QIcon.Normal, QIcon.On)
    ic.addPixmap(pixmap(name, pal["disabled"], size), QIcon.Disabled, QIcon.Off)
    ic.addPixmap(pixmap(name, pal["disabled"], size), QIcon.Disabled, QIcon.On)
    ic.addPixmap(pixmap(name, pal["accent"], size), QIcon.Active, QIcon.On)
    return ic
