"""Prueba del botón «Buscar actualizaciones» con la ventana abierta (consulta GitHub de verdad).

Comprueba que los avisos se muestran y siempre desde el hilo principal (crear ventanas desde
otro hilo colgaba el programa en la 1.3.1).
Uso: python tests/prueba_actualizacion.py
"""
import os
import sys
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from editor_pdf import main_window as MW
from editor_pdf import updater

app = QApplication([])
main_thread = threading.current_thread()
events = []


def record(kind):
    def f(*a, **k):
        events.append((kind, threading.current_thread() is main_thread, (a[2] if len(a) > 2 else "")[:60]))
    return f


QMessageBox.information = staticmethod(record("info"))
QMessageBox.warning = staticmethod(record("aviso"))
MW.MainWindow._offer_update = lambda self, info: events.append(("oferta", threading.current_thread() is main_thread,
                                                                 info["version"]))
win = MW.MainWindow()
win.settings.setValue("update/auto", "false")


def run_check(label):
    events.clear()
    win.check_updates(manual=True)
    for _ in range(300):  # hasta 30 s
        if events:
            break
        app.processEvents()
        threading.Event().wait(0.1)
    print(label, events)
    return events[:]


ok = True
r = run_check("1) al día:")
ok &= bool(r) and r[0][0] == "info" and r[0][1]
real_is_newer = updater.is_newer
updater.is_newer = lambda remote, local="0.0.1": real_is_newer(remote, "0.0.1")
r = run_check("2) hay versión nueva:")
ok &= bool(r) and r[0][0] == "oferta" and r[0][1]
updater.is_newer = real_is_newer
win.settings.setValue("update/auto", "true")
print("TODO OK" if ok else "FALLO")
QTimer.singleShot(0, app.quit)
sys.exit(0 if ok else 1)
