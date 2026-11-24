"""Interfaz del corrector: subrayado al escribir y revisión del documento completo."""
import pymupdf as fitz
from PySide6.QtCore import Qt
from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QApplication, QDialog, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPlainTextEdit,
    QProgressDialog, QPushButton, QVBoxLayout,
)

from . import spell


# ---------------------------------------------------------------- al escribir
class SpellHighlighter(QSyntaxHighlighter):
    def __init__(self, document, speller):
        super().__init__(document)
        self.speller = speller
        self.fmt = QTextCharFormat()
        self.fmt.setUnderlineStyle(QTextCharFormat.SpellCheckUnderline)
        self.fmt.setUnderlineColor(Qt.red)

    def highlightBlock(self, text):
        try:
            for e in self.speller.check(text):
                self.setFormat(e.start, e.length, self.fmt)
        except Exception:
            pass


class SpellTextEdit(QPlainTextEdit):
    """QPlainTextEdit con subrayado de faltas y sugerencias con el botón derecho."""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        from PySide6.QtCore import QSettings
        live = str(QSettings("EditorPDF", "EditorPDF").value("spell/live", "true")).lower() == "true"
        self.speller = spell.get() if live else None
        self.highlighter = SpellHighlighter(self.document(), self.speller) if self.speller else None

    def contextMenuEvent(self, e):
        menu = self.createStandardContextMenu()
        if self.speller:
            cur = self.cursorForPosition(e.pos())
            block = cur.block()
            pos = cur.positionInBlock()
            hit = next((er for er in self.speller.check(block.text())
                        if er.start <= pos <= er.start + er.length), None)
            if hit:
                word = block.text()[hit.start:hit.start + hit.length]
                first = menu.actions()[0] if menu.actions() else None
                acts = []
                if hit.action == spell.ACTION_DELETE:
                    a = menu.addAction(f"Quitar «{word}» repetida")
                    a.triggered.connect(lambda _=False: self._replace(block, hit, ""))
                    acts.append(a)
                else:
                    sugs = [hit.replacement] if hit.replacement else self.speller.suggest(word, 6)
                    for s in sugs:
                        a = menu.addAction(s)
                        f = a.font()
                        f.setBold(True)
                        a.setFont(f)
                        a.triggered.connect(lambda _=False, s=s: self._replace(block, hit, s))
                        acts.append(a)
                    if not sugs:
                        a = menu.addAction("(sin sugerencias)")
                        a.setEnabled(False)
                        acts.append(a)
                add = menu.addAction(f"Añadir «{word}» al diccionario")
                add.triggered.connect(lambda _=False: (self.speller.add(word), self.highlighter.rehighlight()))
                ign = menu.addAction("Ignorar")
                ign.triggered.connect(lambda _=False: (self.speller.ignore(word), self.highlighter.rehighlight()))
                acts += [add, ign]
                if first:
                    for a in acts:
                        menu.removeAction(a)
                    menu.insertActions(first, acts)
                    menu.insertSeparator(first)
        menu.exec(e.globalPos())

    def _replace(self, block, err, text):
        c = QTextCursor(block)
        start = block.position() + err.start
        end = start + err.length
        if not text:  # palabra repetida: quita también el espacio anterior
            if err.start > 0 and block.text()[err.start - 1] == " ":
                start -= 1
        c.setPosition(start)
        c.setPosition(end, QTextCursor.KeepAnchor)
        c.insertText(text)


# ---------------------------------------------------------------- documento completo
def scan_document(doc, speller, pages=None, progress=None):
    """Busca faltas en el texto del PDF. Devuelve una lista de dicts con página, palabra, rectángulo..."""
    found = []
    pages = list(range(doc.page_count)) if pages is None else pages
    for k, i in enumerate(pages):
        if progress and not progress(k, i):
            break
        page = doc[i]
        lines = {}
        for w in page.get_text("words"):
            lines.setdefault((w[5], w[6]), []).append(w)
        for key in sorted(lines):
            words = sorted(lines[key], key=lambda w: w[7])
            text, spans = "", []
            for w in words:
                if text:
                    text += " "
                spans.append((len(text), len(text) + len(w[4]), w))
                text += w[4]
            for er in speller.check(text):
                a, b = er.start, er.start + er.length
                hit = [w for s, e, w in spans if s < b and e > a]
                if not hit:
                    continue
                rect = fitz.Rect(hit[0][:4])
                for w in hit[1:]:
                    rect |= fitz.Rect(w[:4])
                bad = text[a:b]
                # si la falta es solo parte de una «palabra» del PDF (p. ej. con puntuación), se corrige la palabra entera
                whole = " ".join(w[4] for w in hit)
                found.append(dict(page=i, word=bad, whole=whole, rect=rect, action=er.action,
                                  replacement=er.replacement, context=text, offset=(a, b)))
    return found


