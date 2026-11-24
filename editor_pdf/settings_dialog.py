"""Ventana de Ajustes y valores por defecto de las preferencias."""
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QStackedWidget, QVBoxLayout,
    QWidget,
)

from . import fileassoc, icons
from .dialogs import ColorButton

DEFAULTS = {
    "theme": "system",
    "startup": "welcome",
    "default_dir": "",
    "initial_zoom": "width",
    "show_thumbs": "true",
    "tool/color": "#db2626",
    "tool/width": "2",
    "tool/font": "12",
    "spell/live": "true",
    "sign/tsa": "true",
    "sign/tsa_url": "http://timestamp.digicert.com",
    "sign/ltv": "true",
    "sign/show_id": "false",
    "update/auto": "true",
}


def get(settings, key):
    v = settings.value(key, DEFAULTS.get(key))
    return DEFAULTS.get(key) if v is None else v


def get_bool(settings, key):
    return str(get(settings, key)).lower() == "true"


def get_float(settings, key):
    try:
        return float(get(settings, key))
    except (TypeError, ValueError):
        return float(DEFAULTS[key])


def get_color(settings):
    q = QColor(str(get(settings, "tool/color")))
    if not q.isValid():
        q = QColor(DEFAULTS["tool/color"])
    return (q.redF(), q.greenF(), q.blueF())


def _b(v):
    return "true" if v else "false"


