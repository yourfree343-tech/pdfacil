"""Prueba de la firma digital desde la interfaz con el certificado real de Windows.

Necesita internet (sello de tiempo y LTV). Uso: python tests/prueba_firma.py muestra.pdf carpeta_salida
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymupdf as fitz
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox

from editor_pdf import dialogs
from editor_pdf import main_window as MW
from editor_pdf import view as V

src, out = sys.argv[1], sys.argv[2]
app = QApplication([])
QMessageBox.information = staticmethod(lambda *a, **k: print("INFO:", a[2].replace("\n", " | ")))
QMessageBox.critical = staticmethod(lambda *a, **k: print("ERROR:", a[2]))
QMessageBox.warning = staticmethod(lambda *a, **k: print("AVISO:", a[2]))
QMessageBox.question = staticmethod(lambda *a, **k: (print("PREGUNTA:", a[2][:90]), QMessageBox.Yes)[1])
dialogs.DigitalSignDialog.exec = lambda self: (self.reason.setText("Prueba"), QDialog.Accepted)[1]
QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (os.path.join(out, "ui_firmado.pdf"), ""))
results = []
MW.show_signature_results = lambda parent, r: results.extend(r)

win = MW.MainWindow()
win.show()
win.open_path(src)
app.processEvents()
view = win.view
# un cambio sin guardar antes de firmar: debe ir dentro del firmado
win.page_action("rot_right")
win.page_action("rot_left")
view.set_tool(V.T.DIGSIGN)
a = view.to_scene_rect(0, fitz.Rect(330, 600, 331, 601)).topLeft()
b = view.to_scene_rect(0, fitz.Rect(530, 670, 531, 671)).topLeft()
view.drag = {"i": 0, "sp": a, "p": view.to_page(0, a), "moved": True}


class Ev:
    def button(self):
        return Qt.LeftButton

    def position(self):
        return view.mapFromScene(b).toPointF()


view.mouseReleaseEvent(Ev())
print("abierto ahora:", win.pdf.path, "| firmas:", MW.count_signatures(win.pdf.doc))
win.verify_signatures()
for r in results:
    print("verificación:", r.get("ok"), r.get("signer", "")[:20] + "…", r.get("coverage"), r.get("tsa_time"))
# guardar sin cambios conserva la firma; con cambios avisa
win._save_to(os.path.join(out, "copia.pdf"))
print("copia idéntica:", open(os.path.join(out, "copia.pdf"), "rb").read() == open(os.path.join(out, "ui_firmado.pdf"), "rb").read())
win.page_action("rot_right")
win._save_to(os.path.join(out, "modificado.pdf"))
