"""Prueba automática sin pantalla de las funciones principales.

Uso: python tests/prueba_auto.py [carpeta_salida]
"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymupdf as fitz
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import QApplication, QMessageBox

from editor_pdf import main_window as MW
from editor_pdf import ocr
from editor_pdf import view as V
from editor_pdf.document import PasswordNeeded, load_any

out = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp()
os.makedirs(out, exist_ok=True)
ARIAL = r"C:\Windows\Fonts\arial.ttf"

# ---- PDF de muestra
d = fitz.open()
p = d.new_page()
p.insert_text((72, 90), "Contrato de prueba", fontsize=22, fontname="Earial", fontfile=ARIAL)
p.insert_text((72, 130), "El precio total es de 1.250 euros, pagaderos en marzo.", fontsize=12, fontname="Earial", fontfile=ARIAL)
p.insert_text((72, 150), "Segunda línea con más texto para resaltar y tachar.", fontsize=12, fontname="Earial", fontfile=ARIAL)
for name, kind, y in (("nombre", fitz.PDF_WIDGET_TYPE_TEXT, 200), ("acepto", fitz.PDF_WIDGET_TYPE_CHECKBOX, 240),
                      ("ciudad", fitz.PDF_WIDGET_TYPE_COMBOBOX, 280)):
    w = fitz.Widget()
    w.field_name = name
    w.field_type = kind
    w.rect = fitz.Rect(150, y, 400 if kind != fitz.PDF_WIDGET_TYPE_CHECKBOX else 168, y + 18)
    if kind == fitz.PDF_WIDGET_TYPE_COMBOBOX:
        w.choice_values = ["Madrid", "Sevilla", "Bilbao"]
        w.field_value = "Madrid"
    p.insert_text((72, y + 13), name.capitalize() + ":", fontsize=11)
    p.add_widget(w)
src = fitz.open()
sp = src.new_page()
sp.insert_text((72, 100), "Factura escaneada número 77 importe 35,50 €", fontsize=14, fontname="Earial", fontfile=ARIAL)
scan = d.new_page()
scan.insert_image(scan.rect, pixmap=sp.get_pixmap(dpi=200))
r3 = d.new_page()
r3.insert_text((72, 100), "Página girada", fontsize=16)
r3.set_rotation(90)
sample = os.path.join(out, "muestra.pdf")
d.save(sample)

app = QApplication([])
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
QMessageBox.information = staticmethod(lambda *a, **k: None)
QMessageBox.warning = staticmethod(lambda *a, **k: print("AVISO:", a[2] if len(a) > 2 else a))
QMessageBox.critical = staticmethod(lambda *a, **k: print("ERROR:", a[2] if len(a) > 2 else a))
answers = {}
V.TextDialog.ask = classmethod(lambda cls, parent, title, **kw: answers[title](kw))

win = MW.MainWindow()
win.resize(1400, 900)
win.show()
app.processEvents()
win.open_path(sample)
app.processEvents()
pdf, view = win.pdf, win.view
assert pdf.doc.page_count == 3
print("abierto:", pdf.doc.page_count, "páginas, campos:", win.forms.count())
win.grab().save(os.path.join(out, "1_abierto.png"))


class Ev:
    def __init__(self, sp):
        self.sp = sp

    def button(self):
        return Qt.LeftButton

    def position(self):
        return view.mapFromScene(self.sp).toPointF()


def sp_of(i, x, y):
    return view.to_scene_rect(i, fitz.Rect(x, y, x + 0.01, y + 0.01)).topLeft()


def drag(tool, i, a, b):
    view.set_tool(tool) if tool != V.T.SELECT else setattr(view, "tool", tool)
    pa, pb = sp_of(i, *a), sp_of(i, *b)
    view.drag = {"i": i, "sp": pa, "p": view.to_page(i, pa), "moved": True}
    if tool == V.T.INK:
        view.drag["pts"] = [view.to_page(i, pa), view.to_page(i, QPointF((pa.x() + pb.x()) / 2, pb.y())), view.to_page(i, pb)]
    if tool == V.T.SELECT:
        view.drag["move"] = view.sel[1]
    view.mouseReleaseEvent(Ev(pb))


def click(tool, i, a):
    view.set_tool(tool)
    pa = sp_of(i, *a)
    view.drag = {"i": i, "sp": pa, "p": view.to_page(i, pa), "moved": False}
    view.mouseReleaseEvent(Ev(pa))


drag(V.T.HIGHLIGHT, 0, (70, 118), (300, 134))
drag(V.T.STRIKE, 0, (70, 140), (200, 154))
drag(V.T.RECT, 0, (60, 60), (330, 100))
drag(V.T.INK, 0, (400, 400), (500, 450))
drag(V.T.ARROW, 0, (450, 300), (420, 210))
answers["Añadir texto"] = lambda kw: dict(text="Nota añadida: revisar €", size=14, color=(0, 0, 1))
click(V.T.TEXT, 0, (72, 500))


def edit_answer(kw):
    print("  editar, texto original:", repr(kw["text"]), kw["family"], kw["size"])
    return dict(text="El precio total es de 1.500 euros, pagaderos en abril.", size=kw["size"], color=kw["color"],
                family=kw["family"], bold=kw["bold"], italic=kw["italic"])


answers["Editar texto"] = edit_answer
click(V.T.EDIT, 0, (100, 127))
txt = pdf.doc[0].get_text()
assert "1.500" in txt and "1.250" not in txt, txt
P0 = pdf.doc[0]
print("edición de texto OK; anotaciones:", [a.type[1] for a in P0.annots()])

xr = [a.xref for a in P0.annots() if a.type[0] == fitz.PDF_ANNOT_SQUARE][0]
view.select_annot((0, xr))
before = P0.load_annot(xr).rect
drag(V.T.SELECT, 0, (100, 70), (130, 90))
P0 = pdf.doc[0]
print("rect movido:", before, "->", P0.load_annot(view.sel[1]).rect)
xi = [a.xref for a in P0.annots() if a.type[0] == fitz.PDF_ANNOT_INK][0]
view.select_annot((0, xi))
drag(V.T.SELECT, 0, (450, 420), (470, 440))
P0 = pdf.doc[0]
print("tinta movida:", P0.load_annot(view.sel[1]).vertices[0][:1])

img = QImage(300, 100, QImage.Format_ARGB32)
img.fill(0)
pa = QPainter(img)
pa.setPen(QPen(QColor("#0b2a8a"), 4))
pa.drawLine(10, 80, 290, 20)
pa.end()
sig = os.path.join(out, "firma.png")
img.save(sig)
view.get_signature = lambda: sig
click(V.T.SIGN, 0, (450, 650))
print("imágenes en pág 1:", len(pdf.doc[0].get_images()))
answers["Añadir texto"] = lambda kw: dict(text="Texto en página girada", size=12, color=(1, 0, 0))
click(V.T.TEXT, 2, (300, 300))
click(V.T.SIGN, 2, (200, 400))

for k, (t, ed, on) in win.forms.editors.items():
    if t == fitz.PDF_WIDGET_TYPE_TEXT:
        ed.setText("Ana Prueba")
    if t == fitz.PDF_WIDGET_TYPE_CHECKBOX:
        ed.setChecked(True)
    if t == fitz.PDF_WIDGET_TYPE_COMBOBOX:
        ed.setCurrentIndex(1)
win.apply_forms()
P0 = pdf.doc[0]
print("formulario:", {w.field_name: w.field_value for w in P0.widgets()})

win.search_box.setText("euros")
win.find_step(1)
print("búsqueda:", win.search_info.text())

engine, info = ocr.create_engine()
n = ocr.ocr_page(pdf.doc[1], engine)
print("OCR:", info, n, "palabras ->", repr(pdf.doc[1].get_text().strip()[:70]))
win.doc_changed([1])
app.processEvents()
view.goto_page(0)
app.processEvents()
win.grab().save(os.path.join(out, "2_editado.png"))
view.goto_page(2)
app.processEvents()
win.grab().save(os.path.join(out, "3_girada.png"))

win.thumbs.clearSelection()
win.page_action("rot_right")
print("rotación pág 3:", pdf.doc[2].rotation)
win.page_action("duplicate")
print("tras duplicar:", pdf.doc.page_count)
win.reorder([3, 0, 1, 2])
print("reordenado, rotación pág 1:", pdf.doc[0].rotation)
view.goto_page(0)
app.processEvents()
win.page_action("delete")
print("tras borrar:", pdf.doc.page_count)
win.undo()
win.undo()
print("tras 2 deshacer:", pdf.doc.page_count, "rotación pág 1:", pdf.doc[0].rotation)
win.redo()
print("rehacer:", pdf.doc.page_count)

outpdf = os.path.join(out, "resultado.pdf")
assert win._save_to(outpdf)
chk = fitz.open(outpdf)
print("guardado:", chk.page_count, "págs,", os.path.getsize(outpdf), "bytes; texto editado presente:",
      "1.500" in "".join(pg.get_text() for pg in chk))
pdf.compress_to(os.path.join(out, "comprimido.pdf"), 110, 65)
print("comprimido:", os.path.getsize(os.path.join(out, "comprimido.pdf")), "bytes")
pdf.export_images([0], out, "img", "png", 72)
print("png exportado:", os.path.exists(os.path.join(out, "img_pag001.png")))
pdf.user_pw = pdf.owner_pw = "secreto"
win._save_to(os.path.join(out, "protegido.pdf"))
try:
    load_any(os.path.join(out, "protegido.pdf"))
    print("ERROR: abrió sin contraseña")
except PasswordNeeded:
    print("pide contraseña: OK")
print("reabrir con contraseña:", load_any(os.path.join(out, "protegido.pdf"), "secreto").page_count, "págs")
print("TODO OK")
