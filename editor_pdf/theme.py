"""Tema visual claro/oscuro: paleta, hoja de estilos (QSS) y barra de título de Windows a juego."""
import ctypes

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication, QWidget

LIGHT = dict(
    dark=False,
    window="#f3f4f6", header="#ffffff", surface="#ffffff", surface2="#f5f6f8", raised="#ffffff",
    border="#e2e4e8", border_strong="#cfd3d9", text="#1f2328", muted="#6b7280", disabled="#b4b9c1",
    accent="#2563eb", accent_hover="#1d4ed8", accent_text="#ffffff", accent_soft="#e3ebfd",
    hover="#eef0f3", pressed="#e3e6ea", canvas="#e7e9ec", page_shadow="#000000",
    thumb_text="#4b5563", danger="#dc2626", ok="#16a34a",
)
DARK = dict(
    dark=True,
    window="#1c1d20", header="#25262a", surface="#2a2b30", surface2="#2f3035", raised="#33343a",
    border="#393a40", border_strong="#4a4b52", text="#e7e8ea", muted="#9ca0a8", disabled="#5f636b",
    accent="#5b93ff", accent_hover="#7aa8ff", accent_text="#0b1220", accent_soft="#263a5e",
    hover="#34353b", pressed="#3d3e45", canvas="#16171a", page_shadow="#000000",
    thumb_text="#c4c7cd", danger="#f87171", ok="#4ade80",
)


def system_is_dark():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
    except Exception:
        return False


def palette_for(mode):
    """mode: 'system' | 'light' | 'dark'"""
    dark = system_is_dark() if mode == "system" else mode == "dark"
    return DARK if dark else LIGHT


def _assets(p):
    """Dibujos para la hoja de estilos (marca de verificación y flechas) con los colores del tema."""
    import os
    import tempfile
    folder = os.path.join(tempfile.gettempdir(), "PDFacil-tema")
    os.makedirs(folder, exist_ok=True)
    svgs = {
        "check": ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path d="M3.5 8.5l3 3 6-7" fill="none" '
                  f'stroke="{p["accent_text"]}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>'),
        "up": ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path d="M4 10l4-4 4 4" fill="none" '
               f'stroke="{p["muted"]}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>'),
        "down": ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path d="M4 6l4 4 4-4" fill="none" '
                 f'stroke="{p["muted"]}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>'),
    }
    out = {}
    tag = "oscuro" if p["dark"] else "claro"
    for name, svg in svgs.items():
        path = os.path.join(folder, f"{name}_{tag}.svg")
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
        out[name] = path.replace("\\", "/")
    return out