class SettingsDialog(QDialog):
    def __init__(self, parent, settings, pal):
        super().__init__(parent)
        self.s = settings
        self.pal = pal
        self.setWindowTitle("Ajustes")
        self.resize(820, 560)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 12)
        body = QHBoxLayout()
        body.setSpacing(0)
        self.nav = QListWidget()
        self.nav.setObjectName("settingsnav")
        self.nav.setFixedWidth(210)
        self.nav.setIconSize(QSize(18, 18))
        self.pages = QStackedWidget()
        body.addWidget(self.nav)
        body.addWidget(self.pages, 1)
        root.addLayout(body, 1)
        for title, ic, builder in (("General", "pages", self._general), ("Documento", "file", self._document),
                                   ("Herramientas", "ink", self._tools), ("Firma digital", "digsign", self._sign),
                                   ("Ortografía", "edit", self._spell), ("Archivos PDF", "open", self._files)):
            it = QListWidgetItem(icons.icon(ic, pal, 18), title)
            it.setSizeHint(QSize(0, 40))
            self.nav.addItem(it)
            page = QWidget()
            lay = QVBoxLayout(page)
            lay.setContentsMargins(28, 22, 28, 10)
            h = QLabel(title)
            h.setObjectName("pagetitle")
            lay.addWidget(h)
            builder(lay)
            lay.addStretch()
            self.pages.addWidget(page)
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.nav.setCurrentRow(0)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.RestoreDefaults)
        bb.button(QDialogButtonBox.Ok).setText("Guardar")
        bb.button(QDialogButtonBox.Cancel).setText("Cancelar")
        bb.button(QDialogButtonBox.RestoreDefaults).setText("Valores por defecto")
        bb.button(QDialogButtonBox.RestoreDefaults).clicked.connect(self._restore)
        bb.accepted.connect(self._save)
        bb.rejected.connect(self.reject)
        bl = QHBoxLayout()
        bl.setContentsMargins(16, 0, 16, 0)
        bl.addWidget(bb)
        root.addLayout(bl)
        self.recent_cleared = False

    # ---------- utilidades
    @staticmethod
    def _form(lay):
        f = QFormLayout()
        f.setHorizontalSpacing(18)
        f.setVerticalSpacing(12)
        f.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        lay.addLayout(f)
        return f

    @staticmethod
    def _note(lay, text):
        n = QLabel(text)
        n.setObjectName("muted")
        n.setWordWrap(True)
        lay.addWidget(n)
        return n

    @staticmethod
    def _combo(items, current):
        c = QComboBox()
        for key, label in items:
            c.addItem(label, key)
        i = c.findData(current)
        c.setCurrentIndex(max(i, 0))
        return c

    # ---------- páginas
    def _general(self, lay):
        f = self._form(lay)
        self.theme = self._combo([("system", "Como Windows"), ("light", "Claro"), ("dark", "Oscuro")],
                                 get(self.s, "theme"))
        f.addRow("Tema:", self.theme)
        self.startup = self._combo([("welcome", "Pantalla de bienvenida"), ("last", "Abrir el último documento")],
                                   get(self.s, "startup"))
        f.addRow("Al iniciar:", self.startup)
        row = QHBoxLayout()
        self.default_dir = QLineEdit(get(self.s, "default_dir"))
        self.default_dir.setPlaceholderText("La última carpeta usada")
        row.addWidget(self.default_dir, 1)
        b = QPushButton("Elegir…")
        b.clicked.connect(self._pick_dir)
        row.addWidget(b)
        f.addRow("Carpeta predeterminada:", row)
        self.update_auto = QCheckBox("Buscar actualizaciones al iniciar")
        self.update_auto.setChecked(get_bool(self.s, "update/auto"))
        f.addRow("Actualizaciones:", self.update_auto)
        clear = QPushButton("Borrar la lista de recientes")
        clear.clicked.connect(self._clear_recent)
        f.addRow("Recientes:", clear)

    def _document(self, lay):
        f = self._form(lay)
        self.zoom = self._combo([("width", "Ajustar al ancho"), ("page", "Página completa"), ("100", "Tamaño real (100 %)")],
                                get(self.s, "initial_zoom"))
        f.addRow("Zoom al abrir:", self.zoom)
        self.show_thumbs = QCheckBox("Mostrar el panel de páginas al abrir un documento")
        self.show_thumbs.setChecked(get_bool(self.s, "show_thumbs"))
        f.addRow("", self.show_thumbs)

    def _tools(self, lay):
        f = self._form(lay)
        self.color = ColorButton(get_color(self.s))
        self.color.setFixedSize(48, 26)
        f.addRow("Color por defecto:", self.color)
        self.width = QDoubleSpinBox()
        self.width.setRange(0.5, 20)
        self.width.setSingleStep(0.5)
        self.width.setSuffix(" pt")
        self.width.setValue(get_float(self.s, "tool/width"))
        self.width.setFixedWidth(110)
        f.addRow("Grosor de línea:", self.width)
        self.font = QDoubleSpinBox()
        self.font.setRange(4, 200)
        self.font.setSuffix(" pt")
        self.font.setValue(get_float(self.s, "tool/font"))
        self.font.setFixedWidth(110)
        f.addRow("Tamaño de letra:", self.font)
        self._note(lay, "Es lo que se usa al abrir el programa; luego puedes cambiarlo en la barra de cada herramienta.")

    def _sign(self, lay):
        from .signing import TSA_SERVERS
        f = self._form(lay)
        self.tsa = QCheckBox("Añadir sello de tiempo")
        self.tsa.setChecked(get_bool(self.s, "sign/tsa"))
        f.addRow("", self.tsa)
        self.tsa_url = QComboBox()
        self.tsa_url.setEditable(True)
        for _, url in TSA_SERVERS:
            self.tsa_url.addItem(url)
        self.tsa_url.setCurrentText(get(self.s, "sign/tsa_url"))
        f.addRow("Servidor de sellos:", self.tsa_url)
        self.ltv = QCheckBox("Validación a largo plazo (LTV)")
        self.ltv.setChecked(get_bool(self.s, "sign/ltv"))
        f.addRow("", self.ltv)
        self.show_id = QCheckBox("Mostrar el DNI en el recuadro de la firma")
        self.show_id.setChecked(get_bool(self.s, "sign/show_id"))
        f.addRow("", self.show_id)
        self._note(lay, "Son los valores con los que se abre la ventana de firma; allí puedes cambiarlos en cada firma.")

    def _spell(self, lay):
        f = self._form(lay)
        self.spell_live = QCheckBox("Subrayar las faltas mientras escribo")
        self.spell_live.setChecked(get_bool(self.s, "spell/live"))
        f.addRow("", self.spell_live)
        try:
            from . import spell
            sp = spell.get()
            info = f"Diccionario de Windows: {sp.tag}" if sp else f"No disponible: {spell.error()}"
        except Exception as e:
            info = f"No disponible: {e}"
        self._note(lay, info + ". Las palabras que añades al diccionario se guardan en Windows "
                               "y sirven en otros programas.")

    def _files(self, lay):
        self.assoc_state = QLabel("")
        self.assoc_state.setWordWrap(True)
        lay.addWidget(self.assoc_state)
        row = QHBoxLayout()
        self.b_reg = QPushButton("Añadir a «Abrir con»")
        self.b_reg.clicked.connect(self._register)
        self.b_def = QPushButton("Elegir como predeterminado…")
        self.b_def.setProperty("primary", True)
        self.b_def.clicked.connect(self._make_default)
        self.b_unreg = QPushButton("Quitar")
        self.b_unreg.clicked.connect(self._unregister)
        row.addWidget(self.b_reg)
        row.addWidget(self.b_def)
        row.addWidget(self.b_unreg)
        row.addStretch()
        lay.addLayout(row)
        self._note(lay, "Windows no deja que un programa se ponga como predeterminado por su cuenta. "
                        "«Elegir como predeterminado» registra PDFácil y abre la pantalla de Windows: "
                        "allí, en «.pdf», elige PDFácil.\n\nSolo afecta a tu usuario y no necesita permisos "
                        "de administrador.")
        self._refresh_assoc()

    # ---------- acciones
    def _refresh_assoc(self):
        st = fileassoc.status()
        if fileassoc.is_default():
            txt, col = "✔  PDFácil es el programa predeterminado para los PDF.", self.pal["ok"]
        elif st == "ok":
            txt, col = "PDFácil aparece en «Abrir con», pero no es el predeterminado.", self.pal["muted"]
        elif st == "old":
            txt, col = "Está registrado con otra ubicación del programa. Pulsa «Añadir a «Abrir con»» para actualizarlo.", self.pal["danger"]
        else:
            txt, col = "PDFácil todavía no está registrado para abrir los PDF.", self.pal["muted"]
        self.assoc_state.setText(txt)
        self.assoc_state.setStyleSheet(f"color:{col}; font-weight:600;")
        self.b_unreg.setEnabled(st != "none")

    def _register(self):
        try:
            fileassoc.register()
        except OSError as e:
            QMessageBox.warning(self, "Ajustes", f"No se pudo registrar:\n{e}")
        self._refresh_assoc()

    def _make_default(self):
        self._register()
        try:
            fileassoc.open_default_apps_settings()
        except OSError:
            QMessageBox.information(self, "Ajustes", "Abre Configuración > Aplicaciones > Aplicaciones predeterminadas "
                                                     "y elige PDFácil para «.pdf».")

    def _unregister(self):
        fileassoc.unregister()
        self._refresh_assoc()

    def _pick_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Carpeta predeterminada", self.default_dir.text())
        if d:
            self.default_dir.setText(d)

    def _clear_recent(self):
        self.recent_cleared = True
        self.sender().setText("Se borrará al guardar")
        self.sender().setEnabled(False)

    def _restore(self):
        self.theme.setCurrentIndex(self.theme.findData(DEFAULTS["theme"]))
        self.startup.setCurrentIndex(self.startup.findData(DEFAULTS["startup"]))
        self.default_dir.clear()
        self.zoom.setCurrentIndex(self.zoom.findData(DEFAULTS["initial_zoom"]))
        self.show_thumbs.setChecked(True)
        q = QColor(DEFAULTS["tool/color"])
        self.color.set_color((q.redF(), q.greenF(), q.blueF()))
        self.width.setValue(float(DEFAULTS["tool/width"]))
        self.font.setValue(float(DEFAULTS["tool/font"]))
        self.spell_live.setChecked(True)
        self.tsa.setChecked(True)
        self.tsa_url.setCurrentText(DEFAULTS["sign/tsa_url"])
        self.ltv.setChecked(True)
        self.show_id.setChecked(False)
        self.update_auto.setChecked(True)

    def _save(self):
        s = self.s
        s.setValue("theme", self.theme.currentData())
        s.setValue("startup", self.startup.currentData())
        s.setValue("default_dir", self.default_dir.text().strip())
        s.setValue("initial_zoom", self.zoom.currentData())
        s.setValue("show_thumbs", _b(self.show_thumbs.isChecked()))
        s.setValue("tool/color", QColor.fromRgbF(*self.color.color).name())
        s.setValue("tool/width", str(self.width.value()))
        s.setValue("tool/font", str(self.font.value()))
        s.setValue("spell/live", _b(self.spell_live.isChecked()))
        s.setValue("sign/tsa", _b(self.tsa.isChecked()))
        s.setValue("sign/tsa_url", self.tsa_url.currentText().strip())
        s.setValue("sign/ltv", _b(self.ltv.isChecked()))
        s.setValue("sign/show_id", _b(self.show_id.isChecked()))
        s.setValue("update/auto", _b(self.update_auto.isChecked()))
        if self.recent_cleared:
            s.setValue("recent", [])
        self.accept()
