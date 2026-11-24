"""Actualizaciones desde las versiones (releases) públicas de GitHub.

Cada versión publicada lleva el instalador «EditorPDF-<versión>-instalador.exe» como archivo adjunto.
El programa compara su versión con la última publicada y, si hay una nueva, descarga el instalador
y lo ejecuta; el instalador cierra el programa, lo actualiza y lo vuelve a abrir.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request

from PySide6.QtCore import QObject, QThread, Signal

from . import GITHUB_REPO, __version__

API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
UA = {"User-Agent": "EditorPDF-updater", "Accept": "application/vnd.github+json"}


def parse_version(v):
    nums = re.findall(r"\d+", v or "")
    return tuple(int(n) for n in nums[:4]) + (0,) * (4 - len(nums[:4]))


def latest_release(timeout=8):
    """Devuelve dict(version, notes, url, size, page) de la última versión, o None si no hay ninguna."""
    req = urllib.request.Request(API, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:  # todavía no hay versiones publicadas
            return None
        raise
    asset = next((a for a in data.get("assets", []) if a["name"].lower().endswith("instalador.exe")), None)
    return dict(version=data.get("tag_name", "").lstrip("vV"), notes=data.get("body") or "",
                url=asset["browser_download_url"] if asset else None, size=asset["size"] if asset else 0,
                name=asset["name"] if asset else "", page=data.get("html_url", ""))


def is_newer(remote, local=__version__):
    return parse_version(remote) > parse_version(local)


def download(url, name, progress=None, cancelled=lambda: False):
    folder = os.path.join(tempfile.gettempdir(), "EditorPDF-actualizacion")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, os.path.basename(name) or "EditorPDF-instalador.exe")
    req = urllib.request.Request(url, headers={"User-Agent": UA["User-Agent"]})
    with urllib.request.urlopen(req, timeout=30) as r, open(path + ".part", "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while True:
            if cancelled():
                raise RuntimeError("Descarga cancelada.")
            chunk = r.read(256 * 1024)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)
    os.replace(path + ".part", path)
    return path


def run_installer(path):
    """Lanza el instalador en modo silencioso; cierra y vuelve a abrir el programa él solo."""
    subprocess.Popen([path, "/SILENT", "/SP-", "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS"],
                     close_fds=True, creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))


def can_self_update():
    """Solo se actualiza solo el programa instalado (el .exe), no al ejecutarlo desde el código."""
    return getattr(sys, "frozen", False)


class CheckWorker(QObject):
    """Comprueba en segundo plano para no bloquear la ventana."""
    finished = Signal(object, str)  # info o None, error

    def run(self):
        try:
            self.finished.emit(latest_release(), "")
        except Exception as e:
            self.finished.emit(None, str(e))


def check_async(parent, callback):
    th = QThread(parent)
    w = CheckWorker()
    w.moveToThread(th)
    th.started.connect(w.run)

    def done(info, err):
        callback(info, err)
        th.quit()
    w.finished.connect(done)
    th.finished.connect(w.deleteLater)
    th.finished.connect(th.deleteLater)
    th._worker = w  # mantener la referencia
    th.start()
    return th
