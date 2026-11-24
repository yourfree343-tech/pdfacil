"""Abre cada ventana y diálogo del programa y guarda una captura (revisión visual).

Uso: python tests/capturas_dialogos.py <carpeta_salida> <light|dark> [muestra.pdf]
Necesita pantalla real (no offscreen) para que salgan las letras.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QInputDialog, QLineEdit, QMessageBox, QProgressDialog

from editor_pdf import dialogs, theme
from editor_pdf import settings_dialog as cfg
from editor_pdf.main_window import MainWindow, show_signature_results
from editor_pdf.spell_ui import SpellCheckDialog

out, mode = sys.argv[1], sys.argv[2]
sample = sys.argv[3] if len(sys.argv) > 3 else None
os.makedirs(out, exist_ok=True)
app = QApplication([])
theme.apply(app, mode)
theme.install_spanish(app)
win = MainWindow()
win.apply_theme(mode)
win.settings.setValue("update/auto", "false")
win.resize(1400, 880)
win.show()
if sample:
    win.open_path(sample)


def make_list():
    certs = []
    try:
        from editor_pdf import wincert
        certs = [c for c in wincert.signing_certificates() if c.personal]
    except Exception:
        pass
    items = [
        ("texto", lambda: dialogs.TextDialog(win, "Añadir texto", text="Texto con una falta: exelente", size=12,
                                             color=(0.1, 0.2, 0.8))),
        ("editar_texto", lambda: dialogs.TextDialog(win, "Editar texto", text="El precio total es de 1.500 euros",
                                                    size=11, color=(0, 0, 0), font_opts=True)),
        ("firma_manuscrita", lambda: dialogs.SignatureDialog(win, os.path.join(out, "firma_tmp.png"))),
        ("dividir", lambda: dialogs.SplitDialog(win, 12)),
        ("exportar_imagenes", lambda: dialogs.ExportImagesDialog(win, 12, 0)),
        ("comprimir", lambda: dialogs.CompressDialog(win)),
        ("contrasena", lambda: dialogs.PasswordDialog(win)),
        ("ajustes", lambda: cfg.SettingsDialog(win, win.settings, win.pal)),
    ]
    if certs:
        items.append(("firma_digital", lambda: dialogs.DigitalSignDialog(win, certs, True, True, win.settings)))
    if win.pdf:
        items.append(("ortografia", lambda: _spell()))

    def about():
        b = QMessageBox(win)
        b.setWindowTitle("Acerca de Editor PDF")
        b.setText("<h3>Editor PDF</h3><p>Versión 1.3.0<br>© 2026 Agencia Daga</p><p>Visor y editor de PDF.</p>")
        b.setIconPixmap(win.windowIcon().pixmap(64, 64))
        return b

    def question():
        b = QMessageBox(QMessageBox.Question, "Editor PDF", "¿Guardar los cambios de «documento.pdf»?",
                        QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, win)
        return b

    def inputd():
        d = QInputDialog(win)
        d.setWindowTitle("Contraseña")
        d.setLabelText("«documento.pdf» está protegido.\nContraseña:")
        d.setTextEchoMode(QLineEdit.Password)
        return d

    def progress():
        p = QProgressDialog("Reconociendo texto (Español)… página 3", "Cancelar", 0, 10, win)
        p.setWindowTitle("OCR")
        p.setValue(4)
        return p
    items += [("acerca_de", about), ("pregunta", question), ("contrasena_abrir", inputd), ("progreso", progress)]
    return items


def _spell():
    d = SpellCheckDialog(win, win.pdf, win.view, lambda *a: False)
    d.show()
    d.rescan()
    return d


items = make_list()
state = {"i": 0, "dlg": None}


def step():
    if state["dlg"] is not None:
        state["dlg"].grab().save(os.path.join(out, f"{mode}_{items[state['i']][0]}.png"))
        state["dlg"].close()
        state["dlg"].deleteLater()
        state["dlg"] = None
        state["i"] += 1
    if state["i"] >= len(items):
        win.grab().save(os.path.join(out, f"{mode}_ventana.png"))
        if win.pdf:
            win.pdf.dirty = False
        win.settings.setValue("update/auto", "true")
        win.settings.setValue("theme", "system")
        app.quit()
        return
    d = items[state["i"]][1]()
    d.show()
    state["dlg"] = d
    QTimer.singleShot(700, step)


QTimer.singleShot(1500, step)
app.exec()
