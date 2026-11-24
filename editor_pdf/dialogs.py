"""Diálogos de la aplicación."""
import os
import shutil

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton,
    QRadioButton, QSpinBox, QVBoxLayout, QWidget,
)

from .document import IMAGE_FILTER
from .spell_ui import SpellTextEdit


def rgb_to_qcolor(c):
    return QColor.fromRgbF(*c)


def qcolor_to_rgb(q):
    return (q.redF(), q.greenF(), q.blueF())


class ColorButton(QPushButton):
    def __init__(self, color=(0, 0, 0), parent=None):
        super().__init__(parent)
        self.setObjectName("colorbtn")
        self.setFixedSize(34, 24)
        self.setToolTip("Color")
        self.set_color(color)
        self.clicked.connect(self._pick)

    def set_color(self, c):
        self.color = tuple(c)
        q = rgb_to_qcolor(self.color)
        self.setStyleSheet(f"QPushButton#colorbtn {{ background:{q.name()}; border:2px solid rgba(128,128,128,0.75); }}")

    def _pick(self):
        q = QColorDialog.getColor(rgb_to_qcolor(self.color), self, "Elige un color")
        if q.isValid():
            self.set_color(qcolor_to_rgb(q))


class TextDialog(QDialog):
    """Pide un texto con tamaño, color y (opcional) tipo de letra."""

    def __init__(self, parent, title, text="", size=12.0, color=(0, 0, 0), font_opts=False,
                 family="sans", bold=False, italic=False):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(600, 280)
        lay = QVBoxLayout(self)
        self.edit = SpellTextEdit(text)
        lay.addWidget(self.edit)
        row = QHBoxLayout()
        row.addWidget(QLabel("Tamaño:"))
        self.size = QDoubleSpinBox()
        self.size.setRange(4, 200)
        self.size.setDecimals(1)
        self.size.setValue(size)
        row.addWidget(self.size)
        row.addWidget(QLabel("Color:"))
        self.color = ColorButton(color)
        row.addWidget(self.color)
        if font_opts:
            self.family = QComboBox()
            for key, label in (("sans", "Sin serifa (Arial)"), ("serif", "Con serifa (Times)"), ("mono", "Monoespaciada (Courier)")):
                self.family.addItem(label, key)
            self.family.setCurrentIndex(["sans", "serif", "mono"].index(family))
            row.addWidget(self.family)
            self.bold = QCheckBox("Negrita")
            self.bold.setChecked(bold)
            self.italic = QCheckBox("Cursiva")
            self.italic.setChecked(italic)
            row.addWidget(self.bold)
            row.addWidget(self.italic)
        row.addStretch()
        lay.addLayout(row)
        self.font_opts = font_opts
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Aceptar")
        bb.button(QDialogButtonBox.Cancel).setText("Cancelar")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.edit.setFocus()
        self.edit.selectAll()

    @classmethod
    def ask(cls, parent, title, **kw):
        d = cls(parent, title, **kw)
        if d.exec() != QDialog.Accepted:
            return None
        text = d.edit.toPlainText().rstrip("\n")
        if not text.strip():
            return None
        res = dict(text=text, size=d.size.value(), color=d.color.color)
        if d.font_opts:
            res.update(family=d.family.currentData(), bold=d.bold.isChecked(), italic=d.italic.isChecked())
        return res