def qss(p):
    a = _assets(p)
    return f"""
* {{ font-family: "Segoe UI Variable Text", "Segoe UI"; font-size: 10pt; }}
QMainWindow, QDialog {{ background: {p['window']}; color: {p['text']}; }}
QWidget {{ color: {p['text']}; }}
QToolTip {{ background: {p['raised']}; color: {p['text']}; border: 1px solid {p['border']};
            padding: 6px 8px; border-radius: 6px; }}

/* menús */
QMenuBar {{ background: {p['header']}; color: {p['text']}; padding: 2px 6px; border: none; }}
QMenuBar::item {{ background: transparent; padding: 5px 10px; border-radius: 6px; }}
QMenuBar::item:selected {{ background: {p['hover']}; }}
QMenu {{ background: {p['raised']}; border: 1px solid {p['border']}; border-radius: 10px; padding: 6px; }}
QMenu::item {{ padding: 7px 28px 7px 14px; border-radius: 6px; }}
QMenu::item:selected {{ background: {p['accent_soft']}; color: {p['text']}; }}
QMenu::item:disabled {{ color: {p['disabled']}; }}
QMenu::separator {{ height: 1px; background: {p['border']}; margin: 5px 8px; }}
QMenu::right-arrow {{ width: 8px; }}

/* barras */
QToolBar {{ background: {p['header']}; border: none; spacing: 2px; }}
QToolBar#header {{ border-bottom: 1px solid {p['border']}; padding: 6px 10px; }}
QToolBar#props {{ background: {p['surface2']}; border-bottom: 1px solid {p['border']}; padding: 4px 12px; }}
QToolBar#rail {{ border-right: 1px solid {p['border']}; padding: 6px 5px; spacing: 1px; }}
QToolBar::separator {{ background: {p['border']}; width: 1px; height: 1px; margin: 6px 6px; }}
QToolButton {{ background: transparent; border: none; border-radius: 8px; padding: 6px; color: {p['text']}; }}
QToolButton:hover {{ background: {p['hover']}; }}
QToolButton:pressed {{ background: {p['pressed']}; }}
QToolButton:checked {{ background: {p['accent_soft']}; }}
QToolButton:disabled {{ color: {p['disabled']}; }}
QToolBar#rail QToolButton {{ padding: 6px; }}
QToolBar#rail::separator {{ margin: 3px 6px; }}
QWidget#pill {{ background: {p['surface2']}; border: 1px solid {p['border']}; border-radius: 9px; }}
QWidget#pill QToolButton {{ border-radius: 7px; padding: 4px; }}
QWidget#pill QLabel {{ color: {p['muted']}; }}
QLineEdit#pagebox {{ background: {p['surface']}; border: 1px solid {p['border']}; border-radius: 6px; padding: 2px 4px; }}
QLineEdit#pagebox:focus {{ border: 1px solid {p['accent']}; }}
QLabel#toolname {{ font-weight: 600; }}
QLabel#hint, QLabel#muted {{ color: {p['muted']}; }}
QToolButton#swatch {{ border-radius: 11px; padding: 0; border: 2px solid transparent; }}
QToolButton#swatch:checked {{ border: 2px solid {p['text']}; }}

/* campos */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit {{
    background: {p['surface']}; border: 1px solid {p['border_strong']}; border-radius: 7px;
    padding: 5px 8px; selection-background-color: {p['accent']}; selection-color: {p['accent_text']}; }}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border: 1px solid {p['accent']}; }}
QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled {{ color: {p['disabled']}; }}
QLineEdit#search {{ border-radius: 9px; padding: 5px 8px; background: {p['surface2']};
                    border: 1px solid {p['border']}; }}
QLineEdit#search:focus {{ background: {p['surface']}; border: 1px solid {p['accent']}; }}
QWidget#pill QSpinBox, QWidget#pill QComboBox {{ background: transparent; border: none; padding: 0 2px; }}
QWidget#pill QSpinBox::up-button, QWidget#pill QSpinBox::down-button {{ width: 0; height: 0; border: none; }}
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    width: 18px; border: none; background: transparent; }}
QSpinBox::up-button:hover, QSpinBox::down-button:hover, QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
    background: {p['hover']}; border-radius: 4px; }}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{ image: url({a['up']}); width: 12px; height: 12px; }}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{ image: url({a['down']}); width: 12px; height: 12px; }}
QComboBox::down-arrow {{ image: url({a['down']}); width: 14px; height: 14px; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {p['raised']}; border: 1px solid {p['border']}; border-radius: 8px;
    padding: 4px; selection-background-color: {p['accent_soft']}; selection-color: {p['text']}; outline: 0; }}

/* botones */
QPushButton {{ background: {p['surface']}; border: 1px solid {p['border_strong']}; border-radius: 8px; min-width: 64px;
               padding: 7px 18px; }}
QPushButton:hover {{ background: {p['hover']}; }}
QPushButton:pressed {{ background: {p['pressed']}; }}
QPushButton:disabled {{ color: {p['disabled']}; border-color: {p['border']}; }}
QPushButton:default, QPushButton[primary="true"] {{ background: {p['accent']}; color: {p['accent_text']};
    border: 1px solid {p['accent']}; }}
QPushButton:default:hover, QPushButton[primary="true"]:hover {{ background: {p['accent_hover']}; }}
QPushButton[flat="true"] {{ background: transparent; border: none; text-align: left; padding: 8px 10px; }}
QPushButton[flat="true"]:hover {{ background: {p['hover']}; }}
QPushButton#colorbtn {{ min-width: 28px; padding: 0; border-radius: 6px; }}
QCheckBox, QRadioButton {{ spacing: 8px; }}
QCheckBox::indicator, QRadioButton::indicator {{ width: 16px; height: 16px; border: 1.5px solid {p['border_strong']};
    background: {p['surface']}; }}
QCheckBox::indicator {{ border-radius: 4px; }}
QRadioButton::indicator {{ border-radius: 9px; }}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{ border-color: {p['accent']}; }}
QCheckBox::indicator:checked {{ background: {p['accent']}; border-color: {p['accent']}; image: url({a['check']}); }}
QRadioButton::indicator:checked {{ border-color: {p['accent']}; background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5, stop:0 {p['accent']}, stop:0.45 {p['accent']}, stop:0.55 {p['surface']}, stop:1 {p['surface']}); }}
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{ background: {p['surface2']}; border-color: {p['border']}; }}
QLabel#context {{ background: {p['surface']}; border: 1px solid {p['border']}; border-radius: 8px; padding: 8px; }}

/* paneles */
QDockWidget {{ color: {p['text']}; titlebar-close-icon: none; }}
QDockWidget::title {{ background: {p['header']}; padding: 9px 12px; font-weight: 600;
                      border-bottom: 1px solid {p['border']}; text-align: left; }}
QDockWidget > QWidget {{ background: {p['surface']}; }}
QListWidget {{ background: {p['surface']}; border: none; outline: 0; }}
QListWidget::item {{ border-radius: 8px; padding: 4px; }}
QListWidget::item:hover {{ background: {p['hover']}; }}
QListWidget::item:selected {{ background: {p['accent_soft']}; color: {p['text']}; }}
QListWidget#thumbs {{ background: {p['surface']}; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QStatusBar {{ background: {p['header']}; color: {p['muted']}; border-top: 1px solid {p['border']}; }}
QStatusBar QLabel {{ color: {p['muted']}; padding: 0 8px; }}
QStatusBar::item {{ border: none; }}
QProgressBar {{ border: 1px solid {p['border']}; border-radius: 6px; background: {p['surface2']};
                text-align: center; height: 14px; }}
QProgressBar::chunk {{ background: {p['accent']}; border-radius: 5px; }}

/* barras de desplazamiento finas */
QScrollBar:vertical {{ background: transparent; width: 12px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 2px; }}
QScrollBar::handle {{ background: {p['border_strong']}; border-radius: 4px; min-height: 30px; min-width: 30px; margin: 2px; }}
QScrollBar::handle:hover {{ background: {p['muted']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ajustes */
QListWidget#settingsnav {{ background: {p['surface2']}; border-right: 1px solid {p['border']}; padding: 10px 8px; }}
QListWidget#settingsnav::item {{ padding: 6px 10px; margin: 1px 0; }}
QListWidget#settingsnav::item:selected {{ background: {p['accent_soft']}; color: {p['text']}; font-weight: 600; }}
QLabel#pagetitle {{ font-size: 15pt; font-weight: 600; padding-bottom: 8px; }}

/* bienvenida */
QWidget#welcome {{ background: {p['window']}; }}
QFrame#card {{ background: {p['surface']}; border: 1px solid {p['border']}; border-radius: 14px; }}
QFrame#dropzone {{ border: 2px dashed {p['border_strong']}; border-radius: 12px; background: {p['surface2']}; }}
QLabel#title {{ font-size: 20pt; font-weight: 600; }}
QLabel#subtitle {{ color: {p['muted']}; font-size: 11pt; }}
QLabel#section {{ color: {p['muted']}; font-size: 9pt; font-weight: 600; }}
QPushButton#bigaction {{ text-align: left; padding: 12px 14px; border-radius: 10px; font-size: 10.5pt; }}
"""


