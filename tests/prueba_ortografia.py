"""Prueba del corrector ortográfico. Uso: python tests/prueba_ortografia.py carpeta_salida"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymupdf as fitz
from PySide6.QtWidgets import QApplication, QMessageBox

from editor_pdf import main_window as MW
from editor_pdf.spell_ui import SpellTextEdit

out = sys.argv[1]
os.makedirs(out, exist_ok=True)
ARIAL = r"C:\Windows\Fonts\arial.ttf"
d = fitz.open()
p = d.new_page()
p.insert_text((72, 100), "Informe de la reunion del equipo.", fontsize=16, fontname="Earial", fontfile=ARIAL)
p.insert_text((72, 140), "Esto es una prueva de ortografia, con con palabras mal escritas.", fontsize=11,
              fontname="Earial", fontfile=ARIAL)
p.insert_text((72, 160), "El camion llego tarde pero todo salió bien.", fontsize=11, fontname="Earial", fontfile=ARIAL)
src = os.path.join(out, "faltas.pdf")
d.save(src)

app = QApplication([])
QMessageBox.information = staticmethod(lambda *a, **k: None)
win = MW.MainWindow()
win.resize(1300, 850)
win.show()
win.open_path(src)
app.processEvents()

# subrayado al escribir
ed = SpellTextEdit("Hola, esto tiene una falta: arbol y otra: exelente.")
errs = ed.speller.check(ed.toPlainText())
print("al escribir:", [ed.toPlainText()[e.start:e.start + e.length] for e in errs])

win.spell_check()
dlg = win._spell_dlg
app.processEvents()
print("faltas encontradas:", [(it["page"] + 1, it["word"], it["action"]) for it in dlg.items])
dlg.grab().save(os.path.join(out, "ortografia_dialogo.png"))
# corrige todas con la primera sugerencia
for _ in range(20):
    if not dlg.items:
        break
    dlg.errors.setCurrentRow(0)
    word = dlg.items[0]["word"]
    print(f"  {word!r} -> {dlg.repl.text()!r}")
    n = len(dlg.items)
    dlg._fix()
    if len(dlg.items) == n:
        print("   no se pudo corregir, se ignora")
        dlg._ignore_one()
txt = win.pdf.doc[0].get_text().replace("\xa0", " ")
print("texto final:\n" + txt)
win.view.goto_page(0)
app.processEvents()
win.view.render_visible()
win.pdf.doc[0].get_pixmap(dpi=100, clip=fitz.Rect(60, 80, 520, 175)).save(os.path.join(out, "ortografia_corregido.png"))
dlg.rescan()
print("tras corregir quedan:", [it["word"] for it in dlg.items])
win.pdf.dirty = False