# ---------------------------------------------------------------- firma
class SignaturePad(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(560, 220)
        self.paths = []
        self.cur = None
        self.pen_color = QColor("#0b2a8a")
        self.setCursor(Qt.CrossCursor)

    def clear(self):
        self.paths = []
        self.update()

    def mousePressEvent(self, e):
        self.cur = QPainterPath(e.position())
        self.cur.lineTo(e.position() + QPointF(0.1, 0.1))
        self.paths.append(self.cur)
        self.update()

    def mouseMoveEvent(self, e):
        if self.cur is not None:
            self.cur.lineTo(e.position())
            self.update()

    def mouseReleaseEvent(self, e):
        self.cur = None

    def _pen(self, scale=1.0):
        return QPen(self.pen_color, 2.6 * scale, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor("#c9cdd3"), 1))
        p.setBrush(Qt.white)
        p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 8, 8)
        p.setPen(QPen(QColor("#bbb"), 1, Qt.DashLine))
        y = self.height() - 50
        p.drawLine(30, y, self.width() - 30, y)
        p.setPen(QColor("#999"))
        p.drawText(30, y + 20, "Firma encima de la línea")
        p.setPen(self._pen())
        for path in self.paths:
            p.drawPath(path)

    def to_image(self):
        if not self.paths:
            return None
        bounds = QRectF()
        for path in self.paths:
            bounds = bounds.united(path.boundingRect())
        bounds = bounds.adjusted(-6, -6, 6, 6)
        s = 4
        img = QImage(int(bounds.width() * s), int(bounds.height() * s), QImage.Format_ARGB32)
        img.fill(Qt.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        p.scale(s, s)
        p.translate(-bounds.topLeft())
        p.setPen(self._pen())
        for path in self.paths:
            p.drawPath(path)
        p.end()
        return img


class SignatureDialog(QDialog):
    def __init__(self, parent, out_path):
        super().__init__(parent)
        self.out_path = out_path
        self.loaded = None
        self.setWindowTitle("Mi firma")
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Dibuja tu firma con el ratón, el lápiz o el dedo, o carga una imagen."))
        self.pad = SignaturePad()
        lay.addWidget(self.pad)
        row = QHBoxLayout()
        b = QPushButton("Borrar")
        b.clicked.connect(self.pad.clear)
        row.addWidget(b)
        for name, col in (("Azul", "#0b2a8a"), ("Negro", "#111111")):
            cb = QPushButton(name)
            cb.clicked.connect(lambda _=False, c=col: self._set_color(c))
            row.addWidget(cb)
        lb = QPushButton("Cargar imagen…")
        lb.clicked.connect(self._load)
        row.addWidget(lb)
        row.addStretch()
        lay.addLayout(row)
        self.info = QLabel("")
        lay.addWidget(self.info)
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Save).setText("Guardar firma")
        bb.button(QDialogButtonBox.Cancel).setText("Cancelar")
        bb.accepted.connect(self._save)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _set_color(self, c):
        self.pad.pen_color = QColor(c)
        self.pad.update()

    def _load(self):
        path, _ = QFileDialog.getOpenFileName(self, "Imagen de la firma", "", IMAGE_FILTER)
        if path:
            self.loaded = path
            self.info.setText("Imagen elegida: " + os.path.basename(path))

    def _save(self):
        os.makedirs(os.path.dirname(self.out_path), exist_ok=True)
        if self.pad.paths:
            self.pad.to_image().save(self.out_path, "PNG")
        elif self.loaded:
            img = QImage(self.loaded)
            if img.isNull():
                shutil.copyfile(self.loaded, self.out_path)
            else:
                img.save(self.out_path, "PNG")
        else:
            self.info.setText("Primero dibuja la firma o carga una imagen.")
            return
        self.accept()


# ---------------------------------------------------------------- otros
def _buttons(dlg, ok="Aceptar"):
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    bb.button(QDialogButtonBox.Ok).setText(ok)
    bb.button(QDialogButtonBox.Cancel).setText("Cancelar")
    bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    return bb


class SplitDialog(QDialog):
    def __init__(self, parent, n):
        super().__init__(parent)
        self.setWindowTitle("Dividir PDF")
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"El documento tiene {n} páginas."))
        self.r_every = QRadioButton("Un archivo cada")
        self.every = QSpinBox()
        self.every.setRange(1, max(1, n))
        self.every.setValue(1)
        row = QHBoxLayout()
        row.addWidget(self.r_every)
        row.addWidget(self.every)
        row.addWidget(QLabel("páginas"))
        row.addStretch()
        lay.addLayout(row)
        self.r_ranges = QRadioButton("Por rangos (un archivo por rango):")
        lay.addWidget(self.r_ranges)
        self.ranges = QLineEdit()
        self.ranges.setPlaceholderText("Ejemplo: 1-3, 4, 5-")
        lay.addWidget(self.ranges)
        g = QButtonGroup(self)
        g.addButton(self.r_every)
        g.addButton(self.r_ranges)
        self.r_every.setChecked(True)
        self.ranges.textEdited.connect(lambda _: self.r_ranges.setChecked(True))
        lay.addWidget(_buttons(self, "Dividir…"))


class ExportImagesDialog(QDialog):
    def __init__(self, parent, n, current):
        super().__init__(parent)
        self.setWindowTitle("PDF a imágenes")
        f = QFormLayout(self)
        self.fmt = QComboBox()
        self.fmt.addItem("PNG (sin pérdida)", "png")
        self.fmt.addItem("JPG (ocupa menos)", "jpg")
        f.addRow("Formato:", self.fmt)
        self.dpi = QSpinBox()
        self.dpi.setRange(36, 600)
        self.dpi.setValue(150)
        self.dpi.setSuffix(" ppp")
        f.addRow("Resolución:", self.dpi)
        self.pages = QLineEdit(f"1-{n}")
        self.pages.setToolTip(f"Página actual: {current + 1}")
        f.addRow("Páginas:", self.pages)
        f.addRow(_buttons(self, "Exportar…"))


class CompressDialog(QDialog):
    LEVELS = [("Buena calidad (150 ppp)", 150, 80), ("Equilibrado (110 ppp)", 110, 65), ("Máxima compresión (72 ppp)", 72, 45)]

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Comprimir PDF")
        f = QFormLayout(self)
        self.level = QComboBox()
        for label, dpi, q in self.LEVELS:
            self.level.addItem(label, (dpi, q))
        self.level.setCurrentIndex(1)
        f.addRow("Nivel:", self.level)
        f.addRow(QLabel("Reduce las imágenes y limpia el archivo.\nSe guarda como un archivo nuevo."))
        f.addRow(_buttons(self, "Comprimir…"))