def _qpalette(p):
    pal = QPalette()
    c = lambda k: QColor(p[k])
    pal.setColor(QPalette.Window, c("window"))
    pal.setColor(QPalette.WindowText, c("text"))
    pal.setColor(QPalette.Base, c("surface"))
    pal.setColor(QPalette.AlternateBase, c("surface2"))
    pal.setColor(QPalette.Text, c("text"))
    pal.setColor(QPalette.Button, c("surface"))
    pal.setColor(QPalette.ButtonText, c("text"))
    pal.setColor(QPalette.Highlight, c("accent"))
    pal.setColor(QPalette.HighlightedText, c("accent_text"))
    pal.setColor(QPalette.ToolTipBase, c("raised"))
    pal.setColor(QPalette.ToolTipText, c("text"))
    pal.setColor(QPalette.PlaceholderText, c("muted"))
    pal.setColor(QPalette.Link, c("accent"))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        pal.setColor(QPalette.Disabled, role, c("disabled"))
    return pal


def install_spanish(app):
    """Botones y diálogos estándar de Qt (Aceptar, Cancelar, Guardar, abrir archivo…) en español."""
    from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
    QLocale.setDefault(QLocale(QLocale.Spanish, QLocale.Spain))
    path = QLibraryInfo.path(QLibraryInfo.TranslationsPath)
    app._translators = []
    for name in ("qtbase_es", "qt_es"):
        t = QTranslator(app)
        if t.load(name, path):
            app.installTranslator(t)
            app._translators.append(t)


def _colorref(hexcolor):
    q = QColor(hexcolor)
    return q.red() | (q.green() << 8) | (q.blue() << 16)


def style_titlebar(widget, p):
    """Barra de título de Windows 10/11 en modo oscuro/claro y (en Windows 11) del color de la cabecera."""
    try:
        hwnd = int(widget.winId())
        dwm = ctypes.windll.dwmapi
        val = ctypes.c_int(1 if p["dark"] else 0)
        dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(val), 4)          # modo oscuro
        cap = ctypes.c_int(_colorref(p["header"]))
        dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(cap), 4)          # color del título (Win 11)
        txt = ctypes.c_int(_colorref(p["text"]))
        dwm.DwmSetWindowAttribute(hwnd, 36, ctypes.byref(txt), 4)          # color del texto
        brd = ctypes.c_int(_colorref(p["border"]))
        dwm.DwmSetWindowAttribute(hwnd, 34, ctypes.byref(brd), 4)          # color del borde
    except Exception:
        pass


class _TitlebarFilter(QObject):
    """Aplica la barra de título a juego a cada ventana nueva (diálogos incluidos)."""

    def __init__(self):
        super().__init__()
        self.pal = LIGHT

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Show and isinstance(obj, QWidget) and obj.isWindow():
            style_titlebar(obj, self.pal)
        return False


_filter = None


def apply(app: QApplication, mode="system"):
    global _filter
    p = palette_for(mode)
    app.setStyle("Fusion")
    app.setPalette(_qpalette(p))
    f = QFont("Segoe UI Variable Text")
    f.setPointSizeF(10)
    app.setFont(f)
    app.setStyleSheet(qss(p))
    if _filter is None:
        _filter = _TitlebarFilter()
        app.installEventFilter(_filter)
    _filter.pal = p
    for w in app.topLevelWidgets():
        if w.isVisible():
            style_titlebar(w, p)
    return p