class SpellCheckDialog(QDialog):
    """Revisión ortográfica del documento. apply_fix(page, rect, nuevo_texto) hace el cambio en el PDF."""

    def __init__(self, parent, pdf, view, apply_fix):
        super().__init__(parent)
        self.setWindowTitle("Revisar ortografía")
        self.resize(640, 600)
        self.pdf, self.view, self.apply_fix = pdf, view, apply_fix
        self.speller = spell.get()
        self.items = []
        lay = QVBoxLayout(self)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        self.errors = QListWidget()
        self.errors.currentRowChanged.connect(self._select)
        lay.addWidget(self.errors, 2)
        self.context = QLabel("")
        self.context.setWordWrap(True)
        self.context.setTextFormat(Qt.RichText)
        self.context.setObjectName("context")
        lay.addWidget(self.context)
        lay.addWidget(QLabel("Sugerencias:"))
        self.sugs = QListWidget()
        self.sugs.currentTextChanged.connect(lambda t: self.repl.setText(t))
        self.sugs.itemDoubleClicked.connect(lambda _: self._fix())
        lay.addWidget(self.sugs, 1)
        row = QHBoxLayout()
        row.addWidget(QLabel("Cambiar por:"))
        self.repl = QLineEdit()
        self.repl.returnPressed.connect(self._fix)
        row.addWidget(self.repl, 1)
        lay.addLayout(row)
        btns = QGridLayout()
        btns.setHorizontalSpacing(8)
        btns.setVerticalSpacing(8)
        for k, (label, slot) in enumerate((("Corregir", self._fix), ("Ignorar", self._ignore_one),
                                           ("Ignorar todas", self._ignore_all), ("Añadir al diccionario", self._add),
                                           ("Volver a revisar", self.rescan))):
            b = QPushButton(label)
            b.clicked.connect(slot)
            btns.addWidget(b, k // 3, k % 3)
            if label == "Corregir":
                b.setDefault(True)
                self.fix_btn = b
        lay.addLayout(btns)
        note = QLabel("La corrección reescribe la palabra en el PDF con una fuente parecida. "
                      "Se puede deshacer con Ctrl+Z.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#666;")
        lay.addWidget(note)

    def rescan(self):
        doc = self.pdf.doc
        prog = QProgressDialog("Revisando ortografía…", "Cancelar", 0, doc.page_count, self)
        prog.setWindowModality(Qt.WindowModal)
        prog.setMinimumDuration(400)

        def progress(k, i):
            prog.setValue(k)
            QApplication.processEvents()
            return not prog.wasCanceled()
        self.items = scan_document(doc, self.speller, progress=progress)
        prog.close()
        self._fill()
        if not any(doc[i].get_text().strip() for i in range(doc.page_count)):
            self.status.setText("El documento no tiene texto. Si es un escaneo, pasa antes el OCR (menú Convertir).")

    def _fill(self, row=0):
        self.errors.blockSignals(True)
        self.errors.clear()
        for it in self.items:
            label = f"Pág. {it['page'] + 1}:  {it['word']}"
            if it["action"] == spell.ACTION_DELETE:
                label += "  (repetida)"
            self.errors.addItem(QListWidgetItem(label))
        self.errors.blockSignals(False)
        n = len(self.items)
        self.status.setText(f"{n} posibles faltas (idioma: {self.speller.tag})." if n else "No se han encontrado faltas. ✔")
        self.fix_btn.setEnabled(bool(n))
        if n:
            self.errors.setCurrentRow(min(row, n - 1))
        else:
            self.context.setText("")
            self.sugs.clear()
            self.repl.clear()

    def _current(self):
        r = self.errors.currentRow()
        return (r, self.items[r]) if 0 <= r < len(self.items) else (r, None)

    def _select(self, r):
        if not (0 <= r < len(self.items)):
            return
        it = self.items[r]
        a, b = it["offset"]
        ctx = it["context"]
        esc = lambda s: s.replace("&", "&amp;").replace("<", "&lt;")
        self.context.setText(esc(ctx[max(0, a - 60):a]) + "<b style='color:#c00'><u>" + esc(ctx[a:b]) + "</u></b>"
                             + esc(ctx[b:b + 60]))
        self.sugs.clear()
        if it["action"] == spell.ACTION_DELETE:
            self.sugs.addItem("")
            self.repl.setText("")
            self.repl.setPlaceholderText("(se quitará la palabra repetida)")
        else:
            sugs = [it["replacement"]] if it["replacement"] else self.speller.suggest(it["word"], 8)
            self.sugs.addItems(sugs)
            self.repl.setPlaceholderText("")
            if sugs:
                self.sugs.setCurrentRow(0)
            else:
                self.repl.setText(it["word"])
        self.view.goto_page(it["page"]) if not self._visible(it) else None
        self.view.flash(it["page"], it["rect"])

    def _visible(self, it):
        return self.view.current_page() == it["page"]

    def _fix(self):
        r, it = self._current()
        if not it:
            return
        new = self.repl.text()
        if it["action"] != spell.ACTION_DELETE and not new.strip():
            return
        # conserva la puntuación pegada a la palabra (p. ej. «prueva,» -> «prueba,»)
        whole = it["whole"]
        new_whole = whole.replace(it["word"], new, 1) if it["word"] in whole else new
        if self.apply_fix(it["page"], it["rect"], new_whole.strip()):
            del self.items[r]
            self._fill(r)

    def _ignore_one(self):
        r, it = self._current()
        if it:
            del self.items[r]
            self._fill(r)

    def _drop_word(self, word):
        r = self.errors.currentRow()
        self.items = [x for x in self.items if x["word"] != word]
        self._fill(r)

    def _ignore_all(self):
        r, it = self._current()
        if it:
            self.speller.ignore(it["word"])
            self._drop_word(it["word"])

    def _add(self):
        r, it = self._current()
        if it:
            self.speller.add(it["word"])
            self._drop_word(it["word"])
