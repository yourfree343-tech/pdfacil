"""Ventana principal de PDFácil."""
import os

import pymupdf as fitz
from PySide6.QtCore import QSettings, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QActionGroup, QColor, QIntValidator, QKeySequence, QPainter
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QDockWidget, QDoubleSpinBox, QFileDialog, QFrame, QHBoxLayout,
    QInputDialog, QLabel, QLineEdit, QMainWindow, QMessageBox, QProgressDialog, QPushButton, QSizePolicy,
    QSpinBox, QStackedWidget, QToolBar, QToolButton, QVBoxLayout, QWidget,
)

from . import APP_NAME, __publisher__, __version__
from . import settings_dialog as cfg
from . import icons, ocr, theme
from .dialogs import (
    ColorButton, CompressDialog, DigitalSignDialog, ExportImagesDialog, PasswordDialog, SignatureDialog, SplitDialog,
)
from .document import IMAGE_FILTER, OPEN_FILTER, PasswordNeeded, PdfDoc, images_to_pdf, load_any, parse_ranges
from .forms import FormPanel
from .icon import make_icon, make_pixmap
from .thumbs import ThumbPanel
from .view import PageView, T, pixmap_to_qimage

APP = APP_NAME
DATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "EditorPDF")
SIGNATURE = os.path.join(DATA_DIR, "firma.png")
MAX_RECENT = 8

# (herramienta, icono, nombre, pista, atajo, opciones que usa)
TOOLS = [
    (T.HAND, "hand", "Mano", "Arrastra para moverte por el documento.", "H", ""),
    (T.SELECT, "select", "Seleccionar", "Clic en una anotación para seleccionarla · arrastra para moverla · "
                                        "Supr para borrarla · doble clic para editarla.", "V", "color width"),
    (T.TEXTSEL, "textsel", "Copiar texto", "Arrastra sobre el texto para copiarlo al portapapeles.", "C", ""),
    None,
    (T.EDIT, "edit", "Editar texto", "Haz clic en una línea del PDF para cambiar lo que pone.", "E", ""),
    (T.TEXT, "text", "Añadir texto", "Haz clic donde quieras escribir.", "T", "color font"),
    (T.NOTE, "note", "Nota", "Haz clic donde quieras pegar una nota.", "N", ""),
    None,
    (T.HIGHLIGHT, "highlight", "Resaltar", "Arrastra sobre el texto para resaltarlo.", "R", ""),
    (T.UNDERLINE, "underline", "Subrayar", "Arrastra sobre el texto para subrayarlo.", "U", "color"),
    (T.STRIKE, "strike", "Tachar", "Arrastra sobre el texto para tacharlo.", "", "color"),
    None,
    (T.INK, "ink", "Dibujar", "Dibuja a mano alzada.", "D", "color width"),
    (T.RECT, "rect", "Rectángulo", "Arrastra para dibujar un rectángulo.", "", "color width"),
    (T.ELLIPSE, "ellipse", "Elipse", "Arrastra para dibujar una elipse.", "", "color width"),
    (T.ARROW, "arrow", "Flecha", "Arrastra para dibujar una flecha.", "", "color width"),
    (T.LINE, "line", "Línea", "Arrastra para dibujar una línea.", "", "color width"),
    None,
    (T.IMAGE, "image", "Imagen", "Arrastra un recuadro (o haz clic) para poner una imagen.", "", ""),
    (T.SIGN, "sign", "Firma manuscrita", "Arrastra un recuadro (o haz clic) para poner tu firma.", "", ""),
    (T.DIGSIGN, "digsign", "Firma digital", "Arrastra un recuadro para firmar con tu certificado digital.", "", ""),
    None,
    (T.WHITEOUT, "whiteout", "Borrar zona", "Arrastra un recuadro: lo que haya dentro se borra para siempre.", "", ""),
]
SWATCHES = [("Rojo", (0.86, 0.15, 0.15)), ("Naranja", (0.95, 0.5, 0.1)), ("Verde", (0.13, 0.6, 0.3)),
            ("Azul", (0.15, 0.39, 0.92)), ("Morado", (0.52, 0.27, 0.82)), ("Negro", (0.1, 0.1, 0.12))]


def count_signatures(doc):
    return sum(1 for page in doc for w in page.widgets() if w.field_type == fitz.PDF_WIDGET_TYPE_SIGNATURE)


def _spacer(expand=True, w=8):
    s = QWidget()
    if expand:
        s.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    else:
        s.setFixedWidth(w)
    return s


