"""Panel para rellenar formularios PDF."""
import pymupdf as fitz
from PySide6.QtCore import QEvent, Signal
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QFormLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

TEXT = fitz.PDF_WIDGET_TYPE_TEXT
CHECK = fitz.PDF_WIDGET_TYPE_CHECKBOX
RADIO = fitz.PDF_WIDGET_TYPE_RADIOBUTTON
COMBO = fitz.PDF_WIDGET_TYPE_COMBOBOX
LIST = fitz.PDF_WIDGET_TYPE_LISTBOX
MULTILINE = 4096


def _is_on(value):
    return value not in (None, False, "", "Off", "off", "No")


def read_value(w):
    t = w.field_type
    if t in (CHECK, RADIO):
        return _is_on(w.field_value)
    v = w.field_value
    if isinstance(v, (list, tuple)):
        v = v[0] if v else ""
    return "" if v is None else str(v)


class FormPanel(QWidget):
    applyRequested = Signal()
    fieldFocused = Signal(int, object)   # página, rect

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        self.info = QLabel("")
        self.info.setWordWrap(True)
        lay.addWidget(self.info)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        lay.addWidget(self.scroll, 1)
        self.apply_btn = QPushButton("Aplicar al PDF")
        self.apply_btn.clicked.connect(self.applyRequested.emit)
        lay.addWidget(self.apply_btn)
        self.editors = {}
        self.pdf = None

    def set_document(self, pdf):
        self.pdf = pdf
        self.rebuild()

    def count(self):
        return len(self.editors)

    def rebuild(self):
        self.editors = {}
        host = QWidget()
        form = QFormLayout(host)
        groups = {}
        if self.pdf:
            for page in self.pdf.doc:
                for w in page.widgets():
                    t = w.field_type
                    key = (page.number, w.xref)
                    label = w.field_label or w.field_name or f"Campo {w.xref}"
                    if t == TEXT:
                        if w.field_flags & MULTILINE:
                            ed = QPlainTextEdit(read_value(w))
                            ed.setFixedHeight(70)
                        else:
                            ed = QLineEdit(read_value(w))
                            if w.text_maxlen:
                                ed.setMaxLength(w.text_maxlen)
                    elif t in (CHECK, RADIO):
                        ed = QCheckBox(str(w.on_state()) if t == RADIO else "")
                        ed.setChecked(read_value(w))
                        if t == RADIO:
                            g = groups.setdefault(w.field_name, QButtonGroup(host))
                            g.addButton(ed)
                    elif t in (COMBO, LIST):
                        ed = QComboBox()
                        for c in w.choice_values or []:
                            if isinstance(c, (list, tuple)):
                                ed.addItem(str(c[1]), str(c[0]))
                            else:
                                ed.addItem(str(c), str(c))
                        ed.setEditable(t == COMBO and bool(w.field_flags & (1 << 18)))
                        cur = read_value(w)
                        idx = ed.findData(cur)
                        if idx >= 0:
                            ed.setCurrentIndex(idx)
                        elif ed.isEditable():
                            ed.setEditText(cur)
                    else:
                        continue
                    if w.field_flags & 1:
                        ed.setEnabled(False)
                    ed.installEventFilter(self)
                    ed.setProperty("fkey", key)
                    ed.setProperty("frect", tuple(w.rect))
                    form.addRow(f"{label}  (p. {page.number + 1})", ed)
                    self.editors[key] = (t, ed, w.on_state() if t in (CHECK, RADIO) else None)
        self.scroll.setWidget(host)
        if not self.pdf:
            self.info.setText("Abre un PDF.")
        elif self.editors:
            self.info.setText(f"{len(self.editors)} campos. Rellénalos y pulsa «Aplicar al PDF».")
        else:
            self.info.setText("Este PDF no tiene campos de formulario.")
        self.apply_btn.setEnabled(bool(self.editors))

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.FocusIn and obj.property("fkey") is not None:
            pn, _ = obj.property("fkey")
            self.fieldFocused.emit(pn, obj.property("frect"))
        return False

    def editor_value(self, t, ed, on):
        if t == TEXT:
            return ed.toPlainText() if isinstance(ed, QPlainTextEdit) else ed.text()
        if t in (CHECK, RADIO):
            return ed.isChecked()
        data = ed.currentData()
        return ed.currentText() if ed.isEditable() or data is None else data

    def changes(self):
        """Devuelve {(pagina, xref): valor} solo con lo que ha cambiado."""
        out = {}
        for page in self.pdf.doc:
            for w in page.widgets():
                key = (page.number, w.xref)
                if key not in self.editors:
                    continue
                t, ed, on = self.editors[key]
                new = self.editor_value(t, ed, on)
                if new != read_value(w):
                    out[key] = new
        return out

    @staticmethod
    def apply(doc, changes):
        pages = set()
        # primero lo que se desmarca, luego lo que se marca (grupos de radio)
        for (pn, xref), val in sorted(changes.items(), key=lambda kv: kv[1] is True):
            page = doc[pn]
            for w in page.widgets():
                if w.xref != xref:
                    continue
                if w.field_type in (CHECK, RADIO):
                    w.field_value = w.on_state() if val else "Off"
                else:
                    w.field_value = val
                w.update()
                pages.add(pn)
        return sorted(pages)

    def focus_field(self, page, xref):
        item = self.editors.get((page, xref))
        if item:
            ed = item[1]
            self.scroll.ensureWidgetVisible(ed)
            ed.setFocus()