class DigitalSignDialog(QDialog):
    """Opciones de la firma digital con certificado."""

    def __init__(self, parent, certs, visible, has_handwritten, settings):
        super().__init__(parent)
        self.setWindowTitle("Firma digital con certificado")
        self.setMinimumWidth(560)
        self.certs = certs
        self.settings = settings
        f = QFormLayout(self)
        self.cert = QComboBox()
        for c in certs:
            label = f"{c.nice_name} — {c.issuer} (caduca {c.not_after:%d/%m/%Y})"
            if not c.valid_now:
                label += "  [CADUCADO]"
            self.cert.addItem(label, c.thumb)
        last = settings.value("sign/cert", "")
        idx = self.cert.findData(last)
        if idx >= 0:
            self.cert.setCurrentIndex(idx)
        f.addRow("Certificado:", self.cert)
        self.reason = QLineEdit(settings.value("sign/reason", ""))
        self.reason.setPlaceholderText("Opcional. Ej.: Conformidad, Aprobado…")
        f.addRow("Motivo:", self.reason)
        self.location = QLineEdit(settings.value("sign/location", ""))
        self.location.setPlaceholderText("Opcional. Ej.: Madrid")
        f.addRow("Lugar:", self.location)
        self.show_id = QCheckBox("Mostrar el DNI en el recuadro (el certificado lo incluye igualmente)")
        self.show_id.setChecked(settings.value("sign/show_id", "false") == "true")
        self.image = QCheckBox("Añadir mi firma manuscrita al recuadro")
        self.image.setChecked(has_handwritten and settings.value("sign/image", "true") == "true")
        self.image.setEnabled(has_handwritten)
        if not has_handwritten:
            self.image.setToolTip("Crea tu firma en Edición > Crear o cambiar mi firma")
        if visible:
            f.addRow("", self.show_id)
            f.addRow("", self.image)
        self.tsa = QCheckBox("Añadir sello de tiempo")
        self.tsa.setChecked(settings.value("sign/tsa", "true") == "true")
        self.tsa_server = QComboBox()
        self.tsa_server.setEditable(True)
        from .signing import TSA_SERVERS
        for label, url in TSA_SERVERS:
            self.tsa_server.addItem(url)
        self.tsa_server.setCurrentText(settings.value("sign/tsa_url", TSA_SERVERS[0][1]))
        row = QHBoxLayout()
        row.addWidget(self.tsa)
        row.addWidget(self.tsa_server, 1)
        f.addRow("", row)
        self.ltv = QCheckBox("Validación a largo plazo (LTV): guarda la prueba de que el certificado no estaba revocado")
        self.ltv.setChecked(settings.value("sign/ltv", "true") == "true")
        f.addRow("", self.ltv)
        note = QLabel("El sello de tiempo y la LTV necesitan internet: solo se envía un resumen cifrado del "
                      "documento, nunca el documento.\nWindows puede pedirte confirmación o el PIN del certificado.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#666;")
        f.addRow(note)
        self.tsa.toggled.connect(self.tsa_server.setEnabled)
        self.tsa_server.setEnabled(self.tsa.isChecked())
        f.addRow(_buttons(self, "Firmar…"))

    def values(self):
        s = self.settings
        s.setValue("sign/cert", self.cert.currentData())
        s.setValue("sign/reason", self.reason.text())
        s.setValue("sign/location", self.location.text())
        s.setValue("sign/show_id", "true" if self.show_id.isChecked() else "false")
        s.setValue("sign/image", "true" if self.image.isChecked() else "false")
        s.setValue("sign/tsa", "true" if self.tsa.isChecked() else "false")
        s.setValue("sign/tsa_url", self.tsa_server.currentText().strip())
        s.setValue("sign/ltv", "true" if self.ltv.isChecked() else "false")
        return dict(
            cert=self.certs[self.cert.currentIndex()],
            reason=self.reason.text().strip(),
            location=self.location.text().strip(),
            show_id=self.show_id.isChecked(),
            image=self.image.isChecked() and self.image.isEnabled(),
            tsa_url=self.tsa_server.currentText().strip() if self.tsa.isChecked() else None,
            ltv=self.ltv.isChecked(),
        )


class PasswordDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Proteger con contraseña")
        f = QFormLayout(self)
        self.user = QLineEdit()
        self.user.setEchoMode(QLineEdit.Password)
        self.user2 = QLineEdit()
        self.user2.setEchoMode(QLineEdit.Password)
        f.addRow("Contraseña para abrir:", self.user)
        f.addRow("Repítela:", self.user2)
        f.addRow(QLabel("Se aplica al guardar (cifrado AES de 256 bits)."))
        self.msg = QLabel("")
        self.msg.setStyleSheet("color:#c00")
        f.addRow(self.msg)
        bb = _buttons(self)
        bb.accepted.disconnect()
        bb.accepted.connect(self._check)
        f.addRow(bb)

    def _check(self):
        if not self.user.text():
            self.msg.setText("Escribe una contraseña.")
        elif self.user.text() != self.user2.text():
            self.msg.setText("Las contraseñas no coinciden.")
        else:
            self.accept()