class PageBox(QLineEdit):
    """Campo del número de página (solo números), con la interfaz de QSpinBox que usa la ventana."""
    valueChanged = Signal(int)

    def __init__(self):
        super().__init__("1")
        self._min, self._max, self._val = 1, 1, 1
        self.setObjectName("pagebox")
        self.setAlignment(Qt.AlignCenter)
        self.setValidator(QIntValidator(1, 99999, self))
        self.editingFinished.connect(self._commit)

    def setRange(self, a, b):
        self._min, self._max = a, b
        self.setValue(min(max(self._val, a), b))

    def value(self):
        return self._val

    def setValue(self, v):
        self._val = v
        self.setText(str(v))

    def _commit(self):
        try:
            v = min(max(int(self.text()), self._min), self._max)
        except ValueError:
            v = self._val
        self.setValue(v)
        if not self.signalsBlocked():
            self.valueChanged.emit(v)
        self.clearFocus()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("EditorPDF", "EditorPDF")
        self.pdf = None
        self._iconed = []          # (widget/acción, icono) para recolorear al cambiar de tema
        self.theme_mode = self.settings.value("theme", "system")
        self.pal = theme.palette_for(self.theme_mode)
        self.setWindowIcon(make_icon())
        self.resize(1440, 900)
        self.setAcceptDrops(True)

        self.view = PageView()
        self.view.color = cfg.get_color(self.settings)
        self.view.width = cfg.get_float(self.settings, "tool/width")
        self.view.fontsize = cfg.get_float(self.settings, "tool/font")
        self.view.get_signature = self.get_signature
        self.view.on_digital_sign = self.digital_sign
        self.view.modified.connect(self.doc_changed)
        self.view.message.connect(lambda m: self.statusBar().showMessage(m, 6000))
        self.view.currentPageChanged.connect(self._page_changed)
        self.view.zoomChanged.connect(self._zoom_changed)
        self.view.widgetClicked.connect(self._widget_clicked)

        self.stack = QStackedWidget()
        self.welcome_host = QWidget()
        self.welcome_host.setObjectName("welcome")
        QVBoxLayout(self.welcome_host).setContentsMargins(0, 0, 0, 0)
        self.stack.addWidget(self.welcome_host)
        self.stack.addWidget(self.view)
        self.setCentralWidget(self.stack)

        self.thumbs = ThumbPanel()
        self.thumbs.pageActivated.connect(self.view.goto_page)
        self.thumbs.orderChanged.connect(self.reorder)
        self.thumbs.action.connect(self.page_action)
        self.thumb_dock = QDockWidget("Páginas", self)
        self.thumb_dock.setObjectName("paginas")
        self.thumb_dock.setWidget(self.thumbs)
        self.thumb_dock.setFeatures(QDockWidget.DockWidgetClosable)
        self.thumb_dock.setMinimumWidth(176)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.thumb_dock)
        self.resizeDocks([self.thumb_dock], [190], Qt.Horizontal)

        self.forms = FormPanel()
        self.forms.applyRequested.connect(self.apply_forms)
        self.forms.fieldFocused.connect(lambda pn, r: self.view.flash(pn, fitz.Rect(r)))
        self.form_dock = QDockWidget("Formulario", self)
        self.form_dock.setObjectName("formulario")
        self.form_dock.setWidget(self.forms)
        self.form_dock.setFeatures(QDockWidget.DockWidgetClosable)
        self.form_dock.setMinimumWidth(320)
        self.addDockWidget(Qt.RightDockWidgetArea, self.form_dock)
        self.form_dock.hide()

        self.doc_actions = []
        self._build_actions()
        self.status_info = QLabel("")
        self.statusBar().addPermanentWidget(self.status_info)
        self.statusBar().setSizeGripEnabled(False)
        self.apply_theme(self.theme_mode)
        self._update_ui()
        self.select_tool(T.HAND)
        if cfg.get_bool(self.settings, "update/auto"):
            QTimer.singleShot(3000, lambda: self.check_updates(manual=False))

    # ================================================================ tema e iconos
    def _ic(self, obj, name, size=20):
        obj.setIcon(icons.icon(name, self.pal, size))
        self._iconed.append((obj, name, size))
        return obj

    def apply_theme(self, mode):
        self.theme_mode = mode
        self.settings.setValue("theme", mode)
        self.pal = theme.apply(QApplication.instance(), mode)
        for obj, name, size in self._iconed:
            try:
                obj.setIcon(icons.icon(name, self.pal, size))
            except RuntimeError:  # widget ya destruido (p. ej. bienvenida reconstruida)
                pass
        self._iconed = [x for x in self._iconed if self._alive(x[0])]
        self.theme_btn.setIcon(icons.icon("sun" if self.pal["dark"] else "moon", self.pal))
        self.view.set_theme(self.pal)
        self.thumbs.set_theme(self.pal)
        for k, a in self.theme_actions.items():
            a.setChecked(k == mode)
        self._build_welcome()

    @staticmethod
    def _alive(obj):
        try:
            obj.objectName()
            return True
        except RuntimeError:
            return False

    def toggle_theme(self):
        self.apply_theme("light" if self.pal["dark"] else "dark")

    # ================================================================ bienvenida
    def recent_files(self):
        v = self.settings.value("recent", [])
        if isinstance(v, str):
            v = [v]
        return [p for p in (v or []) if os.path.exists(p)]

    def add_recent(self, path):
        path = os.path.abspath(path)
        r = [p for p in self.recent_files() if os.path.abspath(p) != path]
        self.settings.setValue("recent", ([path] + r)[:MAX_RECENT])

    def _build_welcome(self):
        lay = self.welcome_host.layout()
        while lay.count():
            w = lay.takeAt(0).widget()
            if w:
                w.deleteLater()
        outer = QWidget()
        ol = QHBoxLayout(outer)
        ol.addStretch(1)
        col = QWidget()
        col.setMaximumWidth(780)
        col.setMinimumWidth(560)
        cl = QVBoxLayout(col)
        cl.setSpacing(18)
        cl.addStretch(1)
        # cabecera
        head = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(make_pixmap(128).scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        head.addWidget(logo)
        tl = QVBoxLayout()
        t = QLabel(APP)
        t.setObjectName("title")
        s = QLabel("Abre, edita, firma y organiza tus PDF.")
        s.setObjectName("subtitle")
        tl.addWidget(t)
        tl.addWidget(s)
        head.addLayout(tl)
        head.addStretch()
        cl.addLayout(head)
        # acciones grandes
        row = QHBoxLayout()
        row.setSpacing(12)
        for text, ic, slot, primary in (("Abrir archivo", "open", self.open_dialog, True),
                                        ("PDF desde imágenes", "images", self.new_from_images, False),
                                        ("Combinar archivos", "merge", self.merge_files, False)):
            b = QPushButton("  " + text)
            b.setObjectName("bigaction")
            b.setIconSize(QSize(22, 22))
            if primary:
                b.setProperty("primary", True)
                b.setIcon(icons.icon(ic, dict(self.pal, text=self.pal["accent_text"]), 22))
            else:
                self._ic(b, ic, 22)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(slot)
            row.addWidget(b, 1)
        cl.addLayout(row)
        # zona para soltar
        drop = QFrame()
        drop.setObjectName("dropzone")
        dl = QVBoxLayout(drop)
        dl.setContentsMargins(20, 26, 20, 26)
        di = QLabel()
        di.setPixmap(icons.pixmap("drop", self.pal["muted"], 34))
        di.setAlignment(Qt.AlignCenter)
        dt = QLabel("Arrastra aquí tus PDF o imágenes")
        dt.setObjectName("subtitle")
        dt.setAlignment(Qt.AlignCenter)
        dl.addWidget(di)
        dl.addWidget(dt)
        cl.addWidget(drop)
        # recientes
        rec = self.recent_files()
        if rec:
            sec = QLabel("RECIENTES")
            sec.setObjectName("section")
            cl.addWidget(sec)
            card = QFrame()
            card.setObjectName("card")
            rl = QVBoxLayout(card)
            rl.setContentsMargins(6, 6, 6, 6)
            rl.setSpacing(0)
            for p in rec:
                b = QPushButton(f"  {os.path.basename(p)}")
                b.setFlat(True)
                b.setProperty("flat", True)
                b.setToolTip(p)
                b.setIconSize(QSize(18, 18))
                self._ic(b, "file", 18)
                b.setCursor(Qt.PointingHandCursor)
                b.clicked.connect(lambda _=False, p=p: self.open_path(p))
                h = QHBoxLayout()
                h.setContentsMargins(0, 0, 0, 0)
                h.addWidget(b, 1)
                folder = QLabel(os.path.dirname(p))
                folder.setObjectName("muted")
                folder.setMaximumWidth(330)
                folder.setText(folder.fontMetrics().elidedText(os.path.dirname(p), Qt.ElideMiddle, 320))
                h.addWidget(folder)
                h.addSpacing(10)
                rl.addLayout(h)
            cl.addWidget(card)
        cl.addStretch(2)
        foot = QLabel(f"Versión {__version__} · {__publisher__}")
        foot.setObjectName("muted")
        foot.setAlignment(Qt.AlignCenter)
        cl.addWidget(foot)
        ol.addWidget(col, 4)
        ol.addStretch(1)
        lay.addWidget(outer)

    # ================================================================ acciones y barras
    def _act(self, text, slot, shortcut=None, needs_doc=True, tip=None, icon=None):
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        if tip or shortcut:
            sc = QKeySequence(shortcut).toString(QKeySequence.NativeText) if shortcut else ""
            a.setToolTip(f"{tip or text.rstrip('…')}" + (f"  ({sc})" if sc else ""))
            a.setStatusTip(tip or "")
        if icon:
            self._ic(a, icon)
        a.triggered.connect(lambda _=False: slot())
        if needs_doc:
            self.doc_actions.append(a)
        return a

    def _tbtn(self, action):
        b = QToolButton()
        b.setDefaultAction(action)
        b.setIconSize(QSize(18, 18))
        b.setAutoRaise(True)
        return b

    def _build_actions(self):
        mb = self.menuBar()
        # ---- Archivo
        m = mb.addMenu("&Archivo")
        self.a_open = self._act("Abrir…", self.open_dialog, QKeySequence.Open, False, icon="open")
        m.addAction(self.a_open)
        m.addAction(self._act("Crear PDF desde imágenes…", self.new_from_images, None, False, icon="images"))
        m.addAction(self._act("Combinar varios archivos en un PDF…", self.merge_files, None, False, icon="merge"))
        m.addSeparator()
        self.a_save = self._act("Guardar", self.save, QKeySequence.Save, icon="save")
        m.addAction(self.a_save)
        m.addAction(self._act("Guardar como…", self.save_as, "Ctrl+Shift+S"))
        m.addSeparator()
        self.a_print = self._act("Imprimir…", self.print_doc, QKeySequence.Print, icon="print")
        m.addAction(self.a_print)
        m.addSeparator()
        m.addAction(self._act("Proteger con contraseña…", self.protect))
        m.addAction(self._act("Quitar contraseña", self.unprotect))
        m.addSeparator()
        m.addAction(self._act("Firmar digitalmente (sin recuadro visible)…", lambda: self.digital_sign(None, None),
                              icon="digsign"))
        m.addAction(self._act("Verificar firmas digitales…", self.verify_signatures))
        m.addSeparator()
        m.addAction(self._act("Cerrar documento", self.close_doc, "Ctrl+W"))
        m.addSeparator()
        self.a_settings = self._act("Ajustes…", self.open_settings, "Ctrl+,", False, icon="settings")
        m.addAction(self.a_settings)
        m.addSeparator()
        m.addAction(self._act("Salir", self.close, None, False))
        # ---- Edición
        m = mb.addMenu("&Edición")
        self.a_undo = self._act("Deshacer", self.undo, QKeySequence.Undo, icon="undo")
        self.a_redo = self._act("Rehacer", self.redo, "Ctrl+Y", icon="redo")
        m.addAction(self.a_undo)
        m.addAction(self.a_redo)
        m.addSeparator()
        self.a_find = self._act("Buscar…", self.focus_search, QKeySequence.Find, icon="search")
        m.addAction(self.a_find)
        m.addAction(self._act("Buscar siguiente", lambda: self.find_step(1), "F3"))
        m.addAction(self._act("Buscar anterior", lambda: self.find_step(-1), "Shift+F3"))
        m.addSeparator()
        m.addAction(self._act("Revisar ortografía del documento…", self.spell_check, "F7"))
        m.addAction(self._act("Copiar el texto de la página", self.copy_page_text))
        m.addAction(self._act("Borrar anotación seleccionada", self.view.delete_selected))
        m.addSeparator()
        m.addAction(self._act("Crear o cambiar mi firma…", self.edit_signature, None, False, icon="sign"))
        # ---- Ver
        m = mb.addMenu("&Ver")
        self.a_zoom_in = self._act("Acercar", lambda: self.view.set_zoom(self.view.zoom * 1.25), QKeySequence.ZoomIn,
                                   icon="zoom_in")
        self.a_zoom_out = self._act("Alejar", lambda: self.view.set_zoom(self.view.zoom / 1.25), QKeySequence.ZoomOut,
                                    icon="zoom_out")
        m.addAction(self.a_zoom_in)
        m.addAction(self.a_zoom_out)
        m.addAction(self._act("Tamaño real (100 %)", lambda: self.view.set_zoom(1.0), "Ctrl+0"))
        self.a_fit = self._act("Ajustar al ancho", self.view.fit_width, "Ctrl+2", icon="fit")
        m.addAction(self.a_fit)
        m.addAction(self._act("Página completa", self.view.fit_page, "Ctrl+1"))
        m.addSeparator()
        self.a_prev = self._act("Página anterior", lambda: self.view.goto_page(self.view.current_page() - 1),
                                "PgUp", icon="left")
        self.a_next = self._act("Página siguiente", lambda: self.view.goto_page(self.view.current_page() + 1),
                                "PgDown", icon="right")
        m.addAction(self.a_prev)
        m.addAction(self.a_next)
        m.addAction(self._act("Primera página", lambda: self.view.goto_page(0), "Home"))
        m.addAction(self._act("Última página", lambda: self.view.goto_page(self.pdf.doc.page_count - 1), "End"))
        m.addSeparator()
        ta = self.thumb_dock.toggleViewAction()
        ta.setText("Panel de páginas")
        self._ic(ta, "panel_left")
        fa = self.form_dock.toggleViewAction()
        fa.setText("Panel de formulario")
        self._ic(fa, "panel_right")
        m.addAction(ta)
        m.addAction(fa)
        m.addSeparator()
        tm = m.addMenu("Tema")
        tg = QActionGroup(self)
        self.theme_actions = {}
        for key, label in (("system", "Como Windows"), ("light", "Claro"), ("dark", "Oscuro")):
            a = QAction(label, self, checkable=True)
            a.triggered.connect(lambda _=False, k=key: self.apply_theme(k))
            tg.addAction(a)
            tm.addAction(a)
            self.theme_actions[key] = a
        # ---- Páginas
        m = mb.addMenu("&Páginas")
        m.addAction(self._act("Girar a la izquierda", lambda: self.page_action("rot_left"), "Ctrl+Shift+-"))
        m.addAction(self._act("Girar a la derecha", lambda: self.page_action("rot_right"), "Ctrl+Shift++"))
        m.addSeparator()
        m.addAction(self._act("Insertar página en blanco", lambda: self.page_action("blank")))
        m.addAction(self._act("Duplicar página", lambda: self.page_action("duplicate")))
        m.addAction(self._act("Insertar páginas desde archivo…", self.insert_from_file))
        m.addAction(self._act("Eliminar página(s)", lambda: self.page_action("delete")))
        m.addSeparator()
        m.addAction(self._act("Extraer páginas a un PDF nuevo…", lambda: self.page_action("extract")))
        m.addAction(self._act("Dividir PDF…", self.split))
        m.addSeparator()
        m.addAction(QAction("Consejo: selecciona varias miniaturas con Ctrl o Mayús y arrástralas para reordenar.",
                            self, enabled=False))
        # ---- Herramientas
        self.tool_menu = mb.addMenu("&Herramientas")
        # ---- Convertir
        m = mb.addMenu("&Convertir")
        m.addAction(self._act("Reconocer texto (OCR) en todo el documento…", lambda: self.run_ocr(True)))
        m.addAction(self._act("Reconocer texto (OCR) en esta página", lambda: self.run_ocr(False)))
        m.addSeparator()
        m.addAction(self._act("PDF a imágenes…", self.export_images))
        m.addAction(self._act("PDF a texto (.txt)…", self.export_text))
        m.addAction(self._act("Imágenes a PDF…", self.new_from_images, None, False))
        m.addSeparator()
        m.addAction(self._act("Comprimir PDF…", self.compress))
        # ---- Ayuda
        m = mb.addMenu("A&yuda")
        m.addAction(self._act("Buscar actualizaciones…", lambda: self.check_updates(manual=True), None, False,
                              icon="update"))
        m.addSeparator()
        m.addAction(self._act("Acerca de…", self.about, None, False))

        # ---- cabecera
        tb = QToolBar("Principal")
        tb.setObjectName("header")
        tb.setMovable(False)
        tb.setIconSize(QSize(18, 18))
        tb.setContextMenuPolicy(Qt.PreventContextMenu)
        self.addToolBar(tb)
        for a in (self.a_open, self.a_save, self.a_print):
            tb.addAction(a)
        tb.addSeparator()
        tb.addAction(self.a_undo)
        tb.addAction(self.a_redo)
        tb.addWidget(_spacer())
        # páginas
        pill = QWidget()
        pill.setObjectName("pill")
        pl = QHBoxLayout(pill)
        pl.setContentsMargins(3, 2, 8, 2)
        pl.setSpacing(2)
        pl.addWidget(self._tbtn(self.a_prev))
        self.page_spin = PageBox()
        self.page_spin.setFixedWidth(48)
        self.page_spin.valueChanged.connect(lambda v: self.view.goto_page(v - 1))
        pl.addWidget(self.page_spin)
        self.page_total = QLabel("/ 0")
        pl.addWidget(self.page_total)
        pl.addWidget(self._tbtn(self.a_next))
        tb.addWidget(pill)
        tb.addWidget(_spacer(False, 10))
        # zoom
        pill = QWidget()
        pill.setObjectName("pill")
        pl = QHBoxLayout(pill)
        pl.setContentsMargins(3, 2, 3, 2)
        pl.setSpacing(2)
        pl.addWidget(self._tbtn(self.a_zoom_out))
        self.zoom_box = QComboBox()
        self.zoom_box.setEditable(True)
        self.zoom_box.addItems(["50%", "75%", "100%", "125%", "150%", "200%", "300%", "400%",
                                "Ajustar ancho", "Página completa"])
        self.zoom_box.setFixedWidth(84)
        self.zoom_box.lineEdit().setAlignment(Qt.AlignCenter)
        self.zoom_box.activated.connect(self._zoom_box_changed)
        self.zoom_box.lineEdit().returnPressed.connect(self._zoom_box_changed)
        pl.addWidget(self.zoom_box)
        pl.addWidget(self._tbtn(self.a_zoom_in))
        pl.addWidget(self._tbtn(self.a_fit))
        tb.addWidget(pill)
        tb.addWidget(_spacer())
        # búsqueda
        self.search_box = QLineEdit()
        self.search_box.setObjectName("search")
        self.search_box.setPlaceholderText("Buscar en el documento")
        self.search_box.setFixedWidth(240)
        self.search_box.setClearButtonEnabled(True)
        self._search_icon = self.search_box.addAction(icons.icon("search", self.pal, 16), QLineEdit.LeadingPosition)
        self._iconed.append((self._search_icon, "search", 16))
        self.search_box.returnPressed.connect(lambda: self.find_step(1))
        self.search_box.textChanged.connect(lambda _: setattr(self, "_search_dirty", True))
        tb.addWidget(self.search_box)
        self.a_find_prev = self._act("Resultado anterior", lambda: self.find_step(-1), icon="up")
        self.a_find_next = self._act("Resultado siguiente", lambda: self.find_step(1), icon="down")
        tb.addAction(self.a_find_prev)
        tb.addAction(self.a_find_next)
        self.search_info = QLabel("")
        self.search_info.setObjectName("muted")
        tb.addWidget(self.search_info)
        tb.addSeparator()
        tb.addAction(ta)
        tb.addAction(fa)
        self.theme_btn = QToolButton()
        self.theme_btn.setToolTip("Cambiar entre tema claro y oscuro")
        self.theme_btn.setIconSize(QSize(18, 18))
        self.theme_btn.clicked.connect(self.toggle_theme)
        tb.addWidget(self.theme_btn)
        tb.addAction(self.a_settings)
        self._search_dirty = True

        # ---- barra contextual de la herramienta
        self.addToolBarBreak()
        pb = QToolBar("Opciones de la herramienta")
        pb.setObjectName("props")
        pb.setMovable(False)
        pb.setContextMenuPolicy(Qt.PreventContextMenu)
        self.addToolBar(pb)
        self.props_bar = pb
        self.tool_icon = QLabel()
        pb.addWidget(self.tool_icon)
        pb.addWidget(_spacer(False, 6))
        self.tool_name = QLabel("")
        self.tool_name.setObjectName("toolname")
        self.tool_name.setMinimumWidth(130)
        pb.addWidget(self.tool_name)
        pb.addWidget(_spacer(False, 12))
        self.tool_hint = QLabel("")
        self.tool_hint.setObjectName("hint")
        pb.addWidget(self.tool_hint)
        pb.addWidget(_spacer())
        # colores
        cw = QWidget()
        cl = QHBoxLayout(cw)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(6)
        lab = QLabel("Color")
        lab.setObjectName("muted")
        cl.addWidget(lab)
        self.swatch_group = []
        for name, rgb in SWATCHES:
            b = QToolButton()
            b.setObjectName("swatch")
            b.setCheckable(True)
            b.setFixedSize(22, 22)
            b.setToolTip(name)
            q = QColor.fromRgbF(*rgb)
            b.setStyleSheet(f"QToolButton#swatch {{ background: {q.name()}; }}")
            b.clicked.connect(lambda _=False, c=rgb: self._pick_color(c))
            cl.addWidget(b)
            self.swatch_group.append((b, rgb))
        self.color_btn = ColorButton(self.view.color)
        self.color_btn.setToolTip("Otro color…")
        self.color_btn.setFixedSize(30, 22)
        self.color_btn.clicked.connect(lambda: QTimer.singleShot(0, lambda: self._pick_color(self.color_btn.color)))
        cl.addWidget(self.color_btn)
        self.opt_color = pb.addWidget(cw)
        # grosor
        ww = QWidget()
        wl = QHBoxLayout(ww)
        wl.setContentsMargins(14, 0, 0, 0)
        lab = QLabel("Grosor")
        lab.setObjectName("muted")
        wl.addWidget(lab)
        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(0.5, 20)
        self.width_spin.setSingleStep(0.5)
        self.width_spin.setSuffix(" pt")
        self.width_spin.setValue(self.view.width)
        self.width_spin.setFixedWidth(92)
        self.width_spin.valueChanged.connect(self._style_changed)
        wl.addWidget(self.width_spin)
        self.opt_width = pb.addWidget(ww)
        # tamaño de letra
        fw = QWidget()
        fl = QHBoxLayout(fw)
        fl.setContentsMargins(14, 0, 0, 0)
        lab = QLabel("Tamaño")
        lab.setObjectName("muted")
        fl.addWidget(lab)
        self.font_spin = QDoubleSpinBox()
        self.font_spin.setRange(4, 200)
        self.font_spin.setSuffix(" pt")
        self.font_spin.setValue(self.view.fontsize)
        self.font_spin.setFixedWidth(92)
        self.font_spin.valueChanged.connect(self._style_changed)
        fl.addWidget(self.font_spin)
        self.opt_font = pb.addWidget(fw)
        self._pick_color(self.view.color)

        # ---- barra lateral de herramientas
        rail = QToolBar("Herramientas")
        rail.setObjectName("rail")
        rail.setMovable(False)
        rail.setOrientation(Qt.Vertical)
        rail.setIconSize(QSize(20, 20))
        rail.setContextMenuPolicy(Qt.PreventContextMenu)
        self.addToolBar(Qt.LeftToolBarArea, rail)
        self.rail = rail
        group = QActionGroup(self)
        group.setExclusive(True)
        self.tool_actions = {}
        self.tool_info = {}
        for entry in TOOLS:
            if entry is None:
                rail.addSeparator()
                self.tool_menu.addSeparator()
                continue
            key, ic, name, hint, sc, opts = entry
            a = QAction(name, self, checkable=True)
            self._ic(a, ic)
            if sc:
                a.setShortcut(QKeySequence(sc))
            a.setToolTip(f"<b>{name}</b>" + (f" &nbsp;<span style='color:{self.pal['muted']}'>{sc}</span>" if sc else "")
                         + f"<br>{hint}")
            a.triggered.connect(lambda _=False, k=key: self.select_tool(k))
            group.addAction(a)
            rail.addAction(a)
            self.tool_menu.addAction(a)
            self.tool_actions[key] = a
            self.tool_info[key] = (ic, name, hint, opts)
            self.doc_actions.append(a)
        self.tool_actions[T.HAND].setChecked(True)

    def select_tool(self, key):
        self.view.set_tool(key)
        self.tool_actions[key].setChecked(True)
        ic, name, hint, opts = self.tool_info[key]
        self.tool_icon.setPixmap(icons.pixmap(ic, self.pal["accent"], 18))
        self.tool_name.setText(name)
        self.tool_hint.setText(hint)
        self.opt_color.setVisible("color" in opts)
        self.opt_width.setVisible("width" in opts)
        self.opt_font.setVisible("font" in opts)

    def _pick_color(self, rgb):
        self.color_btn.set_color(rgb)
        for b, c in self.swatch_group:
            b.setChecked(all(abs(x - y) < 0.01 for x, y in zip(c, rgb)))
        self._style_changed()

    def _update_ui(self):
        has = self.pdf is not None
        for a in self.doc_actions:
            a.setEnabled(has)
        self.stack.setCurrentIndex(1 if has else 0)
        self.props_bar.setVisible(has)
        self.rail.setVisible(has)
        if not has:
            self.thumb_dock.hide()
            self.zoom_box.setEditText("")
        elif cfg.get_bool(self.settings, "show_thumbs") and not self.thumb_dock.isVisible() \
                and not getattr(self, "_thumbs_shown_once", False):
            self._thumbs_shown_once = True
            self.thumb_dock.show()
            self.resizeDocks([self.thumb_dock], [190], Qt.Horizontal)
        self.page_spin.setEnabled(has)
        self.zoom_box.setEnabled(has)
        self.search_box.setEnabled(has)
        if has:
            self.a_undo.setEnabled(bool(self.pdf.undo_stack))
            self.a_redo.setEnabled(bool(self.pdf.redo_stack))
            n = self.pdf.doc.page_count
            self.page_spin.blockSignals(True)
            self.page_spin.setRange(1, max(1, n))
            self.page_spin.blockSignals(False)
            self.page_total.setText(f"/ {n}")
            self.setWindowTitle(f"{'● ' if self.pdf.dirty else ''}{self.pdf.name} — {APP}")
            self.status_info.setText(f"{n} página{'s' if n != 1 else ''}"
                                     + (" · protegido con contraseña" if self.pdf.user_pw else "")
                                     + (" · cambios sin guardar" if self.pdf.dirty else ""))
        else:
            self.page_total.setText("/ 0")
            self.setWindowTitle(APP)
            self.status_info.setText("")

    def _page_changed(self, i):
        self.page_spin.blockSignals(True)
        self.page_spin.setValue(i + 1)
        self.page_spin.blockSignals(False)
        self.thumbs.set_current(i)

    def _zoom_changed(self, z):
        self.zoom_box.setEditText(f"{round(z * 100)}%")

    def _zoom_box_changed(self, *_):
        t = self.zoom_box.currentText().strip()
        if t.startswith("Ajustar"):
            self.view.fit_width()
        elif t.startswith("Página"):
            self.view.fit_page()
        else:
            try:
                self.view.set_zoom(float(t.replace("%", "").replace(",", ".")) / 100)
            except ValueError:
                pass
        self._zoom_changed(self.view.zoom)

    def _style_changed(self, *_):
        self.view.color = self.color_btn.color
        self.view.width = self.width_spin.value()
        self.view.fontsize = self.font_spin.value()

    def _widget_clicked(self, page, xref):
        self.form_dock.show()
        self.forms.focus_field(page, xref)

    # ================================================================ documento
    def set_pdf(self, pdf):
        if getattr(self, "_spell_dlg", None):
            self._spell_dlg.close()
            self._spell_dlg = None
        self.pdf = pdf
        if pdf is None:
            self._build_welcome()
        self.view.set_document(pdf)
        self.thumbs.set_document(pdf)
        self.forms.set_document(pdf)
        self.form_dock.setVisible(self.forms.count() > 0)
        self.search_info.setText("")
        self._search_dirty = True
        self._update_ui()
        if pdf:
            QTimer.singleShot(0, self._initial_zoom)
            self.statusBar().showMessage(f"{pdf.name}: {pdf.doc.page_count} páginas"
                                         + (f", {self.forms.count()} campos de formulario" if self.forms.count() else ""), 8000)

    def _initial_zoom(self):
        if not self.pdf or not self.pdf.doc.page_count:
            return
        mode = cfg.get(self.settings, "initial_zoom")
        self.view.zoom = 0  # fuerza el redibujado
        if mode == "page":
            self.view.fit_page()
        elif mode == "100":
            self.view.set_zoom(1.0)
        else:
            w = self.pdf.doc[0].rect.width
            z = (self.view.viewport().width() - 60) / w
            self.view.set_zoom(min(max(z, 0.3), 1.25))
        self.view.goto_page(0)

    def doc_changed(self, pages=None):
        self.view.refresh(pages)
        self.thumbs.refresh(pages)
        if self.forms.count() or pages is None:
            self.forms.rebuild()
        self._search_dirty = True
        self._update_ui()

    def ask_password(self, path):
        pw, ok = QInputDialog.getText(self, "Contraseña", f"«{os.path.basename(path)}» está protegido.\nContraseña:",
                                      QLineEdit.Password)
        return pw if ok else None

    def load_file(self, path):
        """Carga un archivo como fitz.Document pidiendo la contraseña si hace falta. None si se cancela."""
        pw = None
        while True:
            try:
                return load_any(path, pw), pw
            except PasswordNeeded:
                if pw is not None:
                    QMessageBox.warning(self, APP, "Contraseña incorrecta.")
                pw = self.ask_password(path)
                if pw is None:
                    return None, None
            except Exception as e:
                QMessageBox.critical(self, APP, f"No se pudo abrir «{os.path.basename(path)}»:\n{e}")
                return None, None

    def open_path(self, path):
        if not self.maybe_save():
            return
        doc, pw = self.load_file(path)
        if doc is None:
            return
        pdf = PdfDoc(doc, path if path.lower().endswith(".pdf") else None, pw)
        if path.lower().endswith(".pdf"):
            with open(path, "rb") as fh:
                pdf.source_bytes = fh.read()
        else:
            pdf.dirty = True
        self.settings.setValue("last_dir", os.path.dirname(path))
        self.add_recent(path)
        self.set_pdf(pdf)
        n = count_signatures(pdf.doc)
        if n:
            self.statusBar().showMessage(f"Este PDF tiene {n} firma(s) digital(es). Compruébalas en Archivo > "
                                         "Verificar firmas digitales.", 12000)

    def _last_dir(self):
        d = cfg.get(self.settings, "default_dir")
        if d and os.path.isdir(d):
            return d
        return self.settings.value("last_dir", os.path.expanduser("~/Documents"))

    def open_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Abrir", self._last_dir(), OPEN_FILTER)
        if path:
            self.open_path(path)

    def new_from_images(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Elige las imágenes (en orden)", self._last_dir(), IMAGE_FILTER)
        if not paths or not self.maybe_save():
            return
        try:
            doc = images_to_pdf(sorted(paths))
        except Exception as e:
            QMessageBox.critical(self, APP, f"No se pudieron convertir las imágenes:\n{e}")
            return
        pdf = PdfDoc(doc)
        pdf.dirty = True
        self.set_pdf(pdf)

    def merge_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Archivos a combinar (se unen por orden de nombre)",
                                                self._last_dir(), OPEN_FILTER)
        if not paths:
            return
        if self.pdf is None:
            pdf = PdfDoc(fitz.open())
            for p in sorted(paths):
                d, _ = self.load_file(p)
                if d is not None:
                    pdf.insert_doc(d)
            if pdf.doc.page_count == 0:
                return
            pdf.dirty = True
            self.set_pdf(pdf)
        else:
            self._insert_files(sorted(paths), -1)

    def insert_from_file(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Insertar páginas desde…", self._last_dir(), OPEN_FILTER)
        if paths:
            self._insert_files(sorted(paths), self.view.current_page() + 1)

    def _insert_files(self, paths, at):
        docs = []
        for p in paths:
            d, _ = self.load_file(p)
            if d is not None:
                docs.append(d)
        if not docs:
            return
        with self.pdf.change():
            pos = at
            for d in docs:
                self.pdf.insert_doc(d, pos)
                if pos >= 0:
                    pos += d.page_count
        self.doc_changed(None)
        self.statusBar().showMessage(f"Añadidas {sum(d.page_count for d in docs)} páginas.", 6000)

    def save(self):
        if not self.pdf:
            return False
        if not self.pdf.path:
            return self.save_as()
        return self._save_to(self.pdf.path)

    def save_as(self):
        if not self.pdf:
            return False
        base = self.pdf.path or os.path.join(self._last_dir(), "documento.pdf")
        path, _ = QFileDialog.getSaveFileName(self, "Guardar como", base, "PDF (*.pdf)")
        if not path:
            return False
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        return self._save_to(path)

    def _save_to(self, path):
        if count_signatures(self.pdf.doc) and getattr(self.pdf, "source_bytes", None):
            if not self.pdf.dirty and self.pdf.path and os.path.abspath(path) == os.path.abspath(self.pdf.path):
                self.statusBar().showMessage("No hay cambios que guardar.", 4000)
                return True
            if not self.pdf.dirty:  # copia exacta: conserva las firmas
                with open(path, "wb") as fh:
                    fh.write(self.pdf.source_bytes)
                self.pdf.path = path
                self._update_ui()
                return True
            if QMessageBox.question(self, APP, "Este PDF tiene firmas digitales. Al guardar los cambios, las firmas "
                                    "dejarán de ser válidas.\n\n¿Guardar igualmente?") != QMessageBox.Yes:
                return False
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            self.pdf.save(path)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, APP, f"No se pudo guardar:\n{e}\n\n¿Está abierto en otro programa?")
            return False
        QApplication.restoreOverrideCursor()
        self.settings.setValue("last_dir", os.path.dirname(path))
        self.add_recent(path)
        self._update_ui()
        self.statusBar().showMessage(f"Guardado en {path}", 6000)
        return True

    def maybe_save(self):
        if not self.pdf or not self.pdf.dirty:
            return True
        r = QMessageBox.question(self, APP, f"¿Guardar los cambios de «{self.pdf.name}»?",
                                 QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
        if r == QMessageBox.Save:
            return self.save()
        return r == QMessageBox.Discard

    def close_doc(self):
        if self.maybe_save():
            self.set_pdf(None)

    def closeEvent(self, e):
        if self.maybe_save():
            e.accept()
        else:
            e.ignore()

    def undo(self):
        if self.pdf and self.pdf.undo():
            self.view.sel = None
            self.doc_changed(None)

    def redo(self):
        if self.pdf and self.pdf.redo():
            self.view.sel = None
            self.doc_changed(None)

    # ================================================================ arrastrar archivos
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if not paths:
            return
        if self.pdf is None:
            self.open_path(paths[0])
            if self.pdf and len(paths) > 1:
                self._insert_files(paths[1:], -1)
            return
        box = QMessageBox(self)
        box.setWindowTitle(APP)
        box.setText("¿Qué quieres hacer con " + ("este archivo?" if len(paths) == 1 else f"estos {len(paths)} archivos?"))
        b_add = box.addButton("Añadir al final", QMessageBox.AcceptRole)
        b_here = box.addButton("Insertar tras esta página", QMessageBox.AcceptRole)
        b_open = box.addButton("Abrir", QMessageBox.AcceptRole)
        box.addButton("Cancelar", QMessageBox.RejectRole)
        theme.fit_buttons(box)
        box.exec()
        c = box.clickedButton()
        if c == b_add:
            self._insert_files(paths, -1)
        elif c == b_here:
            self._insert_files(paths, self.view.current_page() + 1)
        elif c == b_open:
            self.open_path(paths[0])

    # ================================================================ páginas
    def target_pages(self):
        sel = self.thumbs.selected_pages()
        return sel if len(sel) > 1 else [self.view.current_page()]

    def page_action(self, key):
        if not self.pdf:
            return
        pages = self.target_pages()
        n = self.pdf.doc.page_count
        if key == "extract":
            self._extract(pages)
            return
        if key == "delete":
            if len(pages) >= n:
                QMessageBox.information(self, APP, "No se pueden eliminar todas las páginas.")
                return
            txt = f"la página {pages[0] + 1}" if len(pages) == 1 else f"{len(pages)} páginas"
            if QMessageBox.question(self, APP, f"¿Eliminar {txt}?") != QMessageBox.Yes:
                return
        with self.pdf.change():
            if key == "rot_left":
                self.pdf.rotate(pages, -90)
            elif key == "rot_right":
                self.pdf.rotate(pages, 90)
            elif key == "delete":
                self.pdf.delete(pages)
            elif key == "duplicate":
                self.pdf.duplicate(pages)
            elif key == "blank":
                self.pdf.insert_blank(pages[-1] + 1, like=pages[-1])
        self.doc_changed(None)
        if key == "blank":
            self.view.goto_page(pages[-1] + 1)

    def reorder(self, order):
        with self.pdf.change():
            self.pdf.reorder(order)
        self.doc_changed(None)
        self.statusBar().showMessage("Páginas reordenadas.", 4000)

    def _extract(self, pages):
        base = os.path.splitext(self.pdf.name)[0]
        default = os.path.join(self._last_dir(), f"{base}_paginas.pdf")
        path, _ = QFileDialog.getSaveFileName(self, "Guardar páginas extraídas", default, "PDF (*.pdf)")
        if not path:
            return
        out = self.pdf.extract(pages)
        out.save(path, garbage=3, deflate=True)
        self.statusBar().showMessage(f"{len(pages)} páginas guardadas en {path}", 6000)

    def split(self):
        n = self.pdf.doc.page_count
        d = SplitDialog(self, n)
        if d.exec() != QDialog.Accepted:
            return
        try:
            if d.r_every.isChecked():
                k = d.every.value()
                groups = [list(range(s, min(s + k, n))) for s in range(0, n, k)]
            else:
                groups = parse_ranges(d.ranges.text(), n)
        except ValueError as e:
            QMessageBox.warning(self, APP, str(e))
            return
        folder = QFileDialog.getExistingDirectory(self, "Carpeta donde guardar las partes", self._last_dir())
        if not folder:
            return
        base = os.path.splitext(self.pdf.name)[0]
        for k, g in enumerate(groups, 1):
            out = self.pdf.extract(g)
            out.save(os.path.join(folder, f"{base}_parte{k:02d}.pdf"), garbage=3, deflate=True)
        QMessageBox.information(self, APP, f"Creados {len(groups)} archivos en:\n{folder}")

    # ================================================================ formularios
    def apply_forms(self):
        ch = self.forms.changes()
        if not ch:
            self.statusBar().showMessage("No hay cambios en el formulario.", 4000)
            return
        result = {}
        with self.pdf.change():
            result["pages"] = FormPanel.apply(self.pdf.doc, ch)
        self.doc_changed(result["pages"])
        self.statusBar().showMessage(f"Formulario actualizado ({len(ch)} campos).", 5000)

    # ================================================================ búsqueda
    def focus_search(self):
        self.search_box.setFocus()
        self.search_box.selectAll()

    def find_step(self, step):
        if not self.pdf:
            return
        text = self.search_box.text().strip()
        if self._search_dirty:
            n = self.view.search(text)
            self._search_dirty = False
            if not text:
                self.search_info.setText("")
                return
            if not n:
                self.search_info.setText(" Sin resultados ")
                return
            self.view.show_result(0)
        elif self.view.results:
            self.view.show_result(self.view.cur_result + step)
        if self.view.results:
            self.search_info.setText(f" {self.view.cur_result + 1} de {len(self.view.results)} ")

    def copy_page_text(self):
        t = self.pdf.doc[self.view.current_page()].get_text()
        QApplication.clipboard().setText(t)
        self.statusBar().showMessage("Texto de la página copiado." if t.strip() else
                                     "La página no tiene texto (prueba con el OCR).", 5000)

    # ================================================================ firma
    def get_signature(self):
        if not os.path.exists(SIGNATURE):
            if SignatureDialog(self, SIGNATURE).exec() != QDialog.Accepted:
                return None
        return SIGNATURE

    def edit_signature(self):
        if SignatureDialog(self, SIGNATURE).exec() == QDialog.Accepted:
            self.statusBar().showMessage("Firma guardada. Usa la herramienta «Firmar» para ponerla.", 6000)

    # ================================================================ convertir
    def run_ocr(self, whole):
        engine, info = ocr.create_engine()
        if engine is None:
            QMessageBox.warning(self, APP, info)
            return
        doc = self.pdf.doc
        if whole:
            pages = [i for i in range(doc.page_count) if not doc[i].get_text().strip()]
            if not pages:
                if QMessageBox.question(self, APP, "Todas las páginas ya tienen texto. ¿Pasar el OCR igualmente?") != QMessageBox.Yes:
                    return
                pages = list(range(doc.page_count))
        else:
            cur = self.view.current_page()
            if doc[cur].get_text().strip():
                if QMessageBox.question(self, APP, "Esta página ya tiene texto. ¿Pasar el OCR igualmente?") != QMessageBox.Yes:
                    return
            pages = [cur]
        prog = QProgressDialog(f"Reconociendo texto ({info})…", "Cancelar", 0, len(pages), self)
        prog.setWindowTitle("OCR")
        prog.setWindowModality(Qt.WindowModal)
        prog.setMinimumDuration(0)
        total = 0
        done = []
        try:
            with self.pdf.change():
                for k, i in enumerate(pages):
                    if prog.wasCanceled():
                        break
                    prog.setLabelText(f"Reconociendo texto ({info})… página {i + 1}")
                    QApplication.processEvents()
                    total += ocr.ocr_page(self.pdf.doc[i], engine)
                    done.append(i)
                    prog.setValue(k + 1)
                self.pdf.fonts_added = True
        except Exception as e:
            prog.close()
            QMessageBox.critical(self, APP, f"Error en el OCR:\n{e}")
            self.doc_changed(None)
            return
        prog.close()
        self.doc_changed(done)
        QMessageBox.information(self, APP, f"OCR terminado: {len(done)} páginas, {total} palabras reconocidas.\n"
                                           "Ya puedes buscar, copiar y editar ese texto.")

    def export_images(self):
        n = self.pdf.doc.page_count
        d = ExportImagesDialog(self, n, self.view.current_page())
        if d.exec() != QDialog.Accepted:
            return
        try:
            pages = [i for g in parse_ranges(d.pages.text(), n) for i in g]
        except ValueError as e:
            QMessageBox.warning(self, APP, str(e))
            return
        folder = QFileDialog.getExistingDirectory(self, "Carpeta de destino", self._last_dir())
        if not folder:
            return
        prog = QProgressDialog("Exportando…", "Cancelar", 0, len(pages), self)
        prog.setWindowModality(Qt.WindowModal)
        prog.setMinimumDuration(300)
        base = os.path.splitext(self.pdf.name)[0]
        for k, i in enumerate(pages):
            if prog.wasCanceled():
                break
            self.pdf.export_images([i], folder, base, d.fmt.currentData(), d.dpi.value())
            prog.setValue(k + 1)
            QApplication.processEvents()
        prog.close()
        self.statusBar().showMessage(f"Imágenes guardadas en {folder}", 6000)
        os.startfile(folder)

    def export_text(self):
        base = os.path.splitext(self.pdf.name)[0]
        path, _ = QFileDialog.getSaveFileName(self, "Guardar texto", os.path.join(self._last_dir(), base + ".txt"),
                                              "Texto (*.txt)")
        if path:
            self.pdf.export_text(path)
            self.statusBar().showMessage(f"Texto guardado en {path}", 6000)

    def compress(self):
        d = CompressDialog(self)
        if d.exec() != QDialog.Accepted:
            return
        dpi, q = d.level.currentData()
        base = os.path.splitext(self.pdf.name)[0]
        path, _ = QFileDialog.getSaveFileName(self, "Guardar PDF comprimido",
                                              os.path.join(self._last_dir(), base + "_comprimido.pdf"), "PDF (*.pdf)")
        if not path:
            return
        if self.pdf.path and os.path.abspath(path) == os.path.abspath(self.pdf.path):
            QMessageBox.warning(self, APP, "Elige otro nombre: el comprimido se guarda como archivo nuevo.")
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            before = len(self.pdf.doc.tobytes(garbage=3, deflate=True))
            self.pdf.compress_to(path, dpi, q)
            after = os.path.getsize(path)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, APP, f"No se pudo comprimir:\n{e}")
            return
        QApplication.restoreOverrideCursor()
        pct = 100 - after * 100 / max(before, 1)
        QMessageBox.information(self, APP, f"Antes: {before / 1048576:.2f} MB\nDespués: {after / 1048576:.2f} MB"
                                           f"\nAhorro: {max(pct, 0):.0f} %\n\n{path}")

    # ================================================================ imprimir y seguridad
    def print_doc(self):
        printer = QPrinter(QPrinter.HighResolution)
        n = self.pdf.doc.page_count
        dlg = QPrintDialog(printer, self)
        dlg.setMinMax(1, n)
        dlg.setFromTo(1, n)
        if dlg.exec() != QDialog.Accepted:
            return
        first, last = printer.fromPage(), printer.toPage()
        if first == 0:
            first, last = 1, n
        painter = QPainter()
        if not painter.begin(printer):
            QMessageBox.warning(self, APP, "No se pudo iniciar la impresión.")
            return
        prog = QProgressDialog("Imprimiendo…", "Cancelar", 0, last - first + 1, self)
        prog.setWindowModality(Qt.WindowModal)
        for k, i in enumerate(range(first - 1, last)):
            if prog.wasCanceled():
                break
            if k:
                printer.newPage()
            pix = self.pdf.doc[i].get_pixmap(dpi=300, alpha=False)
            img = pixmap_to_qimage(pix)
            area = painter.viewport()
            size = img.size()
            size.scale(area.size(), Qt.KeepAspectRatio)
            painter.setViewport(area.x() + (area.width() - size.width()) // 2,
                                area.y() + (area.height() - size.height()) // 2, size.width(), size.height())
            painter.setWindow(img.rect())
            painter.drawImage(0, 0, img)
            painter.setViewport(area)
            painter.setWindow(area)
            prog.setValue(k + 1)
            QApplication.processEvents()
        painter.end()
        prog.close()

    def protect(self):
        d = PasswordDialog(self)
        if d.exec() == QDialog.Accepted:
            self.pdf.user_pw = self.pdf.owner_pw = d.user.text()
            self.pdf.dirty = True
            self._update_ui()
            self.statusBar().showMessage("La contraseña se aplicará al guardar.", 6000)

    def unprotect(self):
        if not (self.pdf.user_pw or self.pdf.owner_pw):
            QMessageBox.information(self, APP, "Este documento no tiene contraseña.")
            return
        self.pdf.user_pw = self.pdf.owner_pw = None
        self.pdf.dirty = True
        self._update_ui()
        self.statusBar().showMessage("La contraseña se quitará al guardar.", 6000)

    # ================================================================ firma digital
    def digital_sign(self, page, rect):
        from . import wincert
        try:
            certs = [c for c in wincert.signing_certificates() if c.personal]
        except Exception as e:
            QMessageBox.critical(self, APP, f"No se pudieron leer los certificados de Windows:\n{e}")
            return
        if not certs:
            QMessageBox.information(self, APP, "No hay ningún certificado personal con clave privada instalado en "
                                               "Windows (por ejemplo, el de la FNMT o el DNI electrónico).")
            return
        if count_signatures(self.pdf.doc) and self.pdf.dirty:
            if QMessageBox.question(self, APP, "El documento ya tiene firmas y tiene cambios sin guardar: al firmar, "
                                    "las firmas anteriores dejarán de ser válidas.\n\n¿Seguir?") != QMessageBox.Yes:
                return
        d = DigitalSignDialog(self, certs, rect is not None, os.path.exists(SIGNATURE), self.settings)
        if d.exec() != QDialog.Accepted:
            return
        opt = d.values()
        if not opt["cert"].valid_now:
            QMessageBox.warning(self, APP, "Ese certificado está caducado: la firma no sería válida.")
            return
        base = os.path.splitext(self.pdf.name)[0]
        if base.endswith("_firmado"):
            base = base[:-8]
        out, _ = QFileDialog.getSaveFileName(self, "Guardar el PDF firmado",
                                             os.path.join(self._last_dir(), base + "_firmado.pdf"), "PDF (*.pdf)")
        if not out:
            return
        if not out.lower().endswith(".pdf"):
            out += ".pdf"
        src = getattr(self.pdf, "source_bytes", None)
        if self.pdf.dirty or not src:
            src = self.pdf.doc.tobytes(**self.pdf._save_kwargs())
        box = None
        if rect is not None:
            pg = self.pdf.doc[page]
            b = fitz.Rect(rect) * pg.transformation_matrix
            b.normalize()
            box = (b.x0, b.y0, b.x1, b.y1)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.statusBar().showMessage("Firmando…")
        QApplication.processEvents()
        try:
            from . import signing
            warns = signing.sign_pdf(src, out, opt["cert"], page=page or 0, box=box, reason=opt["reason"],
                                     location=opt["location"], show_id=opt["show_id"],
                                     image_path=SIGNATURE if opt["image"] else None, tsa_url=opt["tsa_url"],
                                     ltv=opt["ltv"], password=self.pdf.user_pw)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            msg = str(e)
            low = msg.lower()
            if "timestamp" in low or "tsa" in low or "connect" in low or "timeout" in low:
                msg += "\n\nNo se pudo contactar con el servidor de sellos de tiempo. Prueba otro o quita el sello."
            QMessageBox.critical(self, APP, f"No se pudo firmar:\n{msg}")
            self.statusBar().clearMessage()
            return
        QApplication.restoreOverrideCursor()
        self.pdf.dirty = False  # los cambios pendientes ya van dentro del firmado
        self.open_path(out)
        self.select_tool(T.HAND)
        text = f"Documento firmado y guardado en:\n{out}"
        if warns:
            text += "\n\nAviso: " + "\n".join(warns)
        text += "\n\nSi lo modificas, guárdalo con otro nombre: cualquier cambio invalida la firma."
        QMessageBox.information(self, APP, text)

    def verify_signatures(self):
        if not count_signatures(self.pdf.doc):
            QMessageBox.information(self, APP, "Este documento no tiene firmas digitales.")
            return
        data = getattr(self.pdf, "source_bytes", None)
        if not data:
            QMessageBox.information(self, APP, "Guarda el documento primero.")
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            from . import signing
            results = signing.verify(data, self.pdf.user_pw)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, APP, f"No se pudieron verificar las firmas:\n{e}")
            return
        QApplication.restoreOverrideCursor()
        show_signature_results(self, results)

    # ================================================================ ortografía
    def spell_check(self):
        from . import spell
        from .spell_ui import SpellCheckDialog
        if spell.get() is None:
            QMessageBox.warning(self, APP, "No se pudo usar el corrector de Windows:\n" + (spell.error() or ""))
            return
        if getattr(self, "_spell_dlg", None):
            self._spell_dlg.close()
        self._spell_dlg = SpellCheckDialog(self, self.pdf, self.view, self.view.replace_word)
        self._spell_dlg.show()
        self._spell_dlg.rescan()

    # ================================================================ ajustes
    def open_settings(self):
        d = cfg.SettingsDialog(self, self.settings, self.pal)
        if d.exec() != QDialog.Accepted:
            return
        self.apply_theme(cfg.get(self.settings, "theme"))
        self._build_welcome()
        self.statusBar().showMessage("Ajustes guardados.", 4000)

    # ================================================================ actualizaciones
    def check_updates(self, manual=False):
        from . import updater

        def done(info, err):
            if err:
                if manual:
                    QMessageBox.warning(self, APP, f"No se pudo comprobar si hay actualizaciones:\n{err}")
                return
            if not info or not updater.is_newer(info["version"]):
                if manual:
                    QMessageBox.information(self, APP, f"Tienes la última versión ({__version__}).")
                return
            if not manual and self.settings.value("update/skipped", "") == info["version"]:
                return
            self._offer_update(info)
        if manual:
            self.statusBar().showMessage("Buscando actualizaciones…", 4000)
        self._upd_thread = updater.check_async(self, done)

    def _offer_update(self, info):
        from . import updater
        box = QMessageBox(self)
        box.setWindowTitle("Actualización disponible")
        box.setIcon(QMessageBox.Information)
        box.setText(f"<b>Hay una versión nueva de {APP}: {info['version']}</b><br>Tienes la {__version__}.")
        if info["notes"]:
            box.setInformativeText("Novedades:\n" + info["notes"][:1200])
        can = updater.can_self_update() and info["url"]
        b_now = box.addButton("Actualizar ahora" if can else "Abrir la página de descarga", QMessageBox.AcceptRole)
        b_skip = box.addButton("Saltar esta versión", QMessageBox.DestructiveRole)
        box.addButton("Más tarde", QMessageBox.RejectRole)
        box.setDefaultButton(b_now)
        theme.fit_buttons(box)
        # que no se quede detrás de otras ventanas: la principal queda bloqueada hasta que se responda
        if self.isMinimized():
            self.showNormal()
        self.raise_()
        self.activateWindow()
        box.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        box.show()
        box.raise_()
        box.activateWindow()
        box.exec()
        if box.clickedButton() == b_skip:
            self.settings.setValue("update/skipped", info["version"])
            return
        if box.clickedButton() != b_now:
            return
        if not can:
            import webbrowser
            webbrowser.open(info["page"])
            return
        if not self.maybe_save():
            return
        prog = QProgressDialog("Descargando la actualización…", "Cancelar", 0, 100, self)
        prog.setWindowTitle(APP)
        prog.setWindowModality(Qt.WindowModal)
        prog.setMinimumDuration(0)

        def progress(done, total):
            if total:
                prog.setValue(int(done * 100 / total))
                prog.setLabelText(f"Descargando la actualización… {done / 1048576:.0f} de {total / 1048576:.0f} MB")
            QApplication.processEvents()
        try:
            path = updater.download(info["url"], info["name"], progress, prog.wasCanceled)
        except Exception as e:
            prog.close()
            if "cancel" not in str(e).lower():
                QMessageBox.warning(self, APP, f"No se pudo descargar la actualización:\n{e}")
            return
        prog.close()
        updater.run_installer(path)
        if self.pdf:
            self.pdf.dirty = False
        QApplication.quit()

    def about(self):
        QMessageBox.about(self, f"Acerca de {APP}",
                          f"<h3>{APP}</h3>"
                          f"<p>Versión {__version__}<br>© 2026 {__publisher__}</p>"
                          "<p>Visor y editor de PDF.</p>")


def show_signature_results(parent, results):
    html, details = [], []
    for k, r in enumerate(results, 1):
        if r.get("error"):
            html.append(f"<p><b>Firma {k}</b>: <span style='color:#c00'>no se pudo comprobar</span><br>{r['error']}</p>")
            continue
        if r["ok"]:
            head = "<span style='color:#1a7f37'>✔ Firma válida</span>"
        elif r["intact"] and r["valid"] and not r["trusted"]:
            head = "<span style='color:#b8860b'>⚠ Firma correcta, pero el certificado no es de una entidad de confianza</span>"
        elif not r["intact"]:
            head = "<span style='color:#c00'>✖ El documento se modificó después de firmarlo</span>"
        else:
            head = "<span style='color:#c00'>✖ Firma no válida</span>"
        when = r["tsa_time"] or r["time"]
        when_txt = when.astimezone().strftime("%d/%m/%Y %H:%M:%S") if when else "desconocida"
        origin = "sello de tiempo" if r["tsa_time"] else "reloj del firmante"
        html.append(f"<p><b>Firma {k}</b>: {head}<br>Firmante: <b>{r['signer']}</b><br>Emisor: {r['issuer']}<br>"
                    f"Fecha: {when_txt} ({origin})<br>{r['coverage']} {r['modification']}"
                    + ("<br><span style='color:#c00'>Certificado revocado</span>" if r["revoked"] else "")
                    + "</p>")
        details.append(f"===== Firma {k} =====\n{r.get('details', '')}")
    box = QMessageBox(parent)
    box.setWindowTitle("Firmas digitales")
    box.setTextFormat(Qt.RichText)
    box.setText("".join(html))
    if details:
        box.setDetailedText("\n\n".join(details))
    box.exec()
